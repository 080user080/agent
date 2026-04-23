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

    def test_log_task_spec_handler_ok(self):
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[
                Task(
                    id="a",
                    kind="log_task_spec",
                    params={
                        "placeholder_step": True,
                        "spec_task_id": "tid42",
                        "spec_domain": "code",
                        "spec_goal": "build thing",
                    },
                )
            ],
        )
        result = runner.run(plan)
        assert result.all_ok is True
        step = result.report.steps[0]
        assert step.status == STATUS_OK
        assert "tid42" in step.summary
        assert "code" in step.summary
        assert any("tid42" in e.message for e in result.report.events)

    def test_log_task_spec_handler_missing_params_ok(self):
        """Handler не повинен падати навіть якщо TaskSpec-поля відсутні."""
        runner = _make_runner()
        plan = Plan(
            name="t",
            tasks=[Task(id="a", kind="log_task_spec", params={})],
        )
        result = runner.run(plan)
        assert result.all_ok is True

    def test_skeleton_pipeline_plan_runnable(self):
        """Kомплексний тест S6→S7: SkeletonPipeline Plan виконується на TaskRunner."""
        from functions.core_plan_compiler import SkeletonPipeline
        from functions.core_task_intake import DOMAIN_MIXED, TaskSpec

        spec = TaskSpec(goal="demo", domain=DOMAIN_MIXED)
        plan = SkeletonPipeline().compile(spec)
        runner = _make_runner()
        result = runner.run(plan)
        assert result.all_ok is True
        assert result.report.steps[0].status == STATUS_OK


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


# --- batch_task (Phase 13 S8a) ---------------------------------------------


