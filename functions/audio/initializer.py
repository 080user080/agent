# functions/audio/initializer.py
"""Ініціалізатор аудіо-підсистеми (STT/TTS).

Капсулює:
- Діагностику мікрофонів
- Smoke-тест запису
- Завантаження STT двигуна
- Ініціалізацію TTS двигуна
- Створення аудіо фільтра
- Створення безперервного слухача

Використовується замість масивного блоку ініціалізації в main.py.
"""
import time
from colorama import Fore, Back, Style

from functions.config import (
    SAMPLE_RATE, LISTEN_DURATION, VOLUME_THRESHOLD,
    ACTIVATION_WORD, ACTIVATION_LISTEN_DURATION, COMMAND_LISTEN_DURATION,
    MICROPHONE_DEVICE_ID, CONTINUOUS_MODE,
    CONTINUOUS_LISTENING_ENABLED,
    ASSISTANT_NAME, ASSISTANT_EMOJI, ASSISTANT_DISPLAY_NAME,
    TTS_ENABLED, TTS_DEVICE, TTS_CACHE_DIR, TTS_VOICES_DIR,
    TTS_DEFAULT_VOICE, TTS_SPEECH_RATE, TTS_VOLUME, TTS_SPEAK_PREFIXES
)
from functions.audio.logic_stt import get_stt_engine
from functions.audio.logic_tts import TTSEngine
from functions.audio.logic_audio_filtering import get_audio_filter
from functions.audio.logic_continuous_listener import create_continuous_listener


def _gui_notify(gui_queue, status_msg: str, chat_msg: str | None = None):
    """Допоміжна функція: відправити статус + чат-повідомлення в GUI."""
    if gui_queue is None:
        return
    gui_queue.put(('update_status', status_msg))
    if chat_msg:
        gui_queue.put(('add_message', ('assistant', chat_msg)))




