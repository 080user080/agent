"""Тести для logic_repair_loop.py — Phase 12.2."""
import pytest
from unittest.mock import Mock, MagicMock, patch

from functions.logic_repair_loop import (
    RepairAction,
    RepairProposal,
    RepairProposer,
    RepairLoop,
)
from functions.logic_expectations import ExpectationResult, ExpectSpec
from functions.logic_task_runner import Task
from functions.logic_execution_report import ExecutionReport


class TestRepairAction:
    """Тести для RepairAction enum."""

    def test_action_values(self):
        """Перевірити що всі action values коректні."""
        assert RepairAction.RETRY.value == "retry"
        assert RepairAction.SKIP.value == "skip"
        assert RepairAction.REPLAN.value == "replan"
        assert RepairAction.STOP.value == "stop"


class TestRepairProposal:
    """Тести для RepairProposal dataclass."""

    def test_minimal_proposal(self):
        """Створити мінімальну пропозицію."""
        proposal = RepairProposal(
            action=RepairAction.STOP,
            reason="Немає стратегії repair",
        )
        assert proposal.action == RepairAction.STOP
        assert proposal.reason == "Немає стратегії repair"
        assert proposal.modified_args is None
        assert proposal.skip_reason is None
        assert proposal.replan_summary is None

    def test_retry_proposal(self):
        """Створити пропозицію для retry."""
        proposal = RepairProposal(
            action=RepairAction.RETRY,
            reason="Невірний шлях до файлу",
            modified_args={"path": "/correct/path"},
        )
        assert proposal.action == RepairAction.RETRY
        assert proposal.modified_args == {"path": "/correct/path"}

    def test_skip_proposal(self):
        """Створити пропозицію для skip."""
        proposal = RepairProposal(
            action=RepairAction.SKIP,
            reason="Крок не критичний",
            skip_reason="Файл вже існує",
        )
        assert proposal.action == RepairAction.SKIP
        assert proposal.skip_reason == "Файл вже існує"

    def test_replan_proposal(self):
        """Створити пропозицію для replan."""
        proposal = RepairProposal(
            action=RepairAction.REPLAN,
            reason="Зміна контексту",
            replan_summary="Спробувати інший підхід",
        )
        assert proposal.action == RepairAction.REPLAN
        assert proposal.replan_summary == "Спробувати інший підхід"


