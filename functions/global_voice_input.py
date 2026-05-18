"""Global Voice Input — глобальне голосове введення в будь-яку програму.

⚠️ УВАГА: Логіка вставки тексту в методах _insert_segment та _send_input_unicode є критичною
і не повинна змінюватися без узгодження. Ці методи оптимізовані для Windows 10/11 з підтримкою
кирилиці та емодзі. Будь-які зміни можуть призвести до дублювання тексту, відсутності вставки
або спотворення символів.

"""
from __future__ import annotations

import ctypes
import threading
import time
from typing import Callable, Optional

import numpy as np
import pyperclip
import sounddevice as sd

from .core_stt_listener import STTListener
from .config import SAMPLE_RATE, LISTEN_DURATION, VOLUME_THRESHOLD, SILENCE_DURATION, MICROPHONE_DEVICE_ID
from .gui.voice_tray_icon import get_voice_tray_icon, VoiceStatus


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
WM_PASTE = 0x0302

# KBDLLHOOKSTRUCT для правильного читання vkCode
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_uint),
        ("scanCode", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("time", ctypes.c_uint),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("hwndActive", ctypes.c_void_p),
        ("hwndFocus", ctypes.c_void_p),
        ("hwndCapture", ctypes.c_void_p),
        ("hwndMenuOwner", ctypes.c_void_p),
        ("hwndMoveSize", ctypes.c_void_p),
        ("hwndCaret", ctypes.c_void_p),
        ("rcCaret_left", ctypes.c_long),
        ("rcCaret_top", ctypes.c_long),
        ("rcCaret_right", ctypes.c_long),
        ("rcCaret_bottom", ctypes.c_long),
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

        # Debounce: запобігає подвійному спрацьовуванню
        self._last_fire_time = 0.0
        self._debounce_sec = 0.8  # мінімальний інтервал між спрацьовуваннями

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

            # Відстежування модифікаторів
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
            now = time.time()
            if letter_needed:
                if hasattr(key, 'char') and key.char and key.char.upper() == letter_needed:
                    if now - self._last_fire_time >= self._debounce_sec:
                        self._last_fire_time = now
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
                    if now - self._last_fire_time >= self._debounce_sec:
                        self._last_fire_time = now
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
        self._last_window_title = None
        self._last_cursor_pos = None
        # Захист від подвійного спрацьовування (debounce)
        self._toggle_lock = threading.Lock()
        self._stop_requested = False
        self._last_hotkey_time = 0.0
        self._debounce_sec = 0.8

    def _debug_find_edit_control(self, parent_hwnd: int):
        """Знайти всі дочірні контроли в вікні."""
        import ctypes

        found = []

        def enum_callback(hwnd, lparam):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 255)
            class_name = buf.value

            buf2 = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf2, 511)
            title = buf2.value

            visible = ctypes.windll.user32.IsWindowVisible(hwnd)
            enabled = ctypes.windll.user32.IsWindowEnabled(hwnd)

            found.append({
                "hwnd": hwnd,
                "class": class_name,
                "title": title[:30],
                "visible": visible,
                "enabled": enabled,
            })
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        callback = WNDENUMPROC(enum_callback)
        ctypes.windll.user32.EnumChildWindows(parent_hwnd, callback, 0)

        print(f"[DEBUG] Дочірні контроли вікна {parent_hwnd}:")
        for item in found:
            print(f"  hwnd={item['hwnd']} class='{item['class']}' visible={item['visible']} enabled={item['enabled']} title='{item['title']}'")

        return found

    def _get_window_class_name(self, hwnd: int) -> str:
        """Отримати Win32 class name вікна/контрола."""
        try:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buf, 255)
            return buf.value or ""
        except Exception:
            return ""

    def _resolve_focus_target(self, hwnd: int) -> tuple[int, str]:
        """Знайти фокусований контрол усередині вікна."""
        try:
            thread_id = user32.GetWindowThreadProcessId(hwnd, None)
            target_hwnd = hwnd

            if thread_id:
                gui = GUITHREADINFO()
                gui.cbSize = ctypes.sizeof(GUITHREADINFO)
                if user32.GetGUIThreadInfo(thread_id, ctypes.byref(gui)):
                    if gui.hwndFocus:
                        target_hwnd = gui.hwndFocus

            # Спеціальна обробка для Chrome-based редакторів (Windsurf/VS Code)
            parent_class = self._get_window_class_name(hwnd).lower()
            if "chrome_widgetwin" in parent_class:
                # Знайти Chrome_RenderWidgetHostHWND - це поле вводу
                render_widget = self._find_chrome_render_widget(hwnd)
                if render_widget:
                    target_hwnd = render_widget
            # Спеціальна обробка для PyQt6
            elif "qt" in parent_class and "qwindowicon" in parent_class:
                # Знайти QTextEdit або інший контрол вводу в PyQt6
                qt_edit = self._find_qt_edit_control(hwnd)
                if qt_edit:
                    target_hwnd = qt_edit

            class_name = self._get_window_class_name(target_hwnd)
            return int(target_hwnd or 0), class_name
        except Exception:
            return int(hwnd or 0), self._get_window_class_name(hwnd)

    def _find_chrome_render_widget(self, parent_hwnd: int) -> Optional[int]:
        """Знайти Chrome_RenderWidgetHostHWND в Chrome-based вікні."""
        import ctypes
        
        found = []
        
        def enum_callback(hwnd, lparam):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 255)
            class_name = buf.value
            
            if "Chrome_RenderWidgetHostHWND" in class_name:
                visible = ctypes.windll.user32.IsWindowVisible(hwnd)
                enabled = ctypes.windll.user32.IsWindowEnabled(hwnd)
                if visible and enabled:
                    found.append(hwnd)
                    return False  # зупинити пошук після першого знаходження
            return True
        
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        callback = WNDENUMPROC(enum_callback)
        ctypes.windll.user32.EnumChildWindows(parent_hwnd, callback, 0)
        
        return found[0] if found else None

    def _find_qt_edit_control(self, parent_hwnd: int) -> Optional[int]:
        """Знайти QTextEdit або інший контрол вводу в PyQt6 вікні."""
        import ctypes
        
        found = []
        
        def enum_callback(hwnd, lparam):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 255)
            class_name = buf.value
            
            # Шукаємо Qt контроли які можуть приймати текст
            qt_edit_classes = [
                "QTextEdit",
                "QLineEdit", 
                "QPlainTextEdit",
                "QComboBox",
                "QSpinBox",
                "QDoubleSpinBox"
            ]
            
            if any(qt_class in class_name for qt_class in qt_edit_classes):
                visible = ctypes.windll.user32.IsWindowVisible(hwnd)
                enabled = ctypes.windll.user32.IsWindowEnabled(hwnd)
                if visible and enabled:
                    found.append(hwnd)
                    return False  # зупинити пошук після першого знаходження
            return True
        
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        callback = WNDENUMPROC(enum_callback)
        ctypes.windll.user32.EnumChildWindows(parent_hwnd, callback, 0)
        
        return found[0] if found else None

    def _get_insert_strategy(self, class_name: str, title: str) -> str:
        """Обрати стратегію вставки залежно від типу вікна/контрола.

        Повертає:
        - `win32_paste` для класичних edit-контролів;
        - `ctrl_v` для браузерних/чатових поверхонь;
        - `ctrl_v` як універсальний fallback.
        """
        class_name = (class_name or "").lower()
        title = (title or "").lower()

        safe_classes = {
            "edit",
            "richeditd2dpt",
            "richedit20w",
            "richedit50w",
            "akeleditw",
            "scintilla",
        }
        browserish_classes = {
            "chrome_widgetwin_1",
            "chrome_renderwidgethosthwnd",
            "mozillawindowclass",
        }

        if class_name in browserish_classes:
            return "ctrl_v"
        if "gemini" in title or "chatgpt" in title or "windsurf" in title:
            return "ctrl_v"
        if class_name in safe_classes:
            return "win32_paste"
        return "ctrl_v"

    def _set_clipboard_text_verified(self, text: str, retries: int = 10, delay: float = 0.05) -> bool:
        """Покласти текст у clipboard і переконатися, що саме він там лежить."""
        try:
            pyperclip.copy(text)
            for _ in range(retries):
                time.sleep(delay)
                try:
                    if pyperclip.paste() == text:
                        return True
                except Exception:
                    pass
            return False
        except Exception as e:
            print(f"[GVI] Pamylka set clipboard: {e}")
            return False

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
        now = time.time()
        if now - self._last_hotkey_time < self._debounce_sec:
            print(f"[GVI] Debounce: ігнорую (прошло {now - self._last_hotkey_time:.2f}s < {self._debounce_sec}s)")
            return
        self._last_hotkey_time = now
        print(f"[GVI] _on_hotkey_pressed викликано! is_listening={self.is_listening}")

        # 🔥 ПЕРШО відпустити модифікатори щоб уникнути випадкового Ctrl+V
        try:
            import pyautogui
            pyautogui.keyUp("ctrl")
            pyautogui.keyUp("shift")
            pyautogui.keyUp("alt")
            pyautogui.keyUp("win")
            time.sleep(0.05)  # Чекаємо щоб модифікатори точно відпустилися
        except Exception as e:
            print(f"[GVI] Помилка відпускання модифікаторів: {e}")
        
        # Debug-Loop: Логування буфера при натисканні Ctrl+F9 (ПІСЛЯ відпускання модифікаторів)
        try:
            import pyperclip
            clipboard_on_hotkey = pyperclip.paste() if pyperclip.paste() else ""
            print(f"[DEBUG-GVI] _on_hotkey_pressed: буфер ПРИ натисканні Ctrl+F9 (після відпускання модифікаторів): '{clipboard_on_hotkey[:50] if clipboard_on_hotkey else ''}...' (len={len(clipboard_on_hotkey)})")
        except Exception as e:
            print(f"[DEBUG-GVI] Помилка читання буфера: {e}")

        with self._toggle_lock:
            if self.is_listening:
                # Вже слухаємо — зупинити
                print("[GVI] Hotkey: зупинка запису...")
                self._stop_requested = True
                print(f"[DEBUG-GVI] _stop_requested встановлено в True")
                if hasattr(self, '_stop_event') and self._stop_event:
                    self._stop_event.set()
                    print(f"[DEBUG-GVI] _stop_event встановлено")
                else:
                    print(f"[DEBUG-GVI] _stop_event не існує або None")
                self.stt_listener.stop()
                print(f"[DEBUG-GVI] stt_listener.stop() викликано")
                self.is_listening = False
                print(f"[DEBUG-GVI] is_listening встановлено в False")
                self._update_tray_status(VoiceStatus.IDLE, "Зупинено")
                self._update_status("[GVI] Зупинено")
            else:
                # Почати запис
                print("[GVI] Hotkey: початок запису...")
                self._start_recording()

    def _start_recording(self):
        """Почати запис і розпізнавання."""
        try:
            # 0. 🔥 Очистити буфер обміну перед записом (більш надійний метод)
            try:
                import pyperclip
                # Debug-Loop: Логування стану буфера перед очищенням
                old_clipboard = pyperclip.paste() if pyperclip.paste() else ""
                print(f"[DEBUG-GVI] Буфер обміну ПЕРЕД очищенням: '{old_clipboard[:100] if old_clipboard else ''}...' (len={len(old_clipboard)})")
                
                # Спроба 1: очистити через порожній рядок
                for i in range(3):
                    pyperclip.copy("")
                    time.sleep(0.05)
                    current = pyperclip.paste()
                    print(f"[DEBUG-GVI] Спроба {i+1} очищення: '{current}' (len={len(current)})")
                    if not current:
                        break
                
                final_clipboard = pyperclip.paste()
                print(f"[GVI] Буфер обміну очищено перед записом (перевірка: '{final_clipboard}', len={len(final_clipboard)})")
            except Exception as e:
                print(f"[GVI] Помилка очищення буфера: {e}")
                import traceback
                traceback.print_exc()
            
            # 1. Запам'ятати активне вікно (заголовок) та позицію курсора
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            self._last_window_title = buffer.value
            self._last_window_hwnd = hwnd
            
            # Запам'ятати позицію курсора
            import pyautogui
            self._last_cursor_pos = pyautogui.position()
            print(f"[GVI] Zapamiatovane aktyvnae vakno: hwnd={hwnd}, title='{self._last_window_title}', cursor={self._last_cursor_pos}")

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
        """Запісаць і распазнаць у фонавым патоку (псевдопотокове розпізнавання)."""
        try:
            self.is_listening = True
            self._stop_event = threading.Event()

            # Callback для вставки кожного сегменту
            def segment_callback(segment_text: str):
                """Вставити розпізнаний сегмент тексту."""
                print(f"[GVI] Вставка сегменту: '{segment_text}'")
                self._insert_segment(segment_text)

            # Використовуємо псевдопотокове розпізнавання з callback
            text = self.stt_listener.listen_streaming(stop_event=self._stop_event, segment_callback=segment_callback)

            # Якщо є текст який не був вставлений через callback (наприклад, фінальний сегмент)
            if text and text.strip():
                print(f"[GVI] Розпізнано текст: '{text}'")
                # Текст вже вставлений чанками через callback, тому тут тільки лог
                # Не вставляємо фінальний текст повторно, щоб уникнути дублювання
            elif self._stop_requested:
                print("[GVI] Zapyniena karystalnikam (без тексту)")
                self.is_listening = False
                self._update_tray_status(VoiceStatus.IDLE, "Gatavy")
            else:
                print("[GVI] Не розпізнано текст")
                self.is_listening = False
                self._update_tray_status(VoiceStatus.IDLE, "Gatavy")
        except Exception as e:
            print(f"[GVI] Pamylka raspaznawania: {e}")
            import traceback
            traceback.print_exc()
            self.is_listening = False
            self._update_tray_status(VoiceStatus.ERROR, "Pamylka")

    def _on_text_recognized(self, text: str):
        """Апрацаваць распазнаны тэкст (текст вже вставлений чанками через callback)."""
        self.is_listening = False
        self._update_status(f"[GVI] Raspaznana: {text}")
        self._update_tray_status(VoiceStatus.IDLE, "Gatavy")
        self._update_status("[GVI] Gatavy")

        if self.callback:
            try:
                self.callback(text)
            except Exception as e:
                print(f"[GVI] Pamylka callback: {e}")

    def _paste_into_window(self, hwnd: int) -> bool:
        """Вставити clipboard у фокусований контрол конкретного вікна через Win32."""
        try:
            # Debug-Loop: Логування перед вставкою
            import pyperclip
            clipboard_before = pyperclip.paste() if pyperclip.paste() else ""
            print(f"[DEBUG-GVI] _paste_into_window: буфер ПЕРЕД вставкою: '{clipboard_before[:50] if clipboard_before else ''}...' (len={len(clipboard_before)})")
            
            target_hwnd, _class_name = self._resolve_focus_target(hwnd)
            if not target_hwnd:
                print(f"[DEBUG-GVI] _paste_into_window: не вдалося знайти target_hwnd")
                return False

            print(f"[DEBUG-GVI] _paste_into_window: target_hwnd={target_hwnd}, class={_class_name}")
            user32.SendMessageW(target_hwnd, WM_PASTE, 0, 0)
            
            # Debug-Loop: Логування після вставки
            time.sleep(0.1)
            clipboard_after = pyperclip.paste() if pyperclip.paste() else ""
            print(f"[DEBUG-GVI] _paste_into_window: буфер ПІСЛЯ вставки: '{clipboard_after[:50] if clipboard_after else ''}...' (len={len(clipboard_after)})")
            
            return True
        except Exception as e:
            print(f"[GVI] Pamylka Win32 paste: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _insert_segment(self, segment_text: str) -> bool:
        """
        Вставити один сегмент тексту без зовнішнього макросу.
        
        ⚠️ КРИТИЧНИЙ МЕТОД - НЕ ЗМІНЮВАТИ БЕЗ УЗГОДЖЕННЯ
        Логіка оптимізована для Windows 10/11 з підтримкою кирилиці та емодзі.
        """
        import ctypes
        import pyperclip
        import time

        user32 = ctypes.windll.user32
        WM_PASTE = 0x0302

        print(f"[GVI] _insert_segment: '{segment_text[:50]}' (len={len(segment_text)})")

        # Відновити фокус
        hwnd = self._last_window_hwnd
        if hwnd:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.2)

        # Відпустити модифікатори
        try:
            import pyautogui
            for key in ("ctrl", "shift", "alt", "win"):
                pyautogui.keyUp(key)
            time.sleep(0.05)
        except Exception:
            pass

        # Визначити клас контрола
        target_hwnd, class_name = self._resolve_focus_target(hwnd) if hwnd else (0, "")
        
        # Переводимо в нижній регістр для зручного пошуку
        class_name_lower = class_name.lower()
        is_chrome = "chrome" in class_name_lower or "mozilla" in class_name_lower
        is_qt = "qt" in class_name_lower
        is_notepad = "notepad" in class_name_lower # Додаємо новий Блокнот (Win11)

        print(f"[GVI] target_hwnd={target_hwnd}, class='{class_name}', chrome={is_chrome}, qt={is_qt}, notepad={is_notepad}")

        ok = False

        # 1. Chrome, PyQt6, новий Notepad: SendInput Unicode (найкраще для сучасних UI)
        if is_chrome or is_qt or is_notepad:
            print(f"[GVI] Modern UI Detected -> SendInput Unicode")
            time.sleep(0.1)
            ok = self._send_input_unicode(segment_text)
            
            # Fallback на Ctrl+V ТІЛЬКИ якщо SendInput НЕ спрацював
            if not ok and is_qt:
                print("[GVI] SendInput failed for PyQt6 -> Ctrl+V fallback")
                pyperclip.copy(segment_text)
                time.sleep(0.15)
                try:
                    VK_CONTROL, VK_V = 0x11, 0x56
                    KEYEVENTF_KEYDOWN, KEYEVENTF_KEYUP = 0x0000, 0x0002
                    
                    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYDOWN, 0)
                    time.sleep(0.05)
                    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYDOWN, 0)
                    time.sleep(0.05)
                    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
                    time.sleep(0.05)
                    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
                    time.sleep(0.1)
                    ok = True
                except Exception as e:
                    print(f"[GVI] Win32 Ctrl+V failed: {e}")

        # 2. Старий Win32 (AkelPad, класичний Edit): WM_PASTE
        elif target_hwnd and not is_qt:
            try:
                # ВАЖЛИВО: Спочатку кладемо текст у буфер!
                pyperclip.copy(segment_text)
                time.sleep(0.05) # Даємо ОС час оновити буфер
                
                user32.SendMessageW(target_hwnd, WM_PASTE, 0, 0)
                time.sleep(0.1)
                ok = True
                print("[GVI] WM_PASTE: ok")
            except Exception as e:
                print(f"[GVI] WM_PASTE failed: {e}")

        # 3. Fallback: SendInput Unicode
        if not ok:
            print("[GVI] Fallback → SendInput Unicode")
            ok = self._send_input_unicode(segment_text)

        # 4. Останній fallback: Ctrl+V через pyautogui
        if not ok:
            print("[GVI] Fallback → Ctrl+V")
            pyperclip.copy(segment_text)
            time.sleep(0.05)
            try:
                pyautogui.hotkey("ctrl", "v")
                ok = True
            except Exception as e:
                print(f"[GVI] Ctrl+V failed: {e}")

        return ok

    def _send_input_unicode(self, text: str) -> bool:
        """
        Вставити текст через SendInput з KEYEVENTF_UNICODE.
        
        ⚠️ КРИТИЧНИЙ МЕТОД - НЕ ЗМІНЮВАТИ БЕЗ УЗГОДЖЕННЯ
        Логіка оптимізована для Windows 10/11 з підтримкою кирилиці та емодзі.
        """
        import ctypes
        import ctypes.wintypes as wt

        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP   = 0x0002
        INPUT_KEYBOARD    = 1

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk",         wt.WORD),
                ("wScan",       wt.WORD),
                ("dwFlags",     wt.DWORD),
                ("time",        wt.DWORD),
                ("dwExtraInfo", ctypes.c_ulonglong),
            ]

        class _INPUTunion(ctypes.Union):
            _fields_ = [
                ("ki",   KEYBDINPUT),
                ("_pad", ctypes.c_byte * 28),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wt.DWORD),
                ("_u",   _INPUTunion),
            ]

        cb = ctypes.sizeof(INPUT)
        print(f"[GVI] sizeof(INPUT)={cb}")  # має бути 40

        user32 = ctypes.windll.user32
        inputs = []

        for char in text:
            code = ord(char)

            inp_down = INPUT(INPUT_KEYBOARD)
            inp_down._u.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0)
            inputs.append(inp_down)

            inp_up = INPUT(INPUT_KEYBOARD)
            inp_up._u.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
            inputs.append(inp_up)

        n = len(inputs)
        arr = (INPUT * n)(*inputs)
        sent = user32.SendInput(n, arr, cb)

        if sent != n:
            err = ctypes.GetLastError()
            print(f"[GVI] SendInput failed: sent={sent}/{n}, error={err}")
            return False

        print(f"[GVI] SendInput Unicode: ok, sent={sent}/{n}")
        return True

    def _insert_text_with_script(self, text: str) -> bool:
        """Універсальна вставка: копіювати в буфер, натиснути Shift+F10, чекати 2 сек, очистити буфер."""
        try:
            # 1. Копіювати текст в буфер обміну
            from functions.tools.tools_mouse_keyboard import clipboard_copy_text
            copy_result = clipboard_copy_text(text)
            print(f"[GVI] Текст скопійовано в буфер: {copy_result}")
            
            if not copy_result or not copy_result.get("success"):
                return False
            
            time.sleep(0.1)
            
            # 2. Натиснути Shift+F10 для запуску скрипта користувача
            try:
                import pyautogui
                pyautogui.hotkey('shift', 'f10')
                print(f"[GVI] Натиснуто Shift+F10")
            except Exception as e:
                print(f"[GVI] Помилка натискання Shift+F10: {e}")
                return False
            
            # 3. Чекати 2 секунди щоб скрипт вставив текст
            time.sleep(2.0)
            print(f"[GVI] Чекання завершено")
            
            # 4. Очистити буфер обміну
            try:
                import pyperclip
                pyperclip.copy("")
                print(f"[GVI] Буфер обміну очищено")
            except Exception as e:
                print(f"[GVI] Помилка очищення буфера: {e}")
            
            print(f"[GVI] Текст вставлено через скрипт: {text[:50]}...")
            return True
        except Exception as e:
            print(f"[GVI] Помилка _insert_text_with_script: {e}")
            return False

    def _insert_text(self, text: str) -> bool:
        """Уставіць тэкст у мэтавае вакно праз clipboard + Ctrl+V.

        Для глобального hotkey це надійніше за посимвольний `typewrite()`:
        модифікатори гарячої клавіші можуть ще бути затиснуті ОС, а поточна
        розкладка може спотворити символи. Clipboard paste обходить обидві
        проблеми і стабільно вставляє український текст.
        """
        try:
            # Debug-Loop: Логування вхідних даних
            print(f"[DEBUG-GVI] _insert_text викликано: text='{text[:50]}...' (len={len(text)})")
            
            if not self._last_window_title:
                print("[GVI] Няма запамятаванага загалоўка вакна")
                return False

            title = self._last_window_title
            print(f"[GVI] Устаўка тэксту ў вакно '{title}'")

            # 1. Для Chrome не використовуємо activate_window_by_title —
            # він не може знайти вікно через кракозябри в заголовку і скидає фокус.
            # Фокус вже відновлено через SetForegroundWindow + клік в _on_text_recognized.
            if "chrome" not in title.lower():
                from functions.aaa_voice_input import activate_window_by_title
                result = activate_window_by_title(title)
                print(f"[GVI] Актывацыя вакна: {result}")
                time.sleep(0.25)
            else:
                print(f"[GVI] Chrome: пропускаємо activate_window_by_title, фокус вже є")
                time.sleep(0.1)

            # 2. keyboard_type через pyautogui не підтримує кирилицю —
            # вставляє сміття ("_.", "  !"). Для всіх вікон, включно з Chrome,
            # використовуємо clipboard + Ctrl+V (кроки 4-6 нижче).

            # 3. Дати Windows дорозпустити модифікатори глобального hotkey
            try:
                import pyautogui
                pyautogui.keyUp("ctrl")
                pyautogui.keyUp("shift")
                pyautogui.keyUp("alt")
                pyautogui.keyUp("win")
            except Exception as e:
                print(f"[GVI] Памылка пры адпусканні мадыфікатараў: {e}")
            time.sleep(0.1)

            # 4. Debug-Loop: Логування буфера перед вставкою
            old_clipboard = None
            try:
                old_clipboard = pyperclip.paste()
                print(f"[DEBUG-GVI] Буфер ПЕРЕД вставкою: '{old_clipboard[:50] if old_clipboard else ''}...' (len={len(old_clipboard) if old_clipboard else 0})")
            except Exception as e:
                print(f"[GVI] Nie atrymалася прачытаць clipboard: {e}")

            from functions.tools.tools_mouse_keyboard import clipboard_copy_text, keyboard_hotkey

            copy_result = clipboard_copy_text(text)
            print(f"[GVI] clipboard_copy_text result: {copy_result}")
            if not copy_result or not copy_result.get("success"):
                return False

            time.sleep(0.1)
            paste_ok = False
            used_ctrl_v_fallback = False
            
            # 5. Спробувати Win32 paste для деяких класів вікон
            if self._last_window_hwnd:
                target_hwnd, target_class = self._resolve_focus_target(self._last_window_hwnd)
                insert_strategy = self._get_insert_strategy(target_class, title)
                print(f"[GVI] Focus target: hwnd={target_hwnd}, class='{target_class}', strategy='{insert_strategy}'")
                if insert_strategy == "win32_paste":
                    paste_ok = self._paste_into_window(self._last_window_hwnd)
                    print(f"[GVI] Win32 paste result: {paste_ok}")
                else:
                    print(f"[GVI] Win32 paste skipped for class='{target_class}' title='{title}'")

            # 6. Fallback на Ctrl+V
            if not paste_ok:
                used_ctrl_v_fallback = True
                paste_result = keyboard_hotkey("ctrl", "v")
                print(f"[GVI] keyboard_hotkey(ctrl+v) result: {paste_result}")
                paste_ok = bool(paste_result and paste_result.get("success"))

            # 7. Fallback на keyboard_type
            if not paste_ok:
                from functions.tools.tools_mouse_keyboard import keyboard_type
                type_result = keyboard_type(text=text)
                print(f"[GVI] keyboard_type fallback result: {type_result}")
                paste_ok = bool(type_result and type_result.get("success"))

            # 8. Fallback на PowerShell SendKeys (для Chrome)
            if not paste_ok:
                try:
                    import subprocess
                    # Escape text for PowerShell
                    escaped_text = text.replace('"', '`"').replace('$', '`$').replace('`', '``')
                    ps_script = f'[System.Windows.Forms.SendKeys]::SendWait("{escaped_text}")'
                    result = subprocess.run(
                        ['powershell', '-Command', f'Add-Type -AssemblyName System.Windows.Forms; {ps_script}'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    paste_ok = result.returncode == 0
                    print(f"[GVI] PowerShell SendKeys result: {paste_ok}")
                except Exception as e:
                    print(f"[GVI] PowerShell SendKeys error: {e}")

            # 9. Fallback на AutoHotkey скрипт (найнадійніший для Chrome)
            if not paste_ok:
                try:
                    import subprocess
                    import os
                    ahk_script = os.path.join(os.path.dirname(__file__), '..', 'paste_text.ahk')
                    if os.path.exists(ahk_script):
                        result = subprocess.run(
                            [ahk_script, text],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        paste_ok = result.returncode == 0
                        print(f"[GVI] AutoHotkey result: {paste_ok}")
                    else:
                        print(f"[GVI] AutoHotkey скрипт не знайдено: {ahk_script}")
                except Exception as e:
                    print(f"[GVI] AutoHotkey error: {e}")

            # 10. Fallback на UIA для Chrome (пряма вставка в елемент)
            if not paste_ok:
                try:
                    from .tools_ui_accessibility import UIAWrapper, uia_get_focused_element
                    uia = UIAWrapper()
                    if uia.is_available():
                        # Отримати сфокусований елемент
                        focused = uia_get_focused_element({})
                        if focused.get("ok"):
                            # Спробувати вставити через ValuePattern
                            try:
                                element = focused.get("element")
                                if element and hasattr(element, 'GetPattern'):
                                    from uiautomation import ValuePattern
                                    value_pattern = element.GetPattern(ValuePattern)
                                    if value_pattern:
                                        current_value = value_pattern.CurrentValue or ""
                                        value_pattern.SetValue(current_value + text)
                                        paste_ok = True
                                        print(f"[GVI] UIA ValuePattern вставка успішна")
                            except Exception as e:
                                print(f"[GVI] UIA ValuePattern error: {e}")
                except Exception as e:
                    print(f"[GVI] UIA fallback error: {e}")

            # 11. Fallback на SendInput з Unicode (для Chrome)
            if not paste_ok:
                try:
                    import ctypes
                    from ctypes import wintypes
                    
                    # SendInput структури
                    class KEYBDINPUT(ctypes.Structure):
                        _fields_ = [
                            ("wVk", wintypes.WORD),
                            ("wScan", wintypes.WORD),
                            ("dwFlags", wintypes.DWORD),
                            ("time", wintypes.DWORD),
                            ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
                        ]
                    
                    class INPUT(ctypes.Structure):
                        class _INPUT(ctypes.Union):
                            _fields_ = [("ki", KEYBDINPUT)]
                        _anonymous_ = ("_input",)
                        _fields_ = [
                            ("type", wintypes.DWORD),
                            ("_input", _INPUT),
                        ]
                    
                    KEYEVENTF_UNICODE = 0x0004
                    KEYEVENTF_KEYUP = 0x0002
                    
                    inputs = []
                    for char in text:
                        # Key down
                        ki = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE, 0, None)
                        inp = INPUT(1, ki)
                        inputs.append(inp)
                        # Key up
                        ki = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)
                        inp = INPUT(1, ki)
                        inputs.append(inp)
                    
                    n_inputs = len(inputs)
                    input_array = (INPUT * n_inputs)(*inputs)
                    sent = user32.SendInput(n_inputs, ctypes.byref(input_array), ctypes.sizeof(INPUT))
                    paste_ok = sent == n_inputs
                    print(f"[GVI] SendInput Unicode result: {paste_ok}, sent={sent}/{n_inputs}")
                except Exception as e:
                    print(f"[GVI] SendInput Unicode error: {e}")

            if paste_ok:
                print(f"[GVI] Текст устаўлены: {text[:50]}...")
                if old_clipboard is not None:
                    try:
                        restore_delay = 1.0 if used_ctrl_v_fallback else 0.05
                        time.sleep(restore_delay)
                        pyperclip.copy(old_clipboard)
                    except Exception as e:
                        print(f"[GVI] Nie atrymалася аднавіць clipboard: {e}")
                return True

            # Якщо всі методи не спрацювали - повідомити користувача
            print(f"[GVI] ⚠️ Автоматична вставка не вдалася. Текст скопійовано в буфер обміну. Натисніть Ctrl+V для вставки.")
            # Текст вже в буфері, не відновлюємо old_clipboard
            return True  # Повертаємо True бо текст в буфері

        except Exception as e:
            print(f"[GVI] Памылка ўстаўкі: {e}")
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
