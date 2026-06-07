"""AgentPlanner — фаза планування (вибір стратегії).

Винесено з AgentLoop.plan() для модульності (Phase 7.1).
Зберігає зворотню сумісність: AgentLoop делегує планування цьому класу.

Логіка вибору джерела плану (пріоритет):
  1. LLM ActionDecider (основний — якщо доступний)
  2. Planner.create_plan() (legacy, тільки перший крок)
  3. Продовження плану через збережений _plan_steps
  4. CompiledPlan від TaskSpec
  5. Fallback noop/done
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_planner")


class AgentPlanner:
    """Фаза планування для AgentLoop.

    Вибирає стратегію виконання задачі на основі наявних інструментів:
    ActionDecider (LLM), legacy Planner, або CompiledPlan.

    Args:
        assistant: Об'єкт VoiceAssistant (доступ до planner, LLM).
        decider: ActionDecider для LLM-планування (опційно).
        compiled_plan: CompiledPlan від TaskSpec (опційно).
        enable_llm_decider: Чи вмикати LLM ActionDecider.
        replan_after_failures: Поріг consecutive failures для replan.
        loop_detector: LoopDetector для виявлення зациклення.
        context_controller: ContextController для бюджету контексту.
    """

    def __init__(
        self,
        assistant,
        decider=None,
        compiled_plan=None,
        enable_llm_decider: bool = True,
        replan_after_failures: int = 3,
        loop_detector=None,
        context_controller=None,
    ):
        self.assistant = assistant
        self.decider = decider
        self.compiled_plan = compiled_plan
        self.enable_llm_decider = enable_llm_decider
        self.replan_after_failures = replan_after_failures
        self.loop_detector = loop_detector
        self.context_controller = context_controller
        self._plan_steps: Optional[List[Dict[str, Any]]] = None

    def set_compiled_plan(self, compiled_plan) -> None:
        """Встановити CompiledPlan від TaskSpec."""
        self.compiled_plan = compiled_plan

    def reset(self) -> None:
        """Скинути внутрішній стан (новий запуск)."""
        self._plan_steps = None

    def plan(
        self,
        task: str,
        obs: Any,
        state: Any,
    ) -> Dict[str, Any]:
        """Вирішити що робити далі.

        Пріоритети:
          1. LLM ActionDecider
          2. Planner.create_plan() (legacy, тільки step 0)
          3. Продовження плану від Planner
          4. CompiledPlan
          5. Fallback noop/done

        Args:
            task: Текст задачі.
            obs: Observation — результат спостереження.
            state: AgentState — поточний стан агента.

        Returns:
            dict з action, args, done та іншими полями.
        """
        # 1. LLM ActionDecider
        if self.enable_llm_decider and self.decider and self.decider.is_available:
            try:
                result = self._plan_from_decider(task, obs, state)
                if result:
                    return result
            except Exception:
                logger.exception("plan_from_decider error")

        # 2. Planner (legacy — тільки перший крок)
        if state.step == 0:
            plan_steps = self._plan_from_planner(task)
            if plan_steps:
                self._plan_steps = plan_steps
                return self._step_from_plan(state.step)

        # 3. Продовження плану від Planner (історія)
        plan_steps = self._plan_steps or self._get_plan_from_history(state)
        if plan_steps and state.step < len(plan_steps):
            step = plan_steps[state.step]
            return {
                "action": step.get("action", "noop"),
                "args": step.get("args", {}),
                "done": step.get("done", False),
                "step_index": state.step,
                "total_steps": len(plan_steps),
                "from_compiled_plan": False,
            }

        # 4. CompiledPlan (від TaskSpec)
        if (self.compiled_plan
                and hasattr(self.compiled_plan, "steps")
                and self.compiled_plan.steps):
            steps = self.compiled_plan.steps
            if state.step < len(steps):
                step = steps[state.step]
                return {
                    "action": step.get("action", "noop"),
                    "args": step.get("args", {}),
                    "done": step.get("done", False),
                    "from_compiled_plan": True,
                }

        # 5. Fallback — noop / done
        return {"action": "noop", "args": {}, "done": True}

    # ── Внутрішні методи ────────────────────────────────────────────────────

    def _plan_from_decider(
        self, task: str, obs: Any, state: Any,
    ) -> Optional[Dict[str, Any]]:
        """Отримати крок від LLM ActionDecider."""
        last_result = (
            state.actions_history[-1].get("act_result")
            if state.actions_history else None
        )

        if state.consecutive_failures >= self.replan_after_failures:
            action = self.decider.replan(
                goal=task,
                observation=obs,
                history=state.actions_history,
                consecutive_failures=state.consecutive_failures,
                progress_summary=state.progress_summary,
                context_controller=self.context_controller,
            )
            state.consecutive_failures = 0
        else:
            stuck_warning = ""
            if self.loop_detector and self.loop_detector.is_stuck:
                stuck_warning = self.loop_detector.get_stuck_warning_message()
            action = self.decider.decide(
                goal=task,
                observation=obs,
                history=state.actions_history,
                last_result=last_result,
                progress_summary=state.progress_summary,
                context_controller=self.context_controller,
                stuck_warning=stuck_warning,
            )

        if action.name in ("done",):
            return {
                "action": "done",
                "args": dict(action.arguments),
                "done": True,
                "success": bool(action.arguments.get("success", True)),
                "from_decider": True,
            }

        # Звичайна дія
        real_name = self.decider.resolve_alias(action.name)
        return {
            "action": real_name,
            "args": dict(action.arguments),
            "done": False,
            "from_decider": True,
            "reasoning": action.reasoning,
        }

    def _plan_from_planner(self, task: str) -> Optional[List[Dict[str, Any]]]:
        """Спробувати створити план через legacy Planner (тільки step 0)."""
        planner = getattr(self.assistant, "planner", None)
        if not planner:
            return None
        try:
            plan_steps = planner.create_plan(task)
            if plan_steps and isinstance(plan_steps, list) and len(plan_steps) > 0:
                return plan_steps
        except Exception:
            logger.exception("Planner.create_plan error")
        return None

    @staticmethod
    def _get_plan_from_history(state: Any) -> Optional[List[Dict[str, Any]]]:
        """Спробувати отримати план з історії стану."""
        if hasattr(state, "_plan_steps") and state._plan_steps:
            return state._plan_steps
        if (state.actions_history
                and isinstance(state.actions_history[0], dict)
                and "plan" in state.actions_history[0]):
            return state.actions_history[0]["plan"]
        return None

    def _step_from_plan(self, step_idx: int) -> Dict[str, Any]:
        """Конвертувати крок плану у формат AgentLoop."""
        if not self._plan_steps or step_idx >= len(self._plan_steps):
            return {"action": "noop", "args": {}, "done": True}
        step = self._plan_steps[step_idx]
        return {
            "action": step.get("action", "noop"),
            "args": step.get("args", {}),
            "done": step.get("done", False),
            "step_index": step_idx,
            "total_steps": len(self._plan_steps),
            "from_compiled_plan": False,
        }


__all__ = ["AgentPlanner"]