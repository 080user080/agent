"""Agent Skills — високорівневі абстракції над базовими діями.

Архітектура:
- Кожен skill — це клас, що наслідує BaseSkill.
- Skills можуть використовувати інші skills (композиція).
- Skills реєструються в SkillRegistry для автоматичного виявлення.
- Skills logging через стандартний `logging.getLogger("skills.xxx")`.
"""

from __future__ import annotations

from .base import BaseSkill, SkillResult, SkillError
from .registry import SkillRegistry
from .browser_skills import OpenBrowser, SearchGoogle, FillForm

__all__ = [
    "BaseSkill",
    "SkillResult",
    "SkillError",
    "SkillRegistry",
    "OpenBrowser",
    "SearchGoogle",
    "FillForm",
]