"""Тести для DPI/мультимонітор підтримки — Phase V5."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from functions.tools.tools_screen_capture import get_dpi_scaling, get_dpi_scaling_global, ScreenCapture
from functions.tools.tools_mouse_keyboard import _apply_dpi_correction


class TestDPIScaling:
    """Тести для DPI scaling detection."""

    def test_get_dpi_scaling_no_ctypes(self):
        """DPI detection коли ctypes недоступний."""
        with patch("functions.tools.tools_screen_capture.DPI_AVAILABLE", False):
            scaling = get_dpi_scaling()
            assert scaling == 1.0

    @patch("functions.tools.tools_screen_capture.DPI_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.ctypes")
    def test_get_dpi_scaling_success(self, mock_ctypes):
        """Успішне отримання DPI scaling."""
        # Mock Windows API calls
        mock_user32 = MagicMock()
        mock_gdi32 = MagicMock()
        mock_ctypes.windll.user32 = mock_user32
        mock_ctypes.windll.gdi32 = mock_gdi32

        mock_user32.GetDesktopWindow.return_value = 123
        mock_user32.GetDC.return_value = 456
        mock_gdi32.GetDeviceCaps.return_value = 144  # 150% DPI
        mock_user32.ReleaseDC.return_value = None

        scaling = get_dpi_scaling()
        assert scaling == 1.5  # 144 / 96

    @patch("functions.tools.tools_screen_capture.DPI_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.ctypes")
    def test_get_dpi_scaling_error(self, mock_ctypes):
        """Помилка при отриманні DPI."""
        mock_ctypes.windll.user32.GetDesktopWindow.side_effect = Exception("Error")

        scaling = get_dpi_scaling()
        assert scaling == 1.0  # Fallback to 1.0 on error

    def test_get_dpi_scaling_global(self):
        """Глобальна функція для DPI scaling."""
        with patch("functions.tools.tools_screen_capture.get_dpi_scaling", return_value=1.5):
            scaling = get_dpi_scaling_global()
            assert scaling == 1.5


class TestDPICorrection:
    """Тести для DPI correction в координатах."""

    def test_apply_dpi_correction_no_scaling(self):
        """DPI correction коли scaling = 1.0."""
        with patch("functions.tools.tools_screen_capture.get_dpi_scaling", return_value=1.0):
            x, y = _apply_dpi_correction(100, 200)
            assert x == 100
            assert y == 200

    def test_apply_dpi_correction_150_percent(self):
        """DPI correction коли scaling = 1.5."""
        with patch("functions.tools.tools_screen_capture.get_dpi_scaling", return_value=1.5):
            x, y = _apply_dpi_correction(150, 300)
            assert x == 100  # 150 / 1.5
            assert y == 200  # 300 / 1.5

    def test_apply_dpi_correction_200_percent(self):
        """DPI correction коли scaling = 2.0."""
        with patch("functions.tools.tools_screen_capture.get_dpi_scaling", return_value=2.0):
            x, y = _apply_dpi_correction(400, 600)
            assert x == 200  # 400 / 2.0
            assert y == 300  # 600 / 2.0

    def test_apply_dpi_correction_error(self):
        """DPI correction коли помилка при отриманні scaling."""
        with patch("functions.tools.tools_screen_capture.get_dpi_scaling", side_effect=Exception("Error")):
            x, y = _apply_dpi_correction(100, 200)
            assert x == 100  # Fallback to original
            assert y == 200


class TestScreenCaptureDPI:
    """Тести для ScreenCapture з DPI."""

    @patch("functions.tools.tools_screen_capture.get_dpi_scaling", return_value=1.5)
    @patch("functions.tools.tools_screen_capture.MSS_AVAILABLE", False)
    def test_get_monitors_info_with_dpi(self, mock_get_dpi):
        """get_monitors_info повертає DPI scaling."""
        capture = ScreenCapture()
        monitors = capture.get_monitors_info()

        assert len(monitors) == 1
        assert monitors[0]["dpi_scaling"] == 1.5

    @patch("functions.tools.tools_screen_capture.get_dpi_scaling", return_value=1.25)
    @patch("functions.tools.tools_screen_capture.MSS_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.mss.mss")
    def test_get_monitors_info_mss_with_dpi(self, mock_mss_class, mock_get_dpi):
        """get_monitors_info з MSS повертає DPI scaling."""
        mock_sct = MagicMock()
        mock_sct.monitors = [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 1920, "top": 0, "width": 1920, "height": 1080},
        ]
        mock_mss_class.return_value.__enter__.return_value = mock_sct

        capture = ScreenCapture()
        monitors = capture.get_monitors_info()

        assert len(monitors) == 2
        assert monitors[0]["dpi_scaling"] == 1.25
        assert monitors[1]["dpi_scaling"] == 1.25
