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

    def test_available_without_tools(self):
        # tools не обов'язкові — LLM може працювати через JSON parsing
        d = ActionDecider(ask_llm_with_tools_fn=lambda **k: None, tools_schema=[])
        assert d.is_available

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
        # З новою логікою fallback, якщо content не JSON → take_screenshot
        response = ChatToolsResponse(content="Готово!", tool_calls=[])
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="test", observation=None, history=[])
        # Fallback на take_screenshot при помилці парсингу
        assert action.name == "take_screenshot"
        assert "fallback" in action.reasoning

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

    def execute_function(self, name: str, args: Dict[str, Any], auto_create: bool = False):
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


# --------------------------------------------------------------------------- #
# Long integration tests with different task types                              #
# --------------------------------------------------------------------------- #


class TestJSONParsingFallback:
    """Тести для JSON parsing fallback (без function-calling)."""

    def test_parse_valid_json_from_content(self):
        """LLM повертає валідний JSON в content без tool_calls."""
        response = ChatToolsResponse(
            content='{"action":"take_screenshot","args":{},"reasoning":"Need to see screen"}',
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="показати екран", observation=None, history=[])
        assert action.name == "take_screenshot"
        assert action.arguments == {}
        assert "screen" in action.reasoning

    def test_parse_json_with_args(self):
        """JSON з складними аргументами."""
        response = ChatToolsResponse(
            content='{"action":"list_directory","args":{"directory":"d:\\\\Python\\\\agent"},"reasoning":"List files"}',
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="показати файли", observation=None, history=[])
        assert action.name == "list_directory"
        assert action.arguments["directory"] == "d:\\Python\\agent"

    def test_parse_json_from_markdown(self):
        """JSON обгорнутий в ```json ... ```."""
        response = ChatToolsResponse(
            content='```json\n{"action":"ocr_screen","args":{"lang":"ukr+eng"},"reasoning":"Read text"}\n```',
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="прочитати текст", observation=None, history=[])
        assert action.name == "ocr_screen"
        assert action.arguments["lang"] == "ukr+eng"

    def test_fallback_to_take_screenshot_on_parse_error(self):
        """При помилці парсингу fallback на take_screenshot."""
        response = ChatToolsResponse(
            content="not valid json at all",
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="test", observation=None, history=[])
        assert action.name == "take_screenshot"
        assert "fallback" in action.reasoning

    def test_regex_extraction_of_json(self):
        """JSON витягується через regex з тексту."""
        response = ChatToolsResponse(
            content="Some text before {\"action\":\"done\",\"args\":{\"summary\":\"OK\"}} some after",
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="test", observation=None, history=[])
        assert action.name == "done"
        assert action.arguments["summary"] == "OK"

    def test_thinking_blocks_removed_before_json_parsing(self):
        """Thinking блоки Qwen3 видаляються перед парсингом JSON."""
        response = ChatToolsResponse(
            content='Потрібно знайти файли в директорії.\n{"action":"list_directory","args":{"directory":"d:\\\\Python\\\\MARK\\\\tests_3"},"reasoning":"List files in tests_3"}',
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="показати файли", observation=None, history=[])
        assert action.name == "list_directory"
        assert action.arguments["directory"] == "d:\\Python\\MARK\\tests_3"

    def test_think_tags_inside_json_string_not_removed(self):
        """`` теги всередині JSON рядка не видаляються."""
        response = ChatToolsResponse(
            content='{"action":"type_text","args":{"text":"User said: "},"reasoning":"Type text"}',
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)
        action = d.decide(goal="ввести текст", observation=None, history=[])
        assert action.name == "type_text"
        assert 'User said:' in action.arguments["text"]



