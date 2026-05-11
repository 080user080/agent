"""Provider Chain — послідовний fallback ланцюг провайдерів.

Рівень 2 в архітектурі оркестрації ШІ:
- Виконує запит через ланцюг провайдерів з fallback
- Quota tracking (простий consecutive errors limiter)
- Health-check для LM Studio
- Observability через structured logging
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from .router import RoutingDecision
from ..logic_ai_adapter import AIProvider, ChatRequest, ChatResponse

logger = logging.getLogger("mark.orchestration")


class ProviderChain:
    """Виконує запит через ланцюг провайдерів з fallback."""

    def __init__(self, providers: dict[str, AIProvider]):
        """Ініціалізує ланцюг провайдерів.

        Args:
            providers: Словник {provider_id: AIProvider}.
        """
        self.providers = providers
        self.stats = {}  # provider_id → {calls, errors, consecutive_errors, last_ok}

    def execute(
        self,
        request: ChatRequest,
        decision: RoutingDecision,
        timeout_per_provider: float = 180.0,
    ) -> ChatResponse:
        """Виконує запит через ланцюг провайдерів з fallback.

        Args:
            request: Запит до LLM.
            decision: Рішення маршрутизації.
            timeout_per_provider: Таймаут на кожного провайдера (секунди).

        Returns:
            ChatResponse від першого успішного провайдера або error response.
        """
        chain = [decision.primary_provider_id] + decision.fallback_chain
        last_error = None

        for provider_id in chain:
            provider = self.providers.get(provider_id)
            if not provider:
                logger.warning(f"Provider {provider_id} not found in registry")
                continue

            if not provider.available():
                logger.warning(f"Provider {provider_id} not available")
                continue

            # Health-check для LM Studio (ConnectionRefused обробка)
            if not self._health_check(provider_id):
                logger.warning(f"Provider {provider_id} health-check failed")
                self._record_error(provider_id)
                continue

            # Перевірка квоти
            if self._is_quota_exceeded(provider_id):
                logger.warning(f"Provider {provider_id}: quota exceeded, skipping")
                continue

            try:
                start = time.monotonic()
                response = provider.chat(request)
                elapsed = time.monotonic() - start

                self._record_success(provider_id, elapsed)

                # Логування успішного виклику
                logger.info(
                    "provider_call_success",
                    extra={
                        "provider": provider_id,
                        "task_type": decision.task_type.value,
                        "latency_ms": int(elapsed * 1000),
                        "tokens": getattr(response, "usage", {}).get("total_tokens", 0),
                    },
                )

                if response.ok:
                    if provider_id != decision.primary_provider_id:
                        logger.info(f"Used fallback provider: {provider_id}")
                    return response

                # Soft error (finish_reason="error") — логуємо і продовжуємо
                last_error = response.error
                self._record_error(provider_id)
                logger.warning(f"Provider {provider_id} returned error: {last_error}")

            except Exception as e:
                last_error = str(e)
                self._record_error(provider_id)
                logger.error(f"Provider {provider_id} exception: {e}")

        # Всі провайдери недоступні — graceful degradation
        logger.error("All providers failed", extra={"last_error": last_error})
        return ChatResponse(
            content=f"Усі провайдери недоступні. Остання помилка: {last_error}",
            finish_reason="error",
            error=last_error or "no_providers",
        )

    def _health_check(self, provider_id: str) -> bool:
        """Простий health-check для провайдера.

        Для LM Studio — перевіряє чи є ConnectionRefused.
        """
        provider = self.providers.get(provider_id)
        if not provider:
            return False

        # Якщо є метод health_check — викликаємо його
        if hasattr(provider, "health_check"):
            try:
                return provider.health_check()
            except Exception:
                return False

        # За замовчуванням вважаємо що провайдер здоровий
        return True

    def _is_quota_exceeded(self, provider_id: str) -> bool:
        """Перевіряє чи вичерпана квота провайдера.

        Простий rate limiter: не більше 3 помилок підряд.
        """
        stats = self.stats.get(provider_id, {})
        return stats.get("consecutive_errors", 0) >= 3

    def _record_success(self, provider_id: str, elapsed: float):
        """Записує успішний виклик."""
        s = self.stats.setdefault(
            provider_id,
            {"calls": 0, "errors": 0, "consecutive_errors": 0, "last_ok": None},
        )
        s["calls"] += 1
        s["consecutive_errors"] = 0
        s["last_ok"] = time.time()

    def _record_error(self, provider_id: str):
        """Записує помилку."""
        s = self.stats.setdefault(
            provider_id,
            {"calls": 0, "errors": 0, "consecutive_errors": 0, "last_ok": None},
        )
        s["errors"] += 1
        s["consecutive_errors"] = s.get("consecutive_errors", 0) + 1

    def get_stats(self) -> dict:
        """Повертає статистику по всіх провайдерах."""
        return self.stats.copy()
