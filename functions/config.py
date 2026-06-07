# functions/config.py
"""Глобальні налаштування — типізовані константи (Phase 8.1).

Кожна підсистема згрупована в окремий dataclass/TypedDict для
кращої автодоповнюваності та валідації. Зворотня сумісність
зберігається: всі змінні доступні як модульні атрибути.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Асистент
# ═══════════════════════════════════════════════════════════════════════════════

ASSISTANT_NAME: str = "Марк"
ASSISTANT_EMOJI: str = "⚡"
ASSISTANT_DISPLAY_NAME: str = f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}"

# Режими роботи
ASSISTANT_MODES: Dict[str, Dict[str, Any]] = {
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

ACTIVE_MODE: str = "verbose"

# Режим агента: "voice" (звичайний голосовий) або "coding" (агент для коду)
AGENT_MODE: str = "voice"


# ═══════════════════════════════════════════════════════════════════════════════
# Аудіо / STT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AudioConfig:
    """Налаштування аудіопідсистеми."""
    sample_rate: int = 16000
    listen_duration: int = 5
    volume_threshold: float = 0.003
    silence_duration: float = 3.0
    min_silence_duration: float = 2.0
    max_silence_duration: float = 8.0
    microphone_device_id: int = 1
    stt_logging_enabled: bool = True


AUDIO: AudioConfig = AudioConfig()

# Залишаємо модульні змінні для зворотної сумісності
SAMPLE_RATE: int = AUDIO.sample_rate
LISTEN_DURATION: int = AUDIO.listen_duration
VOLUME_THRESHOLD: float = AUDIO.volume_threshold
MICROPHONE_DEVICE_ID: int = AUDIO.microphone_device_id
STT_LOGGING_ENABLED: bool = AUDIO.stt_logging_enabled
SILENCE_DURATION: float = AUDIO.silence_duration
MIN_SILENCE_DURATION: float = AUDIO.min_silence_duration
MAX_SILENCE_DURATION: float = AUDIO.max_silence_duration


# Активація (застаріло)
ACTIVATION_WORD: str = "марк"
ACTIVATION_LISTEN_DURATION: float = 1.5
COMMAND_LISTEN_DURATION: int = 4
ACTIVATION_SIMILARITY_THRESHOLD: float = 0.75

# TTS префікси
TTS_SPEAK_PREFIXES: List[str] = [f"{ASSISTANT_DISPLAY_NAME}:", f"{ASSISTANT_NAME}:"]


# Безперервне прослуховування
CONTINUOUS_MODE: Dict[str, float] = {
    "chunk_duration": 4.0,
    "overlap_duration": 0.0,
    "min_volume": 0.09,
    "sound_threshold": 0.1,
    "command_cooldown": 1.0,
}

CONTINUOUS_LISTENING_ENABLED: bool = False

# Модель розпізнавання мови (Speech-to-Text)
STT_ENABLED: bool = True
STT_MODEL_TYPE: str = "both"       # "whisper", "w2v-bert", або "both"
STT_MODEL_ID: str = "large-v3"    # Для whisper: tiny, base, small, medium, large-v3
STT_LANGUAGE: str = "uk"
STT_PARALLEL_ENABLED: bool = True
STT_CONFIDENCE_THRESHOLD: float = 0.6
STT_DEVICE: str = "cuda"          # "cuda", "cpu" або "auto"

# Налаштування Whisper
WHISPER_COMPUTE_TYPE: str = "float16"
WHISPER_BATCH_SIZE: int = 8

# Налаштування w2v-bert-uk
W2V_BERT_MODEL_NAME: str = "Yehor/w2v-bert-uk-v2.1"


# ═══════════════════════════════════════════════════════════════════════════════
# TTS (Text-to-Speech)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TTSConfig:
    """Налаштування TTS підсистеми."""
    enabled: bool = True
    device: str = "cuda"
    cache_dir: str = "tts_cache"
    voices_dir: str = "voices"
    default_voice: str = "default"
    speech_rate: float = 0.88
    volume: float = 1.0
    model_dir: str = "voices"


TTS_CFG: TTSConfig = TTSConfig()

# Залишаємо модульні змінні для зворотної сумісності
TTS_ENABLED: bool = TTS_CFG.enabled
TTS_DEVICE: str = TTS_CFG.device
TTS_CACHE_DIR: str = TTS_CFG.cache_dir
TTS_VOICES_DIR: str = TTS_CFG.voices_dir
TTS_DEFAULT_VOICE: str = TTS_CFG.default_voice
TTS_SPEECH_RATE: float = TTS_CFG.speech_rate
TTS_VOLUME: float = TTS_CFG.volume
TTS_MODEL_DIR: str = TTS_CFG.model_dir
TTS_SPEAK_PREFIXES = [f"{ASSISTANT_DISPLAY_NAME}:", f"{ASSISTANT_NAME}:"]


# ═══════════════════════════════════════════════════════════════════════════════
# Vision-LM
# ═══════════════════════════════════════════════════════════════════════════════

VISION_PROVIDER: str = "none"      # none, openai, claude, gemini
VISION_API_KEY: str = ""
VISION_MODEL: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# LLM Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

# Legacy (використовується лише якщо LLM_ENDPOINTS пустий)
LM_STUDIO_URL: str = "http://localhost:1234/v1/chat/completions"


@dataclass
class LLMEndpoint:
    """Один LLM-ендпоінт."""
    id: str
    name: str
    enabled: bool = False
    role: str = "primary"           # "1", "secondary", "fallback", "alternative"
    type: str = "openai_compatible"  # "openai_compatible" або "script"
    url: str = ""
    model: str = ""
    api_key: str = ""
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout: int = 60
    script_command: str = ""
    script_output_file: str = ""
    rate_limit_mode: str = "unlimited"  # "unlimited", "rpm", "total"
    rate_limit_rpm: int = 60
    rate_limit_total: int = 10000


LLM_ENDPOINTS: List[Dict[str, Any]] = [
    {
        "id": "llm1",
        "name": "Gemini",
        "enabled": True,
        "role": "1",
        "type": "script",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-3.1-flash-lite-preview",
        "api_key": "",
        "temperature": 0.1,
        "max_tokens": 2048,
        "timeout": 60,
        "script_command": "",
        "script_output_file": "",
        "rate_limit_mode": "unlimited",
        "rate_limit_rpm": 60,
        "rate_limit_total": 10000,
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

# Стратегія для planner-задач
LLM_PLANNER_STRATEGY: str = "single"  # "single" або "parallel"


# ═══════════════════════════════════════════════════════════════════════════════
# Фільтрація команд
# ═══════════════════════════════════════════════════════════════════════════════

MIN_COMMAND_LENGTH: int = 3
IGNORE_PHRASES: set = {
    "дякую", "Дякуємо!", "спасибі", "дякую за перегляд",
    "так", "ні", "ну", "ага", "угу", "ок", "окей",
}

# Виправлення помилок розпізнавання
WHISPER_CORRECTIONS: Dict[str, str] = {
    "з крейп": "відкрий",
    "відкрай": "відкрий",
    "відкри": "відкрий",
    "вікрив": "відкрий",
    "мікрий": "відкрий",
    "блокнат": "блокнот",
    "блокма": "блокнот",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Аудіо фільтри
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AudioFilterSettings:
    """Налаштування аудіо-фільтрів."""
    use_agc: bool = True
    use_rnnoise: bool = True
    target_volume: float = 0.05
    max_gain: float = 50.0
    agc_attack_time: float = 0.05


# AGC & RNNoise
AGC_ENABLED: bool = True
AGC_TARGET_VOLUME: float = 0.05
AGC_MAX_GAIN: float = 50.0
AGC_ATTACK_TIME: float = 0.05
RNNOISE_ENABLED: bool = True
WHISPER_VOLUME_BOOST: float = 3.0
W2V_BERT_VOLUME_BOOST: float = 50.0

AUDIO_FILTER_SETTINGS: Dict[str, Any] = {
    "use_agc": AGC_ENABLED,
    "use_rnnoise": RNNOISE_ENABLED,
    "target_volume": AGC_TARGET_VOLUME,
    "max_gain": AGC_MAX_GAIN,
}