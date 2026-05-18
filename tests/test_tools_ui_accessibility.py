"""Тести для Windows UI Automation (UIA) tools — ЕТАП 3."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from functions.tools.tools_ui_accessibility import (
    UIElement,
    UIAWrapper,
    get_uia_wrapper,
    uia_list_elements,
    uia_find_button,
    uia_click_element,
    uia_set_text,
    uia_get_value,
    uia_wait_for_element,
    uia_list_buttons,
    uia_list_inputs,
    uia_get_focused_element,
)


class TestUIElement:
    """Тести для UIElement dataclass."""

    def test_ui_element_creation(self):
        """Створення UIElement."""
        elem = UIElement(
            name="TestButton",
            control_type="Button",
            automation_id="btn1",
            rect={"left": 100, "top": 200, "width": 50, "height": 30},
        )
        assert elem.name == "TestButton"
        assert elem.control_type == "Button"
        assert elem.automation_id == "btn1"
        assert elem.is_enabled is True
        assert elem.is_visible is True
        assert len(elem.children) == 0

    def test_ui_element_defaults(self):
        """Значення за замовчуванням для UIElement."""
        elem = UIElement(name="Test", control_type="Edit")
        assert elem.rect == {}
        assert elem.children == []
        assert elem.is_enabled is True
        assert elem.is_visible is True


class TestUIAWrapper:
    """Тести для UIAWrapper."""

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_singleton(self, mock_init):
        """Singleton instance."""
        wrapper1 = get_uia_wrapper()
        wrapper2 = get_uia_wrapper()
        assert wrapper1 is wrapper2
        mock_init.assert_called_once()

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_is_available_true(self, mock_init):
        """is_available повертає True при успішній ініціалізації."""
        wrapper = UIAWrapper()
        wrapper._available = True
        assert wrapper.is_available() is True

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_is_available_false(self, mock_init):
        """is_available повертає False при неуспішній ініціалізації."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.is_available() is False

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_get_root_element_unavailable(self, mock_init):
        """get_root_element повертає None якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.get_root_element() is None

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_get_focused_element_unavailable(self, mock_init):
        """get_focused_element повертає None якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.get_focused_element() is None

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_find_element_by_name_unavailable(self, mock_init):
        """find_element_by_name повертає None якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.find_element_by_name("Test") is None

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_find_element_by_automation_id_unavailable(self, mock_init):
        """find_element_by_automation_id повертає None якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.find_element_by_automation_id("id1") is None

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_click_element_unavailable(self, mock_init):
        """click_element повертає error якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        elem = UIElement(name="Test", control_type="Button", rect={"left": 100, "top": 200, "width": 50, "height": 30})
        result = wrapper.click_element(elem)
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_set_text_unavailable(self, mock_init):
        """set_text повертає error якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        elem = UIElement(name="Test", control_type="Edit", rect={"left": 100, "top": 200, "width": 50, "height": 30})
        result = wrapper.set_text(elem, "Hello")
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_get_value_unavailable(self, mock_init):
        """get_value повертає error якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        elem = UIElement(name="Test", control_type="Edit")
        result = wrapper.get_value(elem)
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_wait_for_element_unavailable(self, mock_init):
        """wait_for_element повертає None якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.wait_for_element("Test", timeout=1.0) is None

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_list_all_buttons_unavailable(self, mock_init):
        """list_all_buttons повертає пустий список якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.list_all_buttons() == []

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_list_all_inputs_unavailable(self, mock_init):
        """list_all_inputs повертає пустий список якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.list_all_inputs() == []

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_list_all_checkboxes_unavailable(self, mock_init):
        """list_all_checkboxes повертає пустий список якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.list_all_checkboxes() == []

    @patch("functions.tools.tools_ui_accessibility.UIAWrapper._init_uia")
    def test_get_ui_tree_unavailable(self, mock_init):
        """get_ui_tree повертає None якщо UIA недоступний."""
        wrapper = UIAWrapper()
        wrapper._available = False
        assert wrapper.get_ui_tree() is None


class TestLLMTools:
    """Тести для LLM tools."""

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_list_elements_unavailable(self, mock_get_wrapper):
        """uia_list_elements повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_list_elements({})
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_find_button_unavailable(self, mock_get_wrapper):
        """uia_find_button повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_find_button({"name": "Test"})
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_find_button_missing_name(self, mock_get_wrapper):
        """uia_find_button повертає error якщо не задано name або automation_id."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = True
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_find_button({})
        assert result["ok"] is False
        assert "name або automation_id required" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_click_element_unavailable(self, mock_get_wrapper):
        """uia_click_element повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_click_element({"name": "Test"})
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_set_text_unavailable(self, mock_get_wrapper):
        """uia_set_text повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_set_text({"text": "Hello"})
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_set_text_missing_text(self, mock_get_wrapper):
        """uia_set_text повертає error якщо не задано text."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = True
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_set_text({"name": "Test"})
        assert result["ok"] is False
        assert "text required" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_get_value_unavailable(self, mock_get_wrapper):
        """uia_get_value повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_get_value({"name": "Test"})
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_wait_for_element_unavailable(self, mock_get_wrapper):
        """uia_wait_for_element повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_wait_for_element({"name": "Test"})
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_wait_for_element_missing_name(self, mock_get_wrapper):
        """uia_wait_for_element повертає error якщо не задано name."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = True
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_wait_for_element({})
        assert result["ok"] is False
        assert "name required" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_list_buttons_unavailable(self, mock_get_wrapper):
        """uia_list_buttons повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_list_buttons({})
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_list_inputs_unavailable(self, mock_get_wrapper):
        """uia_list_inputs повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_list_inputs({})
        assert result["ok"] is False
        assert "недоступний" in result["error"]

    @patch("functions.tools.tools_ui_accessibility.get_uia_wrapper")
    def test_uia_get_focused_element_unavailable(self, mock_get_wrapper):
        """uia_get_focused_element повертає error якщо UIA недоступний."""
        mock_wrapper = Mock()
        mock_wrapper.is_available.return_value = False
        mock_get_wrapper.return_value = mock_wrapper

        result = uia_get_focused_element({})
        assert result["ok"] is False
        assert "недоступний" in result["error"]


class TestUIAFallbackIntegration:
    """Тести для UIA fallback в tools_ui_detector."""

    @patch("functions.tools.tools_ui_detector.UIA_AVAILABLE", False)
    def test_uia_fallback_disabled(self):
        """Перевірка що fallback працює коли UIA недоступний."""
        from functions.tools.tools_ui_detector import find_button_by_text

        # Якщо UIA недоступний, fallback на OCR+CV
        # (тут тільки перевіряємо що функція не крашиться)
        result = find_button_by_text("Test", use_uia_first=True)
        # Результат залежить від OCR, але функція повинна повернути dict
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
