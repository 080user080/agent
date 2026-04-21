"""Windows-специфічні condition-фабрики для Watcher (I3).

Phase 8 / I3. Розширення `logic_watcher.py` — умови, що спираються на
стан Windows-середовища: заголовки вікон, процеси, «тиша» в чаті.

Дизайн:
- Всі фабрики приймають **injection points** (lister/reader-функції), щоб
  юніт-тести повністю мокалися на Linux CI, а реальний код користувався
  за замовчуванням `pygetwindow` / `psutil`.
- Жодного Windows-специфічного raise в коді фабрик — якщо бібліотеки
  недоступні (або жодного вікна не знайдено), фабрика повертає
  condition-функцію, яка видає `False`.
- `condition_chat_idle` - generic: не «знає» про конкретний провайдер,
  а очікує `activity_fn() -> str | None`. Викликач сам вирішує, як
  визначати активність (polling-сніпшот чату, timestamp файлу, хеш UI-тексту).
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Union

from .logic_watcher import ConditionFn


# ---------------------------------------------------------------------------
# Default backends (lazy import)
# ---------------------------------------------------------------------------


def _default_window_lister() -> List[str]:
    """Повертає список видимих заголовків вікон через pygetwindow.

    На Linux/без pygetwindow повертає `[]`, щоб condition видавала False
    замість raise.
    """
    try:
        import pygetwindow as gw  # type: ignore[import]
    except ImportError:
        return []
    try:
        titles = [w.title for w in gw.getAllWindows() if w.title]
        return titles
    except Exception:  # noqa: BLE001
        return []


def _default_process_lister() -> List[Dict[str, Any]]:
    """Повертає список словників `{pid, name}` через psutil.

    На помилках — `[]`.
    """
    try:
        import psutil  # type: ignore[import]
    except ImportError:
        return []
    try:
        out: List[Dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name"]):
            info = proc.info
            out.append({"pid": info.get("pid"), "name": (info.get("name") or "")})
        return out
    except Exception:  # noqa: BLE001
        return []


# Type aliases
WindowLister = Callable[[], List[str]]
ProcessLister = Callable[[], List[Dict[str, Any]]]
ActivityFn = Callable[[], Any]


# ---------------------------------------------------------------------------
# Windows conditions
# ---------------------------------------------------------------------------


def condition_window_title_contains(
    substr: str,
    *,
    case_insensitive: bool = True,
    window_lister: Optional[WindowLister] = None,
) -> ConditionFn:
    """True, якщо серед відкритих вікон є хоч одне, чий заголовок містить `substr`.

    Використовується для шаблонів на кшталт «коли з'явиться діалог з
    таким-то текстом». Кожен виклик condition — заново питає lister'а,
    без кешу (щоб бачити появу/зникнення вікна).
    """
    needle = substr.lower() if case_insensitive else substr
    lister = window_lister or _default_window_lister

    def _check(_ctx: Dict[str, Any]) -> bool:
        titles = lister()
        for title in titles:
            hay = title.lower() if case_insensitive else title
            if needle in hay:
                return True
        return False

    return _check


def condition_process_running(
    target: Union[str, int],
    *,
    case_insensitive: bool = True,
    process_lister: Optional[ProcessLister] = None,
) -> ConditionFn:
    """True, якщо процес з таким `name` або `pid` запущений.

    - `target`-int → matching по `pid`.
    - `target`-str → matching по `name` (часткове співпадіння, за замовч.
      case-insensitive). Зручно: `".exe"` можна не вказувати.
    """
    lister = process_lister or _default_process_lister
    if isinstance(target, int):
        pid_target: Optional[int] = target
        name_target: Optional[str] = None
    else:
        pid_target = None
        name_target = target.lower() if case_insensitive else target

    def _check(_ctx: Dict[str, Any]) -> bool:
        for p in lister():
            if pid_target is not None:
                if p.get("pid") == pid_target:
                    return True
            else:
                pname = p.get("name") or ""
                if case_insensitive:
                    pname = pname.lower()
                if name_target and name_target in pname:
                    return True
        return False

    return _check


def condition_process_finished(
    target: Union[str, int],
    *,
    case_insensitive: bool = True,
    process_lister: Optional[ProcessLister] = None,
) -> ConditionFn:
    """True *один раз*, коли процес, що раніше був запущеним, зник.

    One-shot. Corner case: якщо при першому виклику condition процесу вже
    немає — вона повертає `False` (не знаємо, чи він був запущений, тож не
    ризикуємо з false-positive). Треба запустити watcher *поки* процес
    ще живий.
    """
    running_check = condition_process_running(
        target,
        case_insensitive=case_insensitive,
        process_lister=process_lister,
    )
    state = {"ever_running": False, "fired": False}

    def _check(ctx: Dict[str, Any]) -> bool:
        if state["fired"]:
            return False
        currently = running_check(ctx)
        if currently:
            state["ever_running"] = True
            return False
        if state["ever_running"]:
            state["fired"] = True
            return True
        return False

    return _check


def condition_chat_idle(
    activity_fn: ActivityFn,
    *,
    idle_seconds: float,
    time_fn: Callable[[], float] = time.monotonic,
) -> ConditionFn:
    """True, коли `activity_fn()` не змінює результат протягом `idle_seconds`.

    `activity_fn` — будь-що, що повертає «знімок стану чату» для equality-
    порівняння: string-хеш тексту, timestamp останнього токена, номер
    повідомлення, tuple будь-чого. Якщо два послідовні опитування дають
    те саме значення → запускаємо таймер; коли проходить `idle_seconds` —
    condition спрацьовує.

    Після спрацьовування стан скидається — тобто condition автоматично
    готова знову детектувати наступний idle.
    """
    _UNSET = object()
    state: Dict[str, Any] = {
        "last_value": _UNSET,
        "last_change_at": None,
        "fired": False,
    }

    def _check(_ctx: Dict[str, Any]) -> bool:
        try:
            current = activity_fn()
        except Exception:  # noqa: BLE001
            # не знаємо стан — вважаємо, що активність триває
            state["last_value"] = _UNSET
            state["last_change_at"] = None
            state["fired"] = False
            return False

        now = time_fn()
        if state["last_value"] is _UNSET or current != state["last_value"]:
            state["last_value"] = current
            state["last_change_at"] = now
            state["fired"] = False
            return False

        last_change = state["last_change_at"]
        if last_change is None:
            last_change = now
            state["last_change_at"] = now
        elapsed = now - last_change
        if elapsed >= idle_seconds:
            # одноразове спрацьовування до наступної активності
            already = state["fired"]
            state["fired"] = True
            return not already
        return False

    return _check
