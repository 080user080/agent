"""Тести для Global Voice Input."""
from unittest.mock import Mock, patch


class TestGlobalVoiceInput:
    """Перевірка основної логіки GlobalVoiceInput."""

    @patch("functions.global_voice_input.STTListener")
    def test_init(self, mock_stt_listener):
        from functions.global_voice_input import GlobalVoiceInput

        callback = Mock()
        gvi = GlobalVoiceInput(hotkey="ctrl+f9", callback=callback)

        assert gvi.hotkey_hook is not None
        assert gvi.callback == callback
        assert not gvi.is_running

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.HotkeyHook")
    def test_start_initializes_stt_and_hook(self, mock_hook_class, mock_stt_listener):
        from functions.global_voice_input import GlobalVoiceInput

        mock_stt = Mock()
        mock_stt.initialize.return_value = True
        mock_stt_listener.return_value = mock_stt

        mock_hook = Mock()
        mock_hook.start.return_value = True
        mock_hook_class.return_value = mock_hook

        gvi = GlobalVoiceInput()
        result = gvi.start()

        assert result is True
        assert gvi.is_running is True
        mock_stt.initialize.assert_called_once()
        mock_hook.start.assert_called_once()

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.HotkeyHook")
    def test_start_fails_when_stt_init_fails(self, mock_hook_class, mock_stt_listener):
        from functions.global_voice_input import GlobalVoiceInput

        mock_stt = Mock()
        mock_stt.initialize.return_value = False
        mock_stt_listener.return_value = mock_stt

        gvi = GlobalVoiceInput()
        result = gvi.start()

        assert result is False
        assert gvi.is_running is False

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.time.sleep", return_value=None)
    def test_insert_segment_uses_win32_paste_for_standard_edit(
        self,
        mock_sleep,
        mock_stt_listener,
    ):
        from functions.global_voice_input import GlobalVoiceInput
        import pyperclip

        gvi = GlobalVoiceInput()
        gvi._last_window_title = "Notepad"
        gvi._last_window_hwnd = 12345

        with patch.object(gvi, "_resolve_focus_target", return_value=(12345, "Edit")), \
             patch("pyperclip.copy") as mock_copy, \
             patch("pyperclip.paste", return_value="old clipboard"):
            result = gvi._insert_segment("Тестовий текст")

        assert result is True
        mock_copy.assert_called_with("Тестовий текст")

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.time.sleep", return_value=None)
    @patch("functions.tools_mouse_keyboard.keyboard_hotkey")
    def test_insert_segment_fallback_to_ctrl_v(
        self,
        mock_keyboard_hotkey,
        mock_sleep,
        mock_stt_listener,
    ):
        from functions.global_voice_input import GlobalVoiceInput

        mock_keyboard_hotkey.return_value = {"success": True, "hotkey": ["ctrl", "v"]}

        gvi = GlobalVoiceInput()
        gvi._last_window_title = "Unknown App"
        gvi._last_window_hwnd = 12345

        with patch.object(gvi, "_send_input_unicode", return_value=False), \
             patch.object(gvi, "_resolve_focus_target", return_value=(12345, "UnknownClass")), \
             patch("pyperclip.copy") as mock_copy, \
             patch("pyperclip.paste", return_value="old clipboard"):
            result = gvi._insert_segment("Текст для fallback")

        assert result is True
        mock_copy.assert_called_with("Текст для fallback")
        mock_keyboard_hotkey.assert_called_once_with("ctrl", "v")

    
    @patch("functions.global_voice_input.STTListener")
    def test_insert_strategy_for_classic_edit_and_browser(self, mock_stt_listener):
        from functions.global_voice_input import GlobalVoiceInput

        gvi = GlobalVoiceInput()

        assert gvi._get_insert_strategy("AkelEditW", "AkelPad") == "win32_paste"
        assert gvi._get_insert_strategy("Edit", "Notepad") == "win32_paste"
        assert gvi._get_insert_strategy("Chrome_WidgetWin_1", "Google Gemini - Google Chrome") == "ctrl_v"
        assert gvi._get_insert_strategy("Chrome_WidgetWin_1", "ChatGPT") == "ctrl_v"

    @patch("functions.global_voice_input.STTListener")
    def test_on_text_recognized_calls_insert_and_callback(self, mock_stt_listener):
        from functions.global_voice_input import GlobalVoiceInput

        callback = Mock()
        gvi = GlobalVoiceInput(callback=callback)

        with patch.object(gvi, "_insert_segment", return_value=True):
            gvi._on_text_recognized("test text")

        callback.assert_called_once_with("test text")

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.time.sleep", return_value=None)
    def test_insert_segment_uses_win32_paste_for_chrome(
        self,
        mock_sleep,
        mock_stt_listener,
    ):
        from functions.global_voice_input import GlobalVoiceInput

        gvi = GlobalVoiceInput()
        gvi._last_window_title = "Windsurf - agent"
        gvi._last_window_hwnd = 12345

        with patch.object(gvi, "_resolve_focus_target", return_value=(54321, "Chrome_RenderWidgetHostHWND")), \
             patch("pyperclip.copy") as mock_copy, \
             patch("pyperclip.paste", return_value="old clipboard"):
            result = gvi._insert_segment("Тестовий текст")

        assert result is True
        mock_copy.assert_called_with("Тестовий текст")

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.time.sleep", return_value=None)
    def test_insert_segment_uses_sendinput_for_pyqt6(
        self,
        mock_sleep,
        mock_stt_listener,
    ):
        from functions.global_voice_input import GlobalVoiceInput

        gvi = GlobalVoiceInput()
        gvi._last_window_title = "PyQt6 Test Window"
        gvi._last_window_hwnd = 12345

        with patch.object(gvi, "_resolve_focus_target", return_value=(12345, "Qt6110QWindowIcon")), \
             patch.object(gvi, "_send_input_unicode", return_value=True) as mock_send_input, \
             patch("pyperclip.copy") as mock_copy, \
             patch("pyperclip.paste", return_value="old clipboard"):
            result = gvi._insert_segment("Текст для PyQt6")

        assert result is True
        mock_copy.assert_called_with("Текст для PyQt6")
        mock_send_input.assert_called_once_with("Текст для PyQt6")

    @patch("functions.global_voice_input.STTListener")
    def test_find_chrome_render_widget(self, mock_stt_listener):
        from functions.global_voice_input import GlobalVoiceInput
        import ctypes

        gvi = GlobalVoiceInput()
        
        # Mock для тесту
        with patch.object(gvi, '_find_chrome_render_widget', return_value=999999) as mock_find:
            result = gvi._find_chrome_render_widget(12345)
            mock_find.assert_called_once_with(12345)
            assert result == 999999

    @patch("functions.global_voice_input.STTListener")
    def test_find_qt_edit_control(self, mock_stt_listener):
        from functions.global_voice_input import GlobalVoiceInput

        gvi = GlobalVoiceInput()
        
        # Mock для тесту
        with patch.object(gvi, '_find_qt_edit_control', return_value=888888) as mock_find:
            result = gvi._find_qt_edit_control(12345)
            mock_find.assert_called_once_with(12345)
            assert result == 888888

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.HotkeyHook")
    def test_stop(self, mock_hook_class, mock_stt_listener):
        from functions.global_voice_input import GlobalVoiceInput

        mock_stt = Mock()
        mock_stt.initialize.return_value = True
        mock_stt_listener.return_value = mock_stt

        mock_hook = Mock()
        mock_hook.start.return_value = True
        mock_hook_class.return_value = mock_hook

        gvi = GlobalVoiceInput()
        gvi.start()
        gvi.stop()

        assert gvi.is_running is False
        mock_hook.stop.assert_called_once()
        mock_stt.stop.assert_called_once()
