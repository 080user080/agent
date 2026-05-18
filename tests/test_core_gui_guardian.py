"""
Тести для модуля core_gui_guardian.py

GUI Automation Phase 6 — GUI Guardian (захист від небезпечних дій).
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestGUIGuardian:
    """Тести для класу GUIGuardian."""

    def test_init(self):
        """Тест ініціалізації GUIGuardian."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        assert guardian is not None

    def test_check_action_safety(self):
        """Тест перевірки безпеки дії."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        result = guardian.check_action_safety("mouse_click", {"x": 100, "y": 200})

        assert result is not None

    def test_check_dangerous_action(self):
        """Тест перевірки небезпечної дії."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        result = guardian.check_action_safety("delete_file", {"path": "important.txt"})

        assert result is not None

    def test_add_dangerous_pattern(self):
        """Тест додавання небезпечного патерна."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.add_dangerous_pattern("delete")

        assert "delete" in guardian.dangerous_patterns

    def test_remove_dangerous_pattern(self):
        """Тест видалення небезпечного патерна."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.add_dangerous_pattern("delete")
        guardian.remove_dangerous_pattern("delete")

        assert "delete" not in guardian.dangerous_patterns

    def test_whitelist_action(self):
        """Тест білого списку дій."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.whitelist_action("mouse_click")

        assert "mouse_click" in guardian.whitelist

    def test_is_whitelisted(self):
        """Тест перевірки білого списку."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.whitelist_action("mouse_click")

        result = guardian.is_whitelisted("mouse_click")
        assert result is True


class TestActionValidator:
    """Тести для класу ActionValidator."""

    def test_init(self):
        """Тест ініціалізації ActionValidator."""
        from functions.gui.core_gui_guardian import ActionValidator

        validator = ActionValidator()
        assert validator is not None

    def test_validate_mouse_coordinates(self):
        """Тест валідації координат миші."""
        from functions.gui.core_gui_guardian import ActionValidator

        validator = ActionValidator()
        result = validator.validate_mouse_coordinates(100, 200)

        assert result is not None

    def test_validate_text_input(self):
        """Тест валідації текстового вводу."""
        from functions.gui.core_gui_guardian import ActionValidator

        validator = ActionValidator()
        result = validator.validate_text_input("hello world")

        assert result is not None

    def test_validate_file_path(self):
        """Тест валідації шляху до файлу."""
        from functions.gui.core_gui_guardian import ActionValidator

        validator = ActionValidator()
        result = validator.validate_file_path("test.txt")

        assert result is not None


class TestSafetyPolicy:
    """Тести для класу SafetyPolicy."""

    def test_init(self):
        """Тест ініціалізації SafetyPolicy."""
        from functions.gui.core_gui_guardian import SafetyPolicy

        policy = SafetyPolicy()
        assert policy is not None

    def test_add_rule(self):
        """Тест додавання правила."""
        from functions.gui.core_gui_guardian import SafetyPolicy

        policy = SafetyPolicy()
        policy.add_rule("no_delete", lambda action: action != "delete_file")

        assert "no_delete" in policy.rules

    def test_check_policy(self):
        """Тест перевірки політики."""
        from functions.gui.core_gui_guardian import SafetyPolicy

        policy = SafetyPolicy()
        policy.add_rule("no_delete", lambda action: action != "delete_file")

        result = policy.check("mouse_click")
        assert result is not None

    def test_remove_rule(self):
        """Тест видалення правила."""
        from functions.gui.core_gui_guardian import SafetyPolicy

        policy = SafetyPolicy()
        policy.add_rule("no_delete", lambda action: action != "delete_file")
        policy.remove_rule("no_delete")

        assert "no_delete" not in policy.rules


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
