"""BaseTab — базовий клас для всіх вкладок (без ABC, тільки QWidget)."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QWidget


class BaseTab(QWidget):
    """Базовий клас для вкладки.

    Кожна вкладка наслідує BaseTab і реалізує:
    - setup_ui() — створення віджетів
    - refresh() — оновлення даних при перемиканні
    - get_title() — назва вкладки (для QTabWidget)
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._main_window: Any = None

    def set_main_window(self, mw: Any) -> None:
        """Зберегти посилання на MainWindow для доступу до спільних об'єктів."""
        self._main_window = mw

    def setup_ui(self) -> None:
        """Створити всі віджети вкладки. Має бути перевизначений."""
        raise NotImplementedError("setup_ui must be overridden")

    def refresh(self) -> None:
        """Оновити дані вкладки при перемиканні. За замовчуванням нічого не робить."""

    def get_title(self) -> str:
        """Повернути назву вкладки для QTabWidget."""
        raise NotImplementedError("get_title must be overridden")
