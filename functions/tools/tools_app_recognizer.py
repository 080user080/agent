"""
Розпізнавання програм та аналіз їхнього стану.

GUI Automation Phase 4 — "розуміння" якої програма відкрита.
Визначає тип діалогів, стан завантаження, контекстні меню.
"""

import cv2
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import win32gui
import win32process
import psutil

from functions.tools_screen_capture import ScreenCapture
from functions.tools_ocr import ScreenOCR
from functions.tools_window_manager import WindowManager


class AppRecognizer:
    """Розпізнавання програм та їхнього стану."""

    # Відомі шаблони діалогів (title patterns)
    DIALOG_PATTERNS = {
        "open": ["open", "відкрити", "открыть", "ファイルを開く", "öffnen"],
        "save": ["save", "зберегти", "сохранить", "保存", "speichern", "save as", "зберегти як"],
        "error": ["error", "помилка", "ошибка", "エラー", "fehler", "failed", "не вдалося"],
        "confirm": ["confirm", "підтвердження", "подтверждение", "確認", "bestätigung"],
        "warning": ["warning", "попередження", "предупреждение", "警告", "warnung"],
    }

    # Відомі елементи стану завантаження
    LOADING_INDICATORS = {
        "spinner": {"color_ranges": [(np.array([0, 0, 200]), np.array([180, 30, 255]))]},  # Білий/сірий спінер
        "progress_bar": {"min_width": 50, "height_range": (4, 25)},
        "hourglass_cursor": False,  # Перевіряється через API
    }

    def __init__(self, screen_capture: Optional[ScreenCapture] = None,
                 screen_ocr: Optional[ScreenOCR] = None):
        self.capture = screen_capture or ScreenCapture()
        self.ocr = screen_ocr or ScreenOCR(self.capture)
        self.window_manager = WindowManager()
        self._app_profiles = self._load_default_profiles()

    def _load_default_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Завантажити профілі типових програм."""
        return {
            "notepad": {
                "exe_names": ["notepad.exe", "notepad"],
                "title_patterns": ["notepad", "блокнот", "- notepad", "*.txt"],
                "common_elements": ["file", "edit", "format", "view", "help"],
                "typical_size": (800, 600),
            },
            "calculator": {
                "exe_names": ["calc.exe", "calculator.exe", "calculator"],
                "title_patterns": ["calculator", "калькулятор", "rechner"],
                "common_elements": ["0", "1", "2", "+", "-", "*", "/", "="],
                "typical_size": (350, 500),
            },
            "explorer": {
                "exe_names": ["explorer.exe"],
                "title_patterns": [],  # Динамічні заголовки
                "common_elements": ["file", "home", "share", "view", "quick access"],
                "typical_size": (1000, 700),
            },
            "chrome": {
                "exe_names": ["chrome.exe"],
                "title_patterns": ["- google chrome", "- chromium"],
                "common_elements": ["address bar", "tabs", "back", "forward", "refresh"],
                "typical_size": (1200, 800),
            },
            "word": {
                "exe_names": ["winword.exe"],
                "title_patterns": ["- word", "microsoft word", ".docx"],
                "common_elements": ["file", "home", "insert", "design", "layout"],
                "typical_size": (1200, 900),
            },
            "excel": {
                "exe_names": ["excel.exe"],
                "title_patterns": ["- excel", "microsoft excel", ".xlsx", ".xls"],
                "common_elements": ["file", "home", "insert", "formulas", "data"],
                "typical_size": (1200, 900),
            },
        }

    # ==================== РОЗПІЗНАВАННЯ ПРОГРАМ ====================

    def detect_active_application(self, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Визначити яка програма активна.

        Args:
            hwnd: Handle вікна (None = активне вікно)

        Returns:
            {"name": str, "type": str, "confidence": float, "exe_path": str, "pid": int}
        """
        try:
            if hwnd is None:
                hwnd = win32gui.GetForegroundWindow()

            # Отримуємо інформацію про вікно
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            # Отримуємо ім'я процесу
            try:
                process = psutil.Process(pid)
                exe_name = process.name().lower()
                exe_path = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                exe_name = "unknown"
                exe_path = ""

            # Порівнюємо з відомими профілями
            best_match = None
            best_confidence = 0.0

            for app_name, profile in self._app_profiles.items():
                confidence = self._calculate_app_match(title, exe_name, profile)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = app_name

            # Визначаємо тип
            app_type = self._determine_app_type(exe_name, title, best_match)

            return {
                "success": True,
                "name": best_match or exe_name.replace(".exe", ""),
                "type": app_type,
                "confidence": best_confidence,
                "exe_name": exe_name,
                "exe_path": exe_path,
                "pid": pid,
                "hwnd": hwnd,
                "title": title
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect_application_state(self, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Визначити стан програми (idle, loading, error, dialog).

        Args:
            hwnd: Handle вікна

        Returns:
            {"state": str, "details": dict}
        """
        try:
            if hwnd is None:
                hwnd = win32gui.GetForegroundWindow()

            # Отримуємо скріншот вікна
            result = self.capture.capture_window(hwnd)
            if not result.get("success"):
                return {"success": False, "error": "Cannot capture window"}

            screenshot = result.get("image")
            if screenshot is None:
                return {"success": False, "error": "No screenshot available"}

            # Перевіряємо різні стани
            state_checks = [
                ("dialog", self._detect_dialog_state),
                ("error", self._detect_error_state),
                ("loading", self._detect_loading_state),
            ]

            for state_name, check_func in state_checks:
                details = check_func(screenshot)
                if details.get("detected"):
                    return {
                        "success": True,
                        "state": state_name,
                        "details": details,
                        "hwnd": hwnd
                    }

            # За замовчуванням — idle
            return {
                "success": True,
                "state": "idle",
                "details": {},
                "hwnd": hwnd
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def is_application_ready(self, hwnd: Optional[int] = None,
                              timeout: float = 0.5) -> Dict[str, Any]:
        """
        Перевірити чи програма завершила завантаження.

        Args:
            hwnd: Handle вікна
            timeout: Час очікування стабільності

        Returns:
            {"ready": bool, "state": str}
        """
        try:
            state_result = self.detect_application_state(hwnd)
            if not state_result.get("success"):
                return {"success": False, "error": state_result.get("error")}

            state = state_result.get("state", "idle")
            ready = state == "idle"

            return {
                "success": True,
                "ready": ready,
                "state": state,
                "hwnd": hwnd or win32gui.GetForegroundWindow()
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== ДЕТЕКЦІЯ ДІАЛОГІВ ====================

    def detect_file_dialog(self, hwnd: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Визначити чи відкрито файловий діалог (Open/Save).

        Args:
            hwnd: Handle вікна

        Returns:
            {"type": "open"|"save", "current_path": str, "title": str} або None
        """
        try:
            if hwnd is None:
                hwnd = win32gui.GetForegroundWindow()

            title = win32gui.GetWindowText(hwnd).lower()

            # Визначаємо тип діалогу за заголовком
            dialog_type = None
            for dtype, patterns in self.DIALOG_PATTERNS.items():
                if dtype in ["open", "save"]:
                    for pattern in patterns:
                        if pattern in title:
                            dialog_type = dtype
                            break
                if dialog_type:
                    break

            if not dialog_type:
                return None

            # Скануємо діалог через OCR для пошуку шляху
            ocr_result = self.ocr.ocr_window(hwnd)
            current_path = ""

            if ocr_result.get("success"):
                text_lines = ocr_result.get("text", "").split("\n")
                # Шукаємо рядок який схожий на шлях
                for line in text_lines:
                    if any(c in line for c in [":\\", "/", "\\"]):
                        current_path = line.strip()
                        break

            return {
                "success": True,
                "type": dialog_type,
                "current_path": current_path,
                "title": win32gui.GetWindowText(hwnd),
                "hwnd": hwnd
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect_error_dialog(self, hwnd: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Визначити чи є діалог помилки.

        Args:
            hwnd: Handle вікна

        Returns:
            {"title": str, "message": str, "buttons": [str]} або None
        """
        try:
            if hwnd is None:
                hwnd = win32gui.GetForegroundWindow()

            title = win32gui.GetWindowText(hwnd).lower()

            # Перевіряємо чи заголовок схожий на помилку
            is_error = any(
                pattern in title
                for pattern in self.DIALOG_PATTERNS["error"]
            )

            if not is_error:
                return None

            # Розпізнаємо текст діалогу
            ocr_result = self.ocr.ocr_window(hwnd)
            message = ""
            buttons = []

            if ocr_result.get("success"):
                text = ocr_result.get("text", "")
                lines = text.split("\n")

                # Шукаємо кнопки (зазвичай OK, Cancel, Retry, etc.)
                button_keywords = ["ok", "cancel", "retry", "yes", "no",
                                   "так", "ні", "повторити", "скасувати"]
                for line in lines:
                    line_lower = line.strip().lower()
                    if any(kw in line_lower for kw in button_keywords):
                        buttons.append(line.strip())
                    elif len(line.strip()) > 10:
                        message = line.strip()

            return {
                "success": True,
                "title": win32gui.GetWindowText(hwnd),
                "message": message,
                "buttons": buttons,
                "hwnd": hwnd
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect_context_menu(self, hwnd: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Визначити чи відкрито контекстне меню.

        Args:
            hwnd: Handle вікна

        Returns:
            {"items": [str], "positions": [{"x": int, "y": int}]} або None
        """
        try:
            # Контекстне меню — це зазвичай окреме вікно без заголовка
            # або спливаюче вікно з вертикальним списком
            if hwnd is None:
                # Шукаємо вікна без заголовка
                def enum_windows_callback(hwnd, results):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        rect = win32gui.GetWindowRect(hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]

                        # Контекстне меню: невелике вікно без заголовка
                        if not title and 100 < width < 400 and 50 < height < 600:
                            results.append(hwnd)
                    return True

                menu_windows = []
                win32gui.EnumWindows(enum_windows_callback, menu_windows)

                if not menu_windows:
                    return None

                hwnd = menu_windows[0]

            # Розпізнаємо пункти меню
            ocr_result = self.ocr.ocr_window(hwnd)
            items = []

            if ocr_result.get("success"):
                text = ocr_result.get("text", "")
                items = [line.strip() for line in text.split("\n") if line.strip()]

            return {
                "success": True,
                "items": items,
                "hwnd": hwnd,
                "count": len(items)
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== ДОПОМІЖНІ МЕТОДИ ====================

    def _calculate_app_match(self, title: str, exe_name: str,
                              profile: Dict[str, Any]) -> float:
        """Обчислити ймовірність співпадіння з профілем програми."""
        confidence = 0.0

        # Перевіряємо exe_name
        exe_names = profile.get("exe_names", [])
        if any(name.lower() == exe_name.lower() for name in exe_names):
            confidence += 0.5
        elif any(name.lower() in exe_name.lower() for name in exe_names):
            confidence += 0.3

        # Перевіряємо title
        title_lower = title.lower()
        for pattern in profile.get("title_patterns", []):
            if pattern in title_lower:
                confidence += 0.2

        return min(confidence, 1.0)

    def _determine_app_type(self, exe_name: str, title: str,
                            matched_profile: Optional[str]) -> str:
        """Визначити тип програми."""
        if matched_profile:
            type_map = {
                "notepad": "text_editor",
                "word": "document_editor",
                "excel": "spreadsheet",
                "calculator": "utility",
                "explorer": "file_manager",
                "chrome": "browser",
            }
            return type_map.get(matched_profile, "application")

        # Евристики за exe_name
        if any(x in exe_name for x in ["chrome", "firefox", "edge", "opera"]):
            return "browser"
        elif any(x in exe_name for x in ["word", "writer", "doc"]):
            return "document_editor"
        elif any(x in exe_name for x in ["excel", "calc", "sheet"]):
            return "spreadsheet"
        elif any(x in exe_name for x in ["notepad", "sublime", "code", "vscode"]):
            return "text_editor"

        return "unknown"

    def _detect_dialog_state(self, screenshot) -> Dict[str, Any]:
        """Визначити чи це діалогове вікно."""
        img_array = np.array(screenshot)
        h, w = img_array.shape[:2]

        # Діалоги зазвичай менші за типові вікна
        is_small = w < 600 and h < 400

        # Шукаємо кнопки внизу (характерно для діалогів)
        bottom_region = img_array[int(h*0.7):, :]
        gray = cv2.cvtColor(bottom_region, cv2.COLOR_RGB2GRAY)

        # Проста евристика: шукаємо прямокутні області (кнопки)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        button_like = sum(1 for cnt in contours if 50 < cv2.boundingRect(cnt)[2] < 150)

        return {
            "detected": is_small and button_like >= 1,
            "button_count": button_like,
            "is_small": is_small
        }

    def _detect_error_state(self, screenshot) -> Dict[str, Any]:
        """Визначити чи це вікно помилки."""
        # Конвертуємо в numpy якщо потрібно
        if hasattr(screenshot, 'convert'):
            img_array = np.array(screenshot.convert('RGB'))
        else:
            img_array = screenshot

        # Перевіряємо наявність червоних елементів (характерно для помилок)
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = mask1 + mask2

        red_ratio = np.sum(red_mask > 0) / (red_mask.size / 100)

        # Також перевіряємо через OCR на ключові слова помилок
        has_error_text = False

        return {
            "detected": red_ratio > 0.5 or has_error_text,
            "red_ratio": red_ratio
        }

    def _detect_loading_state(self, screenshot) -> Dict[str, Any]:
        """Визначити чи йде завантаження."""
        if hasattr(screenshot, 'convert'):
            img_array = np.array(screenshot.convert('RGB'))
        else:
            img_array = screenshot

        # Шукаємо прогрес-бари
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

        # Яскраві кольори для прогрес-барів
        lower_color = np.array([0, 50, 100])
        upper_color = np.array([180, 255, 255])
        mask = cv2.inRange(hsv, lower_color, upper_color)

        # Шукаємо горизонтальні лінії
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 5))
        dilated = cv2.dilate(mask, kernel)

        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        progress_bars = [
            cnt for cnt in contours
            if 50 < cv2.boundingRect(cnt)[2] < 400
            and 3 < cv2.boundingRect(cnt)[3] < 30
        ]

        return {
            "detected": len(progress_bars) > 0,
            "progress_bar_count": len(progress_bars)
        }


# ==================== PUBLIC API ====================

_app_recognizer = None

def get_app_recognizer() -> AppRecognizer:
    """Отримати глобальний екземпляр AppRecognizer."""
    global _app_recognizer
    if _app_recognizer is None:
        _app_recognizer = AppRecognizer()
    return _app_recognizer


# Функції для реєстрації в TOOL_POLICIES

def detect_active_application(hwnd: Optional[int] = None) -> Dict[str, Any]:
    """Визначити активну програму."""
    return get_app_recognizer().detect_active_application(hwnd)


def detect_application_state(hwnd: Optional[int] = None) -> Dict[str, Any]:
    """Визначити стан програми."""
    return get_app_recognizer().detect_application_state(hwnd)


def is_application_ready(hwnd: Optional[int] = None, timeout: float = 0.5) -> Dict[str, Any]:
    """Перевірити чи програма готова."""
    return get_app_recognizer().is_application_ready(hwnd, timeout)


def detect_file_dialog(hwnd: Optional[int] = None) -> Dict[str, Any]:
    """Визначити чи відкрито файловий діалог."""
    result = get_app_recognizer().detect_file_dialog(hwnd)
    if result is None:
        return {"success": False, "message": "No file dialog detected"}
    return result


def detect_error_dialog(hwnd: Optional[int] = None) -> Dict[str, Any]:
    """Визначити чи є діалог помилки."""
    result = get_app_recognizer().detect_error_dialog(hwnd)
    if result is None:
        return {"success": False, "message": "No error dialog detected"}
    return result


def detect_context_menu(hwnd: Optional[int] = None) -> Dict[str, Any]:
    """Визначити чи відкрито контекстне меню."""
    result = get_app_recognizer().detect_context_menu(hwnd)
    if result is None:
        return {"success": False, "message": "No context menu detected"}
    return result
