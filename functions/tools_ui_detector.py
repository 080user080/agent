"""
Детекція UI-елементів через Computer Vision.

GUI Automation Phase 4 — "розуміння" інтерфейсу агентом.
Використовує OpenCV для пошуку кнопок, чекбоксів, полів вводу.
Комбінує OCR + CV для семантичного пошуку елементів.
"""

import cv2
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
import colorsys

from functions.tools_screen_capture import ScreenCapture
from functions.tools_ocr import ScreenOCR


class UIDetector:
    """Детектор UI-елементів на екрані."""

    # Характерні кольори для станів кнопок (RGB)
    BUTTON_COLORS = {
        "disabled": [(200, 200, 200), (192, 192, 192)],  # Сірий
        "hovered": [(230, 230, 250), (220, 220, 255)],   # Світло-блакитний
        "pressed": [(180, 180, 220)],                     # Темніший
    }

    # Розміри типових UI-елементів (для евристик)
    UI_SIZES = {
        "checkbox": (12, 12),      # Стандартний чекбокс Windows
        "radio": (12, 12),        # Radio button
        "scrollbar_width": 17,    # Ширина скролбару
        "button_min": (60, 23),   # Мінімальний розмір кнопки
    }

    def __init__(self, screen_capture: Optional[ScreenCapture] = None,
                 screen_ocr: Optional[ScreenOCR] = None):
        self.capture = screen_capture or ScreenCapture()
        self.ocr = screen_ocr or ScreenOCR(self.capture)
        self._template_cache = {}

    # ==================== TEMPLATE MATCHING ====================

    def find_button_by_image(self, template_path: str, confidence: float = 0.8,
                             region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Dict[str, Any]]:
        """
        Знайти кнопку за зображенням-шаблоном.

        Args:
            template_path: Шлях до зображення кнопки
            confidence: Мінімальний поріг співпадіння (0.0-1.0)
            region: Обмежити пошук регіоном (x, y, w, h)

        Returns:
            {"x": int, "y": int, "width": int, "height": int, "confidence": float} або None
        """
        try:
            screenshot = self._get_screenshot(region)
            template = self._load_template(template_path)

            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= confidence:
                h, w = template.shape[:2]
                x = max_loc[0] + (region[0] if region else 0)
                y = max_loc[1] + (region[1] if region else 0)
                return {
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "confidence": float(max_val),
                    "center_x": x + w // 2,
                    "center_y": y + h // 2
                }
            return None
        except Exception as e:
            return {"error": str(e)}

    def find_icon(self, icon_name_or_path: str, confidence: float = 0.8,
                  region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Dict[str, Any]]:
        """
        Знайти іконку на екрані.

        Args:
            icon_name_or_path: Назва відомої іконки або шлях до файлу
            confidence: Поріг співпадіння
            region: Обмежити пошук регіоном

        Returns:
            {"x": int, "y": int, "confidence": float} або None
        """
        return self.find_button_by_image(icon_name_or_path, confidence, region)

    def find_all_matches(self, template_path: str, confidence: float = 0.8,
                         region: Optional[Tuple[int, int, int, int]] = None,
                         max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Знайти всі входження шаблону на екрані.

        Args:
            template_path: Шлях до зображення-шаблону
            confidence: Поріг співпадіння
            region: Обмежити пошук
            max_results: Максимальна кількість результатів

        Returns:
            Список {"x", "y", "width", "height", "confidence"}
        """
        try:
            screenshot = self._get_screenshot(region)
            template = self._load_template(template_path)

            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= confidence)

            matches = []
            h, w = template.shape[:2]
            offset_x = region[0] if region else 0
            offset_y = region[1] if region else 0

            for pt in zip(*locations[::-1]):
                # Перевіряємо чи не занадто близько до інших знайдених
                too_close = any(
                    abs(pt[0] + offset_x - m["x"]) < w // 2 and
                    abs(pt[1] + offset_y - m["y"]) < h // 2
                    for m in matches
                )
                if not too_close:
                    matches.append({
                        "x": pt[0] + offset_x,
                        "y": pt[1] + offset_y,
                        "width": w,
                        "height": h,
                        "confidence": float(result[pt[1], pt[0]]),
                        "center_x": pt[0] + offset_x + w // 2,
                        "center_y": pt[1] + offset_y + h // 2
                    })
                    if len(matches) >= max_results:
                        break

            return matches
        except Exception as e:
            return [{"error": str(e)}]

    # ==================== CV ДЕТЕКЦІЯ ЕЛЕМЕНТІВ ====================

    def find_checkbox(self, region: Optional[Tuple[int, int, int, int]] = None,
                      checked: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Знайти чекбокси на екрані за допомогою CV.

        Args:
            region: Область для пошуку
            checked: Фільтр за станом (True=включений, False=вимкнений, None=всі)

        Returns:
            Список {"x", "y", "width", "height", "checked": bool}
        """
        try:
            screenshot = self._get_screenshot(region)
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

            # Шукаємо квадратні контури типового розміру чекбокса
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            checkboxes = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)

                # Фільтр за розміром чекбокса
                if 10 <= w <= 20 and 10 <= h <= 20 and 0.8 <= w/h <= 1.2:
                    # Перевіряємо чи це дійсно чекбокс (аналіз вмісту)
                    roi = screenshot[y:y+h, x:x+w]
                    is_checked = self._analyze_checkbox_state(roi)

                    if checked is None or is_checked == checked:
                        offset_x = region[0] if region else 0
                        offset_y = region[1] if region else 0
                        checkboxes.append({
                            "x": x + offset_x,
                            "y": y + offset_y,
                            "width": w,
                            "height": h,
                            "checked": is_checked,
                            "center_x": x + offset_x + w // 2,
                            "center_y": y + offset_y + h // 2
                        })

            return checkboxes
        except Exception as e:
            return [{"error": str(e)}]

    def find_input_field(self, region: Optional[Tuple[int, int, int, int]] = None,
                         min_width: int = 80, min_height: int = 20) -> List[Dict[str, Any]]:
        """
        Знайти поля вводу (input fields) на екрані.

        Args:
            region: Область для пошуку
            min_width: Мінімальна ширина поля
            min_height: Мінімальна висота поля

        Returns:
            Список {"x", "y", "width", "height"}
        """
        try:
            screenshot = self._get_screenshot(region)
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

            # Шукаємо прямокутні контури з характерним співвідношенням
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            fields = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)

                # Поле вводу: широкий прямокутник невеликої висоти
                if w >= min_width and 20 <= h <= 40 and w > h * 2:
                    # Перевіряємо чи має рамку (характерно для input)
                    if self._has_border(gray, x, y, w, h):
                        offset_x = region[0] if region else 0
                        offset_y = region[1] if region else 0
                        fields.append({
                            "x": x + offset_x,
                            "y": y + offset_y,
                            "width": w,
                            "height": h,
                            "center_x": x + offset_x + w // 2,
                            "center_y": y + offset_y + h // 2
                        })

            return fields
        except Exception as e:
            return [{"error": str(e)}]

    def find_progress_bar(self, region: Optional[Tuple[int, int, int, int]] = None,
                          min_width: int = 60) -> Optional[Dict[str, Any]]:
        """
        Знайти прогрес-бар на екрані.

        Args:
            region: Область для пошуку
            min_width: Мінімальна ширина прогрес-бару

        Returns:
            {"x", "y", "width", "height", "percent": float} або None
        """
        try:
            screenshot = self._get_screenshot(region)
            hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)

            # Шукаємо горизонтальні лінії з яскравими кольорами (заповнена частина)
            # Типові кольори прогрес-бару: синій, зелений, помаранчевий
            lower_blue = np.array([100, 50, 50])
            upper_blue = np.array([130, 255, 255])
            mask = cv2.inRange(hsv, lower_blue, upper_blue)

            # Шукаємо контури
            contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)

                # Прогрес-бар: широкий, низький
                if w >= min_width and 4 <= h <= 25:
                    # Оцінюємо відсоток заповнення
                    percent = self._estimate_progress_percent(screenshot, x, y, w, h)

                    offset_x = region[0] if region else 0
                    offset_y = region[1] if region else 0
                    return {
                        "x": x + offset_x,
                        "y": y + offset_y,
                        "width": w,
                        "height": h,
                        "percent": percent
                    }

            return None
        except Exception as e:
            return {"error": str(e)}

    # ==================== КОМБІНОВАНИЙ OCR + CV ПОШУК ====================

    def find_button_by_text(self, text: str, region: Optional[Tuple[int, int, int, int]] = None,
                            confidence: float = 0.7) -> Optional[Dict[str, Any]]:
        """
        Знайти кнопку за текстом (OCR + CV евристики).

        Args:
            text: Текст на кнопці
            region: Область для пошуку
            confidence: Мінімальна впевненість OCR

        Returns:
            {"x", "y", "center_x", "center_y", "text", "confidence"} або None
        """
        try:
            # Спочатку шукаємо текст через OCR
            ocr_result = self.ocr.find_text_on_screen(text, region, case_sensitive=False)

            if ocr_result and ocr_result.get("success"):
                for match in ocr_result.get("matches", []):
                    if match.get("confidence", 0) >= confidence:
                        # Перевіряємо чи це схоже на кнопку (прямокутна область з рамкою)
                        x, y, w, h = match["x"], match["y"], match["width"], match["height"]

                        return {
                            "x": x,
                            "y": y,
                            "center_x": match.get("center_x", x + w // 2),
                            "center_y": match.get("center_y", y + h // 2),
                            "width": w,
                            "height": h,
                            "text": match.get("text", text),
                            "confidence": match.get("confidence", 0)
                        }

            return None
        except Exception as e:
            return {"error": str(e)}

    def find_label(self, text: str, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Dict[str, Any]]:
        """
        Знайти мітку (label) з вказаним текстом.

        Args:
            text: Текст мітки
            region: Область для пошуку

        Returns:
            {"x", "y", "center_x", "center_y", "text"} або None
        """
        return self.find_button_by_text(text, region)

    def find_input_near_label(self, label_text: str, region: Optional[Tuple[int, int, int, int]] = None,
                               max_distance: int = 100) -> Optional[Dict[str, Any]]:
        """
        Знайти поле вводу поруч з міткою.

        Args:
            label_text: Текст мітки
            region: Область для пошуку
            max_distance: Максимальна відстань від мітки до поля

        Returns:
            {"x", "y", "width", "height", "label": {...}} або None
        """
        try:
            # Знаходимо мітку
            label = self.find_label(label_text, region)
            if not label:
                return None

            # Шукаємо поля вводу в околі мітки
            label_x, label_y = label["x"], label["y"]
            search_region = (
                max(0, label_x - max_distance),
                max(0, label_y - 20),
                max_distance * 2,
                60
            )

            fields = self.find_input_field(search_region)
            if fields:
                # Беремо найближче поле
                closest = min(fields,
                    key=lambda f: abs(f["x"] - label_x) + abs(f["y"] - label_y))
                closest["label"] = label
                return closest

            return None
        except Exception as e:
            return {"error": str(e)}

    # ==================== АНАЛІЗ СТАНУ ЕЛЕМЕНТІВ ====================

    def is_button_enabled(self, x: int, y: int, width: int, height: int) -> bool:
        """
        Визначити чи кнопка активна (не disabled) за кольором.

        Args:
            x, y, width, height: Координати кнопки

        Returns:
            True якщо кнопка активна, False якщо disabled
        """
        try:
            screenshot = self._get_screenshot()
            roi = screenshot[y:y+height, x:x+width]

            # Обчислюємо середній колір
            mean_color = cv2.mean(roi)[:3]

            # Перевіряємо чи не сірий (disabled)
            r, g, b = mean_color
            gray_diff = abs(int(r) - int(g)) + abs(int(g) - int(b)) + abs(int(r) - int(b))

            # Якщо кольори близькі до сірого — кнопка disabled
            return gray_diff > 30  # Поріг різниці кольорів
        except Exception:
            return True  # За замовчуванням вважаємо активною

    def is_checkbox_checked(self, x: int, y: int, width: int = 16, height: int = 16) -> bool:
        """
        Визначити стан чекбокса (включений/вимкнений).

        Args:
            x, y: Координати чекбокса
            width, height: Розмір (за замовчуванням 16x16)

        Returns:
            True якщо включений, False якщо вимкнений
        """
        try:
            screenshot = self._get_screenshot()
            roi = screenshot[y:y+height, x:x+width]

            return self._analyze_checkbox_state(roi)
        except Exception:
            return False

    def get_button_state(self, x: int, y: int, width: int = 80, height: int = 25) -> str:
        """
        Визначити візуальний стан кнопки.

        Args:
            x, y: Координати кнопки
            width, height: Розмір кнопки

        Returns:
            "normal" | "hovered" | "pressed" | "disabled"
        """
        try:
            screenshot = self._get_screenshot()
            roi = screenshot[y:y+height, x:x+width]

            mean_color = cv2.mean(roi)[:3]
            r, g, b = int(mean_color[0]), int(mean_color[1]), int(mean_color[2])

            # Конвертуємо в HSV для кращого аналізу
            h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)

            # Евристики для станів
            gray_diff = abs(r - g) + abs(g - b) + abs(r - b)

            if gray_diff < 20 and v < 0.6:
                return "disabled"
            elif s > 0.3 and v > 0.8:
                return "hovered"
            elif v < 0.5:
                return "pressed"
            else:
                return "normal"
        except Exception:
            return "normal"

    # ==================== ДОПОМІЖНІ МЕТОДИ ====================

    def _get_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
        """Отримати скріншот як numpy array (BGR для OpenCV)."""
        if region:
            result = self.capture.capture_region(*region)
        else:
            result = self.capture.take_screenshot()

        if not result.get("success"):
            raise RuntimeError(f"Failed to capture screenshot: {result.get('error')}")

        # Конвертуємо PIL Image в numpy array
        img = result.get("image")
        if img is None:
            raise RuntimeError("No image in screenshot result")

        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def _load_template(self, template_path: str) -> np.ndarray:
        """Завантажити шаблон з кешуванням."""
        if template_path not in self._template_cache:
            template = cv2.imread(template_path)
            if template is None:
                raise ValueError(f"Cannot load template: {template_path}")
            self._template_cache[template_path] = template
        return self._template_cache[template_path]

    def _analyze_checkbox_state(self, roi: np.ndarray) -> bool:
        """Аналізувати чи включений чекбокс."""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Шукаємо контури всередині чекбокса (галочка)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

        # Підраховуємо білі пікселі (галочка)
        white_pixels = np.sum(thresh > 0)
        total_pixels = thresh.size

        # Якщо білих пікселів достатньо — галочка є
        return white_pixels / total_pixels > 0.1

    def _has_border(self, gray_img: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
        """Перевірити чи має область рамку (характерно для input field)."""
        # Перевіряємо градієнт по краях
        top = np.mean(gray_img[y, x:x+w])
        bottom = np.mean(gray_img[y+h-1, x:x+w])
        left = np.mean(gray_img[y:y+h, x])
        right = np.mean(gray_img[y:y+h, x+w-1])

        center = np.mean(gray_img[y+2:y+h-2, x+2:x+w-2])
        edges_avg = (top + bottom + left + right) / 4

        # Якщо краї темніші за центр — ймовірно це рамка
        return edges_avg < center - 10

    def _estimate_progress_percent(self, screenshot: np.ndarray, x: int, y: int, w: int, h: int) -> float:
        """Оцінити відсоток заповнення прогрес-бару."""
        roi = screenshot[y:y+h, x:x+w]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Шукаємо яскраві кольори (заповнена частина)
        lower_color = np.array([0, 50, 50])
        upper_color = np.array([180, 255, 255])
        mask = cv2.inRange(hsv, lower_color, upper_color)

        # Підраховуємо заповнення
        filled_pixels = np.sum(mask > 0)
        total_pixels = mask.size

        return (filled_pixels / total_pixels) * 100 if total_pixels > 0 else 0.0


# ==================== PUBLIC API ====================

# Глобальний екземпляр для зручного використання
_ui_detector = None

def get_ui_detector() -> UIDetector:
    """Отримати глобальний екземпляр UIDetector."""
    global _ui_detector
    if _ui_detector is None:
        _ui_detector = UIDetector()
    return _ui_detector


# Функції для реєстрації в TOOL_POLICIES

def find_button_by_image(template_path: str, confidence: float = 0.8,
                         region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    """Знайти кнопку за зображенням-шаблоном."""
    result = get_ui_detector().find_button_by_image(template_path, confidence, region)
    if result is None:
        return {"success": False, "message": "Button not found"}
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}
    return {"success": True, "button": result}


def find_icon(icon_name_or_path: str, confidence: float = 0.8,
              region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    """Знайти іконку на екрані."""
    result = get_ui_detector().find_icon(icon_name_or_path, confidence, region)
    if result is None:
        return {"success": False, "message": "Icon not found"}
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}
    return {"success": True, "icon": result}


def find_checkbox(region: Optional[Tuple[int, int, int, int]] = None,
                  checked: Optional[bool] = None) -> Dict[str, Any]:
    """Знайти чекбокси на екрані."""
    result = get_ui_detector().find_checkbox(region, checked)
    if not result:
        return {"success": False, "message": "No checkboxes found"}
    if len(result) == 1 and "error" in result[0]:
        return {"success": False, "error": result[0]["error"]}
    return {"success": True, "checkboxes": result, "count": len(result)}


def find_input_field(region: Optional[Tuple[int, int, int, int]] = None,
                     min_width: int = 80, min_height: int = 20) -> Dict[str, Any]:
    """Знайти поля вводу на екрані."""
    result = get_ui_detector().find_input_field(region, min_width, min_height)
    if not result:
        return {"success": False, "message": "No input fields found"}
    if len(result) == 1 and "error" in result[0]:
        return {"success": False, "error": result[0]["error"]}
    return {"success": True, "fields": result, "count": len(result)}


def find_progress_bar(region: Optional[Tuple[int, int, int, int]] = None,
                      min_width: int = 60) -> Dict[str, Any]:
    """Знайти прогрес-бар на екрані."""
    result = get_ui_detector().find_progress_bar(region, min_width)
    if result is None:
        return {"success": False, "message": "Progress bar not found"}
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}
    return {"success": True, "progress_bar": result}


def find_button_by_text(text: str, region: Optional[Tuple[int, int, int, int]] = None,
                        confidence: float = 0.7) -> Dict[str, Any]:
    """Знайти кнопку за текстом (OCR + CV)."""
    result = get_ui_detector().find_button_by_text(text, region, confidence)
    if result is None:
        return {"success": False, "message": f"Button with text '{text}' not found"}
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}
    return {"success": True, "button": result}


