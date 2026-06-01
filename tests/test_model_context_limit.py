"""Тести для get_model_context_limit та пов'язаних функцій.
    
Задача 2: Знати ліміт контексту активної моделі.

Перевіряємо:
- get_model_context_limit() для відомих моделей (точний збіг)
- get_model_context_limit() для часткових збігів (префікс, вкладена назва)
- get_model_context_limit() для невідомих моделей (дефолт)
- fetch_local_model_context_limit() з підставленими даними
- SettingsManager.set_active_model() / get_active_model() / get_active_model_context_limit()
"""
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from functions.llm.endpoint_client import (
    KNOWN_MODEL_CONTEXT_LIMITS,
    _DEFAULT_CONTEXT_LIMIT,
    get_model_context_limit,
    fetch_local_model_context_limit,
)
from functions.runtime.core_settings import SettingsManager


# =============================================================================
# get_model_context_limit — точний збіг
# =============================================================================


class TestGetModelContextLimitExact:
    """Перевірка точного збігу з відомими моделями."""

    @pytest.mark.parametrize("model,expected", [
        ("gpt-4o", 128000),
        ("gpt-4o-mini", 128000),
        ("gpt-4-turbo", 128000),
        ("gpt-4", 8192),
        ("gpt-4-32k", 32768),
        ("gpt-3.5-turbo", 16385),
        ("o1", 200000),
        ("o1-mini", 128000),
        ("o3-mini", 200000),
        ("claude-3-5-sonnet", 200000),
        ("claude-3-5-haiku", 200000),
        ("claude-3-opus", 200000),
        ("claude-sonnet-4-6", 200000),
        ("claude-opus-4-5", 200000),
        ("gemini-2.0-flash", 1048576),
        ("gemini-1.5-pro", 1048576),
        ("gemini-3.1-flash-lite-preview", 1048576),
        ("llama-3.3-70b", 131072),
        ("llama-3.1-8b", 131072),
        ("mixtral-8x7b", 32768),
        ("gemma2-9b", 8192),
        ("mistral-large", 128000),
        ("codestral", 256000),
        ("deepseek-chat", 128000),
        ("qwen-2.5-72b", 131072),
        ("phi-4", 16384),
        ("phi-3-mini", 128000),
        ("local-model", 4096),
    ])
    def test_exact_match(self, model: str, expected: int) -> None:
        assert get_model_context_limit(model) == expected


class TestGetModelContextLimitPartial:
    """Перевірка часткового збігу (префікс, вкладена назва)."""

    def test_prefix_match_gpt4o_date(self) -> None:
        """gpt-4o-2024-08-06 має збігтися з gpt-4o."""
        assert get_model_context_limit("gpt-4o-2024-08-06") == 128000

    def test_prefix_match_claude_date(self) -> None:
        """claude-3-5-sonnet-20241022 має збігтися з claude-3-5-sonnet."""
        assert get_model_context_limit("claude-3-5-sonnet-20241022") == 200000

    def test_prefix_match_o1_date(self) -> None:
        """o1-2024-12-17 має збігтися з o1."""
        assert get_model_context_limit("o1-2024-12-17") == 200000

    def test_nested_name_match(self) -> None:
        """meta/llama-3.1-70b містить llama-3.1-70b."""
        assert get_model_context_limit("meta/llama-3.1-70b") == 131072

    def test_nested_name_match_hf(self) -> None:
        """mistralai/Mistral-7B-v0.1 містить mistral-7b."""
        result = get_model_context_limit("mistralai/Mistral-7B-v0.1")
        assert result == 32768

    def test_organization_prefix(self) -> None:
        """openai/gpt-4o має збігтися з gpt-4o."""
        assert get_model_context_limit("openai/gpt-4o") == 128000


class TestGetModelContextLimitUnknown:
    """Перевірка для невідомих / граничних випадків."""

    def test_unknown_model(self) -> None:
        """Невідома модель повертає дефолт."""
        assert get_model_context_limit("some-unknown-model-v1") == _DEFAULT_CONTEXT_LIMIT

    def test_empty_string(self) -> None:
        """Порожній рядок повертає дефолт."""
        assert get_model_context_limit("") == _DEFAULT_CONTEXT_LIMIT

    def test_none(self) -> None:
        """None повертає дефолт."""
        assert get_model_context_limit(None) == _DEFAULT_CONTEXT_LIMIT  # type: ignore

    def test_garbled_name(self) -> None:
        """Випадковий шум не збігається."""
        assert get_model_context_limit("asdf1234!!!") == _DEFAULT_CONTEXT_LIMIT


# =============================================================================
# fetch_local_model_context_limit
# =============================================================================


