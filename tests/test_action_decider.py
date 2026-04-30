"""Тести для ActionDecider та logic_agent_tools_schema."""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from functions.agent_loop import (
    ActionDecider,
    AgentAction,
    AgentLoop,
    AgentLoopConfig,
    AgentState,
    Observation,
    build_default_decider,
)
from functions.logic_agent_tools_schema import (
    AGENT_TOOLS,
    ALL_AGENT_TOOLS,
    BROWSER_TOOLS,
    SPECIAL_TOOLS,
    TOOL_NAME_ALIASES,
    UIA_TOOLS,
    VISION_TOOLS,
    get_tools_for_capabilities,
)
from functions.logic_llm_tools import ChatToolsResponse, ToolCall


# --------------------------------------------------------------------------- #
# logic_agent_tools_schema                                                     #
# --------------------------------------------------------------------------- #


class TestToolsSchema:
    def test_agent_tools_have_required_actions(self):
        names = {t["function"]["name"] for t in AGENT_TOOLS}
        assert "mouse_click" in names
        assert "keyboard_type" in names
        assert "keyboard_press" in names
        assert "take_screenshot" in names
        assert "ocr_screen" in names
        assert "click_text" in names
        assert "open_program" in names
        assert "wait_for_text" in names
        assert "done" in names
        assert "ask_user" in names

    def test_all_tools_have_valid_openai_format(self):
        for tool in ALL_AGENT_TOOLS:
            assert tool["type"] == "function"
            fn = tool["function"]
            assert "name" in fn and isinstance(fn["name"], str) and fn["name"]
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"
            assert "properties" in fn["parameters"]

    def test_special_tools_present(self):
        names = {t["function"]["name"] for t in AGENT_TOOLS}
        for special in SPECIAL_TOOLS:
            assert special in names

    def test_tool_name_aliases_cover_known_actions(self):
        # alias має існувати для дій, що відрізняються від registry-імен
        assert "describe_screen" in TOOL_NAME_ALIASES
        assert "uia_click_by_name" in TOOL_NAME_ALIASES
        assert "browser_open_url" in TOOL_NAME_ALIASES

    def test_get_tools_for_capabilities_default(self):
        tools = get_tools_for_capabilities()
        assert len(tools) == len(AGENT_TOOLS)

    def test_get_tools_for_capabilities_with_vision(self):
        tools = get_tools_for_capabilities(enable_vision=True)
        assert len(tools) == len(AGENT_TOOLS) + len(VISION_TOOLS)

    def test_get_tools_for_capabilities_full(self):
        tools = get_tools_for_capabilities(
            enable_vision=True, enable_uia=True, enable_browser=True
        )
        expected = len(AGENT_TOOLS) + len(VISION_TOOLS) + len(UIA_TOOLS) + len(BROWSER_TOOLS)
        assert len(tools) == expected
        assert len(tools) == len(ALL_AGENT_TOOLS)


# --------------------------------------------------------------------------- #
# ActionDecider                                                                #
# --------------------------------------------------------------------------- #


def _make_decider(tools: List[Dict[str, Any]] = None, llm_fn=None) -> ActionDecider:
    return ActionDecider(
        ask_llm_with_tools_fn=llm_fn,
        tools_schema=tools or AGENT_TOOLS,
        tool_aliases=dict(TOOL_NAME_ALIASES),
    )


class TestActionDeciderAvailability:
    def test_unavailable_without_llm_fn(self):
        d = ActionDecider(ask_llm_with_tools_fn=None, tools_schema=AGENT_TOOLS)
        assert not d.is_available

    def test_unavailable_without_tools(self):
        d = ActionDecider(ask_llm_with_tools_fn=lambda **k: None, tools_schema=[])
        assert not d.is_available

    def test_available_when_both_provided(self):
        d = _make_decider(llm_fn=lambda **k: None)
        assert d.is_available


class TestActionDeciderDecide:
    def test_decide_returns_noop_when_unavailable(self):
        d = ActionDecider(ask_llm_with_tools_fn=None, tools_schema=AGENT_TOOLS)
        action = d.decide(goal="test", observation=None, history=[])
        assert action.name == "noop"

    def test_decide_parses_tool_call(self):
        response = ChatToolsResponse(
            tool_calls=[ToolCall(name="keyboard_type", arguments={"text": "hi"}, id="c1")],
            content="плану ввести 'hi'",
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="ввести hi", observation=None, history=[])
        assert action.name == "keyboard_type"
        assert action.arguments == {"text": "hi"}
        assert action.tool_call_id == "c1"

    def test_decide_returns_done_when_no_tool_calls(self):
        response = ChatToolsResponse(content="Готово!", tool_calls=[])
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="test", observation=None, history=[])
        assert action.name == "done"
        assert "Готово" in action.arguments.get("summary", "")

    def test_decide_handles_llm_error(self):
        response = ChatToolsResponse(error="network: connection refused")
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="test", observation=None, history=[])
        assert action.name == "noop"
        assert "network" in action.reasoning

    def test_decide_handles_llm_exception(self):
        llm_fn = MagicMock(side_effect=RuntimeError("boom"))
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="test", observation=None, history=[])
        assert action.name == "noop"
        assert "boom" in action.reasoning

    def test_resolve_alias(self):
        d = _make_decider(llm_fn=lambda **k: None)
        # describe_screen → vision_describe_screen
        assert d.resolve_alias("describe_screen") == "vision_describe_screen"
        # mouse_click — без alias
        assert d.resolve_alias("mouse_click") == "mouse_click"

    def test_build_messages_includes_observation_and_history(self):
        d = _make_decider(llm_fn=lambda **k: None)
        obs = Observation(
            ocr_text="Hello world",
            active_window_title="Notepad",
            ui_elements=[{"type": "button", "text": "Save", "x": 10, "y": 20}],
        )
        history = [
            {"action": "mouse_click", "args": {"x": 1, "y": 2},
             "act_result": {"ok": True}, "check_result": {"detail": "OK"}},
        ]
        msgs = d.build_messages("збережи файл", obs, history)
        assert msgs[0]["role"] == "system"
        user = msgs[1]["content"]
        assert "збережи файл" in user
        assert "Notepad" in user
        assert "Hello world" in user
        assert "Save" in user
        assert "mouse_click" in user

    def test_replan_uses_warning_instructions(self):
        captured = {}

        def llm_fn(**kwargs):
            captured["messages"] = kwargs.get("messages")
            return ChatToolsResponse(
                tool_calls=[ToolCall(name="take_screenshot", arguments={})]
            )

        d = _make_decider(llm_fn=llm_fn)
        action = d.replan(goal="t", observation=None, history=[], consecutive_failures=3)
        assert action.name == "take_screenshot"
        assert "(replan)" in action.reasoning or action.reasoning == "(replan) "
        assert any("3 спроби" in m["content"] for m in captured["messages"])


