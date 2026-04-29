"""Тести для functions/logic_watcher.py.

Всі тести запускаємо у blocking-режимі (`start(blocking=True)`) — це дає
детермінізм без залежності від реального `time.sleep`. `sleep_fn` і
`time_fn` підмінені на ручні лічильники.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.core_session_budget import SessionBudget, SessionLimits  # noqa: E402
from functions.logic_watcher import (  # noqa: E402
    Watcher,
    WatcherConfig,
    WatcherEngine,
    condition_all,
    condition_any,
    condition_counter_reached,
    condition_file_changed,
    condition_file_exists,
    condition_idle_for,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_fake_time():
    """Повертає (time_fn, advance(sec)) — ручний годинник."""
    state = {"t": 0.0}

    def time_fn():
        return state["t"]

    def advance(seconds):
        state["t"] += seconds

    return time_fn, advance


# ---------------------------------------------------------------------------
# Watcher core loop
# ---------------------------------------------------------------------------


class TestWatcherBasics:
    def test_runs_until_max_iterations(self):
        """Watcher зупиняється, коли досягнуто max_iterations (loop passes)."""
        time_fn, advance = make_fake_time()
        config = WatcherConfig(name="iters", poll_interval=0, max_iterations=3)
        ctx = {"count": 0}

        def action(c):
            c["count"] += 1
            advance(0.01)

        watcher = Watcher(
            config,
            condition=lambda c: True,
            action=action,
            context=ctx,
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        assert ctx["count"] == 3
        assert watcher.state.loop_passes == 3
        assert watcher.state.actions_fired == 3
        assert watcher.state.iterations == 3  # alias
        assert watcher.state.stop_reason == "max_iterations"
        assert watcher.state.running is False

    def test_runs_until_max_duration(self):
        time_fn, advance = make_fake_time()
        config = WatcherConfig(
            name="dur",
            poll_interval=1,
            max_iterations=None,
            max_duration_seconds=5,
        )
        calls = [0]

        def action(_):
            calls[0] += 1

        watcher = Watcher(
            config,
            condition=lambda c: True,
            action=action,
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        assert watcher.state.stop_reason == "max_duration"
        # Мали хоча б одну дію.
        assert calls[0] >= 1

    def test_action_runs_only_when_condition_true(self):
        """Action викликається тільки на тих проходах, де condition=true."""
        time_fn, advance = make_fake_time()
        config = WatcherConfig(name="cond", poll_interval=0, max_iterations=10)
        ctx = {"tick": 0, "fired": 0}

        def cond(c):
            c["tick"] += 1
            return c["tick"] % 2 == 0  # кожен другий

        def action(c):
            c["fired"] += 1

        watcher = Watcher(
            config,
            condition=cond,
            action=action,
            context=ctx,
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        # max_iterations обмежує кількість проходів циклу (loop_passes), не action-ів.
        assert watcher.state.loop_passes == 10
        assert ctx["tick"] == 10
        # action файрив на парних tick → 5 разів.
        assert ctx["fired"] == 5
        assert watcher.state.actions_fired == 5

    def test_condition_exception_does_not_crash(self):
        time_fn, advance = make_fake_time()
        config = WatcherConfig(name="err", poll_interval=0, max_iterations=5)

        def bad_cond(_c):
            raise RuntimeError("condition boom")

        action_calls = [0]

        watcher = Watcher(
            config,
            condition=bad_cond,
            action=lambda c: action_calls.__setitem__(0, action_calls[0] + 1),
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        # Дія ніколи не викликалася (condition=false через exception).
        assert action_calls[0] == 0
        # loop_passes продовжують зростати навіть при error condition → watcher зупиниться.
        assert watcher.state.loop_passes == 5
        assert watcher.state.errors == 5
        assert watcher.state.stop_reason == "max_iterations"
        assert "condition boom" in watcher.state.last_error

    def test_action_exception_counted_as_error(self):
        time_fn, advance = make_fake_time()
        config = WatcherConfig(name="aerr", poll_interval=0, max_iterations=3)

        def bad_action(_c):
            raise RuntimeError("action boom")

        watcher = Watcher(
            config,
            condition=lambda c: True,
            action=bad_action,
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        assert watcher.state.errors == 3
        assert watcher.state.actions_fired == 0
        assert "action boom" in watcher.state.last_error


# ---------------------------------------------------------------------------
# Budget integration
# ---------------------------------------------------------------------------


class TestBudgetIntegration:
    def test_budget_exhaustion_stops_watcher(self):
        time_fn, advance = make_fake_time()
        config = WatcherConfig(name="b", poll_interval=0, max_iterations=100)
        budget = SessionBudget(
            SessionLimits(
                max_steps=2,
                max_tokens=None,
                max_errors=None,
                max_cost_usd=None,
                max_duration_seconds=None,
            )
        )

        watcher = Watcher(
            config,
            condition=lambda c: True,
            action=lambda c: None,
            budget=budget,
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        # 2 успішні action-и → budget exhausted → stop.
        assert watcher.state.actions_fired == 2
        assert "budget" in watcher.state.stop_reason

    def test_budget_records_action_steps(self):
        time_fn, advance = make_fake_time()
        config = WatcherConfig(name="b2", poll_interval=0, max_iterations=5)
        budget = SessionBudget()

        watcher = Watcher(
            config,
            condition=lambda c: True,
            action=lambda c: None,
            budget=budget,
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        assert budget.usage.steps == 5

    def test_budget_records_errors(self):
        time_fn, advance = make_fake_time()
        config = WatcherConfig(name="b3", poll_interval=0, max_iterations=3)
        budget = SessionBudget()

        def bad_action(_):
            raise RuntimeError("x")

        watcher = Watcher(
            config,
            condition=lambda c: True,
            action=bad_action,
            budget=budget,
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        assert budget.usage.errors == 3


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_writes_jsonl_log(self, tmp_path):
        time_fn, advance = make_fake_time()
        log_path = tmp_path / "w.jsonl"
        config = WatcherConfig(name="log", poll_interval=0, max_iterations=2)

        watcher = Watcher(
            config,
            condition=lambda c: True,
            action=lambda c: {"ok": True},
            log_path=log_path,
            sleep_fn=lambda s: advance(s),
            time_fn=time_fn,
        )
        watcher.start(blocking=True)

        assert log_path.exists()
        lines = [json.loads(l) for l in log_path.read_text().splitlines()]
        events = [e["event"] for e in lines]
        # 2 action + 1 stopped.
        assert events.count("action") == 2
        assert events[-1] == "stopped"


# ---------------------------------------------------------------------------
# Threading (start non-blocking + stop)
# ---------------------------------------------------------------------------


class TestThreading:
    def test_non_blocking_start_and_stop(self):
        """Справжній тред, stop() має коректно завершити loop."""
        import threading as _t
        import time as _time

        config = WatcherConfig(name="t", poll_interval=0.01)
        hits = [0]
        done = _t.Event()

        def action(_c):
            hits[0] += 1
            if hits[0] >= 3:
                done.set()

        watcher = Watcher(config, lambda c: True, action)
        watcher.start()  # non-blocking

        assert done.wait(timeout=2.0), "watcher did not fire 3 times in time"
        watcher.stop(reason="test_done")
        # Після stop watcher має бути running=False.
        _time.sleep(0.05)
        assert watcher.state.running is False

    def test_double_start_raises(self):
        watcher = Watcher(
            WatcherConfig(name="d", poll_interval=0.01, max_iterations=1000),
            lambda c: False,
            lambda c: None,
        )
        watcher.start()
        try:
            with pytest.raises(RuntimeError):
                watcher.start()
        finally:
            watcher.stop(reason="cleanup")


# ---------------------------------------------------------------------------
# WatcherEngine
# ---------------------------------------------------------------------------


class TestEngine:
    def test_register_and_list(self, tmp_path):
        engine = WatcherEngine(logs_dir=tmp_path)
        config = WatcherConfig(name="e1", poll_interval=0, max_iterations=1)
        w = engine.start(config, lambda c: True, lambda c: None, blocking=True)

        states = engine.list_watchers()
        assert len(states) == 1
        assert states[0].watcher_id == w.id
        assert states[0].running is False

    def test_stop_by_id(self, tmp_path):
        engine = WatcherEngine(logs_dir=tmp_path)
        config = WatcherConfig(name="e2", poll_interval=0.01)
        w = engine.start(config, lambda c: False, lambda c: None)
        assert engine.stop(w.id, reason="t") is True
        assert engine.stop("unknown") is False

    def test_stop_all(self, tmp_path):
        engine = WatcherEngine(logs_dir=tmp_path)
        config1 = WatcherConfig(name="a", poll_interval=0.01)
        config2 = WatcherConfig(name="b", poll_interval=0.01)
        engine.start(config1, lambda c: False, lambda c: None)
        engine.start(config2, lambda c: False, lambda c: None)
        engine.stop_all()
        # Обидва watcher-и мають припинити роботу.
        import time as _time
        _time.sleep(0.1)
        for s in engine.list_watchers():
            assert s.running is False


# ---------------------------------------------------------------------------
# Built-in conditions
# ---------------------------------------------------------------------------


class TestConditions:
    def test_counter_reached(self):
        cond = condition_counter_reached(3, counter_key="n")
        assert cond({"n": 2}) is False
        assert cond({"n": 3}) is True
        assert cond({"n": 10}) is True
        assert cond({}) is False

    def test_file_exists(self, tmp_path):
        path = tmp_path / "x"
        cond = condition_file_exists(path)
        assert cond({}) is False
        path.touch()
        assert cond({}) is True
        # Наступні виклики — False (одноразове).
        assert cond({}) is False

    def test_file_changed(self, tmp_path):
        path = tmp_path / "c.txt"
        path.write_text("v1")
        cond = condition_file_changed(path)
        # Стартово — baseline, не тригерить.
        assert cond({}) is False
        # Без змін — теж не тригерить.
        assert cond({}) is False
        # Змінюємо mtime вручну.
        import os as _os
        new_mtime = path.stat().st_mtime + 10
        _os.utime(path, (new_mtime, new_mtime))
        assert cond({}) is True
        # Друга перевірка без нових змін — False.
        assert cond({}) is False

    def test_idle_for(self):
        time_fn, advance = make_fake_time()
        cond = condition_idle_for(5, time_fn=time_fn)
        ctx = {"last_activity_at": 0.0}
        assert cond(ctx) is False
        advance(3)
        assert cond(ctx) is False
        advance(2.1)  # total 5.1
        assert cond(ctx) is True

    def test_idle_without_activity_key(self):
        cond = condition_idle_for(1)
        assert cond({}) is False

    def test_condition_any(self):
        cond = condition_any(
            condition_counter_reached(5, counter_key="a"),
            condition_counter_reached(5, counter_key="b"),
        )
        assert cond({"a": 0, "b": 0}) is False
        assert cond({"a": 5, "b": 0}) is True
        assert cond({"a": 0, "b": 5}) is True

    def test_condition_all(self):
        cond = condition_all(
            condition_counter_reached(5, counter_key="a"),
            condition_counter_reached(5, counter_key="b"),
        )
        assert cond({"a": 5, "b": 0}) is False
        assert cond({"a": 5, "b": 5}) is True
