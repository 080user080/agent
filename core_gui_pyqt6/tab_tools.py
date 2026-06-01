"""ToolsTab — вкладка інструментів для PyQt6.

Завантажує список зареєстрованих інструментів з FunctionRegistry при відкритті.
Кнопка "Виконати" показує QMessageBox з підказкою ввести команду в чаті.
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QFrame, QMessageBox,
)

from .base_tab import BaseTab


class ToolsTab(BaseTab):
    """Вкладка інструментів: таблиця, оновлення, виконання (тільки читання)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tools_data: list[dict] = []

        # Створюються в setup_ui
        self.table: QTableWidget | None = None

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Верхня панель
        top_frame = QFrame()
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)

        refresh_btn = QPushButton("🔄 Оновити список")
        refresh_btn.clicked.connect(self._load_tools)
        top_layout.addWidget(refresh_btn)

        exec_btn = QPushButton("▶ Виконати")
        exec_btn.clicked.connect(self._on_execute_tool)
        top_layout.addWidget(exec_btn)

        top_layout.addStretch()
        layout.addWidget(top_frame)

        # Таблиця інструментів
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Назва", "Опис", "Ризик", "Статус"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        # Завантажити інструменти
        self._load_tools()

    def get_title(self) -> str:
        return "🔧 Інструменти"

    def refresh(self) -> None:
        """Оновити список при перемиканні вкладки."""
        self._load_tools()

    # ─── Завантаження інструментів ────────────────────────────────────────────

    def _load_tools(self) -> None:
        """Завантажити список інструментів з FunctionRegistry."""
        self._tools_data.clear()

        # 1. Спроба отримати з FunctionRegistry
        try:
            from functions.tools.core_tool_runtime import FunctionRegistry  # type: ignore
            registry = FunctionRegistry()
            tools = registry.list_tools() if hasattr(registry, 'list_tools') else []

            for tool in tools:
                if isinstance(tool, dict):
                    self._tools_data.append(tool)
                elif hasattr(tool, '__dict__'):
                    self._tools_data.append(tool.__dict__)
                else:
                    self._tools_data.append({"name": str(tool)})
        except Exception:
            pass

        # 2. Fallback — спроба отримати через main_window.assistant
        if not self._tools_data:
            mw = self._main_window
            if mw and hasattr(mw, 'assistant') and mw.assistant:
                try:
                    core = mw.assistant
                    if hasattr(core, 'list_tools'):
                        tools = core.list_tools()
                        if isinstance(tools, list):
                            for tool in tools:
                                if isinstance(tool, dict):
                                    self._tools_data.append(tool)
                except Exception:
                    pass

        self._update_table()

    def _update_table(self) -> None:
        """Заповнити таблицю з поточними даними."""
        if not self.table:
            return

        self.table.setRowCount(len(self._tools_data))

        for i, tool in enumerate(self._tools_data):
            name = tool.get("name", tool.get("action", "?"))
            desc = tool.get("description", tool.get("desc", ""))
            risk = tool.get("risk", tool.get("risk_level", "unknown"))
            status = tool.get("status", "available")

            self.table.setItem(i, 0, QTableWidgetItem(str(name)))
            self.table.setItem(i, 1, QTableWidgetItem(str(desc)))

            risk_item = QTableWidgetItem(str(risk).upper())
            # Колір для ризику
            risk_color = QColor("#2e7d32")  # зелений — low
            if str(risk).lower() in ("high", "critical"):
                risk_color = QColor("#c62828")  # червоний
            elif str(risk).lower() == "medium":
                risk_color = QColor("#e65100")  # помаранчевий
            risk_item.setForeground(risk_color)
            self.table.setItem(i, 2, risk_item)

            status_item = QTableWidgetItem(str(status))
            # Колір для статусу
            if str(status).lower() == "available":
                status_item.setForeground(QColor("#2e7d32"))
            elif str(status).lower() == "disabled":
                status_item.setForeground(QColor("#888888"))
            self.table.setItem(i, 3, status_item)

        self.table.resizeRowsToContents()

    # ─── Виконання інструменту ────────────────────────────────────────────────

    def _on_execute_tool(self) -> None:
        """Показати підказку: виконання через чат."""
        QMessageBox.information(
            self,
            "Виконання інструменту",
            "Введіть команду в чаті для виконання інструменту.\n\n"
            "Наприклад: \"відкрий блокнот\" або \"натисни кнопку OK\"",
        )