"""
Тести для модуля tools_window_manager.py

GUI Automation Phase 1 — керування вікнами Windows.
"""

import pytest
from unittest.mock import patch, MagicMock, call
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.tools_window_manager import (
    WindowManager,
    list_windows, find_window_by_title, find_window_by_process,
    activate_window, minimize_window, maximize_window, close_window,
    get_window_rect, is_window_visible, wait_for_window
)


class TestWindowManager:
    """Тести для класу WindowManager."""

    @pytest.fixture
    def manager(self):
        """Фікстура для створення менеджера."""
        return WindowManager()

    # ==================== Тести пошуку вікон ====================

    @patch('functions.tools_window_manager.win32gui.EnumWindows')
    @patch('functions.tools_window_manager.win32gui.IsWindowVisible')
    @patch('functions.tools_window_manager.win32gui.GetWindowText')
    @patch('functions.tools_window_manager.win32gui.GetWindowRect')
    def test_list_windows_visible_only(self, mock_rect, mock_text, mock_visible, mock_enum, manager):
        """Тест списку тільки видимих вікон."""
        # Симулюємо callback з двома вікнами
        def fake_enum(callback, _):
            callback(12345, None)  # Видиме вікно
            callback(67890, None)  # Приховане вікно

        mock_enum.side_effect = fake_enum
        mock_visible.side_effect = [True, False]  # Перше видиме, друге ні
        mock_text.return_value = "Test Window"
        mock_rect.return_value = (100, 100, 500, 400)

        with patch.object(manager, '_get_window_pid', return_value=1234):
            with patch.object(manager, '_get_process_name', return_value='notepad.exe'):
                result = manager.list_windows(include_hidden=False)

        # Тільки видиме вікно
        assert len(result) == 1
        assert result[0]['hwnd'] == 12345
        assert result[0]['title'] == "Test Window"
        assert result[0]['visible'] is True

    @patch('functions.tools_window_manager.win32gui.EnumWindows')
    @patch('functions.tools_window_manager.win32gui.IsWindowVisible')
    @patch('functions.tools_window_manager.win32gui.GetWindowText')
    def test_list_windows_include_hidden(self, mock_text, mock_visible, mock_enum, manager):
        """Тест списку з прихованими вікнами."""
        def fake_enum(callback, _):
            callback(12345, None)
            callback(67890, None)

        mock_enum.side_effect = fake_enum
        mock_visible.return_value = True
        mock_text.return_value = "Window"

        with patch.object(manager, '_get_window_pid', return_value=1234):
            with patch.object(manager, '_get_process_name', return_value='test.exe'):
                with patch('functions.tools_window_manager.win32gui.GetWindowRect', return_value=(0, 0, 100, 100)):
                    result = manager.list_windows(include_hidden=True)

        assert len(result) == 2

    @patch('functions.tools_window_manager.win32gui.EnumWindows')
    @patch('functions.tools_window_manager.win32gui.IsWindowVisible')
    @patch('functions.tools_window_manager.win32gui.GetWindowText')
    @patch('functions.tools_window_manager.win32gui.GetWindowRect')
    def test_find_window_by_title_partial(self, mock_rect, mock_text, mock_visible, mock_enum, manager):
        """Тест пошуку вікна за частковим збігом заголовка."""
        windows_data = [
            (11111, "Notepad - Untitled"),
            (22222, "Calculator"),
        ]

        call_count = [0]

        def fake_enum(callback, _):
            for hwnd, title in windows_data:
                call_count[0] += 1
                callback(hwnd, None)

        mock_enum.side_effect = fake_enum
        mock_visible.return_value = True

        text_results = {11111: "Notepad - Untitled", 22222: "Calculator"}

        def text_side_effect(hwnd):
            return text_results.get(hwnd, "")

        mock_text.side_effect = text_side_effect
        mock_rect.return_value = (0, 0, 100, 100)

        with patch.object(manager, '_get_window_pid', return_value=1234):
            with patch.object(manager, '_get_process_name', return_value='test.exe'):
                result = manager.find_window_by_title("notepad", exact=False)

        assert result == 11111

    @patch('functions.tools_window_manager.win32gui.EnumWindows')
    @patch('functions.tools_window_manager.win32gui.IsWindowVisible')
    @patch('functions.tools_window_manager.win32gui.GetWindowText')
    @patch('functions.tools_window_manager.win32gui.GetWindowRect')
    def test_find_window_by_title_exact(self, mock_rect, mock_text, mock_visible, mock_enum, manager):
        """Тест пошуку вікна за точним заголовком."""
        windows_data = [
            (11111, "Exact Title"),
            (22222, "Another Title"),
        ]

        def fake_enum(callback, _):
            for hwnd, title in windows_data:
                callback(hwnd, None)

        mock_enum.side_effect = fake_enum
        mock_visible.return_value = True

        text_results = {11111: "Exact Title", 22222: "Another Title"}
        mock_text.side_effect = lambda hwnd: text_results.get(hwnd, "")
        mock_rect.return_value = (0, 0, 100, 100)

        with patch.object(manager, '_get_window_pid', return_value=1234):
            with patch.object(manager, '_get_process_name', return_value='test.exe'):
                result = manager.find_window_by_title("Exact Title", exact=True)

        assert result == 11111

    # ==================== Тести керування вікнами ====================

    @patch('functions.tools_window_manager.win32gui.IsIconic')
    @patch('functions.tools_window_manager.win32gui.ShowWindow')
    @patch('functions.tools_window_manager.win32gui.SetForegroundWindow')
    @patch('functions.tools_window_manager.win32process.GetCurrentThreadId')
    @patch('functions.tools_window_manager.win32process.GetWindowThreadProcessId')
    @patch('functions.tools_window_manager.win32process.AttachThreadInput')
    def test_activate_window_success(self, mock_attach, mock_get_thread, mock_current_thread,
                                     mock_set_fg, mock_show, mock_is_iconic, manager):
        """Тест успішної активації вікна."""
        mock_is_iconic.return_value = False
        mock_current_thread.return_value = 1234
        mock_get_thread.return_value = (5678, None)

        result = manager.activate_window(11111)

        assert result['success'] is True
        assert result['hwnd'] == 11111
        mock_set_fg.assert_called_once_with(11111)
        mock_attach.assert_has_calls([
            call(1234, 5678, True),
            call(1234, 5678, False)
        ])

    @patch('functions.tools_window_manager.win32gui.IsIconic')
    @patch('functions.tools_window_manager.win32gui.ShowWindow')
    @patch('functions.tools_window_manager.win32gui.SetForegroundWindow')
    def test_activate_window_minimized(self, mock_set_fg, mock_show, mock_is_iconic, manager):
        """Тест активації згорнутого вікна (спочатку restore)."""
        mock_is_iconic.return_value = True

        with patch('functions.tools_window_manager.win32process.GetCurrentThreadId', return_value=1):
            with patch('functions.tools_window_manager.win32process.GetWindowThreadProcessId', return_value=(2, None)):
                with patch('functions.tools_window_manager.win32process.AttachThreadInput'):
                    result = manager.activate_window(11111)

        # Перевіряємо, що було викликано SW_RESTORE
        mock_show.assert_any_call(11111, 9)  # win32con.SW_RESTORE = 9

    @patch('functions.tools_window_manager.win32gui.ShowWindow')
    def test_minimize_window_success(self, mock_show, manager):
        """Тест згортання вікна."""
        result = manager.minimize_window(11111)

        assert result['success'] is True
        assert result['action'] == 'minimize'
        mock_show.assert_called_once_with(11111, 6)  # SW_MINIMIZE = 6

    @patch('functions.tools_window_manager.win32gui.ShowWindow')
    def test_maximize_window_success(self, mock_show, manager):
        """Тест розгортання вікна."""
        result = manager.maximize_window(11111)

        assert result['success'] is True
        assert result['action'] == 'maximize'
        mock_show.assert_called_once_with(11111, 3)  # SW_MAXIMIZE = 3

    @patch('functions.tools_window_manager.win32gui.ShowWindow')
    def test_restore_window_success(self, mock_show, manager):
        """Тест відновлення вікна."""
        result = manager.restore_window(11111)

        assert result['success'] is True
        assert result['action'] == 'restore'
        mock_show.assert_called_once_with(11111, 9)  # SW_RESTORE = 9

    @patch('functions.tools_window_manager.win32gui.PostMessage')
    def test_close_window_soft(self, mock_post, manager):
        """Тест м'якого закриття вікна (WM_CLOSE)."""
        result = manager.close_window(11111, force=False)

        assert result['success'] is True
        assert result['action'] == 'close'
        mock_post.assert_called_once_with(11111, 16, 0, 0)  # WM_CLOSE = 16

    @patch('functions.tools_window_manager.psutil.Process')
    @patch.object(WindowManager, '_get_window_pid')
    def test_close_window_force(self, mock_get_pid, mock_process_class, manager):
        """Тест форсованого закриття вікна (terminate)."""
        mock_get_pid.return_value = 1234
        mock_process = MagicMock()
        mock_process_class.return_value = mock_process

        result = manager.close_window(11111, force=True)

        assert result['success'] is True
        assert result['action'] == 'force_close'
        mock_process.terminate.assert_called_once()

    @patch('functions.tools_window_manager.win32gui.MoveWindow')
    @patch('functions.tools_window_manager.win32gui.GetWindowRect')
    def test_move_window_success(self, mock_rect, mock_move, manager):
        """Тест переміщення вікна."""
        mock_rect.return_value = (100, 100, 500, 400)  # x, y, right, bottom

        result = manager.move_window(11111, 200, 300)

        assert result['success'] is True
        assert result['position'] == {'x': 200, 'y': 300}
        mock_move.assert_called_once_with(11111, 200, 300, 400, 300, True)  # width=400, height=300

    @patch('functions.tools_window_manager.win32gui.MoveWindow')
    @patch('functions.tools_window_manager.win32gui.GetWindowRect')
    def test_resize_window_success(self, mock_rect, mock_move, manager):
        """Тест зміни розміру вікна."""
        mock_rect.return_value = (100, 100, 500, 400)

        result = manager.resize_window(11111, 800, 600)

        assert result['success'] is True
        assert result['size'] == {'width': 800, 'height': 600}
        mock_move.assert_called_once_with(11111, 100, 100, 800, 600, True)

    @patch('functions.tools_window_manager.win32gui.MoveWindow')
    def test_move_resize_window_success(self, mock_move, manager):
        """Тест одночасного переміщення та зміни розміру."""
        result = manager.move_resize_window(11111, 100, 200, 800, 600)

        assert result['success'] is True
        assert result['position'] == {'x': 100, 'y': 200}
        assert result['size'] == {'width': 800, 'height': 600}
        mock_move.assert_called_once_with(11111, 100, 200, 800, 600, True)

    @patch('functions.tools_window_manager.win32gui.GetWindowRect')
    def test_get_window_rect_success(self, mock_rect, manager):
        """Тест отримання координат вікна."""
        mock_rect.return_value = (100, 200, 500, 600)

        result = manager.get_window_rect(11111)

        assert result == {'x': 100, 'y': 200, 'width': 400, 'height': 400}

    @patch('functions.tools_window_manager.win32gui.IsWindowVisible')
    def test_is_window_visible_true(self, mock_visible, manager):
        """Тест перевірки видимості — видиме."""
        mock_visible.return_value = True

        result = manager.is_window_visible(11111)

        assert result is True

    @patch('functions.tools_window_manager.win32gui.IsWindowVisible')
    def test_is_window_visible_false(self, mock_visible, manager):
        """Тест перевірки видимості — приховане."""
        mock_visible.return_value = False

        result = manager.is_window_visible(11111)

        assert result is False

    @patch('functions.tools_window_manager.win32gui.IsIconic')
    def test_is_window_minimized_true(self, mock_iconic, manager):
        """Тест перевірки згорнутості."""
        mock_iconic.return_value = True

        result = manager.is_window_minimized(11111)

        assert result is True

    @patch('functions.tools_window_manager.win32gui.GetWindowPlacement')
    def test_is_window_maximized_true(self, mock_placement, manager):
        """Тест перевірки розгорнутості."""
        mock_placement.return_value = (None, 3, None)  # SW_SHOWMAXIMIZED = 3

        result = manager.is_window_maximized(11111)

        assert result is True

    @patch('functions.tools_window_manager.win32gui.GetForegroundWindow')
    @patch('functions.tools_window_manager.win32gui.GetWindowText')
    @patch('functions.tools_window_manager.win32gui.GetWindowRect')
    def test_get_active_window_success(self, mock_rect, mock_text, mock_fg, manager):
        """Тест отримання активного вікна."""
        mock_fg.return_value = 11111
        mock_text.return_value = "Active Window"
        mock_rect.return_value = (0, 0, 100, 100)

        with patch.object(manager, '_get_window_pid', return_value=1234):
            with patch.object(manager, '_get_process_name', return_value='test.exe'):
                result = manager.get_active_window()

        assert result['hwnd'] == 11111
        assert result['title'] == "Active Window"
        assert result['process_name'] == 'test.exe'

    @patch('functions.tools_window_manager.win32gui.GetForegroundWindow')
    def test_get_active_window_none(self, mock_fg, manager):
        """Тест коли немає активного вікна."""
        mock_fg.return_value = 0

        result = manager.get_active_window()

        assert 'error' in result

    @patch('functions.tools_window_manager.time.sleep')
    @patch('functions.tools_window_manager.win32gui.IsWindow')
    def test_wait_window_close_success(self, mock_is_window, mock_sleep, manager):
        """Тест успішного очікування закриття вікна."""
        mock_is_window.side_effect = [True, True, False]  # Вікно закривається на 3-й перевірці

        result = manager.wait_window_close(11111, timeout=1.0)

        assert result is True

    @patch('functions.tools_window_manager.time.sleep')
    @patch('functions.tools_window_manager.win32gui.IsWindow')
    def test_wait_window_close_timeout(self, mock_is_window, mock_sleep, manager):
        """Тест timeout при очікуванні закриття."""
        mock_is_window.return_value = True  # Вікно ніколи не закривається

        result = manager.wait_window_close(11111, timeout=0.1)

        assert result is False


