"""ExecutionReport — структурований звіт виконання плану (Phase 11.3).

Збирає `StepReport`-и від TaskRunner-а та рендерить тезисний markdown /
json / plain-text формат з таймінгами, токенами, вартістю.

Дизайн:
- Без залежностей на решту модулів — чистий колектор.
- Stable-безпечний (можна дзвонити `record` паралельно, поки TaskRunner
  ітерується).
- Автосейв (`autosave_path`) — після кожного `record` дописує на диск,
  щоб при падінні плану звіт не губився.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"
STATUS_DENIED = "denied"
STATUS_TIMEOUT = "timeout"
STATUS_PRECHECK_FAILED = "precheck_failed"
STATUS_EXPECT_FAILED = "expect_failed"


@dataclass
class StepReport:
    """Звіт одного кроку TaskRunner-а."""

    task_id: str
    task_name: str = ""
    kind: str = ""
    status: str = STATUS_OK
    started_at: float = 0.0  # unix epoch
    finished_at: float = 0.0  # unix epoch
    duration_s: float = 0.0
    summary: str = ""
    stdout_tail: str = ""
    error: str = ""
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def icon(self) -> str:
        return {
            STATUS_OK: "[ok]",
            STATUS_SKIPPED: "[skip]",
            STATUS_ERROR: "[err]",
            STATUS_DENIED: "[deny]",
            STATUS_TIMEOUT: "[timeout]",
        }.get(self.status, "[?]")


@dataclass
class ExecutionReportEvent:
    """Вільний event-рядок у звіті (не привʼязаний до кроку)."""

    at: float
    message: str


@dataclass
class ReportFooter:
    """Підсумкова метадата, яку TaskRunner може додати у кінці звіту."""

    budget_snapshot: Dict[str, Any] = field(default_factory=dict)
    provider_descriptions: List[Dict[str, Any]] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)


class ExecutionReport:
    """Колектор `StepReport` + довільні event-и + footer."""

    def __init__(
        self,
        *,
        plan_name: str = "",
        autosave_path: Optional[str] = None,
        time_fn=time.time,
    ):
        self.plan_name = plan_name
        self.steps: List[StepReport] = []
        self.events: List[ExecutionReportEvent] = []
        self.footer: ReportFooter = ReportFooter()
        self.started_at: float = time_fn()
        self.finished_at: Optional[float] = None
        self.autosave_path = Path(autosave_path) if autosave_path else None
        self._time = time_fn
        self._lock = threading.Lock()

    # ----- Recording -----

    def record(self, step: StepReport) -> None:
        with self._lock:
            self.steps.append(step)
        self._autosave()

    def add_event(self, message: str) -> None:
        with self._lock:
            self.events.append(
                ExecutionReportEvent(at=self._time(), message=message)
            )
        self._autosave()

    def mark_finished(self) -> None:
        with self._lock:
            self.finished_at = self._time()
        self._autosave()

    def set_footer(self, footer: ReportFooter) -> None:
        with self._lock:
            self.footer = footer
        self._autosave()

    # ----- Totals -----

    def totals(self) -> Dict[str, Any]:
        with self._lock:
            steps = list(self.steps)
        counts: Dict[str, int] = {}
        total_cost = 0.0
        total_prompt = 0
        total_completion = 0
        total_duration = 0.0
        for s in steps:
            counts[s.status] = counts.get(s.status, 0) + 1
            total_cost += s.cost_usd
            total_prompt += s.prompt_tokens
            total_completion += s.completion_tokens
            total_duration += s.duration_s
        return {
            "steps_total": len(steps),
            "by_status": counts,
            "cost_usd": round(total_cost, 6),
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "duration_s": round(total_duration, 3),
        }

    # ----- Renderers -----

    def to_markdown(self) -> str:
        lines: List[str] = []
        started_str = _format_ts(self.started_at)
        finished_str = (
            _format_ts(self.finished_at) if self.finished_at else "(триває)"
        )
        wall = (self.finished_at or self._time()) - self.started_at
        lines.append(f"# Звіт виконання: {self.plan_name or '(без назви)'}")
        lines.append(
            f"Початок: {started_str} | Кінець: {finished_str} | "
            f"Тривалість: {_format_duration(wall)}"
        )
        lines.append("")

        with self._lock:
            steps = list(self.steps)
            events = list(self.events)
            footer = self.footer

        for idx, s in enumerate(steps, start=1):
            title = s.task_name or s.task_id or "(без назви)"
            header = f"## {idx}. {title} ({s.kind}) {s.icon}"
            lines.append(header)
            t1 = _format_ts(s.started_at) if s.started_at else "—"
            t2 = _format_ts(s.finished_at) if s.finished_at else "—"
            lines.append(
                f"- Час: {t1} → {t2} ({_format_duration(s.duration_s)})"
            )
            if s.prompt_tokens or s.completion_tokens or s.cost_usd:
                lines.append(
                    f"- Tokens: {s.prompt_tokens} prompt / "
                    f"{s.completion_tokens} completion | "
                    f"Cost: ${s.cost_usd:.4f}"
                )
            if s.summary:
                lines.append(f"- Summary: {s.summary}")
            if s.stdout_tail:
                tail = s.stdout_tail.strip().splitlines()
                if len(tail) > 3:
                    tail = tail[-3:]
                for ln in tail:
                    lines.append(f"  - `{ln}`")
            if s.error:
                lines.append(f"- Error: `{s.error}`")
            lines.append("")

        if events:
            lines.append("## Події")
            for ev in events:
                lines.append(f"- {_format_ts(ev.at)} — {ev.message}")
            lines.append("")

        totals = self.totals()
        lines.append("## Підсумок")
        lines.append(f"- Кроків: {totals['steps_total']}")
        for status, cnt in sorted(totals["by_status"].items()):
            lines.append(f"  - {status}: {cnt}")
        lines.append(f"- Загальна вартість: ${totals['cost_usd']:.4f}")
        lines.append(
            f"- Токени: {totals['prompt_tokens']} prompt / "
            f"{totals['completion_tokens']} completion"
        )

        if footer.budget_snapshot:
            lines.append("")
            lines.append("### Budget snapshot")
            for k, v in footer.budget_snapshot.items():
                lines.append(f"- {k}: {v}")
        if footer.provider_descriptions:
            lines.append("")
            lines.append("### Providers")
            for p in footer.provider_descriptions:
                lines.append(
                    f"- {p.get('name', '?')} (available={p.get('available', '?')})"
                )
        return "\n".join(lines).rstrip() + "\n"

    def to_json(self) -> str:
        with self._lock:
            steps = [asdict(s) for s in self.steps]
            events = [asdict(e) for e in self.events]
            footer = asdict(self.footer)
        payload = {
            "plan_name": self.plan_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "steps": steps,
            "events": events,
            "footer": footer,
            "totals": self.totals(),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def to_text(self) -> str:
        """Компактний тезисний вигляд для console / stdout."""
        lines: List[str] = []
        lines.append(f"Plan: {self.plan_name or '(unnamed)'}")
        with self._lock:
            steps = list(self.steps)
        for idx, s in enumerate(steps, start=1):
            t = _format_duration(s.duration_s)
            lines.append(f"{idx:2d}. {s.icon} {s.task_name or s.task_id} [{t}]")
            if s.summary:
                lines.append(f"    -> {s.summary}")
            if s.error:
                lines.append(f"    !! {s.error}")
        totals = self.totals()
        lines.append(
            f"-- done: {totals['steps_total']} step(s), "
            f"${totals['cost_usd']:.4f}, "
            f"{_format_duration(totals['duration_s'])}"
        )
        return "\n".join(lines) + "\n"

    # ----- Persistence -----

    def save(self, path: Optional[str] = None, *, fmt: str = "markdown") -> Path:
        """Записати звіт у файл. fmt: markdown | json | text."""
        target = Path(path) if path else self.autosave_path
        if target is None:
            raise ValueError("no path provided and autosave_path is not set")
        target.parent.mkdir(parents=True, exist_ok=True)
        body = self._render(fmt)
        target.write_text(body, encoding="utf-8")
        return target

    def _autosave(self) -> None:
        if self.autosave_path is None:
            return
        try:
            self.save(fmt="markdown")
        except Exception:  # noqa: BLE001
            # autosave не має падати основний потік
            pass

    def _render(self, fmt: str) -> str:
        if fmt == "markdown":
            return self.to_markdown()
        if fmt == "json":
            return self.to_json()
        if fmt == "text":
            return self.to_text()
        raise ValueError(f"unknown report format: {fmt!r}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_ts(value: float) -> str:
    if not value:
        return "—"
    dt = datetime.fromtimestamp(value, tz=timezone.utc).astimezone()
    return dt.strftime("%H:%M:%S")


def _format_duration(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


# ===========================================================================
# Universal post-execution report generator (об'єднано з logic_report_generator)
# ===========================================================================
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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

from functions.planning.core_task_intake import TaskSpec


_FAIL_STATUSES = {
    STATUS_ERROR,
    STATUS_DENIED,
    STATUS_TIMEOUT,
    STATUS_PRECHECK_FAILED,
    STATUS_EXPECT_FAILED,
}


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


def _derive_next_steps(summary: "ReportSummary") -> List[str]:
    hints: List[str] = []
    if not summary.overall_ok and summary.failed_steps:
        head = summary.failed_steps[0]
        hints.append(
            f"Проаналізувати помилку у `{head}` та перезапустити тільки цей крок."
        )
    if summary.failed_expectations:
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
    "StepReport", "ExecutionReportEvent", "ReportFooter",
    "ExecutionReport",
    "STATUS_OK", "STATUS_SKIPPED", "STATUS_ERROR",
    "STATUS_DENIED", "STATUS_TIMEOUT",
    "STATUS_PRECHECK_FAILED", "STATUS_EXPECT_FAILED",
    # From logic_report_generator
    "ReportSummary",
    "build_report_summary",
    "render_summary_markdown",
    "generate_report",
]