"""TaskSpec — структурований опис задачі для декомпозиції (Phase 13).

Приймає довільне ТЗ і перетворює його на структурований Plan з milestones.
Це S3: TaskSpec → compile() MVP.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("task_spec")


class Domain(Enum):
    """Домен задачі — визначає доступні інструменти та стратегії."""
    CODE = "code"  # Написання коду, рефакторинг, тести
    PHOTO = "photo"  # Обробка зображень, ComfyUI, Photoshop
    PRESENTATION = "presentation"  # PowerPoint, Google Slides
    WEB = "web"  # Браузерні задачі, веб-скрапінг
    DESKTOP = "desktop"  # Загальні десктоп задачі (файли, вікна)
    MIXED = "mixed"  # Комбіновані задачі
    UNKNOWN = "unknown"


class Priority(Enum):
    """Пріоритет задачі."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskSpec:
    """Структурований опис задачі.

    Приклад ТЗ: "Напиши функцію сортування списку на Python з тестами"
    → TaskSpec(domain=CODE, description="...", deliverables=["sort_function.py", "tests/"])
    """
    # Основні поля
    description: str  # Оригінальне ТЗ від користувача
    domain: Domain = Domain.UNKNOWN
    priority: Priority = Priority.MEDIUM

    # Deliverables — що має бути створено
    deliverables: List[str] = field(default_factory=list)  # ["file.py", "folder/", "report.pdf"]

    # Constraints — обмеження
    max_duration_seconds: float = 3600.0  # 1 година за замовчуванням
    max_budget_tokens: int = 100000  # Ліміт токенів LLM

    # Context — додатковий контекст
    files_to_modify: List[str] = field(default_factory=list)  # ["src/main.py"]
    tools_allowed: List[str] = field(default_factory=list)  # ["python", "pytest", "git"]
    tools_forbidden: List[str] = field(default_factory=list)  # ["delete", "format"]

    # Milestones — ключові точки виконання
    milestones: List[str] = field(default_factory=list)  # ["write_code", "run_tests", "refactor"]

    # Metadata
    created_at: float = 0.0
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.created_at == 0.0:
            import time
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Конвертувати в dict для LLM."""
        return {
            "description": self.description,
            "domain": self.domain.value,
            "priority": self.priority.value,
            "deliverables": self.deliverables,
            "max_duration_seconds": self.max_duration_seconds,
            "max_budget_tokens": self.max_budget_tokens,
            "files_to_modify": self.files_to_modify,
            "tools_allowed": self.tools_allowed,
            "tools_forbidden": self.tools_forbidden,
            "milestones": self.milestones,
            "tags": self.tags,
        }


@dataclass
class CompiledPlan:
    """Результат compile() — структурований план виконання."""
    task_spec: TaskSpec
    steps: List[Dict[str, Any]] = field(default_factory=list)  # Кроки для TaskRunner
    milestones: List[Dict[str, Any]] = field(default_factory=list)  # {"name": "...", "step_index": 5}
    estimated_duration_seconds: float = 0.0
    estimated_tokens: int = 0
    validation_rules: List[str] = field(default_factory=list)  # Правила валідації результату

    def to_dict(self) -> Dict[str, Any]:
        """Конвертувати в dict."""
        return {
            "task_spec": self.task_spec.to_dict(),
            "steps": self.steps,
            "milestones": self.milestones,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "estimated_tokens": self.estimated_tokens,
            "validation_rules": self.validation_rules,
        }


class TaskSpecCompiler:
    """Компілятор TaskSpec → CompiledPlan.

    Використовує LLM для декомпозиції ТЗ на кроки з milestones.
    """

    def __init__(self, assistant, registry):
        self.assistant = assistant
        self.registry = registry

    def _detect_domain(self, description: str) -> Domain:
        """Авто-детекція домену з опису."""
        desc_lower = description.lower()

        # Ключові слова для кожного домену
        domain_keywords = {
            Domain.CODE: ["код", "функція", "клас", "python", "javascript", "refactor", "тест", "test", "git", "коміт", "code", "function"],
            Domain.PHOTO: ["фото", "зображення", "картинка", "comfyui", "photoshop", "обробити", "ресайз", "кроп", "photo", "image", "resize", "crop"],
            Domain.PRESENTATION: ["презентація", "презентацію", "слайд", "powerpoint", "pptx", "доклад", "звіт", "presentation", "slide", "report"],
            Domain.WEB: ["браузер", "сайт", "сторінка", "скрапінг", "скачати", "url", "chrome", "browser", "website", "scraping"],
            Domain.DESKTOP: ["файл", "папка", "вікно", "програма", "відкрити", "закрити", "скріншот", "file", "folder", "window", "program", "screenshot"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                return domain

        return Domain.UNKNOWN

    def parse(self, description: str, context: Optional[Dict[str, Any]] = None) -> TaskSpec:
        """Парсити текстове ТЗ в TaskSpec."""
        context = context or {}

        # Авто-детекція домену
        domain = self._detect_domain(description)

        # Базовий TaskSpec
        spec = TaskSpec(
            description=description,
            domain=domain,
            priority=context.get("priority", Priority.MEDIUM),
            max_duration_seconds=context.get("max_duration_seconds", 3600.0),
        )

        # Якщо є deliverables в контексті
        if "deliverables" in context:
            spec.deliverables = context["deliverables"]

        # Якщо є milestones в контексті
        if "milestones" in context:
            spec.milestones = context["milestones"]

        logger.info(f"TaskSpec parsed: domain={domain}, deliverables={len(spec.deliverables)}")
        return spec

    def compile(self, spec: TaskSpec) -> CompiledPlan:
        """Компілювати TaskSpec в CompiledPlan з кроками.

        Використовує LLM для декомпозиції.
        """
        # Поки використовуємо існуючий Planner для створення плану
        planner = getattr(self.assistant, 'planner', None)
        if not planner:
            logger.warning("Planner недоступний, повертаю пустий план")
            return CompiledPlan(task_spec=spec)

        # Створити план через Planner
        steps = planner.create_plan(spec.description)
        if not steps:
            logger.warning("Planner повернув порожній план")
            return CompiledPlan(task_spec=spec)

        # Створити CompiledPlan
        plan = CompiledPlan(
            task_spec=spec,
            steps=steps,
        )

        # Додати milestones якщо є в spec
        for i, milestone_name in enumerate(spec.milestones):
            # Знайти крок який відповідає milestone
            if i < len(steps):
                plan.milestones.append({
                    "name": milestone_name,
                    "step_index": i,
                })

        # Оцінка тривалості (приблизно 30с на крок)
        plan.estimated_duration_seconds = len(steps) * 30
        plan.estimated_tokens = len(steps) * 1000  # Приблизно 1000 токенів на крок

        logger.info(f"Compiled plan: {len(steps)} steps, {len(plan.milestones)} milestones")
        return plan

    def validate_plan(self, plan: CompiledPlan) -> tuple[bool, str]:
        """Валідація CompiledPlan."""
        if not plan.steps:
            return False, "План порожній"

        if len(plan.steps) > 100:
            return False, "Занадто багато кроків (>100)"

        spec = plan.task_spec
        if spec.max_duration_seconds > 0 and plan.estimated_duration_seconds > spec.max_duration_seconds:
            return False, f"Очікувана тривалість ({plan.estimated_duration_seconds}s) перевищує ліміт ({spec.max_duration_seconds}s)"

        return True, "План валідний"
