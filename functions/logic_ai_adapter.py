"""AIProvider — абстракція виклику зовнішніх ШІ (API та браузер).

Phase 9 / J1. Це **скелет**: без реальних HTTP/Playwright-викликів. Даємо
чисті data-types (Message / Request / Response / Capabilities), базовий
абстрактний клас `AIProvider`, та дві прості реалізації для тестів —
`EchoProvider` і `ScriptedProvider`. Реальні OpenAI/Anthropic/Google-
адаптери додамо окремими PR, коли з'являться credentials/секрети.

Дизайн-принципи:
- Data-first. Всі DTO — `@dataclass(frozen=False)` щоб легко копіювати/
  серіалізувати.
- Жодних raise-в у бізнес-коді адаптерів. Помилки летять як
  `ChatResponse(finish_reason="error", error=str)`, щоб оркестратор міг
  ретраїти чи перемикатися на fallback-провайдера без try/except скрізь.
- Capabilities — проста flag-модель. Оркестратор (J4) відбиратиме
  провайдер по `requires={"vision": True, "tools": True}`.
- `cost_per_1k` — орієнтовна ціна, щоб `SessionBudget` міг ним платити.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Message / Request / Response
# ---------------------------------------------------------------------------


ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL = "tool"

ALLOWED_ROLES = (ROLE_SYSTEM, ROLE_USER, ROLE_ASSISTANT, ROLE_TOOL)


@dataclass
class ChatMessage:
    role: str
    content: str
    name: Optional[str] = None  # для tool-role (tool-name)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in ALLOWED_ROLES:
            raise ValueError(
                f"Unknown role {self.role!r}; expected one of {ALLOWED_ROLES}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolSpec:
    """Опис доступного tool-call для провайдерів, що підтримують tools."""

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatRequest:
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    tools: List[ToolSpec] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add(self, role: str, content: str) -> "ChatRequest":
        self.messages.append(ChatMessage(role=role, content=content))
        return self


@dataclass
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    content: str = ""
    provider: str = ""
    model: str = ""
    finish_reason: str = "stop"
    usage: UsageInfo = field(default_factory=UsageInfo)
    tool_calls: List[ToolCall] = field(default_factory=list)
    error: str = ""
    raw: Optional[Any] = None

    @property
    def ok(self) -> bool:
        return self.finish_reason != "error" and not self.error


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


@dataclass
class ProviderCapabilities:
    """Що провайдер уміє.

    - `chat` — базовий одно-шотовий виклик (обов'язково у всіх).
    - `streaming` — токен-стрім (коли у вас є UI з typing-індикатором).
    - `tools` — function/tool-calling.
    - `vision` — передача зображень.
    - `code_execution` — виконання коду в пісочниці (як у GPT code-interpreter).
    - `browsing` — має доступ до вебу.
    - `max_context` — скільки токенів контексту тримає.
    - `offline` — можна використовувати без інтернету.
    """

    chat: bool = True
    streaming: bool = False
    tools: bool = False
    vision: bool = False
    code_execution: bool = False
    browsing: bool = False
    max_context: int = 4096
    offline: bool = False

    def satisfies(self, requirements: Dict[str, Any]) -> bool:
        """Перевірка, чи capabilities задовольняють набір вимог.

        `requirements` — підмножина полів `ProviderCapabilities`:
        для bool-полів вимагається True, для int-полів — `>=`.
        """
        for key, wanted in requirements.items():
            if not hasattr(self, key):
                return False
            current = getattr(self, key)
            if isinstance(wanted, bool):
                if wanted and not current:
                    return False
            elif isinstance(wanted, (int, float)):
                if current < wanted:
                    return False
            else:
                if current != wanted:
                    return False
        return True


# ---------------------------------------------------------------------------
# AIProvider (ABC)
# ---------------------------------------------------------------------------


class AIProvider(ABC):
    """Абстрактний провайдер ШІ."""

    name: str = "abstract"
    display_name: str = "Abstract"

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        display_name: Optional[str] = None,
        capabilities: Optional[ProviderCapabilities] = None,
        priority: int = 100,
        cost_per_1k_prompt: float = 0.0,
        cost_per_1k_completion: float = 0.0,
    ):
        if name:
            self.name = name
        if display_name:
            self.display_name = display_name
        self.capabilities = capabilities or ProviderCapabilities()
        self.priority = priority
        self.cost_per_1k_prompt = cost_per_1k_prompt
        self.cost_per_1k_completion = cost_per_1k_completion

    # ----- Public -----

    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse:  # pragma: no cover
        ...

    def available(self) -> bool:  # noqa: D401
        """Чи готовий провайдер (ключі встановлено, сервіс доступний)."""
        return True

    def estimate_tokens(self, request: ChatRequest) -> int:
        """Груба оцінка promp-токенів (len_chars // 4 — досить для MVP)."""
        total_chars = sum(len(m.content) for m in request.messages)
        return max(1, total_chars // 4)

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        prompt = prompt_tokens / 1000 * self.cost_per_1k_prompt
        completion = completion_tokens / 1000 * self.cost_per_1k_completion
        return round(prompt + completion, 6)

    # ----- Diagnostics -----

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "capabilities": asdict(self.capabilities),
            "priority": self.priority,
            "available": self.available(),
            "cost_per_1k_prompt": self.cost_per_1k_prompt,
            "cost_per_1k_completion": self.cost_per_1k_completion,
        }


# ---------------------------------------------------------------------------
# Reference providers (for tests/fallback)
# ---------------------------------------------------------------------------


class EchoProvider(AIProvider):
    """Повертає останнє user-повідомлення префіксом `echo: `.

    Нульові витрати, завжди доступний, корисно для smoke-тестів і як
    fallback, коли всі зовнішні провайдери недоступні.
    """

    name = "echo"
    display_name = "Echo (local)"

    def __init__(self, **kwargs: Any):
        caps = kwargs.pop("capabilities", None) or ProviderCapabilities(
            chat=True, offline=True, max_context=8192
        )
        super().__init__(capabilities=caps, **kwargs)

    def chat(self, request: ChatRequest) -> ChatResponse:
        last_user = next(
            (m for m in reversed(request.messages) if m.role == ROLE_USER),
            None,
        )
        content = f"echo: {last_user.content}" if last_user else "echo: <empty>"
        prompt_tokens = self.estimate_tokens(request)
        completion_tokens = max(1, len(content) // 4)
        return ChatResponse(
            content=content,
            provider=self.name,
            model=request.model or "echo-1",
            finish_reason="stop",
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_usd=self.estimate_cost(prompt_tokens, completion_tokens),
            ),
        )


class ScriptedProvider(AIProvider):
    """Повертає заздалегідь задану послідовність відповідей.

    Використовується в тестах, щоб мокнути реальні API-відповіді.
    """

    name = "scripted"
    display_name = "Scripted (test)"

    def __init__(
        self,
        responses: List[str] | List[ChatResponse],
        *,
        cycle: bool = False,
        **kwargs: Any,
    ):
        caps = kwargs.pop("capabilities", None) or ProviderCapabilities(
            chat=True, offline=True
        )
        super().__init__(capabilities=caps, **kwargs)
        self._responses: List[Any] = list(responses)
        self._cycle = cycle
        self._idx = 0
        self.calls: List[ChatRequest] = []

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.calls.append(request)
        if not self._responses:
            return ChatResponse(
                provider=self.name,
                finish_reason="error",
                error="scripted: no responses configured",
            )
        idx = self._idx
        if self._cycle:
            value = self._responses[idx % len(self._responses)]
        else:
            value = self._responses[min(idx, len(self._responses) - 1)]
        self._idx += 1

        if isinstance(value, ChatResponse):
            return value
        return ChatResponse(
            content=str(value),
            provider=self.name,
            model=request.model or "scripted-1",
            finish_reason="stop",
            usage=UsageInfo(
                prompt_tokens=self.estimate_tokens(request),
                completion_tokens=max(1, len(str(value)) // 4),
                total_tokens=0,
            ),
        )


class CallableProvider(AIProvider):
    """Провайдер, який делегує виклик довільній функції.

    Корисно, коли треба підміняти логіку інкапсуляцією без створення нового
    класу. Функція дістає `ChatRequest`, повертає `str` або `ChatResponse`.
    """

    name = "callable"
    display_name = "Callable"

    def __init__(
        self,
        handler: Callable[[ChatRequest], Any],
        *,
        capabilities: Optional[ProviderCapabilities] = None,
        **kwargs: Any,
    ):
        super().__init__(capabilities=capabilities, **kwargs)
        self._handler = handler

    def chat(self, request: ChatRequest) -> ChatResponse:
        try:
            result = self._handler(request)
        except Exception as exc:  # noqa: BLE001
            return ChatResponse(
                provider=self.name,
                finish_reason="error",
                error=f"{type(exc).__name__}: {exc}",
            )
        if isinstance(result, ChatResponse):
            if not result.provider:
                result.provider = self.name
            return result
        return ChatResponse(
            content=str(result),
            provider=self.name,
            model=request.model or "callable-1",
            finish_reason="stop",
        )
