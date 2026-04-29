"""Unit-тести для `functions.core_planner_runner`.

Перевіряємо bridge: legacy `List[Dict]` → TaskRunner-виконання через generic-handler.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

import pytest

from functions.core_planner_critic import legacy_plan_to_plan
from functions.core_planner_runner import (
    LEGACY_ACTION_KIND,
    LegacyRunResult,
    make_legacy_action_handler,
    register_legacy_actions,
    run_legacy_plan_via_runner,
)
from functions.logic_plan_critic import (
    CritiqueResult,
    PlanCritic,
    VERDICT_APPROVE,
    VERDICT_REDO,
)
from functions.logic_provider_registry import ProviderRegistry
from functions.logic_task_runner import (
    STATUS_ERROR,
    STATUS_OK,
    Plan,
    Task,
    TaskContext,
    TaskRunner,
)


# ---------------------------------------------------------------------------
# Stub FunctionRegistry
# ---------------------------------------------------------------------------


class StubFunctionRegistry:
    """Мінімальний duck-typed FunctionRegistry для тестів.

    Підтримує `execute_function(action, params, auto_create=...)` що:
      - повертає `message` (string);
      - виставляє `self.last_tool_result = {...}` у форматі `make_tool_result`.
    """

    def __init__(self) -> None:
        self.functions: Dict[str, Dict[str, Any]] = {}
        self.last_tool_result: Dict[str, Any] = {}
        self.calls: List[Dict[str, Any]] = []

    def add_tool(
        self,
        name: str,
        *,
        ok: bool = True,
        message: str = "",
        data: Mapping[str, Any] = {},
        error: str = "",
        raises: Exception = None,
    ) -> None:
        def _impl(**kwargs: Any) -> Dict[str, Any]:
            if raises is not None:
                raise raises
            self.calls.append({"action": name, "params": dict(kwargs)})
            return {
                "ok": ok,
                "message": message or f"{name} executed",
                "data": dict(data),
                "error": error or None,
                "needs_confirmation": False,
                "retryable": False,
            }

        self.functions[name] = {"function": _impl, "info": {}}

    def execute_function(
        self, action: str, params: Dict[str, Any], auto_create: bool = True
    ) -> str:
        if action not in self.functions:
            self.last_tool_result = {
                "ok": False,
                "message": f"function {action} not found",
                "data": {},
                "error": f"missing: {action}",
                "needs_confirmation": False,
                "retryable": False,
            }
            return self.last_tool_result["message"]

        func = self.functions[action]["function"]
        try:
            result = func(**params)
        except Exception as exc:  # noqa: BLE001
            self.last_tool_result = {
                "ok": False,
                "message": f"exception: {exc}",
                "data": {},
                "error": f"{type(exc).__name__}: {exc}",
                "needs_confirmation": False,
                "retryable": False,
            }
            return self.last_tool_result["message"]

        self.last_tool_result = dict(result)
        return str(result["message"])


# ---------------------------------------------------------------------------
# make_legacy_action_handler
# ---------------------------------------------------------------------------


class TestMakeLegacyActionHandler:
    def _ctx(self, runner: TaskRunner, task: Task) -> TaskContext:
        from functions.logic_execution_report import ExecutionReport

        return TaskContext(
            task=task,
            runner=runner,
            report=ExecutionReport(plan_name="t"),
            gate=runner.gate,
            previous_results={},
        )

    def test_dispatches_by_kind(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("create_file", message="file created", data={"path": "a.txt"})

        handler = make_legacy_action_handler(reg)
        task = Task(id="t1", kind="create_file", params={"path": "a.txt"})
        result = handler(self._ctx(TaskRunner(), task))

        assert result["status"] == STATUS_OK
        assert result["summary"] == "file created"
        assert result["data"] == {"path": "a.txt"}
        assert reg.calls == [{"action": "create_file", "params": {"path": "a.txt"}}]

    def test_strips_legacy_metadata_from_params(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("echo", message="ok")

        handler = make_legacy_action_handler(reg)
        task = Task(
            id="t1",
            kind="echo",
            params={"msg": "hi", "_legacy": {"goal": "greet"}},
        )
        handler(self._ctx(TaskRunner(), task))

        # Переконуємось, що _legacy не потрапив у tool.
        assert reg.calls[0]["params"] == {"msg": "hi"}

    def test_handles_tool_error(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("bad", ok=False, message="boom", error="some failure")

        handler = make_legacy_action_handler(reg)
        task = Task(id="t1", kind="bad", params={})
        result = handler(self._ctx(TaskRunner(), task))

        assert result["status"] == STATUS_ERROR
        assert result["error"] == "some failure"

    def test_handles_exception_in_registry(self) -> None:
        class BrokenRegistry:
            functions: Dict[str, Any] = {}
            last_tool_result = None

            def execute_function(self, action, params, auto_create=False):
                raise RuntimeError("kaboom")

        handler = make_legacy_action_handler(BrokenRegistry())
        task = Task(id="t1", kind="x", params={})
        result = handler(self._ctx(TaskRunner(), task))

        assert result["status"] == STATUS_ERROR
        assert "kaboom" in result["error"]
        assert result["summary"].startswith("exception while executing 'x'")

    def test_name_alias(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("real_name", message="aliased")

        handler = make_legacy_action_handler(
            reg, name_alias={"llm_name": "real_name"}
        )
        task = Task(id="t1", kind="llm_name", params={})
        result = handler(self._ctx(TaskRunner(), task))

        assert result["status"] == STATUS_OK
        assert reg.calls[0]["action"] == "real_name"

    def test_missing_last_tool_result_still_returns_ok(self) -> None:
        class MinimalRegistry:
            functions = {"x": None}
            last_tool_result = None

            def execute_function(self, action, params, auto_create=False):
                return "plain string"

        handler = make_legacy_action_handler(MinimalRegistry())
        task = Task(id="t1", kind="x", params={})
        result = handler(self._ctx(TaskRunner(), task))

        assert result["status"] == STATUS_OK
        assert result["summary"] == "plain string"


# ---------------------------------------------------------------------------
# register_legacy_actions
# ---------------------------------------------------------------------------


class TestRegisterLegacyActions:
    def test_registers_all_known_kinds(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("foo")
        reg.add_tool("bar")

        runner = TaskRunner()
        registered = register_legacy_actions(runner, reg)

        assert "foo" in registered
        assert "bar" in registered
        assert "foo" in runner.handlers
        assert "bar" in runner.handlers
        assert LEGACY_ACTION_KIND in runner.handlers

    def test_respects_kinds_filter(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("foo")
        reg.add_tool("bar")
        reg.add_tool("baz")

        runner = TaskRunner()
        registered = register_legacy_actions(runner, reg, kinds=["foo", "baz"])

        assert set(registered) >= {"foo", "baz"}
        assert "bar" not in runner.handlers

    def test_does_not_override_without_flag(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("foo")

        runner = TaskRunner()
        original = lambda ctx: {"status": STATUS_OK, "summary": "original"}  # noqa: E731
        runner.register("foo", original)

        register_legacy_actions(runner, reg, include_generic=False)

        assert runner.handlers["foo"] is original

    def test_override_true_replaces(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("foo", message="new")

        runner = TaskRunner()
        original = lambda ctx: {"status": STATUS_OK, "summary": "original"}  # noqa: E731
        runner.register("foo", original)

        register_legacy_actions(
            runner, reg, override=True, include_generic=False
        )

        assert runner.handlers["foo"] is not original

    def test_skip_generic_kind(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("foo")

        runner = TaskRunner()
        register_legacy_actions(runner, reg, include_generic=False)

        assert LEGACY_ACTION_KIND not in runner.handlers


# ---------------------------------------------------------------------------
# Generic legacy_action dispatcher
# ---------------------------------------------------------------------------


class TestGenericDispatcher:
    def test_reads_action_from_params(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("create_file", message="done", data={"path": "x.txt"})

        runner = TaskRunner()
        register_legacy_actions(runner, reg)

        plan = Plan(
            name="p",
            tasks=[
                Task(
                    id="t1",
                    kind=LEGACY_ACTION_KIND,
                    params={"action": "create_file", "path": "x.txt"},
                )
            ],
        )
        result = runner.run(plan)

        assert result.report.steps[0].status == STATUS_OK
        assert reg.calls == [
            {"action": "create_file", "params": {"path": "x.txt"}}
        ]

    def test_nested_args_format(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("echo", message="hi")

        runner = TaskRunner()
        register_legacy_actions(runner, reg)

        plan = Plan(
            name="p",
            tasks=[
                Task(
                    id="t1",
                    kind=LEGACY_ACTION_KIND,
                    params={
                        "action": "echo",
                        "args": {"msg": "hi", "n": 3},
                    },
                )
            ],
        )
        result = runner.run(plan)

        assert result.report.steps[0].status == STATUS_OK
        assert reg.calls[0]["params"] == {"msg": "hi", "n": 3}

    def test_missing_action_returns_error(self) -> None:
        reg = StubFunctionRegistry()
        runner = TaskRunner()
        register_legacy_actions(runner, reg)

        plan = Plan(
            name="p",
            tasks=[
                Task(
                    id="t1",
                    kind=LEGACY_ACTION_KIND,
                    params={},
                    on_error="skip",
                )
            ],
        )
        result = runner.run(plan)

        assert result.report.steps[0].status == STATUS_ERROR
        assert "action" in (result.report.steps[0].error or "").lower()


# ---------------------------------------------------------------------------
# run_legacy_plan_via_runner (high-level)
# ---------------------------------------------------------------------------


class TestRunLegacyPlanViaRunner:
    def _make_legacy(self) -> List[Dict[str, Any]]:
        return [
            {
                "action": "echo",
                "args": {"msg": "one"},
                "goal": "say one",
                "validation": "output printed",
            },
            {
                "action": "echo",
                "args": {"msg": "two"},
                "goal": "say two",
                "validation": "output printed",
            },
        ]

    def test_basic_execution_without_critic(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("echo", message="echoed")

        result = run_legacy_plan_via_runner(self._make_legacy(), reg)

        assert isinstance(result, LegacyRunResult)
        assert result.approved is True
        assert result.executed is True
        assert result.critique is None
        assert len(result.run_result.report.steps) == 2
        assert all(s.status == STATUS_OK for s in result.run_result.report.steps)
        assert [c["action"] for c in reg.calls] == ["echo", "echo"]

    def test_strips_legacy_meta_before_tool_call(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("echo", message="ok")

        run_legacy_plan_via_runner(self._make_legacy(), reg)

        # args у legacy-плані = {"msg": "one"} — жодних goal/validation/_legacy у реальному tool.
        assert reg.calls[0]["params"] == {"msg": "one"}
        assert "_legacy" not in reg.calls[0]["params"]
        assert "goal" not in reg.calls[0]["params"]

    def test_with_approving_critic(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("echo", message="ok")

        class ApprovingCritic:
            def review(self, plan, *, context="", policies=None):
                return CritiqueResult(verdict=VERDICT_APPROVE)

        result = run_legacy_plan_via_runner(
            self._make_legacy(), reg, critic=ApprovingCritic()
        )

        assert result.approved is True
        assert result.executed is True
        assert result.critique.verdict == VERDICT_APPROVE

    def test_blocked_by_critic_without_replan(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("echo", message="ok")

        class BlockingCritic:
            def review(self, plan, *, context="", policies=None):
                return CritiqueResult(
                    verdict=VERDICT_REDO,
                    concerns=[
                        {
                            "step": 0,
                            "issue": "risky",
                            "severity": "block",
                            "suggestion": "rethink",
                        }
                    ],
                )

        result = run_legacy_plan_via_runner(
            self._make_legacy(),
            reg,
            critic=BlockingCritic(),
            max_redos=0,
        )

        assert result.approved is False
        assert result.executed is False
        assert result.run_result is None
        assert result.attempts == 1
        assert "critic blocked" in result.stop_reason

    def test_replan_recovers(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("echo", message="ok")

        # Fixture: перший раз — redo, другий — approve.
        call_count = {"n": 0}

        class ToggleCritic:
            def review(self, plan, *, context="", policies=None):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return CritiqueResult(
                        verdict=VERDICT_REDO,
                        concerns=[
                            {
                                "step": 0,
                                "issue": "first try bad",
                                "severity": "block",
                                "suggestion": "retry",
                            }
                        ],
                    )
                return CritiqueResult(verdict=VERDICT_APPROVE)

        def _replan(plan, critique):
            return [{"action": "echo", "args": {"msg": "new"}, "goal": "ok"}]

        result = run_legacy_plan_via_runner(
            self._make_legacy(),
            reg,
            critic=ToggleCritic(),
            replan_fn=_replan,
            max_redos=1,
        )

        assert result.approved is True
        assert result.executed is True
        assert result.attempts == 2
        assert len(result.plan) == 1
        assert result.plan[0]["args"] == {"msg": "new"}

    def test_to_dict_is_json_serializable(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("echo", message="ok")

        result = run_legacy_plan_via_runner(self._make_legacy(), reg)
        dumped = result.to_dict()

        import json

        json.dumps(dumped)  # не повинно кидати
        assert dumped["approved"] is True
        assert dumped["executed"] is True
        assert dumped["run_result"]["steps"] == 2
        assert dumped["run_result"]["all_ok"] is True


# ---------------------------------------------------------------------------
# Integration: convert legacy → Plan, execute via TaskRunner directly
# ---------------------------------------------------------------------------


class TestIntegrationLegacyToPlan:
    def test_round_trip_via_legacy_plan_to_plan(self) -> None:
        reg = StubFunctionRegistry()
        reg.add_tool("create_file", message="fc", data={"bytes": 10})
        reg.add_tool("read_file_action", message="rc")

        legacy = [
            {"action": "create_file", "args": {"path": "a.txt"}},
            {"action": "read_file_action", "args": {"path": "a.txt"}},
        ]

        plan_obj: Plan = legacy_plan_to_plan(legacy, name="round")
        assert len(plan_obj.tasks) == 2
        assert plan_obj.tasks[0].kind == "create_file"

        runner = TaskRunner()
        register_legacy_actions(runner, reg)
        result = runner.run(plan_obj)

        assert all(s.status == STATUS_OK for s in result.report.steps)
        assert [c["action"] for c in reg.calls] == [
            "create_file",
            "read_file_action",
        ]
