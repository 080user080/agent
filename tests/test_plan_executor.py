"""Tests for PlanExecutor (S2: GUI ↔ TaskRunner bridge)."""
import threading
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from functions.plan_executor import PlanExecutor, PlanExecutionConfig, PlanExecutionState


# ─── Helpers ──────────────────────────────────────────────────────────────────

class FakeAssistant:
    """Мінімальний stub для VoiceAssistant."""

    def __init__(self, actions: Dict[str, str] = None):
        self._actions = actions or {}
        self.conversation_history = [{"role": "user", "content": "тест"}]
        self.registry = MagicMock()
        self.planner = None

    def execute_action(self, action: str, args: Dict[str, Any]) -> str:
        return self._actions.get(action, f"✅ {action} done")


def _collect_gui(messages: List):
    """Повертає GUI callback, що збирає повідомлення в список."""
    def cb(msg_type, data=None):
        messages.append((msg_type, data))
    return cb


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestPlannerStepsConversion:
    def test_basic_conversion(self):
        steps = [
            {"action": "open_program", "args": {"program_name": "notepad"}, "goal": "open"},
            {"action": "keyboard_type", "args": {"text": "hi"}, "goal": "type"},
        ]
        plan = PlanExecutor.planner_steps_to_task_runner_plan(steps, "test")
        assert plan["name"] == "test"
        assert len(plan["tasks"]) == 2
        assert plan["tasks"][0]["kind"] == "agent_action"
        assert plan["tasks"][1]["params"]["action"] == "keyboard_type"

    def test_empty_plan(self):
        plan = PlanExecutor.planner_steps_to_task_runner_plan([], "empty")
        assert plan["tasks"] == []


class TestExecutePlan:
    def test_successful_execution(self):
        msgs = []
        assistant = FakeAssistant({"step1": "✅ ok", "step2": "✅ ok"})
        executor = PlanExecutor(assistant, gui_callback=_collect_gui(msgs))

        steps = [
            {"action": "step1", "args": {}, "goal": "first"},
            {"action": "step2", "args": {}, "goal": "second"},
        ]
        result = executor.execute_plan(steps, "test task")

        assert result["ok"] is True
        assert result["stats"]["ok"] == 2
        assert result["stats"]["error"] == 0

        # GUI messages include plan_started, step_updates, plan_finished
        msg_types = [m[0] for m in msgs]
        assert "execution_started" in msg_types
        assert "plan_started" in msg_types
        assert "plan_finished" in msg_types
        assert "execution_finished" in msg_types

    def test_error_step(self):
        msgs = []
        assistant = FakeAssistant({"ok_step": "✅ ok", "bad_step": "❌ failed"})
        executor = PlanExecutor(assistant, gui_callback=_collect_gui(msgs))

        steps = [
            {"action": "ok_step", "args": {}, "goal": "works"},
            {"action": "bad_step", "args": {}, "goal": "fails"},
        ]
        result = executor.execute_plan(steps, "test")

        assert result["ok"] is False
        assert result["stats"]["ok"] == 1
        assert result["stats"]["error"] == 1

    def test_stop_requested(self):
        """Stop mid-execution via a slow action that triggers stop."""
        msgs = []
        call_count = [0]

        class StopAssistant(FakeAssistant):
            def __init__(self, executor_ref):
                super().__init__()
                self._executor_ref = executor_ref

            def execute_action(self, action, args):
                call_count[0] += 1
                if call_count[0] >= 2:
                    # Після першого кроку — стоп
                    self._executor_ref[0].request_stop()
                return f"✅ {action} done"

        executor_ref = [None]
        assistant = StopAssistant(executor_ref)
        executor = PlanExecutor(assistant, gui_callback=_collect_gui(msgs))
        executor_ref[0] = executor

        steps = [
            {"action": "step1", "args": {}, "goal": "first"},
            {"action": "step2", "args": {}, "goal": "second"},
            {"action": "step3", "args": {}, "goal": "third"},
        ]
        result = executor.execute_plan(steps, "test")

        assert result["stopped"] is True
        # step1 ok, step2 triggers stop (still executes), step3 skipped
        assert result["stats"]["ok"] >= 1
        assert result["stats"]["skipped"] >= 1

    def test_duplicate_execution_blocked(self):
        assistant = FakeAssistant()
        executor = PlanExecutor(assistant)

        # Simulate running state
        executor.state.is_running = True
        result = executor.execute_plan([{"action": "x", "args": {}}], "test")
        assert result["ok"] is False
        assert "вже виконується" in result["error"]


class TestExecutionState:
    def test_initial_state(self):
        state = PlanExecutionState()
        assert state.is_running is False
        assert state.stop_requested is False
        assert state.current_step == 0


class TestConfig:
    def test_defaults(self):
        cfg = PlanExecutionConfig()
        assert cfg.max_steps == 50
        assert cfg.max_duration_seconds == 3600.0
        assert cfg.max_errors == 5
