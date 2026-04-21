"""Тести для functions/providers_openai_compatible.py.

Усі HTTP-виклики моканні — реальна мережа НЕ зачіпається.
"""
import os
import sys
from typing import Any, Dict, List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.logic_ai_adapter import (  # noqa: E402
    ChatMessage,
    ChatRequest,
    ToolSpec,
)
from functions.providers_openai_compatible import (  # noqa: E402
    DEFAULT_RETRIES,
    HTTPResponse,
    OpenAICompatibleProvider,
    lmstudio_provider,
    ollama_provider,
    openai_provider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_success_body(
    *,
    content: str = "hello",
    model: str = "gpt-4o-mini",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    tool_calls: list = None,
    finish_reason: str = "stop",
) -> Dict[str, Any]:
    message: Dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "model": model,
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class RecordingClient:
    """Моканий HTTP-клієнт, який записує всі виклики та повертає зафіксовані відповіді."""

    def __init__(self, responses: List[HTTPResponse]):
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        timeout: float,
    ) -> HTTPResponse:
        self.calls.append(
            {"url": url, "headers": headers, "payload": payload, "timeout": timeout}
        )
        if not self._responses:
            return HTTPResponse(status=0, body=None, error="no more responses")
        return self._responses.pop(0)


def sleep_noop(_: float) -> None:
    pass


# ---------------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------------


class TestBasics:
    def test_builds_correct_url_and_headers(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body=make_success_body())]
        )
        p = OpenAICompatibleProvider(
            base_url="http://localhost:1234/v1",
            api_key="sk-123",
            model="local",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        p.chat(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["url"] == "http://localhost:1234/v1/chat/completions"
        assert call["headers"]["Authorization"] == "Bearer sk-123"
        assert call["headers"]["Content-Type"] == "application/json"

    def test_no_api_key_omits_auth_header(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body=make_success_body())]
        )
        p = OpenAICompatibleProvider(
            base_url="http://localhost:1234/v1",
            api_key=None,
            http_client=client,
            sleep_fn=sleep_noop,
        )
        p.chat(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))
        assert "Authorization" not in client.calls[0]["headers"]

    def test_strips_trailing_slash_from_base_url(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body=make_success_body())]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1/",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        p.chat(ChatRequest(messages=[]))
        assert client.calls[0]["url"] == "http://x/v1/chat/completions"


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------


class TestPayload:
    def test_messages_serialized(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body=make_success_body())]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        req = ChatRequest(
            messages=[
                ChatMessage(role="system", content="s"),
                ChatMessage(role="user", content="u"),
                ChatMessage(role="tool", content="t", name="my_tool"),
            ],
            model="custom-model",
            temperature=0.7,
            max_tokens=256,
        )
        p.chat(req)
        payload = client.calls[0]["payload"]
        assert payload["model"] == "custom-model"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 256
        assert payload["messages"][2] == {"role": "tool", "content": "t", "name": "my_tool"}

    def test_tools_serialized(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body=make_success_body())]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="x")],
            tools=[
                ToolSpec(
                    name="grep",
                    description="search",
                    parameters={"type": "object", "properties": {}},
                )
            ],
        )
        p.chat(req)
        tools = client.calls[0]["payload"]["tools"]
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "grep"

    def test_default_model_used_when_request_has_none(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body=make_success_body())]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            model="default-m",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        p.chat(ChatRequest(messages=[]))
        assert client.calls[0]["payload"]["model"] == "default-m"


# ---------------------------------------------------------------------------
# Success parsing
# ---------------------------------------------------------------------------


class TestSuccessParsing:
    def test_parses_content_and_usage(self):
        client = RecordingClient(
            [
                HTTPResponse(
                    status=200,
                    body=make_success_body(
                        content="hi there",
                        prompt_tokens=50,
                        completion_tokens=20,
                    ),
                )
            ]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            cost_per_1k_prompt=0.01,
            cost_per_1k_completion=0.03,
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(
            ChatRequest(messages=[ChatMessage(role="user", content="ping")])
        )
        assert resp.ok
        assert resp.content == "hi there"
        assert resp.usage.prompt_tokens == 50
        assert resp.usage.completion_tokens == 20
        assert resp.usage.total_tokens == 70
        assert resp.usage.cost_usd == pytest.approx(50 / 1000 * 0.01 + 20 / 1000 * 0.03)

    def test_parses_tool_calls(self):
        body = make_success_body(
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "grep",
                        "arguments": '{"pattern": "foo"}',
                    }
                },
                {
                    "function": {
                        "name": "read_file",
                        "arguments": {"path": "a.txt"},
                    }
                },
            ],
        )
        client = RecordingClient([HTTPResponse(status=200, body=body)])
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].name == "grep"
        assert resp.tool_calls[0].arguments == {"pattern": "foo"}
        assert resp.tool_calls[1].arguments == {"path": "a.txt"}

    def test_bad_arguments_json_wraps_as_raw(self):
        body = make_success_body(
            content="",
            tool_calls=[
                {"function": {"name": "x", "arguments": "not-json"}},
            ],
        )
        client = RecordingClient([HTTPResponse(status=200, body=body)])
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert resp.tool_calls[0].arguments == {"_raw": "not-json"}


