"""
STT Listener — модуль прийому голосових команд для агента.

Функціонал:
- Активація по кнопці (GUI) або wake word ("Окей Марк")
- Розпізнавання мови через STT Engine
- Передача тексту в process_text_command()
- Індикація стану (слухає/розпізнає/готово)
"""

import threading
import time
import numpy as np
import sounddevice as sd
from typing import Callable, Optional, Dict, Any
from colorama import Fore

from .logic_stt import get_stt_engine, STTEngine
from .config import (
    SAMPLE_RATE, LISTEN_DURATION, VOLUME_THRESHOLD,
    MICROPHONE_DEVICE_ID, STT_ENABLED, STT_LANGUAGE
)


class STTListener:
    """Слухач голосових команд для агента."""

    # Wake words для активації
    WAKE_WORDS = ["окей марк", "окей марке", "ок марк", "hey mark", "okay mark"]

    def __init__(self, command_callback: Callable[[str], None], status_callback: Optional[Callable[[str, Any], None]] = None):
        """
        Args:
            command_callback: Функція, яка викликається з розпізнаним текстом команди
            status_callback: Функція для оновлення статусу (listening, processing, idle)
        """
        self.command_callback = command_callback
        self.status_callback = status_callback

        # STT Engine
        self.stt_engine: Optional[STTEngine] = None

        # Стан
        self.is_running = False
        self.is_listening = False
        self.is_processing = False
        self.listen_thread: Optional[threading.Thread] = None

        # Налаштування
        self.sample_rate = SAMPLE_RATE
        self.listen_duration = LISTEN_DURATION
        self.volume_threshold = VOLUME_THRESHOLD
        self.device_id = MICROPHONE_DEVICE_ID

        # Wake word режим
        self.wake_word_enabled = False
        self.wake_word_buffer = []
        self.wake_word_buffer_duration = 2.0  # секунди для wake word

    def initialize(self) -> bool:
        """Ініціалізувати STT Engine."""
        try:
            # Перевіряємо актуальне user-налаштування (не тільки config.py константу)
            try:
                from .core_settings import get_setting
                stt_on = get_setting("STT_ENABLED", STT_ENABLED)
            except Exception:
                stt_on = STT_ENABLED
            if not stt_on:
                print(f"{Fore.YELLOW}⚠️  STT вимкнено в налаштуваннях")
                return False

            print(f"{Fore.CYAN}🔊 Ініціалізація STT Listener...")
            self.stt_engine = get_stt_engine()

            available = self.stt_engine.get_available_models()
            if not available:
                print(f"{Fore.RED}❌ Немає доступних STT моделей")
                return False

            print(f"{Fore.GREEN}✅ STT Listener готовий: {', '.join(available)}")
            return True

        except Exception as e:
            print(f"{Fore.RED}❌ Помилка ініціалізації STT: {e}")
            return False

    def _update_status(self, status: str, data: Any = None):
        """Оновити статус через callback."""
        if self.status_callback:
            try:
                self.status_callback(status, data)
            except Exception as e:
                print(f"{Fore.RED}   Помилка status callback: {e}")

    def start(self, wake_word_mode: bool = False):
        """Запустити постійне прослуховування (в окремому потоці)."""
        if self.is_running:
            print(f"{Fore.YELLOW}⚠️  STT Listener вже запущено")
            return

        if not self.stt_engine:
            if not self.initialize():
                return

        self.wake_word_enabled = wake_word_mode
        self.is_running = True

        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

        mode = "wake word" if wake_word_mode else "manual"
        print(f"{Fore.GREEN}✅ STT Listener запущено ({mode} mode)")

    def stop(self):
        """Зупинити прослуховування."""
        self.is_running = False
        self.is_listening = False

        if self.listen_thread and self.listen_thread.is_alive():
            # Не чекаємо — просто позначаємо для зупинки
            pass

        self._update_status("stopped")
        print(f"{Fore.YELLOW}⏹️  STT Listener зупинено")

    def listen_once(self, duration: Optional[int] = None, wait_for_speech: bool = True) -> Optional[str]:
        """
        Одноразовий запис і розпізнавання (для кнопки в GUI).

        Args:
            duration: Тривалість запису (якщо None — використовує LISTEN_DURATION)
            wait_for_speech: Чекати початку мови перед записом

        Returns:
            Розпізнаний текст або None
        """
        if not self.stt_engine:
            if not self.initialize():
                return None

        duration = duration or self.listen_duration

        try:
            self._update_status("listening")
            print(f"{Fore.CYAN}🎤 Слухаю {duration}с...")

            # Запис аудіо
            audio = self._record_audio(duration, wait_for_speech=wait_for_speech)

            if audio is None or len(audio) == 0:
                print(f"{Fore.YELLOW}⚠️  Не отримано аудіо")
                self._update_status("idle")
                return None

            # Розпізнавання
            self._update_status("processing", {"duration": len(audio) / self.sample_rate})
            print(f"{Fore.CYAN}🔍 Розпізнаю...")

            text = self.stt_engine.transcribe(audio)

            if text and text.strip():
                cleaned = self._clean_text(text)
                print(f"{Fore.GREEN}✅ Розпізнано: '{cleaned}'")
                self._update_status("recognized", {"text": cleaned})
                return cleaned
            else:
                print(f"{Fore.YELLOW}⚠️  Не розпізнано текст")
                self._update_status("idle")
                return None

        except Exception as e:
            print(f"{Fore.RED}❌ Помилка запису/розпізнавання: {e}")
            self._update_status("error", {"error": str(e)})
            return None

    def _record_audio(self, duration: int, wait_for_speech: bool = True) -> Optional[np.ndarray]:
        """Записати аудіо з мікрофона."""
        try:
            # Якщо чекаємо мову — слухаємо поки не почнеться
            if wait_for_speech:
                audio = self._wait_for_speech_and_record(duration)
                return audio
            else:
                # Простий запис
                recording = sd.rec(
                    int(duration * self.sample_rate),
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype=np.float32,
                    device=self.device_id,
                    blocking=True
                )
                return np.squeeze(recording)

        except Exception as e:
            print(f"{Fore.RED}❌ Помилка запису: {e}")
            return None

    def _wait_for_speech_and_record(self, duration: int, pre_buffer_sec: float = 0.5) -> Optional[np.ndarray]:
        """Чекати початку мови, потім записати."""
        print(f"{Fore.CYAN}   ⏳ Чекаю на мову...")

        # Параметри
        chunk_size = int(0.1 * self.sample_rate)  # 100ms chunks
        pre_buffer_size = int(pre_buffer_sec * self.sample_rate)
        max_wait_time = 10.0  # максимум чекати 10 секунд

        pre_buffer = []
        audio_chunks = []
        silence_chunks = 0
        max_silence_chunks = 20  # 2 секунди тиші = кінець
        is_recording = False
        start_time = time.time()

        # Потоковий запис
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            device=self.device_id,
            blocksize=chunk_size
        ) as stream:
            while time.time() - start_time < max_wait_time + duration:
                chunk, _ = stream.read(chunk_size)
                chunk = np.squeeze(chunk)

                # Рівень гучності
                volume = np.sqrt(np.mean(chunk**2))

                if not is_recording:
                    # Чекаємо початку мови
                    pre_buffer.append(chunk)
                    if len(pre_buffer) > pre_buffer_size // chunk_size:
                        pre_buffer.pop(0)

                    if volume > self.volume_threshold:
                        print(f"{Fore.GREEN}   🎙️  Виявлено мову, починаю запис...")
                        is_recording = True
                        # Додаємо pre-buffer щоб не втратити початок
                        audio_chunks.extend(pre_buffer)
                        audio_chunks.append(chunk)
                        pre_buffer = []
                else:
                    # Записуємо
                    audio_chunks.append(chunk)

                    # Перевірка тиші для закінчення
                    if volume < self.volume_threshold:
                        silence_chunks += 1
                        if silence_chunks > max_silence_chunks:
                            print(f"{Fore.CYAN}   ⏹️  Тиша, закінчую запис...")
                            break
                    else:
                        silence_chunks = 0

                    # Перевірка максимальної тривалості
                    if len(audio_chunks) * chunk_size / self.sample_rate >= duration:
                        break

        if not is_recording:
            print(f"{Fore.YELLOW}   ⚠️  Мову не виявлено за {max_wait_time}с")
            return None

        # Об'єднати чанки
        audio = np.concatenate(audio_chunks)
        return audio

    def _listen_loop(self):
        """Головний цикл прослуховування (для wake word режиму)."""
        while self.is_running:
            try:
                if self.wake_word_enabled:
                    # Wake word режим
                    self._listen_for_wake_word()
                else:
                    # Manual режим — просто спимо
                    time.sleep(0.1)

            except Exception as e:
                print(f"{Fore.RED}❌ Помилка в listen_loop: {e}")
                time.sleep(1)

    def _listen_for_wake_word(self):
        """Слухати wake word і потім команду."""
        # TODO: Реалізувати lightweight wake word detection
        # Поки що — просто слухаємо 2 секунди і перевіряємо чи є wake word

        audio = self._record_audio(2, wait_for_speech=False)
        if audio is None:
            return

        # Швидке розпізнавання (тільки для wake word)
        text = self.stt_engine.transcribe(audio)
        if not text:
            return

        text_lower = text.lower().strip()

        # Перевірка wake words
        for wake_word in self.WAKE_WORDS:
            if wake_word in text_lower:
                print(f"{Fore.GREEN}🎯 Wake word виявлено: '{wake_word}'")
                self._update_status("wake_word_detected")

                # Слухаємо команду
                command = self.listen_once(duration=10)
                if command:
                    self._execute_command(command)
                return

    def _execute_command(self, text: str):
        """Виконати команду через callback."""
        print(f"{Fore.GREEN}🚀 Виконую команду: '{text}'")
        self._update_status("executing", {"command": text})

        try:
            self.command_callback(text)
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка виконання команди: {e}")
            self._update_status("error", {"error": str(e)})

    def _clean_text(self, text: str) -> str:
        """Очистити розпізнаний текст."""
        import re

        # Видалити non-printable
        text = re.sub(r'[^\x20-\x7E\u0410-\u044F\u0406\u0407\u0456\u0457ЄєІіЇїҐґ\s.,!?-]', '', text)

        # Нормалізувати пробіли
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def set_wake_word_enabled(self, enabled: bool):
        """Увімкнути/вимкнути wake word режим."""
        self.wake_word_enabled = enabled
        mode = "wake word" if enabled else "manual"
        print(f"{Fore.CYAN}🔧 Режим STT: {mode}")


