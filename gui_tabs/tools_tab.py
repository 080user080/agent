"""Вкладка інструментів."""
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
)

from .base_tab import BaseTab
from .constants import TEST_TOOLS


class ToolsTab(BaseTab):
    """Вкладка інструментів."""

    def __init__(self, parent=None):
        self.tools_table = None
        self.execute_button = None
        super().__init__(parent)

    def _build_content(self, layout):
        """Побудувати контент вкладки інструментів."""
        # Група: Доступні інструменти
        tools_group = self.create_group("Доступні інструменти", layout)
        tools_layout = QVBoxLayout()

        self.tools_table = QTableWidget()
        self.tools_table.setColumnCount(3)
        self.tools_table.setHorizontalHeaderLabels(["Інструмент", "Опис", "Статус"])
        self.tools_table.horizontalHeader().setStretchLastSection(True)
        tools_layout.addWidget(self.tools_table)

        tools_group.setLayout(tools_layout)

        # Додати тестові інструменти
        self.add_test_tools()

        # Кнопка виконання
        self.execute_button = QPushButton("Виконати вибраний інструмент")
        self.execute_button.clicked.connect(self.execute_tool)
        layout.addWidget(self.execute_button)

    def add_test_tools(self):
        """Додати тестові інструменти."""
        for tool, desc, status in TEST_TOOLS:
            row = self.tools_table.rowCount()
            self.tools_table.insertRow(row)
            self.tools_table.setItem(row, 0, QTableWidgetItem(tool))
            self.tools_table.setItem(row, 1, QTableWidgetItem(desc))
            self.tools_table.setItem(row, 2, QTableWidgetItem(status))

    def execute_tool(self):
        """Виконати вибраний інструмент."""
        selected = self.tools_table.selectedItems()
        if selected:
            tool_name = selected[0].text()
            print(f"Виконання інструменту: {tool_name}")
