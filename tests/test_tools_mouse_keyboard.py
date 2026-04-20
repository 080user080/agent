"""
Тести для модуля tools_mouse_keyboard.py

GUI Automation Phase 1 — керування мишею та клавіатурою.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.tools_mouse_keyboard import (
    MouseKeyboardController,
    mouse_click, mouse_move, mouse_scroll, mouse_drag,
    get_mouse_position, mouse_click_image,
    keyboard_press, keyboard_type, keyboard_hotkey,
    keyboard_hold, keyboard_send_special,
    clipboard_copy_text, clipboard_get_text, clipboard_copy_image
)


class TestMouseKeyboardController:
    """Тести для класу MouseKeyboardController."""

    @pytest.fixture
    def controller(self):
        """Фікстура для створення контролера."""
        return MouseKeyboardController()

    # ==================== Тести миші ====================

    @patch('functions.tools_mouse_keyboard.pyautogui.click')
    def test_mouse_click_success(self, mock_click, controller):
        """Тест успішного кліку мишою."""
        result = controller.mouse_click(100, 200, button='left', clicks=1)

        assert result['success'] is True
        assert result['position'] == {'x': 100, 'y': 200}
        assert result['button'] == 'left'
        mock_click.assert_called_once_with(x=100, y=200, button='left', clicks=1, interval=0.1)

    @patch('functions.tools_mouse_keyboard.pyautogui.click')
    def test_mouse_click_double_click(self, mock_click, controller):
        """Тест подвійного кліку."""
        result = controller.mouse_click(100, 200, clicks=2)

        assert result['success'] is True
        assert result['clicks'] == 2
        mock_click.assert_called_once_with(x=100, y=200, button='left', clicks=2, interval=0.1)

    @patch('functions.tools_mouse_keyboard.pyautogui.click')
    def test_mouse_click_error(self, mock_click, controller):
        """Тест обробки помилки при кліку."""
        mock_click.side_effect = Exception("Click failed")

        result = controller.mouse_click(100, 200)

        assert result['success'] is False
        assert 'error' in result

    @patch('functions.tools_mouse_keyboard.pyautogui.moveTo')
    @patch('functions.tools_mouse_keyboard.pyautogui.position')
    def test_mouse_move_success(self, mock_position, mock_move, controller):
        """Тест успішного переміщення курсора."""
        mock_position.return_value = MagicMock(x=50, y=50)

        result = controller.mouse_move(100, 200, duration=0.5)

        assert result['success'] is True
        assert result['from'] == {'x': 50, 'y': 50}
        assert result['to'] == {'x': 100, 'y': 200}
        mock_move.assert_called_once_with(100, 200, duration=0.5)

    @patch('functions.tools_mouse_keyboard.pyautogui.scroll')
    def test_mouse_scroll_vertical(self, mock_scroll, controller):
        """Тест вертикальної прокрутки."""
        result = controller.mouse_scroll(3)

        assert result['success'] is True
        assert result['amount'] == 3
        assert result['direction'] == 'vertical'
        mock_scroll.assert_called_once_with(3)

    @patch('functions.tools_mouse_keyboard.pyautogui.hscroll')
    def test_mouse_scroll_horizontal(self, mock_hscroll, controller):
        """Тест горизонтальної прокрутки."""
        result = controller.mouse_scroll(3, direction='horizontal')

        assert result['success'] is True
        assert result['direction'] == 'horizontal'
        mock_hscroll.assert_called_once_with(3)

    @patch('functions.tools_mouse_keyboard.pyautogui.moveTo')
    @patch('functions.tools_mouse_keyboard.pyautogui.dragTo')
    def test_mouse_drag_success(self, mock_drag, mock_move, controller):
        """Тест успішного drag & drop."""
        result = controller.mouse_drag(100, 100, 200, 200, duration=0.5, button='left')

        assert result['success'] is True
        assert result['start'] == {'x': 100, 'y': 100}
        assert result['end'] == {'x': 200, 'y': 200}
        mock_move.assert_called_once_with(100, 100)
        mock_drag.assert_called_once_with(200, 200, duration=0.5, button='left')

    @patch('functions.tools_mouse_keyboard.pyautogui.position')
    def test_get_mouse_position(self, mock_position, controller):
        """Тест отримання позиції курсора."""
        mock_position.return_value = MagicMock(x=150, y=250)

        result = controller.get_mouse_position()

        assert result == {'x': 150, 'y': 250}

    # ==================== Тести клавіатури ====================

    @patch('functions.tools_mouse_keyboard.pyautogui.press')
    def test_keyboard_press_success(self, mock_press, controller):
        """Тест успішного натискання клавіші."""
        result = controller.keyboard_press('enter')

        assert result['success'] is True
        assert result['key'] == 'enter'
        mock_press.assert_called_once_with('enter')

    @patch('functions.tools_mouse_keyboard.pyautogui.typewrite')
    def test_keyboard_type_success(self, mock_type, controller):
        """Тест успішного введення тексту."""
        result = controller.keyboard_type('Hello World', interval=0.02)

        assert result['success'] is True
        assert result['text'] == 'Hello World'
        assert result['length'] == 11
        mock_type.assert_called_once_with('Hello World', interval=0.02)

    @patch('functions.tools_mouse_keyboard.pyautogui.hotkey')
    def test_keyboard_hotkey_success(self, mock_hotkey, controller):
        """Тест успішної комбінації клавіш."""
        result = controller.keyboard_hotkey('ctrl', 'c')

        assert result['success'] is True
        assert result['hotkey'] == ['ctrl', 'c']
        mock_hotkey.assert_called_once_with('ctrl', 'c')

    @patch('functions.tools_mouse_keyboard.pyautogui.keyDown')
    @patch('functions.tools_mouse_keyboard.pyautogui.keyUp')
    @patch('functions.tools_mouse_keyboard.time.sleep')
    def test_keyboard_hold_success(self, mock_sleep, mock_keyup, mock_keydown, controller):
        """Тест успішного утримання клавіші."""
        result = controller.keyboard_hold('shift', duration=1.0)

        assert result['success'] is True
        assert result['key'] == 'shift'
        assert result['duration'] == 1.0
        mock_keydown.assert_called_once_with('shift')
        mock_keyup.assert_called_once_with('shift')
        mock_sleep.assert_called_once_with(1.0)

    @patch('functions.tools_mouse_keyboard.pyautogui.press')
    def test_keyboard_send_special_printscreen(self, mock_press, controller):
        """Тест спеціальної клавіші PrintScreen."""
        result = controller.keyboard_send_special('printscreen')

        assert result['success'] is True
        assert result['key'] == 'printscreen'

    @patch('functions.tools_mouse_keyboard.pyautogui.press')
    def test_keyboard_send_special_prtsc_alias(self, mock_press, controller):
        """Тест аліасу prtsc для PrintScreen."""
        result = controller.keyboard_send_special('prtsc')

        assert result['success'] is True
        assert result['key'] == 'printscreen'

    # ==================== Тести clipboard ====================

    @patch('functions.tools_mouse_keyboard.pyperclip.copy')
    def test_clipboard_copy_text_success(self, mock_copy, controller):
        """Тест копіювання тексту в буфер."""
        result = controller.clipboard_copy_text('Test text')

        assert result['success'] is True
        assert result['length'] == 9
        mock_copy.assert_called_once_with('Test text')

    @patch('functions.tools_mouse_keyboard.pyperclip.paste')
    def test_clipboard_get_text_success(self, mock_paste, controller):
        """Тест отримання тексту з буфера."""
        mock_paste.return_value = 'Pasted text'

        result = controller.clipboard_get_text()

        assert result['text'] == 'Pasted text'
        assert result['length'] == 11

    @patch('functions.tools_mouse_keyboard.os.path.exists')
    def test_clipboard_copy_image_not_found(self, mock_exists, controller):
        """Тест копіювання зображення — файл не знайдено."""
        mock_exists.return_value = False

        result = controller.clipboard_copy_image('nonexistent.png')

        assert result['success'] is False
        assert 'not found' in result['error'].lower()


# ==================== Тести функцій-обгорток ====================

@patch('functions.tools_mouse_keyboard.pyautogui.click')
def test_mouse_click_wrapper(mock_click):
    """Тест функції-обгортки mouse_click."""
    result = mouse_click(100, 200)
    assert result['success'] is True


@patch('functions.tools_mouse_keyboard.pyautogui.moveTo')
@patch('functions.tools_mouse_keyboard.pyautogui.position')
def test_mouse_move_wrapper(mock_position, mock_move):
    """Тест функції-обгортки mouse_move."""
    mock_position.return_value = MagicMock(x=0, y=0)
    result = mouse_move(100, 200)
    assert result['success'] is True


@patch('functions.tools_mouse_keyboard.pyautogui.typewrite')
def test_keyboard_type_wrapper(mock_type):
    """Тест функції-обгортки keyboard_type."""
    result = keyboard_type('test')
    assert result['success'] is True


@patch('functions.tools_mouse_keyboard.pyautogui.hotkey')
def test_keyboard_hotkey_wrapper(mock_hotkey):
    """Тест функції-обгортки keyboard_hotkey."""
    result = keyboard_hotkey('ctrl', 'c')
    assert result['success'] is True


@patch('functions.tools_mouse_keyboard.pyperclip.copy')
def test_clipboard_copy_text_wrapper(mock_copy):
    """Тест функції-обгортки clipboard_copy_text."""
    result = clipboard_copy_text('test')
    assert result['success'] is True


@patch('functions.tools_mouse_keyboard.pyperclip.paste')
def test_clipboard_get_text_wrapper(mock_paste):
    """Тест функції-обгортки clipboard_get_text."""
    mock_paste.return_value = 'test'
    result = clipboard_get_text()
    assert result['text'] == 'test'
