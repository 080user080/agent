"""Інтеграційні тести: ProviderRegistry.chat(budget=...) → SessionBudget.

Перевіряє, що після успішного LLM-виклику через registry.chat()
з параметром `budget`, SessionBudget.usage.tokens та cost оновлюються.
"""
import os
import sys
from typing import Any, Dict

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.llm.logic_ai_adapter import (  # noqa: E402
    ChatMessage,
    ChatRequest,
    ChatResponse,
    UsageInfo,
)
from functions.llm.logic_provider_registry import (  # noqa: E402
    ProviderRegistry,
    SelectionCriteria,
)
from functions.runtime.core_session_budget import (  # noqa: E402
    SessionBudget,
    SessionLimits,
)


# ---------------------------------------------------------------------------
# Fake provider with controllable usage
# ---------------------------------------------------------------------------


class UsageTrackingProvider:
    """Mock-провайдер, що повертає заданий UsageInfo в кожному ChatResponse."""

    name = "usage-tracker"
    display_name = "Usage Tracker (test)"

    def __init__(self, prompt_tokens: int = 50, completion_tokens: int = 30):
        self.capabilities = type("Cap", (), {
            "chat": True,
            "streaming": False,
            "tools": False,
            "vision": False,
            "offline": True,
            "max_context": 8192,
            "satisfies": lambda self, r: True,
        })()
        self.priority = 50
        self.cost_per_1k_prompt = 0.01
        self.cost_per_1k_completion = 0.03
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens

    def available(self) -> bool:
        return True

    def chat(self, request: ChatRequest) -> ChatResponse:
        total = self._prompt_tokens + self._completion_tokens
        cost = (
            self._prompt_tokens / 1000 * self.cost_per_1k_prompt
            + self._completion_tokens / 1000 * self.cost_per_1k_completion
        )
        return ChatResponse(
            content="test response",
            provider=self.name,
            model="test-model",
            finish_reason="stop",
            usage=UsageInfo(
                prompt_tokens=self._prompt_tokens,
                completion_tokens=self._completion_tokens,
                total_tokens=total,
                cost_usd=round(cost, 6),
            ),
        )


class DefaultProvider:
    """Mock-провайдер для fallback-тестів."""

    name = "default"
    display_name = "Default (test)"

    def __init__(self):
        self.capabilities = type("Cap", (), {
            "chat": True,
            "streaming": False,
            "tools": False,
            "vision": False,
            "offline": True,
            "max_context": 8192,
            "satisfies": lambda self, r: True,
        })()
        self.priority = 100
        self.cost_per_1k_prompt = 0.0
        self.cost_per_1k_completion = 0.0

    def available(self) -> bool:
        return True

    def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            content="fallback ok",
            provider=self.name,
            model="test-model",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBudgetIntegration:
    def test_registry_chat_with_budget_records_tokens(self):
        """Після registry.chat(budget=b) budget.usage.tokens має бути > 0."""
        reg = ProviderRegistry()
        reg.register(UsageTrackingProvider(prompt_tokens=100, completion_tokens=50))

        budget = SessionBudget()
        req = ChatRequest(messages=[ChatMessage(role="user", content="test")])

        # До виклику — 0 токенів
        assert budget.usage.tokens == 0
        assert budget.usage.cost_usd == 0.0

        resp = reg.chat(req, budget=budget)

        assert resp.ok
        assert resp.usage.total_tokens == 150
        # Після виклику — токени записано
        assert budget.usage.tokens == 150
        assert budget.usage.cost_usd > 0
        assert budget.usage.steps == 0  # кроки не чіпаємо

    def test_registry_chat_without_budget_does_not_record(self):
        """Без budget budget не міняється."""
        reg = ProviderRegistry()
        reg.register(UsageTrackingProvider(prompt_tokens=10, completion_tokens=5))

        budget = SessionBudget()
        req = ChatRequest(messages=[ChatMessage(role="user", content="test")])

        # Виклик без budget=
        resp = reg.chat(req)
        assert resp.ok
        # budget не передавався — токени не записані
        assert budget.usage.tokens == 0

    def test_budget_records_only_from_ok_response(self):
        """Якщо всі провайдери впали — токени не записуються."""
        reg = ProviderRegistry()
        # Провайдер, який завжди падає
        failing = UsageTrackingProvider(prompt_tokens=100, completion_tokens=50)
        failing.available = lambda: True
        original_chat = failing.chat

        def broken_chat(req):
            return ChatResponse(
                finish_reason="error",
                error="simulated failure",
            )

        failing.chat = broken_chat
        reg.register(failing)

        budget = SessionBudget()
        req = ChatRequest(messages=[ChatMessage(role="user", content="test")])

        resp = reg.chat(req, budget=budget)
        assert not resp.ok
        assert budget.usage.tokens == 0
        assert budget.usage.cost_usd == 0.0

    def test_fallback_still_records_tokens(self):
        """При fallback з primary на secondary — токени записуються з secondary."""
        reg = ProviderRegistry()

        # Primary — падає
        primary = UsageTrackingProvider()
        primary.name = "primary"
        primary.priority = 10
        original = primary.chat

        def failing_chat(req):
            return ChatResponse(
                finish_reason="error",
                error="primary failed",
            )
        primary.chat = failing_chat
        reg.register(primary)

        # Secondary — успішний
        reg.register(DefaultProvider())

        budget = SessionBudget()
        req = ChatRequest(messages=[ChatMessage(role="user", content="test")])

        resp = reg.chat(req, budget=budget)
        assert resp.ok
        assert resp.provider == "default"
        # Токени записано з secondary (8 токенів)
        assert budget.usage.tokens == 8

    def test_multiple_calls_accumulate(self):
        """Декілька викликів накопичують токени."""
        reg = ProviderRegistry()
        reg.register(UsageTrackingProvider(prompt_tokens=30, completion_tokens=20))

        budget = SessionBudget()
        req = ChatRequest(messages=[ChatMessage(role="user", content="test")])

        for _ in range(3):
            resp = reg.chat(req, budget=budget)
            assert resp.ok

        # 3 виклики * 50 токенів = 150
        assert budget.usage.tokens == 150
        assert budget.usage.steps == 0  # кроки не чіпаємо

    def test_registry_chain_fallback_preserves_budget(self):
        """Test з реального ProviderChain-like сценарію."""
        reg = ProviderRegistry()

        p1 = UsageTrackingProvider(prompt_tokens=100, completion_tokens=50)
        p1.name = "p1"
        p1.priority = 10
        reg.register(p1)

        budget = SessionBudget()
        req = ChatRequest(messages=[ChatMessage(role="user", content="hello")])

        resp = reg.chat(req, budget=budget)

        assert resp.ok
        assert resp.provider == "p1"
        assert budget.usage.tokens == 150
        assert budget.check().ok is True

    def test_budget_cost_wired_with_estimate_cost(self):
        """Cost з UsageInfo матчиться з estimate_cost провайдера."""
        reg = ProviderRegistry()
        p = UsageTrackingProvider(prompt_tokens=100, completion_tokens=50)
        reg.register(p)

        budget = SessionBudget()
        req = ChatRequest(messages=[ChatMessage(role="user", content="test")])
        resp = reg.chat(req, budget=budget)

        expected_cost = (
            100 / 1000 * 0.01 + 50 / 1000 * 0.03
        )
        assert resp.usage.cost_usd == pytest.approx(expected_cost)
        assert budget.usage.cost_usd == pytest.approx(expected_cost)