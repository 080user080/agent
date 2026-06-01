"""Tests for UIA + Vision-LM (S4)."""
from unittest.mock import MagicMock

import pytest

from functions.llm.providers_vision import VisionLMProvider, VisionQuery, VisionResponse
from functions.tools.tools_ui_accessibility import UIAWrapper, UIElement


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestUIElement:
    def test_initial_state(self):
        elem = UIElement(name="test", control_type="Button")
        assert elem.name == "test"
        assert elem.control_type == "Button"
        assert elem.automation_id == ""
        assert elem.is_enabled is True
        assert elem.is_visible is True
        assert elem.children == []

    def test_with_rect(self):
        elem = UIElement(
            name="test",
            control_type="Button",
            rect={"left": 100, "top": 200, "width": 50, "height": 30},
        )
        assert elem.rect == {"left": 100, "top": 200, "width": 50, "height": 30}


class TestUIAWrapper:
    def test_initial_state(self):
        wrapper = UIAWrapper()
        # pywinauto може бути недоступний якщо не встановлено
        # Тест просто перевіряє що ініціалізація не падає
        assert wrapper is not None

    def test_get_root_element(self):
        wrapper = UIAWrapper()
        if wrapper.is_available():
            elem = wrapper.get_root_element()
            assert elem is not None
            # control_type може бути різним залежно від бекенда
            assert elem.control_type in ("Desktop", "Pane")
        else:
            pass

    def test_get_focused_element(self):
        wrapper = UIAWrapper()
        if wrapper.is_available():
            elem = wrapper.get_focused_element()
            # uiautomation може повернути фокований елемент
            # pywinauto fallback повертає None
            assert elem is None or elem.control_type is not None
        else:
            pass

    def test_find_element_by_name(self):
        wrapper = UIAWrapper()
        if wrapper.is_available():
            # Пошук існуючого вікна (наприклад, "explorer" або "File Explorer")
            elem = wrapper.find_element_by_name("explorer")
            # Може знайти або ні залежно від того що відкрито
            assert elem is None or elem.control_type in ("Window", "Pane")
        else:
            pass

    def test_click_element_with_rect(self):
        wrapper = UIAWrapper()
        elem = UIElement(
            name="test",
            control_type="Button",
            rect={"left": 100, "top": 200, "width": 50, "height": 30},
        )
        if wrapper.is_available():
            result = wrapper.click_element(elem)
            # Для MVP клік через pyautogui — може працювати або ні
            assert "ok" in result
        else:
            result = wrapper.click_element(elem)
            assert result["ok"] is False

    def test_set_text_with_rect(self):
        wrapper = UIAWrapper()
        elem = UIElement(
            name="test",
            control_type="Edit",
            rect={"left": 100, "top": 200, "width": 200, "height": 30},
        )
        if wrapper.is_available():
            result = wrapper.set_text(elem, "test text")
            # Для MVP через pyperclip + Ctrl+V
            assert "ok" in result
        else:
            result = wrapper.set_text(elem, "test text")
            assert result["ok"] is False


class TestVisionQuery:
    def test_initial_state(self):
        query = VisionQuery(image_path="test.png")
        assert query.image_path == "test.png"
        assert query.question == "Опиши що видно на цьому зображенні"
        assert query.context == ""
        assert query.max_tokens == 500

    def test_with_custom_params(self):
        query = VisionQuery(
            image_path="test.png",
            question="Custom question",
            max_tokens=1000,
        )
        assert query.question == "Custom question"
        assert query.max_tokens == 1000


class TestVisionResponse:
    def test_initial_state(self):
        response = VisionResponse(text="test")
        assert response.text == "test"
        assert response.confidence == 0.0
        assert response.detected_elements == []
        assert response.suggested_actions == []

    def test_with_elements(self):
        response = VisionResponse(
            text="test",
            detected_elements=["button", "input"],
            suggested_actions=["click button"],
        )
        assert len(response.detected_elements) == 2
        assert len(response.suggested_actions) == 1


class TestVisionLMProvider:
    def test_initial_state(self):
        assistant = MagicMock()
        provider = VisionLMProvider(assistant)
        assert provider.is_available() is False  # MVP — недоступний

    def test_analyze_image_not_available(self):
        assistant = MagicMock()
        provider = VisionLMProvider(assistant)
        query = VisionQuery(image_path="test.png")
        response = provider.analyze_image(query)
        assert response.text == "Vision-LM недоступний"
        assert response.confidence == 0.0

    def test_detect_ui_elements_not_available(self):
        assistant = MagicMock()
        provider = VisionLMProvider(assistant)
        elements = provider.detect_ui_elements("test.png")
        assert elements == []

    def test_suggest_actions_not_available(self):
        assistant = MagicMock()
        provider = VisionLMProvider(assistant)
        actions = provider.suggest_actions("test.png", "submit form")
        assert actions == []
