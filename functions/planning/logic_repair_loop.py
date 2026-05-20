"""LLM repair loop for TaskRunner — Phase 12.2.

Це Phase 12.2 — повний Actor-Critic цикл.
Коли expect не пройшов (STATUS_EXPECT_FAILED), LLM пропонує як виправити:
- retry з іншими аргументами
- пропустити крок
- перепланувати решту плану
- зупинитися

Архітектура:
- RepairProposer — запитує LLM про стратегію repair
- RepairLoop — виконує repair з retry/replan/skip/stop
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from functions.planning.logic_execution_report import ExecutionReport, StepReport
from functions.planning.logic_expectations import ExpectationResult, failures, all_ok
from functions.llm.logic_llm_tools import ask_llm_with_tools

if TYPE_CHECKING:
    from functions.planning.logic_task_runner import Task

logger = logging.getLogger("repair_loop")


class RepairAction(str, Enum):
    """Тип дії repair."""
    RETRY = "retry"  # повторити крок з іншими аргументами
    SKIP = "skip"  # пропустити крок і продовжити
    REPLAN = "replan"  # перепланувати решту плану
    STOP = "stop"  # зупинити виконання


@dataclass
class RepairProposal:
    """Пропозиція repair від LLM."""
    action: RepairAction
    reason: str  # чому LLM пропонує цю дію
    modified_args: Optional[Dict[str, Any]] = None  # нові аргументи для RETRY
    skip_reason: Optional[str] = None  # чому можна пропустити (для SKIP)
    replan_summary: Optional[str] = None  # короткий опис нового плану (для REPLAN)


class RepairProposer:
    """Запитує LLM про стратегію repair для failed expectations."""

    def __init__(self, assistant):
        self.assistant = assistant
        self._available = True

    def is_available(self) -> bool:
        """Перевірити чи repair proposer доступний."""
        return self._available

    def propose_repair(
        self,
        expect_results: List[ExpectationResult],
        task: Task,
        report: ExecutionReport,
    ) -> Optional[RepairProposal]:
        """Запропонувати repair стратегію для failed expectations.

        Args:
            expect_results: результати перевірок expect
            task: задача що не пройшла expect
            report: поточний execution report

        Returns:
            RepairProposal або None якщо LLM не може запропонувати
        """
        if not self._available:
            logger.warning("Repair proposer недоступний")
            return None

        # Формуємо контекст для LLM
        failed = failures(expect_results)
        context = self._build_repair_context(failed, task, report)

        # Запитуємо LLM
        prompt = self._build_repair_prompt(context)

        try:
            response = ask_llm_with_tools(
                assistant=self.assistant,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ти — repair strategist для агента. "
                            "Коли expect не пройшов, ти пропонуєш як виправити: "
                            "retry з іншими аргументами, skip, replan або stop. "
                            "Відповідай у форматі JSON з полями: action, reason, "
                            "modified_args (для retry), skip_reason (для skip), replan_summary (для replan)."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=None,  # MVP — без tools
                response_format={"type": "json_object"},
            )

            if response.error:
                logger.warning("LLM repair request failed: %s", response.error)
                return None

            # Парсимо відповідь
            return self._parse_repair_response(response.raw)

        except Exception as e:
            logger.warning("Repair proposer error: %s", e)
            return None

    def _build_repair_context(
        self,
        failed: List[ExpectationResult],
        task: Task,
        report: ExecutionReport,
    ) -> Dict[str, Any]:
        """Побудувати контекст для LLM."""
        return {
            "failed_expectations": [
                {
                    "kind": r.kind,
                    "reason": r.reason,
                    "details": r.details,
                }
                for r in failed
            ],
            "task": {
                "kind": task.kind,
                "name": task.display(),
                "params": task.params,
            },
            "current_step": len(report.steps),
            "total_steps": len(report.steps),
        }

    def _build_repair_prompt(self, context: Dict[str, Any]) -> str:
        """Побудувати промпт для LLM."""
        prompt = (
            "Останній крок не пройшов expect перевірку:\n\n"
            f"Failed expectations:\n"
        )
        for exp in context["failed_expectations"]:
            prompt += f"- {exp['kind']}: {exp['reason']}\n"
            if exp.get("details"):
                prompt += f"  Details: {exp['details']}\n"

        prompt += (
            f"\nTask: {context['task']['kind']} — {context['task']['name']}\n"
            f"Params: {context['task']['params']}\n"
            f"Progress: {context['current_step']}/{context['total_steps']}\n\n"
            "Пропонуй як виправити (retry/skip/replan/stop)."
        )
        return prompt

    def _parse_repair_response(self, raw: Dict[str, Any]) -> Optional[RepairProposal]:
        """Парсити відповідь LLM."""
        try:
            action_str = raw.get("action", "").lower()
            action = RepairAction(action_str)

            proposal = RepairProposal(
                action=action,
                reason=raw.get("reason", ""),
                modified_args=raw.get("modified_args"),
                skip_reason=raw.get("skip_reason"),
                replan_summary=raw.get("replan_summary"),
            )

            logger.info("LLM repair proposal: %s — %s", action, proposal.reason)
            return proposal

        except (ValueError, KeyError) as e:
            logger.warning("Failed to parse repair response: %s", e)
            return None


class RepairLoop:
    """Виконує repair loop для TaskRunner."""

    def __init__(self, proposer: RepairProposer):
        self.proposer = proposer
        self.max_repair_attempts = 3

    def repair_failed_step(
        self,
        expect_results: List[ExpectationResult],
        task: Task,
        report: ExecutionReport,
    ) -> tuple[RepairAction, Optional[Dict[str, Any]]]:
        """Спробувати виправити failed step.

        Returns:
            (action, modified_args) — action що треба виконати, та модифіковані аргументи (для RETRY)
        """
        if not self.proposer.is_available():
            logger.warning("Repair proposer недоступний — пропускаємо repair")
            return RepairAction.STOP, None

        proposal = self.proposer.propose_repair(expect_results, task, report)

        if not proposal:
            logger.warning("LLM не запропонував repair стратегію")
            return RepairAction.STOP, None

        # Виконуємо пропозицію
        if proposal.action == RepairAction.RETRY:
            if proposal.modified_args:
                logger.info("Repair: retry з новими аргументами")
                return RepairAction.RETRY, proposal.modified_args
            else:
                logger.warning("Repair: RETRY без modified_args — зупиняємо")
                return RepairAction.STOP, None

        elif proposal.action == RepairAction.SKIP:
            logger.info("Repair: skip крок — %s", proposal.skip_reason)
            return RepairAction.SKIP, None

        elif proposal.action == RepairAction.REPLAN:
            logger.info("Repair: replan — %s", proposal.replan_summary)
            # Для MVP REPLAN треба перепланувати весь план — це складно
            # Тому поки що просто зупиняємо
            return RepairAction.STOP, None

        elif proposal.action == RepairAction.STOP:
            logger.info("Repair: stop — %s", proposal.reason)
            return RepairAction.STOP, None

        else:
            logger.warning("Невідомий repair action: %s", proposal.action)
            return RepairAction.STOP, None


# ─── StepRepairer (для AgentLoop) ──────────────────────────────────────────────

@dataclass
class RepairDecision:
    """Рішення StepRepairer для AgentLoop."""
    action: RepairAction  # retry / skip / replan / stop
    reason: str
    modified_action: Optional[Dict[str, Any]] = None  # {"action": "...", "args": {...}}


class StepRepairer:
    """Адаптивний repair для `AgentLoop._execute_single_step`.

    Викликається при `consecutive_failures >= threshold`. Аналізує контекст
    (failed_action, act_result, observation, history) через LLM і пропонує:
    - RETRY з модифікованими args
    - SKIP крок
    - REPLAN всю стратегію
    - STOP

    Має бюджет: `max_repairs_per_session` (default 3) — захист від нескінченного циклу.
    """

    DEFAULT_MAX_REPAIRS = 3

    def __init__(self, assistant=None, max_repairs: int = DEFAULT_MAX_REPAIRS):
        self.assistant = assistant
        self.max_repairs = max_repairs
        self._repairs_used = 0

    def reset(self) -> None:
        """Скинути лічильник (новий запуск AgentLoop)."""
        self._repairs_used = 0

    @property
    def repairs_remaining(self) -> int:
        return max(0, self.max_repairs - self._repairs_used)

    @property
    def is_available(self) -> bool:
        """Чи можна ще робити repair (бюджет + LLM доступний)."""
        if self._repairs_used >= self.max_repairs:
            return False
        if self.assistant is None:
            return False
        return True

    def repair(
        self,
        failed_action: Dict[str, Any],
        act_result: Optional[Dict[str, Any]],
        observation: Optional[Any],
        history: List[Dict[str, Any]],
        expectations: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[RepairDecision]:
        """Запропонувати repair-рішення.

        Args:
            failed_action: {"action": str, "args": dict, "reasoning": str}
            act_result: результат виконання (ok, error, output)
            observation: Observation (опційно — для опису екрану)
            history: список останніх дій (action, args, act_result, check_result)
            expectations: очікування які не пройшли (опційно)

        Returns:
            RepairDecision або None якщо бюджет вичерпано / LLM недоступний.
        """
        if not self.is_available:
            logger.info("StepRepairer: бюджет вичерпано (%s/%s) або немає LLM",
                        self._repairs_used, self.max_repairs)
            return None

        self._repairs_used += 1
        prompt = self._build_prompt(failed_action, act_result, observation, history, expectations)

        try:
            response = ask_llm_with_tools(
                assistant=self.assistant,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ти — repair strategist для GUI-агента. Крок провалився. "
                            "Проаналізуй контекст і поверни JSON-об'єкт:\n"
                            '{"action": "retry|skip|replan|stop", "reason": "...", '
                            '"modified_action": {"action": "...", "args": {...}} (тільки для retry)}\n'
                            "- retry: якщо проблему можна виправити іншими аргументами (інші координати, селектор, текст).\n"
                            "- skip: якщо крок не критичний.\n"
                            "- replan: якщо потрібна нова стратегія цілком.\n"
                            "- stop: якщо ціль недосяжна або помилка фатальна."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                response_format={"type": "json_object"},
            )

            if getattr(response, "error", None):
                logger.warning("StepRepairer LLM error: %s", response.error)
                return RepairDecision(action=RepairAction.STOP, reason=f"LLM error: {response.error}")

            return self._parse_decision(getattr(response, "raw", None) or {})

        except Exception as e:
            logger.warning("StepRepairer error: %s", e)
            return RepairDecision(action=RepairAction.STOP, reason=str(e))

    def _build_prompt(
        self,
        failed_action: Dict[str, Any],
        act_result: Optional[Dict[str, Any]],
        observation: Optional[Any],
        history: List[Dict[str, Any]],
        expectations: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Побудувати промпт для repair."""
        lines = ["Останній крок провалився.\n"]

        # Дія яка провалилась
        lines.append("FAILED ACTION:")
        lines.append(f"  action: {failed_action.get('action', '?')}")
        lines.append(f"  args: {failed_action.get('args', {})}")
        if failed_action.get("reasoning"):
            lines.append(f"  reasoning: {failed_action['reasoning']}")

        # Результат виконання
        lines.append("\nACT RESULT:")
        if act_result:
            lines.append(f"  ok: {act_result.get('ok', False)}")
            if act_result.get("error"):
                lines.append(f"  error: {act_result['error']}")
            if act_result.get("output"):
                output = str(act_result["output"])[:300]
                lines.append(f"  output: {output}")
        else:
            lines.append("  (немає результату)")

        # Очікування
        if expectations:
            lines.append("\nEXPECTATIONS (не пройшли):")
            for exp in expectations[:5]:
                lines.append(f"  - {exp}")

        # Опис екрану (якщо є)
        if observation is not None:
            window = getattr(observation, "active_window_title", None)
            if window:
                lines.append(f"\nACTIVE WINDOW: {window}")
            vision_desc = getattr(observation, "vision_description", None)
            if vision_desc:
                lines.append(f"SCREEN DESCRIPTION: {str(vision_desc)[:300]}")
            ocr_text = getattr(observation, "ocr_text", None)
            if ocr_text:
                lines.append(f"OCR (скорочено): {str(ocr_text)[:300]}")

        # Останні кроки
        if history:
            lines.append("\nRECENT HISTORY (останні 3 кроки):")
            for entry in history[-3:]:
                act = entry.get("action", "?")
                ok = entry.get("act_result", {}).get("ok") if isinstance(entry.get("act_result"), dict) else None
                lines.append(f"  - {act} (ok={ok})")

        lines.append(
            "\nПоверни JSON: action (retry/skip/replan/stop), reason, "
            "modified_action (для retry, з полями action і args)."
        )
        return "\n".join(lines)

    def _parse_decision(self, raw: Dict[str, Any]) -> RepairDecision:
        """Парсити JSON-відповідь LLM у RepairDecision."""
        try:
            action_str = str(raw.get("action", "stop")).lower()
            try:
                action = RepairAction(action_str)
            except ValueError:
                logger.warning("Unknown action '%s' — fallback to STOP", action_str)
                action = RepairAction.STOP

            return RepairDecision(
                action=action,
                reason=str(raw.get("reason", "")),
                modified_action=raw.get("modified_action") if action == RepairAction.RETRY else None,
            )
        except Exception as e:
            logger.warning("Parse repair decision error: %s", e)
            return RepairDecision(action=RepairAction.STOP, reason=f"parse error: {e}")