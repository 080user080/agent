"""
Тести для модуля tools_screen_capture.py

GUI Automation Phase 2 — Скріншоти + аудит дій.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestScreenCapture:
    """Тести для функцій скріншотів."""

    @patch('functions.tools.tools_screen_capture.mss')
    def test_capture_screen_basic(self, mock_mss):
        """Тест базового захоплення екрану."""
        from functions.tools.tools_screen_capture import capture_screen

        # Mock mss screenshot
        mock_sct = MagicMock()
        mock_sct.shot.return_value = MagicMock(rgb=b'fake_image_data')
        mock_mss.mss.return_value = mock_sct

        result = capture_screen()

        assert result is not None
        mock_sct.shot.assert_called_once()

    @patch('functions.tools.tools_screen_capture.mss')
    def test_capture_region(self, mock_mss):
        """Тест захоплення регіону екрану."""
        from functions.tools.tools_screen_capture import capture_region

        # Mock mss screenshot
        mock_sct = MagicMock()
        mock_sct.shot.return_value = MagicMock(rgb=b'fake_image_data')
        mock_mss.mss.return_value = mock_sct

        result = capture_region(100, 100, 200, 200)

        assert result is not None
        mock_sct.shot.assert_called_once()

    @patch('functions.tools.tools_screen_capture.mss')
    def test_capture_screen_fallback(self, mock_mss):
        """Тест fallback на PIL коли mss недоступний."""
        from functions.tools.tools_screen_capture import capture_screen

        # Mock mss недоступний
        mock_mss.mss.side_effect = ImportError()

        with patch('functions.tools.tools_screen_capture.ImageGrab'):
            result = capture_screen()
            # Повинно використати fallback або повернути None

    def test_save_screenshot(self):
        """Тест збереження скріншоту."""
        from functions.tools.tools_screen_capture import save_screenshot
        from PIL import Image

        # Створити фейкове зображення
        fake_image = Image.new('RGB', (100, 100), color='red')

        with patch('functions.tools.tools_screen_capture.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_file = MagicMock()
            mock_path.return_value.__truediv__.return_value = mock_file

            save_screenshot(fake_image, "test.png")
            mock_file.save.assert_called_once()


class TestScreenCaptureIntegration:
    """Інтеграційні тести для скріншотів."""

    @patch('functions.tools.tools_screen_capture.capture_screen')
    def test_screenshot_workflow(self, mock_capture):
        """Тест повного workflow скріншоту."""
        from functions.tools.tools_screen_capture import capture_screen, save_screenshot

        # Mock capture
        from PIL import Image
        fake_image = Image.new('RGB', (100, 100), color='blue')
        mock_capture.return_value = fake_image

        # Виконати workflow
        screenshot = capture_screen()
        assert screenshot is not None

        # Зберегти
        with patch('functions.tools.tools_screen_capture.Path'):
            save_screenshot(screenshot, "workflow_test.png")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
