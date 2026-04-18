# functions/core_settings.py
"""Єдина точка доступу до налаштувань асистента.

Структура:
- Базові значення читаються з functions/config.py
- Користувацькі оверрайди зберігаються у user_settings.json (поруч із config.py)
- Runtime-флаги (auto_approve_all) живуть у пам'яті до перезапуску,
  але можуть бути persist-нуті у user_settings.json.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

from . import config as base_config

# Шлях до user-налаштувань
_HERE = os.path.dirname(os.path.abspath(__file__))
USER_SETTINGS_PATH = os.path.join(_HERE, "user_settings.json")

# Схема налаштувань для UI (тип, label, опис, варіанти)
# Тип: bool | int | float | str | choice | readonly
SETTINGS_SCHEMA: Dict[str, Dict[str, Any]] = {
    # --- Асистент ---
    "ASSISTANT_NAME": {
        "type": "str", "group": "Асистент", "label": "Ім'я асистента",
        "desc": "Як звати асистента (використовується у промптах).",
    },
    "ACTIVE_MODE": {
        "type": "choice", "group": "Асистент", "label": "Режим відповідей",
        "choices": ["terse", "normal", "verbose"],
        "desc": "terse — 5 слів, normal — 10, verbose — 20.",
    },
    "AGENT_MODE": {
        "type": "choice", "group": "Асистент", "label": "Режим агента",
        "choices": ["voice", "coding"],
        "desc": "voice — голосовий асистент; coding — агент для коду.",
    },

    # --- Безпека / підтвердження ---
    "auto_approve_all": {
        "type": "bool", "group": "Безпека", "label": "Автопідтвердження всіх дій",
        "desc": "Усі дії, що потребують підтвердження, будуть схвалені автоматично. УВАГА: безпека знижена!",
        "default": True, "user_only": True,
    },
    "auto_approve_expires_ms": {
        "type": "int", "group": "Безпека", "label": "Тайм-аут автопідтвердження (сек, 0=назавжди)",
        "desc": "Скільки секунд тримати 'автопідтвердження' після увімкнення. 0 = до вимкнення вручну.",
        "default": 0, "user_only": True, "min": 0, "max": 3600,
    },

    # --- Продуктивність ---
    "CACHE_ENABLED": {
        "type": "bool", "group": "Продуктивність", "label": "Кешування команд",
        "desc": "Зберігати результати команд і повертати їх миттєво при повторі. УВАГА: може повертати застарілі відповіді після оновлень.",
        "default": False, "user_only": True,
    },
    "CACHE_DURATION_HOURS": {
        "type": "int", "group": "Продуктивність", "label": "Час життя кешу (годин)",
        "desc": "Скільки годин зберігати кешовані відповіді.",
        "default": 24, "user_only": True, "min": 1, "max": 720,
    },

    # --- LLM ---
    "LM_STUDIO_URL": {
        "type": "str", "group": "LLM", "label": "URL LM Studio (legacy)",
        "desc": "Запасний ендпоінт. Використовується, якщо LLM_ENDPOINTS пустий.",
    },
    "LLM_PLANNER_STRATEGY": {
        "type": "choice", "group": "LLM", "label": "Стратегія для planner",
        "choices": ["single", "parallel"],
        "desc": "single — primary модель; parallel — primary + secondary одночасно (fastest wins).",
    },
    "LLM_ENDPOINTS": {
        "type": "llm_endpoints", "group": "LLM Моделі", "label": "LLM-моделі",
        "desc": "До 5 LLM-моделей: primary, secondary (паралельно для planner), fallback, альтернативний скрипт.",
    },

    # --- STT ---
    "STT_MODEL_TYPE": {
        "type": "choice", "group": "Розпізнавання мови", "label": "Тип STT-моделі",
        "choices": ["whisper", "w2v-bert", "both"],
        "desc": "Яку модель використовувати для розпізнавання.",
    },
    "STT_MODEL_ID": {
        "type": "str", "group": "Розпізнавання мови", "label": "ID моделі Whisper",
        "desc": "tiny / base / small / medium / large-v3.",
    },
    "STT_LANGUAGE": {
        "type": "str", "group": "Розпізнавання мови", "label": "Мова",
        "desc": "Код мови (uk, en, ru).",
    },
    "STT_DEVICE": {
        "type": "choice", "group": "Розпізнавання мови", "label": "Пристрій STT",
        "choices": ["cuda", "cpu", "auto"],
        "desc": "GPU (cuda) чи CPU.",
    },
    "STT_CONFIDENCE_THRESHOLD": {
        "type": "float", "group": "Розпізнавання мови", "label": "Поріг впевненості",
        "desc": "0.0–1.0. Нижче цього значення результат відхиляється.",
        "min": 0.0, "max": 1.0,
    },

    # --- Аудіо ---
    "SAMPLE_RATE": {
        "type": "int", "group": "Аудіо", "label": "Sample rate (Hz)",
        "desc": "Частота дискретизації мікрофона. Рекомендовано 16000.",
        "min": 8000, "max": 48000,
    },
    "LISTEN_DURATION": {
        "type": "int", "group": "Аудіо", "label": "Тривалість запису (сек)",
        "desc": "Максимальна тривалість одного запису.",
        "min": 1, "max": 60,
    },
    "VOLUME_THRESHOLD": {
        "type": "float", "group": "Аудіо", "label": "Поріг гучності",
        "desc": "Мінімальна гучність, щоб зафіксувати мову (0.001–0.1).",
        "min": 0.0, "max": 1.0,
    },
    "MICROPHONE_DEVICE_ID": {
        "type": "int", "group": "Аудіо", "label": "ID мікрофона",
        "desc": "Індекс аудіопристрою в системі.",
        "min": 0, "max": 32,
    },
    "CONTINUOUS_LISTENING_ENABLED": {
        "type": "bool", "group": "Аудіо", "label": "Безперервне прослуховування",
        "desc": "Експериментально! Слухає без кнопки активації.",
    },

    # --- TTS ---
    "TTS_ENABLED": {
        "type": "bool", "group": "Озвучення", "label": "Увімкнути TTS",
        "desc": "Голосове озвучення відповідей.",
    },
    "TTS_DEVICE": {
        "type": "choice", "group": "Озвучення", "label": "Пристрій TTS",
        "choices": ["cuda", "cpu"],
        "desc": "GPU чи CPU для синтезу.",
    },
    "TTS_DEFAULT_VOICE": {
        "type": "str", "group": "Озвучення", "label": "Голос (без .pt)",
        "desc": "Назва файлу голосу у папці voices/.",
    },
    "TTS_SPEECH_RATE": {
        "type": "float", "group": "Озвучення", "label": "Швидкість мови",
        "desc": "0.7 (повільно) – 1.3 (швидко).",
        "min": 0.5, "max": 2.0,
    },
    "TTS_VOLUME": {
        "type": "float", "group": "Озвучення", "label": "Гучність",
        "desc": "0.0–1.0.",
        "min": 0.0, "max": 1.0,
    },

    # --- Аудіо-фільтри ---
    "AGC_ENABLED": {
        "type": "bool", "group": "Аудіо-фільтри", "label": "AGC (автогучність)",
        "desc": "Автоматично вирівнювати гучність мікрофона.",
    },
    "AGC_TARGET_VOLUME": {
        "type": "float", "group": "Аудіо-фільтри", "label": "Цільова гучність AGC",
        "desc": "0.01–0.1.",
        "min": 0.0, "max": 1.0,
    },
    "RNNOISE_ENABLED": {
        "type": "bool", "group": "Аудіо-фільтри", "label": "RNNoise шумодав",
        "desc": "Придушення шуму нейромережею.",
    },
}


class SettingsManager:
    """Зчитує/оновлює налаштування поверх `config.py`."""

    def __init__(self):
        self._lock = threading.RLock()
        self._user: Dict[str, Any] = {}
        self._runtime: Dict[str, Any] = {}
        # Зберегти оригінальні дефолти з config.py ДО будь-яких модифікацій
        self._defaults: Dict[str, Any] = {}
        for key in SETTINGS_SCHEMA.keys():
            if hasattr(base_config, key):
                self._defaults[key] = getattr(base_config, key)
        self._load()

    # ---------- базові операції ----------

    def _load(self):
        if os.path.exists(USER_SETTINGS_PATH):
            try:
                with open(USER_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    self._user = json.load(f) or {}
            except (json.JSONDecodeError, OSError):
                self._user = {}
        # Застосувати збережені значення до base_config для модулів,
        # які читають "from .config import X"
        for key, value in self._user.items():
            if hasattr(base_config, key):
                try:
                    setattr(base_config, key, value)
                except (AttributeError, TypeError):
                    pass

    def _save(self):
        try:
            with open(USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._user, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"⚠️ Не вдалося зберегти user_settings.json: {e}")

    # ---------- API ----------

    def get(self, key: str, default: Any = None) -> Any:
        """Повернути поточне значення (runtime > user > config.py > schema default > default)."""
        with self._lock:
            if key in self._runtime:
                return self._runtime[key]
            if key in self._user:
                return self._user[key]
            # config.py
            if hasattr(base_config, key):
                return getattr(base_config, key)
            # SCHEMA default — важливо для user_only ключів (як auto_approve_all)
            schema = SETTINGS_SCHEMA.get(key)
            if schema and "default" in schema:
                return schema["default"]
            return default

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        """Змінити значення. persist=True — зберегти в user_settings.json.

        Також оновлює `base_config` в пам'яті, щоб модулі, що читають
        `from .config import X`, бачили нове значення при наступному імпорті.
        """
        with self._lock:
            if persist:
                self._user[key] = value
                self._save()
            else:
                self._runtime[key] = value

            # Оновити атрибут у config-модулі (не torches user_only ключі)
            if hasattr(base_config, key):
                try:
                    setattr(base_config, key, value)
                except (AttributeError, TypeError):
                    pass

    def set_runtime(self, key: str, value: Any) -> None:
        """Змінити значення тільки на час життя процесу."""
        self.set(key, value, persist=False)

    def reset(self, key: str) -> None:
        """Скинути значення до оригінального дефолту з config.py."""
        with self._lock:
            self._user.pop(key, None)
            self._runtime.pop(key, None)
            # Повернути base_config до оригінального значення
            if key in self._defaults and hasattr(base_config, key):
                try:
                    setattr(base_config, key, self._defaults[key])
                except (AttributeError, TypeError):
                    pass
            self._save()

    def all_known_keys(self):
        """Усі ключі, про які ми знаємо (зі схеми + з user)."""
        keys = set(SETTINGS_SCHEMA.keys())
        keys.update(self._user.keys())
        return sorted(keys)

    def as_dict(self) -> Dict[str, Any]:
        """Дамп поточних значень (для UI)."""
        result = {}
        for key in self.all_known_keys():
            result[key] = self.get(key)
        return result

    # ---------- runtime-флаги для підтвердження ----------

    def is_auto_approve_all(self) -> bool:
        """Чи включено глобальне автопідтвердження."""
        if not self.get("auto_approve_all", False):
            return False
        # Перевіряємо тайм-аут (якщо він заданий)
        expires_at = self._runtime.get("_auto_approve_expires_at")
        if expires_at is not None:
            import time
            if time.time() > expires_at:
                # Сплив
                self.set("auto_approve_all", False, persist=False)
                self._runtime.pop("_auto_approve_expires_at", None)
                return False
        return True

    def enable_auto_approve_all(self, duration_seconds: Optional[int] = None) -> None:
        """Увімкнути автопідтвердження. duration_seconds: 0 або None = до вимкнення."""
        self.set("auto_approve_all", True, persist=False)
        if duration_seconds and duration_seconds > 0:
            import time
            self._runtime["_auto_approve_expires_at"] = time.time() + duration_seconds
        else:
            self._runtime.pop("_auto_approve_expires_at", None)

    def disable_auto_approve_all(self) -> None:
        self.set("auto_approve_all", False, persist=False)
        self._runtime.pop("_auto_approve_expires_at", None)


# --- Singleton ---
_settings: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    global _settings
    if _settings is None:
        _settings = SettingsManager()
    return _settings


def get_setting(key: str, default: Any = None) -> Any:
    """Зручний шорткат."""
    return get_settings().get(key, default)
