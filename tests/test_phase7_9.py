"""Тести для Phase 7–9 компонентів.

HTTP-виклики моканні — реальна мережа НЕ зачіпається.
"""
import os
import sys
from typing import Any, Dict, List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Anthropic / Google providers
# ---------------------------------------------------------------------------

from functions.providers_anthropic import AnthropicAdapter  # noqa: E402
from functions.providers_google import GoogleAdapter  # noqa: E402


def test_anthropic_adapter_init():
    adapter = AnthropicAdapter(api_key="test-key")
    assert adapter.name == "anthropic"
    assert adapter.available() is True


def test_anthropic_adapter_no_key():
    adapter = AnthropicAdapter(api_key="")
    assert adapter.available() is False


def test_google_adapter_init():
    adapter = GoogleAdapter(api_key="test-key")
    assert adapter.name == "google"
    assert adapter.available() is True


def test_google_adapter_no_key():
    adapter = GoogleAdapter(api_key="")
    assert adapter.available() is False


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

from functions.logic_orchestrator import Orchestrator, SubTask, OrchestrationResult  # noqa: E402
from functions.logic_provider_registry import ProviderRegistry, SelectionCriteria  # noqa: E402


def test_orchestrator_decompose_single():
    registry = ProviderRegistry()
    orch = Orchestrator(registry)
    tasks = orch.decompose_task("simple task")
    assert len(tasks) == 1
    assert tasks[0] == "simple task"


def test_orchestrator_decompose_multi():
    registry = ProviderRegistry()
    orch = Orchestrator(registry)
    tasks = orch.decompose_task("step 1\nstep 2\nstep 3")
    assert len(tasks) == 3
    assert tasks == ["step 1", "step 2", "step 3"]


# ---------------------------------------------------------------------------
# Task Learner
# ---------------------------------------------------------------------------

from functions.logic_task_learner import (  # noqa: E402
    TaskPattern,
    detect_repeated_pattern,
    suggest_automation,
    create_macro_from_pattern,
    adaptive_click,
)


def test_detect_repeated_pattern_basic():
    history = [
        {"action": "click", "params": {"x": 1}},
        {"action": "click", "params": {"x": 1}},
        {"action": "click", "params": {"x": 1}},
    ]
    pattern = detect_repeated_pattern(history, min_occurrences=3)
    assert pattern is not None
    assert pattern.frequency >= 3


def test_detect_repeated_pattern_none():
    history = [
        {"action": "click"},
        {"action": "type"},
    ]
    assert detect_repeated_pattern(history, min_occurrences=3) is None


def test_suggest_automation():
    pattern = TaskPattern(name="test", steps=[{"action": "a"}, {"action": "b"}], frequency=2)
    text = suggest_automation(pattern)
    assert "test" in text
    assert "2" in text


def test_create_macro_from_pattern():
    pattern = TaskPattern(name="auto", steps=[{"action": "click", "params": {"x": 1}}], frequency=1)
    macro = create_macro_from_pattern(pattern, name="click_macro")
    assert macro.name == "click_macro"
    assert len(macro.steps) == 1


def test_adaptive_click_empty_fallback():
    result = adaptive_click("test", [])
    assert result["success"] is False


def test_adaptive_click_image():
    # Без tools_window_manager click_fn — поверне False
    result = adaptive_click("btn", [("image", "btn.png")])
    assert result["success"] is False
    assert result["attempted"] == 1


# ---------------------------------------------------------------------------
# Web conditions
# ---------------------------------------------------------------------------

from functions.conditions_web import (  # noqa: E402
    condition_url_response_contains,
    condition_url_status_ok,
    condition_chat_idle,
)


def test_condition_url_response_contains_no_requests(monkeypatch):
    monkeypatch.setattr("functions.conditions_web.requests", None)
    assert condition_url_response_contains("http://example.com", "test") is False


def test_condition_url_status_ok_no_requests(monkeypatch):
    monkeypatch.setattr("functions.conditions_web.requests", None)
    assert condition_url_status_ok("http://example.com") is False


def test_condition_chat_idle_no_provider():
    assert condition_chat_idle(None, 1) is False


def test_condition_chat_idle_with_provider():
    class FakeProvider:
        def is_responding(self):
            return False
    assert condition_chat_idle(FakeProvider(), 0) is True