# ==================== Тести функцій-обгорток ====================

@patch('functions.tools_window_manager.win32gui.EnumWindows')
@patch('functions.tools_window_manager.win32gui.IsWindowVisible')
@patch('functions.tools_window_manager.win32gui.GetWindowText')
@patch('functions.tools_window_manager.win32gui.GetWindowRect')
def test_list_windows_wrapper(mock_rect, mock_text, mock_visible, mock_enum):
    """Тест функції-обгортки list_windows."""
    def fake_enum(callback, _):
        callback(12345, None)

    mock_enum.side_effect = fake_enum
    mock_visible.return_value = True
    mock_text.return_value = "Test"
    mock_rect.return_value = (0, 0, 100, 100)

    with patch('functions.tools_window_manager.WindowManager._get_window_pid', return_value=1):
        with patch('functions.tools_window_manager.WindowManager._get_process_name', return_value='test.exe'):
            result = list_windows()

    assert isinstance(result, list)


@patch('functions.tools_window_manager.win32gui.EnumWindows')
@patch('functions.tools_window_manager.win32gui.IsWindowVisible')
@patch('functions.tools_window_manager.win32gui.GetWindowText')
def test_find_window_by_title_wrapper(mock_text, mock_visible, mock_enum):
    """Тест функції-обгортки find_window_by_title."""
    def fake_enum(callback, _):
        callback(12345, None)

    mock_enum.side_effect = fake_enum
    mock_visible.return_value = True
    mock_text.return_value = "Notepad Window"

    with patch('functions.tools_window_manager.win32gui.GetWindowRect', return_value=(0, 0, 100, 100)):
        with patch('functions.tools_window_manager.WindowManager._get_window_pid', return_value=1):
            with patch('functions.tools_window_manager.WindowManager._get_process_name', return_value='notepad.exe'):
                result = find_window_by_title("Notepad", exact=False)

    assert result == 12345


