"""
Керування мишею та клавіатурою через pyautogui.

Модуль для GUI Automation Phase 1.
Забезпечує керування мишою, клавіатурою та буфером обміну.

⚠️ УВАГА: Логіка вставки тексту в методах send_input_unicode та insert_text_smart є критичною
і не повинна змінюватися без узгодження. Ці методи оптимізовані для Windows 10/11 з підтримкою
кирилиці та емодзі. Будь-які зміни можуть призвести до дублювання тексту, відсутності вставки
або спотворення символів.
"""

import ctypes
import os
import sys
import time
from io import BytesIO
from typing import Dict, Any, Optional, Tuple

import pyautogui
import pyperclip
from PIL import Image

# Win32 constants
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002

def _get_dpi_scaling_cached() -> float:
    """Отримати DPI scaling з кешуванням.
    
    Використовує utils.screen_helper для отримання масштабу.
    
    Returns:
        DPI scaling factor (наприклад, 1.0 для 100% DPI, 1.5 для 150%)
    """
    from functions.tools.screen_helper import get_windows_scale_factor
    return get_windows_scale_factor()


def _apply_dpi_correction(x: int, y: int) -> Tuple[int, int]:
    """Застосувати DPI correction до координат з кешуванням.
    
    Args:
        x: X координата
        y: Y координата
        
    Returns:
        Кореговані координати (x, y) з урахуванням DPI
    """
    try:
        scaling = _get_dpi_scaling_cached()
        # Якщо DPI > 100%, треба поділити координати на scaling
        if scaling != 1.0:
            x = int(x / scaling)
            y = int(y / scaling)
        return x, y
    except Exception:
        return x, y


# Налаштування pyautogui для безпеки
pyautogui.FAILSAFE = True  # Рух мишою в кут екрану = аварійна зупинка
pyautogui.PAUSE = 0.1  # Пауза між діями


