"""Context Controller — єдиний центр управління пам'ятю для AgentLoop та VoiceAssistant.

Цей модуль вирішує проблеми:
- VoiceAssistant та AgentLoop використовують один спільний контекст
- Автоматичне підсумовування старих дій через LLM
- Стиснення OCR та інших довгих даних
- Токенометрія для контролю розміру промпту
"""

from typing import List, Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken не встановлено — токенометрія недоступна. pip install tiktoken")


class ContextController:
    """Єдиний контролер контексту для AgentLoop та VoiceAssistant.
    
    Зберігає:
    - global_summary: стислий підсумок виконання завдання
    - short_term_memory: останні 3-5 детальних подій
    - Використовує LLM для автоматичного підсумовування старих дій
    - Стискає довгі дані (OCR, UIA) перед записом
    """
    
    def __init__(
        self,
        ask_llm_fn: Optional[Callable[[str, Optional[str]], str]] = None,
        model_name: str = "gpt-4o",
        max_short_term: int = 5,
        max_content_chars: int = 800,
    ):
        """
        Args:
            ask_llm_fn: Функція для виклику LLM (prompt, system_prompt) -> str
            model_name: Назва моделі для токенометрії
            max_short_term: Скільки подій тримати в деталях
            max_content_chars: Максимальна довжина контенту перед стисненням
        """
        self.ask_llm_fn = ask_llm_fn
        self.global_summary = "Завдання розпочато. Жодних дій ще не виконано."
        self.short_term_memory: List[Dict[str, Any]] = []
        self.max_short_term = max_short_term
        self.max_content_chars = max_content_chars
        
        # Ініціалізація токенометра
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.get_encoding("cl100k_base")  # Стандарт для GPT-4/3.5
                logger.info(f"ContextController: tiktoken ініціалізовано для {model_name}")
            except Exception as e:
                logger.warning(f"ContextController: не вдалося ініціалізувати tiktoken: {e}")
                self.encoding = None
        else:
            self.encoding = None
    
    def add_event(self, event_type: str, content: Any) -> Optional[str]:
        """Додає подію в короткочасову пам'ять.
        
        Args:
            event_type: Тип події ('action', 'observation', 'voice_command', 'error')
            content: Дані події
            
        Returns:
            Новий global_summary якщо відбулося підсумовування, інакше None
        """
        # Очищення та стиснення контенту
        cleaned_content = self._clean_content(content)
        
        event = {
            "type": event_type,
            "content": cleaned_content,
        }
        
        self.short_term_memory.append(event)
        
        # Якщо пам'ять переповнена — схлопуємо найстарішу подію
        if len(self.short_term_memory) > self.max_short_term:
            return self._summarize_oldest()
        
        return None
    
    def _clean_content(self, content: Any) -> str:
        """Очищення та стиснення контенту перед записом в історію.
        
        Args:
            content: Вхідні дані (будь-якого типу)
            
        Returns:
            Очищений та стиснутий текст
        """
        text = str(content)
        
        # Якщо текст занадто довгий — стискаємо
        if len(text) > self.max_content_chars:
            half = self.max_content_chars // 2
            return f"{text[:half]}... [ДАНІ ОБРІЗАНО] ... {text[-half:]}"
        
        return text
    
    def _summarize_oldest(self) -> str:
        """Викликає LLM для оновлення глобального підсумку.
        
        Returns:
            Новий global_summary
        """
        if not self.short_term_memory:
            return self.global_summary
        
        # Витягуємо найстарішу подію
        old_event = self.short_term_memory.pop(0)
        
        prompt = f"""
Онови глобальний звіт про роботу агента Марк.

ПОТОЧНИЙ ЗВІТ:
{self.global_summary}

НОВА ПОДІЯ:
Тип: {old_event['type']}
Дані: {old_event['content']}

ЗАВДАННЯ:
Додай інформацію про нову подію до звіту.
Пиши максимально стисло (один-два рядки).
Видали технічні деталі (координати, зайвий текст), залиш тільки суть виконаної роботи.
Якщо подія — це помилка, обов'язково зазнач, що крок не вдався.

НОВИЙ ЗВІТ:
"""
        
        try:
            if self.ask_llm_fn:
                new_summary = self.ask_llm_fn(
                    prompt,
                    system_prompt="Ти — архіватор логів Марка. Пиши тільки оновлений текст звіту українською."
                )
                if new_summary:
                    self.global_summary = new_summary.strip()
                    logger.info(f"ContextController: summary оновлено: {self.global_summary[:100]}...")
                    return self.global_summary
            else:
                # Fallback без LLM — просте об'єднання
                self.global_summary += f"\n- {old_event['type']}: {old_event['content'][:100]}"
                # Обмежуємо довжину
                if len(self.global_summary) > 1000:
                    self.global_summary = self.global_summary[:1000] + "..."
        except Exception as e:
            logger.warning(f"ContextController: помилка при підсумовуванні: {e}")
            # Fallback
            self.global_summary += f"\n- {old_event['type']}: {old_event['content'][:100]}"
        
        return self.global_summary
    
    def get_full_context(self) -> str:
        """Повертає повний контекст для вставки в системний промпт.
        
        Returns:
            Рядок з global_summary та останніми детальними кроками
        """
        history_str = "\n".join([
            f"- {m['type']}: {m['content']}"
            for m in self.short_term_memory
        ])
        
        return f"ПРОГРЕС (summary):\n{self.global_summary}\n\nОСТАННІ ДЕТАЛЬНІ КРОКИ:\n{history_str}"
    
    def count_tokens(self, text: str) -> int:
        """Підраховує кількість токенів у тексті.
        
        Args:
            text: Текст для підрахунку
            
        Returns:
            Кількість токенів (або груба оцінка якщо tiktoken недоступний)
        """
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass
        
        # Fallback: груба оцінка (1 токен ≈ 4 символи)
        return len(text) // 4
    
    def get_compressed_ocr(self, ocr_text: str, max_chars: int = 500) -> str:
        """Стискає OCR текст.
        
        Args:
            ocr_text: Текст OCR
            max_chars: Максимальна кількість символів
            
        Returns:
            Стиснутий текст
        """
        if len(ocr_text) <= max_chars:
            return ocr_text
        
        half = max_chars // 2
        return f"{ocr_text[:half]}... [SCALED] ... {ocr_text[-half:]}"
    
    def reset(self):
        """Скидає стан контролера (для нових завдань)."""
        self.global_summary = "Завдання розпочато. Жодних дій ще не виконано."
        self.short_term_memory = []
        logger.info("ContextController: стан скинуто")
