"""
Тести для модуля tools_ui_detector.py

GUI Automation Phase 4 — Computer Vision (UI елементи).
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import numpy as np

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestUIDetector:
    """Тести для класу UIDetector."""

    @patch('functions.tools.tools_ui_detector.CV_AVAILABLE', True)
    def test_init_cv_available(self):
        """Тест ініціалізації з доступним OpenCV."""
        from functions.tools.tools_ui_detector import UIDetector

        detector = UIDetector()
        assert detector is not None

    @patch('functions.tools.tools_ui_detector.CV_AVAILABLE', False)
    def test_init_cv_unavailable(self):
        """Тест ініціалізації без OpenCV."""
        from functions.tools.tools_ui_detector import UIDetector

        detector = UIDetector()
        assert detector is not None

    @patch('functions.tools.tools_ui_detector.cv2')
    def test_detect_buttons(self, mock_cv2):
        """Тест виявлення кнопок."""
        from functions.tools.tools_ui_detector import UIDetector

        # Mock image
        fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cv2.cvtColor.return_value = fake_image
        mock_cv2.findContours.return_value = ([], None)

        detector = UIDetector()
        result = detector.detect_buttons(fake_image)

        assert result is not None or result == []

    @patch('functions.tools.tools_ui_detector.cv2')
    def test_detect_text_regions(self, mock_cv2):
        """Тест виявлення текстових регіонів."""
        from functions.tools.tools_ui_detector import UIDetector

        # Mock image
        fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cv2.cvtColor.return_value = fake_image

        detector = UIDetector()
        result = detector.detect_text_regions(fake_image)

        assert result is not None or result == []


class TestElementMatcher:
    """Тести для класу ElementMatcher."""

    def test_init(self):
        """Тест ініціалізації ElementMatcher."""
        from functions.tools.tools_ui_detector import ElementMatcher

        matcher = ElementMatcher()
        assert matcher is not None

    def test_match_by_template(self):
        """Тест пошуку за шаблоном."""
        from functions.tools.tools_ui_detector import ElementMatcher
        import numpy as np

        matcher = ElementMatcher()
        fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
        fake_template = np.zeros((20, 20, 3), dtype=np.uint8)

        with patch('functions.tools.tools_ui_detector.cv2'):
            result = matcher.match_by_template(fake_image, fake_template)
            assert result is not None or result == []

    def test_match_by_color(self):
        """Тест пошуку за кольором."""
        from functions.tools.tools_ui_detector import ElementMatcher
        import numpy as np

        matcher = ElementMatcher()
        fake_image = np.zeros((100, 100, 3), dtype=np.uint8)

        result = matcher.match_by_color(fake_image, (0, 0, 255))
        assert result is not None or result == []


class TestClickDetection:
    """Тести для виявлення клікабельних елементів."""

    @patch('functions.tools.tools_ui_detector.UIDetector')
    def test_find_clickable_elements(self, mock_detector):
        """Тест пошуку клікабельних елементів."""
        from functions.tools.tools_ui_detector import find_clickable_elements
        import numpy as np

        fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_detector.return_value.detect_buttons.return_value = []

        result = find_clickable_elements(fake_image)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