def find_label(text: str, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    """Знайти мітку з вказаним текстом."""
    result = get_ui_detector().find_label(text, region)
    if result is None:
        return {"success": False, "message": f"Label '{text}' not found"}
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}
    return {"success": True, "label": result}


def find_input_near_label(label_text: str, region: Optional[Tuple[int, int, int, int]] = None,
                           max_distance: int = 100) -> Dict[str, Any]:
    """Знайти поле вводу поруч з міткою."""
    result = get_ui_detector().find_input_near_label(label_text, region, max_distance)
    if result is None:
        return {"success": False, "message": f"No input field found near label '{label_text}'"}
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}
    return {"success": True, "field": result}


def is_button_enabled(x: int, y: int, width: int, height: int) -> Dict[str, Any]:
    """Перевірити чи кнопка активна."""
    result = get_ui_detector().is_button_enabled(x, y, width, height)
    return {"success": True, "enabled": result}


def is_checkbox_checked(x: int, y: int, width: int = 16, height: int = 16) -> Dict[str, Any]:
    """Перевірити стан чекбокса."""
    result = get_ui_detector().is_checkbox_checked(x, y, width, height)
    return {"success": True, "checked": result}


def get_button_state(x: int, y: int, width: int = 80, height: int = 25) -> Dict[str, Any]:
    """Отримати візуальний стан кнопки."""
    result = get_ui_detector().get_button_state(x, y, width, height)
    return {"success": True, "state": result}
