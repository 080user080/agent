"""Vision-LM provider — розуміння UI через LLM з vision capabilities (V2).

Це Phase V2 — провайдер для LLM з image input.
Дозволяє агенту "розуміти" незнайомі UI (ComfyUI, Blender тощо) через аналіз скріншотів.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from functions.runtime.core_settings import get_setting

logger = logging.getLogger("vision_provider")


@dataclass
class VisionQuery:
    """Запит до Vision-LM."""
    image_path: str
    question: str = "Опиши що видно на цьому зображенні"
    context: str = ""  # Додатковий контекст
    max_tokens: int = 500


@dataclass
class VisionResponse:
    """Відповідь від Vision-LM."""
    text: str
    confidence: float = 0.0
    detected_elements: List[str] = None  # ["button", "input", "menu", ...]
    suggested_actions: List[str] = None  # ["click button X", "type in field Y", ...]

    def __post_init__(self):
        if self.detected_elements is None:
            self.detected_elements = []
        if self.suggested_actions is None:
            self.suggested_actions = []


class VisionLMProvider:
    """Провайдер для LLM з vision capabilities.

    MVP — базовий інтерфейс, який можна розширити з:
    - OpenAI GPT-4V
    - Claude 3.5 Sonnet (vision)
    - Google Gemini Pro Vision
    - Локальні vision моделі (LLaVA, etc.)
    """

    def __init__(self, assistant):
        self.assistant = assistant
        self._available = False
        self._init_vision()

    def _init_vision(self):
        """Ініціалізувати vision провайдер."""
        try:
            provider = get_setting("VISION_PROVIDER", "none")
            api_key = get_setting("VISION_API_KEY", "")
            model = get_setting("VISION_MODEL", "gpt-4-vision-preview")

            if provider == "none":
                logger.info("Vision-LM вимкнено в налаштуваннях")
                self._available = False
                return

            if provider == "openai":
                self.endpoint = "https://api.openai.com/v1/chat/completions"
                self.provider_type = "openai"
            elif provider == "claude":
                self.endpoint = "https://api.anthropic.com/v1/messages"
                self.provider_type = "claude"
            elif provider == "gemini":
                self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                self.provider_type = "gemini"
            else:
                logger.warning("Невідомий vision провайдер: %s", provider)
                self._available = False
                return

            self.api_key = api_key
            self.model = model

            if not api_key:
                logger.warning("Vision-LM недоступний: не вказано API ключ")
                self._available = False
                return

            self._available = True
            logger.info("Vision-LM ініціалізовано: %s з моделлю %s", provider, model)
        except Exception as e:
            logger.warning("Vision-LM недоступний: %s", e)
            self._available = False

    def is_available(self) -> bool:
        """Перевірити чи vision-LM доступний."""
        return self._available

    def analyze_image(self, query: VisionQuery) -> VisionResponse:
        """Аналізувати зображення через Vision-LM."""
        if not self._available:
            return VisionResponse(
                text="Vision-LM недоступний",
                confidence=0.0,
            )

        try:
            # Кодуємо зображення в base64
            with open(query.image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            if self.provider_type == "openai":
                return self._analyze_openai(image_data, query)
            elif self.provider_type == "claude":
                return self._analyze_claude(image_data, query)
            elif self.provider_type == "gemini":
                return self._analyze_gemini(image_data, query)
            else:
                return VisionResponse(
                    text="Невідомий провайдер",
                    confidence=0.0,
                )
        except Exception as e:
            logger.error("Помилка аналізу зображення: %s", e)
            return VisionResponse(
                text=f"Помилка: {e}",
                confidence=0.0,
            )

    def _analyze_openai(self, image_data: str, query: VisionQuery) -> VisionResponse:
        """Аналіз через OpenAI GPT-4V."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query.question},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        },
                    ],
                }
            ],
            "max_tokens": query.max_tokens,
        }

        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        text = data["choices"][0]["message"]["content"]

        return VisionResponse(text=text, confidence=0.8)

    def _analyze_claude(self, image_data: str, query: VisionQuery) -> VisionResponse:
        """Аналіз через Claude 3.5 Sonnet (vision)."""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "max_tokens": query.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query.question},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                    ],
                }
            ],
        }

        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        text = data["content"][0]["text"]

        return VisionResponse(text=text, confidence=0.8)

    def _analyze_gemini(self, image_data: str, query: VisionQuery) -> VisionResponse:
        """Аналіз через Google Gemini Pro Vision."""
        headers = {"Content-Type": "application/json"}

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": query.question},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_data,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": query.max_tokens},
        }

        url = f"{self.endpoint}?key={self.api_key}"
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        return VisionResponse(text=text, confidence=0.8)

    def detect_ui_elements(self, image_path: str) -> List[Dict[str, Any]]:
        """Детектувати UI елементи на скріншоті.

        Returns:
            [{"type": "button", "name": "Submit", "rect": {...}}, ...]
        """
        if not self._available:
            return []

        query = VisionQuery(
            image_path=image_path,
            question="Опиши всі UI елементи які видно: кнопки, поля вводу, меню, текст. Для кожного вкажи тип, ім'я та приблизну позицію.",
        )

        response = self.analyze_image(query)

        # TODO: Парсинг відповіді для витягування структурованих даних
        # Для MVP повертаємо пустий список
        return []

    def suggest_actions(self, image_path: str, goal: str) -> List[str]:
        """Запропонувати дії для досягнення цілі на основі UI.

        Args:
            image_path: шлях до скріншоту
            goal: мета (наприклад, "відправити форму", "знайти кнопку налаштувань")

        Returns:
            ["click на кнопку X", "ввести текст в поле Y", ...]
        """
        if not self._available:
            return []

        query = VisionQuery(
            image_path=image_path,
            question=f"Що треба зробити щоб: {goal}? Опиши конкретні дії.",
        )

        response = self.analyze_image(query)

        # TODO: Парсинг відповіді для витягування дій
        # Для MVP повертаємо пустий список
        return response.suggested_actions


