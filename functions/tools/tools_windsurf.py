"""Windsurf-адаптер: тонкий шар поверх Window/OCR-тулів.

Phase 12.5 / V-трек (пробіли до «як людина»).

Чисто data-layer:
- знайти вікно Windsurf (за title / process_name);
- зняти snapshot тексту чату (OCR або custom reader);
- нормалізувати текст і порахувати хеш;
- зрозуміти чи з'явилась нова відповідь (diff-і з попереднім snapshot-ом).

**Без прямої залежності** на Windows-API: усі «важкі» операції інжектуються
через параметри (`window_finder`, `snapshot_fn`) — тому тести бігають на
Linux CI, а реальний код використовує дефолтні адаптери поверх
`tools_window_manager` + `tools_ocr`.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


WindsurfWindow = Dict[str, Any]
"""Dict опис вікна: `{hwnd, title, process_name, pid, rect}`."""

WindowFinder = Callable[[], Optional[WindsurfWindow]]
"""Сигнатура функції, яка знаходить Windsurf-вікно або `None`."""

SnapshotFn = Callable[[WindsurfWindow], str]
"""Сигнатура функції, яка знімає поточний текст чату."""


# Характерні паттерни заголовка Windsurf (desktop / web-Electron).
# Match-имо case-insensitive.
DEFAULT_TITLE_PATTERNS: List[str] = [
    "windsurf",
    "codeium",  # IDE-тема
]

DEFAULT_PROCESS_NAMES: List[str] = [
    "windsurf",
    "windsurf.exe",
]


# ---------------------------------------------------------------------------
# Default adapters (lazy imports — Linux CI не зламається)
# ---------------------------------------------------------------------------


def _default_list_windows() -> List[Dict[str, Any]]:
    """Спроба скористатись `tools_window_manager.WindowManager.list_windows()`.

    На Linux / без pywin32 — повертає `[]`. Це тригерить `find_windsurf_window`
    повернути `None` — коректно без raise.
    """
    try:
        from .tools_window_manager import WindowManager  # type: ignore[import]
    except Exception:  # noqa: BLE001
        return []
    try:
        wm = WindowManager()
        return wm.list_windows()
    except Exception:  # noqa: BLE001
        return []


def _default_ocr_window(hwnd: int) -> Dict[str, Any]:
    """Спроба скористатись `tools_ocr.ocr_window`."""
    try:
        from .tools_ocr import ocr_window  # type: ignore[import]
    except Exception:  # noqa: BLE001
        return {"text": "", "ok": False}
    try:
        return ocr_window(hwnd)
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Find Windsurf window
# ---------------------------------------------------------------------------


def make_default_window_finder(
    *,
    title_patterns: Optional[List[str]] = None,
    process_names: Optional[List[str]] = None,
    window_lister: Optional[Callable[[], List[Dict[str, Any]]]] = None,
) -> WindowFinder:
    """Фабрика `WindowFinder`-а на основі list-of-windows.

    Патерни й процеси — case-insensitive substring.
    """
    titles = [t.lower() for t in (title_patterns or DEFAULT_TITLE_PATTERNS)]
    procs = [p.lower() for p in (process_names or DEFAULT_PROCESS_NAMES)]
    lister = window_lister or _default_list_windows

    def _find() -> Optional[WindsurfWindow]:
        try:
            windows = lister() or []
        except Exception:  # noqa: BLE001
            return None
        for w in windows:
            title = (w.get("title") or "").lower()
            proc = (w.get("process_name") or "").lower()
            if not title and not proc:
                continue
            if any(p and p in proc for p in procs):
                return dict(w)
            if any(t and t in title for t in titles):
                return dict(w)
        return None

    return _find


def find_windsurf_window(
    *,
    title_patterns: Optional[List[str]] = None,
    process_names: Optional[List[str]] = None,
    window_lister: Optional[Callable[[], List[Dict[str, Any]]]] = None,
) -> Optional[WindsurfWindow]:
    """Одноразовий пошук Windsurf-вікна. Зручна обгортка над
    `make_default_window_finder()`."""
    return make_default_window_finder(
        title_patterns=title_patterns,
        process_names=process_names,
        window_lister=window_lister,
    )()


# ---------------------------------------------------------------------------
# Snapshot / normalization
# ---------------------------------------------------------------------------


_WHITESPACE_RE = re.compile(r"\s+")
_CURSOR_MARKERS_RE = re.compile(r"[▌▎▍▋█]")  # blinking-cursor символи, що ловить OCR


def normalize_text(text: str) -> str:
    """Прибирає blinking-cursor знаки й зводить whitespace до одного пробілу.

    Це ключове для `condition_chat_idle`: OCR на кожному кадрі ловить
    моргаючий каретка-символ як різний → idle ніколи не настає. Нормалізація
    робить два сусідні кадри однаковими, поки реальний текст не змінився.
    """
    if not text:
        return ""
    cleaned = _CURSOR_MARKERS_RE.sub("", text)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def compute_text_hash(text: str) -> str:
    """SHA-256 хеш нормалізованого тексту — стабільний snapshot-id."""
    norm = normalize_text(text)
    return hashlib.sha256(norm.encode("utf-8", errors="ignore")).hexdigest()


def make_default_snapshot_fn(
    ocr_window_fn: Optional[Callable[[int], Dict[str, Any]]] = None,
) -> SnapshotFn:
    """Фабрика SnapshotFn поверх `tools_ocr.ocr_window`.

    На помилках OCR повертає порожній рядок — condition_chat_idle
    спрацює по стабільності (порожній == порожній).
    """
    ocr = ocr_window_fn or _default_ocr_window

    def _snap(window: WindsurfWindow) -> str:
        hwnd = window.get("hwnd")
        if not isinstance(hwnd, int):
            return ""
        result = ocr(hwnd) or {}
        text = result.get("text") or ""
        return normalize_text(str(text))

    return _snap


# ---------------------------------------------------------------------------
# Response diff / dedup
# ---------------------------------------------------------------------------


@dataclass
class ResponseDiff:
    """Різниця між попереднім і поточним snapshot-ом чату."""

    previous_hash: str
    current_hash: str
    changed: bool
    new_text: str = ""
    """Tail, що з'явився після попереднього snapshot-у (best-effort).

    Якщо поточний snapshot починається з попереднього — `new_text` = різниця.
    Якщо структура змінилась (scroll / resize / видалення історії) —
    `new_text` дорівнює поточному цілому snapshot-у.
    """


def diff_snapshots(previous: str, current: str) -> ResponseDiff:
    """Порахувати diff двох snapshot-ів чату.

    Повертає `ResponseDiff` з `new_text`, що є найкращою апроксимацією
    свіжо-згенерованої відповіді для логу.
    """
    prev_norm = normalize_text(previous)
    curr_norm = normalize_text(current)
    prev_hash = compute_text_hash(prev_norm)
    curr_hash = compute_text_hash(curr_norm)
    if prev_hash == curr_hash:
        return ResponseDiff(prev_hash, curr_hash, changed=False, new_text="")

    new_tail: str
    if prev_norm and curr_norm.startswith(prev_norm):
        new_tail = curr_norm[len(prev_norm):].strip()
    else:
        new_tail = curr_norm
    return ResponseDiff(prev_hash, curr_hash, changed=True, new_text=new_tail)


# ---------------------------------------------------------------------------
# Context accumulator
# ---------------------------------------------------------------------------


@dataclass
class WindsurfState:
    """Статистика live-сесії Watcher-а для Windsurf.

    Мутабельний контейнер; Watcher-context тримає одну таку структуру як
    `ctx["windsurf"]`. Кожен дозволений на запис тільки з action-handler-а
    (single-threaded всередині Watcher-а).
    """

    responses_captured: int = 0
    last_response_hash: str = ""
    last_snapshot: str = ""
    window_lost_count: int = 0
    snapshots_taken: int = 0
    responses: List[Dict[str, Any]] = field(default_factory=list)
    """Список {at, hash, text, length} — кільцевий буфер (див. WATCHER_MAX_RESPONSES)."""

    def register_response(
        self, *, at: float, diff: ResponseDiff, max_keep: int = 64
    ) -> Dict[str, Any]:
        """Додати нову відповідь у буфер і оновити лічильники."""
        entry: Dict[str, Any] = {
            "at": at,
            "hash": diff.current_hash,
            "text": diff.new_text,
            "length": len(diff.new_text),
        }
        self.responses.append(entry)
        if len(self.responses) > max_keep:
            # Trim з початку, щоб не розростатись у RAM на довгих сесіях.
            self.responses = self.responses[-max_keep:]
        self.responses_captured += 1
        self.last_response_hash = diff.current_hash
        return entry


__all__ = [
    "DEFAULT_PROCESS_NAMES",
    "DEFAULT_TITLE_PATTERNS",
    "ResponseDiff",
    "SnapshotFn",
    "WindowFinder",
    "WindsurfState",
    "WindsurfWindow",
    "compute_text_hash",
    "diff_snapshots",
    "find_windsurf_window",
    "make_default_snapshot_fn",
    "make_default_window_finder",
    "normalize_text",
]
