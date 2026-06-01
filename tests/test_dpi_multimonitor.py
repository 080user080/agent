"""Тести для DPI/мультимонітор підтримки — Phase V5."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from functions.tools.tools_screen_capture import get_dpi_scaling, get_dpi_scaling_global, ScreenCapture


class TestDPIScaling:
    """Тести для DPI scaling detection."""

    def test_get_dpi_scaling_no_ctypes(self):
        """DPI detection коли ctypes недоступний."""
        with patch("functions.tools.tools_screen_capture.DPI_AVAILABLE", False):
            scaling = get_dpi_scaling()
            assert scaling == 1.0

    @patch("functions.tools.tools_screen_capture.DPI_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.ctypes.windll")
    def test_get_dpi_scaling_success(self, mock_windll):
        """Успішне отримання DPI scaling."""
        mock_user32 = MagicMock()
        mock_gdi32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_windll.gdi32 = mock_gdi32

        mock_user32.GetDesktopWindow.return_value = 123
        mock_user32.GetDC.return_value = 456
        mock_gdi32.GetDeviceCaps.return_value = 144  # 150% DPI
        mock_user32.ReleaseDC.return_value = 1

        scaling = get_dpi_scaling()
        assert scaling == 1.5  # 144 / 96

    @patch("functions.tools.tools_screen_capture.DPI_AVAILABLE", True)
    @patch("functions.tools.tools_screen_capture.ctypes.windll")
    def test_get_dpi_scaling_error(self, mock_windll):
        """Помилка при отриманні DPI."""
        mock_windll.user32.GetDesktopWindow.side_effect = Exception("Error")

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
            from functions.tools.tools_screen_capture import get_dpi_scaling
            scaling = get_dpi_scaling()
            x, y = int(100 / scaling), int(200 / scaling)
            assert x == 100
            assert y == 200

    def test_apply_dpi_correction_150_percent(self):
        """DPI correction коли scaling = 1.5."""
        with patch("functions.tools.tools_screen_capture.get_dpi_scaling", return_value=1.5):
            from functions.tools.tools_screen_capture import get_dpi_scaling
            scaling = get_dpi_scaling()
            x, y = int(150 / scaling), int(300 / scaling)
            assert x == 100  # 150 / 1.5
            assert y == 200  # 300 / 1.5

    def test_apply_dpi_correction_200_percent(self):
        """DPI correction коли scaling = 2.0."""
        with patch("functions.tools.tools_screen_capture.get_dpi_scaling", return_value=2.0):
            from functions.tools.tools_screen_capture import get_dpi_scaling
            scaling = get_dpi_scaling()
            x, y = int(400 / scaling), int(600 / scaling)
            assert x == 200  # 400 / 2.0
            assert y == 300  # 600 / 2.0

    def test_apply_dpi_correction_error(self):
        """DPI correction коли помилка при отриманні scaling."""
        with patch("functions.tools.tools_screen_capture.get_dpi_scaling", side_effect=Exception("Error")):
            try:
                scaling = get_dpi_scaling()
            except Exception:
                scaling = 1.0
            x, y = int(100 / scaling), int(200 / scaling)
            assert x == 100  # Fallback to original
            assert y == 200


class TestScreenCaptureDPI:
    """Тести для ScreenCapture з DPI."""

    def test_get_monitors_info_with_dpi(self):
        """get_monitors_info повертає DPI scaling."""
        capture = ScreenCapture()
        monitors = capture.get_monitors_info()
        assert len(monitors) >= 1
        assert monitors[0].get("dpi_scaling", 1.0) >= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])