class TestRepairProposer:
    """Тести для RepairProposer."""

    def test_init(self):
        """Ініціалізація proposer."""
        assistant = Mock()
        proposer = RepairProposer(assistant)
        assert proposer.assistant == assistant
        assert proposer._available is True

    def test_is_available(self):
        """Перевірка доступності."""
        assistant = Mock()
        proposer = RepairProposer(assistant)
        assert proposer.is_available() is True

    def test_is_available_when_disabled(self):
        """Перевірка коли proposer недоступний."""
        assistant = Mock()
        proposer = RepairProposer(assistant)
        proposer._available = False
        assert proposer.is_available() is False

    def test_propose_repair_when_unavailable(self):
        """Повертає None коли proposer недоступний."""
        assistant = Mock()
        proposer = RepairProposer(assistant)
        proposer._available = False

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        result = proposer.propose_repair(expect_results, task, report)
        assert result is None

    @patch("functions.logic_repair_loop.ask_llm_with_tools")
    def test_propose_repair_success(self, mock_ask_llm):
        """Успішна пропозиція repair від LLM."""
        assistant = Mock()
        proposer = RepairProposer(assistant)

        # Mock LLM response
        mock_ask_llm.return_value = MagicMock(
            error=None,
            raw={
                "action": "retry",
                "reason": "Невірний шлях",
                "modified_args": {"path": "/correct/path"},
            },
        )

        expect_results = [
            ExpectationResult(kind="file_exists", ok=False, reason="Файл не знайдено")
        ]
        task = Task(id="1", kind="write_file", params={"path": "/wrong/path"})
        report = ExecutionReport(plan_name="test")

        result = proposer.propose_repair(expect_results, task, report)

        assert result is not None
        assert result.action == RepairAction.RETRY
        assert result.reason == "Невірний шлях"
        assert result.modified_args == {"path": "/correct/path"}

    @patch("functions.logic_repair_loop.ask_llm_with_tools")
    def test_propose_repair_llm_error(self, mock_ask_llm):
        """LLM повертає помилку."""
        assistant = Mock()
        proposer = RepairProposer(assistant)

        mock_ask_llm.return_value = MagicMock(error="LLM error")

        expect_results = [
            ExpectationResult(kind="file_exists", ok=False, reason="Файл не знайдено")
        ]
        task = Task(id="1", kind="write_file", params={"path": "/wrong/path"})
        report = ExecutionReport(plan_name="test")

        result = proposer.propose_repair(expect_results, task, report)
        assert result is None

    @patch("functions.logic_repair_loop.ask_llm_with_tools")
    def test_propose_repair_invalid_response(self, mock_ask_llm):
        """LLM повертає невалідний response."""
        assistant = Mock()
        proposer = RepairProposer(assistant)

        mock_ask_llm.return_value = MagicMock(error=None, raw={"invalid": "data"})

        expect_results = [
            ExpectationResult(kind="file_exists", ok=False, reason="Файл не знайдено")
        ]
        task = Task(id="1", kind="write_file", params={"path": "/wrong/path"})
        report = ExecutionReport(plan_name="test")

        result = proposer.propose_repair(expect_results, task, report)
        assert result is None

    def test_build_repair_context(self):
        """Перевірка формування контексту."""
        assistant = Mock()
        proposer = RepairProposer(assistant)

        failed = [
            ExpectationResult(
                kind="file_exists",
                ok=False,
                reason="Файл не знайдено",
                details={"path": "/wrong/path"},
            )
        ]
        task = Task(id="1", kind="write_file", params={"path": "/wrong/path"})
        report = ExecutionReport(plan_name="test")

        context = proposer._build_repair_context(failed, task, report)

        assert "failed_expectations" in context
        assert len(context["failed_expectations"]) == 1
        assert context["failed_expectations"][0]["kind"] == "file_exists"
        assert context["failed_expectations"][0]["reason"] == "Файл не знайдено"

        assert "task" in context
        assert context["task"]["kind"] == "write_file"
        assert context["task"]["params"] == {"path": "/wrong/path"}

        assert "current_step" in context
        assert context["current_step"] == 0

    def test_parse_repair_response(self):
        """Парсинг відповіді LLM."""
        assistant = Mock()
        proposer = RepairProposer(assistant)

        raw = {
            "action": "retry",
            "reason": "Невірний шлях",
            "modified_args": {"path": "/correct/path"},
        }

        result = proposer._parse_repair_response(raw)

        assert result is not None
        assert result.action == RepairAction.RETRY
        assert result.reason == "Невірний шлях"
        assert result.modified_args == {"path": "/correct/path"}

    def test_parse_repair_response_invalid_action(self):
        """Парсинг з невалідним action."""
        assistant = Mock()
        proposer = RepairProposer(assistant)

        raw = {"action": "invalid", "reason": "test"}

        result = proposer._parse_repair_response(raw)
        assert result is None

    def test_parse_repair_response_missing_action(self):
        """Парсинг без action."""
        assistant = Mock()
        proposer = RepairProposer(assistant)

        raw = {"reason": "test"}

        result = proposer._parse_repair_response(raw)
        assert result is None


