"""Conditions для Windows-специфічних сценаріїв (idle-детекція чату, вікна, процеси).

Кожна функція повертає **condition-функцію** з сигнатурою `(ctx: dict) -> bool`.
Це дозволяє використовувати їх у `Watcher` та інших циклах очікування.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Утиліти
# ---------------------------------------------------------------------------

def _make_window_lister() -> Callable[[], List[str]]:
    """Повертає функцію, яка читає список заголовків вікон через pygetwindow.

    Якщо pygetwindow не встановлено — повертає пустий список.
    """
    try:
        import pygetwindow as gw
        return lambda: [w.title for w in gw.getWindowsWithTitle("") if w.title]
    except ImportError:
        return lambda: []


def _make_process_lister() -> Callable[[], List[Dict[str, Any]]]:
    """Повертає функцію, яка читає список процесів через psutil.

    Якщо psutil не встановлено — повертає пустий список.
    """
    try:
        import psutil
        def _list():
            result = []
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pinfo = proc.info
                    result.append({"pid": pinfo["pid"], "name": pinfo["name"]})
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return result
        return _list
    except ImportError:
        return lambda: []


# ---------------------------------------------------------------------------
# condition_window_title_contains
# ---------------------------------------------------------------------------


def condition_window_title_contains(
    substring: str,
    *,
    case_insensitive: bool = True,
    window_lister: Optional[Callable[[], List[str]]] = None,
) -> Callable[[Dict[str, Any]], bool]:
    """Повертає condition: True якщо будь-яке вікно містить `substring` у тайтлі.

    Args:
        substring: підрядок для пошуку.
        case_insensitive: регістронезалежний пошук (default True).
        window_lister: функція, що повертає список заголовків вікон.
            Якщо None — використовується дефолтний через pygetwindow.

    Returns:
        condition-функція (ctx -> bool).
    """
    lister = window_lister or _make_window_lister()

    if case_insensitive:
        sub_lower = substring.lower()
        def _check(_ctx: Dict[str, Any]) -> bool:
            titles = lister()
            return any(sub_lower in t.lower() for t in titles)
    else:
        def _check(_ctx: Dict[str, Any]) -> bool:
            titles = lister()
            return any(substring in t for t in titles)

    return _check


# ---------------------------------------------------------------------------
# condition_process_running
# ---------------------------------------------------------------------------


def condition_process_running(
    name_or_pid: Union[str, int],
    *,
    process_lister: Optional[Callable[[], List[Dict[str, Any]]]] = None,
) -> Callable[[Dict[str, Any]], bool]:
    """Повертає condition: True якщо процес з таким ім'ям або PID існує.

    Args:
        name_or_pid: рядок (ім'я, регістронезалежно) або int (PID).
        process_lister: функція, що повертає список [{pid, name}, ...].
            Якщо None — використовується дефолтний через psutil.

    Returns:
        condition-функція (ctx -> bool).
    """
    lister = process_lister or _make_process_lister()

    if isinstance(name_or_pid, int):
        pid_target = name_or_pid
        def _check(_ctx: Dict[str, Any]) -> bool:
            procs = lister()
            return any(p.get("pid") == pid_target for p in procs)
    else:
        name_lower = name_or_pid.lower()
        def _check(_ctx: Dict[str, Any]) -> bool:
            procs = lister()
            pname: Optional[str]
            for p in procs:
                pname = p.get("name")
                if pname is not None and name_lower in pname.lower():
                    return True
            return False

    return _check


# ---------------------------------------------------------------------------
# condition_process_finished
# ---------------------------------------------------------------------------


def condition_process_finished(
    name_or_pid: Union[str, int],
    *,
    process_lister: Optional[Callable[[], List[Dict[str, Any]]]] = None,
) -> Callable[[Dict[str, Any]], bool]:
    """Повертає one-shot condition: True коли процес зник після того, як був.

    **One-shot**: після першого True завжди повертає False, навіть якщо
    процес з'явиться і знову зникне. Щоб перевикористати — створити новий
    condition.

    Args:
        name_or_pid: рядок (ім'я) або int (PID).
        process_lister: функція, що повертає список [{pid, name}, ...].
            Якщо None — використовується дефолтний через psutil.

    Returns:
        condition-функція (ctx -> bool).
    """
    lister = process_lister or _make_process_lister()
    _seen = False
    _fired = False

    def _check(_ctx: Dict[str, Any]) -> bool:
        nonlocal _seen, _fired
        if _fired:
            return False

        procs = lister()

        if isinstance(name_or_pid, int):
            found = any(p.get("pid") == name_or_pid for p in procs)
        else:
            name_lower = name_or_pid.lower()
            found = any(
                p.get("name") is not None and name_lower in p["name"].lower()
                for p in procs
            )

        if found:
            _seen = True
            return False

        if _seen and not found:
            _fired = True
            return True

        return False

    return _check


# ---------------------------------------------------------------------------
# condition_chat_idle
# ---------------------------------------------------------------------------


def condition_chat_idle(
    activity_fn: Callable[[], Any],
    *,
    idle_seconds: float = 2.0,
    time_fn: Optional[Callable[[], float]] = None,
) -> Callable[[Dict[str, Any]], bool]:
    """Повертає condition: True коли `activity_fn` не змінює значення
    протягом `idle_seconds` секунд.

    **One-shot per idle period**: після спрацювання повертає False при
    повторних викликах, поки не з'явиться нова активність (activity_fn змінить значення).

    Args:
        activity_fn: функція без аргументів, повертає будь-яке значення.
        idle_seconds: скільки секунд має бути тихо.
        time_fn: годинник (за замовчуванням time.time). Для тестів передають
            фіктивний `lambda: clock[0]`.

    Returns:
        condition-функція (ctx -> bool).
    """
    if time_fn is None:
        time_fn = time.time

    _last_value: Any = None
    _last_time: float = 0.0
    _has_baseline: bool = False
    _fired: bool = False

    def _check(_ctx: Dict[str, Any]) -> bool:
        nonlocal _last_value, _last_time, _has_baseline, _fired

        try:
            current = activity_fn()
        except Exception:
            # Якщо activity_fn кидає помилку — вважаємо, що активність є
            _has_baseline = False
            return False

        now = time_fn()

        if not _has_baseline:
            _last_value = current
            _last_time = now
            _has_baseline = True
            _fired = False
            return False

        if current != _last_value:
            # Активність змінилась — скидаємо таймер
            _last_value = current
            _last_time = now
            _fired = False
            return False

        # Значення не змінилось — перевіряємо чи минуло idle_seconds
        if not _fired and (now - _last_time) >= idle_seconds:
            _fired = True
            return True

        return False

    return _check


# ---------------------------------------------------------------------------
# Експорт
# ---------------------------------------------------------------------------

__all__ = [
    "condition_chat_idle",
    "condition_process_finished",
    "condition_process_running",
    "condition_window_title_contains",
]