class AudioInitializer:
    """Менеджер ініціалізації аудіо-підсистеми.

    Замінює масивний блок ініціалізації в AssistantCore.
    Капсулює створення STT, TTS, аудіо-фільтра та безперервного слухача.
    """

    def __init__(self, gui_queue=None):
        self.gui_queue = gui_queue

        # Ініціалізовані компоненти
        self.stt_engine = None
        self.tts_engine = None
        self.audio_filter = None
        self.listener = None

        # Час завантаження
        self.stt_load_time = 0.0
        self.tts_load_time = 0.0

    # ── Діагностика ───────────────────────────────────────

    def diagnostics(self):
        """Діагностика мікрофона (вимкнена для прискорення запуску)."""
        pass

    # ── STT ────────────────────────────────────────────────

    def _load_stt_model(self):
        """Завантажити STT двигун (внутрішній метод)."""
        try:
            stt_engine = get_stt_engine()
            available_models = stt_engine.get_available_models()

            if not available_models:
                print(f"{Fore.RED}   ❌ Немає доступних моделей STT")
                raise Exception("Не вдалося завантажити жодну модель STT")

            print(f"   ✅ Моделі завантажені: {', '.join(available_models)}")
            print(f"   🎯 Пристрій: {stt_engine.device}")

            return stt_engine

        except Exception as e:
            print(f"   ❌ Помилка завантаження моделей STT: {e}")
            raise

    def init_stt(self) -> bool:
        """Ініціалізувати STT двигун.

        Returns:
            True якщо STT готовий (або вимкнено в налаштуваннях),
            False при помилці.
        """
        from functions.runtime.core_settings import get_setting
        stt_enabled = get_setting("STT_ENABLED", False)

        if not stt_enabled:
            print(f"\n{Fore.YELLOW}⏭️  STT вимкнено в налаштуваннях")
            self.stt_engine = None
            return True

        _gui_notify(self.gui_queue,
                    '🔊 Завантаження STT моделей...',
                    '🔊 Завантаження STT моделей... зачекайте')
        print(f"\n{Fore.CYAN}🔊 Завантаження STT моделей...")
        start_time = time.time()

        try:
            self.stt_engine = self._load_stt_model()
            stt_time = time.time() - start_time
            self.stt_load_time = stt_time
            print(f"{Fore.LIGHTBLACK_EX}⏱️  {stt_time:.2f}с")
            _gui_notify(self.gui_queue,
                        f'✅ STT готовий ({stt_time:.1f}с)',
                        f'✅ STT готовий! ({stt_time:.1f}с)')
            return True
        except Exception as e:
            print(f"{Fore.RED}❌ Не вдалося завантажити модель розпізнавання мови")
            print(f"{Fore.RED}   Деталі: {e}")
            _gui_notify(self.gui_queue,
                        '❌ Помилка STT',
                        f'❌ Помилка завантаження STT: {e}')
            self.stt_engine = None
            return False

    # ── TTS ────────────────────────────────────────────────

    def init_tts(self) -> bool:
        """Ініціалізувати TTS двигун.

        Returns:
            True якщо TTS готовий (або вимкнено в налаштуваннях),
            False при помилці.
        """
        self.tts_engine = None

        if not TTS_ENABLED:
            print(f"\n{Fore.YELLOW}⚠️  TTS вимкнено в налаштуваннях")
            return True

        _gui_notify(self.gui_queue,
                    '🔊 Ініціалізація TTS двигуна...',
                    '🔊 Ініціалізація TTS двигуна... зачекайте')
        print(f"\n{Fore.CYAN}🔊 Ініціалізація TTS двигуна...")
        start_time = time.time()

        try:
            self.tts_engine = TTSEngine()
            tts_time = time.time() - start_time
            self.tts_load_time = tts_time
            if self.tts_engine.is_ready:
                print(f"{Fore.GREEN}✅ TTS двигун готовий")
                print(f"{Fore.CYAN}   Голоси: {', '.join(self.tts_engine.get_voices())}")
                print(f"{Fore.CYAN}   Швидкість: {self.tts_engine.speech_rate}")
                print(f"{Fore.CYAN}   Гучність: {self.tts_engine.volume}")
                print(f"{Fore.CYAN}   Пристрій: {self.tts_engine.device}")
                print(f"{Fore.LIGHTBLACK_EX}⏱️  {tts_time:.2f}с")
                _gui_notify(self.gui_queue,
                            f'✅ TTS готовий ({tts_time:.1f}с)',
                            f'✅ TTS готовий! ({tts_time:.1f}с)')
                return True
            else:
                print(f"{Fore.RED}❌ TTS двигун не готовий")
                self.tts_engine = None
                _gui_notify(self.gui_queue, '❌ TTS не готовий', '❌ TTS не готовий')
                return False
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка ініціалізації TTS: {e}")
            import traceback
            traceback.print_exc()
            self.tts_engine = None
            _gui_notify(self.gui_queue,
                        '❌ Помилка TTS',
                        f'❌ Помилка ініціалізації TTS: {e}')
            return False

    # ── Аудіо фільтр ──────────────────────────────────────

    def init_audio_filter(self) -> bool:
        """Ініціалізувати аудіо фільтр.

        Returns:
            True завжди (фільтр створюється навіть при помилках).
        """
        print(f"\n{Fore.CYAN}🎛️  Ініціалізація аудіо фільтрів...")
        start_time = time.time()
        try:
            self.audio_filter = get_audio_filter(SAMPLE_RATE)
            filter_time = time.time() - start_time
            print(f"{Fore.LIGHTBLACK_EX}⏱️  {filter_time:.2f}с")
            return True
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Помилка ініціалізації аудіо фільтра: {e}")
            self.audio_filter = None
            return False

    # ── Безперервний слухач ───────────────────────────────

    def init_listener(self) -> bool:
        """Створити безперервного слухача (якщо увімкнено).

        Returns:
            True якщо слухач створено (або вимкнено в налаштуваннях),
            False при помилці (якщо слухач потрібен, але не створено).
        """
        if not CONTINUOUS_LISTENING_ENABLED:
            self.listener = None
            return False  # not needed, caller should handle this

        print(f"\n{Fore.CYAN}🎧 Створення безперервного слухача...")
        try:
            self.listener = create_continuous_listener(
                SAMPLE_RATE,
                self.audio_filter,
                MICROPHONE_DEVICE_ID,
                CONTINUOUS_MODE
            )
            if not self.listener:
                print(f"{Fore.RED}❌ Не вдалося створити слухача")
                return False
            return True
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка створення слухача: {e}")
            self.listener = None
            return False

    # ── Повна ініціалізація (мастер-метод) ────────────────

    def init_all(self, with_listener: bool = False) -> dict:
        """Повна ініціалізація аудіо-підсистеми.

        Args:
            with_listener: Якщо True — створити безперервного слухача.

        Returns:
            dict з ключами:
                stt_engine, tts_engine, audio_filter, listener,
                stt_load_time, tts_load_time,
                success (bool)
        """
        success = True

        # Діагностика
        self.diagnostics()

        # STT
        if not self.init_stt():
            success = False

        # Аудіо фільтр
        self.init_audio_filter()

        # TTS
        if not self.init_tts():
            success = False

        # Безперервний слухач
        if with_listener:
            if not self.init_listener():
                success = False

        return {
            "stt_engine": self.stt_engine,
            "tts_engine": self.tts_engine,
            "audio_filter": self.audio_filter,
            "listener": self.listener,
            "stt_load_time": self.stt_load_time,
            "tts_load_time": self.tts_load_time,
            "success": success,
        }