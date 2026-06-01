"""AI Actors — делегування задач до зовнішніх AI провайдерів (S5).

Підтримує автоматичний fallback між провайдерами для довгих сесій.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ai_actors")


class Provider(Enum):
    """Доступні AI провайдери."""
    CODEX = "codex"
    WINDSURF = "windsurf"
    CURSOR = "cursor"
    CHATGPT = "chatgpt"
    CLAUDE = "claude"
    GEMINI = "gemini"


@dataclass
class ActorResult:
    """Результат виконання AI actor-а."""
    provider: Provider
    success: bool
    response: str = ""
    error: str = ""
    tokens_used: int = 0
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AIActor:
    """Базовий клас для AI actor-а."""

    def __init__(self, provider: Provider, config: Optional[Dict[str, Any]] = None):
        self.provider = provider
        self.config = config or {}

    def execute(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> ActorResult:
        """Виконати задачу через провайдер."""
        context = context or {}

        try:
            if self.provider == Provider.CODEX:
                return self._execute_codex(prompt, context)
            elif self.provider == Provider.WINDSURF:
                return self._execute_windsurf(prompt, context)
            elif self.provider == Provider.CURSOR:
                return self._execute_cursor(prompt, context)
            elif self.provider == Provider.CHATGPT:
                return self._execute_chatgpt(prompt, context)
            elif self.provider == Provider.CLAUDE:
                return self._execute_claude(prompt, context)
            elif self.provider == Provider.GEMINI:
                return self._execute_gemini(prompt, context)
            else:
                return ActorResult(
                    provider=self.provider,
                    success=False,
                    error=f"Unsupported provider: {self.provider}",
                )
        except Exception as e:
            logger.error(f"AI actor error ({self.provider}): {e}")
            return ActorResult(
                provider=self.provider,
                success=False,
                error=str(e),
            )

    def _execute_codex(self, prompt: str, context: Dict[str, Any]) -> ActorResult:
        """Виконати через Codex API (OpenAI Codex)."""
        try:
            import requests
            import time
            from functions.config import get_endpoint_by_role

            # Отримуємо primary endpoint (для Gemini/DeepSeek)
            endpoint = get_endpoint_by_role("primary")
            if not endpoint:
                return ActorResult(
                    provider=Provider.CODEX,
                    success=False,
                    error="No primary LLM endpoint configured",
                )

            # Використовуємо primary endpoint як Codex API
            headers = {"Content-Type": "application/json"}
            if endpoint.get("api_key"):
                headers["Authorization"] = f"Bearer {endpoint['api_key']}"

            start_time = time.time()
            response = requests.post(
                endpoint["url"],
                headers=headers,
                json={
                    "model": endpoint.get("model", "gpt-4"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": endpoint.get("temperature", 0.1),
                    "max_tokens": endpoint.get("max_tokens", 1024),
                },
                timeout=40
            )
            duration = time.time() - start_time

            if response.status_code != 200:
                return ActorResult(
                    provider=Provider.CODEX,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    duration_seconds=duration,
                )

            result = response.json()
            if 'choices' not in result or not result['choices']:
                return ActorResult(
                    provider=Provider.CODEX,
                    success=False,
                    error="empty choices",
                    duration_seconds=duration,
                )

            content = result['choices'][0].get('message', {}).get('content', '')
            tokens_used = result.get('usage', {}).get('total_tokens', 0)

            return ActorResult(
                provider=Provider.CODEX,
                success=True,
                response=content,
                tokens_used=tokens_used,
                duration_seconds=duration,
                metadata={"model": endpoint.get("model")},
            )
        except Exception as e:
            return ActorResult(
                provider=Provider.CODEX,
                success=False,
                error=str(e),
            )

    def _execute_windsurf(self, prompt: str, context: Dict[str, Any]) -> ActorResult:
        """Виконати через Windsurf (Playwright CDP)."""
        try:
            from functions.tools.tools_browser_cdp import cdp_send_to_ai
            import time

            start_time = time.time()
            result = cdp_send_to_ai(prompt, wait_timeout=120, max_retries=2)
            duration = time.time() - start_time

            if result.get("ok"):
                text = result.get("data", {}).get("text", "")
                return ActorResult(
                    provider=Provider.WINDSURF,
                    success=True,
                    response=text,
                    duration_seconds=duration,
                    metadata={"method": result.get("data", {}).get("method", "cdp")},
                )
            else:
                return ActorResult(
                    provider=Provider.WINDSURF,
                    success=False,
                    error=result.get("error", "Unknown error"),
                    duration_seconds=duration,
                )
        except Exception as e:
            return ActorResult(
                provider=Provider.WINDSURF,
                success=False,
                error=str(e),
            )

    def _execute_cursor(self, prompt: str, context: Dict[str, Any]) -> ActorResult:
        """Виконати через Cursor (Playwright CDP)."""
        try:
            from functions.tools.tools_browser_cdp import cdp_send_to_ai
            import time

            start_time = time.time()
            result = cdp_send_to_ai(prompt, wait_timeout=120, max_retries=2)
            duration = time.time() - start_time

            if result.get("ok"):
                text = result.get("data", {}).get("text", "")
                return ActorResult(
                    provider=Provider.CURSOR,
                    success=True,
                    response=text,
                    duration_seconds=duration,
                    metadata={"method": result.get("data", {}).get("method", "cdp")},
                )
            else:
                return ActorResult(
                    provider=Provider.CURSOR,
                    success=False,
                    error=result.get("error", "Unknown error"),
                    duration_seconds=duration,
                )
        except Exception as e:
            return ActorResult(
                provider=Provider.CURSOR,
                success=False,
                error=str(e),
            )

    def _execute_chatgpt(self, prompt: str, context: Dict[str, Any]) -> ActorResult:
        """Виконати через ChatGPT web (Playwright CDP)."""
        try:
            from functions.tools.tools_browser_cdp import cdp_send_to_ai
            import time

            start_time = time.time()
            result = cdp_send_to_ai(prompt, wait_timeout=120, max_retries=2)
            duration = time.time() - start_time

            if result.get("ok"):
                text = result.get("data", {}).get("text", "")
                return ActorResult(
                    provider=Provider.CHATGPT,
                    success=True,
                    response=text,
                    duration_seconds=duration,
                    metadata={"method": result.get("data", {}).get("method", "cdp")},
                )
            else:
                return ActorResult(
                    provider=Provider.CHATGPT,
                    success=False,
                    error=result.get("error", "Unknown error"),
                    duration_seconds=duration,
                )
        except Exception as e:
            return ActorResult(
                provider=Provider.CHATGPT,
                success=False,
                error=str(e),
            )

    def _execute_claude(self, prompt: str, context: Dict[str, Any]) -> ActorResult:
        """Виконати через Claude web (Playwright CDP)."""
        try:
            from functions.tools.tools_browser_cdp import cdp_send_to_ai
            import time

            start_time = time.time()
            result = cdp_send_to_ai(prompt, wait_timeout=120, max_retries=2)
            duration = time.time() - start_time

            if result.get("ok"):
                text = result.get("data", {}).get("text", "")
                return ActorResult(
                    provider=Provider.CLAUDE,
                    success=True,
                    response=text,
                    duration_seconds=duration,
                    metadata={"method": result.get("data", {}).get("method", "cdp")},
                )
            else:
                return ActorResult(
                    provider=Provider.CLAUDE,
                    success=False,
                    error=result.get("error", "Unknown error"),
                    duration_seconds=duration,
                )
        except Exception as e:
            return ActorResult(
                provider=Provider.CLAUDE,
                success=False,
                error=str(e),
            )

    def _execute_gemini(self, prompt: str, context: Dict[str, Any]) -> ActorResult:
        """Виконати через Gemini API (Google)."""
        try:
            import requests
            import time
            from functions.config import get_endpoint_by_role

            # Отримуємо primary endpoint (для Gemini/DeepSeek)
            endpoint = get_endpoint_by_role("primary")
            if not endpoint:
                return ActorResult(
                    provider=Provider.GEMINI,
                    success=False,
                    error="No primary LLM endpoint configured",
                )

            # Використовуємо primary endpoint як Gemini API
            headers = {"Content-Type": "application/json"}
            if endpoint.get("api_key"):
                headers["Authorization"] = f"Bearer {endpoint['api_key']}"

            start_time = time.time()
            response = requests.post(
                endpoint["url"],
                headers=headers,
                json={
                    "model": endpoint.get("model", "gemini-pro"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": endpoint.get("temperature", 0.1),
                    "max_tokens": endpoint.get("max_tokens", 1024),
                },
                timeout=40
            )
            duration = time.time() - start_time

            if response.status_code != 200:
                return ActorResult(
                    provider=Provider.GEMINI,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    duration_seconds=duration,
                )

            result = response.json()
            if 'choices' not in result or not result['choices']:
                return ActorResult(
                    provider=Provider.GEMINI,
                    success=False,
                    error="empty choices",
                    duration_seconds=duration,
                )

            content = result['choices'][0].get('message', {}).get('content', '')
            tokens_used = result.get('usage', {}).get('total_tokens', 0)

            return ActorResult(
                provider=Provider.GEMINI,
                success=True,
                response=content,
                tokens_used=tokens_used,
                duration_seconds=duration,
                metadata={"model": endpoint.get("model")},
            )
        except Exception as e:
            return ActorResult(
                provider=Provider.GEMINI,
                success=False,
                error=str(e),
            )


class ActorRegistry:
    """Реєстр AI actor-ів з автоматичним fallback."""

    def __init__(self):
        self.actors: Dict[Provider, AIActor] = {}
        self._init_default_actors()

    def _init_default_actors(self):
        """Ініціалізувати дефолтні актори."""
        for provider in Provider:
            self.actors[provider] = AIActor(provider)

    def register(self, provider: Provider, actor: AIActor):
        """Зареєструвати актор для провайдера."""
        self.actors[provider] = actor

    def get_actor(self, provider: Provider) -> Optional[AIActor]:
        """Отримати актор для провайдера."""
        return self.actors.get(provider)

    def execute_with_fallback(
        self,
        prompt: str,
        preferred_order: List[Provider],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActorResult:
        """Виконати з автоматичним fallback між провайдерами.

        Пробує кожного провайдера з preferred_order поки не успішно.
        """
        context = context or {}
        last_error = ""

        for provider in preferred_order:
            actor = self.get_actor(provider)
            if not actor:
                logger.warning(f"No actor for provider: {provider}")
                continue

            logger.info(f"Trying provider: {provider}")
            result = actor.execute(prompt, context)

            if result.success:
                logger.info(f"Success with provider: {provider}")
                return result
            else:
                last_error = result.error
                logger.warning(f"Failed with {provider}: {result.error}")

        # Всі провайдери провалились
        return ActorResult(
            provider=preferred_order[0] if preferred_order else Provider.CODEX,
            success=False,
            error=f"All providers failed. Last error: {last_error}",
        )


# ─── Singleton instance ────────────────────────────────────────────────────────

_actor_registry: Optional[ActorRegistry] = None


def get_actor_registry() -> ActorRegistry:
    """Отримати singleton ActorRegistry."""
    global _actor_registry
    if _actor_registry is None:
        _actor_registry = ActorRegistry()
    return _actor_registry


__all__ = [
    "AIActor",
    "ActorRegistry",
    "ActorResult",
    "Provider",
    "get_actor_registry",
]