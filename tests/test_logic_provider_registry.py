"""Тести для functions/logic_provider_registry.py."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.logic_ai_adapter import (  # noqa: E402
    CallableProvider,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EchoProvider,
    ProviderCapabilities,
    ScriptedProvider,
)
from functions.logic_provider_registry import (  # noqa: E402
    ChatAttempt,
    ProviderRegistry,
    SelectionCriteria,
    get_default_registry,
    reset_default_registry,
)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestCRUD:
    def test_register_and_get(self):
        reg = ProviderRegistry()
        p = EchoProvider()
        reg.register(p)
        assert reg.get("echo") is p

    def test_register_duplicate_raises(self):
        reg = ProviderRegistry()
        reg.register(EchoProvider())
        with pytest.raises(ValueError):
            reg.register(EchoProvider())

    def test_register_overwrite(self):
        reg = ProviderRegistry()
        p1 = EchoProvider(priority=10)
        p2 = EchoProvider(priority=99)
        reg.register(p1)
        reg.register(p2, overwrite=True)
        assert reg.get("echo") is p2

    def test_unregister(self):
        reg = ProviderRegistry()
        reg.register(EchoProvider())
        assert reg.unregister("echo") is True
        assert reg.unregister("echo") is False
        assert reg.get("echo") is None

    def test_list_and_describe(self):
        reg = ProviderRegistry()
        reg.register(EchoProvider())
        reg.register(EchoProvider(name="echo-2"))
        assert set(reg.list_names()) == {"echo", "echo-2"}
        described = reg.describe_all()
        assert len(described) == 2

    def test_clear(self):
        reg = ProviderRegistry()
        reg.register(EchoProvider())
        reg.clear()
        assert reg.list_names() == []


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


class TestSelection:
    def _make_reg(self) -> ProviderRegistry:
        reg = ProviderRegistry()
        reg.register(
            EchoProvider(
                name="cheap",
                priority=100,
                cost_per_1k_prompt=0.001,
                capabilities=ProviderCapabilities(
                    chat=True, offline=False, max_context=4096
                ),
            )
        )
        reg.register(
            EchoProvider(
                name="premium",
                priority=50,
                cost_per_1k_prompt=0.03,
                cost_per_1k_completion=0.06,
                capabilities=ProviderCapabilities(
                    chat=True, vision=True, tools=True, max_context=128_000
                ),
            )
        )
        reg.register(
            CallableProvider(
                handler=lambda r: "local",
                name="local",
                priority=200,
                capabilities=ProviderCapabilities(chat=True, offline=True),
            )
        )
        return reg

    def test_empty_criteria_returns_by_priority(self):
        reg = self._make_reg()
        providers = reg.select_many()
        # Priority: premium (50) < cheap (100) < local (200).
        names = [p.name for p in providers]
        assert names == ["premium", "cheap", "local"]

    def test_requires_vision(self):
        reg = self._make_reg()
        p = reg.select(SelectionCriteria(requires={"vision": True}))
        assert p is not None and p.name == "premium"

    def test_prefer_offline(self):
        reg = self._make_reg()
        providers = reg.select_many(SelectionCriteria(prefer_offline=True))
        assert providers[0].name == "local"

    def test_prefer_cheapest(self):
        reg = self._make_reg()
        providers = reg.select_many(SelectionCriteria(prefer_cheapest=True))
        # local має 0 вартості, далі cheap, потім premium.
        assert providers[0].name == "local"
        assert providers[-1].name == "premium"

    def test_exclude(self):
        reg = self._make_reg()
        providers = reg.select_many(SelectionCriteria(exclude=["premium"]))
        assert all(p.name != "premium" for p in providers)

    def test_prefer_overrides_priority(self):
        reg = self._make_reg()
        providers = reg.select_many(SelectionCriteria(prefer=["local"]))
        assert providers[0].name == "local"

    def test_limit(self):
        reg = self._make_reg()
        providers = reg.select_many(limit=2)
        assert len(providers) == 2

    def test_select_returns_none_when_no_match(self):
        reg = self._make_reg()
        result = reg.select(
            SelectionCriteria(requires={"code_execution": True})
        )
        assert result is None

    def test_select_skips_unavailable(self):
        class Unavailable(CallableProvider):
            def available(self) -> bool:
                return False

        reg = ProviderRegistry()
        reg.register(
            Unavailable(handler=lambda r: "x", name="broken", priority=10)
        )
        reg.register(EchoProvider(name="ok", priority=100))
        p = reg.select()
        assert p is not None and p.name == "ok"


# ---------------------------------------------------------------------------
# chat() with fallback
# ---------------------------------------------------------------------------


class TestChatFallback:
    def test_uses_first_available_provider(self):
        reg = ProviderRegistry()
        reg.register(EchoProvider(priority=10))
        req = ChatRequest(messages=[ChatMessage(role="user", content="hi")])
        resp = reg.chat(req)
        assert resp.ok is True
        assert resp.content == "echo: hi"

    def test_falls_back_on_error(self):
        reg = ProviderRegistry()
        reg.register(
            ScriptedProvider(
                responses=[
                    ChatResponse(
                        provider="first",
                        finish_reason="error",
                        error="first failed",
                    )
                ],
                name="first",
                priority=1,
            )
        )
        reg.register(EchoProvider(name="second", priority=100))
        attempts = []
        req = ChatRequest(messages=[ChatMessage(role="user", content="q")])
        resp = reg.chat(req, on_attempt=attempts.append)

        assert resp.ok is True
        assert resp.provider == "second"
        assert len(attempts) == 2
        assert attempts[0].ok is False
        assert attempts[1].ok is True

    def test_max_retries_respected(self):
        reg = ProviderRegistry()
        for i in range(5):
            reg.register(
                ScriptedProvider(
                    responses=[
                        ChatResponse(
                            provider=f"p{i}",
                            finish_reason="error",
                            error=f"p{i} failed",
                        )
                    ],
                    name=f"p{i}",
                    priority=i,
                )
            )
        attempts = []
        req = ChatRequest(messages=[ChatMessage(role="user", content="q")])
        resp = reg.chat(req, max_retries=2, on_attempt=attempts.append)

        assert resp.ok is False
        # з max_retries=2 → 3 спроби (primary + 2 retries)
        assert len(attempts) == 3

    def test_empty_registry_returns_error(self):
        reg = ProviderRegistry()
        attempts = []
        resp = reg.chat(
            ChatRequest(messages=[]),
            on_attempt=attempts.append,
        )
        assert resp.ok is False
        assert "no providers" in resp.error
        assert len(attempts) == 1
        assert attempts[0].ok is False

    def test_exception_from_provider_is_caught(self):
        def blow_up(_):
            raise RuntimeError("kaboom")

        reg = ProviderRegistry()
        reg.register(
            CallableProvider(handler=blow_up, name="bad", priority=1)
        )
        reg.register(EchoProvider(name="good", priority=100))
        resp = reg.chat(
            ChatRequest(messages=[ChatMessage(role="user", content="hi")])
        )
        # CallableProvider вже перетворює exception на error-response → reg.chat бачить помилку
        # і перемикається на другий провайдер.
        assert resp.ok is True
        assert resp.provider == "good"


# ---------------------------------------------------------------------------
# Default registry helpers
# ---------------------------------------------------------------------------


class TestDefaultRegistry:
    def setup_method(self):
        reset_default_registry()

    def teardown_method(self):
        reset_default_registry()

    def test_singleton(self):
        a = get_default_registry()
        b = get_default_registry()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_default_registry()
        reset_default_registry()
        b = get_default_registry()
        assert a is not b


# ---------------------------------------------------------------------------
# ChatAttempt dataclass
# ---------------------------------------------------------------------------


class TestChatAttempt:
    def test_shape(self):
        a = ChatAttempt(provider="p", ok=True)
        assert a.provider == "p"
        assert a.ok is True
        assert a.error == ""
