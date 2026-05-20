"""Google (Gemini) adapter — Phase 9.1 AI Orchestration.

Використовує Google Generative Language API (`https://generativelanguage.googleapis.com/v1beta`).
Потрібен `GOOGLE_API_KEY`.
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
ROLE_ASSISTANT = "model"
ROLE_SYSTEM = "system"


class GoogleAdapter(AIProvider):
    """Провайдер для Google Gemini API."""

    name = "google"
    display_name = "Google (Gemini)"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        **kwargs: Any,
    ):
        caps = kwargs.pop("capabilities", None) or ProviderCapabilities(
            chat=True,
            max_context=1_000_000,
            streaming=False,
        )
        super().__init__(
            capabilities=caps,
            cost_per_1k_prompt=0.000075,
            cost_per_1k_completion=0.0003,
            **kwargs,
        )
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        return bool(self.api_key) and requests is not None

    def _map_contents(self, request: ChatRequest) -> List[Dict[str, Any]]:
        contents: List[Dict[str, Any]] = []
        for m in request.messages:
            role = ROLE_USER if m.role == ROLE_USER else ROLE_ASSISTANT
            if m.role == ROLE_SYSTEM:
                # Gemini uses systemInstruction top-level field; skip here
                continue
            contents.append({"role": role, "parts": [{"text": m.content}]})
        return contents

    def _extract_system_instruction(self, request: ChatRequest) -> str:
        parts = [m.content for m in request.messages if m.role == ROLE_SYSTEM]
        return "\n".join(parts)

    def chat(self, request: ChatRequest) -> ChatResponse:
        if not self.available():
            raise RuntimeError("Google API key not configured or requests missing")

        url = (
            f"{self.base_url}/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        headers = {"content-type": "application/json"}
        contents = self._map_contents(request)
        payload: Dict[str, Any] = {"contents": contents}

        system_text = self._extract_system_instruction(request)
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        if request.temperature is not None:
            payload["generationConfig"] = {"temperature": request.temperature}

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                text += part.get("text", "")

        usage_data = data.get("usageMetadata", {})
        prompt_tokens = usage_data.get("promptTokenCount", self.estimate_tokens(request))
        completion_tokens = usage_data.get("candidatesTokenCount", max(1, len(text) // 4))

        return ChatResponse(
            content=text,
            provider=self.name,
            model=self.model,
            finish_reason="stop",
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