@patch('functions.tools_window_manager.win32gui.ShowWindow')
def test_minimize_window_wrapper(mock_show):
    """Тест функції-обгортки minimize_window."""
    result = minimize_window(11111)
    assert result['success'] is True


@patch('functions.tools_window_manager.win32gui.ShowWindow')
def test_maximize_window_wrapper(mock_show):
    """Тест функції-обгортки maximize_window."""
    result = maximize_window(11111)
    assert result['success'] is True


@patch('functions.tools_window_manager.win32gui.PostMessage')
def test_close_window_wrapper(mock_post):
    """Тест функції-обгортки close_window."""
    result = close_window(11111)
    assert result['success'] is True


@patch('functions.tools_window_manager.win32gui.GetWindowRect')
def test_get_window_rect_wrapper(mock_rect):
    """Тест функції-обгортки get_window_rect."""
    mock_rect.return_value = (100, 100, 500, 400)
    result = get_window_rect(11111)
    assert result['width'] == 400


@patch('functions.tools_window_manager.win32gui.IsWindowVisible')
def test_is_window_visible_wrapper(mock_visible):
    """Тест функції-обгортки is_window_visible."""
    mock_visible.return_value = True
    result = is_window_visible(11111)
    assert result is True


@patch('functions.tools_window_manager.win32gui.EnumWindows')
@patch('functions.tools_window_manager.win32gui.IsWindowVisible')
@patch('functions.tools_window_manager.win32gui.GetWindowText')
@patch('functions.tools_window_manager.time.sleep')
def test_wait_for_window_success(mock_sleep, mock_text, mock_visible, mock_enum):
    """Тест функції-обгортки wait_for_window — успіх."""
    call_count = [0]

    def fake_enum(callback, _):
        call_count[0] += 1
        if call_count[0] >= 2:  # На другій спробі знаходимо
            callback(12345, None)

    mock_enum.side_effect = fake_enum
    mock_visible.return_value = True
    mock_text.return_value = "Target Window"

    with patch('functions.tools_window_manager.win32gui.GetWindowRect', return_value=(0, 0, 100, 100)):
        with patch('functions.tools_window_manager.WindowManager._get_window_pid', return_value=1):
            with patch('functions.tools_window_manager.WindowManager._get_process_name', return_value='test.exe'):
                result = wait_for_window("Target", timeout=1.0)

    assert result == 12345
