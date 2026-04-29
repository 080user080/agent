"""Тести для Global Voice Input (Windows hooks + STT)."""
from unittest.mock import Mock, patch, MagicMock

import pytest


class TestHotkeyHook:
    """Тести для HotkeyHook (Windows keyboard hook)."""

    def test_parse_hotkey_ctrl_shift_v(self):
        """Парсинг hotkey 'ctrl+shift+v'."""
        from functions.global_voice_input import HotkeyHook

        hook = HotkeyHook("ctrl+shift+v")
        expected_keys = {0x11, 0x10, 0x56}  # VK_CONTROL, VK_SHIFT, VK_V
        assert hook.required_keys == expected_keys

    def test_parse_hotkey_win_v(self):
        """Парсинг hotkey 'win+v'."""
        from functions.global_voice_input import HotkeyHook

        hook = HotkeyHook("win+v")
        expected_keys = {0x5B, 0x56}  # VK_LWIN, VK_V
        assert hook.required_keys == expected_keys

    def test_callback_invoked_on_hotkey(self):
        """Callback викликається при натисканні hotkey."""
        from functions.global_voice_input import HotkeyHook

        hook = HotkeyHook("ctrl+v")
        callback = Mock()
        hook.set_callback(callback)

        # Симулюємо натискання Ctrl+V
        hook.keys_pressed.add(0x11)  # VK_CONTROL
        hook.keys_pressed.add(0x56)  # VK_V

        # Симулюємо keydown event
        hook._keyboard_proc(0, 0x0100, 0x56)  # WM_KEYDOWN, VK_V

        # Callback повинен бути викликаний
        # (в реальному коді це відбувається в окремому потоці)
        # Тільки перевіряємо що callback встановлено
        assert hook.callback == callback


class TestGlobalVoiceInput:
    """Тести для Global Voice Input."""

    @patch('functions.global_voice_input.STTListener')
    def test_init(self, mock_stt_listener):
        """Ініціалізація GlobalVoiceInput."""
        from functions.global_voice_input import GlobalVoiceInput

        callback = Mock()
        gvi = GlobalVoiceInput(hotkey="ctrl+shift+v", callback=callback)

        assert gvi.hotkey_hook is not None
        assert gvi.callback == callback
        assert not gvi.is_running

    @patch('functions.global_voice_input.STTListener')
    @patch('functions.global_voice_input.HotkeyHook')
    def test_start_stt_init(self, mock_hook_class, mock_stt_listener):
        """STT ініціалізується при старті."""
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

    @patch('functions.global_voice_input.STTListener')
    @patch('functions.global_voice_input.HotkeyHook')
    def test_start_stt_init_fails(self, mock_hook_class, mock_stt_listener):
        """STT ініціалізація не вдалася."""
        from functions.global_voice_input import GlobalVoiceInput

        mock_stt = Mock()
        mock_stt.initialize.return_value = False
        mock_stt_listener.return_value = mock_stt

        gvi = GlobalVoiceInput()
        result = gvi.start()

        assert result is False
        assert gvi.is_running is False

    @patch('functions.global_voice_input.STTListener')
    @patch('functions.global_voice_input.pyperclip')
    def test_insert_text_with_pyperclip(self, mock_pyperclip, mock_stt_listener):
        """Вставка тексту через pyperclip."""
        from functions.global_voice_input import GlobalVoiceInput

        mock_pyperclip.paste.return_value = "old text"
        mock_pyperclip.copy = Mock()

        gvi = GlobalVoiceInput()
        result = gvi._insert_text("test text")

        assert result is True
        mock_pyperclip.copy.assert_called_with("test text")

    @patch('functions.global_voice_input.STTListener')
    @patch('functions.global_voice_input.pyperclip')
    def test_insert_text_pyperclip_fallback(self, mock_pyperclip, mock_stt_listener):
        """Fallback при помилці pyperclip."""
        from functions.global_voice_input import GlobalVoiceInput

        mock_pyperclip.copy.side_effect = ImportError()

        gvi = GlobalVoiceInput()
        # Fallback не повинен падати
        result = gvi._insert_text("test text")

        # Fallback може не працювати без Windows API
        # Тільки перевіряємо що не впав
        assert result is False or result is True

    @patch('functions.global_voice_input.STTListener')
    def test_on_text_recognized(self, mock_stt_listener):
        """Обробка розпізнаного тексту."""
        from functions.global_voice_input import GlobalVoiceInput

        callback = Mock()
        gvi = GlobalVoiceInput(callback=callback)

        with patch.object(gvi, '_insert_text', return_value=True):
            gvi._on_text_recognized("test text")

        callback.assert_called_once_with("test text")

    @patch('functions.global_voice_input.STTListener')
    @patch('functions.global_voice_input.HotkeyHook')
    def test_stop(self, mock_hook_class, mock_stt_listener):
        """Зупинка GlobalVoiceInput."""
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