# ─── Singleton instance ────────────────────────────────────────────────────────

_vision_instance: Optional[VisionLMProvider] = None


def get_vision_provider(assistant) -> VisionLMProvider:
    """Отримати singleton Vision-LM provider."""
    global _vision_instance
    if _vision_instance is None:
        _vision_instance = VisionLMProvider(assistant)
    return _vision_instance


# ─── LLM tools ─────────────────────────────────────────────────────────────────

def vision_analyze_screenshot(args: Dict[str, Any]) -> Dict[str, Any]:
    """Аналізувати скріншот через Vision-LM.

    Args:
        args: {"image_path": "...", "question": "optional question"}

    Returns:
        {"ok": bool, "text": "...", "error": "..."}
    """
    # Ця функція викликається з tool_runtime, тому треба використовувати singleton
    # Для MVP повертаємо заглушку — треба передати assistant ззовні
    return {"ok": False, "error": "Vision-LM потребує ініціалізації через get_vision_provider(assistant)"}


def vision_detect_ui(args: Dict[str, Any]) -> Dict[str, Any]:
    """Детектувати UI елементи на скріншоті.

    Args:
        args: {"image_path": "..."}

    Returns:
        {"ok": bool, "elements": [...], "error": "..."}
    """
    # TODO: Реалізація через get_vision_provider
    return {"ok": False, "error": "Not implemented yet"}


def vision_suggest_actions(args: Dict[str, Any]) -> Dict[str, Any]:
    """Запропонувати дії для досягнення цілі.

    Args:
        args: {"image_path": "...", "goal": "..."}

    Returns:
        {"ok": bool, "actions": [...], "error": "..."}
    """
    # TODO: Реалізація через get_vision_provider
    return {"ok": False, "error": "Not implemented yet"}
