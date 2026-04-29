"""Integration tests: TaskRunner + Step-Check (Phase 12.1)."""
from __future__ import annotations

from functions.logic_execution_report import (
    STATUS_EXPECT_FAILED,
    STATUS_OK,
    STATUS_PRECHECK_FAILED,
)
from functions.logic_expectations import ExpectSpec
from functions.logic_permission_gate import Decision, PermissionGate
from functions.logic_task_runner import Plan, Task, TaskRunner


def _runner(**kw) -> TaskRunner:
    gate = PermissionGate(ask_fn=lambda req: Decision(allow=True, reason="test"))
    return TaskRunner(gate=gate, **kw)


# ---------------------------------------------------------------------------
# Plan.from_dict — parsing expect/precheck
# ---------------------------------------------------------------------------


def test_plan_from_dict_parses_expect_and_precheck():
    data = {
        "name": "p",
        "tasks": [
            {
                "id": "t1",
                "kind": "noop",
                "precheck": [{"kind": "file_exists", "path": "/a"}],
                "expect": {"kind": "file_exists", "path": "/b"},
            }
        ],
    }
    plan = Plan.from_dict(data)
    t = plan.tasks[0]
    assert len(t.precheck) == 1
    assert t.precheck[0].kind == "file_exists"
    assert t.precheck[0].params == {"path": "/a"}
    assert len(t.expect) == 1
    assert t.expect[0].kind == "file_exists"


def test_plan_from_dict_no_expect_defaults_empty():
    plan = Plan.from_dict(
        {"name": "p", "tasks": [{"id": "t1", "kind": "noop"}]}
    )
    assert plan.tasks[0].precheck == []
    assert plan.tasks[0].expect == []


# ---------------------------------------------------------------------------
# Precheck — Step-Check (pre-handler)
# ---------------------------------------------------------------------------


def test_precheck_passes_runs_handler(tmp_path):
    f = tmp_path / "exists.txt"
    f.write_text("ok")
    runner = _runner()
    task = Task(
        id="t1",
        kind="log",
        params={"message": "hi"},
        precheck=[ExpectSpec(kind="file_exists", params={"path": str(f)})],
    )
    plan = Plan(name="p", tasks=[task])
    res = runner.run(plan)
    assert res.all_ok
    assert res.report.steps[0].status == STATUS_OK
    assert res.report.steps[0].metadata.get("precheck_results") is None


def test_precheck_fails_skips_handler(tmp_path):
    runner = _runner()
    called = {"n": 0}

    def handler(ctx):
        called["n"] += 1
        return {"status": STATUS_OK}

    runner.register("probe", handler)
    task = Task(
        id="t1",
        kind="probe",
        precheck=[
            ExpectSpec(
                kind="file_exists",
                params={"path": str(tmp_path / "none.txt")},
            )
        ],
    )
    res = runner.run(Plan(name="p", tasks=[task]))
    assert not res.all_ok
    step = res.report.steps[0]
    assert step.status == STATUS_PRECHECK_FAILED
    assert "file not found" in step.error
    assert called["n"] == 0
    # on_error default = stop → plan зупинено
    assert res.stopped_early


def test_precheck_failure_with_on_error_skip_continues(tmp_path):
    runner = _runner()
    task1 = Task(
        id="t1",
        kind="noop",
        on_error="skip",
        precheck=[
            ExpectSpec(
                kind="file_exists",
                params={"path": str(tmp_path / "none.txt")},
            )
        ],
    )
    task2 = Task(id="t2", kind="noop", params={"note": "continues"})
    res = runner.run(Plan(name="p", tasks=[task1, task2]))
    # t1 precheck_failed, t2 ok → plan not fully ok, але виконується
    assert res.report.steps[0].status == STATUS_PRECHECK_FAILED
    assert res.report.steps[1].status == STATUS_OK
    assert not res.stopped_early


# ---------------------------------------------------------------------------
# Expect — Actor-Critic MVP (post-handler)
# ---------------------------------------------------------------------------


