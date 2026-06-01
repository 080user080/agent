"""Базові тести для tools_comfyui.py (Phase 10)."""
from __future__ import annotations

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from functions.tools_comfyui import (
    REQUESTS_AVAILABLE,
    ComfyUIClient,
    create_comfyui_client,
)


class TestComfyUIAvailability:
    """Тести доступності requests."""

    def test_requests_available_flag(self):
        """Перевірити флаг доступності requests."""
        assert isinstance(REQUESTS_AVAILABLE, bool)


class TestComfyUIClient:
    """Тести класу ComfyUIClient."""

    def test_create_client(self):
        """Створення клієнта."""
        client = ComfyUIClient("http://127.0.0.1:8188")
        assert client.base_url == "http://127.0.0.1:8188"
        assert client.client_id == "agent_comfyui_client"

    def test_create_client_custom_url(self):
        """Створення клієнта з кастомним URL."""
        client = ComfyUIClient("http://192.168.1.100:8188")
        assert client.base_url == "http://192.168.1.100:8188"

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_check_connection_without_requests(self):
        """Перевірка з'єднання без requests."""
        client = ComfyUIClient()
        result = client.check_connection()
        assert result["success"] is False
        assert "requests" in result["error"].lower()

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_get_queue_info_without_requests(self):
        """Отримання інформації про чергу без requests."""
        client = ComfyUIClient()
        result = client.get_queue_info()
        assert result["success"] is False
        assert "requests" in result["error"].lower()

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_get_history_without_requests(self):
        """Отримання історії без requests."""
        client = ComfyUIClient()
        result = client.get_history()
        assert result["success"] is False
        assert "requests" in result["error"].lower()

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_upload_image_without_requests(self):
        """Завантаження зображення без requests."""
        client = ComfyUIClient()
        result = client.upload_image("test.png")
        assert result["success"] is False
        assert "requests" in result["error"].lower()

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_upload_image_nonexistent_file(self):
        """Завантаження неіснуючого файлу."""
        with patch("functions.tools_comfyui.REQUESTS_AVAILABLE", True):
            client = ComfyUIClient()
            result = client.upload_image("nonexistent.png")
            assert result["success"] is False
            assert "не знайдено" in result["error"].lower()

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_get_view_metadata_without_requests(self):
        """Отримання метаданих без requests."""
        client = ComfyUIClient()
        result = client.get_view_metadata("test.png")
        assert result["success"] is False
        assert "requests" in result["error"].lower()

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_execute_workflow_without_requests(self):
        """Виконання workflow без requests."""
        client = ComfyUIClient()
        result = client.execute_workflow({})
        assert result["success"] is False
        assert "requests" in result["error"].lower()

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_generate_text_to_image_without_requests(self):
        """Генерація зображень з тексту без requests."""
        client = ComfyUIClient()
        result = client.generate_text_to_image("test prompt")
        assert result["success"] is False
        assert "requests" in result["error"].lower()

    @patch("functions.tools_comfyui.REQUESTS_AVAILABLE", False)
    def test_interrupt_without_requests(self):
        """Переривання без requests."""
        client = ComfyUIClient()
        result = client.interrupt()
        assert result["success"] is False
        assert "requests" in result["error"].lower()


class TestCreateComfyUIClient:
    """Тести функції create_comfyui_client."""

    def test_create_client_function(self):
        """Створення клієнта через функцію."""
        client = create_comfyui_client()
        assert isinstance(client, ComfyUIClient)
        assert client.base_url == "http://127.0.0.1:8188"

    def test_create_client_function_custom_url(self):
        """Створення клієнта через функцію з кастомним URL."""
        client = create_comfyui_client("http://192.168.1.100:8188")
        assert isinstance(client, ComfyUIClient)
        assert client.base_url == "http://192.168.1.100:8188"
