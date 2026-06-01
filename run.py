"""Універсальна точка входу — PyQt6 GUI.

Запуск:
    python run.py            # запуск PyQt6 GUI
"""
from __future__ import annotations

import os
import sys

# Додаємо шлях до проєкту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_assistant_qt

if __name__ == "__main__":
    app = run_assistant_qt.AssistantAppQt()
    app.start()
