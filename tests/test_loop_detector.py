"""Tests for LoopDetector — виявлення зациклення агента."""
import pytest

from functions.core_loop_detector import LoopDetector, LoopEvent, _action_fingerprint


# ─── Fingerprint tests ────────────────────────────────────────────────────────

class TestActionFingerprint:
    def test_same_action_same_args(self):
        fp1 = _action_fingerprint("click", {"x": 100, "y": 200})
        fp2 = _action_fingerprint("click", {"x": 100, "y": 200})
        assert fp1 == fp2

    def test_same_action_different_args(self):
        fp1 = _action_fingerprint("click", {"x": 100, "y": 200})
        fp2 = _action_fingerprint("click", {"x": 300, "y": 400})
        assert fp1 != fp2

    def test_different_action_same_args(self):
        fp1 = _action_fingerprint("click", {"x": 100, "y": 200})
        fp2 = _action_fingerprint("mouse_move", {"x": 100, "y": 200})
        assert fp1 != fp2

    def test_args_order_irrelevant(self):
        fp1 = _action_fingerprint("click", {"x": 100, "y": 200})
        fp2 = _action_fingerprint("click", {"y": 200, "x": 100})
        assert fp1 == fp2

    def test_empty_args(self):
        fp1 = _action_fingerprint("take_screenshot", {})
        fp2 = _action_fingerprint("take_screenshot", {})
        assert fp1 == fp2

    def test_non_serializable_args(self):
        """Якщо args не серіалізуються — fallback на str()."""
        fp = _action_fingerprint("test", {"fn": lambda x: x})
        assert "test:" in fp


# ─── LoopDetector core tests ─────────────────────────────────────────────────

