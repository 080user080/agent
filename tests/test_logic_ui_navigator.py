"""
Тести для модуля logic_ui_navigator.py

GUI Automation Phase 5 — Розумна навігація по UI.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestUINavigator:
    """Тести для класу UINavigator."""

    def test_init(self):
        """Тест ініціалізації UINavigator."""
        from functions.gui.logic_ui_navigator import UINavigator

        navigator = UINavigator()
        assert navigator is not None

    def test_click_element(self):
        """Тест кліку на елемент (повертає словник з success)."""
        from functions.gui.logic_ui_navigator import UINavigator

        navigator = UINavigator()
        result = navigator.click_element("button", "Save")

        assert isinstance(result, dict)
        assert "success" in result
        assert "message" in result

    def test_type_in_field(self):
        """Тест введення тексту в поле."""
        from functions.gui.logic_ui_navigator import UINavigator

        navigator = UINavigator()
        result = navigator.type_in_field("Search", "hello")

        assert isinstance(result, dict)
        assert "success" in result

    def test_select_option(self):
        """Тест вибору опції."""
        from functions.gui.logic_ui_navigator import UINavigator

        navigator = UINavigator()
        result = navigator.select_option("dropdown", "option")

        assert isinstance(result, dict)
        assert "success" in result

    def test_check_checkbox(self):
        """Тест чекбоксу."""
        from functions.gui.logic_ui_navigator import UINavigator

        navigator = UINavigator()
        result = navigator.check_checkbox("label", True)

        assert isinstance(result, dict)

    def test_simulate_action(self):
        """Тест execute_action."""
        from functions.gui.logic_ui_navigator import UINavigator, UIAction, UIActionType, UIElement

        navigator = UINavigator()
        element = UIElement(element_type="button", description="OK")
        action = UIAction(action_type=UIActionType.CLICK, element=element)

        result = navigator.execute_action(action)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])