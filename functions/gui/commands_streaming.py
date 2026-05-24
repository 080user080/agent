# functions/gui/commands_streaming.py
"""Потокове виведення відповідей LLM у графічний інтерфейс.

Містить логіку накопичення текстових чанків (StreamingBuffer),
взаємодію з чергою графічного інтерфейсу (gui_queue) та оновлення статусів.
"""
import time
from colorama import Fore
from typing import Optional, Callable


class StreamingBuffer:
    """Буфер для накопичення текстових чанків від LLM та виведення в GUI.
    
    Інкапсулює логіку накопичення тексту, флашу за реченнями/розміром
    та оновлення статус-бару. Підтримує як callback-сумісний режим
    (gui_log_callback), так і чергу GUI (gui_queue) для реального часу.
    """
    
    # Мінімальна довжина буфера перед виведенням (~2-3 речення)
    MIN_BUFFER = 180
    
    # Ознаки кінця речення
    SENTENCE_ENDS = ('. ', '! ', '? ', '\n')

    # Максимальний розмір одного флаша — щоб не залити GUI великим текстом
    MAX_FLUSH_SIZE = 500

    def __init__(self, gui_log_callback=None, gui_queue=None):
        self.gui_log_callback = gui_log_callback
        self.gui_queue = gui_queue  # Queue для PyQt6 signal/slot

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
                       Містить сирі байти/неочікувані символи — конвертується
                       з `errors='replace'`.
        """
        if not chunk_text:
            return
        if not isinstance(chunk_text, str):
            try:
                # Захист від не-str типів — безпечне перетворення
                chunk_text = str(chunk_text)
            except Exception:
                return

        # Захист від помилок кодування — замінюємо некоректні символи
        try:
            # На випадок, якщо str містить сурогатні пари або невалідні Unicode
            chunk_text = chunk_text.encode('utf-8', errors='replace').decode('utf-8')
        except Exception:
            # Якщо навіть encode/decode не вдається — ігноруємо чанк
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
        if self._count % 10 == 0:
            self._update_status()
    
    def _update_status(self) -> None:
        """Оновити статус-бар з кількістю токенів (з дебаунсом 0.5с)."""
        now = time.time()
        if now - self._last_status_update < 0.5:
            return
        
        status_text = f"🤔 Думаю... ({self._count} токенів)"
        
        if self.gui_log_callback:
            try:
                self.gui_log_callback("update_status", status_text)
            except Exception:
                pass
        
        if self.gui_queue:
            try:
                self.gui_queue.put_nowait(("update_status", status_text))
            except Exception:
                pass
        
        self._last_status_update = now

    def _flush(self) -> None:
        """Скинути накопичений буфер у GUI (callback та/або чергу).
        
        Виводить лише новий текст, що ще не був відображений.
        Обмежує розмір одного флаша MAX_FLUSH_SIZE символами,
        щоб не залити інтерфейс великим шматком тексту.
        """
        if len(self._text) <= len(self._displayed):
            return
        
        new_text = self._text[len(self._displayed):]
        if not new_text.strip():
            return
        
        # Обмежуємо розмір флаша
        if len(new_text) > self.MAX_FLUSH_SIZE:
            # Шукаємо останній SENTENCE_END у межах MAX_FLUSH_SIZE
            truncate_at = self.MAX_FLUSH_SIZE
            for sep in self.SENTENCE_ENDS:
                idx = new_text[:self.MAX_FLUSH_SIZE].rfind(sep)
                if idx > truncate_at // 2:  # мінімум половина MAX_FLUSH_SIZE
                    truncate_at = min(truncate_at, idx + len(sep))
            new_text = new_text[:truncate_at]
        
        # Позначаємо як виведене
        self._displayed = self._text[:len(self._displayed) + len(new_text)]
        
        # Відправляємо в GUI
        if self.gui_log_callback:
            try:
                self.gui_log_callback("stream_chunk", new_text)
            except Exception:
                pass
        
        if self.gui_queue:
            try:
                self.gui_queue.put_nowait(("stream_chunk", new_text))
            except Exception:
                pass

    def final_flush(self) -> None:
        """Фінальний flush залишку тексту після завершення стрімінгу.
        
        Виводить у GUI весь невідображений текст.
        """
        if self._text and len(self._text) > len(self._displayed):
            remaining = self._text[len(self._displayed):]
            self._displayed = self._text
            
            if self.gui_log_callback:
                try:
                    self.gui_log_callback("stream_chunk", remaining)
                except Exception:
                    pass
            
            if self.gui_queue:
                try:
                    self.gui_queue.put_nowait(("stream_chunk", remaining))
                except Exception:
                    pass
    
    def reset(self) -> None:
        """Скинути буфер до початкового стану (для наступного запиту)."""
        self._text = ""
        self._displayed = ""
        self._count = 0
        self._last_status_update = 0.0


def stream_llm_response(
    streaming_handler,
    messages,
    gui_log_callback=None,
    gui_queue=None,
    on_token: Optional[Callable[[str], None]] = None,
) -> str:
    """Виконати потоковий запит до LLM з буферизацією в GUI.
    
    Args:
        streaming_handler: Екземпляр StreamingHandler з методами 
                          stream_response_with_callback.
        messages: Список повідомлень для LLM (system + conversation history).
        gui_log_callback: Callback для оновлення GUI 
                         (sender, message) або ("update_status", text).
        gui_queue: Queue.Queue для PyQt6 signal/slot (альтернатива callback).
        on_token: Додатковий callback, що викликається на кожен чанк 
                 (отримує сирий chunk_text).
    
    Returns:
        str: Повний текст відповіді LLM (full_response).
    
    Raises:
        Exception: Перевиняток від streaming_handler, якщо стрімінг не вдався.
                  Клієнт повинен обробити це як fallback на звичайний запит.
    """
    buffer = StreamingBuffer(
        gui_log_callback=gui_log_callback,
        gui_queue=gui_queue,
    )
    
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
        try:
            gui_log_callback("update_status", "🤔 Думаю...")
        except Exception:
            pass
    if gui_queue:
        try:
            gui_queue.put_nowait(("update_status", "🤔 Думаю..."))
        except Exception:
            pass
    
    # Виконуємо стрімінг — може викинути виняток
    streaming_handler.stream_response_with_callback(messages, on_chunk)
    
    # Фінальний flush — виводимо залишок тексту
    buffer.final_flush()
    
    return buffer.full_response