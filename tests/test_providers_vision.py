"""Тести для providers_vision.py — Phase V2 (Vision-LM)."""
import base64
import pytest
from unittest.mock import Mock, MagicMock, patch

from functions.llm.providers_vision import (
    VisionQuery,
    VisionResponse,
    VisionLMProvider,
)


class TestVisionQuery:
    """Тести для VisionQuery dataclass."""

    def test_minimal_query(self):
        """Створити мінімальний запит."""
        query = VisionQuery(image_path="/tmp/test.png")
        assert query.image_path == "/tmp/test.png"
        assert query.question == "Опиши що видно на цьому зображенні"
        assert query.context == ""
        assert query.max_tokens == 500

    def test_full_query(self):
        """Створити повний запит."""
        query = VisionQuery(
            image_path="/tmp/test.png",
            question="Що це за кнопка?",
            context="Вікно налаштувань",
            max_tokens=1000,
        )
        assert query.question == "Що це за кнопка?"
        assert query.context == "Вікно налаштувань"
        assert query.max_tokens == 1000


class TestVisionResponse:
    """Тести для VisionResponse dataclass."""

    def test_minimal_response(self):
        """Створити мінімальну відповідь."""
        response = VisionResponse(text="Кнопка Submit")
        assert response.text == "Кнопка Submit"
        assert response.confidence == 0.0
        assert response.detected_elements == []
        assert response.suggested_actions == []

    def test_full_response(self):
        """Створити повну відповідь."""
        response = VisionResponse(
            text="Кнопка Submit",
            confidence=0.9,
            detected_elements=["button", "input"],
            suggested_actions=["click button", "type text"],
        )
        assert response.confidence == 0.9
        assert response.detected_elements == ["button", "input"]
        assert response.suggested_actions == ["click button", "type text"]


class TestVisionLMProvider:
    """Тести для VisionLMProvider."""

    def test_init(self):
        """Ініціалізація провайдера."""
        assistant = Mock()
        provider = VisionLMProvider(assistant)
        assert provider.assistant == assistant
        assert provider._available == False

    @patch("functions.llm.providers_vision.get_setting")
    def test_init_vision_none_provider(self, mock_get_setting):
        """Ініціалізація з provider=none."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "none",
            "VISION_API_KEY": "",
            "VISION_MODEL": "gpt-4-vision-preview",
        }.get(key, default)

        assistant = Mock()
        provider = VisionLMProvider(assistant)
        assert provider._available == False

    @patch("functions.llm.providers_vision.get_setting")
    def test_init_vision_openai_no_api_key(self, mock_get_setting):
        """Ініціалізація з OpenAI але без API ключа."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "openai",
            "VISION_API_KEY": "",
            "VISION_MODEL": "gpt-4-vision-preview",
        }.get(key, default)

        assistant = Mock()
        provider = VisionLMProvider(assistant)
        assert provider._available == False

    @patch("functions.llm.providers_vision.get_setting")
    def test_init_vision_openai_with_api_key(self, mock_get_setting):
        """Ініціалізація з OpenAI та API ключем."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "openai",
            "VISION_API_KEY": "test-key",
            "VISION_MODEL": "gpt-4-vision-preview",
        }.get(key, default)

        assistant = Mock()
        provider = VisionLMProvider(assistant)
        assert provider._available == True
        assert provider.endpoint == "https://api.openai.com/v1/chat/completions"
        assert provider.provider_type == "openai"
        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4-vision-preview"

    @patch("functions.llm.providers_vision.get_setting")
    def test_init_vision_claude(self, mock_get_setting):
        """Ініціалізація з Claude."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "claude",
            "VISION_API_KEY": "test-key",
            "VISION_MODEL": "claude-3-5-sonnet",
        }.get(key, default)

        assistant = Mock()
        provider = VisionLMProvider(assistant)
        assert provider._available == True
        assert provider.endpoint == "https://api.anthropic.com/v1/messages"
        assert provider.provider_type == "claude"

    @patch("functions.llm.providers_vision.get_setting")
    def test_init_vision_gemini(self, mock_get_setting):
        """Ініціалізація з Gemini."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "gemini",
            "VISION_API_KEY": "test-key",
            "VISION_MODEL": "gemini-pro-vision",
        }.get(key, default)

        assistant = Mock()
        provider = VisionLMProvider(assistant)
        assert provider._available == True
        assert provider.provider_type == "gemini"
        assert "generativelanguage.googleapis.com" in provider.endpoint

    def test_is_available(self):
        """Перевірка доступності."""
        assistant = Mock()
        provider = VisionLMProvider(assistant)
        assert provider.is_available() == False

    def test_analyze_image_not_available(self):
        """Аналіз коли провайдер недоступний."""
        assistant = Mock()
        provider = VisionLMProvider(assistant)

        query = VisionQuery(image_path="/tmp/test.png")
        response = provider.analyze_image(query)

        assert response.text == "Vision-LM недоступний"
        assert response.confidence == 0.0

    @patch("functions.llm.providers_vision.get_setting")
    @patch("builtins.open", create=True)
    @patch("functions.llm.providers_vision.requests.post")
    def test_analyze_image_openai_success(self, mock_post, mock_open, mock_get_setting):
        """Успішний аналіз через OpenAI."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "openai",
            "VISION_API_KEY": "test-key",
            "VISION_MODEL": "gpt-4-vision-preview",
        }.get(key, default)

        # Mock file read
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_image_data"
        mock_open.return_value.__enter__.return_value = mock_file

        # Mock API response
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Це кнопка Submit"}}]
        }
        mock_post.return_value.raise_for_status = MagicMock()

        assistant = Mock()
        provider = VisionLMProvider(assistant)

        query = VisionQuery(image_path="/tmp/test.png", question="Що це?")
        response = provider.analyze_image(query)

        assert response.text == "Це кнопка Submit"
        assert response.confidence == 0.8

    @patch("functions.llm.providers_vision.get_setting")
    @patch("builtins.open", create=True)
    @patch("functions.llm.providers_vision.requests.post")
    def test_analyze_image_openai_error(self, mock_post, mock_open, mock_get_setting):
        """Помилка при аналізі через OpenAI."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "openai",
            "VISION_API_KEY": "test-key",
            "VISION_MODEL": "gpt-4-vision-preview",
        }.get(key, default)

        # Mock file read
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_image_data"
        mock_open.return_value.__enter__.return_value = mock_file

        # Mock API error
        mock_post.side_effect = Exception("API Error")

        assistant = Mock()
        provider = VisionLMProvider(assistant)

        query = VisionQuery(image_path="/tmp/test.png")
        response = provider.analyze_image(query)

        assert "Помилка" in response.text
        assert response.confidence == 0.0

    @patch("functions.llm.providers_vision.get_setting")
    def test_detect_ui_elements_not_available(self, mock_get_setting):
        """Детекція UI коли провайдер недоступний."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "none",
        }.get(key, default)

        assistant = Mock()
        provider = VisionLMProvider(assistant)

        elements = provider.detect_ui_elements("/tmp/test.png")
        assert elements == []

    @patch("functions.llm.providers_vision.get_setting")
    def test_suggest_actions_not_available(self, mock_get_setting):
        """Пропозиція дій коли провайдер недоступний."""
        mock_get_setting.side_effect = lambda key, default: {
            "VISION_PROVIDER": "none",
        }.get(key, default)

        assistant = Mock()
        provider = VisionLMProvider(assistant)

        actions = provider.suggest_actions("/tmp/test.png", "відправити форму")
        assert actions == []
