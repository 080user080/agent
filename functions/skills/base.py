"""BaseSkill — базова абстракція для високорівневих навичок агента.

Кожен skill:
- Має унікальне ім'я (name) та опис (description).
- Приймає контекст виконання (execution context) з доступом до registry.
- Повертає SkillResult зі статусом, даними та метаданими.
- Може логувати прогрес через стандартний logging.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillResult:
    """Результат виконання skill-у.

    Attributes:
        success: True якщо виконання успішне.
        data: Корисні дані результату (напр. текст, знайдені елементи).
        error: Текст помилки (якщо success=False).
        metadata: Додаткова інформація (час виконання, проміжні кроки).
    """
    success: bool = True
    data: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillError(Exception):
    """Виняток для помилок виконання skill-у.

    Містить код помилки (error_code) для програмної обробки.
    """
    def __init__(
        self, message: str, error_code: str = "SKILL_ERROR",
    ):
        super().__init__(message)
        self.error_code = error_code


class BaseSkill:
    """Абстрактний базовий клас для всіх skill-ів.

    Використання:
        class MySkill(BaseSkill):
            name = "my_skill"
            description = "Опис мого скілу"

            async def execute(self, ctx, **kwargs) -> SkillResult:
                # реалізація
                return SkillResult(success=True, data="done")
    """

    name: str = ""
    description: str = ""
    dependencies: List[str] = field(default_factory=list)  # noqa: F811

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(f"{type(self).__name__}: name is required")
        self.logger = logging.getLogger(f"skills.{self.name}")

    async def execute(
        self,
        ctx: Any,
        **kwargs: Any,
    ) -> SkillResult:
        """Виконати skill.

        Args:
            ctx: Контекст виконання (SkillContext) з доступом до registry,
                 tools, тощо.
            **kwargs: Параметри skill-у (залежать від конкретного скілу).

        Returns:
            SkillResult з результатом виконання.

        Raises:
            SkillError: У випадку критичної помилки.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.execute() must be overridden",
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"


__all__ = [
    "BaseSkill",
    "SkillResult",
    "SkillError",
]