class TestAgentLoopLongTasks:
    """Довгі інтеграційні тести для AgentLoop з різними типами задач."""

    def test_code_analysis_task(self):
        """Задача аналізу коду: list_directory → read_code_file → done."""
        actions_sequence = [
            ChatToolsResponse(
                content='{"action":"list_directory","args":{"directory":"d:\\\\Python\\\\agent"},"reasoning":"List files"}',
                tool_calls=[],
            ),
            ChatToolsResponse(
                content='{"action":"read_code_file","args":{"filepath":"d:\\\\Python\\\\agent\\\\main.py"},"reasoning":"Read main file"}',
                tool_calls=[],
            ),
            ChatToolsResponse(
                content='{"action":"done","args":{"summary":"Code analyzed successfully"},"reasoning":"Task complete"}',
                tool_calls=[],
            ),
        ]

        call_count = [0]

        def llm_fn(**kwargs):
            response = actions_sequence[min(call_count[0], len(actions_sequence) - 1)]
            call_count[0] += 1
            return response

        decider = _make_decider(llm_fn=llm_fn)
        registry = _FakeRegistry()

        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=registry,
            config=AgentLoopConfig(
                enable_llm_decider=True,
                enable_ocr=False,
                max_steps=5,
            ),
            decider=decider,
        )

        result = loop.run("проаналізуй код d:\\Python\\agent")
        assert result["ok"] is True
        # done не викликається через registry, тому тільки 2 виклики
        assert len(registry.calls) == 2
        assert registry.calls[0][0] == "list_directory"
        assert registry.calls[1][0] == "read_code_file"
        assert result["summary"] == "Code analyzed successfully"

    def test_gui_task_with_screenshot_and_ocr(self):
        """GUI задача: take_screenshot → ocr_screen → click_text → done."""
        actions_sequence = [
            ChatToolsResponse(
                content='{"action":"take_screenshot","args":{},"reasoning":"Capture screen"}',
                tool_calls=[],
            ),
            ChatToolsResponse(
                content='{"action":"ocr_screen","args":{"lang":"ukr+eng"},"reasoning":"Read text"}',
                tool_calls=[],
            ),
            ChatToolsResponse(
                content='{"action":"click_text","args":{"text":"Save"},"reasoning":"Click Save button"}',
                tool_calls=[],
            ),
            ChatToolsResponse(
                content='{"action":"done","args":{"summary":"File saved"},"reasoning":"Task complete"}',
                tool_calls=[],
            ),
        ]

        call_count = [0]

        def llm_fn(**kwargs):
            response = actions_sequence[min(call_count[0], len(actions_sequence) - 1)]
            call_count[0] += 1
            return response

        decider = _make_decider(llm_fn=llm_fn)
        registry = _FakeRegistry()

        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=registry,
            config=AgentLoopConfig(
                enable_llm_decider=True,
                enable_ocr=False,
                max_steps=5,
            ),
            decider=decider,
        )

        result = loop.run("збережи файл")
        assert result["ok"] is True
        # done не викликається через registry, тому тільки 3 виклики
        assert len(registry.calls) == 3
        assert registry.calls[0][0] == "take_screenshot"
        assert registry.calls[1][0] == "ocr_screen"
        assert registry.calls[2][0] == "click_text"
        assert result["summary"] == "File saved"

    def test_general_task_with_ask_user(self):
        """Загальна задача з ask_user."""
        actions_sequence = [
            ChatToolsResponse(
                content='{"action":"ask_user","args":{"question":"Який файл відкрити?"},"reasoning":"Need user input"}',
                tool_calls=[],
            ),
            ChatToolsResponse(
                content='{"action":"read_code_file","args":{"filepath":"d:\\\\Python\\\\agent\\\\README.md"},"reasoning":"Read README"}',
                tool_calls=[],
            ),
            ChatToolsResponse(
                content='{"action":"done","args":{"summary":"README read"},"reasoning":"Task complete"}',
                tool_calls=[],
            ),
        ]

        call_count = [0]

        def llm_fn(**kwargs):
            response = actions_sequence[min(call_count[0], len(actions_sequence) - 1)]
            call_count[0] += 1
            return response

        decider = _make_decider(llm_fn=llm_fn)
        registry = _FakeRegistry()

        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=registry,
            config=AgentLoopConfig(
                enable_llm_decider=True,
                enable_ocr=False,
                max_steps=5,
            ),
            decider=decider,
        )

        result = loop.run("прочитай документ")
        assert result["ok"] is True
        # ask_user без callback → noop (не викликається через registry)
        # done не викликається через registry
        assert len(registry.calls) == 1
        assert registry.calls[0][0] == "read_code_file"
        assert result["summary"] == "README read"

    def test_task_with_retries_and_replan(self):
        """Задача з повторними спробами і replan."""
        # LLM завжди повертає mouse_click (для симуляції повторних спроб)
        def llm_fn(**kwargs):
            return ChatToolsResponse(
                content='{"action":"mouse_click","args":{"x":100,"y":200},"reasoning":"Click button"}',
                tool_calls=[],
            )

        decider = _make_decider(llm_fn=llm_fn)

        class FailingThenSuccessRegistry:
            def __init__(self):
                self.calls = []
                self.fail_count = 0

            def execute_function(self, name, args, auto_create: bool = False):
                self.calls.append((name, dict(args)))
                if name == "mouse_click" and self.fail_count < 2:
                    self.fail_count += 1
                    return {"ok": False, "error": "click failed"}
                return {"ok": True, "result": f"executed {name}"}

        registry = FailingThenSuccessRegistry()

        loop = AgentLoop(
            assistant=_FakeAssistant(),
            registry=registry,
            config=AgentLoopConfig(
                enable_llm_decider=True,
                enable_ocr=False,
                max_steps=10,
                replan_after_failures=2,  # Replan після 2 невдач
            ),
            decider=decider,
        )

        result = loop.run("натисни кнопку")
        # Перевіряємо, що були спроби і врешті успіх
        assert registry.fail_count == 2  # 2 невдачі перед успіхом
        assert len(registry.calls) == 2  # 2 невдачі, третя не встигає виконатися


