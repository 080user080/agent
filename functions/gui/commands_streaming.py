# functions/gui/commands_streaming.py
"""Потокове виведення відповідей LLM у графічний інтерфейс.

Містить логіку накопичення текстових чанків (stream_chunk),
взаємодію з чергою графічного інтерфейсу (gui_queue) та оновлення статусів.
"""
import time
from colorama import Fore


class StreamingBuffer:
    """Буфер для накопичення текстових чанків від LLM та виведення в GUI.
    
    Інкапсулює логіку накопичення тексту, флашу за реченнями/розміром
    та оновлення статус-бару.
    """
    
    # Мінімальна довжина буфера перед виведенням (~2-3 речення)
    MIN_BUFFER = 180
    
    # Ознаки кінця речення
    SENTENCE_ENDS = ('. ', '! ', '? ', '\n')
    
    def __init__(self, gui_log_callback=None):
        self.gui_log_callback = gui_log_callback
        
        # Внутрішній стан
        self._text = ""           # весь накопичений текст
        self._displayed = ""      # що вже виведено в GUI
        self._count = 0           # лічильник чанків
        self._last_status_update = 0.0
        
    @property
    def full_response(self) -> str:
        """Повний накопичений текст (сира відповідь LLM)."""
        return self._text
    
    def add_chunk(self, chunk_text: str) -> None:
        """Додати черговий чанк тексту від LLM.
        
        Args:
            chunk_text: Текстовий фрагмент від стрімінгу.
                       Може бути None або порожнім — безпечно ігнорується.
        """
        if not chunk_text:
            return
        if not isinstance(chunk_text, str):
            try:
                chunk_text = str(chunk_text)
            except Exception:
                return
        
        self._text += chunk_text
        self._count += 1
        
        # Перевіряємо чи це JSON — якщо так, не показуємо в стрімінгу
        temp_text = self._text.strip()
        if temp_text.startswith('{'):
            return
        
        # Перевіряємо чи треба flush (кінець речення або накопичено достатньо)
        remaining = len(self._text) - len(self._displayed)
        should_flush = (
            self._text.rstrip().endswith(self.SENTENCE_ENDS) or
            remaining >= self.MIN_BUFFER
        )
        
        if should_flush:
            self._flush()
        
        # Оновлюємо статус-бар (кожні 10 токенів)
        if self.gui_log_callback and self._count % 10 == 0:
            now = time.time()
            if now - self._last_status_update > 0.5:  # не частіше ніж раз на 0.5с
                self.gui_log_callback(
                    "update_status",
                    f"🤔 Думаю... ({self._count} токенів)",
                )
                self._last_status_update = now
    
    def _flush(self) -> None:
        """Скинути накопичений буфер у GUI callback."""
        # В поточній реалізації виведення робиться через log_to_gui
        # в кінці process_command. flush_buffer() був заглушкою.
        pass
    
    def final_flush(self) -> None:
        """Фінальний flush залишку тексту після завершення стрімінгу."""
        # Залишок тексту, що не був виведений через SENTENCE_ENDS
        if self._text and len(self._text) > len(self._displayed):
            self._displayed = self._text  # позначаємо як виведене
    
    def reset(self) -> None:
        """Скинути буфер до початкового стану (для наступного запиту)."""
        self._text = ""
        self._displayed = ""
        self._count = 0
        self._last_status_update = 0.0


def stream_llm_response(streaming_handler, messages, gui_log_callback=None,
                         on_token=None):
    """Виконати потоковий запит до LLM з буферизацією в GUI.
    
    Args:
        streaming_handler: Екземпляр StreamingHandler з методами 
                          stream_response_with_callback.
        messages: Список повідомлень для LLM (system + conversation history).
        gui_log_callback: Callback для оновлення GUI 
                         (sender, message) або ("update_status", text).
        on_token: Додатковий callback, що викликається на кожен чанк 
                 (отримує сирий chunk_text).
    
    Returns:
        str: Повний текст відповіді LLM (full_response).
    
    Raises:
        Exception: Перевиняток від streaming_handler, якщо стрімінг не вдався.
                  Клієнт повинен обробити це як fallback на звичайний запит.
    """
    buffer = StreamingBuffer(gui_log_callback=gui_log_callback)
    
    def on_chunk(chunk_text: str):
        """Внутрішній колбек для streaming_handler."""
        # Захист від None / не-str
        if chunk_text is None:
            return
        if not isinstance(chunk_text, str):
            try:
                chunk_text = str(chunk_text)
            except Exception:
                return
        
        buffer.add_chunk(chunk_text)
        
        # Якщо є зовнішній on_token — викликаємо
        if on_token:
            try:
                on_token(chunk_text)
            except Exception:
                pass
    
    # Встановлюємо статус "Думаю..."
    if gui_log_callback:
        gui_log_callback("update_status", "🤔 Думаю...")
    
    # Виконуємо стрімінг — може викинути виняток
    streaming_handler.stream_response_with_callback(messages, on_chunk)
    
    # Фінальний flush
    buffer.final_flush()
    
    return buffer.full_response