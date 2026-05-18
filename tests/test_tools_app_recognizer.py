"""
Тести для модуля tools_app_recognizer.py

GUI Automation Phase 4 — Розпізнавання програм.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestAppRecognizer:
    """Тести для класу AppRecognizer."""

    @patch('functions.tools.tools_app_recognizer.pywin32')
    def test_init(self, mock_pywin32):
        """Тест ініціалізації AppRecognizer."""
        from functions.tools.tools_app_recognizer import AppRecognizer

        recognizer = AppRecognizer()
        assert recognizer is not None

    @patch('functions.tools.tools_app_recognizer.pywin32')
    def test_get_active_window(self, mock_pywin32):
        """Тест отримання активного вікна."""
        from functions.tools.tools_app_recognizer import AppRecognizer

        # Mock pywin32
        mock_pywin32.GetForegroundWindow.return_value = 12345
        mock_pywin32.GetWindowText.return_value = "Test Window"
        mock_pywin32.GetWindowThreadProcessId.return_value = (999, 12345)
        mock_pywin32.OpenProcess.return_value = 999
        mock_pywin32.GetModuleFileNameExW.return_value = "test.exe"

        recognizer = AppRecognizer()
        result = recognizer.get_active_window()

        assert result is not None
        assert "title" in result or "error" in result

    @patch('functions.tools.tools_app_recognizer.pywin32')
    def test_list_windows(self, mock_pywin32):
        """Тест списку вікон."""
        from functions.tools.tools_app_recognizer import AppRecognizer

        # Mock pywin32
        mock_pywin32.EnumWindows.return_value = True
        mock_pywin32.GetWindowText.return_value = "Window Title"
        mock_pywin32.IsWindowVisible.return_value = True

        recognizer = AppRecognizer()
        result = recognizer.list_windows()

        assert result is not None

    @patch('functions.tools.tools_app_recognizer.pywin32')
    def test_find_window_by_title(self, mock_pywin32):
        """Тест пошуку вікна за заголовком."""
        from functions.tools.tools_app_recognizer import AppRecognizer

        # Mock pywin32
        mock_pywin32.FindWindowW.return_value = 12345

        recognizer = AppRecognizer()
        result = recognizer.find_window_by_title("Test")

        assert result is not None


class TestAppProfileMatcher:
    """Тести для співпадіння профілів програм."""

    def test_init(self):
        """Тест ініціалізації AppProfileMatcher."""
        from functions.tools.tools_app_recognizer import AppProfileMatcher

        matcher = AppProfileMatcher()
        assert matcher is not None

    def test_match_by_exe(self):
        """Тест співпадіння за exe."""
        from functions.tools.tools_app_recognizer import AppProfileMatcher

        matcher = AppProfileMatcher()
        result = matcher.match_by_exe("notepad.exe")

        assert result is not None

    def test_match_by_title_pattern(self):
        """Тест співпадіння за шаблоном заголовка."""
        from functions.tools.tools_app_recognizer import AppProfileMatcher

        matcher = AppProfileMatcher()
        result = matcher.match_by_title_pattern(".*Notepad")

        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
