"""Тести для functions/core_session_budget.py."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.core_session_budget import (  # noqa: E402
    BudgetCheckResult,
    SessionBudget,
    SessionLimits,
    SessionUsage,
)


# ---------------------------------------------------------------------------
# Defaults / basics
# ---------------------------------------------------------------------------


class TestBasics:
    def test_default_limits(self):
        budget = SessionBudget()
        assert budget.limits.max_steps == 500
        assert budget.limits.max_tokens == 500_000
        assert budget.limits.max_duration_seconds == 6 * 60 * 60

    def test_fresh_budget_allows_work(self):
        budget = SessionBudget()
        result = budget.check()
        assert result.ok is True
        assert budget.is_exhausted() is False

    def test_snapshot_shape(self):
        budget = SessionBudget()
        budget.record_step(3)
        budget.record_tokens(100)
        budget.record_cost(0.01)
        snap = budget.snapshot()
        assert snap["usage"]["steps"] == 3
        assert snap["usage"]["tokens"] == 100
        assert snap["usage"]["cost_usd"] == pytest.approx(0.01)
        assert "limits" in snap


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


class TestRecording:
    def test_record_step_increments(self):
        budget = SessionBudget()
        budget.record_step()
        budget.record_step(5)
        assert budget.usage.steps == 6

    def test_record_tokens_negative_rejected(self):
        budget = SessionBudget()
        with pytest.raises(ValueError):
            budget.record_tokens(-1)

    def test_record_cost_negative_rejected(self):
        budget = SessionBudget()
        with pytest.raises(ValueError):
            budget.record_cost(-0.5)

    def test_record_error_increments(self):
        budget = SessionBudget()
        budget.record_error()
        budget.record_error(2)
        assert budget.usage.errors == 3

    def test_reset_clears_usage(self):
        budget = SessionBudget()
        budget.record_step(10)
        budget.record_tokens(1000)
        budget.record_error(5)
        budget.stop("test")
        budget.reset()

        assert budget.usage.steps == 0
        assert budget.usage.tokens == 0
        assert budget.usage.errors == 0
        assert budget.check().ok is True


# ---------------------------------------------------------------------------
# Limits enforcement
# ---------------------------------------------------------------------------


class TestLimitsEnforcement:
    def test_steps_limit_enforced(self):
        budget = SessionBudget(SessionLimits(max_steps=3))
        budget.record_step(3)
        result = budget.check()
        assert result.ok is False
        assert result.metric == "steps"
        assert result.limit == 3
        assert result.current == 3

    def test_tokens_limit_enforced(self):
        budget = SessionBudget(SessionLimits(max_tokens=100, max_steps=None))
        budget.record_tokens(100)
        result = budget.check()
        assert result.ok is False
        assert result.metric == "tokens"

    def test_errors_limit_enforced(self):
        budget = SessionBudget(SessionLimits(max_errors=2, max_steps=None))
        budget.record_error(2)
        result = budget.check()
        assert result.ok is False
        assert result.metric == "errors"

    def test_cost_limit_enforced(self):
        budget = SessionBudget(SessionLimits(max_cost_usd=1.0, max_steps=None))
        budget.record_cost(1.0)
        result = budget.check()
        assert result.ok is False
        assert result.metric == "cost_usd"

    def test_duration_limit_enforced(self, monkeypatch):
        """Використовуємо ручний monotonic, щоб не чекати реальний час."""
        budget = SessionBudget(
            SessionLimits(
                max_steps=None,
                max_tokens=None,
                max_cost_usd=None,
                max_errors=None,
                max_duration_seconds=10,
            )
        )
        # Симулюємо, що пройшло 11 секунд.
        budget.usage.started_at = budget.usage.started_at - 11
        result = budget.check()
        assert result.ok is False
        assert result.metric == "duration_seconds"

    def test_none_limit_means_unlimited(self):
        budget = SessionBudget(SessionLimits(max_steps=None, max_tokens=None))
        budget.record_step(1_000_000)
        budget.record_tokens(10_000_000)
        # Лишилися limits на errors/cost/duration, тож може бути ok (пройшло 0с).
        result = budget.check()
        assert result.ok is True

    def test_first_exceeded_metric_returned(self):
        """При кількох пробитих лімітах повертається той, що першим у check()."""
        budget = SessionBudget(
            SessionLimits(max_steps=1, max_tokens=1, max_errors=None, max_cost_usd=None)
        )
        budget.record_step(5)
        budget.record_tokens(5)
        result = budget.check()
        assert result.ok is False
        assert result.metric == "steps"


# ---------------------------------------------------------------------------
# Kill-switches
# ---------------------------------------------------------------------------


class TestKillSwitches:
    def test_manual_stop(self):
        budget = SessionBudget()
        assert budget.check().ok is True
        budget.stop("user_clicked_stop")
        result = budget.check()
        assert result.ok is False
        assert "user_clicked_stop" in result.reason
        assert result.metric == "external"

    def test_stop_file(self, tmp_path):
        marker = tmp_path / "stop"
        budget = SessionBudget(stop_file=marker)
        assert budget.check().ok is True
        marker.touch()
        result = budget.check()
        assert result.ok is False
        assert "stop_file" in result.reason

    def test_kill_switch_callable(self):
        flag = [False]
        budget = SessionBudget(kill_switch=lambda: flag[0])
        assert budget.check().ok is True
        flag[0] = True
        result = budget.check()
        assert result.ok is False
        assert result.reason == "kill_switch"

    def test_kill_switch_exception_still_stops(self):
        def bad_kill():
            raise RuntimeError("boom")

        budget = SessionBudget(kill_switch=bad_kill)
        result = budget.check()
        assert result.ok is False
        assert "kill_switch_error" in result.reason


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_session_usage_duration_nonneg(self):
        usage = SessionUsage()
        assert usage.duration_seconds >= 0

    def test_budget_check_result_as_dict(self):
        r = BudgetCheckResult(ok=False, reason="r", metric="m", limit=1, current=2)
        d = r.as_dict()
        assert d["ok"] is False
        assert d["metric"] == "m"
        assert d["limit"] == 1
