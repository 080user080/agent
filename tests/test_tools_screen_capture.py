"""Тести для tools_screen_capture (Phase 1)."""
import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestScreenCapture:
    """Тести для ScreenCapture."""

    @patch("functions.tools.tools_screen_capture.MSS_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.mss.mss")
    def test_capture_screen_basic(self, mock_mss_class):
        """Базовий тест захоплення екрану."""
        mock_sct = MagicMock()
        mock_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        mock_sct.grab.return_value = MagicMock()
        mock_sct.grab.return_value.rgb = b"test_data"
        mock_sct.grab.return_value.size = (1920, 1080)
        mock_mss_class.return_value.__enter__.return_value = mock_sct

        from functions.tools.tools_screen_capture import ScreenCapture
        capture = ScreenCapture()
        img = capture.capture_screen()
        assert img is not None

    @patch("functions.tools.tools_screen_capture.MSS_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.mss.mss")
    def test_capture_region(self, mock_mss_class):
        """Тест захоплення регіону."""
        mock_sct = MagicMock()
        mock_sct.grab.return_value = MagicMock()
        mock_sct.grab.return_value.rgb = b"test_data"
        mock_sct.grab.return_value.size = (100, 100)
        mock_mss_class.return_value.__enter__.return_value = mock_sct

        from functions.tools.tools_screen_capture import ScreenCapture
        capture = ScreenCapture()
        img = capture.capture_screen(region=(0, 0, 100, 100))
        assert img is not None

    @patch("functions.tools.tools_screen_capture.MSS_AVAILABLE", False)
    def test_capture_screen_fallback(self):
        """Тест fallback захоплення."""
        from functions.tools.tools_screen_capture import ScreenCapture
        capture = ScreenCapture()
        img = capture.capture_screen()
        # Може бути None або зображення
        assert img is not None

    @patch("functions.tools.tools_screen_capture.MSS_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.mss.mss")
    def test_save_screenshot(self, mock_mss_class):
        """Тест збереження скріншоту."""
        mock_sct = MagicMock()
        mock_sct.grab.return_value = MagicMock()
        mock_sct.grab.return_value.rgb = b"test"
        mock_sct.grab.return_value.size = (10, 10)
        mock_mss_class.return_value.__enter__.return_value = mock_sct

        from functions.tools.tools_screen_capture import ScreenCapture, save_screenshot
        capture = ScreenCapture()
        result = capture.save_screenshot("test_screenshot.png")
        assert result is not None


class TestScreenCaptureIntegration:
    """Інтеграційні тести."""

    @patch("functions.tools.tools_screen_capture.MSS_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.mss.mss")
    def test_screenshot_workflow(self, mock_mss_class):
        """Повний workflow."""
        mock_sct = MagicMock()
        mock_sct.grab.return_value = MagicMock()
        mock_sct.grab.return_value.rgb = b"test"
        mock_sct.grab.return_value.size = (10, 10)
        mock_mss_class.return_value.__enter__.return_value = mock_sct

        from functions.tools.tools_screen_capture import ScreenCapture
        capture = ScreenCapture()
        img = capture.capture_screen()
        assert img is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])