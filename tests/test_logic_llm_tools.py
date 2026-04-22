"""Тести для `functions.logic_llm_tools` — OpenAI-compatible tool-calling (F1)."""
from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
import requests

from functions.logic_llm_tools import (
    ChatToolsResponse,
    ToolCall,
    ToolExecutionResult,
    ask_llm_with_tools,
    build_tool_spec,
    execute_tool_calls,
    functions_to_tools,
    parse_tool_calls_from_body,
    registry_to_tools,
    tool_results_to_messages,
)


# --------------------------------------------------------------------------- #
# Допоміжні                                                                   #
# --------------------------------------------------------------------------- #

def _make_http_response(status: int = 200, body: Any = None, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text or json.dumps(body or {})
    if body is None:
        resp.json.side_effect = ValueError("no body")
    else:
        resp.json.return_value = body
    return resp


def _ok_body(
    content: str = "",
    tool_calls: List[Dict[str, Any]] | None = None,
    finish_reason: str = "stop",
    model: str = "test-model",
    usage: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    message: Dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "model": model,
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _fixed_endpoint() -> Dict[str, Any]:
    return {
        "url": "http://test.local/v1/chat/completions",
        "model": "test-model",
        "api_key": "",
        "temperature": 0.0,
        "max_tokens": 256,
        "timeout": 5,
    }


# --------------------------------------------------------------------------- #
# build_tool_spec                                                             #
# --------------------------------------------------------------------------- #

class TestBuildToolSpec:
    def test_minimal_spec(self):
        spec = build_tool_spec("foo")
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "foo"
        assert spec["function"]["description"] == ""
        assert spec["function"]["parameters"] == {"type": "object"}

    def test_with_description_and_parameters(self):
        params = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        spec = build_tool_spec("read_file", "Read text file", params)
        assert spec["function"]["description"] == "Read text file"
        assert spec["function"]["parameters"] == params

    def test_parameters_without_type_gets_wrapped(self):
        params = {"properties": {"x": {"type": "integer"}}}
        spec = build_tool_spec("f", parameters=params)
        assert spec["function"]["parameters"]["type"] == "object"
        assert spec["function"]["parameters"]["properties"] == params["properties"]


# --------------------------------------------------------------------------- #
# functions_to_tools / registry_to_tools                                      #
# --------------------------------------------------------------------------- #

class TestFunctionsToTools:
    def test_converts_registry_format(self):
        functions_map = {
            "create_file": {
                "name": "create_file",
                "description": "Create a text file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
            "open_program": {
                "name": "open_program",
                "description": "Launch a program",
                "parameters": {"type": "object"},
            },
        }
        tools = functions_to_tools(functions_map)
        assert len(tools) == 2
        names = [t["function"]["name"] for t in tools]
        assert "create_file" in names
        assert "open_program" in names

    def test_include_filter(self):
        fm = {"a": {"name": "a"}, "b": {"name": "b"}, "c": {"name": "c"}}
        tools = functions_to_tools(fm, include=["a", "c"])
        names = [t["function"]["name"] for t in tools]
        assert set(names) == {"a", "c"}

    def test_exclude_filter(self):
        fm = {"a": {"name": "a"}, "b": {"name": "b"}, "c": {"name": "c"}}
        tools = functions_to_tools(fm, exclude=["b"])
        names = [t["function"]["name"] for t in tools]
        assert set(names) == {"a", "c"}

    def test_skips_entries_without_name_or_not_mapping(self):
        fm = {
            "a": {"name": "a"},
            "b": None,  # type: ignore[dict-item]
            "c": {"description": "no name"},  # name fallback → key "c"
            "": {"name": ""},
        }
        tools = functions_to_tools(fm)  # type: ignore[arg-type]
        names = [t["function"]["name"] for t in tools]
        assert "a" in names
        assert "c" in names
        assert "" not in names

    def test_empty_or_none_input(self):
        assert functions_to_tools({}) == []
        assert functions_to_tools(None) == []  # type: ignore[arg-type]

    def test_registry_to_tools_reads_functions_attr(self):
        registry = MagicMock()
        registry.functions = {
            "foo": {"name": "foo", "description": "d", "parameters": {}},
        }
        tools = registry_to_tools(registry)
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "foo"

    def test_registry_to_tools_missing_attr_returns_empty(self):
        class _Reg:
            pass

        assert registry_to_tools(_Reg()) == []


# --------------------------------------------------------------------------- #
# parse_tool_calls_from_body                                                  #
# --------------------------------------------------------------------------- #

class TestParseToolCalls:
    def test_empty_body(self):
        assert parse_tool_calls_from_body({}) == []
        assert parse_tool_calls_from_body(None) == []  # type: ignore[arg-type]

    def test_no_tool_calls(self):
        body = _ok_body(content="hello")
        assert parse_tool_calls_from_body(body) == []

    def test_single_tool_call_string_arguments(self):
        body = _ok_body(
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "create_file",
                        "arguments": '{"path": "a.txt", "content": "hi"}',
                    },
                }
            ]
        )
        tcs = parse_tool_calls_from_body(body)
        assert len(tcs) == 1
        assert tcs[0].name == "create_file"
        assert tcs[0].arguments == {"path": "a.txt", "content": "hi"}
        assert tcs[0].id == "call_1"

    def test_arguments_as_dict(self):
        body = _ok_body(
            tool_calls=[
                {
                    "id": "call_2",
                    "function": {"name": "foo", "arguments": {"x": 1}},
                }
            ]
        )
        tcs = parse_tool_calls_from_body(body)
        assert tcs[0].arguments == {"x": 1}

    def test_arguments_invalid_json_preserved_as_raw(self):
        body = _ok_body(
            tool_calls=[
                {"function": {"name": "foo", "arguments": "{not valid"}}
            ]
        )
        tcs = parse_tool_calls_from_body(body)
        assert tcs[0].arguments == {"_raw": "{not valid"}

    def test_arguments_empty_string(self):
        body = _ok_body(tool_calls=[{"function": {"name": "foo", "arguments": ""}}])
        tcs = parse_tool_calls_from_body(body)
        assert tcs[0].arguments == {}

    def test_skips_entry_without_name(self):
        body = _ok_body(
            tool_calls=[
                {"function": {"arguments": "{}"}},
                {"function": {"name": "valid", "arguments": "{}"}},
            ]
        )
        tcs = parse_tool_calls_from_body(body)
        assert len(tcs) == 1
        assert tcs[0].name == "valid"

    def test_multiple_tool_calls(self):
        body = _ok_body(
            tool_calls=[
                {"id": "a", "function": {"name": "f1", "arguments": "{}"}},
                {"id": "b", "function": {"name": "f2", "arguments": '{"k": 2}'}},
            ]
        )
        tcs = parse_tool_calls_from_body(body)
        assert [tc.name for tc in tcs] == ["f1", "f2"]
        assert tcs[1].arguments == {"k": 2}