class MouseKeyboardController:
    """Контролер для керування мишею та клавіатурою."""

    # Спеціальні ключі для keyboard_send_special
    SPECIAL_KEYS = {
        'printscreen': 'printscreen',
        'printscrn': 'printscreen',
        'prtsc': 'printscreen',
        'numlock': 'numlock',
        'scrolllock': 'scrolllock',
        'capslock': 'capslock',
        'pause': 'pause',
        'break': 'pause',
        'insert': 'insert',
        'ins': 'insert',
        'home': 'home',
        'end': 'end',
        'pageup': 'pageup',
        'pagedown': 'pagedown'
    }

    def __init__(self):
        if sys.platform != 'win32':
            raise NotImplementedError(
                "MouseKeyboardController працює лише на Windows "
                "(ctypes.windll.user32 недоступний)"
            )
        self.last_position = None
        self._user32 = ctypes.windll.user32
        # Ініціалізуємо DPI кеш при створенні
        _get_dpi_scaling_cached()

    # ==================== МИША ====================

    def mouse_click(self, x: int, y: int, button: str = 'left',
                    clicks: int = 1, interval: float = 0.1) -> Dict[str, Any]:
        """Клік мишою."""
        try:
            # Застосувати DPI correction
            x, y = _apply_dpi_correction(x, y)
            pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
            return {
                "success": True,
                "position": {"x": x, "y": y},
                "button": button,
                "clicks": clicks
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_move(self, x: int, y: int, duration: float = 0.5) -> Dict[str, Any]:
        """
        Плавне переміщення курсора в координати (x, y).

        Args:
            x: Координата X
            y: Координата Y
            duration: Час переміщення в секундах

        Returns:
            {"success": True, "from": {"x": x0, "y": y0}, "to": {"x": x, "y": y}}
        """
        try:
            # Застосувати DPI correction
            x, y = _apply_dpi_correction(x, y)
            current = pyautogui.position()
            pyautogui.moveTo(x, y, duration=duration)
            return {
                "success": True,
                "from": {"x": current.x, "y": current.y},
                "to": {"x": x, "y": y},
                "duration": duration
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_scroll(self, amount: int, direction: str = 'vertical',
                     x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """
        Прокрутка мишою.

        Args:
            amount: Кількість "кліків" прокрутки (позитивне = вниз/вправо, негативне = вгору/вліво)
            direction: 'vertical' або 'horizontal'
            x, y: Координати для позиціонування перед скролом (опціонально)

        Returns:
            {"success": True, "amount": amount, "direction": direction}
        """
        try:
            if x is not None and y is not None:
                # Застосувати DPI correction
                x, y = _apply_dpi_correction(x, y)
                pyautogui.moveTo(x, y)

            if direction == 'horizontal':
                pyautogui.hscroll(amount)
            else:
                pyautogui.scroll(amount)

            return {
                "success": True,
                "amount": amount,
                "direction": direction,
                "position": {"x": x, "y": y} if x and y else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int,
                   duration: float = 0.5, button: str = 'left') -> Dict[str, Any]:
        """
        Перетягування (drag & drop) з (start_x, start_y) в (end_x, end_y).

        Args:
            start_x, start_y: Початкові координати
            end_x, end_y: Кінцеві координати
            duration: Час перетягування
            button: 'left' або 'right'

        Returns:
            {"success": True, "start": {...}, "end": {...}}
        """
        try:
            # Застосувати DPI correction
            start_x, start_y = _apply_dpi_correction(start_x, start_y)
            end_x, end_y = _apply_dpi_correction(end_x, end_y)
            pyautogui.moveTo(start_x, start_y)
            pyautogui.dragTo(end_x, end_y, duration=duration, button=button)
            return {
                "success": True,
                "start": {"x": start_x, "y": start_y},
                "end": {"x": end_x, "y": end_y},
                "duration": duration,
                "button": button
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_mouse_position(self) -> Dict[str, Any]:
        """
        Отримати поточні координати курсора миші.

        Returns:
            {"x": int, "y": int}
        """
        try:
            pos = pyautogui.position()
            return {"x": pos.x, "y": pos.y}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_click_image(self, image_path: str, confidence: float = 0.8) -> Dict[str, Any]:
        """
        Знайти зображення на екрані та клікнути по ньому (template matching).

        Args:
            image_path: Шлях до зображення для пошуку
            confidence: Поріг впевненості (0.0 - 1.0)

        Returns:
            {"success": True, "position": {"x": x, "y": y}, "confidence": confidence}
        """
        try:
            if not os.path.exists(image_path):
                return {"success": False, "error": f"Image not found: {image_path}"}

            location = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)
            if location is None:
                return {
                    "success": False,
                    "error": f"Image not found on screen: {image_path}",
                    "confidence": confidence
                }

            x, y = location
            # Застосувати DPI correction
            x, y = _apply_dpi_correction(x, y)
            pyautogui.click(x, y)

            return {
                "success": True,
                "position": {"x": x, "y": y},
                "confidence": confidence,
                "image": image_path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== КЛАВІАТУРА ====================

    def keyboard_press(self, key: str) -> Dict[str, Any]:
        """
        Натиснути клавішу.

        Args:
            key: Назва клавіші ('enter', 'esc', 'tab', 'f5', 'delete', 'space', ...)

        Returns:
            {"success": True, "key": key}
        """
        try:
            pyautogui.press(key)
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_foreground_window_title(self) -> str:
        """Отримати заголовок активного вікна."""
        try:
            hwnd = self._user32.GetForegroundWindow()
            length = self._user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception:
            return "?"

    def _paste_via_win32(self) -> bool:
        """Вставити текст через Win32 keybd_event (Ctrl+V). Повертає True якщо успішно."""
        try:
            self._user32.keybd_event(VK_CONTROL, 0, 0, 0)
            time.sleep(0.03)
            self._user32.keybd_event(VK_V, 0, 0, 0)
            time.sleep(0.03)
            self._user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.03)
            self._user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception as e:
            print(f"[DEBUG] keybd_event failed ({e}), fallback to pyautogui")
            return False

    def keyboard_type(self, text: str, interval: float = 0.02) -> Dict[str, Any]:
        """
        Ввести текст у активне вікно через pyautogui.typewrite (Unicode-ready).
        """
        try:
            fg_title = self._get_foreground_window_title()
            print(f"[DEBUG] keyboard_type: foreground='{fg_title}', text='{text[:50]}', len={len(text)}")

            pyautogui.typewrite(text, interval=interval)

            return {
                "success": True,
                "text": text,
                "length": len(text),
                "interval": interval,
                "foreground_window": fg_title,
            }
        except Exception as e:
            print(f"[DEBUG] keyboard_type: error: {e}")
            return {"success": False, "error": str(e)}

    def keyboard_hotkey(self, *keys: str) -> Dict[str, Any]:
        """
        Натиснути комбінацію клавіш.

        Args:
            *keys: Клавіші комбінації ('ctrl', 'c', 'alt', 'f4', 'win', 'd')

        Returns:
            {"success": True, "hotkey": [...]}
        """
        try:
            pyautogui.hotkey(*keys)
            return {"success": True, "hotkey": list(keys)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_hold(self, key: str, duration: float = 1.0) -> Dict[str, Any]:
        """
        Утримувати клавішу протягом часу.

        Args:
            key: Клавіша для утримання
            duration: Час утримання в секундах

        Returns:
            {"success": True, "key": key, "duration": duration}
        """
        try:
            pyautogui.keyDown(key)
            time.sleep(duration)
            pyautogui.keyUp(key)
            return {"success": True, "key": key, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_send_special(self, key_name: str) -> Dict[str, Any]:
        """
        Натиснути спеціальну клавішу.

        Args:
            key_name: 'printscreen', 'numlock', 'scrolllock', 'capslock', 'pause', ...

        Returns:
            {"success": True, "key": key_name}
        """
        try:
            key = self.SPECIAL_KEYS.get(key_name.lower(), key_name)
            pyautogui.press(key)
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== CLIPBOARD ====================

    def clipboard_copy_text(self, text: str) -> Dict[str, Any]:
        """
        Записати текст у буфер обміну.

        Args:
            text: Текст для копіювання

        Returns:
            {"success": True, "length": len(text)}
        """
        try:
            pyperclip.copy(text)
            return {"success": True, "length": len(text)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clipboard_get_text(self) -> Dict[str, Any]:
        """
        Прочитати текст з буфера обміну.
        
        Returns:
            {"success": True, "text": "..."}
        """
        try:
            text = pyperclip.paste()
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_input_unicode(self, text: str) -> Dict[str, Any]:
        """
        Вставити текст через SendInput з KEYEVENTF_UNICODE (працює з кирилицею).
        
        ⚠️ КРИТИЧНИЙ МЕТОД - НЕ ЗМІНЮВАТИ БЕЗ УЗГОДЖЕННЯ
        Логіка оптимізована для Windows 10/11 з підтримкою кирилиці та емодзі.
        
        Args:
            text: Текст для вставки
            
        Returns:
            {"success": True, "sent": n} або {"success": False, "error": "..."}
        """
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

        try:
            cb = ctypes.sizeof(INPUT)
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
                return {"success": False, "error": f"SendInput failed: sent={sent}/{n}, error={err}"}

            return {"success": True, "sent": sent}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def insert_text_smart(self, text: str) -> Dict[str, Any]:
        """
        Універсальна вставка тексту з адаптивною логікою для Windows 10/11:
        
        - Chrome/Qt/Notepad: SendInput Unicode (найнадійніший для сучасних UI)
        - Старий Win32: WM_PASTE (fallback)
        - Last fallback: Ctrl+V
        
        ⚠️ КРИТИЧНИЙ МЕТОД - НЕ ЗМІНЮВАТИ БЕЗ УЗГОДЖЕННЯ
        Логіка оптимізована для Windows 10/11 з підтримкою кирилиці та емодзі.
        
        Args:
            text: Текст для вставки
            
        Returns:
            {"success": True, "method": "..."} або {"success": False, "error": "..."}
        """
        import ctypes
        
        user32 = ctypes.windll.user32
        WM_PASTE = 0x0302
        
        try:
            # Отримати активне вікно
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return {"success": False, "error": "No active window"}
            
            # Визначити клас вікна
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buf, 255)
            class_name = buf.value.lower()
            
            is_chrome = "chrome" in class_name
            is_qt = "qt" in class_name
            is_notepad = "notepad" in class_name  # Windows 11 Notepad
            
            print(f"[Keyboard] class='{class_name}', chrome={is_chrome}, qt={is_qt}, notepad={is_notepad}")
            
            # Спочатку найбільш універсальний метод для сучасних програм
            if is_chrome or is_qt or is_notepad:
                # Для PyQt6 з не-ASCII - одразу Ctrl+V (SendInput спотворює емодзі)
                if is_qt and any(ord(c) > 127 for c in text):
                    print("[Keyboard] PyQt6 with non-ASCII -> Ctrl+V (more reliable)")
                    pyperclip.copy(text)
                    time.sleep(0.15)
                    try:
                        import ctypes
                        VK_CONTROL, VK_V = 0x11, 0x56
                        KEYEVENTF_KEYDOWN, KEYEVENTF_KEYUP = 0x0000, 0x0002
                        
                        user32 = ctypes.windll.user32
                        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYDOWN, 0)
                        time.sleep(0.05)
                        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYDOWN, 0)
                        time.sleep(0.05)
                        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
                        time.sleep(0.05)
                        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
                        time.sleep(0.1)
                        return {"success": True, "method": "Ctrl+V (Win32)", "target": class_name}
                    except Exception as e:
                        print(f"[Keyboard] Win32 Ctrl+V failed: {e}")
                
                # Для Chrome, Notepad або PyQt6 з ASCII - SendInput Unicode
                print(f"[Keyboard] {class_name} detected -> SendInput Unicode")
                time.sleep(0.1)  # Затримка для стабільності
                result = self.send_input_unicode(text)
                
                # Fallback на Ctrl+V ТІЛЬКИ якщо SendInput НЕ спрацював
                if not result.get("success") and is_qt:
                    print("[Keyboard] SendInput failed for PyQt6 -> Ctrl+V fallback")
                    pyperclip.copy(text)
                    time.sleep(0.15)
                    try:
                        import ctypes
                        VK_CONTROL, VK_V = 0x11, 0x56
                        KEYEVENTF_KEYDOWN, KEYEVENTF_KEYUP = 0x0000, 0x0002
                        
                        user32 = ctypes.windll.user32
                        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYDOWN, 0)
                        time.sleep(0.05)
                        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYDOWN, 0)
                        time.sleep(0.05)
                        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
                        time.sleep(0.05)
                        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
                        time.sleep(0.1)
                        return {"success": True, "method": "Ctrl+V (Win32)", "target": class_name}
                    except Exception as e:
                        print(f"[Keyboard] Win32 Ctrl+V failed: {e}")
                
                if result.get("success"):
                    return {"success": True, "method": "SendInput Unicode", "target": class_name}
                else:
                    print(f"[Keyboard] SendInput failed for {class_name}, trying fallback")
            
            # Для старого Win32 або якщо SendInput не спрацював
            if not is_chrome and not is_qt and not is_notepad:
                try:
                    # Спочатку копіюємо в буфер
                    pyperclip.copy(text)
                    time.sleep(0.05)
                    # WM_PASTE для класичних Win32 додатків
                    user32.SendMessageW(hwnd, WM_PASTE, 0, 0)
                    time.sleep(0.1)
                    return {"success": True, "method": "WM_PASTE", "target": class_name}
                except Exception as e:
                    print(f"[Keyboard] WM_PASTE failed: {e}")
            
            # Остаточний універсальний fallback
            print("[Keyboard] Final fallback -> Ctrl+V")
            pyperclip.copy(text)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
            return {"success": True, "method": "Ctrl+V (final fallback)"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== MOUSE ====================

    def _convert_image_to_dib(self, image_path: str) -> bytes:
        """Конвертувати зображення в DIB формат для clipboard."""
        image = Image.open(image_path)
        output = BytesIO()
        image.convert('RGB').save(output, 'BMP')
        data = output.getvalue()[14:]  # Пропускаємо заголовок BMP
        output.close()
        return data

    def clipboard_copy_image(self, image_path: str) -> Dict[str, Any]:
        """
        Скопіювати зображення у буфер обміну.

        Args:
            image_path: Шлях до зображення

        Returns:
            {"success": True, "path": image_path}
        """
        try:
            if not os.path.exists(image_path):
                return {"success": False, "error": f"Image not found: {image_path}"}

            import win32clipboard

            data = self._convert_image_to_dib(image_path)

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()

            return {"success": True, "path": image_path}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==================== Функції для інтеграції в TOOL_POLICIES ====================

try:
    _controller = MouseKeyboardController()
except (NotImplementedError, AttributeError):
    _controller = None


def _ensure_controller() -> MouseKeyboardController:
    if _controller is None:
        raise RuntimeError("MouseKeyboardController недоступний (не Windows)")
    return _controller


def mouse_click(x: int, y: int, button: str = 'left', clicks: int = 1, interval: float = 0.1) -> Dict[str, Any]:
    """Клік мишою в координати."""
    return _ensure_controller().mouse_click(x, y, button, clicks, interval)


def mouse_move(x: int, y: int, duration: float = 0.5) -> Dict[str, Any]:
    """Перемістити курсор в координати."""
    return _ensure_controller().mouse_move(x, y, duration)


def mouse_scroll(amount: int, direction: str = 'vertical',
                 x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Прокрутка мишою."""
    return _ensure_controller().mouse_scroll(amount, direction, x, y)


def mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int,
               duration: float = 0.5, button: str = 'left') -> Dict[str, Any]:
    """Перетягування drag & drop."""
    return _ensure_controller().mouse_drag(start_x, start_y, end_x, end_y, duration, button)


def get_mouse_position() -> Dict[str, Any]:
    """Поточні координати курсора."""
    return _ensure_controller().get_mouse_position()


def wait_for_response(duration: int = 300, check_interval: int = 25, 
                     check_for_confirmation: bool = True, 
                     check_for_response: bool = True,
                     response_keywords: list = None,
                     use_uia: bool = True) -> Dict[str, Any]:
    """Зачекати відповіді від програми (універсально для будь-якого вікна/додатку).
    
    Args:
        duration: Максимальний час очікування в секундах (дефолт 300 = 5 хв)
        check_interval: Інтервал перевірки в секундах (дефолт 25 = перевірка кожні 25с)
        check_for_confirmation: Чи перевіряти наявність запиту на підтвердження через OCR
        check_for_response: Чи перевіряти наявність нової відповіді через OCR або UIA
        response_keywords: Ключові слова що вказують на відповідь (дефолт: ['відповідь', 'response', 'answer'])
        use_uia: Чи використовувати UI Automation для перевірки (швидше і надійніше за OCR)
        
    Returns:
        {"ok": True, "waited_seconds": <time>, "status": "completed|timeout|confirmation_found|response_found"}
    """
    if response_keywords is None:
        response_keywords = ["відповідь", "response", "answer", "result"]
    
    import time
    start_time = time.time()
    status = "completed"
    previous_text = ""
    
    print(f"⏳ Очікування відповіді (макс {duration}с, перевірка кожні {check_interval}с, метод: {'UIA+OCR' if use_uia else 'OCR'})...")
    
    try:
        from .tools_ocr import ocr_image
        from .tools_screen_capture import take_screenshot
        
        # Спробуємо використати UIA якщо доступно
        uia_available = False
        if use_uia:
            try:
                # Ініціалізуємо COM для потоки перед використанням UIA
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                except Exception:
                    pass  # CoInitialize може бути вже викликаний
                
                from .tools_ui_accessibility import UIAWrapper, uia_get_focused_element
                uia_wrapper = UIAWrapper()
                uia_available = uia_wrapper.is_available()
                if uia_available:
                    print(f"✅ UIA доступний")
                else:
                    print(f"⚠️ UIA недоступний, використовуємо OCR")
                    use_uia = False
            except Exception as e:
                print(f"⚠️ UIA недоступний, використовуємо OCR: {e}")
                use_uia = False
        
        # Отримуємо початковий текст для порівняння
        if check_for_response:
            try:
                if use_uia and uia_available:
                    try:
                        focused = uia_get_focused_element({})
                        if focused.get("ok") and focused.get("text"):
                            previous_text = focused["text"]
                            print(f"📝 Початковий текст (UIA): {len(previous_text)} символів")
                        else:
                            # Fallback на OCR якщо UIA не повернув текст
                            result = take_screenshot()
                            if result.get("ok") and result.get("path"):
                                ocr_result = ocr_image({"image_path": result["path"]})
                                if ocr_result.get("ok") and ocr_result.get("text"):
                                    previous_text = ocr_result["text"]
                                    print(f"📝 Початковий текст (OCR fallback): {len(previous_text)} символів")
                    except Exception as e:
                        print(f"⚠️ Помилка UIA для початкового тексту: {e}, використовуємо OCR")
                        result = take_screenshot()
                        if result.get("ok") and result.get("path"):
                            ocr_result = ocr_image({"image_path": result["path"]})
                            if ocr_result.get("ok") and ocr_result.get("text"):
                                previous_text = ocr_result["text"]
                                print(f"📝 Початковий текст (OCR): {len(previous_text)} символів")
                else:
                    result = take_screenshot()
                    if result.get("ok") and result.get("path"):
                        ocr_result = ocr_image({"image_path": result["path"]})
                        if ocr_result.get("ok") and ocr_result.get("text"):
                            previous_text = ocr_result["text"]
                            print(f"📝 Початковий текст (OCR): {len(previous_text)} символів")
            except Exception as e:
                print(f"⚠️ Помилка отримання початкового тексту: {e}")
        
        elapsed = 0
        while elapsed < duration:
            time.sleep(check_interval)
            elapsed = time.time() - start_time
            
            # Перевіряємо на підтвердження
            if check_for_confirmation:
                try:
                    result = take_screenshot()
                    if result.get("ok") and result.get("path"):
                        ocr_result = ocr_image({"image_path": result["path"]})
                        if ocr_result.get("ok") and ocr_result.get("text"):
                            text = ocr_result["text"].lower()
                            # Перевіряємо наявність запитів на підтвердження (багатомовні)
                            confirmation_keywords = [
                                "підтвердити", "confirm", "allow", "дозволити", "продовжити",
                                "approve", "yes", "no", "cancel", "ок", "так", "ні"
                            ]
                            if any(keyword in text for keyword in confirmation_keywords):
                                print(f"✅ Знайдено запит на підтвердження через {elapsed:.1f}с")
                                return {
                                    "ok": True,
                                    "waited_seconds": elapsed,
                                    "status": "confirmation_found",
                                    "confirmation_detected": True
                                }
                except Exception as e:
                    print(f"⚠️ Помилка перевірки підтвердження: {e}")
            
            # Перевіряємо на нову відповідь
            if check_for_response:
                try:
                    current_text = ""
                    
                    if use_uia and uia_available:
                        try:
                            focused = uia_get_focused_element({})
                            if focused.get("ok") and focused.get("text"):
                                current_text = focused["text"]
                                print(f"📝 Поточний текст (UIA): {len(current_text)} символів")
                            else:
                                # Fallback на OCR
                                result = take_screenshot()
                                if result.get("ok") and result.get("path"):
                                    ocr_result = ocr_image({"image_path": result["path"]})
                                    if ocr_result.get("ok") and ocr_result.get("text"):
                                        current_text = ocr_result["text"]
                                        print(f"📝 Поточний текст (OCR fallback): {len(current_text)} символів")
                        except Exception as e:
                            print(f"⚠️ Помилка UIA: {e}, використовуємо OCR")
                            result = take_screenshot()
                            if result.get("ok") and result.get("path"):
                                ocr_result = ocr_image({"image_path": result["path"]})
                                if ocr_result.get("ok") and ocr_result.get("text"):
                                    current_text = ocr_result["text"]
                                    print(f"📝 Поточний текст (OCR): {len(current_text)} символів")
                    else:
                        result = take_screenshot()
                        if result.get("ok") and result.get("path"):
                            ocr_result = ocr_image({"image_path": result["path"]})
                            if ocr_result.get("ok") and ocr_result.get("text"):
                                current_text = ocr_result["text"]
                                print(f"📝 Поточний текст (OCR): {len(current_text)} символів")
                    
                    # Перевіряємо чи текст змінився
                    if current_text and current_text != previous_text:
                        # Перевіряємо наявність ключових слів відповіді
                        text_lower = current_text.lower()
                        if any(keyword.lower() in text_lower for keyword in response_keywords):
                            print(f"✅ Знайдено відповідь через {elapsed:.1f}с")
                            return {
                                "ok": True,
                                "waited_seconds": elapsed,
                                "status": "response_found",
                                "response_detected": True
                            }
                        
                        # Якщо текст суттєво змінився (>50 символів)
                        if len(current_text) > len(previous_text) + 50:
                            print(f"✅ Виявлено новий текст через {elapsed:.1f}с (+{len(current_text) - len(previous_text)} символів)")
                            return {
                                "ok": True,
                                "waited_seconds": elapsed,
                                "status": "response_found",
                                "response_detected": True
                            }
                except Exception as e:
                    print(f"⚠️ Помилка перевірки відповіді: {e}")
            
            print(f"⏳ Пройшло {elapsed:.1f}с...")
            
        status = "timeout" if elapsed >= duration else "completed"
        
    except Exception as e:
        print(f"❌ Помилка очікування: {e}")
        return {"ok": False, "error": str(e)}
    
    print(f"⏱️ Очікування завершено: {status} ({elapsed:.1f}с)")
    return {
        "ok": True,
        "waited_seconds": elapsed,
        "status": status
    }


def mouse_click_image(image_path: str, confidence: float = 0.8) -> Dict[str, Any]:
    """Клік по зображенню на екрані."""
    return _ensure_controller().mouse_click_image(image_path, confidence)


def keyboard_press(key: str) -> Dict[str, Any]:
    """Натиснути клавішу."""
    return _ensure_controller().keyboard_press(key)


def keyboard_type(text: str, interval: float = 0.02) -> Dict[str, Any]:
    """Ввести текст посимвольно."""
    return _ensure_controller().keyboard_type(text, interval)


def keyboard_hotkey(*keys: str) -> Dict[str, Any]:
    """Комбінація клавіш."""
    return _ensure_controller().keyboard_hotkey(*keys)


def keyboard_hold(key: str, duration: float = 1.0) -> Dict[str, Any]:
    """Утримувати клавішу."""
    return _ensure_controller().keyboard_hold(key, duration)


def keyboard_send_special(key_name: str) -> Dict[str, Any]:
    """Спеціальна клавіша (PrintScreen, NumLock, ...)."""
    return _ensure_controller().keyboard_send_special(key_name)


def clipboard_copy_text(text: str) -> Dict[str, Any]:
    """Копіювати текст у буфер."""
    return _ensure_controller().clipboard_copy_text(text)


def clipboard_get_text() -> Dict[str, Any]:
    """Отримати текст з буфера."""
    return _ensure_controller().clipboard_get_text()


def send_input_unicode(text: str) -> Dict[str, Any]:
    """Вставити текст через SendInput з KEYEVENTF_UNICODE (працює з кирилицею)."""
    return _ensure_controller().send_input_unicode(text)


def insert_text_smart(text: str) -> Dict[str, Any]:
    """
    Універсальна вставка тексту з адаптивною логікою:
    
    - Chrome: SendInput Unicode (WM_PASTE не працює)
    - PyQt6/Win32: WM_PASTE
    - Fallback: SendInput Unicode
    - Last fallback: Ctrl+V
    """
    return _ensure_controller().insert_text_smart(text)


def clipboard_copy_image(image_path: str) -> Dict[str, Any]:
    """Копіювати зображення у буфер."""
    return _ensure_controller().clipboard_copy_image(image_path)