class TestFetchLocalModelContextLimit:
    """Перевірка fetch_local_model_context_limit з mock-відповідями."""

    @patch("functions.llm.endpoint_client.requests.get")
    def test_openai_compatible_format(self, mock_get: MagicMock) -> None:
        """OpenAI-compatible формат з max_context_length."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4o", "max_context_length": 128000},
            ]
        }
        mock_get.return_value = mock_response

        result = fetch_local_model_context_limit("http://localhost:1234")
        assert result == 128000

    @patch("functions.llm.endpoint_client.requests.get")
    def test_openai_compatible_context_window(self, mock_get: MagicMock) -> None:
        """OpenAI-compatible формат з context_window."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "custom-model", "context_window": 32768},
            ]
        }
        mock_get.return_value = mock_response

        result = fetch_local_model_context_limit("http://localhost:1234/v1/chat/completions")
        assert result == 32768

    @patch("functions.llm.endpoint_client.requests.get")
    def test_ollama_format_no_limit(self, mock_get: MagicMock) -> None:
        """Ollama формат не має ліміту в API — повертає None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b", "details": {"parameter_size": "8B"}},
            ]
        }
        mock_get.return_value = mock_response

        result = fetch_local_model_context_limit("http://localhost:11434")
        assert result is None

    @patch("functions.llm.endpoint_client.requests.get")
    def test_http_error(self, mock_get: MagicMock) -> None:
        """HTTP помилка повертає None."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = fetch_local_model_context_limit("http://localhost:1234")
        assert result is None

    @patch("functions.llm.endpoint_client.requests.get")
    def test_connection_error(self, mock_get: MagicMock) -> None:
        """Помилка з'єднання повертає None."""
        mock_get.side_effect = Exception("Connection refused")

        result = fetch_local_model_context_limit("http://localhost:9999")
        assert result is None

    @patch("functions.llm.endpoint_client.requests.get")
    def test_url_with_slash(self, mock_get: MagicMock) -> None:
        """URL з /chat/completions правильно трансформується в /models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "model", "max_context_length": 16384},
            ]
        }
        mock_get.return_value = mock_response

        result = fetch_local_model_context_limit("http://localhost:1234/v1/chat/completions")
        mock_get.assert_called_once()
        # Перевіряємо, що URL трансформовано правильно
        call_url = mock_get.call_args[0][0]
        assert "chat/completions" not in call_url
        assert call_url.endswith("/models")
        assert result == 16384


# =============================================================================
# SettingsManager — active model
# =============================================================================


class TestSettingsManagerActiveModel:
    """Перевірка збереження/читання активної моделі та її ліміту."""

    def test_set_and_get(self) -> None:
        """set_active_model + get_active_model."""
        mgr = SettingsManager()
        mgr.set_active_model("gpt-4o", 128000)
        assert mgr.get_active_model() == "gpt-4o"
        assert mgr.get_active_model_context_limit() == 128000

    def test_overwrite(self) -> None:
        """Перезапис моделі."""
        mgr = SettingsManager()
        mgr.set_active_model("gpt-4o", 128000)
        mgr.set_active_model("claude-sonnet-4-6", 200000)
        assert mgr.get_active_model() == "claude-sonnet-4-6"
        assert mgr.get_active_model_context_limit() == 200000

    def test_default_when_not_set(self) -> None:
        """Якщо модель не встановлена — повертає None та дефолтний ліміт."""
        mgr = SettingsManager()
        assert mgr.get_active_model() is None
        assert mgr.get_active_model_context_limit() == 4096

    def test_isolation_between_instances(self) -> None:
        """Різні екземпляри SettingsManager ізольовані."""
        mgr1 = SettingsManager()
        mgr2 = SettingsManager()
        mgr1.set_active_model("gpt-4o", 128000)
        assert mgr2.get_active_model() is None  # другий інстанс не бачить runtime першого

    def test_with_get_model_context_limit(self) -> None:
        """Інтеграційна перевірка: get_model_context_limit + SettingsManager."""
        mgr = SettingsManager()
        model_name = "gpt-4o"
        limit = get_model_context_limit(model_name)
        mgr.set_active_model(model_name, limit)
        assert mgr.get_active_model() == "gpt-4o"
        assert mgr.get_active_model_context_limit() == 128000

    def test_with_claude_date_version(self) -> None:
        """Інтеграційна перевірка з версією моделі з датою."""
        mgr = SettingsManager()
        model_name = "claude-3-5-sonnet-20241022"
        limit = get_model_context_limit(model_name)
        mgr.set_active_model(model_name, limit)
        assert mgr.get_active_model() == model_name
        assert mgr.get_active_model_context_limit() == 200000

    def test_reset_after_clear(self) -> None:
        """Після reset система повертається до дефолту."""
        mgr = SettingsManager()
        mgr.set_active_model("gpt-4o", 128000)
        mgr._runtime.clear()
        assert mgr.get_active_model() is None
        assert mgr.get_active_model_context_limit() == 4096