"""Тести для context_manager — стиснення історії дій."""

import unittest
from unittest.mock import MagicMock, patch
from functions.context_manager import (
    summarize_progress,
    format_actions_for_summary,
    should_summarize,
)


class TestContextManager(unittest.TestCase):
    """Тести для модуля стиснення контексту."""

    def test_format_actions_for_summary_empty(self):
        """Форматування порожнього списку дій."""
        result = format_actions_for_summary([])
        self.assertEqual(result, "")

    def test_format_actions_for_summary_basic(self):
        """Базове форматування дій."""
        actions = [
            {"action": "take_screenshot", "result": "ok"},
            {"action": "ocr_screen", "result": "text found"},
        ]
        result = format_actions_for_summary(actions)
        self.assertIn("take_screenshot", result)
        self.assertIn("ocr_screen", result)
        self.assertIn("Крок 1", result)
        self.assertIn("Крок 2", result)

    def test_format_actions_for_summary_truncates_result(self):
        """Результат обрізається до 100 символів."""
        long_result = "x" * 200
        actions = [{"action": "test", "result": long_result}]
        result = format_actions_for_summary(actions)
        self.assertLess(len(result), 200)  # Результат обрізаний

    def test_format_actions_for_summary_no_result(self):
        """Дія без результату."""
        actions = [{"action": "test"}]
        result = format_actions_for_summary(actions)
        self.assertIn("no result", result)

    def test_should_summarize_default(self):
        """Перевірка порогу підсумовування за замовчуванням."""
        self.assertFalse(should_summarize(5))  # 5 < 7 + 3
        self.assertTrue(should_summarize(11))  # 11 > 7 + 3

    def test_should_summarize_custom_threshold(self):
        """Перевірка з кастомним порогом."""
        self.assertFalse(should_summarize(4, threshold=3, keep_recent=1))  # 4 не > 3+1=4
        self.assertTrue(should_summarize(5, threshold=3, keep_recent=1))   # 5 > 3+1=4

    def test_summarize_progress_empty_actions(self):
        """Підсумовування порожнього списку повертає поточний підсумок."""
        result = summarize_progress([], "Current summary", MagicMock())
        self.assertEqual(result, "Current summary")

    def test_summarize_progress_with_llm_success(self):
        """Підсумовування з успішним викликом LLM."""
        actions = [
            {"action": "take_screenshot", "result": "ok"},
            {"action": "ocr_screen", "result": "text"},
        ]
        mock_llm = MagicMock(return_value="New summary text")
        
        result = summarize_progress(actions, "Old summary", mock_llm)
        
        mock_llm.assert_called_once()
        self.assertEqual(result, "New summary text")
        # Перевіряємо що prompt містить дані
        call_args = mock_llm.call_args
        self.assertIn("Old summary", call_args[0][0])
        self.assertIn("take_screenshot", call_args[0][0])

    def test_summarize_progress_llm_fallback(self):
        """Fallback коли LLM недоступний."""
        actions = [{"action": "test", "result": "ok"}]
        mock_llm = MagicMock(side_effect=Exception("LLM error"))
        
        result = summarize_progress(actions, "Old summary", mock_llm)
        
        # Fallback: об'єднання старого підсумку з новими діями
        self.assertIn("Old summary", result)
        self.assertIn("test", result)
        self.assertLess(len(result), 1100)  # Обмежено до 1000 символів

    def test_summarize_progress_system_prompt(self):
        """Перевірка що system_prompt передається."""
        actions = [{"action": "test", "result": "ok"}]
        mock_llm = MagicMock(return_value="Summary")
        
        summarize_progress(actions, "Old", mock_llm)
        
        call_args = mock_llm.call_args
        self.assertIn("system_prompt", call_args[1])
        self.assertIn("менеджер пам'яті", call_args[1]["system_prompt"])


if __name__ == "__main__":
    unittest.main()