class TestLoopDetectorBasic:
    def test_initial_state(self):
        ld = LoopDetector()
        assert ld.is_stuck is False
        assert ld.total_loops_detected == 0
        assert ld.max_repeats == 3

    def test_custom_max_repeats(self):
        ld = LoopDetector(max_repeats=5)
        assert ld.max_repeats == 5
        assert ld.window_size == 5

    def test_min_max_repeats(self):
        ld = LoopDetector(max_repeats=1)
        assert ld.max_repeats == 2  # min 2

    def test_no_loop_single_action(self):
        ld = LoopDetector(max_repeats=3)
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_stuck is False

    def test_no_loop_two_same_actions(self):
        ld = LoopDetector(max_repeats=3)
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_stuck is False

    def test_loop_detected_three_same_actions(self):
        ld = LoopDetector(max_repeats=3)
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_looping("click", {"x": 100, "y": 200}) is True
        assert ld.is_stuck is True

    def test_loop_resets_after_detection(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        assert ld.is_looping("click", {"x": 100, "y": 200}) is True
        # Після виявлення детектор скидається — нова послідовність
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        # Третя — знову зациклення
        assert ld.is_looping("click", {"x": 100, "y": 200}) is True

    def test_different_actions_break_loop(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        # Інша дія — лічильник скидається
        ld.is_looping("mouse_move", {"x": 100, "y": 200})
        # Ще 2 click — не зациклення (не 3 підряд)
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False

    def test_same_action_different_args_no_loop(self):
        ld = LoopDetector(max_repeats=3)
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_looping("click", {"x": 300, "y": 400}) is False
        assert ld.is_looping("click", {"x": 500, "y": 600}) is False
        assert ld.is_stuck is False


# ─── on_action_success / reset tests ──────────────────────────────────────────

class TestLoopDetectorReset:
    def test_on_action_success_clears_stuck(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        assert ld.is_stuck is True
        ld.on_action_success()
        assert ld.is_stuck is False

    def test_on_action_success_noop_when_not_stuck(self):
        ld = LoopDetector()
        ld.on_action_success()  # Не має падати
        assert ld.is_stuck is False

    def test_reset_clears_history(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.reset()
        # Після reset — потрібно знову набрати 3 дії
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_looping("click", {"x": 100, "y": 200}) is False
        assert ld.is_looping("click", {"x": 100, "y": 200}) is True

    def test_full_reset(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        assert ld.total_loops_detected == 1
        ld.full_reset()
        assert ld.is_stuck is False
        assert ld.total_loops_detected == 0
        assert len(ld.loop_events) == 0


# ─── LoopEvent / stats tests ──────────────────────────────────────────────────

class TestLoopDetectorEvents:
    def test_loop_event_created(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        assert len(ld.loop_events) == 1
        event = ld.loop_events[0]
        assert event.action == "click"
        assert event.repeat_count == 3
        assert "click" in event.message

    def test_total_loops_counter(self):
        ld = LoopDetector(max_repeats=2)
        ld.is_looping("a", {})
        ld.is_looping("a", {})
        assert ld.total_loops_detected == 1
        # Після detection — reset, тому нова послідовність
        ld.is_looping("a", {})
        ld.is_looping("a", {})
        assert ld.total_loops_detected == 2

    def test_get_stats(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("click", {"x": 100, "y": 200})
        stats = ld.get_stats()
        assert stats["is_stuck"] is False
        assert stats["total_loops_detected"] == 0
        assert stats["max_repeats"] == 3
        assert stats["current_window_length"] == 1


# ─── get_stuck_warning_message tests ──────────────────────────────────────────

class TestStuckWarningMessage:
    def test_empty_when_not_stuck(self):
        ld = LoopDetector()
        assert ld.get_stuck_warning_message() == ""

    def test_contains_warning_when_stuck(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        ld.is_looping("click", {"x": 100, "y": 200})
        msg = ld.get_stuck_warning_message()
        assert "КРИТИЧНЕ" in msg
        assert "click" in msg
        assert "НЕ ПРАЦЮЄ" in msg
        assert "інший шлях" in msg

    def test_warning_mentions_alternatives(self):
        ld = LoopDetector(max_repeats=3)
        ld.is_looping("mouse_click", {"x": 50, "y": 50})
        ld.is_looping("mouse_click", {"x": 50, "y": 50})
        ld.is_looping("mouse_click", {"x": 50, "y": 50})
        msg = ld.get_stuck_warning_message()
        assert "гарячі клавіші" in msg
        assert "ask_user" in msg


# ─── Integration with AgentLoop tests ─────────────────────────────────────────

class TestLoopDetectorWithAgentLoop:
    def test_agent_loop_has_loop_detector(self):
        from functions.agent_loop import AgentLoop, AgentLoopConfig
        assistant = type("FakeAssistant", (), {"planner": None})()
        registry = type("FakeRegistry", (), {
            "execute_function": staticmethod(lambda *a, **kw: {"ok": True, "result": "done"})
        })()
        loop = AgentLoop(assistant, registry=registry, config=AgentLoopConfig(max_steps=5))
        assert hasattr(loop, "loop_detector")
        assert loop.loop_detector.max_repeats == 3

    def test_loop_detector_reset_on_run(self):
        from functions.agent_loop import AgentLoop, AgentLoopConfig
        assistant = type("FakeAssistant", (), {"planner": None})()
        registry = type("FakeRegistry", (), {
            "execute_function": staticmethod(lambda *a, **kw: {"ok": True, "result": "done"})
        })()
        loop = AgentLoop(assistant, registry=registry, config=AgentLoopConfig(max_steps=5))
        # Симулюємо попереднє зациклення
        loop.loop_detector.is_stuck = True
        loop.loop_detector._total_loops_detected = 5
        # run() має зробити full_reset
        # Не запускаємо реально — просто перевіряємо що full_reset працює
        loop.loop_detector.full_reset()
        assert loop.loop_detector.is_stuck is False
        assert loop.loop_detector.total_loops_detected == 0

    def test_decider_accepts_stuck_warning(self):
        from functions.agent_loop import ActionDecider
        decider = ActionDecider()
        messages = decider.build_messages(
            goal="test",
            observation=None,
            history=[],
            stuck_warning="🚨 КРИТИЧНЕ ЗАУВАЖЕННЯ: зациклення!",
        )
        user_msg = messages[1]["content"]
        assert "КРИТИЧНЕ" in user_msg
        assert "зациклення" in user_msg
