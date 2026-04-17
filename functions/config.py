# functions/config.py
"""Глобальні налаштування"""

# ⚡ Асистент
ASSISTANT_NAME = "Марк"
ASSISTANT_EMOJI = "⚡"
ASSISTANT_DISPLAY_NAME = f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}"

# Режими роботи
ASSISTANT_MODES = {
    "terse": {
        "max_words": 5,
        "max_sentences": 1,
        "style": "мінімум слів, тільки суть",
        "examples": ["Готово.", "Відкрив.", "Не знайдено.", "Слухаю."]
    },
    "normal": {
        "max_words": 10,
        "max_sentences": 2,
        "style": "коротка нормальна розмова",
        "examples": ["Блокнот відкрито.", "Програму не знайдено. Вкажіть назву."]
    },
    "verbose": {
        "max_words": 20,
        "max_sentences": 3,
        "style": "детальні пояснення",
        "examples": ["Я відкрив блокнот для вас."]
    }
}

ACTIVE_MODE = "verbose"

# Режим агента: "voice" (звичайний голосовий) або "coding" (агент для коду)
AGENT_MODE = "voice"

# Аудіо
SAMPLE_RATE = 16000
LISTEN_DURATION = 5
VOLUME_THRESHOLD = 0.003
MICROPHONE_DEVICE_ID = 1

# Активація (застаріло)
ACTIVATION_WORD = "марк"
ACTIVATION_LISTEN_DURATION = 1.5
COMMAND_LISTEN_DURATION = 4
ACTIVATION_SIMILARITY_THRESHOLD = 0.75

# TTS префікси
TTS_SPEAK_PREFIXES = [f"{ASSISTANT_DISPLAY_NAME}:", f"{ASSISTANT_NAME}:"]

# Безперервне прослуховування
CONTINUOUS_MODE = {
    "chunk_duration": 4.0,
    "overlap_duration": 0.0,
    "min_volume": 0.09,
    "sound_threshold": 0.1,
    "command_cooldown": 1.0,
}

CONTINUOUS_LISTENING_ENABLED = False  # Увімкнути безперервне прослуховування (експериментально)
# Модель розпізнавання мови (Speech-to-Text)
STT_MODEL_TYPE = "both"  # "whisper", "w2v-bert", або "both"
STT_MODEL_ID = "large-v3"       # Для whisper: tiny, base, small, medium, large-v3
                            # Для w2v-bert: "Yehor/w2v-bert-uk-v2.1"
STT_LANGUAGE = "uk"         # Мова для розпізнавання
STT_PARALLEL_ENABLED = True  # Паралельне використання моделей для перевірки
STT_CONFIDENCE_THRESHOLD = 0.6  # Поріг впевненості для вибору результатів

# Пристрій для STT - визначатиметься динамічно
STT_DEVICE = "cuda"  # Може бути "cuda", "cpu" або "auto"

# Налаштування Whisper
WHISPER_COMPUTE_TYPE = "float16"  # float16 для RTX 5060 Ti
WHISPER_BATCH_SIZE = 8

# Налаштування w2v-bert-uk
W2V_BERT_MODEL_NAME = "Yehor/w2v-bert-uk-v2.1"

# ==================== TTS НАЛАШТУВАННЯ ====================
TTS_ENABLED = True                     # Увімкнути/вимкнути TTS
TTS_DEVICE = "cuda"                     # "cpu" або "cuda"
TTS_CACHE_DIR = "tts_cache"            # Кеш аудіо
TTS_VOICES_DIR = "voices"              # 🔥 ВАЖЛИВО: папка з .pt файлами голосів
TTS_DEFAULT_VOICE = "default"          # Назва голосу (без .pt)
TTS_SPEECH_RATE = 0.88                  # Швидкість (0.7-1.3)
TTS_VOLUME = 1.0                       # Гучність (0.0-1.0)
TTS_SPEAK_PREFIXES = ["⚡ Марк:", "Марк:"]  # Префікси для озвучення
TTS_MODEL_DIR = "voices"


# LLM (legacy: використовується лише якщо LLM_ENDPOINTS пустий)
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

