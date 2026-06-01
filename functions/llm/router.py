"""Request Router — класифікація запитів за типом задачі.

Рівень 1 в архітектурі оркестрації ШІ:
- Класифікує запит за типом: CODE, DEBUG, GUI, WEB, GENERAL, QUICK
- Вибирає відповідний провайдер з fallback ланцюгом
- Keyword-based класифікація (швидко, без LLM)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class TaskType(Enum):
    """Тип задачі для маршрутизації."""
    CODE = "code"
    DEBUG = "debug"
    GUI = "gui"
    WEB = "web"
    GENERAL = "general"
    QUICK = "quick"


@dataclass
class RoutingDecision:
    """Рішення маршрутизації."""
    task_type: TaskType
    primary_provider_id: str
    fallback_chain: List[str]
    skip_llm: bool = False  # для QUICK задач (без LLM взагалі)
    requires_tools: bool = False  # чи потрібні tools (GUI, WEB, CODE)
    context_budget: int = 2000  # токени для conversation history


class RequestRouter:
    """Маршрутизатор запитів на основі keyword-based класифікації."""

    # Ключові слова для класифікації (порядок важливий)
    CODE_SIGNALS = [
        "створи файл", "напиши код", "функція", "клас",
        "def ", "import ", "create file", "write code",
        "реалізуй", "додай метод", "напиши скрипт",
        "функц", "клас", "скрипт", "програма"
    ]
    DEBUG_SIGNALS = [
        "помилка", "error", "traceback", "виправ",
        "debug", "fix", "crash",
        "exception", "не запускається", "баг",
        "не працює"  # переміщено вниз, щоб WEB мав пріоритет
    ]
    GUI_SIGNALS = [
        "клікни", "відкрий програму", "вікно", "скріншот",
        "натисни", "click", "window", "gui",
        "переключи", "закрий вікно", "знайди кнопку",
        "відкрий блокнот", "відкрий", "закрий"
    ]
    WEB_SIGNALS = [
        "браузер", "відкрий сайт", "google", "browser", "url",
        "перейди на", "відкри сторінку", "веб",
        "сайт", "сторінка"
    ]
    QUICK_SIGNALS = [
        "привіт", "дякую", "скільки", "який", "що таке",
        "хто", "де", "коли", "чому"
    ]

    def classify(self, text: str) -> TaskType:
        """Класифікує текст запиту за типом задачі.

        Keyword-based класифікація (швидко, без LLM).
        Порядок перевірки: від специфічного до загального.
        """
        text_lower = text.lower()

        # Порядок важливий — від специфічного до загального
        if any(s in text_lower for s in self.DEBUG_SIGNALS):
            return TaskType.DEBUG
        if any(s in text_lower for s in self.CODE_SIGNALS):
            return TaskType.CODE
        if any(s in text_lower for s in self.WEB_SIGNALS):
            return TaskType.WEB
        if any(s in text_lower for s in self.GUI_SIGNALS):
            return TaskType.GUI
        if any(s in text_lower for s in self.QUICK_SIGNALS):
            return TaskType.QUICK
        return TaskType.GENERAL

    def route(self, text: str, available_providers: dict) -> RoutingDecision:
        """Маршрутизує запит на відповідний провайдер.

        Args:
            text: Текст запиту.
            available_providers: Доступні провайдери {id: provider}.

        Returns:
            RoutingDecision з вибраним провайдером і fallback ланцюгом.
        """
        task_type = self.classify(text)

        # Маппінг: тип задачі → бажаний провайдер (пріоритет)
        preference = {
            TaskType.CODE: ["code_generator", "orchestrator", "debugger"],
            TaskType.DEBUG: ["debugger", "orchestrator", "code_generator"],
            TaskType.GUI: ["orchestrator", "debugger"],  # GUI не потребує спеціалізації
            TaskType.WEB: ["orchestrator", "code_generator"],
            TaskType.GENERAL: ["orchestrator", "code_generator"],
            TaskType.QUICK: ["orchestrator"],
        }

        # Фільтруємо тільки доступні провайдери
        chain = [p for p in preference[task_type] if p in available_providers]

        # Якщо немає доступних провайдерів — fallback на orchestrator
        if not chain:
            chain = ["orchestrator"]

        # Context budget залежить від типу задачі
        context_budget = {
            TaskType.CODE: 4000,  # Код потребує більше контексту
            TaskType.DEBUG: 6000,  # Відладка потребує traceback + history
            TaskType.GUI: 2000,
            TaskType.WEB: 2000,
            TaskType.GENERAL: 3000,
            TaskType.QUICK: 500,
        }[task_type]

        return RoutingDecision(
            task_type=task_type,
            primary_provider_id=chain[0],
            fallback_chain=chain[1:],
            skip_llm=(task_type == TaskType.QUICK),
            requires_tools=task_type in (TaskType.GUI, TaskType.WEB, TaskType.CODE),
            context_budget=context_budget,
        )
