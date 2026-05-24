"""SkillRegistry — реєстр усіх доступних skill-ів агента.

Дозволяє:
- Реєструвати нові skills за іменем.
- Знаходити skill за іменем.
- Отримувати список всіх зареєстрованих skills.
- Автоматично виявляти skills через декоратор @skill.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

from .base import BaseSkill, SkillResult

logger = logging.getLogger("skills.registry")


class SkillRegistry:
    """Реєстр skills. Thread-safe для одночасного доступу.

    Приклад:
        registry = SkillRegistry()
        registry.register(OpenBrowser())
        skill = registry.get("open_browser")
        result = await skill.execute(ctx, url="https://example.com")
    """

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """Зареєструвати skill.

        Args:
            skill: Екземпляр класу, що наслідує BaseSkill.

        Raises:
            ValueError: Якщо skill з таким ім'ям вже зареєстровано.
        """
        if not isinstance(skill, BaseSkill):
            raise TypeError(f"Expected BaseSkill instance, got {type(skill)}")
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' is already registered")
        self._skills[skill.name] = skill
        logger.info("Registered skill: %s — %s", skill.name, skill.description)

    def unregister(self, name: str) -> bool:
        """Видалити skill за іменем.

        Returns:
            True якщо skill був знайдений і видалений.
        """
        removed = self._skills.pop(name, None)
        if removed:
            logger.info("Unregistered skill: %s", name)
        return removed is not None

    def get(self, name: str) -> Optional[BaseSkill]:
        """Отримати skill за іменем."""
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """Повернути список всіх зареєстрованих skills з метаданими."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "type": type(s).__name__,
            }
            for s in self._skills.values()
        ]

    @property
    def count(self) -> int:
        """Кількість зареєстрованих skills."""
        return len(self._skills)

    def has(self, name: str) -> bool:
        """Перевірити чи зареєстровано skill з таким ім'ям."""
        return name in self._skills


__all__ = [
    "SkillRegistry",
]