# ==================== MULTI-LLM ENDPOINTS ====================
# Список LLM-моделей. Перший enabled=True з role="primary" — основна.
# Role:
#   primary    — основна модель для простих запитів
#   secondary  — додаткова; викликається паралельно для planner-задач
#   fallback   — запасна на випадок відмови primary
#   alternative — нестандартна (скрипт .py/.bat, результат читається з файлу)
#
# Type:
#   openai_compatible — стандартний HTTP POST (LM Studio, OpenAI, Ollama OpenAI-API, ...)
#   script            — локальний скрипт; результат пишеться у `альтернатива.txt`
#
# Rate limit (тільки для слотів 1-3):
#   mode="unlimited" — без обмежень
#   mode="rpm"       — макс. запитів за хвилину (sliding window)
#   mode="total"     — макс. запитів за сесію
LLM_ENDPOINTS = [
    {
        "id": "llm1",
        "name": "LM Studio (локальна)",
        "enabled": True,
        "role": "primary",
        "type": "openai_compatible",
        "url": "http://localhost:1234/v1/chat/completions",
        "model": "local-model",
        "api_key": "",
        "temperature": 0.1,
        "max_tokens": 1024,
        "timeout": 60,
        "script_command": "",
        "script_output_file": "альтернатива.txt",
        "rate_limit_mode": "unlimited",  # unlimited | rpm | total
        "rate_limit_rpm": 60,
        "rate_limit_total": 10000,
    },
    {
        "id": "llm2",
        "name": "Додаткова модель #2",
        "enabled": False,
        "role": "secondary",
        "type": "openai_compatible",
        "url": "",
        "model": "",
        "api_key": "",
        "temperature": 0.1,
        "max_tokens": 1024,
        "timeout": 60,
        "script_command": "",
        "script_output_file": "альтернатива.txt",
        "rate_limit_mode": "rpm",
        "rate_limit_rpm": 20,
        "rate_limit_total": 500,
    },
    {
        "id": "llm3",
        "name": "Додаткова модель #3",
        "enabled": False,
        "role": "secondary",
        "type": "openai_compatible",
        "url": "",
        "model": "",
        "api_key": "",
        "temperature": 0.1,
        "max_tokens": 1024,
        "timeout": 60,
        "script_command": "",
        "script_output_file": "альтернатива.txt",
        "rate_limit_mode": "rpm",
        "rate_limit_rpm": 20,
        "rate_limit_total": 500,
    },
    {
        "id": "llm4",
        "name": "Резервна модель #4",
        "enabled": False,
        "role": "fallback",
        "type": "openai_compatible",
        "url": "",
        "model": "",
        "api_key": "",
        "temperature": 0.1,
        "max_tokens": 1024,
        "timeout": 60,
        "script_command": "",
        "script_output_file": "альтернатива.txt",
        "rate_limit_mode": "unlimited",
        "rate_limit_rpm": 60,
        "rate_limit_total": 1000,
    },
    {
        "id": "llm5",
        "name": "Альтернативний скрипт",
        "enabled": False,
        "role": "alternative",
        "type": "script",
        "url": "",
        "model": "",
        "api_key": "",
        "temperature": 0.1,
        "max_tokens": 1024,
        "timeout": 120,
        "script_command": "python alternative_llm.py",
        "script_output_file": "альтернатива.txt",
        "rate_limit_mode": "unlimited",
        "rate_limit_rpm": 60,
        "rate_limit_total": 1000,
    },
]

# Стратегія для planner-задач (коли потрібен багатокроковий план):
#   "single"   — викликати тільки primary модель
#   "parallel" — викликати primary + усі secondary одночасно, взяти найшвидший валідний план
LLM_PLANNER_STRATEGY = "single"

# Фільтрація команд
MIN_COMMAND_LENGTH = 3
IGNORE_PHRASES = {
    "дякую", "Дякуємо!", "спасибі", "дякую за перегляд",
    "так", "ні", "ну", "ага", "угу", "ок", "окей",
}

# Виправлення помилок розпізнавання
WHISPER_CORRECTIONS = {
    "з крейп": "відкрий",
    "відкрай": "відкрий",
    "відкри": "відкрий",
    "вікрив": "відкрий",
    "мікрий": "відкрий",
    "блокнат": "блокнот",
    "блокма": "блокнот",
}

# Аудіо фільтри
AUDIO_FILTER_SETTINGS = {
    "use_deepfilter": True,
    "use_vad": False,
    "vad_threshold": 0.003,
    "bandpass_low": 100,
    "bandpass_high": 7500,
    "compression_threshold": -20,
    "compression_ratio": 3.0,
    "compression_makeup": 4,
}
# ==================== AGC & RNNoise НАЛАШТУВАННЯ ====================
# Автоматична регулювання гучності
AGC_ENABLED = True                      # Увімкнути AGC
AGC_TARGET_VOLUME = 0.05                # Цільова гучність (0.01-0.1)
AGC_MAX_GAIN = 50.0                     # Макс підсилення (x50)
AGC_ATTACK_TIME = 0.05                  # Швидкість реакції (сек)

# RNNoise шумодав
RNNOISE_ENABLED = True                  # Увімкнути RNNoise

# Бустинг для різних моделей
WHISPER_VOLUME_BOOST = 3.0              # Whisper не любить сильного бусту
W2V_BERT_VOLUME_BOOST = 50.0            # w2v-bert потрібен сильний буст

# Оновити AUDIO_FILTER_SETTINGS
AUDIO_FILTER_SETTINGS = {
    "use_agc": True,
    "use_rnnoise": True,
    "target_volume": AGC_TARGET_VOLUME,
    "max_gain": AGC_MAX_GAIN,
}
