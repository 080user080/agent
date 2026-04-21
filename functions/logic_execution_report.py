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
from typing import Any, Dict, List, Optional

STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"
STATUS_DENIED = "denied"
STATUS_TIMEOUT = "timeout"


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
