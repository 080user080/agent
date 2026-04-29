"""Global Voice Input — глобальне голосове введення в будь-яку програму.

Використовує Windows hooks для перехоплення гарячої клавіші, STT для розпізнавання
та SendInput/clipboard для вставки тексту в активне поле.

Використання:
    from functions.global_voice_input import GlobalVoiceInput

    def on_text(text):
        print(f"Розпізнано: {text}")

    gvi = GlobalVoiceInput(hotkey="ctrl+shift+v", callback=on_text)
    gvi.start()
"""
from __future__ import annotations

import ctypes
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from .core_stt_listener import STTListener
from .config import SAMPLE_RATE, LISTEN_DURATION, VOLUME_THRESHOLD, SILENCE_DURATION, MICROPHONE_DEVICE_ID


# Windows API для hooks
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Virtual key codes
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_V = 0x56
VK_LWIN = 0x5B


class HotkeyHook:
    """Windows low-level keyboard hook для перехоплення гарячих клавіш."""

    def __init__(self, hotkey: str):
        """
        Args:
            hotkey: Гаряча клавіша (наприклад "ctrl+shift+v", "win+v")
        """
        self.hotkey = hotkey.lower()
        self.keys_pressed = set()
        self.callback: Optional[Callable] = None
        self.hook_id = None

        # Парсинг hotkey
        self.required_keys = self._parse_hotkey(hotkey)

    def _parse_hotkey(self, hotkey: str) -> set[int]:
        """Перетворити hotkey string в set VK codes."""
        keys = set()
        parts = hotkey.split('+')
        for part in parts:
            part = part.strip().lower()
            if part == 'ctrl' or part == 'control':
                keys.add(VK_CONTROL)
            elif part == 'shift':
                keys.add(VK_SHIFT)
            elif part == 'win' or part == 'windows' or part == 'meta':
                keys.add(VK_LWIN)
            elif len(part) == 1:
                # Single letter
                vk = ord(part.upper())
                keys.add(vk)
        return keys

    def set_callback(self, callback: Callable) -> None:
        """Встановити callback при натисканні hotkey."""
        self.callback = callback

    def _keyboard_proc(self, n_code, w_param, l_param):
        """Callback для keyboard hook."""
        if n_code < 0:
            return user32.CallNextHookExW(self.hook_id, n_code, w_param, l_param)

        if w_param == WM_KEYDOWN or w_param == WM_SYSKEYDOWN:
            vk_code = l_param & 0xFF
            self.keys_pressed.add(vk_code)

            # Перевіряємо чи натиснута гаряча клавіша
            if self.required_keys.issubset(self.keys_pressed):
                if self.callback:
                    # Викликаємо callback в окремому потоці
                    threading.Thread(target=self.callback, daemon=True).start()
                # Не блокуємо клавішу (пропускаємо далі)

        elif w_param == WM_KEYUP or w_param == WM_SYSKEYUP:
            vk_code = l_param & 0xFF
            self.keys_pressed.discard(vk_code)

        return user32.CallNextHookExW(self.hook_id, n_code, w_param, l_param)

    def start(self) -> bool:
        """Запустити hook."""
        if self.hook_id:
            return False

        # Define hook callback type
        HOOKPROC = ctypes.CFUNCTYPE(
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p
        )

        self._hook_callback = HOOKPROC(self._keyboard_proc)

        self.hook_id = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_callback,
            kernel32.GetModuleHandleW(None),
            0
        )

        if not self.hook_id:
            return False

        # Start message loop
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

        return True

    def _message_loop(self):
        """Message loop для hook."""
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def stop(self):
        """Зупинити hook."""
        if self.hook_id:
            user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None


