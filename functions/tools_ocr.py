"""
OCR — Розпізнавання тексту на екрані.

GUI Automation Phase 3 — "очі що читають" агента.
Використовує pytesseract як основний движун, easyocr як fallback.
"""

import os
import io
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

# Спробуємо імпортувати OCR бібліотеки
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
    # Налаштування шляху до tesseract (якщо в PATH — працює автоматично)
    # Якщо треба вказати шлях:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# OpenCV для попередньої обробки
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Імпортуємо screen capture для скріншотів
from .tools_screen_capture import ScreenCapture


class OCREngine:
    """Движун OCR для розпізнавання тексту на екрані."""

    def __init__(self, engine: str = "auto", languages: List[str] = None):
        """
        Args:
            engine: "pytesseract", "easyocr", або "auto" (вибрати найкращий)
            languages: Список мов (наприклад, ["ukr", "eng"] для pytesseract)
        """
        self.engine_type = engine
        self.languages = languages or ["ukr", "eng"]
        self.available_engines = []

        # Підготовка движків
        self._init_engines()

    def _init_engines(self):
        """Ініціалізувати доступні OCR движки."""
        # Перевірка pytesseract
        if PYTESSERACT_AVAILABLE:
            try:
                # Тестуємо чи працює
                test_img = Image.new('RGB', (100, 30), color='white')
                pytesseract.image_to_string(test_img)
                self.available_engines.append("pytesseract")
                print(f"✅ PyTesseract доступний (мови: {', '.join(self.languages)})")
            except Exception as e:
                print(f"⚠️ PyTesseract встановлений але не працює: {e}")

        # Перевірка easyocr (ініціалізуємо ліниво — довге завантаження)
        if EASYOCR_AVAILABLE:
            self.available_engines.append("easyocr")
            print(f"✅ EasyOCR доступний (мови: {', '.join(self.languages)})")
            self._easyocr_reader = None  # Лінива ініціалізація

        # Вибір движка
        if self.engine_type == "auto":
            if "pytesseract" in self.available_engines:
                self.engine_type = "pytesseract"
            elif "easyocr" in self.available_engines:
                self.engine_type = "easyocr"
            else:
                raise RuntimeError("Жоден OCR движок не доступний. Встановіть pytesseract або easyocr.")

        print(f"🔧 Використовуємо движок: {self.engine_type}")

    def _get_easyocr_reader(self):
        """Лінива ініціалізація EasyOCR (довге завантаження моделей)."""
        if self._easyocr_reader is None:
            print(f"⏳ Завантаження EasyOCR моделей...")
            start_time = time.time()
            self._easyocr_reader = easyocr.Reader(
                self.languages,
                gpu=torch.cuda.is_available() if 'torch' in dir() else False
            )
            print(f"✅ EasyOCR готовий ({time.time() - start_time:.1f}с)")
        return self._easyocr_reader

    def _preprocess_image(self, img: Image.Image, enhance: bool = True) -> Image.Image:
        """Попередня обробка зображення для кращого OCR."""
        if not enhance:
            return img

        # Конвертуємо в RGB якщо треба
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Збільшення розміру (корисно для малих UI елементів)
        width, height = img.size
        if width < 400 or height < 100:
            scale = max(2, int(400 / min(width, height)))
            img = img.resize((width * scale, height * scale), Image.LANCZOS)

        # Покращення контрасту
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

        # Покращення різкості
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.5)

        return img

    def recognize(self, image: Union[Image.Image, str, np.ndarray],
                  engine: Optional[str] = None) -> Dict[str, Any]:
        """
        Розпізнати текст на зображенні.

        Args:
            image: PIL Image, шлях до файлу, або numpy array
            engine: Движок (якщо None — використовує self.engine_type)

        Returns:
            {"text": str, "confidence": float, "engine": str, "boxes": [...]}
        """
        engine = engine or self.engine_type

        # Конвертуємо в PIL Image
        if isinstance(image, str):
            img = Image.open(image)
        elif isinstance(image, np.ndarray):
            img = Image.fromarray(image)
        elif isinstance(image, Image.Image):
            img = image
        else:
            return {"success": False, "error": f"Непідтримуваний тип зображення: {type(image)}"}

        # Попередня обробка
        img = self._preprocess_image(img)

        # Розпізнавання
        if engine == "pytesseract" and PYTESSERACT_AVAILABLE:
            return self._recognize_pytesseract(img)
        elif engine == "easyocr" and EASYOCR_AVAILABLE:
            return self._recognize_easyocr(img)
        else:
            return {"success": False, "error": f"Движок {engine} не доступний"}

    def _recognize_pytesseract(self, img: Image.Image) -> Dict[str, Any]:
        """Розпізнання через PyTesseract."""
        try:
            lang_str = "+".join(self.languages)

            # Отримуємо дані з координатами
            data = pytesseract.image_to_data(img, lang=lang_str, output_type=pytesseract.Output.DICT)

            # Збираємо текст та bbox-и
            boxes = []
            full_text_parts = []
            total_confidence = 0
            word_count = 0

            for i, text in enumerate(data['text']):
                if text.strip():
                    conf = int(data['conf'][i])
                    if conf > 0:  # Ігноруємо невпевнені слова
                        full_text_parts.append(text)
                        total_confidence += conf
                        word_count += 1

                        boxes.append({
                            "text": text,
                            "confidence": conf / 100,
                            "x": data['left'][i],
                            "y": data['top'][i],
                            "width": data['width'][i],
                            "height": data['height'][i]
                        })

            full_text = " ".join(full_text_parts)
            avg_confidence = (total_confidence / word_count / 100) if word_count > 0 else 0

            return {
                "success": True,
                "text": full_text,
                "confidence": round(avg_confidence, 3),
                "engine": "pytesseract",
                "boxes": boxes,
                "word_count": word_count
            }

        except Exception as e:
            return {"success": False, "error": str(e), "engine": "pytesseract"}

    def _recognize_easyocr(self, img: Image.Image) -> Dict[str, Any]:
        """Розпізнання через EasyOCR."""
        try:
            reader = self._get_easyocr_reader()

            # Конвертуємо PIL в numpy array
            img_array = np.array(img)

            # Розпізнавання
            results = reader.readtext(img_array)

            # Парсинг результатів
            boxes = []
            full_text_parts = []
            total_confidence = 0

            for (bbox, text, conf) in results:
                full_text_parts.append(text)
                total_confidence += conf

                # bbox: [(x1,y1), (x2,y2), (x3,y3), (x4,y4)] — кути
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]

                boxes.append({
                    "text": text,
                    "confidence": round(conf, 3),
                    "x": int(min(x_coords)),
                    "y": int(min(y_coords)),
                    "width": int(max(x_coords) - min(x_coords)),
                    "height": int(max(y_coords) - min(y_coords)),
                    "bbox": bbox
                })

            full_text = " ".join(full_text_parts)
            avg_confidence = total_confidence / len(results) if results else 0

            return {
                "success": True,
                "text": full_text,
                "confidence": round(avg_confidence, 3),
                "engine": "easyocr",
                "boxes": boxes,
                "word_count": len(results)
            }

        except Exception as e:
            return {"success": False, "error": str(e), "engine": "easyocr"}

    def recognize_with_fallback(self, image: Union[Image.Image, str, np.ndarray]) -> Dict[str, Any]:
        """Розпізнання з fallback на інший движок при невдачі."""
        # Спробуємо основний движок
        primary_engine = self.engine_type
        result = self.recognize(image, engine=primary_engine)

        if result.get("success") and result.get("confidence", 0) > 0.5:
            return result

        # Fallback на інший движок
        fallback_engine = "easyocr" if primary_engine == "pytesseract" else "pytesseract"
        if fallback_engine in self.available_engines:
            print(f"⚠️ {primary_engine} низька впевненість, пробуємо {fallback_engine}...")
            fallback_result = self.recognize(image, engine=fallback_engine)

            if fallback_result.get("success") and fallback_result.get("confidence", 0) > result.get("confidence", 0):
                fallback_result["fallback_from"] = primary_engine
                return fallback_result

        return result