# ==================== Інтеграція з GUI ====================

class STTGuiController:
    """Контролер для інтеграції STT в GUI."""

    def __init__(self, process_command_callback: Callable[[str], None]):
        self.listener = STTListener(
            command_callback=process_command_callback,
            status_callback=self._on_status_change
        )

        self.current_status = "idle"  # idle, listening, processing, executing
        self.last_recognized_text = ""

    def initialize(self) -> bool:
        """Ініціалізувати STT."""
        return self.listener.initialize()

    def toggle_listening(self) -> Optional[str]:
        """Перемкнути стан слухання (для кнопки в GUI)."""
        if self.current_status == "listening":
            return None

        text = self.listener.listen_once()
        return text

    def start_wake_word_mode(self):
        """Запустити wake word режим."""
        self.listener.set_wake_word_enabled(True)
        self.listener.start(wake_word_mode=True)

    def stop(self):
        """Зупинити."""
        self.listener.stop()

    def _on_status_change(self, status: str, data: Any = None):
        """Обробник зміни статусу."""
        self.current_status = status

        if status == "recognized" and data:
            self.last_recognized_text = data.get("text", "")

        # Можна додати callback для оновлення UI тут
        # Наприклад: gui_update_callback(status, data)


# ==================== Функція для aaa_*.py ====================

def get_stt_controller(process_command_callback: Callable[[str], None]) -> Optional[STTGuiController]:
    """Створити STT контролер (для інтеграції в main.py)."""
    try:
        controller = STTGuiController(process_command_callback)
        if controller.initialize():
            return controller
        return None
    except Exception as e:
        print(f"{Fore.RED}❌ Не вдалося створити STT контролер: {e}")
        return None