class TestBatchTaskHandler:
    def _items_plan(self, items, template, **batch_params):
        params = {"items": items, "task_template": template}
        params.update(batch_params)
        return Plan(name="b", tasks=[Task(id="batch", kind="batch_task", params=params)])

    def test_happy_path_all_ok(self):
        runner = _make_runner()
        plan = self._items_plan(
            items=["a", "b", "c"],
            template={"kind": "log", "params": {"message": "m"}},
        )
        result = runner.run(plan)
        assert result.all_ok is True
        batch_step = result.report.steps[-1]
        assert batch_step.status == STATUS_OK
        assert "3 items" in batch_step.summary
        assert "ok=3" in batch_step.summary
        meta = batch_step.metadata or {}
        assert meta["items_total"] == 3
        assert meta["items_ok"] == 3
        assert meta["items_failed"] == 0
        assert len(meta["per_item"]) == 3

    def test_item_param_injection(self):
        """Кожен item інʼєктиться під item_param у params."""
        seen = []

        def capturing_handler(ctx):
            seen.append(ctx.task.params.get("photo"))
            return {"status": STATUS_OK, "summary": "ok"}

        runner = _make_runner()
        runner.register("capture", capturing_handler)
        plan = self._items_plan(
            items=["one.jpg", "two.jpg"],
            template={"kind": "capture", "params": {"scale": 2}},
            item_param="photo",
        )
        runner.run(plan)
        assert seen == ["one.jpg", "two.jpg"]

    def test_default_item_param_is_item(self):
        seen = []

        def capturing_handler(ctx):
            seen.append(ctx.task.params.get("item"))
            return {"status": STATUS_OK}

        runner = _make_runner()
        runner.register("capture", capturing_handler)
        plan = self._items_plan(
            items=[1, 2, 3],
            template={"kind": "capture"},
        )
        runner.run(plan)
        assert seen == [1, 2, 3]

    def test_batch_index_is_injected(self):
        seen = []

        def capturing_handler(ctx):
            seen.append(ctx.task.params.get("batch_index"))
            return {"status": STATUS_OK}

        runner = _make_runner()
        runner.register("capture", capturing_handler)
        plan = self._items_plan(
            items=["a", "b", "c"],
            template={"kind": "capture"},
        )
        runner.run(plan)
        assert seen == [0, 1, 2]

    def test_empty_items_is_ok(self):
        runner = _make_runner()
        plan = self._items_plan(
            items=[],
            template={"kind": "log", "params": {"message": "m"}},
        )
        result = runner.run(plan)
        assert result.all_ok is True
        batch_step = result.report.steps[-1]
        assert batch_step.metadata["items_total"] == 0
        assert batch_step.metadata["items_ok"] == 0

    def test_missing_items_errors(self):
        runner = _make_runner()
        plan = Plan(name="b", tasks=[
            Task(id="batch", kind="batch_task", params={
                "task_template": {"kind": "noop"},
            }),
        ])
        result = runner.run(plan)
        assert result.all_ok is False
        assert "'items'" in result.report.steps[-1].error

    def test_missing_template_errors(self):
        runner = _make_runner()
        plan = Plan(name="b", tasks=[
            Task(id="batch", kind="batch_task", params={"items": [1, 2]}),
        ])
        result = runner.run(plan)
        assert result.all_ok is False
        assert "task_template" in result.report.steps[-1].error

    def test_template_without_kind_errors(self):
        runner = _make_runner()
        plan = Plan(name="b", tasks=[
            Task(id="batch", kind="batch_task", params={
                "items": [1], "task_template": {"params": {}},
            }),
        ])
        result = runner.run(plan)
        assert result.all_ok is False
        assert "kind" in result.report.steps[-1].error

    def test_on_item_error_skip_continues(self):
        """on_item_error=skip (default) — fail одного item не зупиняє батч."""
        calls = [0]

        def flaky(ctx):
            calls[0] += 1
            item = ctx.task.params.get("item")
            if item == "bad":
                return {"status": STATUS_ERROR, "error": "oops"}
            return {"status": STATUS_OK}

        runner = _make_runner()
        runner.register("flaky", flaky)
        plan = self._items_plan(
            items=["a", "bad", "c"],
            template={"kind": "flaky"},
        )
        result = runner.run(plan)
        # батч як ціле fail бо був item-fail
        assert result.all_ok is False
        batch_step = result.report.steps[-1]
        assert batch_step.metadata["items_ok"] == 2
        assert batch_step.metadata["items_failed"] == 1
        # але всі 3 itemи оброблені
        assert calls[0] == 3

    def test_on_item_error_stop_halts(self):
        calls = [0]

        def flaky(ctx):
            calls[0] += 1
            if ctx.task.params.get("item") == "bad":
                return {"status": STATUS_ERROR, "error": "oops"}
            return {"status": STATUS_OK}

        runner = _make_runner()
        runner.register("flaky", flaky)
        plan = self._items_plan(
            items=["a", "bad", "c"],
            template={"kind": "flaky"},
            on_item_error=ON_ERROR_STOP,
        )
        result = runner.run(plan)
        assert result.all_ok is False
        # третій item не оброблено
        assert calls[0] == 2
        batch_step = result.report.steps[-1]
        assert batch_step.metadata["stopped_early"] is True

    def test_max_failures_triggers_stop(self):
        """max_failures=1 означає: коли перевищимо — батч зупиняється."""
        def always_fail(ctx):
            return {"status": STATUS_ERROR, "error": "nope"}

        runner = _make_runner()
        runner.register("fail", always_fail)
        plan = self._items_plan(
            items=[1, 2, 3, 4, 5],
            template={"kind": "fail"},
            max_failures=1,
        )
        result = runner.run(plan)
        assert result.all_ok is False
        batch_step = result.report.steps[-1]
        # після 2-го fail (>max_failures=1) — стоп
        assert batch_step.metadata["items_failed"] == 2
        assert batch_step.metadata["stopped_early"] is True

    def test_invalid_on_item_error_value(self):
        runner = _make_runner()
        plan = self._items_plan(
            items=[1],
            template={"kind": "noop"},
            on_item_error="unknown",
        )
        result = runner.run(plan)
        assert result.all_ok is False
        assert "on_item_error" in result.report.steps[-1].error

    def test_per_item_reports_recorded(self):
        """Per-item StepReport-и повинні бути записані у головний звіт."""
        runner = _make_runner()
        plan = self._items_plan(
            items=[1, 2, 3],
            template={"kind": "noop"},
        )
        result = runner.run(plan)
        # 3 item-и + 1 batch = 4 steps у звіті
        assert len(result.report.steps) == 4
        item_ids = [s.task_id for s in result.report.steps[:3]]
        assert item_ids == ["batch__item_0", "batch__item_1", "batch__item_2"]

    def test_progress_event_logged(self):
        runner = _make_runner()
        plan = self._items_plan(
            items=list(range(25)),
            template={"kind": "noop"},
            progress_every=10,
        )
        result = runner.run(plan)
        progress_events = [
            e for e in result.report.events if "batch progress" in e.message
        ]
        # на 25 items з progress_every=10 — 2 progress-евенти (на 10 і 20)
        assert len(progress_events) >= 2

    def test_progress_every_disabled(self):
        runner = _make_runner()
        plan = self._items_plan(
            items=list(range(15)),
            template={"kind": "noop"},
            progress_every=-1,
        )
        r = runner.run(plan)
        progress_events = [
            e for e in r.report.events if "batch progress" in e.message
        ]
        assert progress_events == []

    def test_custom_item_id_prefix(self):
        runner = _make_runner()
        plan = self._items_plan(
            items=["x", "y"],
            template={"kind": "noop"},
            item_id_prefix="photo",
        )
        result = runner.run(plan)
        item_ids = [s.task_id for s in result.report.steps[:2]]
        assert item_ids == ["photo__item_0", "photo__item_1"]

    def test_budget_stops_batch_mid_run(self):
        class _Budget:
            def __init__(self):
                self.calls = 0

            def should_stop(self):
                self.calls += 1
                return self.calls > 2

        budget = _Budget()
        runner = _make_runner(budget=budget)
        plan = self._items_plan(
            items=list(range(10)),
            template={"kind": "noop"},
        )
        result = runner.run(plan)
        batch_step = result.report.steps[-1]
        assert batch_step.metadata["stopped_early"] is True
        # оброблено менше ніж 10
        assert batch_step.metadata["items_total"] == 10
        assert batch_step.metadata["items_ok"] < 10
