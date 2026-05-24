# functions/llm/streaming_buffer.py
"""StreamingBuffer — підрахунок токенів у реальному часі під час стрімінгу.

Принцип роботи:
- Під час стрімінгу кожен чанк тексту дає грубу оцінку токенів `chars // 4`
- Ця оцінка передається в callback для live-оновлення progress bar
- Після завершення стрімінгу реальне `usage` (якщо є) замінює грубу оцінку
"""
from __future__ import annotations

from typing import Callable, Optional


class StreamingBuffer:
    """Буфер стрімінгу з live-оцінкою токенів.

    Attributes:
        total_chars: Загальна кількість символів, отриманих під час стрімінгу
        estimated_tokens: Груба оцінка токенів (total_chars // 4)
        _on_status: Callback(status_text) для оновлення статус-бару
        _on_context_update: Callback(used_tokens, limit, model) для оновлення бару контексту
        _context_limit: Ліміт контексту моделі (береться з endpoint)
        _model: Назва активної моделі
    """

    def __init__(
        self,
        on_status: Optional[Callable[[str], None]] = None,
        on_context_update: Optional[Callable[[int, int, str], None]] = None,
        context_limit: int = 0,
        model: str = "",
    ):
        self.total_chars = 0
        self.estimated_tokens = 0
        self._on_status = on_status
        self._on_context_update = on_context_update
        self._context_limit = context_limit
        self._model = model

    def update_context_limits(self, context_limit: int, model: str) -> None:
        """Оновити ліміт контексту та назву моделі (наприклад, при старті стрімінгу)."""
        self._context_limit = context_limit
        self._model = model

    def add_chunk(self, chunk: str) -> int:
        """Додати чанк тексту, оновити оцінку токенів і викликати callback.

        Args:
            chunk: Фрагмент тексту з стрімінгу

        Returns:
            Поточна оцінка токенів (estimated_tokens)
        """
        if not chunk:
            return self.estimated_tokens

        self.total_chars += len(chunk)
        self.estimated_tokens = self.total_chars // 4  # груба оцінка

        # Оновлюємо статус-бар (текстове повідомлення)
        if self._on_status:
            self._on_status(
                f"⏳ Стрімінг... ~{self.estimated_tokens} токенів"
            )

        # Оновлюємо прогрес-бар контексту (live)
        if self._on_context_update and self._context_limit > 0:
            self._on_context_update(
                self.estimated_tokens, self._context_limit, self._model
            )

        return self.estimated_tokens

    def finish(self, real_usage: Optional[dict] = None) -> int:
        """Завершити стрімінг, замінити оцінку реальним usage якщо є.

        Args:
            real_usage: Словник з реальними usage даними
                       (наприклад, {"total_tokens": 150, "completion_tokens": 100})
                       Якщо None, залишається груба оцінка.

        Returns:
            Фінальна кількість completion токенів
        """
        if real_usage:
            completion_tokens = real_usage.get("completion_tokens", 0)
            total_tokens = real_usage.get("total_tokens", 0)

            if completion_tokens > 0:
                self.estimated_tokens = completion_tokens

            # Оновлюємо бар з реальними даними
            if self._on_context_update and self._context_limit > 0:
                used = total_tokens if total_tokens > 0 else completion_tokens
                self._on_context_update(
                    used, self._context_limit, self._model
                )

            if self._on_status:
                if completion_tokens > 0:
                    self._on_status(
                        f"✅ Стрімінг завершено — {completion_tokens} токенів"
                    )
                else:
                    self._on_status("✅ Стрімінг завершено")

            return completion_tokens

        # Якщо реального usage немає — залишаємо оцінку
        if self._on_context_update and self._context_limit > 0:
            self._on_context_update(
                self.estimated_tokens, self._context_limit, self._model
            )

        if self._on_status:
            self._on_status(
                f"✅ Стрімінг завершено — ~{self.estimated_tokens} токенів (оцінка)"
            )

        return self.estimated_tokens

    def reset(self) -> None:
        """Скинути буфер."""
        self.total_chars = 0
        self.estimated_tokens = 0

    @property
    def current_status(self) -> str:
        """Поточний статус для відображення."""
        return f"~{self.estimated_tokens} токенів (стрімінг)" if self.estimated_tokens > 0 else ""