def test_expect_all_ok_keeps_status_ok(tmp_path):
    f = tmp_path / "out.txt"
    runner = _runner()

    def make_file(ctx):
        f.write_text("done")
        return {"status": STATUS_OK}

    runner.register("make", make_file)
    task = Task(
        id="t1",
        kind="make",
        expect=[ExpectSpec(kind="file_exists", params={"path": str(f)})],
    )
    res = runner.run(Plan(name="p", tasks=[task]))
    assert res.all_ok
    step = res.report.steps[0]
    assert step.status == STATUS_OK
    assert "expect_results" in step.metadata
    assert all(r["ok"] for r in step.metadata["expect_results"])


def test_expect_fail_changes_status(tmp_path):
    runner = _runner()

    def claims_success(ctx):
        return {"status": STATUS_OK, "summary": "claimed OK"}

    runner.register("liar", claims_success)
    task = Task(
        id="t1",
        kind="liar",
        expect=[
            ExpectSpec(
                kind="file_exists",
                params={"path": str(tmp_path / "nope.txt")},
            )
        ],
    )
    res = runner.run(Plan(name="p", tasks=[task]))
    step = res.report.steps[0]
    assert step.status == STATUS_EXPECT_FAILED
    assert "expect failed" in step.summary
    assert "file not found" in step.error
    assert step.metadata["expect_results"][0]["ok"] is False


def test_expect_skipped_when_handler_failed():
    runner = _runner()

    def broken(ctx):
        raise RuntimeError("boom")

    runner.register("broken", broken)
    task = Task(
        id="t1",
        kind="broken",
        expect=[
            ExpectSpec(kind="file_exists", params={"path": "/does/not/matter"})
        ],
    )
    res = runner.run(Plan(name="p", tasks=[task]))
    step = res.report.steps[0]
    # Handler crashed — status=error, expect not evaluated
    assert step.status != STATUS_EXPECT_FAILED
    assert step.status == "error"
    assert "expect_results" not in step.metadata


def test_expect_with_retry_succeeds_second_attempt(tmp_path):
    """Handler повертає OK обидва рази, але state змінюється — на 1-й
    спробі файлу ще немає, на 2-й зʼявляється. Retry має повторити саме
    через expect_failed."""
    f = tmp_path / "late.txt"
    runner = _runner()
    attempts = {"n": 0}

    def appear(ctx):
        attempts["n"] += 1
        if attempts["n"] == 2:
            f.write_text("done")
        return {"status": STATUS_OK}

    runner.register("appear", appear)
    task = Task(
        id="t1",
        kind="appear",
        on_error="retry",
        max_retries=2,
        retry_delay_s=0.0,
        expect=[ExpectSpec(kind="file_exists", params={"path": str(f)})],
    )
    res = runner.run(Plan(name="p", tasks=[task]))
    assert res.all_ok
    assert attempts["n"] == 2
    assert res.report.steps[0].status == STATUS_OK


def test_expect_multiple_all_must_pass(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("1")
    b = tmp_path / "b.txt"  # not created
    runner = _runner()
    task = Task(
        id="t1",
        kind="noop",
        expect=[
            ExpectSpec(kind="file_exists", params={"path": str(a)}),
            ExpectSpec(kind="file_exists", params={"path": str(b)}),
        ],
    )
    res = runner.run(Plan(name="p", tasks=[task]))
    step = res.report.steps[0]
    assert step.status == STATUS_EXPECT_FAILED
    results = step.metadata["expect_results"]
    assert [r["ok"] for r in results] == [True, False]


# ---------------------------------------------------------------------------
# Relative path resolution with runner.cwd
# ---------------------------------------------------------------------------


def test_expect_uses_runner_cwd_for_relative_paths(tmp_path):
    f = tmp_path / "rel.txt"
    f.write_text("x")
    runner = _runner(cwd=str(tmp_path))
    task = Task(
        id="t1",
        kind="noop",
        expect=[ExpectSpec(kind="file_exists", params={"path": "rel.txt"})],
    )
    res = runner.run(Plan(name="p", tasks=[task]))
    assert res.all_ok
    assert res.report.steps[0].status == STATUS_OK
