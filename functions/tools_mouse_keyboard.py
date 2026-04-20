"""
Керування мишею та клавіатурою через pyautogui.

Модуль для GUI Automation Phase 1.
Забезпечує керування мишою, клавіатурою та буфером обміну.
"""

import time
import pyautogui
import pyperclip
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image
import os


# Налаштування pyautogui для безпеки
pyautogui.FAILSAFE = True  # Рух мишою в кут екрану = аварійна зупинка
pyautogui.PAUSE = 0.1  # Пауза між діями


class MouseKeyboardController:
    """Контролер для керування мишею та клавіатурою."""

    def __init__(self):
        self.last_position = None

    # ==================== МИША ====================

    def mouse_click(self, x: int, y: int, button: str = 'left',
                    clicks: int = 1, interval: float = 0.1) -> Dict[str, Any]:
        """
        Клік мишою в координати (x, y).

        Args:
            x: Координата X
            y: Координата Y
            button: 'left', 'right', 'middle'
            clicks: Кількість кліків (1 = одинарний, 2 = подвійний)
            interval: Інтервал між кліками при clicks > 1

        Returns:
            {"success": True, "position": {"x": x, "y": y}, "button": button}
        """
        try:
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

    def keyboard_type(self, text: str, interval: float = 0.02) -> Dict[str, Any]:
        """
        Ввести текст (посимвольно).

        Args:
            text: Текст для введення
            interval: Інтервал між символами в секундах

        Returns:
            {"success": True, "text": text, "length": len(text)}
        """
        try:
            pyautogui.typewrite(text, interval=interval)
            return {
                "success": True,
                "text": text,
                "length": len(text),
                "interval": interval
            }
        except Exception as e:
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
        special_keys = {
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

        try:
            key = special_keys.get(key_name.lower(), key_name)
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
            {"text": str, "length": int}
        """
        try:
            text = pyperclip.paste()
            return {"text": text, "length": len(text) if text else 0}
        except Exception as e:
            return {"success": False, "error": str(e)}

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

            # Використовуємо PIL для копіювання зображення
            from PIL import Image
            image = Image.open(image_path)

            # Для Windows використовуємо win32clipboard
            import win32clipboard
            from io import BytesIO

            output = BytesIO()
            image.convert('RGB').save(output, 'BMP')
            data = output.getvalue()[14:]  # Пропускаємо заголовок BMP
            output.close()

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()

            return {"success": True, "path": image_path}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==================== Функції для інтеграції в TOOL_POLICIES ====================

_controller = MouseKeyboardController()


def mouse_click(x: int, y: int, button: str = 'left', clicks: int = 1, interval: float = 0.1) -> Dict[str, Any]:
    """Клік мишою в координати."""
    return _controller.mouse_click(x, y, button, clicks, interval)


def mouse_move(x: int, y: int, duration: float = 0.5) -> Dict[str, Any]:
    """Перемістити курсор в координати."""
    return _controller.mouse_move(x, y, duration)


def mouse_scroll(amount: int, direction: str = 'vertical',
                 x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Прокрутка мишою."""
    return _controller.mouse_scroll(amount, direction, x, y)


def mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int,
               duration: float = 0.5, button: str = 'left') -> Dict[str, Any]:
    """Перетягування drag & drop."""
    return _controller.mouse_drag(start_x, start_y, end_x, end_y, duration, button)


def get_mouse_position() -> Dict[str, Any]:
    """Поточні координати курсора."""
    return _controller.get_mouse_position()


def mouse_click_image(image_path: str, confidence: float = 0.8) -> Dict[str, Any]:
    """Клік по зображенню на екрані."""
    return _controller.mouse_click_image(image_path, confidence)


def keyboard_press(key: str) -> Dict[str, Any]:
    """Натиснути клавішу."""
    return _controller.keyboard_press(key)


def keyboard_type(text: str, interval: float = 0.02) -> Dict[str, Any]:
    """Ввести текст посимвольно."""
    return _controller.keyboard_type(text, interval)


def keyboard_hotkey(*keys: str) -> Dict[str, Any]:
    """Комбінація клавіш."""
    return _controller.keyboard_hotkey(*keys)


def keyboard_hold(key: str, duration: float = 1.0) -> Dict[str, Any]:
    """Утримувати клавішу."""
    return _controller.keyboard_hold(key, duration)


def keyboard_send_special(key_name: str) -> Dict[str, Any]:
    """Спеціальна клавіша (PrintScreen, NumLock, ...)."""
    return _controller.keyboard_send_special(key_name)


def clipboard_copy_text(text: str) -> Dict[str, Any]:
    """Копіювати текст у буфер."""
    return _controller.clipboard_copy_text(text)


def clipboard_get_text() -> Dict[str, Any]:
    """Отримати текст з буфера."""
    return _controller.clipboard_get_text()


def clipboard_copy_image(image_path: str) -> Dict[str, Any]:
    """Копіювати зображення у буфер."""
    return _controller.clipboard_copy_image(image_path)
