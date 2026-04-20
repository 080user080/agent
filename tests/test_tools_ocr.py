"""
Тести для модуля tools_ocr.py

GUI Automation Phase 3 — OCR (розпізнавання тексту).
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
import numpy as np
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.tools_ocr import (
    OCREngine, ScreenOCR,
    ocr_screen, ocr_region, ocr_image,
    find_text_on_screen, click_text
)


class TestOCREngine:
    """Тести для класу OCREngine."""

    @pytest.fixture
    def mock_pil_image(self):
        """Фікстура для реального PIL Image (маленький білий 100x30).

        Використовуємо справжній Image, бо recognize() робить isinstance-перевірку
        на PIL.Image.Image, і MagicMock не проходить.
        """
        from PIL import Image
        return Image.new('RGB', (100, 30), color='white')

    @patch('functions.tools_ocr.PYTESSERACT_AVAILABLE', True)
    @patch('functions.tools_ocr.pytesseract')
    def test_init_pytesseract_available(self, mock_pytesseract):
        """Тест ініціалізації з доступним PyTesseract."""
        mock_pytesseract.image_to_string.return_value = "test"

        engine = OCREngine(engine="pytesseract", languages=["ukr", "eng"])

        assert "pytesseract" in engine.available_engines
        assert engine.engine_type == "pytesseract"

    @patch('functions.tools_ocr.PYTESSERACT_AVAILABLE', False)
    @patch('functions.tools_ocr.EASYOCR_AVAILABLE', True)
    def test_init_fallback_to_easyocr(self):
        """Тест fallback на EasyOCR коли PyTesseract недоступний."""
        engine = OCREngine(engine="auto", languages=["ukr"])

        assert engine.engine_type == "easyocr"
        assert "easyocr" in engine.available_engines

    @patch('functions.tools_ocr.PYTESSERACT_AVAILABLE', True)
    @patch('functions.tools_ocr.pytesseract')
    def test_recognize_pytesseract_success(self, mock_pytesseract, mock_pil_image):
        """Тест успішного розпізнавання через PyTesseract."""
        # Мокуємо дані pytesseract
        mock_pytesseract.image_to_data.return_value = {
            'text': ['Hello', 'World'],
            'conf': [90, 95],
            'left': [10, 50],
            'top': [10, 10],
            'width': [30, 40],
            'height': [20, 20]
        }
        mock_pytesseract.Output.DICT = 'dict'

        engine = OCREngine(engine="pytesseract")
        result = engine.recognize(mock_pil_image)

        assert result['success'] is True
        assert result['engine'] == 'pytesseract'
        assert 'text' in result
        assert 'boxes' in result

    @patch('functions.tools_ocr.PYTESSERACT_AVAILABLE', True)
    @patch('functions.tools_ocr.pytesseract')
    def test_recognize_pytesseract_empty(self, mock_pytesseract, mock_pil_image):
        """Тест розпізнавання порожнього зображення."""
        mock_pytesseract.image_to_data.return_value = {
            'text': [],
            'conf': [],
            'left': [],
            'top': [],
            'width': [],
            'height': []
        }
        mock_pytesseract.Output.DICT = 'dict'

        engine = OCREngine(engine="pytesseract")
        result = engine.recognize(mock_pil_image)

        assert result['success'] is True
        assert result['word_count'] == 0

    @patch('functions.tools_ocr.PYTESSERACT_AVAILABLE', True)
    @patch('functions.tools_ocr.pytesseract')
    def test_recognize_pytesseract_error(self, mock_pytesseract, mock_pil_image):
        """Тест обробки помилки PyTesseract."""
        mock_pytesseract.image_to_data.side_effect = Exception("Tesseract error")

        engine = OCREngine(engine="pytesseract")
        result = engine.recognize(mock_pil_image)

        assert result['success'] is False
        assert 'error' in result

    def test_preprocess_image_resize_small(self):
        """Тест збільшення малих зображень."""
        from PIL import Image

        engine = OCREngine(engine="pytesseract")
        small_img = Image.new('RGB', (100, 30), color='white')

        processed = engine._preprocess_image(small_img)

        # Маленьке зображення повинно збільшитися
        assert processed.size[0] >= 400

    def test_preprocess_image_enhance(self):
        """Тест покращення контрасту та різкості."""
        from PIL import Image

        engine = OCREngine(engine="pytesseract")
        img = Image.new('RGB', (500, 100), color='white')

        processed = engine._preprocess_image(img, enhance=True)

        assert processed is not None
        assert processed.mode == 'RGB'

    def test_preprocess_image_no_enhance(self):
        """Тест пропуску обробки."""
        from PIL import Image

        engine = OCREngine(engine="pytesseract")
        img = Image.new('RGB', (500, 100), color='white')

        processed = engine._preprocess_image(img, enhance=False)

        assert processed == img


class TestScreenOCR:
    """Тести для класу ScreenOCR."""

    @pytest.fixture
    def mock_screen_ocr(self):
        """Фікстура для ScreenOCR з замоканим захопленням."""
        with patch('functions.tools_ocr.ScreenCapture'):
            with patch('functions.tools_ocr.OCREngine'):
                ocr = ScreenOCR(engine="pytesseract")
                # Мокуємо метод захоплення
                ocr._capture_window_image = MagicMock(return_value=MagicMock())
                return ocr

    @patch('functions.tools_ocr.ScreenCapture')
    def test_ocr_image_file_not_found(self, mock_capture):
        """Тест ocr_image з неіснуючим файлом."""
        ocr = ScreenOCR(engine="pytesseract")
        result = ocr.ocr_image("/nonexistent/path.png")

        assert result['success'] is False
        assert 'не знайдено' in result['error'].lower() or 'not found' in result['error'].lower()

    @patch('functions.tools_ocr.ScreenCapture')
    @patch('builtins.open', mock_open(read_data=b'fake_image_data'))
    @patch('functions.tools_ocr.Image.open')
    @patch('functions.tools_ocr.OCREngine.recognize_with_fallback')
    def test_ocr_image_success(self, mock_recognize, mock_img_open, mock_capture):
        """Тест успішного розпізнавання файлу."""
        mock_recognize.return_value = {
            'success': True,
            'text': 'Test text',
            'confidence': 0.95
        }
        mock_img_open.return_value = MagicMock()

        # Мокуємо os.path.exists
        with patch('os.path.exists', return_value=True):
            ocr = ScreenOCR(engine="pytesseract")
            result = ocr.ocr_image("test.png")

        assert result['success'] is True

    def test_find_text_on_screen_no_matches(self, mock_screen_ocr):
        """Тест пошуку тексту без результатів."""
        mock_screen_ocr.ocr_screen = MagicMock(return_value={
            'success': True,
            'boxes': [
                {'text': 'Hello', 'x': 10, 'y': 10, 'width': 50, 'height': 20, 'confidence': 0.9}
            ]
        })

        result = mock_screen_ocr.find_text_on_screen("NonExistent")

        assert result['found'] is False

    def test_find_text_on_screen_with_matches(self, mock_screen_ocr):
        """Тест успішного пошуку тексту."""
        mock_screen_ocr.ocr_screen = MagicMock(return_value={
            'success': True,
            'boxes': [
                {'text': 'Click here', 'x': 100, 'y': 200, 'width': 80, 'height': 30, 'confidence': 0.95}
            ]
        })

        result = mock_screen_ocr.find_text_on_screen("Click")

        assert result['found'] is True
        assert result['x'] == 100
        assert result['y'] == 200
        assert result['confidence'] == 0.95

    def test_find_all_text_on_screen_multiple(self, mock_screen_ocr):
        """Тест пошуку всіх входжень тексту."""
        mock_screen_ocr.ocr_screen = MagicMock(return_value={
            'success': True,
            'boxes': [
                {'text': 'Save', 'x': 10, 'y': 10, 'width': 40, 'height': 20, 'confidence': 0.9},
                {'text': 'Save As', 'x': 100, 'y': 50, 'width': 60, 'height': 20, 'confidence': 0.85},
                {'text': 'Cancel', 'x': 200, 'y': 10, 'width': 50, 'height': 20, 'confidence': 0.9}
            ]
        })

        results = mock_screen_ocr.find_all_text_on_screen("Save")

        assert len(results) == 2
        assert all(r['text'] in ['Save', 'Save As'] for r in results)


class TestOCRIntegration:
    """Інтеграційні тести OCR функцій."""

    @patch('functions.tools_ocr._get_screen_ocr')
    def test_ocr_screen_integration(self, mock_get_ocr):
        """Тест інтеграції ocr_screen функції."""
        mock_ocr = MagicMock()
        mock_ocr.ocr_screen.return_value = {'success': True, 'text': 'Test'}
        mock_get_ocr.return_value = mock_ocr

        result = ocr_screen()

        assert result['success'] is True
        mock_ocr.ocr_screen.assert_called_once()

    @patch('functions.tools_ocr._get_screen_ocr')
    def test_ocr_region_integration(self, mock_get_ocr):
        """Тест інтеграції ocr_region функції."""
        mock_ocr = MagicMock()
        mock_ocr.ocr_region.return_value = {'success': True, 'text': 'Region text'}
        mock_get_ocr.return_value = mock_ocr

        result = ocr_region(100, 100, 200, 100)

        assert result['success'] is True
        mock_ocr.ocr_region.assert_called_once_with(100, 100, 200, 100, None)

    @patch('functions.tools_ocr._get_screen_ocr')
    def test_find_text_on_screen_integration(self, mock_get_ocr):
        """Тест інтеграції find_text_on_screen функції."""
        mock_ocr = MagicMock()
        mock_ocr.find_text_on_screen.return_value = {'found': True, 'x': 100, 'y': 200}
        mock_get_ocr.return_value = mock_ocr

        result = find_text_on_screen("Button")

        assert result['found'] is True
        mock_ocr.find_text_on_screen.assert_called_once_with("Button", False)


# ==================== Smoke тести (без зовнішніх залежностей) ====================

class TestOCRSmoke:
    """Smoke тести для швидкої перевірки OCR."""

    def test_engine_creation_no_external_deps(self):
        """Тест створення engine без зовнішніх залежностей."""
        with patch('functions.tools_ocr.PYTESSERACT_AVAILABLE', False):
            with patch('functions.tools_ocr.EASYOCR_AVAILABLE', False):
                # Має викликати RuntimeError
                try:
                    OCREngine(engine="auto")
                    assert False, "Мало бути RuntimeError"
                except RuntimeError as e:
                    assert "Жоден OCR движок" in str(e)

    def test_preprocess_preserves_image_mode(self):
        """Тест що препроцесинг зберігає режим RGB."""
        from PIL import Image

        engine = OCREngine(engine="pytesseract")

        # RGB
        img_rgb = Image.new('RGB', (100, 100), color='white')
        processed = engine._preprocess_image(img_rgb)
        assert processed.mode == 'RGB'

        # RGBA — повинен конвертувати в RGB
        img_rgba = Image.new('RGBA', (100, 100), color='white')
        processed = engine._preprocess_image(img_rgba)
        assert processed.mode == 'RGB'
