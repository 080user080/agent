"""Тестове GUI вікно з багатьма вкладками для перевірки можливостей LLM."""
import sys

from PyQt6.QtWidgets import QApplication

# Додати шлях до модуля gui_tabs
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui_tabs import MultiTabGUI


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MultiTabGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
