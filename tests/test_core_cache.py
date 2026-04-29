"""Тести для functions/core_cache.py (CacheManager).

Перевіряє:
- Ідемпотентність — set() відхиляє небезпечні дії.
- Life-cycle записів: set → get → expiry.
- Статистика та clear().
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.core_cache import CacheManager  # noqa: E402


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """CacheManager із тимчасовим файлом зберігання."""
    registry = MagicMock()
    registry.get_tool_risk.return_value = "low"

    # Перенаправляємо cache_file у tmp_path, щоб не чіпати репо.
    monkeypatch.setattr(
        "functions.core_cache.Path",
        lambda *args, **kwargs: Path(*args, **kwargs),
    )
    cm = CacheManager(registry=registry, cache_duration_hours=24)
    cm.cache_file = tmp_path / "cache_data.json"
    cm.cache = {}
    return cm


class TestIdempotencyGuard:
    def test_set_rejects_non_idempotent_action(self, cache):
        """set() з action із чорного списку → False."""
        assert cache.set("Створи файл test.txt", "ok", action="create_file") is False
        assert cache.cache == {}

    def test_set_accepts_idempotent_action(self, cache):
        """set() з idempotent action → True + збережено."""
        assert cache.set("порахуй 2+2", "4", action="execute_python") is True
        assert "порахуй 2+2" in cache.cache

    def test_set_rejects_without_idempotent_keyword(self, cache):
        """Без action/keyword → False (консервативно)."""
        # "зроби щось" не потрапляє ні в IDEMPOTENT_ACTIONS, ні в keyword-list
        assert cache.set("зроби щось цікаве", "результат") is False

    def test_set_accepts_keyword_based(self, cache):
        """Ключові слова ('пошук', 'count', ...) → приймаємо."""
        assert cache.set("знайди 'foo' у файлі", "found at line 10") is True


class TestGetSetRoundtrip:
    def test_get_miss_returns_none_false(self, cache):
        response, cached = cache.get("unknown")
        assert response is None
        assert cached is False

    def test_get_hit_after_set(self, cache):
        cache.set("порахуй sum(range(10))", "45", action="execute_python")
        response, cached = cache.get("порахуй sum(range(10))")
        assert cached is True
        assert response == "45"

    def test_get_increments_hits_counter(self, cache):
        cache.set("обчисли 2+2", "4", action="execute_python")
        cache.get("обчисли 2+2")
        cache.get("обчисли 2+2")
        entry = cache.cache["обчисли 2+2"]
        assert entry["hits"] == 2

    def test_get_expired_entry_removed(self, cache):
        """Прострочений запис видаляється під час get()."""
        cache.set("порахуй 1+1", "2", action="execute_python")
        key = "порахуй 1+1"
        # Зробимо timestamp старшим за cache_duration
        cache.cache[key]["timestamp"] = (
            datetime.now() - timedelta(hours=48)
        ).isoformat()

        response, cached = cache.get(key)
        assert response is None
        assert cached is False
        assert key not in cache.cache


class TestStatsAndClear:
    def test_empty_stats(self, cache):
        assert cache.get_stats() == {"entries": 0, "hits": 0}

    def test_stats_counts_entries_and_hits(self, cache):
        cache.set("порахуй 1", "1", action="execute_python")
        cache.set("порахуй 2", "2", action="execute_python")
        cache.get("порахуй 1")
        cache.get("порахуй 1")
        stats = cache.get_stats()
        assert stats["entries"] == 2
        assert stats["hits"] == 2

    def test_clear_removes_all_entries(self, cache):
        cache.set("порахуй a", "A", action="execute_python")
        cache.set("порахуй b", "B", action="execute_python")
        removed = cache.clear()
        assert removed == 2
        assert cache.cache == {}


class TestExtractActionFromCommand:
    @pytest.mark.parametrize("text,expected", [
        ("порахуй кількість", "execute_python"),
        ("обчисли площу", "execute_python"),
        ("count words in file", "count_words"),
        ("search for pattern", "search_in_text"),
        ("відкрий ютуб", None),
    ])
    def test_extract(self, cache, text, expected):
        assert cache._extract_action_from_command(text) == expected
