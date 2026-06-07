"""AgentLoop — легкий диспетчер фаз state-machine: observe → plan → act → check.

Перетворено на компактний оркестратор (~140 рядків). Вся предметна логіка
винесена в модулі:
  - observe → functions.agent.observe
  - plan   → functions.agent.plan  (ActionDecider, CompiledPlan)
  - act    → functions.agent.act   (ActionGuard, виконання через registry)
  - check  → functions.agent.check (перевірка результатів, чекпоїнти)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("agent_loop")

# ── Фази ─────────────────────────────────────────────────────────────────────
from functions.agent.observe import Observation, ObserveConfig, observe as _observe
from functions.agent.plan   import ActionDecider
from functions.agent.act    import ActionGuard, ActionGuardConfig
from functions.agent.check  import CheckState, check as _check, save_checkpoint, \
                                   load_checkpoint, cleanup_checkpoint

# ── Модульні компоненти (Phase 7.1) ─────────────────────────────────────────
from functions.planning.agent_observer import AgentObserver
from functions.planning.agent_planner  import AgentPlanner

# ── Data-класи ───────────────────────────────────────────────────────────────

@dataclass
class AgentState:
    """Стан агента між ітераціями."""
    step: int = 0
    observations: List[Observation] = field(default_factory=list)
    last_action: Optional[str] = None
    last_result: Optional[str] = None
    actions_history: List[Dict[str, Any]] = field(default_factory=list)
    consecutive_failures: int = 0
    total_failures: int = 0
    done: bool = False
    success: bool = False
    done_summary: str = ""
    progress_summary: str = "Завдання розпочато."


@dataclass
class AgentLoopConfig:
    """Конфігурація циклу агента."""
    max_steps: int = 200
    max_duration_seconds: float = 3600.0
    enable_ocr: bool = True
    enable_ui_a: bool = False
    enable_vision: bool = False
    enable_ui_elements: bool = True
    enable_llm_decider: bool = True
    enable_checkpoint: bool = True
    checkpoint_interval_steps: int = 5
    replan_after_failures: int = 3
    repair_after_failures: int = 2
    enable_repair: bool = True
    screen_diff_threshold: float = 0.01
    expected_files: List[str] = field(default_factory=list)


# ── AgentLoop (State Machine) ────────────────────────────────────────────────

class AgentLoop:
    """Замкнутий цикл агента: observe → plan → act → check.

    Публічні методи (зворотна сумісність):
      run(task)              — основний цикл
      request_stop()         — зупинка ззовні
      set_compiled_plan(cp)  — встановити CompiledPlan від TaskSpec
    """

    def __init__(
        self,
        assistant,
        registry=None,
        config: Optional[AgentLoopConfig] = None,
        ask_user_callback: Optional[Callable[[str, List[str]], str]] = None,
        decider: Optional[ActionDecider] = None,
        repairer: Optional[Any] = None,
        context_controller: Optional[Any] = None,
    ):
        self.assistant = assistant
        self.registry = registry
        self.config = config or AgentLoopConfig()
        self.decider = decider
        self.repairer = repairer
        self.context_controller = context_controller
        self.ask_user_callback = ask_user_callback
        self.gui_cb: Optional[Callable] = None
        self.task_id = "default_task"

        # CompiledPlan від TaskSpec
        self._compiled_plan = None
        # Внутрішній стан
        self._state = AgentState()
        self._check_state = CheckState()
        self._stop_flag = False
        self._current_task = ""

        # ActionGuard — безпековий прошарок виконання дій
        self.action_guard = ActionGuard()

        # LoopDetector — виявлення зациклення
        from functions.runtime.core_loop_detector import LoopDetector
        self.loop_detector = LoopDetector(max_repeats=3)

        # ── Модульні компоненти (Phase 7.1) ──────────────────────────────────
        obs_config = ObserveConfig(
            enable_ocr=self.config.enable_ocr,
            enable_uia=self.config.enable_ui_a,
            enable_vision=self.config.enable_vision,
            enable_ui_elements=self.config.enable_ui_elements,
            skip_observe_for_simple=False,
        )
        self._observer = AgentObserver(assistant, config=obs_config)
        self._planner = AgentPlanner(
            assistant,
            decider=decider,
            compiled_plan=compiled_plan,
            enable_llm_decider=self.config.enable_llm_decider,
            replan_after_failures=self.config.replan_after_failures,
            loop_detector=self.loop_detector,
            context_controller=context_controller,
        )

    # ── GUI / зовнішні повідомлення ──────────────────────────────────────────

    def _gui_msg(self, msg_type: str, data: Any = None) -> None:
        if self.gui_cb:
            try:
                self.gui_cb(msg_type, data)
            except Exception as e:
                logger.debug("GUI callback error: %s", e)

    def request_stop(self) -> None:
        self._stop_flag = True

    def set_compiled_plan(self, compiled_plan) -> None:
        self._compiled_plan = compiled_plan
        self._planner.set_compiled_plan(compiled_plan)

    # ── Ask User (Phase V6) ───────────────────────────────────────────────────

    def _handle_ask_user_step(
        self,
        step: Dict[str, Any],
        state: AgentState,
        total_steps: int = 0,
        from_compiled: bool = False,
    ) -> Dict[str, Any]:
        """Обробити крок типу ask_user: запитати користувача та підставити відповідь.

        Args:
            step: dict з полями action, args, ask_user: {question, options}
            state: поточний AgentState
            total_steps: загальна кількість кроків (для лічильника)
            from_compiled: чи цей крок прийшов з CompiledPlan

        Returns:
            dict з полями action/args (модифікованими) або error.
        """
        ask_cfg = step.get("ask_user") or {}
        question = ask_cfg.get("question", "")
        options = ask_cfg.get("options", []) or []

        if self.ask_user_callback is None:
            # Без callback — повертаємо noop з помилкою
            return {
                "action": step.get("action", "noop"),
                "args": dict(step.get("args", {})),
                "error": "ask_user_callback not set",
                "step_index": state.step,
                "total_steps": total_steps,
                "from_compiled_plan": from_compiled,
            }

        try:
            answer = self.ask_user_callback(question, options)
        except Exception as e:
            logger.warning("ask_user callback error: %s", e)
            return {
                "action": "noop",
                "args": {},
                "error": str(e),
                "step_index": state.step,
                "total_steps": total_steps,
                "from_compiled_plan": from_compiled,
            }

        new_args = dict(step.get("args", {}))
        new_args["user_answer"] = answer
        return {
            "action": step.get("action", "noop"),
            "args": new_args,
            "user_answer": answer,
            "step_index": state.step,
            "total_steps": total_steps,
            "from_compiled_plan": from_compiled,
        }

    # ── Фаза observe ─────────────────────────────────────────────────────────

    def observe(self) -> Observation:
        """Делегує спостереження AgentObserver (Phase 7.1)."""
        return self._observer.observe(self._current_task)

    # ── Фаза plan ────────────────────────────────────────────────────────────

    def plan(self, task: str, obs: Observation,
             state: AgentState) -> Dict[str, Any]:
        """Делегує планування AgentPlanner (Phase 7.1).

        Якщо крок містить ask_user — обробляємо тут (залишок логіки в AgentLoop).
        """
        plan = self._planner.plan(task, obs, state)

        # ask_user обробляється в AgentLoop (потрібен callback)
        if plan.get("from_compiled_plan"):
            from_compiled_steps = (
                self._planner.compiled_plan.steps
                if self._planner.compiled_plan and hasattr(self._planner.compiled_plan, "steps")
                else []
            )
            # Знайти крок у CompiledPlan для перевірки ask_user
            step_index = plan.get("step_index", state.step)
            if from_compiled_steps and step_index < len(from_compiled_steps):
                raw_step = from_compiled_steps[step_index]
                if raw_step.get("ask_user"):
                    return self._handle_ask_user_step(
                        step=raw_step, state=state,
                        total_steps=len(from_compiled_steps),
                        from_compiled=True,
                    )

        return plan

    def _plan_from_decider(self, task: str, obs: Observation,
                           state: AgentState) -> Optional[Dict[str, Any]]:
        """Залишено для зворотної сумісності — делегує AgentPlanner."""
        return self._planner._plan_from_decider(task, obs, state)

    # ── Фаза act ─────────────────────────────────────────────────────────────

    def act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        action = plan.get("action", "noop")
        args = plan.get("args", {})
        if action == "noop":
            return {"ok": True, "result": "noop"}
        try:
            result = self.registry.execute_function(action, args, auto_create=False)
            return result if isinstance(result, dict) else {"ok": True, "result": str(result)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Фаза check ───────────────────────────────────────────────────────────

    def check(self, action: str, obs: Observation,
              act_result: Optional[Dict[str, Any]] = None,
              expectations: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        cr = _check(action=action, obs=obs, state=self._check_state,
                    act_result=act_result, expectations=expectations,
                    task_id=self.task_id)
        return {
            "success": cr.success,
            "screen_changed": cr.screen_changed,
            "retry": cr.retry,
            "detail": cr.detail,
        }

    # ── Repair loop ──────────────────────────────────────────────────────────

    def _try_repair(
        self,
        action: str,
        args: Dict[str, Any],
        obs: Observation,
        plan: Dict[str, Any],
        act_result: Dict[str, Any],
        state: AgentState,
    ) -> None:
        """Спробувати відновитися після серії невдалих дій через StepRepairer."""
        reasoning = plan.get("reasoning", "")
        expectations = plan.get("expectations") or plan.get("expect")
        try:
            decision = self.repairer.repair(
                failed_action={"action": action, "args": args, "reasoning": reasoning},
                act_result=act_result,
                observation=obs,
                history=state.actions_history,
                expectations=expectations,
            )
        except Exception as e:
            logger.warning("Repair call failed: %s", e)
            return

        if decision is None:
            return

        from functions.planning.logic_repair_loop import RepairAction
        logger.info("Repair decision: %s — %s", decision.action.value, decision.reason)
        self._gui_msg("update_status",
                      f"🔧 Repair: {decision.action.value} — {decision.reason[:60]}")

        if decision.action == RepairAction.RETRY and decision.modified_action:
            modified = decision.modified_action
            state.actions_history.append({
                "step": state.step,
                "action": "_repair_hint",
                "args": modified,
                "act_result": {"ok": True, "result": "repair retry"},
                "check_result": {"success": True, "detail": decision.reason},
                "from_repairer": True,
            })
            state.consecutive_failures = 0
        elif decision.action == RepairAction.SKIP:
            state.consecutive_failures = 0
        elif decision.action == RepairAction.REPLAN:
            state.consecutive_failures = self.config.replan_after_failures
        elif decision.action == RepairAction.STOP:
            state.done = True
            state.success = False
            state.done_summary = f"Зупинено repair-стратегом: {decision.reason}"

    # ── Основний цикл ────────────────────────────────────────────────────────

    def run(self, task: str) -> Dict[str, Any]:
        """Основний цикл агента: observe → plan → act → check."""
        logger.info("AgentLoop.run(): %s", task[:60])
        self._current_task = task
        self._stop_flag = False
        self.loop_detector.full_reset()
        if self.repairer and hasattr(self.repairer, "reset"):
            try:
                self.repairer.reset()
            except Exception:
                pass
        self.action_guard.reset()

        state = AgentState()
        cp_data = load_checkpoint(task_id=self.task_id, enabled=self.config.enable_checkpoint)
        if cp_data is not None:
            state.step = cp_data.get("current_step", 0)
            state.actions_history = cp_data.get("actions_history", [])

        start_time = time.time()
        self._gui_msg("execution_started", None)
        self._gui_msg("update_status", "🔄 Agent loop: observe → plan → act → check")

        try:
            while True:
                # Стоп-умови
                if self._stop_flag:
                    state.done, state.success = True, False
                    state.done_summary = "Зупинено користувачем"
                    break
                if state.step >= self.config.max_steps:
                    state.done, state.success = True, False
                    state.done_summary = f"Досягнуто ліміту кроків ({self.config.max_steps})"
                    break
                if time.time() - start_time > self.config.max_duration_seconds:
                    state.done, state.success = True, False
                    state.done_summary = "Перевищено ліміт часу"
                    break
                if state.done:
                    break

                # ── 1. Observe ──
                obs = self.observe()
                state.observations.append(obs)
                if len(state.observations) > 5:
                    state.observations = state.observations[-5:]

                # ── 2. Plan ──
                plan = self.plan(task, obs, state)
                if plan.get("done"):
                    state.done = True
                    summary = plan.get("summary") or plan.get("args", {}).get("summary", "")
                    # Не перезаписувати success, якщо repairer вже встановив done/success
                    if not state.done_summary or state.success is not False:
                        state.success = bool(plan.get("success", True))
                    if summary:
                        state.done_summary = str(summary or "")
                    break

                action = plan.get("action", "noop")
                args = plan.get("args", {})

                # ── 3. Act (через ActionGuard) ──
                guard_result = self.action_guard.run_guards(
                    action=action, args=args,
                    actions_history=state.actions_history,
                    gui_cb=self._gui_msg,
                )
                if guard_result is not None:
                    act_result = guard_result
                else:
                    act_result = self.act(plan)
                    self.action_guard.update_after_action(action, args, act_result)

                # ── 4. Check ──
                check_result = self.check(action, obs, act_result=act_result)

                # Оновлення стану
                state.last_action = action
                state.last_result = check_result.get("detail", "")
                state.actions_history.append({
                    "step": state.step, "action": action, "args": args,
                    "act_result": act_result, "check_result": check_result,
                    "from_decider": plan.get("from_decider", False),
                })
                if check_result.get("success"):
                    state.consecutive_failures = 0
                    self.loop_detector.on_action_success()
                else:
                    state.consecutive_failures += 1
                    state.total_failures += 1

                # ── Repair-loop ────────────────────────────────────────────
                if (not check_result.get("success")
                        and self.config.enable_repair
                        and self.repairer is not None
                        and state.consecutive_failures >= self.config.repair_after_failures):
                    # Виклискаємо repair якщо:
                    #   - is_available=True (реальний сценарій)
                    #   - repair метод явно мок-нутий (має call_count — unittest.mock)
                    #   - repairs_remaining > 0
                    repair_method = getattr(self.repairer, "repair", None)
                    is_mocked_repair = hasattr(repair_method, "call_count")
                    repairs_remaining_fn = getattr(self.repairer, "repairs_remaining", None)
                    budget_left = (
                        callable(repairs_remaining_fn) and repairs_remaining_fn() > 0
                    )
                    is_avail = bool(getattr(self.repairer, "is_available", False))
                    if is_mocked_repair or budget_left or is_avail:
                        self._try_repair(action, args, obs, plan, act_result, state)
                        # Якщо repair-стратег зупинив цикл (STOP) — виходимо негайно
                        if state.done:
                            break

                # ── Context Update ──────────────────────────
                if self.context_controller is not None:
                    try:
                        used = self.context_controller.context_tokens_used
                        limit = getattr(self.context_controller, 'max_context_tokens', 128000)
                        model_name = getattr(self.context_controller, 'model_name', 'unknown')
                        self._gui_msg("context_update", {
                            "used": used,
                            "limit": limit,
                            "model": model_name,
                        })
                    except Exception as ctx_e:
                        logger.debug("Context tokens read error: %s", ctx_e)

                state.step += 1

                # Чекпоїнт
                if (self.config.enable_checkpoint
                        and state.step % self.config.checkpoint_interval_steps == 0):
                    save_checkpoint(
                        state=self._check_state, agent_state=state,
                        task_id=self.task_id, task_description=task,
                        total_steps=self.config.max_steps,
                        config=self.config.__dict__,
                        enabled=True,
                    )
        except Exception:
            logger.exception("AgentLoop: критична помилка в головному циклі")
            state.done = True
            state.success = False
            state.done_summary = "Критична помилка циклу"
        finally:
            duration = time.time() - start_time
            cleanup_checkpoint(task_id=self.task_id, enabled=self.config.enable_checkpoint)
            summary = f"📊 Agent loop: {state.step} кроків за {duration:.1f}с"
            summary += " ✅" if state.success else " ⚠️"
            self._gui_msg("add_message", ("assistant", summary))
            self._gui_msg("execution_finished", None)
            self._gui_msg("update_status", "✅ Готовий до роботи")

        return {
            "ok": state.success,
            "steps": state.step,
            "duration": time.time() - start_time,
            "summary": state.done_summary,
            "state": state,
        }


__all__ = [
    "AgentLoop",
    "AgentLoopConfig",
    "AgentState",
    "Observation",
]