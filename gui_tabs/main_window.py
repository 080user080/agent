"""Головне вікно з багатьма вкладками."""
from datetime import datetime
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow, QTabWidget

from .chat_tab import ChatTab
from .settings_tab import SettingsTab
from .logs_tab import LogsTab
from .statistics_tab import StatisticsTab
from .about_tab import AboutTab
from .tools_tab import ToolsTab
from .constants import TAB_NAMES, APP_VERSION


class MultiTabGUI(QMainWindow):
    """Головне вікно з багатьма вкладками."""

    def __init__(self):
        super().__init__()
        self.tabs = None
        self.status_timer = None
        self._setup_ui()

    def _setup_ui(self):
        """Налаштування UI."""
        self.setWindowTitle("МАРК — Тестове GUI з вкладками")
        self.setGeometry(100, 100, 1200, 800)

        # Створення вкладок
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)

        # Додавання вкладок
        self.tabs.addTab(ChatTab(), TAB_NAMES["chat"])
        self.tabs.addTab(SettingsTab(), TAB_NAMES["settings"])
        self.tabs.addTab(LogsTab(), TAB_NAMES["logs"])
        self.tabs.addTab(StatisticsTab(), TAB_NAMES["statistics"])
        self.tabs.addTab(AboutTab(), TAB_NAMES["about"])
        self.tabs.addTab(ToolsTab(), TAB_NAMES["tools"])

        self.setCentralWidget(self.tabs)

        # Статус бар
        self.statusBar().showMessage(f"Готово | Версія {APP_VERSION}")

        # Таймер для оновлення статусу
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)

    def update_status(self):
        """Оновити статус бар."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.statusBar().showMessage(f"Готово | {timestamp} | Версія {APP_VERSION}")
