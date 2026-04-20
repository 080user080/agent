"""
Захоплення екрану та аналіз скріншотів.

GUI Automation Phase 2 — "очі" агента.
Використовує mss для швидкого захоплення та Pillow для обробки.
"""

import time
import os
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
import numpy as np

try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# win32 для захоплення вікон
import win32gui
import win32con
import win32ui
import ctypes


class ScreenCapture:
    """Клас для захоплення та аналізу екрану."""

    def __init__(self):
        self._cache = {}  # Кеш скріншотів
        self._max_cache_size = 10
        self._screenshot_counter = 0

    # ==================== БАЗОВЕ ЗАХОПЛЕННЯ ====================

    def take_screenshot(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Зняти скріншот всього екрану (усіх моніторів).

        Args:
            save_path: Шлях для збереження (опціонально)

        Returns:
            {"success": True, "image": PIL.Image, "size": (w, h), "path": save_path}
        """
        try:
            if MSS_AVAILABLE:
                with mss.mss() as sct:
                    # Захоплюємо всі монітори
                    screenshot = sct.grab(sct.monitors[0])
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            else:
                # Fallback на Pillow
                img = self._screenshot_pil()

            # Зберігаємо в кеш
            self._cache_screenshot(img)

            result = {
                "success": True,
                "size": img.size,
                "mode": img.mode
            }

            if save_path:
                img.save(save_path)
                result["path"] = save_path
                result["format"] = os.path.splitext(save_path)[1].lower().replace('.', '')

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def capture_monitor(self, monitor_index: int = 0, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Захопити конкретний монітор.

        Args:
            monitor_index: Індекс монітора (0 = основний, 1+ = додаткові)
            save_path: Шлях для збереження

        Returns:
            {"success": True, "image": PIL.Image, "monitor": index, "size": (w, h)}
        """
        try:
            if MSS_AVAILABLE:
                with mss.mss() as sct:
                    monitors = sct.monitors
                    if monitor_index >= len(monitors):
                        return {
                            "success": False,
                            "error": f"Монітор {monitor_index} не існує. Доступно: {len(monitors)}"
                        }

                    monitor = monitors[monitor_index]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            else:
                img = self._screenshot_pil()

            self._cache_screenshot(img)

            result = {
                "success": True,
                "monitor": monitor_index,
                "size": img.size,
                "mode": img.mode
            }

            if save_path:
                img.save(save_path)
                result["path"] = save_path

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def capture_region(self, x: int, y: int, width: int, height: int,
                      save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Захопити прямокутну область екрану.

        Args:
            x, y: Лівий верхній кут
            width, height: Розмір області
            save_path: Шлях для збереження

        Returns:
            {"success": True, "image": PIL.Image, "region": (x, y, w, h)}
        """
        try:
            if MSS_AVAILABLE:
                with mss.mss() as sct:
                    monitor = {"left": x, "top": y, "width": width, "height": height}
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            else:
                # Fallback
                img = self._screenshot_pil().crop((x, y, x + width, y + height))

            self._cache_screenshot(img)

            result = {
                "success": True,
                "region": {"x": x, "y": y, "width": width, "height": height},
                "size": img.size,
                "mode": img.mode
            }

            if save_path:
                img.save(save_path)
                result["path"] = save_path

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def capture_window(self, hwnd: int, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Захопити скріншот конкретного вікна (навіть якщо перекрите).

        Args:
            hwnd: Handle вікна
            save_path: Шлях для збереження

        Returns:
            {"success": True, "image": PIL.Image, "hwnd": hwnd}
        """
        try:
            # Отримуємо координати вікна
            rect = win32gui.GetWindowRect(hwnd)
            x, y, right, bottom = rect
            width = right - x
            height = bottom - y

            # Спосіб 1: Через win32ui (працює навіть для перекритих вікон)
            try:
                # Отримуємо DC вікна
                hwndDC = win32gui.GetWindowDC(hwnd)
                mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                saveDC = mfcDC.CreateCompatibleDC()

                # Створюємо bitmap
                saveBitMap = win32ui.CreateBitmap()
                saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
                saveDC.SelectObject(saveBitMap)

                # Копіюємо вміст вікна
                result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

                # Конвертуємо в PIL Image
                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)
                img = Image.frombuffer(
                    'RGB',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRX', 0, 1)

                # Очищуємо
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)

            except Exception as e:
                # Fallback: захоплюємо регіон
                return self.capture_region(x, y, width, height, save_path)

            self._cache_screenshot(img)

            result = {
                "success": True,
                "hwnd": hwnd,
                "region": {"x": x, "y": y, "width": width, "height": height},
                "size": img.size
            }

            if save_path:
                img.save(save_path)
                result["path"] = save_path

            return result

        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def capture_active_window(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Захопити активне (foreground) вікно.

        Args:
            save_path: Шлях для збереження

        Returns:
            {"success": True, "image": PIL.Image}
        """
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return {"success": False, "error": "Немає активного вікна"}

            return self.capture_window(hwnd, save_path)

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== ІНФОРМАЦІЯ ПРО ЕКРАН ====================

    def get_screen_size(self) -> Dict[str, Any]:
        """
        Отримати роздільну здатність екрану.

        Returns:
            {"width": int, "height": int}
        """
        try:
            if MSS_AVAILABLE:
                with mss.mss() as sct:
                    # sct.monitors[0] — віртуальний екран (усі монітори)
                    monitor = sct.monitors[0]
                    return {
                        "width": monitor["width"],
                        "height": monitor["height"]
                    }
            else:
                # Fallback через ctypes
                user32 = ctypes.windll.user32
                return {
                    "width": user32.GetSystemMetrics(0),
                    "height": user32.GetSystemMetrics(1)
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_monitors_info(self) -> List[Dict[str, Any]]:
        """
        Отримати інформацію про всі монітори.

        Returns:
            [{index, x, y, width, height, primary}, ...]
        """
        try:
            if MSS_AVAILABLE:
                with mss.mss() as sct:
                    monitors = []
                    for i, monitor in enumerate(sct.monitors):
                        monitors.append({
                            "index": i,
                            "x": monitor.get("left", 0),
                            "y": monitor.get("top", 0),
                            "width": monitor["width"],
                            "height": monitor["height"],
                            "primary": i == 0
                        })
                    return monitors
            else:
                # Fallback — один монітор
                size = self.get_screen_size()
                return [{
                    "index": 0,
                    "x": 0,
                    "y": 0,
                    "width": size.get("width", 1920),
                    "height": size.get("height", 1080),
                    "primary": True
                }]
        except Exception as e:
            return [{"success": False, "error": str(e)}]

    def get_pixel_color(self, x: int, y: int) -> Dict[str, Any]:
        """
        Отримати колір пікселя в точці.

        Args:
            x, y: Координати

        Returns:
            {"r": int, "g": int, "b": int, "hex": str}
        """
        try:
            # Захоплюємо 1x1 піксель
            result = self.capture_region(x, y, 1, 1)
            if not result.get("success"):
                return result

            # Отримуємо колір (не зберігаємо файл)
            # Для цього треба зберегти тимчасово
            import io
            img_bytes = io.BytesIO()
            # img не зберігається в результаті capture_region, треба змінити
            # Тому використаємо альтернативний спосіб через win32

            # Альтернатива: через GetPixel
            hdc = win32gui.GetDC(0)
            color = win32gui.GetPixel(hdc, x, y)
            win32gui.ReleaseDC(0, hdc)

            r = color & 0xff
            g = (color >> 8) & 0xff
            b = (color >> 16) & 0xff

            return {
                "r": r,
                "g": g,
                "b": b,
                "hex": f"#{r:02x}{g:02x}{b:02x}"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== ПОРІВНЯННЯ ТА ПОШУК ====================

    def find_image_on_screen(self, template_path: str, confidence: float = 0.8) -> Dict[str, Any]:
        """
        Знайти зображення на екрані (template matching).

        Args:
            template_path: Шлях до шаблону
            confidence: Поріг впевненості (0.0-1.0)

        Returns:
            {"found": True, "x": int, "y": int, "confidence": float} або {"found": False}
        """
        try:
            if not CV2_AVAILABLE:
                return {"success": False, "error": "OpenCV не встановлено (pip install opencv-python)"}

            if not os.path.exists(template_path):
                return {"success": False, "error": f"Шаблон не знайдено: {template_path}"}

            # Захоплюємо екран
            screen_result = self.take_screenshot()
            if not screen_result.get("success"):
                return screen_result

            # Конвертуємо для OpenCV
            # Треба зберегти скріншот тимчасово або передавати як масив
            # Спрощення: використаємо mss напряму

            with mss.mss() as sct:
                screenshot = np.array(sct.grab(sct.monitors[0]))
                template = cv2.imread(template_path)

                if template is None:
                    return {"success": False, "error": "Не вдалося завантажити шаблон"}

                # Template matching
                result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                if max_val >= confidence:
                    return {
                        "found": True,
                        "x": max_loc[0],
                        "y": max_loc[1],
                        "confidence": float(max_val),
                        "template_size": (template.shape[1], template.shape[0])
                    }
                else:
                    return {
                        "found": False,
                        "confidence": float(max_val),
                        "required": confidence
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def wait_for_image(self, template_path: str, timeout: float = 10.0,
                      interval: float = 0.5, confidence: float = 0.8) -> Dict[str, Any]:
        """
        Очікувати появи зображення на екрані.

        Args:
            template_path: Шлях до шаблону
            timeout: Максимальний час очікування (сек)
            interval: Інтервал між перевірками
            confidence: Поріг впевненості

        Returns:
            {"found": True, "x": int, "y": int, "waited": float} або {"found": False}
        """
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                result = self.find_image_on_screen(template_path, confidence)
                if result.get("found"):
                    result["waited"] = time.time() - start_time
                    return result
                time.sleep(interval)

            return {"found": False, "timeout": timeout}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def pixel_matches_color(self, x: int, y: int, color: Tuple[int, int, int],
                          tolerance: int = 10) -> Dict[str, Any]:
        """
        Перевірити, чи піксель відповідає кольору (з допуском).

        Args:
            x, y: Координати
            color: Очікуваний колір (R, G, B)
            tolerance: Допуск для кожного каналу

        Returns:
            {"matches": bool, "actual": (r, g, b), "expected": (r, g, b)}
        """
        try:
            actual = self.get_pixel_color(x, y)
            if actual.get("success") is False:
                return actual

            r, g, b = actual["r"], actual["g"], actual["b"]
            er, eg, eb = color

            matches = (abs(r - er) <= tolerance and
                      abs(g - eg) <= tolerance and
                      abs(b - eb) <= tolerance)

            return {
                "matches": matches,
                "actual": (r, g, b),
                "expected": color,
                "tolerance": tolerance
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def wait_for_color(self, x: int, y: int, color: Tuple[int, int, int],
                      timeout: float = 10.0, tolerance: int = 10) -> Dict[str, Any]:
        """
        Очікувати певний колір в точці.

        Args:
            x, y: Координати
            color: Очікуваний колір (R, G, B)
            timeout: Максимальний час
            tolerance: Допуск

        Returns:
            {"matches": True, "waited": float} або {"matches": False, "timeout": True}
        """
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                result = self.pixel_matches_color(x, y, color, tolerance)
                if result.get("matches"):
                    result["waited"] = time.time() - start_time
                    return result
                time.sleep(0.1)

            return {"matches": False, "timeout": True, "waited": timeout}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== ПРИВАТНІ МЕТОДИ ====================

    def _screenshot_pil(self) -> Image.Image:
        """Fallback скріншот через Pillow (повільніше)."""
        import pyautogui
        screenshot = pyautogui.screenshot()
        return screenshot

    def _cache_screenshot(self, img: Image.Image):
        """Зберегти скріншот в кеш."""
        self._screenshot_counter += 1
        key = f"screenshot_{self._screenshot_counter}"
        self._cache[key] = img

        # Обмежуємо розмір кешу
        if len(self._cache) > self._max_cache_size:
            oldest = min(self._cache.keys())
            del self._cache[oldest]

    def clear_cache(self):
        """Очистити кеш скріншотів."""
        self._cache.clear()
        return {"success": True, "message": "Кеш скріншотів очищено"}


# ==================== Функції для інтеграції в TOOL_POLICIES ====================

_capture = ScreenCapture()


def take_screenshot(save_path: Optional[str] = None) -> Dict[str, Any]:
    """Зняти скріншот всього екрану."""
    return _capture.take_screenshot(save_path)


def capture_monitor(monitor_index: int = 0, save_path: Optional[str] = None) -> Dict[str, Any]:
    """Захопити конкретний монітор."""
    return _capture.capture_monitor(monitor_index, save_path)


def capture_region(x: int, y: int, width: int, height: int,
                  save_path: Optional[str] = None) -> Dict[str, Any]:
    """Захопити область екрану."""
    return _capture.capture_region(x, y, width, height, save_path)


def capture_window(hwnd: int, save_path: Optional[str] = None) -> Dict[str, Any]:
    """Захопити вікно."""
    return _capture.capture_window(hwnd, save_path)


def capture_active_window(save_path: Optional[str] = None) -> Dict[str, Any]:
    """Захопити активне вікно."""
    return _capture.capture_active_window(save_path)


def get_screen_size() -> Dict[str, Any]:
    """Розмір екрану."""
    return _capture.get_screen_size()


def get_monitors_info() -> List[Dict[str, Any]]:
    """Інформація про монітори."""
    return _capture.get_monitors_info()


def get_pixel_color(x: int, y: int) -> Dict[str, Any]:
    """Колір пікселя."""
    return _capture.get_pixel_color(x, y)


def find_image_on_screen(template_path: str, confidence: float = 0.8) -> Dict[str, Any]:
    """Знайти зображення на екрані."""
    return _capture.find_image_on_screen(template_path, confidence)


def wait_for_image(template_path: str, timeout: float = 10.0,
                  interval: float = 0.5, confidence: float = 0.8) -> Dict[str, Any]:
    """Очікувати зображення."""
    return _capture.wait_for_image(template_path, timeout, interval, confidence)


def pixel_matches_color(x: int, y: int, color: Tuple[int, int, int],
                       tolerance: int = 10) -> Dict[str, Any]:
    """Перевірити колір пікселя."""
    return _capture.pixel_matches_color(x, y, color, tolerance)


def wait_for_color(x: int, y: int, color: Tuple[int, int, int],
                timeout: float = 10.0, tolerance: int = 10) -> Dict[str, Any]:
    """Очікувати колір."""
    return _capture.wait_for_color(x, y, color, timeout, tolerance)


def clear_screenshot_cache() -> Dict[str, Any]:
    """Очистити кеш скріншотів."""
    return _capture.clear_cache()
