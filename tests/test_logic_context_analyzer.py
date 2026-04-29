"""
Тести для модуля logic_context_analyzer.py

GUI Automation Phase 5 — Аналіз контексту екрану.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import numpy as np

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestContextAnalyzer:
    """Тести для класу ContextAnalyzer."""

    def test_init(self):
        """Тест ініціалізації ContextAnalyzer."""
        from functions.logic_context_analyzer import ContextAnalyzer

        analyzer = ContextAnalyzer()
        assert analyzer is not None

    @patch('functions.logic_context_analyzer.capture_screen')
    def test_analyze_screen(self, mock_capture):
        """Тест аналізу екрану."""
        from functions.logic_context_analyzer import ContextAnalyzer

        # Mock image
        from PIL import Image
        fake_image = Image.new('RGB', (100, 100), color='white')
        mock_capture.return_value = fake_image

        analyzer = ContextAnalyzer()
        result = analyzer.analyze_screen()

        assert result is not None

    @patch('functions.logic_context_analyzer.capture_screen')
    def test_detect_ui_elements(self, mock_capture):
        """Тест виявлення UI елементів."""
        from functions.logic_context_analyzer import ContextAnalyzer

        # Mock image
        from PIL import Image
        fake_image = Image.new('RGB', (100, 100), color='white')
        mock_capture.return_value = fake_image

        analyzer = ContextAnalyzer()
        result = analyzer.detect_ui_elements(fake_image)

        assert result is not None

    @patch('functions.logic_context_analyzer.capture_screen')
    def test_extract_text_regions(self, mock_capture):
        """Тест виділення текстових регіонів."""
        from functions.logic_context_analyzer import ContextAnalyzer

        # Mock image
        from PIL import Image
        fake_image = Image.new('RGB', (100, 100), color='white')
        mock_capture.return_value = fake_image

        analyzer = ContextAnalyzer()
        result = analyzer.extract_text_regions(fake_image)

        assert result is not None


class TestContextSnapshot:
    """Тести для класу ContextSnapshot."""

    def test_init(self):
        """Тест ініціалізації ContextSnapshot."""
        from functions.logic_context_analyzer import ContextSnapshot

        snapshot = ContextSnapshot()
        assert snapshot is not None

    def test_capture(self):
        """Тест захоплення снепшоту."""
        from functions.logic_context_analyzer import ContextSnapshot

        snapshot = ContextSnapshot()
        with patch('functions.logic_context_analyzer.capture_screen'):
            result = snapshot.capture()
            assert result is not None

    def test_compare_snapshots(self):
        """Тест порівняння снепшотів."""
        from functions.logic_context_analyzer import ContextSnapshot

        snapshot1 = ContextSnapshot()
        snapshot2 = ContextSnapshot()

        with patch('functions.logic_context_analyzer.capture_screen'):
            snapshot1.capture()
            snapshot2.capture()

            result = snapshot1.compare(snapshot2)
            assert result is not None


class TestContextHistory:
    """Тести для історії контексту."""

    def test_init(self):
        """Тест ініціалізації ContextHistory."""
        from functions.logic_context_analyzer import ContextHistory

        history = ContextHistory(max_size=10)
        assert history is not None
        assert history.max_size == 10

    def test_add_snapshot(self):
        """Тест додавання снепшоту."""
        from functions.logic_context_analyzer import ContextHistory

        history = ContextHistory(max_size=10)
        snapshot = MagicMock()
        history.add(snapshot)

        assert len(history.snapshots) == 1

    def test_max_size_limit(self):
        """Тест обмеження розміру історії."""
        from functions.logic_context_analyzer import ContextHistory

        history = ContextHistory(max_size=5)
        for i in range(10):
            history.add(MagicMock())

        assert len(history.snapshots) <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
