"""Anthropic (Claude) adapter — Phase 9.1 AI Orchestration.

Використовує HTTP API Anthropic (`https://api.anthropic.com/v1/messages`).
Потрібен `ANTHROPIC_API_KEY`.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:  # noqa: BLE001
    requests = None  # type: ignore

from .logic_ai_adapter import AIProvider, ChatRequest, ChatResponse, ProviderCapabilities, UsageInfo

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"


class AnthropicAdapter(AIProvider):
    """Провайдер для Anthropic Claude API."""

    name = "anthropic"
    display_name = "Anthropic (Claude)"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com/v1",
        **kwargs: Any,
    ):
        caps = kwargs.pop("capabilities", None) or ProviderCapabilities(
            chat=True,
            max_context=200_000,
            streaming=True,
        )
        super().__init__(
            capabilities=caps,
            cost_per_1k_prompt=0.003,
            cost_per_1k_completion=0.015,
            **kwargs,
        )
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        return bool(self.api_key) and requests is not None

    def _map_messages(self, request: ChatRequest) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = []
        for m in request.messages:
            role = m.role
            if role == ROLE_SYSTEM:
                # Anthropic uses system as a top-level parameter, skip here
                continue
            if role not in (ROLE_USER, ROLE_ASSISTANT):
                role = ROLE_USER
            msgs.append({"role": role, "content": m.content})
        return msgs

    def _extract_system(self, request: ChatRequest) -> str:
        parts = [m.content for m in request.messages if m.role == ROLE_SYSTEM]
        return "\n".join(parts)

    def chat(self, request: ChatRequest) -> ChatResponse:
        if not self.available():
            raise RuntimeError("Anthropic API key not configured or requests missing")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": request.model or self.model,
            "max_tokens": min(request.max_tokens or 4096, 4096),
            "messages": self._map_messages(request),
        }
        system_text = self._extract_system(request)
        if system_text:
            payload["system"] = system_text
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        url = f"{self.base_url}/messages"
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        content_parts = data.get("content", [])
        text = ""
        for part in content_parts:
            if part.get("type") == "text":
                text += part.get("text", "")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", self.estimate_tokens(request))
        completion_tokens = usage.get("output_tokens", max(1, len(text) // 4))

        return ChatResponse(
            content=text,
            provider=self.name,
            model=data.get("model", self.model),
            finish_reason=data.get("stop_reason", "stop"),
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
