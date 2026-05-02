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
from .voice_tray_icon import get_voice_tray_icon, VoiceStatus


# Windows API для hooks
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# Virtual key codes
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_G = 0x47
VK_V = 0x56
VK_LWIN = 0x5B

# KBDLLHOOKSTRUCT для правильного читання vkCode
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_uint),
        ("scanCode", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("time", ctypes.c_uint),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class HotkeyHook:
    """Windows hotkey через pynput (працює без прав адміністратора)."""

    def __init__(self, hotkey: str):
        """
        Args:
            hotkey: Гаряча клавіша (наприклад "ctrl+shift+v", "win+v")
        """
        self.hotkey = hotkey.lower()
        self.callback: Optional[Callable] = None
        self.listener = None
        self.pynput_available = False

        # Стан модифікаторів
        self.ctrl_pressed = False
        self.shift_pressed = False
        self.win_pressed = False

        try:
            from pynput import keyboard
            self.pynput_available = True
            self.keyboard = keyboard
        except ImportError:
            print("⚠️ pynput не встановлено - hotkey не працюватиме")

    def set_callback(self, callback: Callable) -> None:
        """Встановити callback при натисканні hotkey."""
        self.callback = callback

    def _on_press(self, key):
        """Обробити натискання клавіші."""
        try:
            from pynput.keyboard import Key

            # Оновити стан модифікаторів
            if key == Key.ctrl_l or key == Key.ctrl_r:
                self.ctrl_pressed = True
                return
            elif key == Key.shift_l or key == Key.shift_r:
                self.shift_pressed = True
                return
            elif key == Key.cmd or key == Key.cmd_l or key == Key.cmd_r:
                self.win_pressed = True
                return

            # Парсинг hotkey
            parts = self.hotkey.split('+')
            ctrl_needed = any(p.strip().lower() in ['ctrl', 'control'] for p in parts)
            shift_needed = any(p.strip().lower() == 'shift' for p in parts)
            win_needed = any(p.strip().lower() in ['win', 'windows', 'meta'] for p in parts)
            letter_needed = None
            f_key_needed = None
            for p in parts:
                p = p.strip().lower()
                if len(p) == 1 and p not in ['ctrl', 'shift', 'win', 'control', 'windows', 'meta']:
                    letter_needed = p.upper()
                elif p.startswith('f') and p[1:].isdigit():
                    f_key_needed = int(p[1:])

            # Перевірити умови
            if ctrl_needed and not self.ctrl_pressed:
                return
            if shift_needed and not self.shift_pressed:
                return
            if win_needed and not self.win_pressed:
                return

            # Перевірити букву або F-клавішу
            if letter_needed:
                if hasattr(key, 'char') and key.char and key.char.upper() == letter_needed:
                    print(f"[HotkeyHook] ✅ Hotkey спрацював: {self.hotkey}")
                    if self.callback:
                        threading.Thread(target=self.callback, daemon=True).start()
            elif f_key_needed:
                # Перевірити F-клавішу
                f_key_map = {
                    1: Key.f1, 2: Key.f2, 3: Key.f3, 4: Key.f4, 5: Key.f5,
                    6: Key.f6, 7: Key.f7, 8: Key.f8, 9: Key.f9, 10: Key.f10,
                    11: Key.f11, 12: Key.f12
                }
                if f_key_needed in f_key_map and key == f_key_map[f_key_needed]:
                    print(f"[HotkeyHook] ✅ Hotkey спрацював: {self.hotkey}")
                    if self.callback:
                        threading.Thread(target=self.callback, daemon=True).start()
        except Exception as e:
            pass  # Тихо ігноруємо помилки

    def _on_release(self, key):
        """Обробити відпускання клавіші."""
        try:
            from pynput.keyboard import Key

            if key == Key.ctrl_l or key == Key.ctrl_r:
                self.ctrl_pressed = False
            elif key == Key.shift_l or key == Key.shift_r:
                self.shift_pressed = False
            elif key == Key.cmd or key == Key.cmd_l or key == Key.cmd_r:
                self.win_pressed = False
        except Exception as e:
            pass

    def start(self) -> bool:
        """Запустити hotkey через pynput."""
        if not self.pynput_available:
            print("❌ pynput не доступний")
            return False

        try:
            self.listener = self.keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self.listener.start()
            print(f"✅ Hotkey запущено через pynput: {self.hotkey}")
            return True
        except Exception as e:
            print(f"❌ Помилка запуску hotkey: {e}")
            return False

    def stop(self):
        """Зупинити hotkey."""
        if self.listener:
            self.listener.stop()
            self.listener = None


class GlobalVoiceInput:
    """Глобальне голосове введення."""

    def __init__(
        self,
        hotkey: str = "ctrl+shift+g",
        callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Args:
            hotkey: Гаряча клавіша (наприклад "ctrl+shift+g")
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

        # Tray Icon
        self.tray_icon = get_voice_tray_icon()

        # Запам'ятовування активного вікна для повернення фокусу
        self._last_window_hwnd = None
        # Захист від подвійного спрацьовування (debounce)
        self._toggle_lock = threading.Lock()
        self._stop_requested = False

    def _update_status(self, status: str):
        """Оновити статус."""
        if self.status_callback:
            try:
                self.status_callback(status)
            except Exception:
                pass

    def _update_tray_status(self, voice_status: VoiceStatus, text: str = ""):
        """Оновити статус tray icon."""
        if self.tray_icon:
            try:
                self.tray_icon.set_status(voice_status, text)
            except Exception as e:
                print(f"[TrayIcon] Error: {e}")

    def _on_stt_status(self, status: str, data=None):
        """Статус STT."""
        if status == "listening":
            self.is_listening = True
            self._stop_requested = False
            self._update_status("[GVI] Slukhau...")
            self._update_tray_status(VoiceStatus.RECORDING, "Zapis...")
        elif status == "processing":
            self._update_status("[GVI] Raspiznavannie...")
            self._update_tray_status(VoiceStatus.PROCESSING, "Raspiznavannie...")
        elif status == "idle":
            self.is_listening = False
            self._update_status("[GVI] Gatavy")
            self._update_tray_status(VoiceStatus.IDLE, "Gatavy")
        elif status == "error":
            self.is_listening = False
            self._update_status("[GVI] Pamylka")
            self._update_tray_status(VoiceStatus.ERROR, "Pamylka")
        elif status == "no_microphone":
            self.is_listening = False
            self._update_status("[GVI] Nemaie dostupu do mikrofona")
            self._update_tray_status(VoiceStatus.NO_MIC, "Nemaie mikrofona")

    def _on_hotkey_pressed(self):
        """Обробити натискання hotkey — toggle запис."""
        print(f"[GVI] _on_hotkey_pressed викликано! is_listening={self.is_listening}")
        with self._toggle_lock:
            if self.is_listening:
                # Вже слухаємо — зупинити
                print("[GVI] Hotkey: зупинка запису...")
                self._stop_requested = True
                self.stt_listener.stop()
                self.is_listening = False
                self._update_tray_status(VoiceStatus.IDLE, "Зупинено")
                self._update_status("[GVI] Зупинено")
            else:
                # Почати запис
                print("[GVI] Hotkey: початок запису...")
                self._start_recording()

    def _start_recording(self):
        """Почати запис і розпізнавання."""
        try:
            # 1. Запам'ятати активне вікно
            self._last_window_hwnd = user32.GetForegroundWindow()
            print(f"[GVI] Zapamiatovane aktyvnae vakno: {self._last_window_hwnd}")

            # 2. Оновити статус
            self._update_tray_status(VoiceStatus.RECORDING, "Slukhau...")
            self._update_status("[GVI] Slukhau...")

            # 3. Прослухати і розпізнати (у фонавым патоку)
            self._stop_requested = False
            threading.Thread(target=self._record_and_recognize, daemon=True).start()
        except Exception as e:
            print(f"[GVI] Pamylka pachatku zapisu: {e}")
            import traceback
            traceback.print_exc()
            self._update_tray_status(VoiceStatus.ERROR, "Pamylka")

    def _record_and_recognize(self):
        """Запісаць і распазнаць у фонавым патоку."""
        try:
            self.is_listening = True
            # Выклікаем listen_once, які блакуецца пакуль не скончыць запіс
            text = self.stt_listener.listen_once(duration=LISTEN_DURATION, wait_for_speech=True)
            if text and not self._stop_requested:
                self._on_text_recognized(text)
            elif self._stop_requested:
                print("[GVI] Zapyniena karystalnikam")
                self.is_listening = False
                self._update_tray_status(VoiceStatus.IDLE, "Gatavy")
        except Exception as e:
            print(f"[GVI] Pamylka raspaznawania: {e}")
            import traceback
            traceback.print_exc()
            self.is_listening = False
            self._update_tray_status(VoiceStatus.ERROR, "Pamylka")

    def _on_text_recognized(self, text: str):
        """Апрацаваць распазнаны тэкст."""
        self.is_listening = False
        self._update_status(f"[GVI] Raspaznana: {text}")
        self._update_tray_status(VoiceStatus.PROCESSING, "Ustaŭka...")

        # 1. Аднавіць фокус у запамятаванае акно
        if self._last_window_hwnd:
            print(f"[GVI] Adnaŭlieńnie fokusu: {self._last_window_hwnd}")
            user32.SetForegroundWindow(self._last_window_hwnd)
            time.sleep(0.2)  # Час на аднаўленне фокусу

        # 2. Уставіць тэкст
        success = self._insert_text(text)
        if not success:
            print("[GVI] Nie atrymalasia ustaŭić tekst")

        # 3. Вярнуць статус IDLE
        self._update_tray_status(VoiceStatus.IDLE, "Gatavy")
        self._update_status("[GVI] Gatavy")

        # Callback
        if self.callback:
            self.callback(text)

    def _insert_text(self, text: str) -> bool:
        """Уставіць тэкст праз keyboard_type."""
        try:
            from functions.tools_mouse_keyboard import keyboard_type
            result = keyboard_type(text=text)
            if result and result.get('success'):
                print(f"[GVI] Текст вставлено через keyboard_type: {text[:50]}...")
                return True
            else:
                print(f"[GVI] keyboard_type не вдалося: {result}")
                return False
        except ImportError as e:
            print(f"[GVI] keyboard_type не доступний: {e}")
            return False
        except Exception as e:
            print(f"[GVI] Помилка вставки: {e}")
            import traceback
            traceback.print_exc()
            return False


    def start(self) -> bool:
        """Запустити глобальне голосове введення."""
        if self.is_running:
            print("⚠️ GlobalVoiceInput вже запущено")
            return False

        print("🎙️ GlobalVoiceInput: ініціалізація STT Listener...")
        if not self.stt_listener.initialize():
            print("❌ GlobalVoiceInput: STT Listener не ініціалізовано")
            return False
        print("✅ GlobalVoiceInput: STT Listener готовий")

        # Ініціалізувати tray icon
        print("🎙️ GlobalVoiceInput: ініціалізація tray icon...")
        if self.tray_icon:
            if not self.tray_icon.initialize():
                print("⚠️ Не вдалося ініціалізувати tray icon")
            else:
                self._update_tray_status(VoiceStatus.IDLE, "Готовий")
                print("✅ GlobalVoiceInput: tray icon готовий")
        else:
            print("⚠️ GlobalVoiceInput: tray icon недоступний")

        # Налаштувати hotkey callback
        print(f"🎙️ GlobalVoiceInput: налаштування hotkey {self.hotkey_hook.hotkey}...")
        self.hotkey_hook.set_callback(self._on_hotkey_pressed)

        # Запустити hook
        print("🎙️ GlobalVoiceInput: запуск hook...")
        if not self.hotkey_hook.start():
            print("❌ GlobalVoiceInput: hook не запустився")
            return False
        print("✅ GlobalVoiceInput: hook запущено")

        self.is_running = True
        self._update_status(f"✅ Готово (hotkey: {self.hotkey_hook.hotkey})")
        return True

    def stop(self):
        """Зупинити глобальне голосове введення."""
        self.hotkey_hook.stop()
        self.stt_listener.stop()
        self.is_running = False
        self._update_status("⏹️ Зупинено")

        # Очистити tray icon
        if self.tray_icon:
            self.tray_icon.cleanup()
