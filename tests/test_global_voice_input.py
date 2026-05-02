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
    @patch("functions.global_voice_input.pyperclip")
    @patch("functions.aaa_voice_input.activate_window_by_title")
    @patch("functions.tools_mouse_keyboard.keyboard_hotkey")
    @patch("functions.tools_mouse_keyboard.keyboard_type")
    def test_insert_text_uses_win32_paste_first(
        self,
        mock_keyboard_type,
        mock_keyboard_hotkey,
        mock_activate_window,
        mock_pyperclip,
        mock_sleep,
        mock_stt_listener,
    ):
        from functions.global_voice_input import GlobalVoiceInput

        mock_pyperclip.paste.return_value = "old clipboard"
        mock_keyboard_hotkey.return_value = {"success": True, "hotkey": ["ctrl", "v"]}
        mock_activate_window.return_value = True

        gvi = GlobalVoiceInput()
        gvi._last_window_title = "AkelPad"
        gvi._last_window_hwnd = 12345

        with patch.object(gvi, "_paste_into_window", return_value=True) as mock_paste_into_window, \
             patch.object(gvi, "_set_clipboard_text_verified", return_value=True) as mock_set_clipboard, \
             patch.object(gvi, "_resolve_focus_target", return_value=(12345, "AkelEditW")):
            result = gvi._insert_text("Перевірте, чи працює.")

        assert result is True
        mock_activate_window.assert_called_once_with("AkelPad")
        mock_set_clipboard.assert_called_once_with("Перевірте, чи працює.")
        mock_paste_into_window.assert_called_once_with(12345)
        mock_keyboard_type.assert_not_called()
        mock_keyboard_hotkey.assert_not_called()
        mock_pyperclip.copy.assert_called_with("old clipboard")

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.time.sleep", return_value=None)
    @patch("functions.global_voice_input.pyperclip")
    @patch("functions.aaa_voice_input.activate_window_by_title")
    @patch("functions.tools_mouse_keyboard.keyboard_hotkey")
    @patch("functions.tools_mouse_keyboard.keyboard_type")
    def test_insert_text_returns_false_when_copy_fails(
        self,
        mock_keyboard_type,
        mock_keyboard_hotkey,
        mock_activate_window,
        mock_pyperclip,
        mock_sleep,
        mock_stt_listener,
    ):
        from functions.global_voice_input import GlobalVoiceInput

        mock_pyperclip.paste.return_value = "old clipboard"
        mock_activate_window.return_value = True

        gvi = GlobalVoiceInput()
        gvi._last_window_title = "AkelPad"
        gvi._last_window_hwnd = 12345

        with patch.object(gvi, "_paste_into_window", return_value=False), \
             patch.object(gvi, "_set_clipboard_text_verified", return_value=False):
            result = gvi._insert_text("Перевірте, чи працює.")

        assert result is False
        mock_keyboard_type.assert_not_called()
        mock_keyboard_hotkey.assert_not_called()

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.time.sleep", return_value=None)
    @patch("functions.global_voice_input.pyperclip")
    @patch("functions.aaa_voice_input.activate_window_by_title")
    @patch("functions.tools_mouse_keyboard.keyboard_hotkey")
    @patch("functions.tools_mouse_keyboard.keyboard_type")
    def test_insert_text_uses_ctrl_v_for_browser_chat(
        self,
        mock_keyboard_type,
        mock_keyboard_hotkey,
        mock_activate_window,
        mock_pyperclip,
        mock_sleep,
        mock_stt_listener,
    ):
        from functions.global_voice_input import GlobalVoiceInput

        mock_pyperclip.paste.return_value = "old clipboard"
        mock_keyboard_hotkey.return_value = {"success": True, "hotkey": ["ctrl", "v"]}
        mock_activate_window.return_value = True

        gvi = GlobalVoiceInput()
        gvi._last_window_title = "Google Gemini - Google Chrome"
        gvi._last_window_hwnd = 12345

        with patch.object(gvi, "_paste_into_window", return_value=False) as mock_paste_into_window, \
             patch.object(gvi, "_set_clipboard_text_verified", return_value=True), \
             patch.object(gvi, "_resolve_focus_target", return_value=(12345, "Chrome_WidgetWin_1")):
            result = gvi._insert_text("Перевірте, чи працює.")

        assert result is True
        mock_paste_into_window.assert_not_called()
        mock_keyboard_type.assert_not_called()
        mock_keyboard_hotkey.assert_called_once_with("ctrl", "v")

    @patch("functions.global_voice_input.STTListener")
    @patch("functions.global_voice_input.time.sleep", return_value=None)
    @patch("functions.global_voice_input.pyperclip")
    @patch("functions.aaa_voice_input.activate_window_by_title")
    @patch("functions.tools_mouse_keyboard.keyboard_hotkey")
    @patch("functions.tools_mouse_keyboard.keyboard_type")
    def test_insert_text_falls_back_to_typewrite_when_ctrl_v_fails(
        self,
        mock_keyboard_type,
        mock_keyboard_hotkey,
        mock_activate_window,
        mock_pyperclip,
        mock_sleep,
        mock_stt_listener,
    ):
        from functions.global_voice_input import GlobalVoiceInput

        mock_pyperclip.paste.return_value = "old clipboard"
        mock_keyboard_type.return_value = {"success": True, "text": "Перевірте, чи працює."}
        mock_keyboard_hotkey.return_value = {"success": False, "error": "ctrl+v failed"}
        mock_activate_window.return_value = True

        gvi = GlobalVoiceInput()
        gvi._last_window_title = "Google Gemini - Google Chrome"
        gvi._last_window_hwnd = 12345

        with patch.object(gvi, "_paste_into_window", return_value=False) as mock_paste_into_window, \
             patch.object(gvi, "_set_clipboard_text_verified", return_value=True), \
             patch.object(gvi, "_resolve_focus_target", return_value=(12345, "Chrome_WidgetWin_1")):
            result = gvi._insert_text("Перевірте, чи працює.")

        assert result is True
        mock_paste_into_window.assert_not_called()
        mock_keyboard_hotkey.assert_called_once_with("ctrl", "v")
        mock_keyboard_type.assert_called_once_with(text="Перевірте, чи працює.")

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

        with patch.object(gvi, "_insert_text", return_value=True):
            gvi._on_text_recognized("test text")

        callback.assert_called_once_with("test text")

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
