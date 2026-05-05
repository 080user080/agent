"""Вкладка логів."""
from datetime import datetime
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from .base_tab import BaseTab
from .constants import LOG_LEVELS, TEST_LOGS, LOG_LEVEL_COLORS


class LogsTab(BaseTab):
    """Вкладка логів."""

    def _build_content(self, layout):
        """Побудувати контент вкладки логів."""
        # Фільтри
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Рівень:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(LOG_LEVELS)
        filter_layout.addWidget(self.level_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Пошук...")
        filter_layout.addWidget(self.search_input)

        self.clear_button = QPushButton("Очистити")
        self.clear_button.clicked.connect(self.clear_logs)
        filter_layout.addWidget(self.clear_button)

        layout.addLayout(filter_layout)

        # Таблиця логів
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(4)
        self.logs_table.setHorizontalHeaderLabels(["Час", "Рівень", "Модуль", "Повідомлення"])
        self.logs_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.logs_table)

        # Додати тестові логи
        self.add_test_logs()

    def add_test_logs(self):
        """Додати тестові логи для демонстрації."""
        for level, module, message in TEST_LOGS:
            self.add_log(level, module, message)

    def add_log(self, level: str, module: str, message: str):
        """Додати лог в таблицю."""
        row = self.logs_table.rowCount()
        self.logs_table.insertRow(row)

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs_table.setItem(row, 0, QTableWidgetItem(timestamp))
        self.logs_table.setItem(row, 1, QTableWidgetItem(level))
        self.logs_table.setItem(row, 2, QTableWidgetItem(module))
        self.logs_table.setItem(row, 3, QTableWidgetItem(message))

        # Кольорове виділення
        color_hex = LOG_LEVEL_COLORS.get(level, "#000000")
        foreground = QColor(color_hex)
        for col in range(4):
            self.logs_table.item(row, col).setForeground(foreground)

    def clear_logs(self):
        """Очистити таблицю логів."""
        self.logs_table.setRowCount(0)
