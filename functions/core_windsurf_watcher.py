"""Windsurf Watcher — passive monitor для чат-відповідей Windsurf.

Phase 12.5. Перший реальний end-to-end кейс для Phase 11+ стеку:
- `Watcher` (PR #7) крутить цикл у фоновому треді;
- `condition_chat_idle` (PR #11) ловить момент коли Windsurf закінчив
  генерувати (snapshot тексту не змінюється N секунд);
- `tools_windsurf` (цей PR) знаходить вікно й робить OCR-snapshot;
- `SessionBudget` (PR #7) — kill-switch по часу / N-відповідях;
- Persistence: JSONL-лог `logs/windsurf_watch/{watcher_id}.jsonl`.

**Це passive-watcher**: він не пише у Windsurf і не виконує команд, які
пропонує ШІ. Тільки спостерігає й зберігає відповіді. Для auto-execute —
треба окремий слой (follow-up PR: WindsurfActor).

Дизайн безпеки:
- Auto-stop, якщо Windsurf-вікно зникло (`window_lost_max` раз поспіль).
- Auto-stop через файл-маркер (через `SessionBudget.stop_file`).
- Auto-stop при досягненні `max_responses` / `max_duration_seconds`.
- Жодних side effects на Windsurf — тільки OCR (read-only).
"""
from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .conditions_windows import condition_chat_idle
from .core_session_budget import SessionBudget, SessionLimits
from .logic_watcher import ActionFn, ConditionFn, Watcher, WatcherConfig
from .tools_windsurf import (
    SnapshotFn,
    WindowFinder,
    WindsurfState,
    WindsurfWindow,
    diff_snapshots,
    make_default_snapshot_fn,
    make_default_window_finder,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class WindsurfWatcherConfig:
    """Високорівневий конфіг watcher-а.

    Всі поля мають безпечні дефолти для «подивися 6 годин поки я сплю».
    """

    name: str = "windsurf_watch"
    poll_interval: float = 1.0
    idle_seconds: float = 3.0
    """Скільки секунд snapshot-у треба бути стабільним, щоб вважати
    відповідь готовою. Занадто мало → півзгенерована відповідь
    буде записана; занадто багато → reaction-лаг."""

    max_responses: Optional[int] = None
    """Stop after N captured responses. `None` = необмежено."""

    max_duration_seconds: Optional[float] = 6 * 60 * 60  # 6h
    max_tokens: Optional[int] = None
    window_lost_max: int = 5
    """Скільки разів поспіль window_finder може віддати None перед тим,
    як watcher самостійно зупиниться. Це правила з кейсу «я закрив Windsurf»."""

    keep_last_responses: int = 64
    """Скільки свіжих відповідей тримати у RAM-буфері `WindsurfState.responses`."""

    log_dir: Path = field(default_factory=lambda: Path("logs/windsurf_watch"))
    """Директорія для JSONL-логу. Якщо `None` — без логу."""


# ---------------------------------------------------------------------------
# Watcher factory
# ---------------------------------------------------------------------------


def _make_activity_fn(
    window_finder: WindowFinder,
    snapshot_fn: SnapshotFn,
    state: WindsurfState,
    window_lost_flag: Dict[str, Any],
) -> Callable[[], Any]:
    """Повертає activity_fn для `condition_chat_idle`.

    Повертає tuple `(found_bool, snapshot_text)`. condition-idle зазначає
    idle тільки коли цей tuple не змінюється. Якщо Windsurf-вікно зникло —
    tuple стає `(False, "<lost_N>")`, тобто «активність», і idle не спрацює
    → action не викликається, але `window_lost_count` нараховується.
    """

    def _activity() -> Any:
        window = window_finder()
        if window is None:
            window_lost_flag["consecutive"] += 1
            window_lost_flag["total"] += 1
            state.window_lost_count = window_lost_flag["total"]
            # Унікальне значення для кожного «втраченого» polling-у —
            # condition_chat_idle НЕ спрацює, бо значення увесь час міняється.
            return ("lost", window_lost_flag["consecutive"])
        window_lost_flag["consecutive"] = 0
        window_lost_flag["last_window"] = window
        snapshot = snapshot_fn(window)
        state.last_snapshot = snapshot
        state.snapshots_taken += 1
        # Tuple з хешем, щоб idle-condition бачив equality швидко,
        # а не порівнював мегабайти OCR-ованого тексту.
        return ("found", snapshot)

    return _activity


def _make_response_action(
    state: WindsurfState,
    *,
    max_keep: int,
    time_fn: Callable[[], float],
    on_response: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> ActionFn:
    """Повертає action_fn, що викликається коли idle спрацював.

    Дія: diff(prev, curr) → якщо змінилось → register_response() →
    опційно callback.
    """
    prev_snapshot: Dict[str, str] = {"text": ""}

    def _action(_ctx: Dict[str, Any]) -> Dict[str, Any]:
        current = state.last_snapshot
        diff = diff_snapshots(prev_snapshot["text"], current)
        if not diff.changed:
            return {"changed": False}
        prev_snapshot["text"] = current
        entry = state.register_response(at=time_fn(), diff=diff, max_keep=max_keep)
        if on_response is not None:
            try:
                on_response(entry)
            except Exception:  # noqa: BLE001
                # Callback-помилка не має ламати watcher.
                pass
        return {"changed": True, "response": entry}

    return _action


def _make_auto_stop_condition(
    state: WindsurfState,
    *,
    window_lost_flag: Dict[str, Any],
    window_lost_max: int,
    max_responses: Optional[int],
) -> ConditionFn:
    """Допоміжна condition: `True` коли треба примусово зупинити watcher.

    Watcher не підтримує multi-condition з коробки, тому цей перевіряємо
    **перед** idle-condition у composite-wrapper-і.
    """

    def _check(_ctx: Dict[str, Any]) -> bool:
        if window_lost_flag["consecutive"] >= window_lost_max:
            return True
        if max_responses is not None and state.responses_captured >= max_responses:
            return True
        return False

    return _check


def _compose_conditions(
    idle_cond: ConditionFn, stop_cond: ConditionFn, stop_handle: Dict[str, Any]
) -> ConditionFn:
    """Якщо stop_cond спрацювала — виставляємо прапор; idle_cond ігнорується.

    Watcher сам не вміє зупинятись за condition-ом, тому:
    - stop_handle["stopped"] = True коли час зупинятись;
    - воркер `Watcher._run` зупиниться одразу після наступного loop-pass,
      бо condition повертає False (action не виконується) → на наступній
      ітерації ми викликаємо `stop()` через зовнішній таймерний механізм.

    Для простоти та надійності використовуємо окрему функцію
    `WindsurfWatcherRunner._maybe_auto_stop`, яка читає stop_handle.
    """

    def _combined(ctx: Dict[str, Any]) -> bool:
        if stop_cond(ctx):
            stop_handle["stopped"] = True
            return False
        if stop_handle["stopped"]:
            return False
        return idle_cond(ctx)

    return _combined


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class WindsurfWatcherRunner:
    """High-level обгортка над `Watcher`, що вміє passive monitor Windsurf.

    Використання:
    ```
    runner = WindsurfWatcherRunner()
    runner.start()  # non-blocking, у окремому треді
    ...
    runner.stop()
    ```

    Або blocking (CLI-mode):
    ```
    runner.run_forever()  # блокує до stop file / max_duration
    ```
    """

    def __init__(
        self,
        config: Optional[WindsurfWatcherConfig] = None,
        *,
        window_finder: Optional[WindowFinder] = None,
        snapshot_fn: Optional[SnapshotFn] = None,
        budget: Optional[SessionBudget] = None,
        on_response: Optional[Callable[[Dict[str, Any]], None]] = None,
        time_fn: Callable[[], float] = time.time,
        monotonic_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or WindsurfWatcherConfig()
        self.window_finder = window_finder or make_default_window_finder()
        self.snapshot_fn = snapshot_fn or make_default_snapshot_fn()
        self.state = WindsurfState()
        self._window_lost_flag: Dict[str, Any] = {
            "consecutive": 0,
            "total": 0,
            "last_window": None,
        }
        self._stop_handle: Dict[str, Any] = {"stopped": False}
        self._time_fn = time_fn
        self._monotonic_fn = monotonic_fn
        self._sleep_fn = sleep_fn
        self._on_response = on_response

        if budget is not None:
            self._budget: Optional[SessionBudget] = budget
        else:
            limits = SessionLimits(
                max_steps=None,
                max_tokens=self.config.max_tokens,
                max_duration_seconds=self.config.max_duration_seconds,
                max_cost_usd=None,
                max_errors=None,
            )
            self._budget = SessionBudget(limits=limits)

        # Activity / idle / action
        activity = _make_activity_fn(
            self.window_finder,
            self.snapshot_fn,
            self.state,
            self._window_lost_flag,
        )
        idle_cond = condition_chat_idle(
            activity,
            idle_seconds=self.config.idle_seconds,
            time_fn=monotonic_fn,
        )
        stop_cond = _make_auto_stop_condition(
            self.state,
            window_lost_flag=self._window_lost_flag,
            window_lost_max=self.config.window_lost_max,
            max_responses=self.config.max_responses,
        )
        combined = _compose_conditions(idle_cond, stop_cond, self._stop_handle)
        action = _make_response_action(
            self.state,
            max_keep=self.config.keep_last_responses,
            time_fn=time_fn,
            on_response=self._on_response,
        )

        # Log path
        log_path: Optional[Path] = None
        if self.config.log_dir is not None:
            log_path = Path(self.config.log_dir) / f"{self.config.name}.jsonl"

        self.watcher = Watcher(
            config=WatcherConfig(
                name=self.config.name,
                poll_interval=self.config.poll_interval,
                max_duration_seconds=self.config.max_duration_seconds,
            ),
            condition=combined,
            action=action,
            context={"windsurf": self.state},
            budget=self._budget,
            log_path=log_path,
            sleep_fn=sleep_fn,
            time_fn=monotonic_fn,
        )

        self._stop_thread: Optional[threading.Thread] = None

    # -- public API -----------------------------------------------------------

    @property
    def responses_captured(self) -> int:
        return self.state.responses_captured

    def start(self) -> None:
        """Non-blocking старт watcher-а у фоновому треді.

        Додатково піднімає внутрішній «auto-stop» тред, який перевіряє
        `_stop_handle["stopped"]` раз на `poll_interval` і викликає
        `watcher.stop()` коли треба.
        """
        self.watcher.start(blocking=False)
        self._stop_thread = threading.Thread(
            target=self._auto_stop_loop,
            name=f"{self.config.name}-autostop",
            daemon=True,
        )
        self._stop_thread.start()

    def stop(self, reason: str = "manual") -> None:
        """Примусова зупинка. Безпечно викликати декілька разів."""
        self._stop_handle["stopped"] = True
        self.watcher.stop(reason=reason)

    def run_forever(self) -> Dict[str, Any]:
        """Blocking режим для CLI. Повертає summary у самому кінці."""
        self.watcher.start(blocking=True)
        return self.summary()

    def summary(self) -> Dict[str, Any]:
        """Human-readable підсумок поточного стану."""
        st = self.watcher.state
        return {
            "name": self.config.name,
            "running": st.running,
            "stop_reason": st.stop_reason,
            "responses_captured": self.state.responses_captured,
            "snapshots_taken": self.state.snapshots_taken,
            "window_lost": self.state.window_lost_count,
            "loop_passes": st.loop_passes,
            "errors": st.errors,
            "state": asdict(self.state),
        }

    # -- internal -------------------------------------------------------------

    def _auto_stop_loop(self) -> None:
        """Окремий тонкий тред-доглядач: коли composite condition ставить
        `stopped=True` — викликає `watcher.stop()`. Без цього watcher крутився
        б у idle-режимі, бо `Watcher._run` не вміє читати composite-прапор.
        """
        interval = max(0.1, float(self.config.poll_interval))
        while self.watcher.state.running:
            if self._stop_handle["stopped"]:
                reason = "auto:window_lost"
                if (
                    self.config.max_responses is not None
                    and self.state.responses_captured >= self.config.max_responses
                ):
                    reason = "auto:max_responses"
                self.watcher.stop(reason=reason, join=False)
                return
            self._sleep_fn(interval)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def create_windsurf_watcher(
    *,
    poll_interval: float = 1.0,
    idle_seconds: float = 3.0,
    max_duration_seconds: Optional[float] = 6 * 60 * 60,
    max_responses: Optional[int] = None,
    on_response: Optional[Callable[[Dict[str, Any]], None]] = None,
    log_dir: Optional[Path] = None,
    window_finder: Optional[WindowFinder] = None,
    snapshot_fn: Optional[SnapshotFn] = None,
) -> WindsurfWatcherRunner:
    """Convenience-factory: створює готовий runner з дефолтними адаптерами."""
    cfg = WindsurfWatcherConfig(
        poll_interval=poll_interval,
        idle_seconds=idle_seconds,
        max_duration_seconds=max_duration_seconds,
        max_responses=max_responses,
        log_dir=log_dir if log_dir is not None else Path("logs/windsurf_watch"),
    )
    return WindsurfWatcherRunner(
        cfg,
        window_finder=window_finder,
        snapshot_fn=snapshot_fn,
        on_response=on_response,
    )


__all__ = [
    "WindsurfWatcherConfig",
    "WindsurfWatcherRunner",
    "create_windsurf_watcher",
]
