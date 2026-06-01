"""Тести для ContextController — єдиний центр управління пам'яттю."""

import unittest
from unittest.mock import MagicMock, patch
from functions.planning.context_controller import ContextController, TIKTOKEN_AVAILABLE


class TestContextController(unittest.TestCase):
    """Тести для модуля управління контекстом."""

    def test_init_without_llm(self):
        """Ініціалізація без LLM клієнта."""
        controller = ContextController(ask_llm_fn=None)
        self.assertEqual(controller.global_summary, "Завдання розпочато. Жодних дій ще не виконано.")
        self.assertEqual(len(controller.short_term_memory), 0)
        self.assertEqual(controller.max_short_term, 5)

    def test_init_with_llm(self):
        """Ініціалізація з LLM клієнтом."""
        mock_llm = MagicMock(return_value="Updated summary")
        controller = ContextController(ask_llm_fn=mock_llm)
        self.assertEqual(controller.global_summary, "Завдання розпочато. Жодних дій ще не виконано.")
        self.assertEqual(len(controller.short_term_memory), 0)

    def test_add_event_basic(self):
        """Базове додавання події."""
        controller = ContextController(ask_llm_fn=None)
        result = controller.add_event("action", "test action")
        
        # Повертає None бо не досягнуто ліміту
        self.assertIsNone(result)
        self.assertEqual(len(controller.short_term_memory), 1)
        self.assertEqual(controller.short_term_memory[0]["type"], "action")
        self.assertEqual(controller.short_term_memory[0]["content"], "test action")

    def test_add_event_triggers_summarization(self):
        """Події тригерять підсумовування при досягненні ліміту."""
        mock_llm = MagicMock(return_value="Summary updated")
        controller = ContextController(ask_llm_fn=mock_llm, max_short_term=3)
        
        # Додаємо 3 події — четверта тригерить підсумовування
        controller.add_event("action", "action 1")
        controller.add_event("action", "action 2")
        controller.add_event("action", "action 3")
        result = controller.add_event("action", "action 4")
        
        # Підсумовування викликано
        self.assertIsNotNone(result)
        mock_llm.assert_called_once()
        # Пам'ять обмежена до max_short_term
        self.assertLessEqual(len(controller.short_term_memory), 3)

    def test_clean_content_short(self):
        """Короткий контекст не обрізається."""
        controller = ContextController(ask_llm_fn=None)
        result = controller._clean_content("short text")
        self.assertEqual(result, "short text")

    def test_clean_content_long(self):
        """Довгий контекст обрізається."""
        controller = ContextController(ask_llm_fn=None, max_content_chars=50)
        long_text = "x" * 100
        result = controller._clean_content(long_text)
        self.assertLess(len(result), 100)
        self.assertIn("[ДАНІ ОБРІЗАНО]", result)

    def test_summarize_oldest_without_llm(self):
        """Підсумовування без LLM — fallback."""
        controller = ContextController(ask_llm_fn=None)
        controller.short_term_memory.append({"type": "action", "content": "test action"})
        
        result = controller._summarize_oldest()
        
        # Fallback: просте об'єднання
        self.assertIn("action", result)
        self.assertIn("test action", result)
        self.assertEqual(len(controller.short_term_memory), 0)

    def test_summarize_oldest_with_llm(self):
        """Підсумовування з LLM."""
        mock_llm = MagicMock(return_value="New summary")
        controller = ContextController(ask_llm_fn=mock_llm)
        controller.short_term_memory.append({"type": "action", "content": "test action"})
        
        result = controller._summarize_oldest()
        
        self.assertEqual(result, "New summary")
        self.assertEqual(controller.global_summary, "New summary")
        mock_llm.assert_called_once()
        self.assertEqual(len(controller.short_term_memory), 0)

    def test_get_full_context(self):
        """Отримання повного контексту."""
        controller = ContextController(ask_llm_fn=None)
        controller.add_event("action", "action 1")
        controller.add_event("observation", "observation 1")
        
        context = controller.get_full_context()
        
        self.assertIn("ПРОГРЕС (summary):", context)
        self.assertIn("ОСТАННІ ДЕТАЛЬНІ КРОКИ:", context)
        self.assertIn("action", context)
        self.assertIn("observation", context)

    def test_count_tokens_with_tiktoken(self):
        """Підрахунок токенів з tiktoken."""
        if not TIKTOKEN_AVAILABLE:
            self.skipTest("tiktoken не встановлено")
        
        controller = ContextController(ask_llm_fn=None)
        text = "Hello, world!"
        tokens = controller.count_tokens(text)
        self.assertGreater(tokens, 0)

    def test_count_tokens_fallback(self):
        """Fallback підрахунок токенів без tiktoken."""
        # Емулюємо відсутність tiktoken
        with patch('functions.planning.context_controller.TIKTOKEN_AVAILABLE', False):
            controller = ContextController(ask_llm_fn=None)
            text = "Hello, world!"  # ~13 символів
            tokens = controller.count_tokens(text)
            # Fallback: 1 токен ≈ 4 символи
            self.assertEqual(tokens, len(text) // 4)

    def test_get_compressed_ocr_short(self):
        """Короткий OCR текст не стискається."""
        controller = ContextController(ask_llm_fn=None)
        text = "short text"
        result = controller.get_compressed_ocr(text)
        self.assertEqual(result, text)

    def test_get_compressed_ocr_long(self):
        """Довгий OCR текст стискається."""
        controller = ContextController(ask_llm_fn=None)
        text = "x" * 1000
        result = controller.get_compressed_ocr(text, max_chars=100)
        self.assertLess(len(result), 1000)
        self.assertIn("[SCALED]", result)

    def test_context_tokens_used_property(self):
        """Property context_tokens_used повертає int після додавання події."""
        controller = ContextController(ask_llm_fn=None)
        # Початковий стан — контекст порожній, але global_summary не пустий
        tokens_before = controller.context_tokens_used
        self.assertIsInstance(tokens_before, int)
        self.assertGreaterEqual(tokens_before, 0)

        # Після додавання події токенів має побільшати
        controller.add_event("action", "test action event for tokens")
        tokens_after = controller.context_tokens_used
        self.assertIsInstance(tokens_after, int)
        self.assertGreater(tokens_after, 0)

    def test_context_tokens_used_after_reset(self):
        """Скидання контексту зменшує context_tokens_used."""
        controller = ContextController(ask_llm_fn=None)
        controller.add_event("action", "some long text to increase token count " * 10)
        tokens_before = controller.context_tokens_used

        controller.reset()
        tokens_after = controller.context_tokens_used

        self.assertGreater(tokens_before, 0)
        self.assertLess(tokens_after, tokens_before)

    def test_reset(self):
        """Скидання стану контролера."""
        controller = ContextController(ask_llm_fn=None)
        controller.add_event("action", "test")
        controller.global_summary = "Custom summary"
        
        controller.reset()
        
        self.assertEqual(controller.global_summary, "Завдання розпочато. Жодних дій ще не виконано.")
        self.assertEqual(len(controller.short_term_memory), 0)


if __name__ == "__main__":
    unittest.main()
