"""Тести для core_windsurf_watcher (Phase 12.5)."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from functions import core_windsurf_watcher as cww
from functions import tools_windsurf as tw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeClock:
    """Steppable monotonic clock + sleep для детермінованих тестів."""

    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: List[float] = []

    def time(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds

    def advance(self, seconds: float) -> None:
        self.t += seconds


class StubWindow:
    def __init__(self, *, hwnd: int = 1, title: str = "Windsurf",
                 process: str = "windsurf.exe") -> None:
        self._data: Optional[Dict[str, Any]] = {
            "hwnd": hwnd,
            "title": title,
            "process_name": process,
            "rect": {"x": 0, "y": 0, "width": 800, "height": 600},
        }

    def find(self) -> Optional[Dict[str, Any]]:
        return dict(self._data) if self._data else None

    def lose(self) -> None:
        self._data = None

    def restore(self, **kw: Any) -> None:
        self._data = {
            "hwnd": kw.get("hwnd", 1),
            "title": kw.get("title", "Windsurf"),
            "process_name": kw.get("process_name", "windsurf.exe"),
            "rect": kw.get("rect", {"x": 0, "y": 0, "width": 800, "height": 600}),
        }


class ScriptedOCR:
    """Повертає попередньо записані рядки по черзі."""

    def __init__(self, texts: List[str]) -> None:
        self._texts = list(texts)
        self._index = 0

    def __call__(self, _window: Dict[str, Any]) -> str:
        if self._index >= len(self._texts):
            # Застрягли на останньому — корисно для тривалого idle.
            return self._texts[-1] if self._texts else ""
        text = self._texts[self._index]
        self._index += 1
        return text


# ---------------------------------------------------------------------------
# _make_activity_fn
# ---------------------------------------------------------------------------


class TestActivityFn:
    def test_returns_found_when_window_present(self):
        win = StubWindow()
        ocr = ScriptedOCR(["hello world"])
        state = tw.WindsurfState()
        flag = {"consecutive": 0, "total": 0, "last_window": None}
        fn = cww._make_activity_fn(win.find, ocr, state, flag)
        out = fn()
        assert out == ("found", "hello world")
        assert state.snapshots_taken == 1
        assert flag["consecutive"] == 0
        assert flag["last_window"]["hwnd"] == 1

    def test_returns_lost_tuple_when_window_missing(self):
        win = StubWindow()
        win.lose()
        state = tw.WindsurfState()
        flag = {"consecutive": 0, "total": 0, "last_window": None}
        fn = cww._make_activity_fn(win.find, lambda w: "", state, flag)
        a = fn()
        b = fn()
        c = fn()
        assert a == ("lost", 1)
        assert b == ("lost", 2)
        assert c == ("lost", 3)
        assert flag["consecutive"] == 3
        assert state.window_lost_count == 3

    def test_consecutive_resets_on_window_restore(self):
        win = StubWindow()
        ocr = ScriptedOCR(["snap1", "snap1", "snap1"])
        state = tw.WindsurfState()
        flag = {"consecutive": 0, "total": 0, "last_window": None}
        fn = cww._make_activity_fn(win.find, ocr, state, flag)
        fn()  # found
        win.lose()
        fn()  # lost
        fn()  # lost
        win.restore()
        fn()  # found → reset
        assert flag["consecutive"] == 0
        # total counts all lost-events (used as persistent counter)
        assert state.window_lost_count == 2


# ---------------------------------------------------------------------------
# _make_response_action
# ---------------------------------------------------------------------------


class TestResponseAction:
    def test_no_change_returns_changed_false(self):
        state = tw.WindsurfState()
        state.last_snapshot = ""
        clock = FakeClock()
        action = cww._make_response_action(
            state, max_keep=8, time_fn=clock.time
        )
        res = action({})
        assert res == {"changed": False}

    def test_new_snapshot_registers_response(self):
        state = tw.WindsurfState()
        state.last_snapshot = "first answer"
        clock = FakeClock()
        clock.t = 100.0
        action = cww._make_response_action(state, max_keep=8, time_fn=clock.time)
        res = action({})
        assert res["changed"] is True
        assert res["response"]["text"] == "first answer"
        assert state.responses_captured == 1

    def test_second_response_extracts_tail(self):
        state = tw.WindsurfState()
        clock = FakeClock()
        action = cww._make_response_action(state, max_keep=8, time_fn=clock.time)
        state.last_snapshot = "response A"
        action({})
        state.last_snapshot = "response A response B"
        res = action({})
        assert res["changed"] is True
        assert res["response"]["text"] == "response B"
        assert state.responses_captured == 2

    def test_callback_invoked(self):
        state = tw.WindsurfState()
        clock = FakeClock()
        captured: List[Dict[str, Any]] = []
        action = cww._make_response_action(
            state,
            max_keep=8,
            time_fn=clock.time,
            on_response=captured.append,
        )
        state.last_snapshot = "some answer"
        action({})
        assert len(captured) == 1

    def test_callback_exception_is_swallowed(self):
        state = tw.WindsurfState()
        clock = FakeClock()

        def bad_cb(_entry: Dict[str, Any]) -> None:
            raise RuntimeError("callback-boom")

        action = cww._make_response_action(
            state, max_keep=8, time_fn=clock.time, on_response=bad_cb
        )
        state.last_snapshot = "ok"
        # не має впасти
        res = action({})
        assert res["changed"] is True
        assert state.responses_captured == 1


# ---------------------------------------------------------------------------
# Auto-stop condition
# ---------------------------------------------------------------------------


class TestAutoStop:
    def test_stops_on_max_responses(self):
        state = tw.WindsurfState()
        state.responses_captured = 5
        flag = {"consecutive": 0, "total": 0, "last_window": None}
        cond = cww._make_auto_stop_condition(
            state, window_lost_flag=flag, window_lost_max=5, max_responses=5
        )
        assert cond({}) is True

    def test_stops_on_window_lost(self):
        state = tw.WindsurfState()
        flag = {"consecutive": 3, "total": 3, "last_window": None}
        cond = cww._make_auto_stop_condition(
            state, window_lost_flag=flag, window_lost_max=3, max_responses=None
        )
        assert cond({}) is True

    def test_does_not_stop_otherwise(self):
        state = tw.WindsurfState()
        state.responses_captured = 2
        flag = {"consecutive": 1, "total": 1, "last_window": None}
        cond = cww._make_auto_stop_condition(
            state, window_lost_flag=flag, window_lost_max=3, max_responses=5
        )
        assert cond({}) is False


# ---------------------------------------------------------------------------
# Compose conditions
# ---------------------------------------------------------------------------


class TestCompose:
    def test_idle_returns_true_when_idle_triggered(self):
        handle = {"stopped": False}
        combined = cww._compose_conditions(
            idle_cond=lambda _c: True,
            stop_cond=lambda _c: False,
            stop_handle=handle,
        )
        assert combined({}) is True
        assert handle["stopped"] is False

    def test_stop_cond_sets_flag_and_returns_false(self):
        handle = {"stopped": False}
        combined = cww._compose_conditions(
            idle_cond=lambda _c: True,
            stop_cond=lambda _c: True,
            stop_handle=handle,
        )
        assert combined({}) is False
        assert handle["stopped"] is True

    def test_already_stopped_short_circuits(self):
        handle = {"stopped": True}
        idle_calls: List[bool] = []

        def idle(_c: Any) -> bool:
            idle_calls.append(True)
            return True

        combined = cww._compose_conditions(
            idle_cond=idle, stop_cond=lambda _c: False, stop_handle=handle
        )
        assert combined({}) is False
        assert idle_calls == []


# ---------------------------------------------------------------------------
# Runner integration (sync)
# ---------------------------------------------------------------------------


def _build_runner(
    *,
    window: StubWindow,
    texts: List[str],
    idle_seconds: float = 3.0,
    poll_interval: float = 1.0,
    max_responses: Optional[int] = None,
    max_duration_seconds: Optional[float] = None,
    window_lost_max: int = 3,
    clock: Optional[FakeClock] = None,
    log_dir: Optional[Path] = None,
    on_response: Optional[Any] = None,
) -> cww.WindsurfWatcherRunner:
    clock = clock or FakeClock()
    ocr = ScriptedOCR(texts)
    cfg = cww.WindsurfWatcherConfig(
        name="test_watcher",
        poll_interval=poll_interval,
        idle_seconds=idle_seconds,
        max_responses=max_responses,
        max_duration_seconds=max_duration_seconds,
        window_lost_max=window_lost_max,
        log_dir=log_dir,  # type: ignore[arg-type]
    )
    return cww.WindsurfWatcherRunner(
        cfg,
        window_finder=window.find,
        snapshot_fn=ocr,
        on_response=on_response,
        time_fn=clock.time,
        monotonic_fn=clock.time,
        sleep_fn=clock.sleep,
    )


class TestRunnerIntegration:
    def test_captures_response_after_idle(self, tmp_path: Path):
        window = StubWindow()
        clock = FakeClock()
        # Snapshot однаковий у всіх polling-ах → idle через 3 секунди
        runner = _build_runner(
            window=window,
            texts=["hello world"] * 50,
            idle_seconds=3.0,
            poll_interval=1.0,
            max_responses=1,
            clock=clock,
            log_dir=tmp_path / "logs",
        )
        # Runner запускаємо blocking через watcher.start(blocking=True) у окремому
        # треді, щоб auto-stop спрацював.
        t = threading.Thread(target=runner.watcher.start, kwargs={"blocking": True})
        t.start()
        # Поступово «крутимо» FakeClock-ом та чекаємо поки watcher сам зупиниться.
        deadline = time.time() + 5.0  # real wallclock timeout (safety)
        while t.is_alive() and time.time() < deadline:
            time.sleep(0.05)
        runner.stop()
        t.join(timeout=2.0)

        assert runner.state.responses_captured == 1
        assert runner.state.responses[0]["text"] == "hello world"

    def test_stops_when_window_closes(self, tmp_path: Path):
        window = StubWindow()
        clock = FakeClock()
        runner = _build_runner(
            window=window,
            texts=["ignored"] * 50,
            idle_seconds=3.0,
            poll_interval=1.0,
            window_lost_max=2,
            clock=clock,
            log_dir=tmp_path / "logs",
        )
        # Відкриваємо watcher, потім одразу закриваємо вікно.
        window.lose()
        t = threading.Thread(target=runner.watcher.start, kwargs={"blocking": True})
        t.start()
        deadline = time.time() + 5.0
        while t.is_alive() and time.time() < deadline:
            time.sleep(0.05)
        runner.stop()
        t.join(timeout=2.0)
        # Очікуємо, що window_lost_count збільшився і watcher зупинився через
        # stop_cond (або manual stop у нашому safety-bailout).
        assert runner.state.window_lost_count >= 2

    def test_on_response_callback_invoked(self, tmp_path: Path):
        received: List[Dict[str, Any]] = []
        window = StubWindow()
        clock = FakeClock()
        runner = _build_runner(
            window=window,
            texts=["answer-1"] * 50,
            idle_seconds=3.0,
            poll_interval=1.0,
            max_responses=1,
            clock=clock,
            log_dir=tmp_path / "logs",
            on_response=received.append,
        )
        t = threading.Thread(target=runner.watcher.start, kwargs={"blocking": True})
        t.start()
        deadline = time.time() + 5.0
        while t.is_alive() and time.time() < deadline:
            time.sleep(0.05)
        runner.stop()
        t.join(timeout=2.0)
        assert len(received) == 1
        assert received[0]["text"] == "answer-1"


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


class TestCreateWindsurfWatcher:
    def test_defaults(self):
        runner = cww.create_windsurf_watcher(
            window_finder=lambda: None,
            snapshot_fn=lambda w: "",
        )
        assert isinstance(runner, cww.WindsurfWatcherRunner)
        assert runner.config.idle_seconds == 3.0
        assert runner.config.max_duration_seconds == 6 * 60 * 60

    def test_custom_log_dir(self, tmp_path: Path):
        runner = cww.create_windsurf_watcher(
            window_finder=lambda: None,
            snapshot_fn=lambda w: "",
            log_dir=tmp_path / "x",
        )
        assert runner.config.log_dir == tmp_path / "x"

    def test_summary_structure(self):
        runner = cww.create_windsurf_watcher(
            window_finder=lambda: None,
            snapshot_fn=lambda w: "",
        )
        s = runner.summary()
        assert "name" in s
        assert "responses_captured" in s
        assert "state" in s
        assert s["responses_captured"] == 0


# ---------------------------------------------------------------------------
# Basic smoke: start/stop lifecycle (no blocking)
# ---------------------------------------------------------------------------


def test_runner_start_stop_lifecycle(tmp_path: Path):
    """Перевіряємо що start/stop не ламається для non-blocking режиму."""
    window = StubWindow()
    runner = cww.create_windsurf_watcher(
        idle_seconds=30.0,  # довше ніж буде тест — action не викликатиметься
        max_duration_seconds=30.0,
        window_finder=window.find,
        snapshot_fn=lambda w: "text",
        log_dir=tmp_path / "logs",
    )
    runner.start()
    time.sleep(0.1)
    runner.stop()
    # Після стопу тред має коректно завершитись; жодних assertion не потрібно —
    # тест просто не має виснути.
    assert runner.state.snapshots_taken >= 0
