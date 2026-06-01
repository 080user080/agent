"""Тести для drag-n-drop файлів — Phase V10."""
import pytest
from unittest.mock import Mock, patch

from functions.tools.tools_mouse_keyboard import MouseKeyboardController, mouse_drag


class TestMouseDrag:
    """Тести для mouse_drag."""

    def test_mouse_drag_basic(self):
        """Базовий drag & drop."""
        controller = MouseKeyboardController()

        with patch("functions.tools.tools_mouse_keyboard.pyautogui") as mock_pyautogui:
            mock_pyautogui.position.return_value = Mock(x=0, y=0)
            result = controller.mouse_drag(100, 200, 300, 400, duration=0.5, button='left')

            assert result["success"] == True
            assert result["start"] == {"x": 100, "y": 200}
            assert result["end"] == {"x": 300, "y": 400}
            assert result["duration"] == 0.5
            assert result["button"] == "left"

    def test_mouse_drag_with_dpi_correction(self):
        """Drag & drop з DPI correction."""
        controller = MouseKeyboardController()

        with patch("functions.tools.tools_mouse_keyboard._apply_dpi_correction") as mock_dpi:
            mock_dpi.side_effect = lambda x, y: (int(x / 1.5), int(y / 1.5))

            with patch("functions.tools.tools_mouse_keyboard.pyautogui") as mock_pyautogui:
                result = controller.mouse_drag(150, 300, 450, 600)

                # DPI correction має бути застосовано
                mock_pyautogui.moveTo.assert_called_once_with(100, 200)  # 150/1.5, 300/1.5
                mock_pyautogui.dragTo.assert_called_once_with(300, 400, duration=0.5, button='left')  # 450/1.5, 600/1.5

    def test_mouse_drag_error(self):
        """Drag & drop з помилкою."""
        controller = MouseKeyboardController()

        with patch("functions.tools.tools_mouse_keyboard.pyautogui") as mock_pyautogui:
            mock_pyautogui.dragTo.side_effect = Exception("Test error")

            result = controller.mouse_drag(100, 200, 300, 400)

            assert result["success"] == False
            assert "Test error" in result["error"]

    def test_mouse_drag_global_function(self):
        """Глобальна функція mouse_drag."""
        with patch("functions.tools.tools_mouse_keyboard._controller") as mock_controller:
            mock_controller.mouse_drag.return_value = {
                "success": True,
                "start": {"x": 100, "y": 200},
                "end": {"x": 300, "y": 400}
            }

            result = mouse_drag(100, 200, 300, 400)

            mock_controller.mouse_drag.assert_called_once_with(100, 200, 300, 400, 0.5, 'left')
            assert result["success"] == True


class TestDragDropFileScenarios:
    """Тести для drag-n-drop файлів у різних сценаріях."""

    def test_drag_from_explorer_to_app(self):
        """Перетягування файлу з Explorer в програму.

        Сценарій:
        1. Клік на файл у Explorer
        2. Drag до вікна програми
        3. Drop
        """
        controller = MouseKeyboardController()

        with patch("functions.tools.tools_mouse_keyboard.pyautogui") as mock_pyautogui:
            # Симуляція перетягування
            result = controller.mouse_drag(
                start_x=100, start_y=200,  # Координати файлу в Explorer
                end_x=500, end_y=600,  # Координати вікна програми
                duration=1.0  # Повільніше для drag-n-drop
            )

            assert result["success"] == True
            assert result["duration"] == 1.0

    def test_drag_from_app_to_app(self):
        """Перетягування з однієї програми в іншу.

        Сценарій:
        1. Клік на елемент в App A
        2. Drag до App B
        3. Drop
        """
        controller = MouseKeyboardController()

        with patch("functions.tools.tools_mouse_keyboard.pyautogui") as mock_pyautogui:
            result = controller.mouse_drag(
                start_x=200, start_y=300,  # App A
                end_x=800, end_y=400,  # App B
                duration=0.8
            )

            assert result["success"] == True

    def test_drag_with_right_button(self):
        """Перетягування з правою кнопкою."""
        controller = MouseKeyboardController()

        with patch("functions.tools.tools_mouse_keyboard.pyautogui") as mock_pyautogui:
            result = controller.mouse_drag(
                start_x=100, start_y=200,
                end_x=300, end_y=400,
                button='right'
            )

            assert result["success"] == True
            assert result["button"] == "right"
