"""Tests for functions.logic_task_runner (Phase 11.1)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from functions.logic_execution_report import (
    STATUS_DENIED,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    ExecutionReport,
)
from functions.logic_permission_gate import (
    Decision,
    PermissionGate,
    PermissionPolicy,
    always_allow,
    always_deny,
)
from functions.logic_task_runner import (
    ON_ERROR_RETRY,
    ON_ERROR_SKIP,
    ON_ERROR_STOP,
    Plan,
    Task,
    TaskRunner,
)


# --- helpers ----------------------------------------------------------------


@dataclass
class FakeProc:
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


def _make_runner(
    *,
    gate=None,
    subprocess_result=None,
    subprocess_exc=None,
    registry=None,
    budget=None,
    time_source=None,
):
    times = iter(time_source or [1000.0 + i * 0.5 for i in range(200)])

    def _time():
        try:
            return next(times)
        except StopIteration:
            return 9999.0

    calls = []

    def _fake_subprocess(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        if subprocess_exc is not None:
            raise subprocess_exc
        return subprocess_result or FakeProc(stdout="ok")

    sleeps = []
    runner = TaskRunner(
        gate=gate or PermissionGate(ask_fn=always_allow()),
        subprocess_runner=_fake_subprocess,
        sleep_fn=lambda s: sleeps.append(s),
        time_fn=_time,
        registry=registry,
        budget=budget,
    )
    runner._test_subprocess_calls = calls
    runner._test_sleeps = sleeps
    return runner


# --- Plan parsing -----------------------------------------------------------


class TestPlanParsing:
    def test_from_dict_basic(self):
        plan = Plan.from_dict(
            {
                "name": "demo",
                "tasks": [
                    {"id": "a", "kind": "noop"},
                    {"id": "b", "kind": "noop"},
                ],
            }
        )
        assert plan.name == "demo"
        assert len(plan.tasks) == 2
        assert plan.tasks[0].id == "a"

    def test_from_json(self):
        plan = Plan.from_json('{"name": "p", "tasks": [{"id": "x", "kind": "noop"}]}')
        assert plan.name == "p"
        assert plan.tasks[0].kind == "noop"

    def test_from_file(self, tmp_path):
        p = tmp_path / "plan.json"
        p.write_text(
            json.dumps(
                {"name": "filep", "tasks": [{"kind": "noop"}]}
            ),
            encoding="utf-8",
        )
        plan = Plan.from_file(str(p))
        assert plan.name == "filep"
        assert plan.tasks[0].id == "t1"  # auto-assigned

    def test_missing_kind_raises(self):
        with pytest.raises(ValueError, match="missing 'kind'"):
            Plan.from_dict({"name": "bad", "tasks": [{"id": "a"}]})


# --- Noop / log / sleep -----------------------------------------------------


class TestBuiltinSimpleHandlers:
    def test_noop_ok(self):
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="noop", params={"note": "hello"})],
        )
        result = runner.run(plan)
        assert result.all_ok is True
        assert len(result.report.steps) == 1
        assert result.report.steps[0].status == STATUS_OK
        assert "hello" in result.report.steps[0].summary

    def test_log_adds_event(self):
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="log", params={"message": "hi!"})],
        )
        result = runner.run(plan)
        assert result.all_ok is True
        assert any("hi!" in e.message for e in result.report.events)

    def test_sleep_calls_sleep_fn(self):
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="sleep", params={"seconds": 1.5})],
        )
        runner.run(plan)
        assert 1.5 in runner._test_sleeps


# --- run_command -----------------------------------------------------------


class TestRunCommand:
    def test_safe_prefix_runs(self):
        runner = _make_runner(subprocess_result=FakeProc(stdout="clean", returncode=0))
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="run_command", params={"cmd": "git status"})],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_OK
        assert "clean" in result.report.steps[0].stdout_tail

    def test_denied_command(self):
        gate = PermissionGate(ask_fn=always_deny())
        runner = _make_runner(gate=gate)
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="run_command", params={"cmd": "weird-tool"})],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_DENIED
        assert result.all_ok is False

    def test_nonzero_exit_is_error(self):
        runner = _make_runner(
            subprocess_result=FakeProc(stdout="", stderr="fail!", returncode=2)
        )
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="run_command", params={"cmd": "git status"})],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_ERROR
        assert "fail!" in result.report.steps[0].error

    def test_subprocess_exception_becomes_error(self):
        runner = _make_runner(subprocess_exc=TimeoutError("too slow"))
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="run_command", params={"cmd": "git status"})],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_ERROR
        assert "TimeoutError" in result.report.steps[0].error

    def test_missing_cmd(self):
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="run_command", params={})],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_ERROR


# --- read/write file -------------------------------------------------------


class TestFileHandlers:
    def test_write_file_in_project_root(self, tmp_path):
        policy = PermissionPolicy(project_root=str(tmp_path))
        gate = PermissionGate(policy=policy, ask_fn=always_deny())
        runner = _make_runner(gate=gate)
        target = tmp_path / "out.txt"
        plan = Plan(
            name="t",
            tasks=[
                Task(
                    id="a",
                    kind="write_file",
                    params={"path": str(target), "content": "hello"},
                )
            ],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_OK
        assert target.read_text(encoding="utf-8") == "hello"

    def test_write_file_denied_outside_project(self, tmp_path):
        policy = PermissionPolicy(project_root=str(tmp_path / "project"))
        gate = PermissionGate(policy=policy, ask_fn=always_deny())
        runner = _make_runner(gate=gate)
        outside = tmp_path / "other.txt"
        plan = Plan(
            name="t",
            tasks=[
                Task(
                    id="a",
                    kind="write_file",
                    params={"path": str(outside), "content": "no"},
                )
            ],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_DENIED
        assert not outside.exists()

    def test_read_file(self, tmp_path):
        target = tmp_path / "in.txt"
        target.write_text("payload", encoding="utf-8")
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="read_file", params={"path": str(target)})],
        )
        result = runner.run(plan)
        step = result.report.steps[0]
        assert step.status == STATUS_OK
        assert step.metadata["content"] == "payload"


# --- depends_on ------------------------------------------------------------


class TestDependencies:
    def test_skipped_when_dep_failed(self):
        runner = _make_runner(
            subprocess_result=FakeProc(returncode=1, stderr="boom")
        )
        plan = Plan(
            name="t",
            tasks=[
                Task(id="a", kind="run_command", params={"cmd": "git status"},
                     on_error=ON_ERROR_SKIP),
                Task(id="b", kind="noop", depends_on=["a"]),
            ],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_ERROR
        assert result.report.steps[1].status == STATUS_SKIPPED

    def test_runs_when_dep_ok(self):
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[
                Task(id="a", kind="noop"),
                Task(id="b", kind="noop", depends_on=["a"]),
            ],
        )
        result = runner.run(plan)
        assert result.report.steps[1].status == STATUS_OK


# --- on_error --------------------------------------------------------------


class TestOnError:
    def test_stop_halts_on_failure(self):
        runner = _make_runner(
            subprocess_result=FakeProc(returncode=1, stderr="no")
        )
        plan = Plan(
            name="t",
            tasks=[
                Task(id="a", kind="run_command", params={"cmd": "git status"}),
                Task(id="b", kind="noop"),
            ],
        )
        result = runner.run(plan)
        assert result.stopped_early is True
        assert len(result.report.steps) == 1

    def test_skip_continues(self):
        runner = _make_runner(
            subprocess_result=FakeProc(returncode=1, stderr="no")
        )
        plan = Plan(
            name="t",
            tasks=[
                Task(
                    id="a",
                    kind="run_command",
                    params={"cmd": "git status"},
                    on_error=ON_ERROR_SKIP,
                ),
                Task(id="b", kind="noop"),
            ],
        )
        result = runner.run(plan)
        assert len(result.report.steps) == 2
        assert result.report.steps[1].status == STATUS_OK
        assert result.all_ok is False

    def test_retry_eventual_success(self):
        outcomes = iter(
            [FakeProc(returncode=1, stderr="try1"), FakeProc(returncode=0, stdout="win")]
        )

        def fake_sub(cmd, **kw):
            return next(outcomes)

        gate = PermissionGate(ask_fn=always_allow())
        runner = TaskRunner(
            gate=gate,
            subprocess_runner=fake_sub,
            sleep_fn=lambda s: None,
            time_fn=lambda: 100.0,
        )
        plan = Plan(
            name="t",
            tasks=[
                Task(
                    id="a",
                    kind="run_command",
                    params={"cmd": "git status"},
                    on_error=ON_ERROR_RETRY,
                    max_retries=1,
                )
            ],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_OK
        assert "win" in result.report.steps[0].stdout_tail


# --- Budget ----------------------------------------------------------------


class TestBudget:
    def test_budget_stops_before_task(self):
        class _Budget:
            def should_stop(self):
                return True

        runner = _make_runner(budget=_Budget())
        plan = Plan(name="t", tasks=[Task(id="a", kind="noop")])
        result = runner.run(plan)
        assert result.stopped_early is True
        assert "budget" in result.stop_reason.lower()
        assert result.report.steps == []

    def test_should_stop_fn(self):
        state = {"stop": False}
        runner = TaskRunner(
            gate=PermissionGate(ask_fn=always_allow()),
            time_fn=lambda: 100.0,
            should_stop_fn=lambda: state["stop"],
        )
        plan = Plan(
            name="t",
            tasks=[
                Task(id="a", kind="noop"),
                Task(id="b", kind="noop"),
            ],
        )

        # on "b", stop
        original_run_one = runner._run_one

        def _wrap(task, report, previous):
            if task.id == "a":
                state["stop"] = True
            return original_run_one(task, report, previous)

        runner._run_one = _wrap  # type: ignore[method-assign]
        result = runner.run(plan)
        assert result.stopped_early is True
        assert len(result.report.steps) == 1


# --- call_provider ---------------------------------------------------------


class TestCallProvider:
    def test_no_registry_errors(self):
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[
                Task(id="a", kind="call_provider", params={"prompt": "hi"})
            ],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_ERROR
        assert "registry" in result.report.steps[0].error

    def test_with_fake_registry(self):
        from functions.logic_ai_adapter import ChatRequest, ChatResponse, UsageInfo

        class _FakeRegistry:
            def chat(self, req: ChatRequest) -> ChatResponse:
                return ChatResponse(
                    content="pong",
                    provider="fake",
                    model="m",
                    finish_reason="stop",
                    usage=UsageInfo(
                        prompt_tokens=5, completion_tokens=3, cost_usd=0.002
                    ),
                )

        runner = _make_runner(registry=_FakeRegistry())
        plan = Plan(
            name="t",
            tasks=[
                Task(id="a", kind="call_provider", params={"prompt": "ping"})
            ],
        )
        result = runner.run(plan)
        step = result.report.steps[0]
        assert step.status == STATUS_OK
        assert "pong" in step.summary
        assert step.cost_usd == pytest.approx(0.002)
        assert step.prompt_tokens == 5


# --- sub_plan --------------------------------------------------------------


class TestSubPlan:
    def test_sub_plan_inlines_into_same_report(self):
        runner = _make_runner()
        plan = Plan(
            name="outer",
            tasks=[
                Task(
                    id="parent",
                    kind="sub_plan",
                    params={
                        "plan": {
                            "name": "inner",
                            "tasks": [
                                {"id": "c1", "kind": "noop"},
                                {"id": "c2", "kind": "noop"},
                            ],
                        }
                    },
                )
            ],
        )
        result = runner.run(plan)
        ids = [s.task_id for s in result.report.steps]
        assert "c1" in ids and "c2" in ids and "parent" in ids


# --- custom handler --------------------------------------------------------


class TestCustomHandler:
    def test_register_custom_kind(self):
        runner = _make_runner()

        def my_handler(ctx):
            return {"status": STATUS_OK, "summary": f"handled {ctx.task.id}"}

        runner.register("custom-kind", my_handler)
        plan = Plan(
            name="t",
            tasks=[Task(id="x", kind="custom-kind")],
        )
        result = runner.run(plan)
        assert result.report.steps[0].summary == "handled x"

    def test_unknown_kind_is_error(self):
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[Task(id="x", kind="never-registered")],
        )
        result = runner.run(plan)
        assert result.report.steps[0].status == STATUS_ERROR
        assert "unknown kind" in result.report.steps[0].error


# --- integration smoke ------------------------------------------------------


class TestIntegrationSmoke:
    def test_end_to_end_report(self, tmp_path):
        policy = PermissionPolicy(project_root=str(tmp_path))
        gate = PermissionGate(policy=policy, ask_fn=always_deny())
        runner = TaskRunner(
            gate=gate,
            subprocess_runner=lambda cmd, **kw: FakeProc(stdout="all good"),
            sleep_fn=lambda s: None,
            time_fn=lambda: 500.0,
        )
        out = tmp_path / "hello.txt"
        plan = Plan(
            name="smoke",
            tasks=[
                Task(id="t1", kind="log", params={"message": "start"}),
                Task(id="t2", kind="run_command", params={"cmd": "git status"}),
                Task(
                    id="t3",
                    kind="write_file",
                    params={"path": str(out), "content": "hi"},
                ),
                Task(id="t4", kind="noop", params={"note": "done"}),
            ],
        )
        report_path = tmp_path / "report.md"
        result = runner.run(plan, report=ExecutionReport(
            plan_name="smoke", autosave_path=str(report_path), time_fn=lambda: 500.0
        ))
        assert result.all_ok is True
        assert out.read_text(encoding="utf-8") == "hi"
        assert report_path.exists()
        md = report_path.read_text(encoding="utf-8")
        assert "smoke" in md
        assert "start" in md
