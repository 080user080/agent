"""Базові тести для tools_ffmpeg.py (Phase 10)."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from functions.tools_ffmpeg import (
    check_ffmpeg_available,
    combine_videos,
    convert_video,
    create_thumbnail,
    extract_audio,
    extract_frames,
    get_video_metadata,
    trim_video,
)


@pytest.fixture
def temp_video_path():
    """Створити тимчасовий шлях для відео файлу."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestFFmpegAvailability:
    """Тести доступності ffmpeg."""

    @patch("subprocess.run")
    def test_check_ffmpeg_available_success(self, mock_run):
        """Перевірка доступності ffmpeg (успішно)."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ffmpeg version 5.0.1\n"
        )
        result = check_ffmpeg_available()
        assert result["success"] is True
        assert "ffmpeg version" in result["version"]

    @patch("subprocess.run")
    def test_check_ffmpeg_available_not_found(self, mock_run):
        """Перевірка доступності ffmpeg (не знайдено)."""
        mock_run.return_value = MagicMock(returncode=1)
        result = check_ffmpeg_available()
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()

    @patch("subprocess.run")
    def test_check_ffmpeg_available_exception(self, mock_run):
        """Перевірка доступності ffmpeg (помилка)."""
        mock_run.side_effect = Exception("Command not found")
        result = check_ffmpeg_available()
        assert result["success"] is False
        assert "Помилка перевірки" in result["error"]


class TestGetVideoMetadata:
    """Тести отримання метаданих відео."""

    def test_get_metadata_nonexistent_file(self):
        """Отримання метаданих неіснуючого файлу."""
        result = get_video_metadata("nonexistent.mp4")
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()


class TestConvertVideo:
    """Тести конвертації відео."""

    def test_convert_nonexistent_file(self):
        """Конвертація неіснуючого файлу."""
        result = convert_video("nonexistent.mp4", "output.mp4")
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()


class TestExtractAudio:
    """Тести витягування аудіо."""

    def test_extract_audio_nonexistent_file(self):
        """Витягування аудіо з неіснуючого файлу."""
        result = extract_audio("nonexistent.mp4", "output.mp3")
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()


class TestTrimVideo:
    """Тести обрізки відео."""

    def test_trim_nonexistent_file(self):
        """Обрізка неіснуючого файлу."""
        result = trim_video("nonexistent.mp4", "output.mp4", "00:00:10")
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()

    def test_trim_with_duration(self):
        """Обрізка з тривалістю."""
        result = trim_video("test.mp4", "output.mp4", "00:00:10", duration="00:00:30")
        # Перевіряємо, що функція не падає на валідації параметрів
        assert "error" in result or "success" in result

    def test_trim_with_end_time(self):
        """Обрізка з часом кінця."""
        result = trim_video("test.mp4", "output.mp4", "00:00:10", end_time="00:00:40")
        # Перевіряємо, що функція не падає на валідації параметрів
        assert "error" in result or "success" in result


class TestExtractFrames:
    """Тести витягування кадрів."""

    def test_extract_frames_nonexistent_file(self):
        """Витягування кадрів з неіснуючого файлу."""
        result = extract_frames("nonexistent.mp4", "/tmp/frames", fps=1.0)
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()


class TestCreateThumbnail:
    """Тести створення мініатюр."""

    def test_create_thumbnail_nonexistent_file(self):
        """Створення мініатюри з неіснуючого файлу."""
        result = create_thumbnail("nonexistent.mp4", "thumb.png")
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()


class TestCombineVideos:
    """Тести об'єднання відео."""

    def test_combine_empty_list(self):
        """Об'єднання порожнього списку."""
        result = combine_videos([], "output.mp4")
        assert result["success"] is False
        assert "порожній" in result["error"].lower()

    def test_combine_nonexistent_file(self):
        """Об'єднання з неіснуючим файлом."""
        result = combine_videos(["nonexistent.mp4"], "output.mp4")
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()
