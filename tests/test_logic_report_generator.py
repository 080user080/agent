"""Unit tests for logic_report_generator (Phase 13 S10 / 13.10)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from functions.logic_execution_report import (
    STATUS_DENIED,
    STATUS_ERROR,
    STATUS_EXPECT_FAILED,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_TIMEOUT,
    ExecutionReport,
    StepReport,
)
from functions.logic_report_generator import (
    ReportSummary,
    build_report_summary,
    generate_report,
    render_summary_markdown,
)


# Tiny TaskSpec stand-in to avoid heavyweight intake construction.
@dataclass
class _FakeSpec:
    goal: str = ""
    domain: str = ""


def _make_step(
    task_id: str,
    *,
    status: str = STATUS_OK,
    kind: str = "run_command",
    duration_s: float = 1.0,
    summary: str = "",
    error: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> StepReport:
    return StepReport(
        task_id=task_id,
        task_name=task_id,
        kind=kind,
        status=status,
        duration_s=duration_s,
        summary=summary,
        error=error,
        metadata=metadata or {},
    )


def _make_report(
    steps: List[StepReport],
    *,
    plan_name: str = "test-plan",
    footer_budget: Optional[Dict[str, Any]] = None,
) -> ExecutionReport:
    rep = ExecutionReport(plan_name=plan_name)
    for s in steps:
        rep.steps.append(s)
    if footer_budget:
        rep.footer.budget_snapshot = dict(footer_budget)
    rep.finished_at = rep.started_at + sum(s.duration_s for s in steps)
    return rep


# ---------------------------------------------------------------------------
# build_report_summary
# ---------------------------------------------------------------------------


class TestBuildSummary:
    def test_all_ok_success(self):
        rep = _make_report([_make_step("t1"), _make_step("t2")])
        s = build_report_summary(rep)
        assert s.verdict == "success"
        assert s.overall_ok
        assert s.steps_total == 2
        assert s.by_status.get(STATUS_OK) == 2
        assert not s.failed_steps

    def test_with_task_spec(self):
        rep = _make_report([_make_step("t1")])
        spec = _FakeSpec(goal="Build CRUD", domain="code")
        s = build_report_summary(rep, task_spec=spec)
        assert s.goal == "Build CRUD"
        assert s.domain == "code"

    def test_partial_verdict(self):
        rep = _make_report(
            [
                _make_step("t1"),
                _make_step("t2", status=STATUS_ERROR, error="boom"),
            ]
        )
        s = build_report_summary(rep)
        assert s.verdict == "partial"
        assert not s.overall_ok
        assert "t2" in s.failed_steps

    def test_failed_verdict_all_errored(self):
        rep = _make_report(
            [
                _make_step("t1", status=STATUS_ERROR),
                _make_step("t2", status=STATUS_TIMEOUT),
            ]
        )
        s = build_report_summary(rep)
        assert s.verdict == "failed"
        assert not s.overall_ok

    def test_counts_all_fail_statuses(self):
        rep = _make_report(
            [
                _make_step("ok1"),
                _make_step("err1", status=STATUS_ERROR),
                _make_step("den1", status=STATUS_DENIED),
                _make_step("tmo1", status=STATUS_TIMEOUT),
                _make_step("exp1", status=STATUS_EXPECT_FAILED),
            ]
        )
        s = build_report_summary(rep)
        assert set(s.failed_steps) == {"err1", "den1", "tmo1", "exp1"}

    def test_failed_expectations_extracted(self):
        rep = _make_report(
            [
                _make_step(
                    "t1",
                    status=STATUS_EXPECT_FAILED,
                    metadata={
                        "expect_results": [
                            {
                                "kind": "file_exists",
                                "ok": False,
                                "reason": "file not found: /tmp/x",
                            },
                            {"kind": "return_code", "ok": True},
                        ]
                    },
                )
            ]
        )
        s = build_report_summary(rep)
        assert len(s.failed_expectations) == 1
        exp = s.failed_expectations[0]
        assert exp["kind"] == "file_exists"
        assert exp["task_id"] == "t1"
        assert "not found" in exp["reason"]

    def test_milestones_grouping(self):
        rep = _make_report(
            [
                _make_step("t1", metadata={"milestone": "m1"}),
                _make_step("t2", metadata={"milestone": "m1"}),
                _make_step(
                    "t3",
                    status=STATUS_ERROR,
                    metadata={"milestone": "m2"},
                ),
            ]
        )
        s = build_report_summary(rep)
        assert [m["name"] for m in s.milestones] == ["m1", "m2"]
        m1 = s.milestones[0]
        m2 = s.milestones[1]
        assert m1["steps"] == 2
        assert m1["ok"] == 2
        assert m1["status"] == STATUS_OK
        assert m2["failed"] == 1
        assert m2["status"] == STATUS_ERROR

    def test_default_milestone_when_missing(self):
        rep = _make_report([_make_step("t1"), _make_step("t2")])
        s = build_report_summary(rep)
        assert len(s.milestones) == 1
        assert s.milestones[0]["name"] == "default"

    def test_partial_batches_detected(self):
        rep = _make_report(
            [
                _make_step(
                    "batch1",
                    kind="batch_task",
                    status=STATUS_ERROR,
                    metadata={
                        "items_total": 10,
                        "items_ok": 7,
                        "items_failed": 2,
                        "items_skipped": 1,
                        "stopped_early": False,
                    },
                )
            ]
        )
        s = build_report_summary(rep)
        assert len(s.partial_batches) == 1
        b = s.partial_batches[0]
        assert b["total"] == 10
        assert b["failed"] == 2
        assert b["skipped"] == 1

    def test_clean_batch_not_in_partial_list(self):
        rep = _make_report(
            [
                _make_step(
                    "batch1",
                    kind="batch_task",
                    metadata={
                        "items_total": 5,
                        "items_ok": 5,
                        "items_failed": 0,
                        "items_skipped": 0,
                        "stopped_early": False,
                    },
                )
            ]
        )
        s = build_report_summary(rep)
        assert s.partial_batches == []

    def test_stopped_early_batch_captured(self):
        rep = _make_report(
            [
                _make_step(
                    "batch1",
                    kind="batch_task",
                    status=STATUS_ERROR,
                    metadata={
                        "items_total": 10,
                        "items_ok": 3,
                        "items_failed": 0,
                        "items_skipped": 0,
                        "stopped_early": True,
                    },
                )
            ]
        )
        s = build_report_summary(rep)
        assert len(s.partial_batches) == 1
        assert s.partial_batches[0]["stopped_early"] is True

    def test_issues_include_budget_stop(self):
        rep = _make_report(
            [_make_step("t1")],
            footer_budget={"stopped_reason": "wall_clock_exceeded"},
        )
        s = build_report_summary(rep)
        assert any("wall_clock" in i for i in s.issues)

    def test_issues_include_denied_and_timeout(self):
        rep = _make_report(
            [
                _make_step("t1", status=STATUS_DENIED, error="user denied"),
                _make_step("t2", status=STATUS_TIMEOUT),
            ]
        )
        s = build_report_summary(rep)
        has_denied = any("Denied" in i and "t1" in i for i in s.issues)
        has_timeout = any("Timeout" in i and "t2" in i for i in s.issues)
        assert has_denied
        assert has_timeout


# ---------------------------------------------------------------------------
# next-step hints
# ---------------------------------------------------------------------------


class TestNextSteps:
    def test_success_has_encouragement(self):
        rep = _make_report([_make_step("t1")])
        s = build_report_summary(rep)
        assert any("наступного" in n.lower() or "next" in n.lower() for n in s.next_steps)

    def test_failure_suggests_rerun(self):
        rep = _make_report(
            [
                _make_step("t1", status=STATUS_ERROR, error="boom"),
            ]
        )
        s = build_report_summary(rep)
        joined = " ".join(s.next_steps)
        assert "t1" in joined

    def test_failed_expectation_surfaces_as_hint(self):
        rep = _make_report(
            [
                _make_step(
                    "t1",
                    status=STATUS_EXPECT_FAILED,
                    metadata={
                        "expect_results": [
                            {
                                "kind": "python_parseable",
                                "ok": False,
                                "reason": "SyntaxError at line 1",
                            }
                        ]
                    },
                )
            ]
        )
        s = build_report_summary(rep)
        joined = " ".join(s.next_steps)
        assert "python_parseable" in joined

    def test_partial_batch_suggests_rerun(self):
        rep = _make_report(
            [
                _make_step(
                    "batch1",
                    kind="batch_task",
                    status=STATUS_ERROR,
                    metadata={
                        "items_total": 10,
                        "items_ok": 5,
                        "items_failed": 3,
                        "items_skipped": 2,
                        "stopped_early": False,
                    },
                )
            ]
        )
        s = build_report_summary(rep)
        joined = " ".join(s.next_steps)
        assert "batch1" in joined


# ---------------------------------------------------------------------------
# render_summary_markdown
# ---------------------------------------------------------------------------


class TestRenderMarkdown:
    def test_success_contains_ok_marker(self):
        s = ReportSummary(verdict="success", plan_name="demo", overall_ok=True)
        md = render_summary_markdown(s)
        assert "[OK]" in md
        assert "demo" in md

    def test_partial_marker(self):
        s = ReportSummary(verdict="partial", plan_name="demo")
        md = render_summary_markdown(s)
        assert "[PARTIAL]" in md

    def test_failed_marker(self):
        s = ReportSummary(verdict="failed", plan_name="demo")
        md = render_summary_markdown(s)
        assert "[FAIL]" in md

    def test_goal_rendered_when_present(self):
        s = ReportSummary(
            verdict="success",
            plan_name="demo",
            goal="Build CRUD for User model",
            overall_ok=True,
        )
        md = render_summary_markdown(s)
        assert "Build CRUD" in md

    def test_milestones_table_rendered(self):
        s = ReportSummary(
            verdict="success",
            plan_name="demo",
            overall_ok=True,
            milestones=[
                {
                    "name": "m1",
                    "steps": 2,
                    "ok": 2,
                    "failed": 0,
                    "skipped": 0,
                    "duration_s": 1.5,
                    "status": "ok",
                }
            ],
        )
        md = render_summary_markdown(s)
        assert "## Milestones" in md
        assert "| m1 |" in md

    def test_failed_expectations_section(self):
        s = ReportSummary(
            verdict="partial",
            plan_name="demo",
            failed_expectations=[
                {
                    "task_id": "t1",
                    "task_name": "t1",
                    "kind": "file_exists",
                    "reason": "file not found",
                    "details": {},
                }
            ],
        )
        md = render_summary_markdown(s)
        assert "## Failed expectations" in md
        assert "file_exists" in md

    def test_partial_batch_section(self):
        s = ReportSummary(
            verdict="partial",
            plan_name="demo",
            partial_batches=[
                {
                    "task_id": "batch1",
                    "task_name": "batch1",
                    "total": 10,
                    "ok": 7,
                    "failed": 2,
                    "skipped": 1,
                    "stopped_early": False,
                }
            ],
        )
        md = render_summary_markdown(s)
        assert "## Partial batches" in md
        assert "batch1" in md
        assert "7/10" in md

    def test_issues_section(self):
        s = ReportSummary(
            verdict="partial", plan_name="demo", issues=["Budget stopped: X"]
        )
        md = render_summary_markdown(s)
        assert "## Issues" in md
        assert "Budget stopped" in md

    def test_next_steps_section(self):
        s = ReportSummary(
            verdict="success",
            plan_name="demo",
            overall_ok=True,
            next_steps=["Continue with next TZ"],
        )
        md = render_summary_markdown(s)
        assert "## Next steps" in md
        assert "Continue with next TZ" in md


# ---------------------------------------------------------------------------
# generate_report (full pipeline)
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_end_to_end_success_no_spec(self):
        rep = _make_report([_make_step("t1")])
        md = generate_report(rep)
        assert "[OK]" in md
        assert "test-plan" in md

    def test_end_to_end_with_spec(self):
        rep = _make_report([_make_step("t1")])
        spec = _FakeSpec(goal="do stuff", domain="code")
        md = generate_report(rep, task_spec=spec)
        assert "do stuff" in md
        assert "code" in md

    def test_writes_to_disk(self, tmp_path):
        rep = _make_report([_make_step("t1")])
        out = tmp_path / "reports" / "summary.md"
        md = generate_report(rep, output_path=str(out))
        assert out.exists()
        assert out.read_text(encoding="utf-8") == md
        assert "[OK]" in md

    def test_domain_agnostic_photo_like(self):
        """Sanity: same pipeline works for a photo-batch-style report."""
        rep = _make_report(
            [
                _make_step(
                    "list_photos",
                    kind="run_command",
                    summary="Listed 100 photos",
                ),
                _make_step(
                    "upscale",
                    kind="batch_task",
                    status=STATUS_ERROR,
                    metadata={
                        "items_total": 100,
                        "items_ok": 98,
                        "items_failed": 2,
                        "items_skipped": 0,
                        "stopped_early": False,
                    },
                ),
            ],
            plan_name="photo-upscale",
        )
        spec = _FakeSpec(goal="Upscale 100 photos", domain="photo_batch")
        md = generate_report(rep, task_spec=spec)
        assert "Upscale 100 photos" in md
        assert "photo_batch" in md
        assert "98/100" in md
