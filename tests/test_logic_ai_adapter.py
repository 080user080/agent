"""Тести для functions/logic_ai_adapter.py."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.logic_ai_adapter import (  # noqa: E402
    ROLE_ASSISTANT,
    ROLE_USER,
    AIProvider,
    CallableProvider,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EchoProvider,
    ProviderCapabilities,
    ScriptedProvider,
    ToolSpec,
    UsageInfo,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class TestDataClasses:
    def test_chat_message_roles(self):
        for role in ("system", "user", "assistant", "tool"):
            msg = ChatMessage(role=role, content="x")
            assert msg.role == role

    def test_chat_message_invalid_role_raises(self):
        with pytest.raises(ValueError):
            ChatMessage(role="agent", content="x")

    def test_chat_message_to_dict_roundtrip(self):
        msg = ChatMessage(role="user", content="hi", metadata={"k": 1})
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["metadata"] == {"k": 1}

    def test_chat_request_add(self):
        req = ChatRequest(messages=[])
        req.add("system", "you are helpful").add("user", "hello")
        assert len(req.messages) == 2
        assert req.messages[0].role == "system"
        assert req.messages[1].content == "hello"

    def test_chat_response_ok(self):
        r = ChatResponse(content="hi", finish_reason="stop")
        assert r.ok is True
        r2 = ChatResponse(finish_reason="error", error="boom")
        assert r2.ok is False
        r3 = ChatResponse(error="oops")
        assert r3.ok is False

    def test_tool_spec_default_params(self):
        t = ToolSpec(name="grep", description="search")
        assert t.parameters == {}


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_default_capabilities(self):
        caps = ProviderCapabilities()
        assert caps.chat is True
        assert caps.tools is False
        assert caps.max_context == 4096

    def test_satisfies_true_for_empty(self):
        caps = ProviderCapabilities()
        assert caps.satisfies({}) is True

    def test_satisfies_bool_requirements(self):
        caps = ProviderCapabilities(chat=True, vision=True)
        assert caps.satisfies({"vision": True}) is True
        assert caps.satisfies({"tools": True}) is False
        # False-вимога завжди проходить (її все одно хтось задовольняє).
        assert caps.satisfies({"tools": False}) is True

    def test_satisfies_numeric_requirements(self):
        caps = ProviderCapabilities(max_context=8192)
        assert caps.satisfies({"max_context": 4096}) is True
        assert caps.satisfies({"max_context": 8192}) is True
        assert caps.satisfies({"max_context": 16384}) is False

    def test_satisfies_unknown_key_rejected(self):
        caps = ProviderCapabilities()
        assert caps.satisfies({"nonexistent_flag": True}) is False


# ---------------------------------------------------------------------------
# AIProvider (base behaviour)
# ---------------------------------------------------------------------------


class TestBaseProvider:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            AIProvider()  # type: ignore[abstract]

    def test_describe_shape(self):
        p = EchoProvider(priority=50, cost_per_1k_prompt=0.01)
        d = p.describe()
        assert d["name"] == "echo"
        assert d["priority"] == 50
        assert "capabilities" in d
        assert d["available"] is True

    def test_estimate_tokens(self):
        p = EchoProvider()
        req = ChatRequest(messages=[ChatMessage(role="user", content="hello " * 10)])
        tok = p.estimate_tokens(req)
        assert tok >= 10  # не нуль

    def test_estimate_cost(self):
        p = EchoProvider(cost_per_1k_prompt=0.002, cost_per_1k_completion=0.004)
        cost = p.estimate_cost(1000, 500)
        assert cost == pytest.approx(0.002 + 0.002)


# ---------------------------------------------------------------------------
# EchoProvider
# ---------------------------------------------------------------------------


class TestEchoProvider:
    def test_echoes_last_user_message(self):
        p = EchoProvider()
        req = ChatRequest(
            messages=[
                ChatMessage(role="system", content="s"),
                ChatMessage(role="user", content="ping"),
            ]
        )
        resp = p.chat(req)
        assert resp.content == "echo: ping"
        assert resp.provider == "echo"
        assert resp.ok is True
        assert resp.finish_reason == "stop"

    def test_handles_empty_messages(self):
        p = EchoProvider()
        req = ChatRequest(messages=[])
        resp = p.chat(req)
        assert "echo:" in resp.content
        assert resp.ok is True

    def test_usage_populated(self):
        p = EchoProvider()
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="hello world"*5)]
        )
        resp = p.chat(req)
        assert resp.usage.prompt_tokens > 0
        assert resp.usage.completion_tokens > 0
        assert resp.usage.total_tokens > 0


# ---------------------------------------------------------------------------
# ScriptedProvider
# ---------------------------------------------------------------------------


class TestScriptedProvider:
    def test_returns_scripted_sequence(self):
        p = ScriptedProvider(responses=["one", "two", "three"])
        req = ChatRequest(messages=[ChatMessage(role="user", content="?")])
        assert p.chat(req).content == "one"
        assert p.chat(req).content == "two"
        assert p.chat(req).content == "three"
        # далі — останній (без cycle).
        assert p.chat(req).content == "three"

    def test_cycle_mode(self):
        p = ScriptedProvider(responses=["a", "b"], cycle=True)
        req = ChatRequest(messages=[ChatMessage(role="user", content="?")])
        assert p.chat(req).content == "a"
        assert p.chat(req).content == "b"
        assert p.chat(req).content == "a"

    def test_empty_responses_returns_error(self):
        p = ScriptedProvider(responses=[])
        resp = p.chat(ChatRequest(messages=[]))
        assert resp.ok is False
        assert "no responses" in resp.error

    def test_supports_pre_built_response(self):
        fixed = ChatResponse(
            content="from-response",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )
        p = ScriptedProvider(responses=[fixed])
        resp = p.chat(ChatRequest(messages=[]))
        assert resp.content == "from-response"
        assert resp.usage.total_tokens == 30

    def test_records_calls(self):
        p = ScriptedProvider(responses=["a"])
        req = ChatRequest(messages=[ChatMessage(role="user", content="?")])
        p.chat(req)
        p.chat(req)
        assert len(p.calls) == 2


# ---------------------------------------------------------------------------
# CallableProvider
# ---------------------------------------------------------------------------


class TestCallableProvider:
    def test_delegates_to_callable(self):
        p = CallableProvider(handler=lambda req: f"got {req.messages[0].content}")
        resp = p.chat(
            ChatRequest(messages=[ChatMessage(role=ROLE_USER, content="x")])
        )
        assert resp.content == "got x"
        assert resp.provider == "callable"

    def test_exception_becomes_error_response(self):
        def bad(_):
            raise RuntimeError("boom")

        p = CallableProvider(handler=bad)
        resp = p.chat(ChatRequest(messages=[]))
        assert resp.ok is False
        assert "boom" in resp.error
        assert resp.finish_reason == "error"

    def test_returning_response_passed_through(self):
        custom = ChatResponse(content="c", finish_reason="stop", provider="")
        p = CallableProvider(handler=lambda _: custom)
        resp = p.chat(ChatRequest(messages=[]))
        assert resp.content == "c"
        assert resp.provider == "callable"  # fill-in

    def test_provider_accepts_capabilities(self):
        p = CallableProvider(
            handler=lambda _: "ok",
            capabilities=ProviderCapabilities(vision=True, max_context=32_000),
            name="tiny",
        )
        assert p.capabilities.vision is True
        assert p.name == "tiny"


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class TestMisc:
    def test_custom_name_and_display_name(self):
        p = EchoProvider(name="echo-x", display_name="Echo X")
        assert p.name == "echo-x"
        assert p.display_name == "Echo X"

    def test_assistant_role_allowed(self):
        msg = ChatMessage(role=ROLE_ASSISTANT, content="hi")
        assert msg.role == "assistant"