# ==================== Інтеграція з Screen Capture ====================

class ScreenOCR:
    """OCR для екрану — комбінує захоплення та розпізнавання."""

    def __init__(self, engine: str = "auto", languages: List[str] = None):
        self.capture = ScreenCapture()
        self.ocr = OCREngine(engine=engine, languages=languages)

    # --- Базові методи OCR ---

    def ocr_screen(self, save_screenshot: Optional[str] = None) -> Dict[str, Any]:
        """Розпізнати текст на всьому екрані."""
        # Захоплюємо екран
        result = self.capture.take_screenshot(save_path=save_screenshot)
        if not result.get("success"):
            return result

        # Розпізнаємо (треба отримати img з result, але take_screenshot не повертає img)
        # Тому зробимо capture через mss напряму
        try:
            import mss
            with mss.mss() as sct:
                screenshot = sct.grab(sct.monitors[0])
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                return self.ocr.recognize_with_fallback(img)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ocr_region(self, x: int, y: int, width: int, height: int,
                   save_screenshot: Optional[str] = None) -> Dict[str, Any]:
        """Розпізнати текст в області екрану."""
        try:
            # Захоплюємо область
            result = self.capture.capture_region(x, y, width, height, save_path=save_screenshot)
            if not result.get("success"):
                return result

            # Захоплюємо знову для OCR (потрібен img)
            import mss
            with mss.mss() as sct:
                monitor = {"left": x, "top": y, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                return self.ocr.recognize_with_fallback(img)

        except Exception as e:
            return {"success": False, "error": str(e)}

    def ocr_window(self, hwnd: int, save_screenshot: Optional[str] = None) -> Dict[str, Any]:
        """Розпізнати текст у вікні."""
        try:
            result = self.capture.capture_window(hwnd, save_path=save_screenshot)
            if not result.get("success"):
                return result

            # Для вікна теж треба зробити захоплення
            img = self._capture_window_image(hwnd)
            if img:
                return self.ocr.recognize_with_fallback(img)
            else:
                return {"success": False, "error": "Не вдалося захопити зображення вікна"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def ocr_image(self, image_path: str) -> Dict[str, Any]:
        """Розпізнати текст на зображенні з файлу."""
        if not os.path.exists(image_path):
            return {"success": False, "error": f"Файл не знайдено: {image_path}"}

        try:
            img = Image.open(image_path)
            return self.ocr.recognize_with_fallback(img)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _capture_window_image(self, hwnd: int) -> Optional[Image.Image]:
        """Допоміжний метод для захоплення вікна в PIL Image."""
        try:
            import win32gui
            import win32ui
            import win32con
            import ctypes

            # Отримуємо розміри вікна
            rect = win32gui.GetWindowRect(hwnd)
            x, y, right, bottom = rect
            width = right - x
            height = bottom - y

            # Захоплення через win32
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            # Очищення
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)

            return img

        except Exception as e:
            print(f"❌ Помилка захоплення вікна: {e}")
            return None

    # --- Пошук тексту ---

    def find_text_on_screen(self, search_text: str, case_sensitive: bool = False,
                          confidence_threshold: float = 0.7) -> Dict[str, Any]:
        """
        Знайти текст на екрані.

        Returns:
            {"found": True, "x": int, "y": int, "text": str, "confidence": float}
            або {"found": False}
        """
        # Розпізнаємо весь екран
        result = self.ocr_screen()

        if not result.get("success"):
            return {"found": False, "error": result.get("error")}

        boxes = result.get("boxes", [])
        search_lower = search_text if case_sensitive else search_text.lower()

        matches = []
        for box in boxes:
            text = box.get("text", "")
            text_lower = text if case_sensitive else text.lower()

            if search_lower in text_lower:
                matches.append({
                    "found": True,
                    "x": box["x"],
                    "y": box["y"],
                    "width": box["width"],
                    "height": box["height"],
                    "text": text,
                    "confidence": box.get("confidence", 0),
                    "match_ratio": len(search_text) / len(text) if text else 0
                })

        if matches:
            # Повертаємо найкращий матч (найбільша впевненість)
            best = max(matches, key=lambda m: m["confidence"])
            return best

        return {"found": False, "searched_for": search_text}

    def find_all_text_on_screen(self, search_text: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """Знайти всі входження тексту на екрані."""
        result = self.ocr_screen()

        if not result.get("success"):
            return []

        boxes = result.get("boxes", [])
        search_lower = search_text if case_sensitive else search_text.lower()

        matches = []
        for box in boxes:
            text = box.get("text", "")
            text_lower = text if case_sensitive else text.lower()

            if search_lower in text_lower:
                matches.append({
                    "x": box["x"],
                    "y": box["y"],
                    "width": box["width"],
                    "height": box["height"],
                    "text": text,
                    "confidence": box.get("confidence", 0)
                })

        return matches

    def click_text(self, search_text: str, offset_x: int = 0, offset_y: int = 0,
                   case_sensitive: bool = False) -> Dict[str, Any]:
        """Знайти текст і клікнути по ньому."""
        result = self.find_text_on_screen(search_text, case_sensitive)

        if not result.get("found"):
            return {"success": False, "error": f"Текст '{search_text}' не знайдено"}

        # Імпортуємо mouse_keyboard для кліку
        from .tools_mouse_keyboard import mouse_click

        x = result["x"] + result["width"] // 2 + offset_x
        y = result["y"] + result["height"] // 2 + offset_y

        click_result = mouse_click(x, y)

        return {
            "success": click_result.get("success", False),
            "clicked_at": {"x": x, "y": y},
            "found_text": result["text"],
            "confidence": result["confidence"]
        }

    def wait_for_text(self, search_text: str, timeout: float = 10.0,
                     interval: float = 0.5, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """Очікувати появи тексту на екрані."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if region:
                x, y, w, h = region
                result = self.ocr_region(x, y, w, h)
            else:
                result = self.ocr_screen()

            if not result.get("success"):
                time.sleep(interval)
                continue

            # Перевіряємо чи є текст
            full_text = result.get("text", "").lower()
            if search_text.lower() in full_text:
                return {
                    "found": True,
                    "waited": time.time() - start_time,
                    "full_text": result.get("text", "")
                }

            time.sleep(interval)

        return {"found": False, "timeout": timeout}

    def ocr_to_string(self, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """Просте розпізнавання — повертає тільки текст (для LLM)."""
        if region:
            x, y, w, h = region
            result = self.ocr_region(x, y, w, h)
        else:
            result = self.ocr_screen()

        if result.get("success"):
            return result.get("text", "")
        return ""


# ==================== Функції для інтеграції в систему ====================

# Глобальний екземпляр
_screen_ocr = None


def _get_screen_ocr() -> ScreenOCR:
    """Отримати глобальний екземпляр ScreenOCR (lazy initialization)."""
    global _screen_ocr
    if _screen_ocr is None:
        _screen_ocr = ScreenOCR(engine="auto", languages=["ukr", "eng"])
    return _screen_ocr


def ocr_screen(save_screenshot: Optional[str] = None) -> Dict[str, Any]:
    """Розпізнати текст на всьому екрані."""
    return _get_screen_ocr().ocr_screen(save_screenshot)


def ocr_region(x: int, y: int, width: int, height: int,
              save_screenshot: Optional[str] = None) -> Dict[str, Any]:
    """Розпізнати текст в області."""
    return _get_screen_ocr().ocr_region(x, y, width, height, save_screenshot)


def ocr_window(hwnd: int, save_screenshot: Optional[str] = None) -> Dict[str, Any]:
    """Розпізнати текст у вікні."""
    return _get_screen_ocr().ocr_window(hwnd, save_screenshot)


def ocr_image(image_path: str) -> Dict[str, Any]:
    """Розпізнати текст на зображенні."""
    return _get_screen_ocr().ocr_image(image_path)


def find_text_on_screen(search_text: str, case_sensitive: bool = False) -> Dict[str, Any]:
    """Знайти текст на екрані."""
    return _get_screen_ocr().find_text_on_screen(search_text, case_sensitive)


def find_all_text_on_screen(search_text: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
    """Знайти всі входження тексту."""
    return _get_screen_ocr().find_all_text_on_screen(search_text, case_sensitive)


def click_text(search_text: str, offset_x: int = 0, offset_y: int = 0) -> Dict[str, Any]:
    """Знайти текст і клікнути по ньому."""
    return _get_screen_ocr().click_text(search_text, offset_x, offset_y)


def wait_for_text(search_text: str, timeout: float = 10.0,
                 region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    """Очікувати появи тексту."""
    return _get_screen_ocr().wait_for_text(search_text, timeout, region=region)


def ocr_to_string(region: Optional[Tuple[int, int, int, int]] = None) -> str:
    """Просте розпізнавання — повертає тільки текст."""
    return _get_screen_ocr().ocr_to_string(region)
