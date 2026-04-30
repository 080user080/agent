"""Tests for AgentLoop (Phase 12.1: observe → plan → act → check)."""
from unittest.mock import MagicMock

import pytest

from functions.agent_loop import AgentLoop, AgentLoopConfig, AgentState, Observation


# ─── Helpers ──────────────────────────────────────────────────────────────────

class FakeAssistant:
    """Мінімальний stub для VoiceAssistant."""
    def __init__(self):
        self.planner = None


class FakeRegistry:
    """Мінімальний stub для FunctionRegistry."""
    def __init__(self, actions=None):
        self.actions = actions or {}

    def execute_function(self, action, args):
        if action in self.actions:
            return self.actions[action](args)
        return {"ok": True, "result": f"{action} done"}


def _collect_gui(messages):
    """Повертає GUI callback, що збирає повідомлення в список."""
    def cb(msg_type, data=None):
        messages.append((msg_type, data))
    return cb


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestObservation:
    def test_initial_state(self):
        obs = Observation()
        assert obs.screenshot_path == ""
        assert obs.ocr_text == ""
        assert obs.screen_hash == ""
        assert obs.timestamp == 0.0

    def test_with_data(self):
        obs = Observation(
            screenshot_path="test.png",
            ocr_text="hello",
            screen_hash="abc123",
            timestamp=123.45,
        )
        assert obs.screenshot_path == "test.png"
        assert obs.ocr_text == "hello"


class TestAgentState:
    def test_initial_state(self):
        state = AgentState()
        assert state.step == 0
        assert state.done is False
        assert state.success is False
        assert state.last_action is None


class TestAgentLoopConfig:
    def test_defaults(self):
        cfg = AgentLoopConfig()
        assert cfg.max_steps == 50
        assert cfg.max_duration_seconds == 3600.0
        assert cfg.screen_diff_threshold == 0.01
        assert cfg.enable_ocr is True
        assert cfg.enable_ui_a is False


class TestAgentLoopCheck:
    def test_check_first_iteration(self):
        assistant = FakeAssistant()
        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry)

        obs = Observation(screen_hash="abc123")
        result = loop.check("open_program", obs)

        # Перша ітерація — вважаємо OK
        assert result["success"] is True
        assert "Перша ітерація" in result["detail"]

    def test_check_screen_changed(self):
        assistant = FakeAssistant()
        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry)

        # Встановлюємо попередній хеш
        loop._prev_screen_hash = "old_hash"

        obs = Observation(screen_hash="new_hash")
        result = loop.check("open_program", obs)

        assert result["success"] is True
        assert result["screen_changed"] is True
        assert result["retry"] is False

    def test_check_screen_unchanged(self):
        assistant = FakeAssistant()
        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry)

        loop._prev_screen_hash = "same_hash"
        obs = Observation(screen_hash="same_hash")
        result = loop.check("open_program", obs)

        assert result["success"] is False
        assert result["screen_changed"] is False
        assert result["retry"] is True
        assert "не змінився" in result["detail"]


class TestAgentLoopPlan:
    def test_plan_first_step(self):
        assistant = FakeAssistant()
        assistant.planner = MagicMock()
        assistant.planner.create_plan.return_value = [
            {"action": "step1", "args": {}, "goal": "first"},
            {"action": "step2", "args": {}, "goal": "second"},
        ]

        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry)

        state = AgentState()
        obs = Observation()
        plan = loop.plan("test task", obs, state)

        assert plan["action"] == "step1"
        assert plan["done"] is False
        assert plan["step_index"] == 0
        assert plan["total_steps"] == 2

    def test_plan_no_planner_fallback(self):
        assistant = FakeAssistant()  # без planner
        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry)

        state = AgentState()
        obs = Observation()
        plan = loop.plan("test task", obs, state)

        # Fallback до noop
        assert plan["action"] == "noop"
        assert plan["done"] is True


class TestAgentLoopAct:
    def test_act_noop(self):
        assistant = FakeAssistant()
        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry)

        plan = {"action": "noop", "args": {}}
        result = loop.act(plan)

        assert result["ok"] is True
        assert result["result"] == "noop"

    def test_act_via_registry(self):
        assistant = FakeAssistant()
        registry = FakeRegistry({
            "test_action": lambda args: {"ok": True, "result": "test done"},
        })
        loop = AgentLoop(assistant, registry)

        plan = {"action": "test_action", "args": {"x": 1}}
        result = loop.act(plan)

        assert result["ok"] is True
        assert result["result"] == "test done"

    def test_act_error(self):
        assistant = FakeAssistant()
        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry)

        plan = {"action": "bad_action", "args": {}}
        result = loop.act(plan)

        # Registry повертає fallback result
        assert result["ok"] is True


class TestAgentLoopRun:
    def test_run_no_planner(self):
        """Тест запуску без planner — має завершити з done=True без кроків."""
        assistant = FakeAssistant()  # без planner
        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry, config=AgentLoopConfig(max_steps=5))

        result = loop.run("test task")

        # Повинен завершитися з done=True (планер відсутній) без жодного кроку
        assert result["ok"] is True  # success=True бо done=True
        assert result["steps"] == 0  # 0 кроків бо plan() відразу каже done

    def test_run_with_planner_mock(self):
        """Тест з mock planner що повертає план."""
        assistant = FakeAssistant()
        assistant.planner = MagicMock()
        assistant.planner.create_plan.return_value = [
            {"action": "noop", "args": {}, "goal": "done"},
        ]

        registry = FakeRegistry()
        loop = AgentLoop(assistant, registry, config=AgentLoopConfig(max_steps=5))

        result = loop.run("test task")

        assert result["steps"] >= 1
        assert "duration" in result
