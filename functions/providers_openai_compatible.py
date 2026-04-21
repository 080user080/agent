"""OpenAI-сумісний HTTP-провайдер.

Phase 9 / J3. Покриває всі сервіси, що тримають `/v1/chat/completions`
ендпоінт OpenAI-формату:
- **LM Studio** (локально, `http://localhost:1234/v1`, авторизація не потрібна).
- **Ollama** (з `/v1` openai-shim: `http://localhost:11434/v1`).
- **LocalAI** / **vLLM** / **llama.cpp-server** / **text-generation-webui**.
- Справжній **OpenAI** (`https://api.openai.com/v1`, потрібен `OPENAI_API_KEY`).

Всі відмінності між сервісами ховаються в `base_url`, `api_key` та `model`.

Дизайн:
- Нульовий raise в публічних методах. Будь-яка помилка (мережева, парсингу,
  auth) → `ChatResponse(finish_reason="error", error=...)` щоб
  `ProviderRegistry` автоматично перемикався на наступного у fallback-ланцюгу.
- Retry 429/5xx з експоненціальним backoff (3 спроби по замовчуванню).
- Timeout за замовчуванням 60 с — LM Studio на слабшому ноуті може рахувати
  довго, але не треба чекати годинами.
- `requests` — опційна залежність. Якщо бібліотека не встановлена,
  провайдер просто рапортує `available()=False`.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .logic_ai_adapter import (
    AIProvider,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ProviderCapabilities,
    ToolCall,
    UsageInfo,
)

try:  # опційна залежність
    import requests as _requests  # type: ignore[import]

    _REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _requests = None  # type: ignore[assignment]
    _REQUESTS_AVAILABLE = False


DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRIES = 3
RETRYABLE_STATUSES = (408, 425, 429, 500, 502, 503, 504)


# ---------------------------------------------------------------------------
# Low-level HTTP helpers (легко мокаються в тестах)
# ---------------------------------------------------------------------------


@dataclass
class HTTPResponse:
    """Уніфікована обгортка над тим, що повертає `requests`/`aiohttp`/мок."""

    status: int
    body: Any
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300


HTTPClient = Callable[[str, Dict[str, str], Dict[str, Any], float], HTTPResponse]


def _default_http_client(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: float,
) -> HTTPResponse:
    """POST JSON на `url` і повернути HTTPResponse.

    Винесено як модульна функція, щоб у тестах можна було підставити свою.
    """
    if not _REQUESTS_AVAILABLE:  # pragma: no cover - tested via injection
        return HTTPResponse(status=0, body=None, error="requests not installed")
    try:
        r = _requests.post(url, headers=headers, json=payload, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - будь-яка мережева помилка
        return HTTPResponse(status=0, body=None, error=f"{type(exc).__name__}: {exc}")
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        body = {"raw_text": r.text}
    return HTTPResponse(status=r.status_code, body=body)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider(AIProvider):
    """HTTP-адаптер до будь-якого OpenAI-сумісного бекенду."""

    name = "openai-compatible"
    display_name = "OpenAI-compatible"

    def __init__(
        self,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_RETRIES,
        http_client: Optional[HTTPClient] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._http: HTTPClient = http_client or _default_http_client
        self._sleep = sleep_fn

    # ----- AIProvider API -----

    def available(self) -> bool:
        if not _REQUESTS_AVAILABLE and self._http is _default_http_client:
            return False
        return True

    def chat(self, request: ChatRequest) -> ChatResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = self._build_payload(request)
        last_error = "no attempts made"

        for attempt in range(self.max_retries):
            resp = self._http(url, headers, payload, self.timeout)

            if resp.ok:
                return self._parse_success(resp.body, request)

            # error path — вирішуємо, чи ретраїти
            retry = self._should_retry(resp)
            last_error = self._format_error(resp)

            if retry and attempt < self.max_retries - 1:
                backoff = 2 ** attempt  # 1, 2, 4, 8 ...
                self._sleep(backoff)
                continue
            break

        return ChatResponse(
            provider=self.name,
            model=payload["model"],
            finish_reason="error",
            error=last_error,
        )

    # ----- Internals -----

    def _build_payload(self, request: ChatRequest) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": request.model or self.model,
            "messages": [self._serialize_message(m) for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters or {"type": "object"},
                    },
                }
                for t in request.tools
            ]
        return payload

    def _serialize_message(self, msg: ChatMessage) -> Dict[str, Any]:
        out: Dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.name:
            out["name"] = msg.name
        return out

    def _should_retry(self, resp: HTTPResponse) -> bool:
        if resp.error is not None:
            # мережева/парсингова помилка — ретраїмо
            return True
        return resp.status in RETRYABLE_STATUSES

    def _format_error(self, resp: HTTPResponse) -> str:
        if resp.error:
            return f"network: {resp.error}"
        body_msg = ""
        if isinstance(resp.body, dict):
            err_block = resp.body.get("error")
            if isinstance(err_block, dict):
                body_msg = err_block.get("message") or err_block.get("type") or ""
            elif isinstance(err_block, str):
                body_msg = err_block
        return f"http {resp.status}{': ' + body_msg if body_msg else ''}"

    def _parse_success(self, body: Any, request: ChatRequest) -> ChatResponse:
        if not isinstance(body, dict):
            return ChatResponse(
                provider=self.name,
                finish_reason="error",
                error=f"bad payload shape: {type(body).__name__}",
            )
        choices = body.get("choices") or []
        if not choices:
            return ChatResponse(
                provider=self.name,
                finish_reason="error",
                error="no choices in response",
            )
        first = choices[0]
        message = first.get("message") or {}
        content = message.get("content") or ""
        finish_reason = first.get("finish_reason") or "stop"

        tool_calls: List[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                import json

                try:
                    args = json.loads(args)
                except Exception:  # noqa: BLE001
                    args = {"_raw": args}
            tool_calls.append(ToolCall(name=name, arguments=args or {}))

        usage_block = body.get("usage") or {}
        prompt_tokens = int(usage_block.get("prompt_tokens") or 0)
        completion_tokens = int(usage_block.get("completion_tokens") or 0)
        total_tokens = int(
            usage_block.get("total_tokens") or prompt_tokens + completion_tokens
        )
        cost = self.estimate_cost(prompt_tokens, completion_tokens)

        return ChatResponse(
            content=content,
            provider=self.name,
            model=body.get("model", request.model or self.model),
            finish_reason=finish_reason,
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
            ),
            tool_calls=tool_calls,
            raw=body,
        )


# ---------------------------------------------------------------------------
# Preset factories
# ---------------------------------------------------------------------------


def lmstudio_provider(
    *,
    base_url: str = "http://localhost:1234/v1",
    model: str = "local-model",
    name: str = "lmstudio",
    display_name: str = "LM Studio (local)",
    priority: int = 80,
    **kwargs: Any,
) -> OpenAICompatibleProvider:
    """Пресет для LM Studio. Жодного API-ключа, повністю offline-friendly."""
    caps = kwargs.pop("capabilities", None) or ProviderCapabilities(
        chat=True,
        tools=True,
        offline=True,
        max_context=8192,
    )
    return OpenAICompatibleProvider(
        base_url=base_url,
        api_key=None,
        model=model,
        name=name,
        display_name=display_name,
        priority=priority,
        capabilities=caps,
        **kwargs,
    )


def ollama_provider(
    *,
    base_url: str = "http://localhost:11434/v1",
    model: str = "llama3.2",
    name: str = "ollama",
    display_name: str = "Ollama (local)",
    priority: int = 85,
    **kwargs: Any,
) -> OpenAICompatibleProvider:
    """Пресет для Ollama з OpenAI-shim-ом."""
    caps = kwargs.pop("capabilities", None) or ProviderCapabilities(
        chat=True,
        tools=True,
        offline=True,
        max_context=8192,
    )
    return OpenAICompatibleProvider(
        base_url=base_url,
        api_key=None,
        model=model,
        name=name,
        display_name=display_name,
        priority=priority,
        capabilities=caps,
        **kwargs,
    )


def openai_provider(
    *,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
    name: str = "openai",
    display_name: str = "OpenAI",
    priority: int = 50,
    cost_per_1k_prompt: float = 0.00015,  # gpt-4o-mini orientation
    cost_per_1k_completion: float = 0.0006,
    **kwargs: Any,
) -> OpenAICompatibleProvider:
    """Пресет для справжнього OpenAI. Якщо `api_key` не передано — бере з env."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    caps = kwargs.pop("capabilities", None) or ProviderCapabilities(
        chat=True,
        tools=True,
        vision=True,
        streaming=True,
        max_context=128_000,
    )
    return OpenAICompatibleProvider(
        api_key=key,
        model=model,
        base_url=base_url,
        name=name,
        display_name=display_name,
        priority=priority,
        cost_per_1k_prompt=cost_per_1k_prompt,
        cost_per_1k_completion=cost_per_1k_completion,
        capabilities=caps,
        **kwargs,
    )
