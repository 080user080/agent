"""
Тести для модуля logic_ui_navigator.py

GUI Automation Phase 5 — Розумна навігація по UI.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestUINavigator:
    """Тести для класу UINavigator."""

    def test_init(self):
        """Тест ініціалізації UINavigator."""
        from functions.logic_ui_navigator import UINavigator

        navigator = UINavigator()
        assert navigator is not None

    @patch('functions.logic_ui_navigator.find_clickable_elements')
    def test_navigate_to_element(self, mock_find):
        """Тест навігації до елемента."""
        from functions.logic_ui_navigator import UINavigator

        mock_find.return_value = [{"x": 100, "y": 200, "confidence": 0.9}]

        navigator = UINavigator()
        result = navigator.navigate_to_element("button", "Save")

        assert result is not None

    @patch('functions.logic_ui_navigator.find_clickable_elements')
    def test_find_element_by_text(self, mock_find):
        """Тест пошуку елемента за текстом."""
        from functions.logic_ui_navigator import UINavigator

        mock_find.return_value = [{"x": 100, "y": 200, "text": "Save"}]

        navigator = UINavigator()
        result = navigator.find_element_by_text("Save")

        assert result is not None

    @patch('functions.logic_ui_navigator.mouse_click')
    def test_click_element(self, mock_click):
        """Тест кліку на елемент."""
        from functions.logic_ui_navigator import UINavigator

        navigator = UINavigator()
        element = {"x": 100, "y": 200}
        result = navigator.click_element(element)

        assert result is not None


class TestNavigationPath:
    """Тести для планування шляху навігації."""

    def test_init(self):
        """Тест ініціалізації NavigationPath."""
        from functions.logic_ui_navigator import NavigationPath

        path = NavigationPath()
        assert path is not None

    def test_add_step(self):
        """Тест додавання кроку."""
        from functions.logic_ui_navigator import NavigationPath

        path = NavigationPath()
        path.add_step("click", {"x": 100, "y": 200})

        assert len(path.steps) == 1

    def test_execute_path(self):
        """Тест виконання шляху."""
        from functions.logic_ui_navigator import NavigationPath

        path = NavigationPath()
        path.add_step("click", {"x": 100, "y": 200})

        with patch('functions.logic_ui_navigator.mouse_click'):
            result = path.execute()
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
