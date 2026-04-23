"""Universal post-execution report generator (Phase 13 S10 / spec 13.10).

Бере `ExecutionReport` (колектор `StepReport`-ів від `TaskRunner`-а) і
опційно `TaskSpec` (з `core_task_intake`), генерує **domain-agnostic**
markdown-звіт, орієнтований на ціль (goal-driven), а не на низькорівневі
кроки. На відміну від `ExecutionReport.to_markdown`, цей звіт:

- Починається з **goal** (з `TaskSpec`) та загального вердикту (✓/✗).
- Групує кроки в **milestones** (за `metadata.milestone` якщо є, інакше —
  всі як один milestone).
- Виносить окрему секцію з **failed expectations** (із Step-Check
  `expect_results` у `metadata`).
- Підсумовує час / вартість / токени / партіальні-батчі.
- Пропонує **next steps** (евристичні підказки, не LLM).
- Не знає про конкретний домен — працює однаково для коду, фото, ppt,
  web-research, mixed.

Призначення — давати користувачу зрозумілу картину «агент зробив те, що
обіцяв?» після довгих автономних сесій.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

from .logic_execution_report import (
    STATUS_DENIED,
    STATUS_ERROR,
    STATUS_EXPECT_FAILED,
    STATUS_OK,
    STATUS_PRECHECK_FAILED,
    STATUS_SKIPPED,
    STATUS_TIMEOUT,
    ExecutionReport,
    StepReport,
)

if TYPE_CHECKING:  # pragma: no cover — lazy circular guard
    from .core_task_intake import TaskSpec


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ReportSummary:
    """Машино-читабельна короткозведення, з якого рендериться markdown."""

    plan_name: str = ""
    goal: str = ""
    domain: str = ""
    duration_s: float = 0.0
    overall_ok: bool = True
    verdict: str = ""  # "success" | "partial" | "failed"
    steps_total: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    failed_steps: List[str] = field(default_factory=list)
    failed_expectations: List[Dict[str, Any]] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    partial_batches: List[Dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    issues: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FAIL_STATUSES = {
    STATUS_ERROR,
    STATUS_DENIED,
    STATUS_TIMEOUT,
    STATUS_PRECHECK_FAILED,
    STATUS_EXPECT_FAILED,
}


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {sec}s"


def _milestone_of(step: StepReport) -> str:
    raw = step.metadata.get("milestone") if step.metadata else None
    if raw:
        return str(raw)
    return "default"


def _extract_failed_expectations(steps: Iterable[StepReport]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in steps:
        meta = s.metadata or {}
        raw = meta.get("expect_results")
        if not isinstance(raw, list):
            continue
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            if entry.get("ok"):
                continue
            out.append(
                {
                    "task_id": s.task_id,
                    "task_name": s.task_name or s.task_id,
                    "kind": entry.get("kind", "?"),
                    "reason": entry.get("reason", ""),
                    "details": entry.get("details", {}),
                }
            )
    return out


def _extract_partial_batches(steps: Iterable[StepReport]) -> List[Dict[str, Any]]:
    """Збирає batch_task кроки, які мали часткові збої чи skip-и."""
    out: List[Dict[str, Any]] = []
    for s in steps:
        if s.kind != "batch_task":
            continue
        meta = s.metadata or {}
        total = int(meta.get("items_total", 0))
        ok = int(meta.get("items_ok", 0))
        failed = int(meta.get("items_failed", 0))
        skipped = int(meta.get("items_skipped", 0))
        stopped_early = bool(meta.get("stopped_early", False))
        if total == 0 and not stopped_early:
            continue
        if failed == 0 and skipped == 0 and not stopped_early:
            continue
        out.append(
            {
                "task_id": s.task_id,
                "task_name": s.task_name or s.task_id,
                "total": total,
                "ok": ok,
                "failed": failed,
                "skipped": skipped,
                "stopped_early": stopped_early,
            }
        )
    return out


def _derive_next_steps(summary: ReportSummary) -> List[str]:
    hints: List[str] = []
    if not summary.overall_ok and summary.failed_steps:
        head = summary.failed_steps[0]
        hints.append(
            f"Проаналізувати помилку у `{head}` та перезапустити тільки цей крок."
        )
    if summary.failed_expectations:
        # Show up to 2 distinct kinds of expectation failures as hints.
        seen = set()
        for exp in summary.failed_expectations:
            kind = exp.get("kind", "?")
            if kind in seen:
                continue
            seen.add(kind)
            hints.append(
                f"Виправити причину порушення очікування `{kind}`: {exp.get('reason') or 'див. деталі'}"
            )
            if len(seen) >= 2:
                break
    for batch in summary.partial_batches:
        if batch["failed"] or batch["stopped_early"]:
            hints.append(
                f"Перезапустити batch `{batch['task_id']}` для {batch['failed']} провалених "
                f"та {batch['skipped']} пропущених елементів."
            )
    if summary.issues:
        hints.append("Переглянути issues нижче перед наступним запуском.")
    if not hints and summary.overall_ok:
        hints.append("Всі цілі досягнуто — можна переходити до наступного ТЗ.")
    return hints


def _collect_issues(report: ExecutionReport, steps: Iterable[StepReport]) -> List[str]:
    issues: List[str] = []
    footer = report.footer
    budget = footer.budget_snapshot or {}
    if budget.get("stopped_reason"):
        issues.append(f"Budget stopped: {budget['stopped_reason']}")
    for s in steps:
        if s.status == STATUS_DENIED:
            issues.append(f"Denied: {s.task_id} ({s.summary or s.error or '—'})")
        elif s.status == STATUS_TIMEOUT:
            issues.append(f"Timeout: {s.task_id} ({s.summary or s.error or '—'})")
    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_report_summary(
    report: ExecutionReport,
    *,
    task_spec: "Optional[TaskSpec]" = None,
) -> ReportSummary:
    """Складає `ReportSummary` з `ExecutionReport` (+ опційний `TaskSpec`)."""
    totals = report.totals()
    with report._lock:  # noqa: SLF001 — consistent snapshot
        steps = list(report.steps)

    failed_steps = [s.task_id for s in steps if s.status in _FAIL_STATUSES]
    failed_expectations = _extract_failed_expectations(steps)
    partial_batches = _extract_partial_batches(steps)

    overall_ok = (
        not failed_steps
        and not failed_expectations
        and not any(b["failed"] or b["stopped_early"] for b in partial_batches)
    )
    if overall_ok:
        verdict = "success"
    elif totals["by_status"].get(STATUS_OK, 0) > 0:
        verdict = "partial"
    else:
        verdict = "failed"

    summary = ReportSummary(
        plan_name=report.plan_name,
        goal=(task_spec.goal if task_spec else ""),
        domain=(task_spec.domain if task_spec else ""),
        duration_s=float(totals.get("duration_s", 0.0)),
        overall_ok=overall_ok,
        verdict=verdict,
        steps_total=int(totals.get("steps_total", 0)),
        by_status=dict(totals.get("by_status", {})),
        failed_steps=failed_steps,
        failed_expectations=failed_expectations,
        partial_batches=partial_batches,
        cost_usd=float(totals.get("cost_usd", 0.0)),
        prompt_tokens=int(totals.get("prompt_tokens", 0)),
        completion_tokens=int(totals.get("completion_tokens", 0)),
    )

    # Group steps into milestones (stable insertion order).
    groups: Dict[str, List[StepReport]] = {}
    order: List[str] = []
    for s in steps:
        key = _milestone_of(s)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(s)
    milestones: List[Dict[str, Any]] = []
    for key in order:
        group = groups[key]
        duration = sum(x.duration_s for x in group)
        ok_n = sum(1 for x in group if x.status == STATUS_OK)
        fail_n = sum(1 for x in group if x.status in _FAIL_STATUSES)
        skip_n = sum(1 for x in group if x.status == STATUS_SKIPPED)
        milestones.append(
            {
                "name": key,
                "steps": len(group),
                "ok": ok_n,
                "failed": fail_n,
                "skipped": skip_n,
                "duration_s": duration,
                "status": STATUS_OK if fail_n == 0 else STATUS_ERROR,
            }
        )
    summary.milestones = milestones

    summary.issues = _collect_issues(report, steps)
    summary.next_steps = _derive_next_steps(summary)
    return summary


def render_summary_markdown(summary: ReportSummary) -> str:
    """Рендерить `ReportSummary` як концентрований markdown-звіт."""
    lines: List[str] = []
    mark = {"success": "[OK]", "partial": "[PARTIAL]", "failed": "[FAIL]"}.get(
        summary.verdict, "[?]"
    )
    title = summary.plan_name or "(unnamed plan)"
    lines.append(f"# {mark} Task Report — {title}")
    if summary.goal:
        lines.append("")
        lines.append(f"**Goal:** {summary.goal}")
    meta_bits: List[str] = []
    if summary.domain:
        meta_bits.append(f"domain=`{summary.domain}`")
    meta_bits.append(f"verdict=`{summary.verdict}`")
    meta_bits.append(f"duration={_format_duration(summary.duration_s)}")
    meta_bits.append(f"steps={summary.steps_total}")
    if summary.cost_usd:
        meta_bits.append(f"cost=${summary.cost_usd:.4f}")
    if summary.prompt_tokens or summary.completion_tokens:
        meta_bits.append(
            f"tokens={summary.prompt_tokens}p/{summary.completion_tokens}c"
        )
    lines.append("")
    lines.append(" | ".join(meta_bits))
    lines.append("")

    # Milestones table
    if summary.milestones:
        lines.append("## Milestones")
        lines.append("")
        lines.append("| Milestone | Steps | OK | Failed | Skipped | Duration |")
        lines.append("|---|---|---|---|---|---|")
        for m in summary.milestones:
            lines.append(
                f"| {m['name']} | {m['steps']} | {m['ok']} | {m['failed']} | "
                f"{m['skipped']} | {_format_duration(m['duration_s'])} |"
            )
        lines.append("")

    # Status breakdown
    if summary.by_status:
        lines.append("## Status breakdown")
        for status, cnt in sorted(summary.by_status.items()):
            lines.append(f"- `{status}`: {cnt}")
        lines.append("")

    # Failed steps
    if summary.failed_steps:
        lines.append("## Failed steps")
        for tid in summary.failed_steps:
            lines.append(f"- `{tid}`")
        lines.append("")

    # Failed expectations
    if summary.failed_expectations:
        lines.append("## Failed expectations")
        for exp in summary.failed_expectations:
            reason = exp.get("reason") or "(no reason)"
            lines.append(
                f"- `{exp['task_id']}` — `{exp['kind']}`: {reason}"
            )
        lines.append("")

    # Partial batches
    if summary.partial_batches:
        lines.append("## Partial batches")
        for b in summary.partial_batches:
            note = " (stopped early)" if b["stopped_early"] else ""
            lines.append(
                f"- `{b['task_id']}`: {b['ok']}/{b['total']} ok, "
                f"failed={b['failed']}, skipped={b['skipped']}{note}"
            )
        lines.append("")

    # Issues
    if summary.issues:
        lines.append("## Issues")
        for i in summary.issues:
            lines.append(f"- {i}")
        lines.append("")

    # Next steps
    if summary.next_steps:
        lines.append("## Next steps")
        for n in summary.next_steps:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_report(
    report: ExecutionReport,
    *,
    task_spec: "Optional[TaskSpec]" = None,
    output_path: Optional[str] = None,
) -> str:
    """Повний цикл: `ExecutionReport` (+ `TaskSpec`) → markdown string.

    Якщо передано `output_path` — додатково записує markdown на диск.
    """
    summary = build_report_summary(report, task_spec=task_spec)
    md = render_summary_markdown(summary)
    if output_path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(md, encoding="utf-8")
    return md


__all__ = [
    "ReportSummary",
    "build_report_summary",
    "render_summary_markdown",
    "generate_report",
]
