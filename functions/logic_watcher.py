"""Watcher engine — event-driven loops для довгих автономних сесій.

Phase 8 / I1. Ідея:
- Watcher спостерігає за *умовою* (condition_fn) і, коли та стає true,
  виконує *дію* (action_fn). Дія може змінювати стан світу (наприклад,
  відправляти новий промпт у чат Windsurf), після чого cycle повторюється
  до наступного події — і так години.
- Все неблокуюче: watcher працює у окремому треді, UI не «підвисає».
- Вбудовані condition-фабрики у розділі Conditions — прості і доступні
  без PyWin32 (щоб Linux-CI прокручував тести).
- Кожен watcher опційно інтегрується з `SessionBudget` — перед кожною
  ітерацією викликається `budget.check()`, і при exhaustion watcher
  коректно зупиняється.
- Персистенція: append-only JSONL у `logs/watchers/{id}.jsonl`. Досить
  для post-mortem і для `resume_watcher(id)` (перечитуємо останній стан).

Свідомо **без жорсткого зв'язку з TaskExecutor / TOOL_POLICIES**: action_fn
приймається як callable. Це дає:
  - легке юніт-тестування (action = `lambda ctx: ctx['counter'] += 1`),
  - заміну на `orchestrator.delegate(...)` у Phase 9 без переписування.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .core_session_budget import SessionBudget


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


ConditionFn = Callable[[Dict[str, Any]], bool]
ActionFn = Callable[[Dict[str, Any]], Any]


@dataclass
class WatcherConfig:
    """Конфіг watcher-а.

    - `poll_interval` — секунди між перевірками умови.
    - `max_iterations` — скільки разів максимум спрацьовує action (None = ∞).
    - `max_duration_seconds` — hard-таймаут для watcher-а окремо від
      загального SessionBudget (None = ∞).
    """

    name: str
    poll_interval: float = 1.0
    max_iterations: Optional[int] = None
    max_duration_seconds: Optional[float] = None


@dataclass
class WatcherState:
    """Сnapshot поточного стану watcher-а для логів/resume.

    - `loop_passes` — скільки разів викликалася condition (межа `max_iterations`
      рахується саме ним — інакше watcher із always-false condition зациклювався
      б). Для зворотньої сумісності `iterations` є alias-ом.
    - `actions_fired` — скільки разів викликалася action успішно.
    """

    watcher_id: str
    name: str
    running: bool
    loop_passes: int = 0
    actions_fired: int = 0
    errors: int = 0
    started_at: float = 0.0
    stopped_at: Optional[float] = None
    last_action_at: Optional[float] = None
    last_error: str = ""
    stop_reason: str = ""

    @property
    def iterations(self) -> int:  # noqa: D401
        """Alias на loop_passes (backward-compat)."""
        return self.loop_passes


# ---------------------------------------------------------------------------
# Watcher
# ---------------------------------------------------------------------------


class Watcher:
    """Один спостерігач умови + реакції.

    Thread-safe щодо start/stop. Основний loop — у приватному `_run`.
    """

    def __init__(
        self,
        config: WatcherConfig,
        condition: ConditionFn,
        action: ActionFn,
        *,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional[SessionBudget] = None,
        log_path: Optional[Path] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self.config = config
        self._condition = condition
        self._action = action
        self._context = context if context is not None else {}
        self._budget = budget
        self._log_path = log_path
        self._sleep = sleep_fn
        self._time = time_fn

        self.id = uuid.uuid4().hex[:8]
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._state = WatcherState(
            watcher_id=self.id,
            name=config.name,
            running=False,
        )
        self._lock = threading.Lock()

    # ----- Public API ----------------------------------------------------

    @property
    def state(self) -> WatcherState:
        with self._lock:
            # Повертаємо копію, щоб виклик зовні не впливав на внутрішній стан.
            data = asdict(self._state)
            # asdict не віддає property `iterations`, але вона й не нужна в constructor.
            return WatcherState(**data)

    @property
    def context(self) -> Dict[str, Any]:
        return self._context

    def start(self, *, blocking: bool = False) -> None:
        """Запуск. За замовч. у окремому треді (non-blocking)."""
        with self._lock:
            if self._state.running:
                raise RuntimeError(f"Watcher {self.id} is already running")
            self._stop_event.clear()
            self._state.running = True
            self._state.started_at = self._time()
            self._state.stopped_at = None
            self._state.stop_reason = ""

        if blocking:
            self._run()
        else:
            self._thread = threading.Thread(
                target=self._run,
                name=f"watcher-{self.config.name}-{self.id}",
                daemon=True,
            )
            self._thread.start()

    def stop(self, reason: str = "manual", join: bool = True, timeout: float = 5.0) -> None:
        with self._lock:
            if not self._state.running:
                return
            self._state.stop_reason = reason
        self._stop_event.set()
        if join and self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    # ----- Core loop -----------------------------------------------------

    def _run(self) -> None:
        cfg = self.config
        try:
            while not self._stop_event.is_set():
                # 1) Budget (якщо є).
                if self._budget is not None:
                    check = self._budget.check()
                    if not check.ok:
                        self._set_stop_reason(f"budget:{check.reason}")
                        break

                # 2) Watcher-власні ліміти.
                if (
                    cfg.max_iterations is not None
                    and self._state.loop_passes >= cfg.max_iterations
                ):
                    self._set_stop_reason("max_iterations")
                    break
                if (
                    cfg.max_duration_seconds is not None
                    and self._time() - self._state.started_at
                    >= cfg.max_duration_seconds
                ):
                    self._set_stop_reason("max_duration")
                    break

                # 3) Condition check. Кожний прохід циклу нараховується в loop_passes,
                # навіть якщо condition повернув False або кинув exception — інакше
                # watcher із неробочою condition зациклюється на max_iterations.
                with self._lock:
                    self._state.loop_passes += 1
                triggered = self._safe_condition()
                if triggered:
                    self._safe_action()
                    # одразу після action знову перевіряємо стоп,
                    # щоб не робити зайвий sleep.
                    if self._stop_event.is_set():
                        break

                # 4) Sleep (переривається, якщо stop).
                self._interruptible_sleep(cfg.poll_interval)
        finally:
            with self._lock:
                self._state.running = False
                self._state.stopped_at = self._time()
            self._append_log({"event": "stopped", "state": asdict(self._state)})

    def _safe_condition(self) -> bool:
        try:
            return bool(self._condition(self._context))
        except Exception as exc:  # noqa: BLE001
            self._record_error(f"condition: {exc}")
            return False

    def _safe_action(self) -> None:
        try:
            result = self._action(self._context)
            with self._lock:
                self._state.actions_fired += 1
                self._state.last_action_at = self._time()
            if self._budget is not None:
                self._budget.record_step()
            self._append_log(
                {
                    "event": "action",
                    "iteration": self._state.actions_fired,
                    "at": self._state.last_action_at,
                    "result": _safe_repr(result),
                }
            )
        except Exception as exc:  # noqa: BLE001
            self._record_error(f"action: {exc}")
            if self._budget is not None:
                self._budget.record_error()

    def _interruptible_sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        # Використовуємо `wait` events замість звичайного sleep — це дає
        # миттєвий вихід при stop(). Але sleep_fn тестоване: якщо користувач
        # підсунув custom sleep — використаємо його (тест-режим).
        if self._sleep is time.sleep:
            self._stop_event.wait(timeout=seconds)
        else:
            self._sleep(seconds)

    # ----- State helpers -------------------------------------------------

    def _record_error(self, message: str) -> None:
        with self._lock:
            self._state.errors += 1
            self._state.last_error = message
        self._append_log({"event": "error", "message": message})

    def _set_stop_reason(self, reason: str) -> None:
        with self._lock:
            if not self._state.stop_reason:
                self._state.stop_reason = reason

    def _append_log(self, entry: Dict[str, Any]) -> None:
        if self._log_path is None:
            return
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:
            print(f"[Watcher {self.id}] log write failed: {exc}")


# ---------------------------------------------------------------------------
# Engine (manages multiple watchers)
# ---------------------------------------------------------------------------


class WatcherEngine:
    """Реєстр активних watcher-ів + shortcut-и `start/stop/list`."""

    def __init__(self, logs_dir: str | Path = "logs/watchers"):
        self.logs_dir = Path(logs_dir)
        self._watchers: Dict[str, Watcher] = {}
        self._lock = threading.Lock()

    def register(self, watcher: Watcher) -> str:
        with self._lock:
            self._watchers[watcher.id] = watcher
        return watcher.id

    def start(
        self,
        config: WatcherConfig,
        condition: ConditionFn,
        action: ActionFn,
        *,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional[SessionBudget] = None,
        blocking: bool = False,
    ) -> Watcher:
        """Створити, зареєструвати та запустити watcher."""
        log_path = self.logs_dir / f"{config.name}.jsonl"
        watcher = Watcher(
            config=config,
            condition=condition,
            action=action,
            context=context,
            budget=budget,
            log_path=log_path,
        )
        self.register(watcher)
        watcher.start(blocking=blocking)
        return watcher

    def stop(self, watcher_id: str, reason: str = "manual") -> bool:
        with self._lock:
            watcher = self._watchers.get(watcher_id)
        if watcher is None:
            return False
        watcher.stop(reason=reason)
        return True

    def stop_all(self, reason: str = "shutdown") -> None:
        with self._lock:
            watchers = list(self._watchers.values())
        for w in watchers:
            w.stop(reason=reason)

    def list_watchers(self) -> List[WatcherState]:
        with self._lock:
            return [w.state for w in self._watchers.values()]

    def get(self, watcher_id: str) -> Optional[Watcher]:
        with self._lock:
            return self._watchers.get(watcher_id)


# ---------------------------------------------------------------------------
# Built-in condition factories
# ---------------------------------------------------------------------------


def condition_file_changed(path: str | Path) -> ConditionFn:
    """True коли mtime файлу змінився з моменту попередньої перевірки."""
    p = Path(path)
    last_mtime = [p.stat().st_mtime if p.exists() else None]

    def _check(_ctx: Dict[str, Any]) -> bool:
        if not p.exists():
            return False
        current = p.stat().st_mtime
        if last_mtime[0] is None:
            last_mtime[0] = current
            return False
        if current != last_mtime[0]:
            last_mtime[0] = current
            return True
        return False

    return _check


def condition_file_exists(path: str | Path) -> ConditionFn:
    """True коли файл з'явився (стартово false, без повторних спрацювань)."""
    p = Path(path)
    fired = [False]

    def _check(_ctx: Dict[str, Any]) -> bool:
        if fired[0]:
            return False
        if p.exists():
            fired[0] = True
            return True
        return False

    return _check