# --------------------------------------------------------------------------- #
# AgentLoop integration with decider                                            #
# --------------------------------------------------------------------------- #


class _FakeRegistry:
    def __init__(self):
        self.calls = []

    def execute_function(self, name: str, args: Dict[str, Any]):
        self.calls.append((name, dict(args)))
        return {"ok": True, "result": f"executed {name}"}


class _FakeAssistant:
    pass


class TestAgentLoopWithDecider:
    def test_decider_priority_over_compiled_plan(self):
        decider_response = ChatToolsResponse(
            tool_calls=[ToolCall(name="keyboard_type", arguments={"text": "hi"})]
        )
        llm_fn = MagicMock(return_value=decider_response)
        decider = _make_decider(llm_fn=llm_fn)

        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=_FakeRegistry(),
            config=AgentLoopConfig(enable_llm_decider=True, enable_ocr=False),
            decider=decider,
        )
        # Навіть якщо є CompiledPlan — decider мав би перемогти
        plan = loop.plan("test", Observation(), AgentState())
        assert plan["action"] == "keyboard_type"
        assert plan["from_decider"] is True

    def test_decider_done_terminates_loop(self):
        response = ChatToolsResponse(
            tool_calls=[ToolCall(name="done", arguments={"summary": "all good", "success": True})]
        )
        decider = _make_decider(llm_fn=lambda **k: response)
        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=_FakeRegistry(),
            config=AgentLoopConfig(enable_llm_decider=True, enable_ocr=False, max_steps=5),
            decider=decider,
        )
        plan = loop.plan("test", Observation(), AgentState())
        assert plan["done"] is True
        assert plan["summary"] == "all good"
        assert plan["success"] is True

    def test_decider_noop_falls_through(self):
        # Decider returns noop → fallback на наступні пріоритети
        decider = _make_decider(llm_fn=lambda **k: ChatToolsResponse(error="x"))
        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=_FakeRegistry(),
            config=AgentLoopConfig(enable_llm_decider=True, enable_ocr=False),
            decider=decider,
        )
        plan = loop.plan("test", Observation(), AgentState())
        # Fallback path → noop/done
        assert plan["action"] == "noop"
        assert plan["done"] is True

    def test_check_with_act_result_failure(self):
        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=_FakeRegistry(),
            config=AgentLoopConfig(enable_ocr=False),
        )
        loop._prev_screen_hash = "x"
        result = loop.check(
            "mouse_click",
            Observation(screen_hash="x"),
            act_result={"ok": False, "error": "click failed"},
        )
        assert result["success"] is False
        assert result["retry"] is True
        assert "click failed" in result["detail"]

    def test_check_non_visual_action_does_not_fail_on_no_screen_change(self):
        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=_FakeRegistry(),
            config=AgentLoopConfig(enable_ocr=False),
        )
        loop._prev_screen_hash = "same"
        result = loop.check(
            "take_screenshot",
            Observation(screen_hash="same"),
            act_result={"ok": True},
        )
        assert result["success"] is True

    def test_consecutive_failures_increment(self):
        decider = _make_decider(
            llm_fn=lambda **k: ChatToolsResponse(
                tool_calls=[ToolCall(name="mouse_click", arguments={"x": 0, "y": 0})]
            )
        )

        class FailingRegistry:
            def execute_function(self, name, args):
                return {"ok": False, "error": "no"}

        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=FailingRegistry(),
            config=AgentLoopConfig(
                enable_llm_decider=True, enable_ocr=False, max_steps=3,
            ),
            decider=decider,
        )
        # Виконати 2 кроки вручну
        state = AgentState()
        loop._execute_single_step("test", state, 0.0)
        assert state.consecutive_failures >= 1


# --------------------------------------------------------------------------- #
# build_default_decider                                                        #
# --------------------------------------------------------------------------- #


class TestBuildDefaultDecider:
    def test_returns_decider_with_tools(self):
        decider = build_default_decider()
        # У нашому проекті logic_llm_tools та tools_schema імпортуються —
        # отже decider має бути не None
        assert decider is not None
        assert decider.is_available  # llm_fn + tools є
        assert decider.resolve_alias("describe_screen") == "vision_describe_screen"

    def test_with_browser_capability(self):
        decider = build_default_decider(enable_browser=True)
        assert decider is not None
        # Browser-tools мають бути в tools_schema (перевірка opaque, без api)