# --------------------------------------------------------------------------- #
# ask_llm_with_tools                                                          #
# --------------------------------------------------------------------------- #

class TestAskLlmWithTools:
    def test_sends_tools_in_payload(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            captured["timeout"] = timeout
            return _make_http_response(200, _ok_body(content="ok"))

        tools = [build_tool_spec("foo", "bar")]
        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=tools,
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert resp.ok
        assert resp.content == "ok"
        assert captured["url"] == "http://test.local/v1/chat/completions"
        assert captured["payload"]["tools"] == tools
        assert captured["payload"]["model"] == "test-model"
        assert captured["payload"]["stream"] is False

    def test_sends_response_format_json_object(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["payload"] = json
            return _make_http_response(200, _ok_body(content='{"x": 1}'))

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "json pls"}],
            response_format={"type": "json_object"},
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert resp.ok
        assert captured["payload"]["response_format"] == {"type": "json_object"}

    def test_sends_tool_choice(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["payload"] = json
            return _make_http_response(200, _ok_body(content=""))

        ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            tools=[build_tool_spec("f")],
            tool_choice={"type": "function", "function": {"name": "f"}},
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert captured["payload"]["tool_choice"] == {
            "type": "function",
            "function": {"name": "f"},
        }

    def test_omits_tool_choice_when_none(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["payload"] = json
            return _make_http_response(200, _ok_body(content="ok"))

        ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert "tool_choice" not in captured["payload"]

    def test_api_key_adds_authorization_header(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["headers"] = headers
            return _make_http_response(200, _ok_body(content="ok"))

        ep = _fixed_endpoint()
        ep["api_key"] = "sk-test"
        ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=ep,
            request_fn=fake_post,
        )
        assert captured["headers"]["Authorization"] == "Bearer sk-test"

    def test_no_api_key_omits_authorization(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["headers"] = headers
            return _make_http_response(200, _ok_body(content="ok"))

        ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert "Authorization" not in captured["headers"]

    def test_parses_tool_calls_from_response(self):
        body = _ok_body(
            tool_calls=[
                {
                    "id": "c1",
                    "function": {
                        "name": "create_file",
                        "arguments": '{"path": "a.txt"}',
                    },
                }
            ],
            finish_reason="tool_calls",
        )

        def fake_post(url, **kwargs):
            return _make_http_response(200, body)

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "make a.txt"}],
            tools=[build_tool_spec("create_file")],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert resp.ok
        assert resp.has_tool_calls
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "create_file"
        assert resp.tool_calls[0].arguments == {"path": "a.txt"}
        assert resp.finish_reason == "tool_calls"

    def test_network_error_returned_as_error(self):
        def fake_post(url, **kwargs):
            raise requests.exceptions.ConnectionError("refused")

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert not resp.ok
        assert "network" in resp.error
        assert "refused" in resp.error

    def test_timeout_error_returned_as_error(self):
        def fake_post(url, **kwargs):
            raise requests.exceptions.Timeout("slow")

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert not resp.ok
        assert "network" in resp.error

    def test_non_200_status_sets_error_with_body_message(self):
        def fake_post(url, **kwargs):
            return _make_http_response(
                500, {"error": {"message": "server down", "type": "server_error"}}
            )

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert not resp.ok
        assert resp.http_status == 500
        assert "server down" in resp.error

    def test_non_200_with_plain_string_error(self):
        def fake_post(url, **kwargs):
            return _make_http_response(400, {"error": "bad request"})

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert not resp.ok
        assert "bad request" in resp.error

    def test_bad_json_body(self):
        def fake_post(url, **kwargs):
            return _make_http_response(200, body=None, text="not json")

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert not resp.ok
        assert "bad json body" in resp.error

    def test_empty_choices(self):
        def fake_post(url, **kwargs):
            return _make_http_response(200, {"choices": []})

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert not resp.ok
        assert "no choices" in resp.error

    def test_usage_parsed(self):
        def fake_post(url, **kwargs):
            return _make_http_response(
                200,
                _ok_body(
                    content="ok",
                    usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                ),
            )

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert resp.usage["total_tokens"] == 150
        assert resp.usage["prompt_tokens"] == 100

    def test_extra_payload_passed(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["payload"] = json
            return _make_http_response(200, _ok_body(content="ok"))

        ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
            extra_payload={"top_p": 0.9, "seed": 42},
        )
        assert captured["payload"]["top_p"] == 0.9
        assert captured["payload"]["seed"] == 42

    def test_extra_payload_does_not_override_existing(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["payload"] = json
            return _make_http_response(200, _ok_body(content="ok"))

        ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
            extra_payload={"model": "hijack", "temperature": 0.99},
        )
        assert captured["payload"]["model"] == "test-model"
        assert captured["payload"]["temperature"] == 0.0

    def test_messages_deep_copied(self):
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["payload"] = json
            return _make_http_response(200, _ok_body(content="ok"))

        original = [{"role": "user", "content": "hi"}]
        ask_llm_with_tools(
            messages=original,
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        # Мутація payload-копії не повинна впливати на оригінал.
        captured["payload"]["messages"][0]["content"] = "mutated"
        assert original[0]["content"] == "hi"

    def test_uses_default_endpoint_when_none(self, monkeypatch):
        """Якщо endpoint не передано — викликається get_primary_endpoint()."""
        captured: Dict[str, Any] = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            return _make_http_response(200, _ok_body(content="ok"))

        monkeypatch.setattr(
            "functions.logic_llm_tools.get_primary_endpoint",
            lambda: {
                "url": "http://from-default/v1/chat/completions",
                "model": "m",
                "api_key": "",
                "temperature": 0.0,
                "max_tokens": 10,
                "timeout": 5,
            },
        )
        ask_llm_with_tools(
            messages=[{"role": "user", "content": "x"}],
            request_fn=fake_post,
        )
        assert captured["url"] == "http://from-default/v1/chat/completions"


# --------------------------------------------------------------------------- #
# execute_tool_calls                                                          #
# --------------------------------------------------------------------------- #

class TestExecuteToolCalls:
    def test_executes_single_call(self):
        registry = MagicMock()
        registry.execute_function.return_value = {"ok": True, "wrote": "a.txt"}
        calls = [ToolCall(name="create_file", arguments={"path": "a.txt"}, id="c1")]
        results = execute_tool_calls(calls, registry)
        assert len(results) == 1
        assert results[0].ok
        assert results[0].name == "create_file"
        assert results[0].result == {"ok": True, "wrote": "a.txt"}
        assert results[0].call_id == "c1"
        registry.execute_function.assert_called_once_with("create_file", {"path": "a.txt"})

    def test_multiple_calls(self):
        registry = MagicMock()
        registry.execute_function.side_effect = ["r1", "r2", "r3"]
        calls = [
            ToolCall(name="f1"),
            ToolCall(name="f2", arguments={"x": 1}),
            ToolCall(name="f3"),
        ]
        results = execute_tool_calls(calls, registry)
        assert [r.result for r in results] == ["r1", "r2", "r3"]
        assert all(r.ok for r in results)

    def test_failed_call_captured_as_error(self):
        registry = MagicMock()
        registry.execute_function.side_effect = RuntimeError("boom")
        calls = [ToolCall(name="f1", id="c1")]
        results = execute_tool_calls(calls, registry)
        assert not results[0].ok
        assert "RuntimeError" in results[0].error
        assert "boom" in results[0].error
        assert results[0].call_id == "c1"

    def test_name_alias_applied(self):
        registry = MagicMock()
        registry.execute_function.return_value = None
        calls = [ToolCall(name="execute_python_code")]
        execute_tool_calls(
            calls,
            registry,
            name_alias={"execute_python_code": "execute_python"},
        )
        registry.execute_function.assert_called_once_with("execute_python", {})

    def test_one_failing_does_not_stop_others(self):
        registry = MagicMock()
        registry.execute_function.side_effect = [ValueError("bad"), "ok"]
        calls = [ToolCall(name="f1"), ToolCall(name="f2")]
        results = execute_tool_calls(calls, registry)
        assert results[0].ok is False
        assert results[1].ok is True
        assert results[1].result == "ok"

    def test_empty_calls_returns_empty(self):
        registry = MagicMock()
        assert execute_tool_calls([], registry) == []


# --------------------------------------------------------------------------- #
# tool_results_to_messages                                                    #
# --------------------------------------------------------------------------- #

class TestToolResultsToMessages:
    def test_basic_string_result(self):
        calls = [ToolCall(name="foo", id="c1")]
        results = [ToolExecutionResult(name="foo", ok=True, result="hello", call_id="c1")]
        msgs = tool_results_to_messages(calls, results)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "tool"
        assert msgs[0]["tool_call_id"] == "c1"
        assert msgs[0]["name"] == "foo"
        assert msgs[0]["content"] == "hello"

    def test_dict_result_serialized_as_json(self):
        calls = [ToolCall(name="foo", id="c1")]
        results = [
            ToolExecutionResult(
                name="foo", ok=True, result={"k": 1, "v": "a"}, call_id="c1"
            )
        ]
        msgs = tool_results_to_messages(calls, results)
        parsed = json.loads(msgs[0]["content"])
        assert parsed == {"k": 1, "v": "a"}

    def test_error_result_serialized(self):
        calls = [ToolCall(name="foo", id="c1")]
        results = [
            ToolExecutionResult(name="foo", ok=False, error="boom", call_id="c1")
        ]
        msgs = tool_results_to_messages(calls, results)
        parsed = json.loads(msgs[0]["content"])
        assert parsed["ok"] is False
        assert parsed["error"] == "boom"

    def test_matches_by_call_id(self):
        calls = [
            ToolCall(name="a", id="id1"),
            ToolCall(name="b", id="id2"),
        ]
        # Результати у зворотному порядку — матчимо через call_id.
        results = [
            ToolExecutionResult(name="b", ok=True, result="B", call_id="id2"),
            ToolExecutionResult(name="a", ok=True, result="A", call_id="id1"),
        ]
        msgs = tool_results_to_messages(calls, results)
        assert msgs[0]["tool_call_id"] == "id1"
        assert msgs[0]["content"] == "A"
        assert msgs[1]["tool_call_id"] == "id2"
        assert msgs[1]["content"] == "B"

    def test_fallback_to_index_when_no_id(self):
        calls = [ToolCall(name="a"), ToolCall(name="b")]
        results = [
            ToolExecutionResult(name="a", ok=True, result="A"),
            ToolExecutionResult(name="b", ok=True, result="B"),
        ]
        msgs = tool_results_to_messages(calls, results)
        assert len(msgs) == 2
        assert msgs[0]["content"] == "A"
        assert msgs[1]["content"] == "B"
        assert msgs[0]["tool_call_id"] == "call_0"

    def test_none_result(self):
        calls = [ToolCall(name="foo", id="c")]
        results = [ToolExecutionResult(name="foo", ok=True, result=None, call_id="c")]
        msgs = tool_results_to_messages(calls, results)
        assert msgs[0]["content"] == ""


# --------------------------------------------------------------------------- #
# ChatToolsResponse / helpers                                                 #
# --------------------------------------------------------------------------- #

class TestChatToolsResponse:
    def test_ok_property_true_for_success(self):
        r = ChatToolsResponse(content="hi", http_status=200)
        assert r.ok

    def test_ok_property_false_on_error(self):
        r = ChatToolsResponse(error="boom")
        assert not r.ok

    def test_ok_property_false_on_non_200(self):
        r = ChatToolsResponse(http_status=500)
        assert not r.ok

    def test_has_tool_calls(self):
        assert not ChatToolsResponse().has_tool_calls
        assert ChatToolsResponse(tool_calls=[ToolCall(name="x")]).has_tool_calls

    def test_to_dict_round_trip(self):
        r = ChatToolsResponse(
            content="c",
            tool_calls=[ToolCall(name="f", arguments={"x": 1}, id="c1")],
            finish_reason="tool_calls",
            model="m",
            usage={"total_tokens": 10},
            http_status=200,
        )
        d = r.to_dict()
        assert d["content"] == "c"
        assert d["tool_calls"][0]["name"] == "f"
        assert d["tool_calls"][0]["arguments"] == {"x": 1}
        assert d["http_status"] == 200


# --------------------------------------------------------------------------- #
# Integration: full round-trip                                                #
# --------------------------------------------------------------------------- #

class TestFullRoundTrip:
    def test_ask_execute_continue(self):
        """Повний цикл: LLM повертає tool_calls → виконуємо → формуємо tool-messages для наступного turn-а."""

        def fake_post(url, **kwargs):
            body = _ok_body(
                tool_calls=[
                    {
                        "id": "c1",
                        "function": {
                            "name": "create_file",
                            "arguments": '{"path": "a.txt", "content": "hi"}',
                        },
                    }
                ],
                finish_reason="tool_calls",
            )
            return _make_http_response(200, body)

        resp = ask_llm_with_tools(
            messages=[{"role": "user", "content": "create a.txt with 'hi'"}],
            tools=[build_tool_spec("create_file", "Create file")],
            endpoint=_fixed_endpoint(),
            request_fn=fake_post,
        )
        assert resp.ok
        assert resp.has_tool_calls

        registry = MagicMock()
        registry.execute_function.return_value = {"created": "a.txt"}
        exec_results = execute_tool_calls(resp.tool_calls, registry)
        assert len(exec_results) == 1
        assert exec_results[0].ok

        tool_messages = tool_results_to_messages(resp.tool_calls, exec_results)
        assert tool_messages[0]["role"] == "tool"
        assert tool_messages[0]["tool_call_id"] == "c1"
        assert json.loads(tool_messages[0]["content"]) == {"created": "a.txt"}