class TestRepairLoop:
    """Тести для RepairLoop."""

    def test_init(self):
        """Ініціалізація repair loop."""
        proposer = Mock()
        loop = RepairLoop(proposer)
        assert loop.proposer == proposer
        assert loop.max_repair_attempts == 3

    def test_repair_failed_step_proposer_unavailable(self):
        """Repair коли proposer недоступний."""
        proposer = Mock()
        proposer.is_available.return_value = False
        loop = RepairLoop(proposer)

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        action, modified_args = loop.repair_failed_step(expect_results, task, report)

        assert action == RepairAction.STOP
        assert modified_args is None

    def test_repair_failed_step_no_proposal(self):
        """Repair коли LLM не запропонував стратегію."""
        proposer = Mock()
        proposer.is_available.return_value = True
        proposer.propose_repair.return_value = None
        loop = RepairLoop(proposer)

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        action, modified_args = loop.repair_failed_step(expect_results, task, report)

        assert action == RepairAction.STOP
        assert modified_args is None

    def test_repair_failed_step_retry(self):
        """Repair з retry."""
        proposer = Mock()
        proposer.is_available.return_value = True
        proposal = RepairProposal(
            action=RepairAction.RETRY,
            reason="Невірний шлях",
            modified_args={"path": "/correct/path"},
        )
        proposer.propose_repair.return_value = proposal
        loop = RepairLoop(proposer)

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        action, modified_args = loop.repair_failed_step(expect_results, task, report)

        assert action == RepairAction.RETRY
        assert modified_args == {"path": "/correct/path"}

    def test_repair_failed_step_retry_without_args(self):
        """Repair RETRY без modified_args."""
        proposer = Mock()
        proposer.is_available.return_value = True
        proposal = RepairProposal(
            action=RepairAction.RETRY,
            reason="Невірний шлях",
            modified_args=None,  # Без аргументів
        )
        proposer.propose_repair.return_value = proposal
        loop = RepairLoop(proposer)

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        action, modified_args = loop.repair_failed_step(expect_results, task, report)

        assert action == RepairAction.STOP
        assert modified_args is None

    def test_repair_failed_step_skip(self):
        """Repair з skip."""
        proposer = Mock()
        proposer.is_available.return_value = True
        proposal = RepairProposal(
            action=RepairAction.SKIP,
            reason="Крок не критичний",
            skip_reason="Файл вже існує",
        )
        proposer.propose_repair.return_value = proposal
        loop = RepairLoop(proposer)

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        action, modified_args = loop.repair_failed_step(expect_results, task, report)

        assert action == RepairAction.SKIP
        assert modified_args is None

    def test_repair_failed_step_replan(self):
        """Repair з replan."""
        proposer = Mock()
        proposer.is_available.return_value = True
        proposal = RepairProposal(
            action=RepairAction.REPLAN,
            reason="Зміна контексту",
            replan_summary="Спробувати інший підхід",
        )
        proposer.propose_repair.return_value = proposal
        loop = RepairLoop(proposer)

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        action, modified_args = loop.repair_failed_step(expect_results, task, report)

        # Для MVP REPLAN зупиняє виконання
        assert action == RepairAction.STOP
        assert modified_args is None

    def test_repair_failed_step_stop(self):
        """Repair з stop."""
        proposer = Mock()
        proposer.is_available.return_value = True
        proposal = RepairProposal(
            action=RepairAction.STOP,
            reason="Немає стратегії",
        )
        proposer.propose_repair.return_value = proposal
        loop = RepairLoop(proposer)

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        action, modified_args = loop.repair_failed_step(expect_results, task, report)

        assert action == RepairAction.STOP
        assert modified_args is None

    def test_repair_failed_step_unknown_action(self):
        """Repair з невідомим action."""
        proposer = Mock()
        proposer.is_available.return_value = True
        # Створюємо proposal з невалідним action
        proposal = Mock()
        proposal.action = "unknown"
        proposal.reason = "test"
        proposer.propose_repair.return_value = proposal
        loop = RepairLoop(proposer)

        expect_results = []
        task = Task(id="1", kind="test", params={})
        report = ExecutionReport(plan_name="test")

        action, modified_args = loop.repair_failed_step(expect_results, task, report)

        assert action == RepairAction.STOP
        assert modified_args is None
