"""
Тести для модуля tools_ui_detector.py

GUI Automation Phase 4 — Computer Vision (UI елементи).
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestUIDetector:
    """Тести для класу UIDetector."""

    def test_init_cv_available(self):
        """Тест ініціалізації з CV."""
        from functions.tools.tools_ui_detector import UIDetector

        detector = UIDetector()
        assert detector is not None

    def test_init_cv_unavailable(self):
        """Тест ініціалізації."""
        from functions.tools.tools_ui_detector import UIDetector

        detector = UIDetector()
        assert detector is not None

    def test_find_button_by_text(self):
        """Тест пошуку кнопки за текстом."""
        from functions.tools.tools_ui_detector import find_button_by_text, get_ui_detector

        result = find_button_by_text("OK")
        assert isinstance(result, dict)

    def test_find_input_field(self):
        """Тест пошуку поля вводу."""
        from functions.tools.tools_ui_detector import find_input_field

        result = find_input_field()
        assert isinstance(result, list)

    def test_find_checkbox(self):
        """Тест пошуку чекбоксу."""
        from functions.tools.tools_ui_detector import find_checkbox

        result = find_checkbox()
        assert isinstance(result, list)

    def test_find_label(self):
        """Тест пошуку мітки."""
        from functions.tools.tools_ui_detector import find_label

        result = find_label("Name")
        assert isinstance(result, dict)

    def test_get_ui_detector(self):
        """Тест отримання singleton."""
        from functions.tools.tools_ui_detector import get_ui_detector

        detector = get_ui_detector()
        assert detector is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])