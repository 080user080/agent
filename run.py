"""Універсальна точка входу — вибирає GUI бекенд на основі setting `GUI_BACKEND`.

Значення:
    tkinter (default, стабільний)  → run_assistant.py / AssistantApp
    pyqt6   (експериментально)     → run_assistant_qt.py / AssistantAppQt

Запуск:
    python run.py            # використовує налаштування GUI_BACKEND
    python run.py --qt       # форсує PyQt6
    python run.py --tk       # форсує Tkinter
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from functions.core_settings import get_settings  # noqa: E402
get_settings()

from functions.core_settings import get_setting  # noqa: E402


def main() -> None:
    # CLI override
    backend = None
    if "--qt" in sys.argv or "--pyqt6" in sys.argv:
        backend = "pyqt6"
    elif "--tk" in sys.argv or "--tkinter" in sys.argv:
        backend = "tkinter"
    else:
        backend = get_setting("GUI_BACKEND", "tkinter")

    print(f"[run.py] GUI_BACKEND = {backend}", flush=True)

    if backend == "pyqt6":
        from run_assistant_qt import AssistantAppQt
        AssistantAppQt().start()
    else:
        from run_assistant import AssistantApp
        AssistantApp().start()


if __name__ == "__main__":
    main()
