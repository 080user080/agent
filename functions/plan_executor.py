"""Plan Executor — міст між Planner (core_planner) і TaskRunner (Phase 11).

Конвертує план Planner → TaskRunner Plan, запускає виконання з:
- Live progress через GUI callback
- SessionBudget для kill-switch
- PlanCritic для оцінки (опційно)
- Stop через SessionBudget.stop()

Це Phase 12.3 — GUI-інтеграція Phase 11.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("plan_executor")


@dataclass
class PlanExecutionConfig:
    """Конфігурація виконання плану."""
    max_steps: int = 50
    max_duration_seconds: float = 3600.0  # 1 година
    max_errors: int = 5
    use_critic: bool = False
    auto_confirm: bool = True


@dataclass
class PlanExecutionState:
    """Стан виконання (для GUI)."""
    is_running: bool = False
    current_step: int = 0
    total_steps: int = 0
    plan_name: str = ""
    started_at: float = 0.0
    steps_ok: int = 0
    steps_error: int = 0
    steps_skipped: int = 0
    stop_requested: bool = False


# Тип callback для GUI повідомлень
GUICallback = Callable[[str, Any], None]


class PlanExecutor:
    """Виконує план з live progress для GUI.

    Зв'язує:
    - core_planner.Planner (створює план)
    - logic_task_runner.TaskRunner (виконує план)
    - core_session_budget.SessionBudget (ліміти)
    - GUI queue (live progress)
    """

    def __init__(
        self,
        assistant,  # VoiceAssistant instance
        gui_callback: Optional[GUICallback] = None,
        config: Optional[PlanExecutionConfig] = None,
    ):
        self.assistant = assistant
        self.gui_cb = gui_callback
        self.config = config or PlanExecutionConfig()
        self.state = PlanExecutionState()
        self._stop_flag = False  # Зберігається між execute_plan викликами
        self._lock = threading.Lock()
        self._runner = None
        self._budget = None

    # ─── GUI messaging ────────────────────────────────────────────────────

    def _gui_msg(self, msg_type: str, data: Any = None):
        """Відправити повідомлення в GUI."""
        if self.gui_cb:
            try:
                self.gui_cb(msg_type, data)
            except Exception as e:
                logger.debug("GUI callback error: %s", e)

    def _gui_step_update(self, index: int, status: str, action: str, goal: str = "", detail: str = ""):
        """Оновити конкретний крок у GUI plan_panel."""
        self._gui_msg('step_update', {
            'index': index,
            'status': status,
            'action': action,
            'goal': goal,
            'detail': detail,
        })

    # ─── Plan conversion ──────────────────────────────────────────────────

    @staticmethod
    def planner_steps_to_task_runner_plan(
        steps: List[Dict[str, Any]],
        plan_name: str = "plan",
    ) -> Dict[str, Any]:
        """Конвертувати Planner steps → TaskRunner Plan dict.

        Planner steps format:
            [{"action": "open_program", "args": {"program_name": "notepad"}, "goal": "відкрити блокнот"}, ...]

        TaskRunner Plan format:
            {"name": "plan", "tasks": [{"id": "t1", "kind": "agent_action", "name": "...", "params": {...}}, ...]}
        """
        tasks = []
        for i, step in enumerate(steps):
            action = step.get("action", "noop")
            args = step.get("args", {})
            goal = step.get("goal", "")
            on_error = step.get("on_error", "skip")

            tasks.append({
                "id": f"t{i + 1}",
                "kind": "agent_action",
                "name": goal or f"{action}",
                "params": {
                    "action": action,
                    "args": args,
                    "goal": goal,
                },
                "on_error": on_error,
                "max_retries": 1,
            })

        return {
            "name": plan_name,
            "tasks": tasks,
        }

    # ─── Execution ────────────────────────────────────────────────────────

    def create_plan(self, task: str) -> Optional[List[Dict[str, Any]]]:
        """Створити план через Planner."""
        planner = getattr(self.assistant, 'planner', None)
        if not planner:
            logger.error("Planner не доступний")
            return None

        self._gui_msg('update_status', '🤔 Створюю план...')
        try:
            steps = planner.create_plan(task)
            if not steps:
                logger.warning("Planner повернув порожній план")
                return None
            return steps
        except Exception as e:
            logger.error("Помилка створення плану: %s", e)
            return None

    def execute_plan(
        self,
        steps: List[Dict[str, Any]],
        task: str = "",
    ) -> Dict[str, Any]:
        """Виконати план з live progress.

        Args:
            steps: Список кроків від Planner
            task: Оригінальне завдання

        Returns:
            dict з результатами виконання
        """
        with self._lock:
            if self.state.is_running:
                return {"ok": False, "error": "План вже виконується"}
            self._stop_flag = False  # Скинути stop при новому запуску
            self.state = PlanExecutionState(
                is_running=True,
                total_steps=len(steps),
                plan_name=task[:60] if task else "План",
                started_at=time.time(),
            )

        # Підготувати GUI
        gui_steps = [
            {"action": s.get("action", "?"), "goal": s.get("goal", "")}
            for s in steps
        ]
        self._gui_msg('execution_started', None)
        self._gui_msg('plan_started', gui_steps)

        # SessionBudget
        try:
            from .core_session_budget import SessionBudget, SessionLimits
            self._budget = SessionBudget(
                limits=SessionLimits(
                    max_steps=self.config.max_steps,
                    max_duration_seconds=self.config.max_duration_seconds,
                    max_errors=self.config.max_errors,
                ),
            )
        except Exception:
            self._budget = None

        # Виконання кроків
        results = []
        context = {}
        planner = getattr(self.assistant, 'planner', None)
        if planner:
            context = planner.build_execution_context(task, steps)

        try:
            for i, step in enumerate(steps):
                # Перевірка stop
                if self._stop_flag or self.state.stop_requested:
                    self._mark_remaining_skipped(i, steps)
                    break

                # Перевірка budget
                if self._budget and self._budget.is_exhausted():
                    self._mark_remaining_skipped(i, steps)
                    break

                action = step.get("action", "noop")
                goal = step.get("goal", "")
                args = step.get("args", {})

                self.state.current_step = i
                self._gui_step_update(i, "running", action, goal)
                self._gui_msg('update_status', f'▶ Крок {i + 1}/{len(steps)}: {action}')

                # Підготувати крок (resolve placeholders)
                if planner:
                    try:
                        step = planner.prepare_step(step, context)
                        action = step.get("action", action)
                        args = step.get("args", args)
                    except Exception:
                        pass

                # Виконати крок
                start_time = time.time()
                try:
                    result_text = self._execute_action(action, args)
                    duration = time.time() - start_time
                    success = not result_text.startswith("❌")

                    if success:
                        self.state.steps_ok += 1
                        self._gui_step_update(i, "ok", action, goal)
                        # Оновити контекст
                        if planner:
                            try:
                                context = planner.update_context_from_result(step, result_text, context)
                            except Exception:
                                pass
                    else:
                        self.state.steps_error += 1
                        self._gui_step_update(i, "error", action, goal, detail=result_text[:60])
                        if self._budget:
                            self._budget.record_error()

                    results.append({
                        "step": i,
                        "action": action,
                        "goal": goal,
                        "success": success,
                        "result": result_text[:500],
                        "duration": duration,
                    })

                    if self._budget:
                        self._budget.record_step()

                except Exception as e:
                    self.state.steps_error += 1
                    self._gui_step_update(i, "error", action, goal, detail=str(e)[:60])
                    results.append({
                        "step": i,
                        "action": action,
                        "goal": goal,
                        "success": False,
                        "result": f"Exception: {e}",
                        "duration": time.time() - start_time,
                    })
                    if self._budget:
                        self._budget.record_error()

        finally:
            # Завершити
            with self._lock:
                self.state.is_running = False

            total_time = time.time() - self.state.started_at
            stats = {
                "total": len(steps),
                "ok": self.state.steps_ok,
                "error": self.state.steps_error,
                "skipped": self.state.steps_skipped,
            }
            self._gui_msg('plan_finished', stats)
            self._gui_msg('execution_finished', None)

            # Повідомлення в чат
            summary = (
                f"📊 План виконано: {self.state.steps_ok}/{len(steps)} успішно"
                f" ({self.state.steps_error} помилок)"
                f" за {total_time:.1f}с"
            )
            stopped = self._stop_flag or self.state.stop_requested
            if stopped:
                summary += " ⏹ (зупинено користувачем)"
            self._gui_msg('add_message', ('assistant', summary))
            self._gui_msg('update_status', '✅ Готовий до роботи')

        return {
            "ok": self.state.steps_error == 0 and not stopped,
            "stats": stats,
            "results": results,
            "total_time": total_time,
            "stopped": stopped,
        }

    def _execute_action(self, action: str, args: Dict[str, Any]) -> str:
        """Виконати одну дію через VoiceAssistant."""
        try:
            # Спробувати через execute_action (якщо є)
            if hasattr(self.assistant, 'execute_action'):
                return self.assistant.execute_action(action, args)

            # Спробувати через registry
            registry = getattr(self.assistant, 'registry', None)
            if registry and action in registry.functions:
                func_info = registry.functions[action]
                func = func_info['function']
                result = func(**args) if args else func()
                if isinstance(result, dict):
                    return result.get('message', str(result))
                return str(result)

            return f"❌ Дію '{action}' не знайдено"
        except Exception as e:
            return f"❌ Помилка виконання {action}: {e}"

    def _mark_remaining_skipped(self, from_index: int, steps: List[Dict[str, Any]]):
        """Позначити решту кроків як skipped."""
        for j in range(from_index, len(steps)):
            action = steps[j].get("action", "?")
            goal = steps[j].get("goal", "")
            self._gui_step_update(j, "skipped", action, goal)
            self.state.steps_skipped += 1

    # ─── Stop ─────────────────────────────────────────────────────────────

    def request_stop(self):
        """Запросити зупинку виконання (з GUI кнопки)."""
        self._stop_flag = True
        self.state.stop_requested = True
        if self._budget:
            self._budget.stop("user_gui_stop")
        logger.info("Stop requested by user")

    # ─── Full cycle: plan + execute ───────────────────────────────────────

    def plan_and_execute(self, task: str) -> Dict[str, Any]:
        """Повний цикл: створити план → показати → виконати.

        Викликається з GUI через 'run_plan' action.
        """
        # 1. Створити план
        steps = self.create_plan(task)
        if not steps:
            self._gui_msg('add_message', ('assistant', '❌ Не вдалося створити план'))
            return {"ok": False, "error": "empty_plan"}

        # 2. Показати план в чаті
        plan_text = "📋 **План виконання:**\n"
        for i, s in enumerate(steps):
            plan_text += f"  {i + 1}. `{s.get('action', '?')}` — {s.get('goal', '')}\n"
        self._gui_msg('add_message', ('assistant', plan_text))

        # 3. Виконати
        return self.execute_plan(steps, task)
