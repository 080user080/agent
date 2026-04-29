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

from .logic_execution_report import ExecutionReport, StepReport
from .logic_expectations import ExpectationResult, failures, all_ok
from .logic_llm_tools import ask_llm_with_tools

if TYPE_CHECKING:
    from .logic_task_runner import Task

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
