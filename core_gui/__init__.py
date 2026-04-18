# core_gui/__init__.py
"""Модульний GUI асистента (tkinter).

Головна точка входу — AssistantGUI та run_gui.
Міксини ChatPanelMixin/ConfirmationMixin/PlanPanelMixin/SettingsTabMixin
розділяють функціонал по темам для зручності подальшої міграції на PyQt6.
"""
from .main_window import AssistantGUI, run_gui
from .llm_endpoints_editor import LLMEndpointsEditor
from .constants import ASSISTANT_NAME, ASSISTANT_EMOJI, ASSISTANT_TITLE

__all__ = [
    "AssistantGUI",
    "run_gui",
    "LLMEndpointsEditor",
    "ASSISTANT_NAME",
    "ASSISTANT_EMOJI",
    "ASSISTANT_TITLE",
]