class GlobalVoiceInput:
    """Глобальне голосове введення."""

    def __init__(
        self,
        hotkey: str = "ctrl+shift+v",
        callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Args:
            hotkey: Гаряча клавіша (наприклад "ctrl+shift+v")
            callback: Функція, яка викликається з розпізнаним текстом
            status_callback: Функція для статусу (listening, processing, idle)
        """
        self.hotkey_hook = HotkeyHook(hotkey)
        self.callback = callback
        self.status_callback = status_callback

        # STT Listener (без wake word)
        self.stt_listener = STTListener(
            command_callback=self._on_text_recognized,
            status_callback=self._on_stt_status
        )

        self.is_running = False
        self.is_listening = False

    def _update_status(self, status: str):
        """Оновити статус."""
        if self.status_callback:
            try:
                self.status_callback(status)
            except Exception:
                pass

    def _on_stt_status(self, status: str, data=None):
        """Статус STT."""
        if status == "listening":
            self.is_listening = True
            self._update_status("🎤 Слухаю...")
        elif status == "processing":
            self._update_status("🔍 Розпізнаю...")
        elif status == "idle":
            self.is_listening = False
            self._update_status("✅ Готовий")
        elif status == "error":
            self.is_listening = False
            self._update_status("❌ Помилка")

    def _on_text_recognized(self, text: str):
        """Обробити розпізнаний текст."""
        self.is_listening = False
        self._update_status(f"✅ Розпізнано: {text}")

        # Вставити в активне поле
        self._insert_text(text)

        # Callback
        if self.callback:
            self.callback(text)

    def _insert_text(self, text: str) -> bool:
        """Вставити текст в активне поле через clipboard."""
        try:
            import pyperclip
            # Зберігаємо поточний clipboard
            old_clipboard = pyperclip.paste() if pyperclip else ""

            # Копіюємо новий текст
            pyperclip.copy(text)

            # Симулюємо Ctrl+V
            self._simulate_paste()

            # Відновлюємо старий clipboard (опціонально)
            if old_clipboard:
                time.sleep(0.1)
                pyperclip.copy(old_clipboard)

            return True
        except ImportError:
            # Fallback без pyperclip
            return self._insert_text_fallback(text)
        except Exception as e:
            print(f"Помилка вставки тексту: {e}")
            return False

    def _insert_text_fallback(self, text: str) -> bool:
        """Fallback вставка через Windows API clipboard."""
        try:
            # Windows clipboard API
            CF_UNICODETEXT = 13
            if user32.OpenClipboard(0):
                user32.EmptyClipboard()
                # Allocate memory
                size = (len(text) + 1) * 2
                handle = kernel32.GlobalAlloc(0x42, size)  # GMEM_MOVEABLE
                ptr = kernel32.GlobalLock(handle)
                # Write text
                ctypes.create_unicode_buffer(text, len(text))
                kernel32.GlobalUnlock(handle)
                user32.SetClipboardData(CF_UNICODETEXT, handle)
                user32.CloseClipboard()

                # Simulate Ctrl+V
                self._simulate_paste()
                return True
        except Exception as e:
            print(f"Fallback помилка: {e}")
        return False

    def _simulate_paste(self):
        """Симулювати Ctrl+V через SendInput."""
        try:
            # SendInput API
            INPUT = ctypes.c_ubyte * 40
            inputs = (INPUT * 2)()

            # Ctrl down
            inputs[0][0] = 1  # INPUT_KEYBOARD
            inputs[0][2] = VK_CONTROL

            # V down
            inputs[1][0] = 1  # INPUT_KEYBOARD
            inputs[1][2] = VK_V

            user32.SendInput(2, inputs, ctypes.sizeof(INPUT))

            # Ctrl up
            inputs[0][0] = 1  # INPUT_KEYBOARD
            inputs[0][4] = 2  # KEYEVENTF_KEYUP
            inputs[0][2] = VK_CONTROL

            # V up
            inputs[1][0] = 1  # INPUT_KEYBOARD
            inputs[1][4] = 2  # KEYEVENTF_KEYUP
            inputs[1][2] = VK_V

            user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
        except Exception as e:
            print(f"Помилка SendInput: {e}")

    def _on_hotkey_pressed(self):
        """Обробити натискання hotkey."""
        if self.is_listening:
            return

        if not self.stt_listener.stt_engine:
            if not self.stt_listener.initialize():
                return

        # Записати і розпізнати
        text = self.stt_listener.listen_once(duration=LISTEN_DURATION, wait_for_speech=True)
        if text:
            self._on_text_recognized(text)

    def start(self) -> bool:
        """Запустити глобальне голосове введення."""
        if self.is_running:
            return False

        if not self.stt_listener.initialize():
            return False

        # Налаштувати hotkey callback
        self.hotkey_hook.set_callback(self._on_hotkey_pressed)

        # Запустити hook
        if not self.hotkey_hook.start():
            return False

        self.is_running = True
        self._update_status(f"✅ Готово (hotkey: {self.hotkey_hook.hotkey})")
        return True

    def stop(self):
        """Зупинити глобальне голосове введення."""
        self.hotkey_hook.stop()
        self.stt_listener.stop()
        self.is_running = False
        self._update_status("⏹️ Зупинено")
