"""PyQt6 GUI implementation (alternative to tkinter).

Модульна структура:
- main_window.py — QMainWindow з QTabWidget (6 вкладок), без міксинів
- base_tab.py — BaseTab (базовий клас вкладки)
- tab_chat.py — ChatTab (чат)
- tab_plan.py — PlanTab (план)
- tab_logs.py — LogsTab (логи, новий)
- tab_stats.py — StatsTab (статистика, новий)
- tab_tools.py — ToolsTab (інструменти, новий)
- tab_settings.py — SettingsTab (налаштування)
- constants.py — спільні константи
- confirmation_qt.py — діалог підтвердження
- llm_endpoints_editor_qt.py — редактор LLM endpoint-ів
"""
from .main_window import MainWindowPyQt6

__all__ = ['MainWindowPyQt6']