# ---------------------------------------------------------------------------
# Error handling + retries
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_404_not_retried(self):
        client = RecordingClient(
            [
                HTTPResponse(
                    status=404, body={"error": {"message": "model not found"}}
                )
            ]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert not resp.ok
        assert "http 404" in resp.error
        assert "model not found" in resp.error
        assert len(client.calls) == 1

    def test_500_retried(self):
        client = RecordingClient(
            [
                HTTPResponse(status=500, body={}),
                HTTPResponse(status=500, body={}),
                HTTPResponse(
                    status=200, body=make_success_body(content="finally")
                ),
            ]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            max_retries=3,
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert resp.ok
        assert resp.content == "finally"
        assert len(client.calls) == 3

    def test_429_retried(self):
        client = RecordingClient(
            [
                HTTPResponse(status=429, body={"error": {"message": "rate limit"}}),
                HTTPResponse(status=200, body=make_success_body()),
            ]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            max_retries=3,
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert resp.ok
        assert len(client.calls) == 2

    def test_retries_exhausted(self):
        client = RecordingClient(
            [HTTPResponse(status=500, body={"error": "boom"})] * 5
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            max_retries=3,
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert not resp.ok
        assert "http 500" in resp.error
        # точно max_retries спроб
        assert len(client.calls) == 3

    def test_network_error_retried_then_fails(self):
        client = RecordingClient(
            [
                HTTPResponse(status=0, body=None, error="ConnectionError: refused"),
                HTTPResponse(status=0, body=None, error="ConnectionError: refused"),
                HTTPResponse(status=0, body=None, error="ConnectionError: refused"),
            ]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            max_retries=3,
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert not resp.ok
        assert "network" in resp.error
        assert len(client.calls) == 3

    def test_empty_choices_is_error(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body={"choices": [], "usage": {}})]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert not resp.ok
        assert "no choices" in resp.error

    def test_non_dict_body_is_error(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body="plain text response")]
        )
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            http_client=client,
            sleep_fn=sleep_noop,
        )
        resp = p.chat(ChatRequest(messages=[]))
        assert not resp.ok
        assert "bad payload" in resp.error


# ---------------------------------------------------------------------------
# Backoff timing
# ---------------------------------------------------------------------------


class TestBackoff:
    def test_sleeps_between_retries(self):
        client = RecordingClient(
            [
                HTTPResponse(status=500, body={}),
                HTTPResponse(status=500, body={}),
                HTTPResponse(status=200, body=make_success_body()),
            ]
        )
        sleeps: List[float] = []
        p = OpenAICompatibleProvider(
            base_url="http://x/v1",
            max_retries=3,
            http_client=client,
            sleep_fn=sleeps.append,
        )
        p.chat(ChatRequest(messages=[]))
        # між 3-ма викликами — 2 сни з expo-backoff 1, 2
        assert sleeps == [1, 2]


# ---------------------------------------------------------------------------
# Defaults and constants
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_retries_constant(self):
        assert DEFAULT_RETRIES >= 1


# ---------------------------------------------------------------------------
# Preset factories
# ---------------------------------------------------------------------------


class TestPresets:
    def test_lmstudio_defaults(self):
        p = lmstudio_provider()
        assert p.base_url == "http://localhost:1234/v1"
        assert p.api_key is None
        assert p.capabilities.offline is True
        assert p.name == "lmstudio"

    def test_ollama_defaults(self):
        p = ollama_provider()
        assert p.base_url == "http://localhost:11434/v1"
        assert p.api_key is None
        assert p.capabilities.offline is True

    def test_openai_reads_env_when_no_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "from-env")
        p = openai_provider()
        assert p.api_key == "from-env"
        assert p.base_url == "https://api.openai.com/v1"
        assert p.capabilities.vision is True

    def test_openai_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        p = openai_provider(api_key="explicit")
        assert p.api_key == "explicit"

    def test_lmstudio_custom_http_client(self):
        client = RecordingClient(
            [HTTPResponse(status=200, body=make_success_body(content="local"))]
        )
        p = lmstudio_provider(http_client=client, sleep_fn=sleep_noop)
        resp = p.chat(
            ChatRequest(messages=[ChatMessage(role="user", content="hi")])
        )
        assert resp.ok
        assert resp.content == "local"
        assert resp.provider == "lmstudio"

    def test_presets_registrable(self):
        from functions.logic_provider_registry import ProviderRegistry

        reg = ProviderRegistry()
        reg.register(lmstudio_provider())
        reg.register(ollama_provider())
        assert set(reg.list_names()) == {"lmstudio", "ollama"}


# ---------------------------------------------------------------------------
# Integration with registry fallback
# ---------------------------------------------------------------------------


class TestRegistryFallback:
    def test_primary_falls_to_secondary(self):
        from functions.logic_ai_adapter import EchoProvider
        from functions.logic_provider_registry import ProviderRegistry

        broken = OpenAICompatibleProvider(
            base_url="http://down/v1",
            name="broken",
            priority=10,
            http_client=RecordingClient(
                [HTTPResponse(status=500, body={})] * 5
            ),
            sleep_fn=sleep_noop,
            max_retries=1,
        )
        reg = ProviderRegistry()
        reg.register(broken)
        reg.register(EchoProvider(priority=100))

        resp = reg.chat(
            ChatRequest(messages=[ChatMessage(role="user", content="hi")])
        )
        assert resp.ok is True
        assert resp.provider == "echo"
