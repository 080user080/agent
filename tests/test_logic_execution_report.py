"""Tests for functions.logic_execution_report (Phase 11.3)."""
from __future__ import annotations

import json

import pytest

from functions.logic_execution_report import (
    STATUS_DENIED,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    ExecutionReport,
    ReportFooter,
    StepReport,
)


def _step(
    *,
    tid: str = "t1",
    name: str = "",
    kind: str = "noop",
    status: str = STATUS_OK,
    started_at: float = 1000.0,
    finished_at: float = 1001.5,
    summary: str = "",
    error: str = "",
    cost: float = 0.0,
    prompt: int = 0,
    completion: int = 0,
) -> StepReport:
    return StepReport(
        task_id=tid,
        task_name=name,
        kind=kind,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_s=max(0.0, finished_at - started_at),
        summary=summary,
        error=error,
        cost_usd=cost,
        prompt_tokens=prompt,
        completion_tokens=completion,
    )


class TestStepReportIcon:
    def test_ok_icon(self):
        assert _step(status=STATUS_OK).icon == "[ok]"

    def test_error_icon(self):
        assert _step(status=STATUS_ERROR).icon == "[err]"

    def test_skipped_icon(self):
        assert _step(status=STATUS_SKIPPED).icon == "[skip]"

    def test_denied_icon(self):
        assert _step(status=STATUS_DENIED).icon == "[deny]"

    def test_unknown_status_icon(self):
        assert _step(status="weird").icon == "[?]"


class TestRecordAndTotals:
    def test_empty_report_totals(self):
        rep = ExecutionReport(plan_name="test", time_fn=lambda: 100.0)
        totals = rep.totals()
        assert totals["steps_total"] == 0
        assert totals["cost_usd"] == 0.0

    def test_record_accumulates(self):
        rep = ExecutionReport(plan_name="test", time_fn=lambda: 100.0)
        rep.record(_step(tid="a", cost=0.001, prompt=10, completion=5))
        rep.record(_step(tid="b", cost=0.002, prompt=20, completion=8))
        totals = rep.totals()
        assert totals["steps_total"] == 2
        assert totals["cost_usd"] == pytest.approx(0.003, rel=1e-3)
        assert totals["prompt_tokens"] == 30
        assert totals["completion_tokens"] == 13

    def test_by_status_counts(self):
        rep = ExecutionReport(plan_name="test", time_fn=lambda: 100.0)
        rep.record(_step(tid="a", status=STATUS_OK))
        rep.record(_step(tid="b", status=STATUS_ERROR))
        rep.record(_step(tid="c", status=STATUS_OK))
        counts = rep.totals()["by_status"]
        assert counts[STATUS_OK] == 2
        assert counts[STATUS_ERROR] == 1


class TestMarkdownRendering:
    def test_contains_plan_name(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        assert "demo" in rep.to_markdown()

    def test_contains_step_title(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(_step(tid="a", name="read-stuff", summary="done"))
        md = rep.to_markdown()
        assert "read-stuff" in md
        assert "done" in md

    def test_cost_and_tokens_shown(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(
            _step(tid="a", kind="call_provider", cost=0.0015, prompt=100, completion=50)
        )
        md = rep.to_markdown()
        assert "100 prompt" in md
        assert "$0.0015" in md

    def test_error_shown(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(_step(tid="a", status=STATUS_ERROR, error="boom"))
        md = rep.to_markdown()
        assert "boom" in md

    def test_events_section(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.add_event("hello world")
        md = rep.to_markdown()
        assert "hello world" in md

    def test_footer_budget(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.set_footer(
            ReportFooter(budget_snapshot={"steps": 10, "duration_s": 120})
        )
        md = rep.to_markdown()
        assert "Budget snapshot" in md
        assert "steps: 10" in md


class TestJsonRendering:
    def test_valid_json(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(_step(tid="a"))
        payload = json.loads(rep.to_json())
        assert payload["plan_name"] == "demo"
        assert len(payload["steps"]) == 1

    def test_json_totals_present(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(_step(cost=0.5))
        payload = json.loads(rep.to_json())
        assert payload["totals"]["cost_usd"] == 0.5


class TestTextRendering:
    def test_text_includes_step(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(_step(tid="a", name="hello", summary="world"))
        text = rep.to_text()
        assert "hello" in text
        assert "world" in text

    def test_text_summary_footer(self):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(_step())
        text = rep.to_text()
        assert "done" in text


class TestSaveAndAutosave:
    def test_save_markdown(self, tmp_path):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(_step(summary="ok"))
        target = tmp_path / "out.md"
        rep.save(str(target), fmt="markdown")
        assert "demo" in target.read_text(encoding="utf-8")

    def test_save_json(self, tmp_path):
        rep = ExecutionReport(plan_name="demo", time_fn=lambda: 100.0)
        rep.record(_step())
        target = tmp_path / "out.json"
        rep.save(str(target), fmt="json")
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["plan_name"] == "demo"

    def test_save_requires_path_or_autosave(self):
        rep = ExecutionReport(plan_name="demo")
        with pytest.raises(ValueError):
            rep.save()

    def test_autosave_writes_after_each_record(self, tmp_path):
        target = tmp_path / "auto.md"
        rep = ExecutionReport(
            plan_name="demo", autosave_path=str(target), time_fn=lambda: 100.0
        )
        rep.record(_step(tid="a", summary="alpha"))
        assert "alpha" in target.read_text(encoding="utf-8")
        rep.record(_step(tid="b", summary="beta"))
        content = target.read_text(encoding="utf-8")
        assert "alpha" in content and "beta" in content

    def test_unknown_format_raises(self, tmp_path):
        rep = ExecutionReport(plan_name="demo")
        with pytest.raises(ValueError):
            rep.save(str(tmp_path / "out"), fmt="xml")
