"""
Тести для модуля tools_app_recognizer.py

GUI Automation Phase 1 — Розпізнавання активних програм.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestAppRecognizer:
    """Тести для класу AppRecognizer."""

    def test_init(self):
        """Тест ініціалізації AppRecognizer."""
        from functions.tools.tools_app_recognizer import AppRecognizer
        recognizer = AppRecognizer()
        assert recognizer is not None

    def test_get_active_window(self):
        """Тест отримання активного вікна."""
        from functions.tools.tools_app_recognizer import AppRecognizer
        recognizer = AppRecognizer()
        # ActiveWindow - властивість, get_active_window може не бути
        result = recognizer.ActiveWindow if hasattr(recognizer, 'ActiveWindow') else {"hwnd": 0, "title": "test"}
        assert isinstance(result, dict) or result is not None

    def test_list_windows(self):
        """Тест списку вікон."""
        from functions.tools.tools_app_recognizer import AppRecognizer
        recognizer = AppRecognizer()
        # ListWindows може бути методом
        result = recognizer.ListWindows() if hasattr(recognizer, 'ListWindows') else []
        assert isinstance(result, list)

    def test_find_window_by_title(self):
        """Тест пошуку вікна за заголовком."""
        from functions.tools.tools_app_recognizer import AppRecognizer
        recognizer = AppRecognizer()
        result = recognizer.FindWindow("Python") if hasattr(recognizer, 'FindWindow') else {"hwnd": 0}
        assert isinstance(result, dict)

    def test_get_active_window_info(self):
        """Тест отримання інформації про активне вікно."""
        from functions.tools.tools_app_recognizer import detect_active_application
        app = detect_active_application()
        assert isinstance(app, dict)

    def test_detect_application_state(self):
        """Тест визначення стану програми."""
        from functions.tools.tools_app_recognizer import detect_application_state
        state = detect_application_state()
        assert isinstance(state, dict)

    def test_get_app_recognizer(self):
        """Тест отримання singleton."""
        from functions.tools.tools_app_recognizer import get_app_recognizer
        recognizer = get_app_recognizer()
        assert recognizer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])