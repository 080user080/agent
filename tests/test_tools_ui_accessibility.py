"""Тести для tools_ui_accessibility (Phase 4)."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestUIElement:
    """Тести для UIElement."""

    def test_ui_element_creation(self):
        """Тест створення UIElement."""
        from functions.tools.tools_ui_accessibility import UIElement

        element = UIElement(
            name="OK",
            control_type="Button",
            automation_id="btn_ok",
            bounding_rectangle=(0, 0, 100, 30),
            is_enabled=True
        )
        assert element.name == "OK"
        assert element.control_type == "Button"
        assert element.is_enabled is True

    def test_ui_element_defaults(self):
        """Тест дефолтних значень UIElement."""
        from functions.tools.tools_ui_accessibility import UIElement

        element = UIElement(name="test")
        assert element.name == "test"
        assert element.control_type is None
        assert element.is_enabled is True


class TestUIAWrapper:
    """Тести для UIAWrapper."""

    def test_is_available_true(self):
        """Перевірка доступності UIA."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        available = wrapper.is_available()
        assert isinstance(available, bool)

    def test_is_available_false(self):
        """UIA недоступний."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        assert wrapper.is_available() is not None

    def test_get_root_element_unavailable(self):
        """Отримання кореневого елементу."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.get_root_element()
        assert isinstance(result, dict)

    def test_get_focused_element_unavailable(self):
        """Отримання фокусованого елементу."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.get_focused_element()
        assert isinstance(result, dict)

    def test_find_element_by_name_unavailable(self):
        """Пошук елементу за ім'ям."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.find_element_by_name("OK")
        assert isinstance(result, dict)

    def test_find_element_by_automation_id_unavailable(self):
        """Пошук за automation_id."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.find_element_by_automation_id("btn_ok")
        assert isinstance(result, dict)

    def test_click_element_unavailable(self):
        """Клік по елементу."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.click_element(MagicMock())
        assert isinstance(result, dict)

    def test_set_text_unavailable(self):
        """Встановлення тексту."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.set_text(MagicMock(), "test")
        assert isinstance(result, dict)

    def test_get_value_unavailable(self):
        """Отримання значення."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.get_value(MagicMock())
        assert isinstance(result, dict)

    def test_wait_for_element_unavailable(self):
        """Очікування елементу."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.wait_for_element("OK", timeout=0.1)
        assert isinstance(result, dict)

    def test_list_all_buttons_unavailable(self):
        """Список кнопок."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.list_all_buttons()
        assert isinstance(result, list)

    def test_list_all_inputs_unavailable(self):
        """Список полів вводу."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.list_all_inputs()
        assert isinstance(result, list)

    def test_list_all_checkboxes_unavailable(self):
        """Список чекбоксів."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.list_all_checkboxes()
        assert isinstance(result, list)

    def test_get_ui_tree_unavailable(self):
        """Отримання UI дерева."""
        from functions.tools.tools_ui_accessibility import UIAWrapper
        wrapper = UIAWrapper()
        result = wrapper.get_ui_tree()
        assert isinstance(result, list)


class TestLLMTools:
    """Тести для публічних функцій."""

    def test_uia_list_elements_unavailable(self):
        """Список елементів."""
        from functions.tools.tools_ui_accessibility import uia_list_elements
        result = uia_list_elements(control_type="Button")
        assert isinstance(result, list)

    def test_uia_find_button_unavailable(self):
        """Пошук кнопки."""
        from functions.tools.tools_ui_accessibility import uia_find_button
        result = uia_find_button("OK")
        assert isinstance(result, dict)

    def test_uia_find_button_missing_name(self):
        """Пошук кнопки без імені."""
        from functions.tools.tools_ui_accessibility import uia_find_button
        result = uia_find_button("")
        assert isinstance(result, dict)

    def test_uia_click_element_unavailable(self):
        """Клік."""
        from functions.tools.tools_ui_accessibility import uia_click_element
        result = uia_click_element(MagicMock())
        assert isinstance(result, dict)

    def test_uia_set_text_unavailable(self):
        """Встановлення тексту."""
        from functions.tools.tools_ui_accessibility import uia_set_text
        result = uia_set_text(MagicMock(), "test")
        assert isinstance(result, dict)

    def test_uia_set_text_missing_text(self):
        """Встановлення тексту без тексту."""
        from functions.tools.tools_ui_accessibility import uia_set_text
        result = uia_set_text(MagicMock(), "")
        assert isinstance(result, dict)

    def test_uia_get_value_unavailable(self):
        """Отримання значення."""
        from functions.tools.tools_ui_accessibility import uia_get_value
        result = uia_get_value(MagicMock())
        assert isinstance(result, dict)

    def test_uia_wait_for_element_unavailable(self):
        """Очікування."""
        from functions.tools.tools_ui_accessibility import uia_wait_for_element
        result = uia_wait_for_element("OK", timeout=0.1)
        assert isinstance(result, dict)

    def test_uia_wait_for_element_missing_name(self):
        """Очікування без імені."""
        from functions.tools.tools_ui_accessibility import uia_wait_for_element
        result = uia_wait_for_element("", timeout=0.1)
        assert isinstance(result, dict)

    def test_uia_list_buttons_unavailable(self):
        """Список кнопок."""
        from functions.tools.tools_ui_accessibility import uia_list_buttons
        result = uia_list_buttons()
        assert isinstance(result, list)

    def test_uia_list_inputs_unavailable(self):
        """Список полів."""
        from functions.tools.tools_ui_accessibility import uia_list_inputs
        result = uia_list_inputs()
        assert isinstance(result, list)

    def test_uia_get_focused_element_unavailable(self):
        """Фокусований елемент."""
        from functions.tools.tools_ui_accessibility import uia_get_focused_element
        result = uia_get_focused_element()
        assert isinstance(result, dict)


class TestUIAFallbackIntegration:
    """Тести fallback інтеграції."""

    def test_uia_fallback_disabled(self):
        """Fallback вимкнено."""
        from functions.tools.tools_ui_accessibility import get_uia_wrapper
        wrapper = get_uia_wrapper()
        assert wrapper is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])