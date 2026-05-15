"""Тести для screen_helper — корекція координат DPI."""

import unittest
from unittest.mock import patch, MagicMock
from functions.gui.screen_helper import (
    get_windows_scale_factor,
    normalize_coordinates,
    denormalize_coordinates,
    get_screen_resolution,
)


class TestScreenHelper(unittest.TestCase):
    """Тести для модуля корекції координат DPI."""

    @patch('functions.gui.screen_helper.ctypes.windll')
    def test_get_windows_scale_factor_100_percent(self, mock_windll):
        """Тест для 100% масштабу."""
        mock_windll.shcore.SetProcessDpiAwareness.return_value = None
        mock_windll.shcore.GetScaleFactorForDevice.return_value = 100
        
        scale = get_windows_scale_factor()
        
        self.assertEqual(scale, 1.0)
        mock_windll.shcore.SetProcessDpiAwareness.assert_called_once_with(1)
        mock_windll.shcore.GetScaleFactorForDevice.assert_called_once_with(0)

    @patch('functions.gui.screen_helper.ctypes.windll')
    def test_get_windows_scale_factor_125_percent(self, mock_windll):
        """Тест для 125% масштабу."""
        mock_windll.shcore.SetProcessDpiAwareness.return_value = None
        mock_windll.shcore.GetScaleFactorForDevice.return_value = 125
        
        scale = get_windows_scale_factor()
        
        self.assertEqual(scale, 1.25)

    @patch('functions.gui.screen_helper.ctypes.windll')
    def test_get_windows_scale_factor_150_percent(self, mock_windll):
        """Тест для 150% масштабу."""
        mock_windll.shcore.SetProcessDpiAwareness.return_value = None
        mock_windll.shcore.GetScaleFactorForDevice.return_value = 150
        
        scale = get_windows_scale_factor()
        
        self.assertEqual(scale, 1.5)

    @patch('functions.gui.screen_helper.get_windows_scale_factor')
    def test_normalize_coordinates_100_percent(self, mock_scale):
        """Нормалізація координат при 100% масштабі."""
        mock_scale.return_value = 1.0
        
        result = normalize_coordinates(1000, 500)
        
        self.assertEqual(result, (1000, 500))

    @patch('functions.gui.screen_helper.get_windows_scale_factor')
    def test_normalize_coordinates_125_percent(self, mock_scale):
        """Нормалізація координат при 125% масштабі."""
        mock_scale.return_value = 1.25
        
        result = normalize_coordinates(1000, 500)
        
        # 1000 / 1.25 = 800, 500 / 1.25 = 400
        self.assertEqual(result, (800, 400))

    @patch('functions.gui.screen_helper.get_windows_scale_factor')
    def test_normalize_coordinates_150_percent(self, mock_scale):
        """Нормалізація координат при 150% масштабі."""
        mock_scale.return_value = 1.5
        
        result = normalize_coordinates(1500, 750)
        
        # 1500 / 1.5 = 1000, 750 / 1.5 = 500
        self.assertEqual(result, (1000, 500))

    @patch('functions.gui.screen_helper.get_windows_scale_factor')
    def test_denormalize_coordinates_100_percent(self, mock_scale):
        """Зворотна нормалізація при 100% масштабі."""
        mock_scale.return_value = 1.0
        
        result = denormalize_coordinates(1000, 500)
        
        self.assertEqual(result, (1000, 500))

    @patch('functions.gui.screen_helper.get_windows_scale_factor')
    def test_denormalize_coordinates_125_percent(self, mock_scale):
        """Зворотна нормалізація при 125% масштабі."""
        mock_scale.return_value = 1.25
        
        result = denormalize_coordinates(800, 400)
        
        # 800 * 1.25 = 1000, 400 * 1.25 = 500
        self.assertEqual(result, (1000, 500))

    @patch('functions.gui.screen_helper.get_windows_scale_factor')
    def test_roundtrip_normalization(self, mock_scale):
        """Тест roundtrip: нормалізація → зворотна нормалізація."""
        mock_scale.return_value = 1.5
        
        original = (1500, 750)
        normalized = normalize_coordinates(*original)
        denormalized = denormalize_coordinates(*normalized)
        
        self.assertEqual(original, denormalized)

    @patch('functions.gui.screen_helper.ctypes.windll')
    def test_get_windows_scale_factor_fallback(self, mock_windll):
        """Fallback при помилці ctypes."""
        mock_windll.shcore.SetProcessDpiAwareness.side_effect = Exception("Test error")
        
        scale = get_windows_scale_factor()
        
        # Fallback повертає 1.0
        self.assertEqual(scale, 1.0)

    @patch('functions.gui.screen_helper.PYAUTOGUI_AVAILABLE', False)
    def test_get_screen_resolution_unavailable(self):
        """get_screen_resolution коли pyautogui недоступний."""
        result = get_screen_resolution()
        
        self.assertIsNone(result)

    @patch('functions.gui.screen_helper.pyautogui')
    def test_get_screen_resolution_available(self, mock_pyautogui):
        """get_screen_resolution коли pyautogui доступний."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = get_screen_resolution()
        
        self.assertEqual(result, (1920, 1080))
        mock_pyautogui.size.assert_called_once()


if __name__ == "__main__":
    unittest.main()