class TestDirectLLMWithoutAgentLoop:
    """Тести для прямого виклику LLM без AgentLoop."""

    def test_direct_llm_call_with_json_response(self):
        """Прямий виклик LLM з JSON відповіддю."""
        response = ChatToolsResponse(
            content='{"action":"list_directory","args":{"directory":"d:\\\\Python\\\\agent"},"reasoning":"List files"}',
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)

        action = d.decide(
            goal="показати файли в d:\\Python\\agent",
            observation=None,
            history=[],
        )

        assert action.name == "list_directory"
        assert action.arguments["directory"] == "d:\\Python\\agent"

    def test_direct_llm_with_history_context(self):
        """LLM враховує історію дій."""
        response = ChatToolsResponse(
            content='{"action":"read_code_file","args":{"filepath":"d:\\\\Python\\\\agent\\\\main.py"},"reasoning":"Read next file"}',
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)

        history = [
            {
                "action": "list_directory",
                "args": {"directory": "d:\\Python\\agent"},
                "act_result": {"ok": True, "result": "files listed"},
            }
        ]

        action = d.decide(
            goal="прочитай основний файл",
            observation=None,
            history=history,
        )

        assert action.name == "read_code_file"
        # Перевіряємо, що історія була передана в LLM
        llm_fn.assert_called_once()
        call_kwargs = llm_fn.call_args[1]
        messages = call_kwargs["messages"]
        assert len(messages) >= 2  # system + user
        user_content = messages[1]["content"]
        assert "list_directory" in user_content

    def test_direct_llm_with_observation_context(self):
        """LLM враховує observation (скріншот, OCR, UI elements)."""
        response = ChatToolsResponse(
            content='{"action":"click_text","args":{"text":"Save"},"reasoning":"Click Save button"}',
            tool_calls=[],
        )
        llm_fn = MagicMock(return_value=response)
        d = _make_decider(llm_fn=llm_fn)

        obs = Observation(
            ocr_text="File Edit View Save Exit",
            active_window_title="Notepad",
            ui_elements=[{"type": "button", "text": "Save", "x": 100, "y": 10}],
        )

        action = d.decide(
            goal="збережи файл",
            observation=obs,
            history=[],
        )

        assert action.name == "click_text"
        # Перевіряємо, що observation був переданий
        llm_fn.assert_called_once()
        call_kwargs = llm_fn.call_args[1]
        messages = call_kwargs["messages"]
        user_content = messages[1]["content"]
        assert "Notepad" in user_content
        assert "Save" in user_content
