"""Базовий клас для вкладок GUI."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox


class BaseTab(QWidget):
    """Базовий клас для всіх вкладок."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Налаштування UI. Перевизначається в підкласах."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self._build_content(layout)

    def _build_content(self, layout: QVBoxLayout):
        """Побудувати контент вкладки. Перевизначається в підкласах."""
        pass

    def create_group(self, title: str, parent_layout: QVBoxLayout) -> QGroupBox:
        """Створити групу з заголовком."""
        group = QGroupBox(title)
        parent_layout.addWidget(group)
        return group

    def create_hbox(self, parent_layout: QVBoxLayout) -> QHBoxLayout:
        """Створити горизонтальний layout."""
        hbox = QHBoxLayout()
        parent_layout.addLayout(hbox)
        return hbox