def condition_idle_for(
    seconds: float,
    *,
    last_activity_key: str = "last_activity_at",
    time_fn: Callable[[], float] = time.monotonic,
) -> ConditionFn:
    """True, якщо з моменту `ctx[last_activity_key]` пройшло ≥ seconds.

    Використовується для шаблону «інший ШІ закінчив відповідати»: у `ctx`
    записуєш timestamp останнього відомого оновлення (наприклад з polling-у
    чату), а watcher чекає, поки не пройде потрібний проміжок без змін.
    """

    def _check(ctx: Dict[str, Any]) -> bool:
        last = ctx.get(last_activity_key)
        if last is None:
            return False
        return (time_fn() - last) >= seconds

    return _check


def condition_counter_reached(
    target: int,
    *,
    counter_key: str = "counter",
) -> ConditionFn:
    """True, якщо `ctx[counter_key] >= target`. Простий примітив для тестів."""

    def _check(ctx: Dict[str, Any]) -> bool:
        return ctx.get(counter_key, 0) >= target

    return _check


def condition_any(*conditions: ConditionFn) -> ConditionFn:
    """Логічне OR — спрацьовує, якщо хоч одна умова true."""

    def _check(ctx: Dict[str, Any]) -> bool:
        return any(c(ctx) for c in conditions)

    return _check


def condition_all(*conditions: ConditionFn) -> ConditionFn:
    """Логічне AND — спрацьовує, коли всі умови одночасно true."""

    def _check(ctx: Dict[str, Any]) -> bool:
        return all(c(ctx) for c in conditions)

    return _check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_repr(value: Any, limit: int = 500) -> str:
    try:
        text = repr(value)
    except Exception:  # noqa: BLE001
        return "<unrepr>"
    if len(text) > limit:
        return text[:limit] + f"...({len(text) - limit} more)"
    return text
