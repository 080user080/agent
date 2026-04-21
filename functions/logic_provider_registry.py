"""ProviderRegistry — реєстр ШІ-провайдерів + вибір за capability/вартістю.

Phase 9 / J2. Центральна точка доступу до всіх `AIProvider`-ів, відомих
агенту. Оркестратор (J4) через неї питає «дай мені провайдер що вміє vision
і коштує найменше», а також пропонує fallback-ланцюжок коли основний
провайдер впав.

Функціонал:
- `register` / `unregister` / `get` / `list`.
- `select` — пошук найкращого за вимогами + sort key.
- `select_many` — fallback-ланцюжок (primary + alternatives).
- `chat` — hi-level shortcut: вибрати провайдер і одразу зробити виклик;
  при помилці — автоматично спробувати наступного по fallback-ланцюгу
  (`max_retries` штук).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .logic_ai_adapter import (
    AIProvider,
    ChatRequest,
    ChatResponse,
)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


@dataclass
class SelectionCriteria:
    """Критерії вибору провайдера.

    - `requires` — subset ProviderCapabilities полів, які мають бути
      задоволені (див. `ProviderCapabilities.satisfies`).
    - `prefer_cheapest` — сортувати за ціною prompt+completion по 1k.
    - `prefer_offline` — offline-провайдери ставити першими (для
      приватних/секретних даних).
    - `exclude` — імена провайдерів, яких не використовувати.
    - `prefer` — імена, які ставити першими, якщо наявні.
    """

    requires: Dict[str, Any] = field(default_factory=dict)
    prefer_cheapest: bool = False
    prefer_offline: bool = False
    exclude: List[str] = field(default_factory=list)
    prefer: List[str] = field(default_factory=list)


@dataclass
class ChatAttempt:
    """Запис про одну спробу у `registry.chat()` з fallback-ланцюгом."""

    provider: str
    ok: bool
    error: str = ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ProviderRegistry:
    """Сховище AIProvider-ів + критеріальний вибір."""

    def __init__(self) -> None:
        self._providers: Dict[str, AIProvider] = {}
        self._lock = threading.Lock()

    # ----- CRUD ----------------------------------------------------------

    def register(self, provider: AIProvider, *, overwrite: bool = False) -> None:
        with self._lock:
            if not overwrite and provider.name in self._providers:
                raise ValueError(
                    f"Provider {provider.name!r} already registered; "
                    "use overwrite=True to replace"
                )
            self._providers[provider.name] = provider

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._providers.pop(name, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._providers.clear()

    def get(self, name: str) -> Optional[AIProvider]:
        with self._lock:
            return self._providers.get(name)

    def list_names(self) -> List[str]:
        with self._lock:
            return list(self._providers.keys())

    def list_providers(self) -> List[AIProvider]:
        with self._lock:
            return list(self._providers.values())

    def describe_all(self) -> List[Dict[str, Any]]:
        return [p.describe() for p in self.list_providers()]

    # ----- Selection -----------------------------------------------------

    def select(
        self,
        criteria: Optional[SelectionCriteria] = None,
    ) -> Optional[AIProvider]:
        """Повертає найкращого провайдера або None, якщо жодного не знайдено."""
        many = self.select_many(criteria, limit=1)
        return many[0] if many else None

    def select_many(
        self,
        criteria: Optional[SelectionCriteria] = None,
        *,
        limit: Optional[int] = None,
    ) -> List[AIProvider]:
        """Повертає відфільтрований та відсортований список провайдерів.

        Сортування:
          1) `prefer` — за порядком у списку (явні improvements нагору);
          2) `prefer_offline` (якщо True) — offline вище;
          3) `prefer_cheapest` (якщо True) — дешевше вище;
          4) `priority` (нижче = вище пріоритет);
          5) `name` — детермінований tiebreaker.
        """
        criteria = criteria or SelectionCriteria()
        filtered = []
        for provider in self.list_providers():
            if provider.name in criteria.exclude:
                continue
            if not provider.capabilities.satisfies(criteria.requires):
                continue
            if not provider.available():
                continue
            filtered.append(provider)

        def sort_key(p: AIProvider):
            try:
                prefer_rank = criteria.prefer.index(p.name)
            except ValueError:
                prefer_rank = len(criteria.prefer)
            offline_rank = (
                0 if (criteria.prefer_offline and p.capabilities.offline) else 1
            )
            cost = p.cost_per_1k_prompt + p.cost_per_1k_completion
            cost_rank = cost if criteria.prefer_cheapest else 0
            return (prefer_rank, offline_rank, cost_rank, p.priority, p.name)

        filtered.sort(key=sort_key)
        if limit is not None:
            filtered = filtered[:limit]
        return filtered

    # ----- Fallback chat -------------------------------------------------

    def chat(
        self,
        request: ChatRequest,
        *,
        criteria: Optional[SelectionCriteria] = None,
        max_retries: int = 3,
        on_attempt: Optional[Callable[[ChatAttempt], None]] = None,
    ) -> ChatResponse:
        """Shortcut: вибрати провайдера і одразу зробити chat()."""
        providers = self.select_many(criteria)
        if not providers:
            resp = ChatResponse(
                finish_reason="error",
                error="no providers match criteria",
            )
            if on_attempt:
                on_attempt(ChatAttempt(provider="", ok=False, error=resp.error))
            return resp

        last_response: ChatResponse = ChatResponse(
            finish_reason="error",
            error="no attempts made",
        )
        for provider in providers[: max_retries + 1]:
            try:
                resp = provider.chat(request)
            except Exception as exc:  # noqa: BLE001
                resp = ChatResponse(
                    provider=provider.name,
                    finish_reason="error",
                    error=f"{type(exc).__name__}: {exc}",
                )
            last_response = resp
            attempt = ChatAttempt(
                provider=provider.name,
                ok=resp.ok,
                error=resp.error,
            )
            if on_attempt:
                on_attempt(attempt)
            if resp.ok:
                return resp
            # інакше — пробуємо наступного з fallback-ланцюга
        return last_response


# ---------------------------------------------------------------------------
# Module-level default registry (DI-friendly)
# ---------------------------------------------------------------------------


_default_registry: Optional[ProviderRegistry] = None
_default_lock = threading.Lock()


def get_default_registry() -> ProviderRegistry:
    """Лейзі-ініт shared-реєстру на процес.

    Потрібен для сценаріїв, де UI / CLI / watcher доставляють однаковий
    pool провайдерів. Для тестів завжди робіть власний `ProviderRegistry()`.
    """
    global _default_registry
    with _default_lock:
        if _default_registry is None:
            _default_registry = ProviderRegistry()
        return _default_registry


def reset_default_registry() -> None:
    """Скинути shared-реєстр (використовується в тестах)."""
    global _default_registry
    with _default_lock:
        _default_registry = None
