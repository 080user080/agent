"""Windows Windsurf IDE — window finder, OCR snapshot, state.

Phase 12.5 інфраструктура для Windsurf Watcher.
Модуль знаходить вікно IDE, робить OCR-знімок тексту,
відстежує стан (snapshots, responses, window lost).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Типи
# ---------------------------------------------------------------------------

SnapshotFn = Callable[[Dict[str, Any]], str]
"""Приймає window dict, повертає OCR-текст."""

WindowFinder = Callable[[], Optional[Dict[str, Any]]]
"""Повертає window dict або None, якщо вікно не знайдено."""


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


@dataclass
class SnapshotDiff:
    """Результат diff-у двох snapshot-ів."""

    changed: bool = False
    new_text: str = ""


def diff_snapshots(old: str, new: str) -> SnapshotDiff:
    """Порівнює два snapshot-и тексту.

    Якщо текст змінився — повертає SnapshotDiff(changed=True, new_text=new).
    Якщо не змінився — SnapshotDiff(changed=False, new_text="").
    """
    if old == new:
        return SnapshotDiff(changed=False, new_text="")
    # Визначаємо новий текст (tail)
    if new.startswith(old):
        tail = new[len(old):]
    else:
        tail = new
    return SnapshotDiff(changed=True, new_text=tail or new)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class WindsurfState:
    """Стан спостереження за Windsurf."""

    snapshots_taken: int = 0
    window_lost_count: int = 0
    last_snapshot: str = ""
    responses_captured: int = 0
    responses: List[Dict[str, Any]] = field(default_factory=list)

    def register_response(
        self,
        at: float,
        diff: SnapshotDiff,
        max_keep: int,
    ) -> Dict[str, Any]:
        """Реєструє нову відповідь, обрізає історію до max_keep."""
        entry: Dict[str, Any] = {
            "text": diff.new_text,
            "timestamp": at,
        }
        self.responses.append(entry)
        self.responses_captured += 1
        if len(self.responses) > max_keep:
            self.responses = self.responses[-max_keep:]
        return entry


# ---------------------------------------------------------------------------
# Window helpers
# ---------------------------------------------------------------------------


@dataclass
class WindsurfWindow:
    """Опис вікна Windsurf IDE."""

    hwnd: int = 0
    title: str = ""
    process_name: str = ""
    rect: Dict[str, int] = field(default_factory=lambda: {
        "x": 0, "y": 0, "width": 800, "height": 600,
    })

    def find(self) -> Optional[Dict[str, Any]]:
        """Намагається знайти вікно Windsurf.

        Повертає window dict або None. Базова імплементація —
        заглушка (шукає вікно за заголовком через win32gui).
        """
        try:
            import win32gui  # noqa: PLC0415
            hwnd = win32gui.FindWindow(None, self.title) if self.title else 0
            if hwnd:
                return self._as_dict(hwnd=hwnd)
            # Fallback: пошук по partial title
            def enum_cb(h: int, _: Any) -> None:
                nonlocal hwnd
                if win32gui.IsWindowVisible(h) and "windsurf" in win32gui.GetWindowText(h).lower():
                    hwnd = h
            win32gui.EnumWindows(enum_cb, None)
            if hwnd:
                return self._as_dict(hwnd=hwnd)
            return None
        except ImportError:
            return None

    def _as_dict(self, hwnd: int) -> Dict[str, Any]:
        return {
            "hwnd": hwnd,
            "title": self.title or "Windsurf",
            "process_name": self.process_name or "windsurf.exe",
            "rect": dict(self.rect),
        }


# ---------------------------------------------------------------------------
# Default factories
# ---------------------------------------------------------------------------


def make_default_window_finder() -> WindowFinder:
    """Створює WindowFinder за замовчуванням."""
    w = WindsurfWindow(title="Windsurf")
    return w.find


def make_default_snapshot_fn() -> SnapshotFn:
    """Створює SnapshotFn за замовчуванням (OCR через win32gui + Tesseract)."""
    def _snapshot(window: Dict[str, Any]) -> str:
        """Робить OCR-знімок вікна.

        Заглушка — реально не виконує OCR.
        Для повноцінної роботи потрібен Tesseract.
        """
        return ""
    return _snapshot


__all__ = [
    "SnapshotDiff",
    "SnapshotFn",
    "WindowFinder",
    "WindsurfState",
    "WindsurfWindow",
    "diff_snapshots",
    "make_default_snapshot_fn",
    "make_default_window_finder",
]