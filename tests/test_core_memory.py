"""Тести для core_memory.py

Запуск: python -m pytest tests/test_core_memory.py -v
"""
import pytest
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.core_memory import SessionMemory, TaskMemory, MemoryManager


class TestSessionMemory:
    """Тести для SessionMemory."""

    def test_init_creates_empty_session(self):
        """Сесія створюється порожньою."""
        session = SessionMemory()
        assert session.command_count == 0
        assert session.error_count == 0
        assert session.file_paths == []

    def test_track_command_increments_count(self):
        """track_command збільшує лічильник."""
        session = SessionMemory()
        session.track_command()
        session.track_command()
        assert session.command_count == 2

    def test_track_error_increments_count(self):
        """track_error збільшує лічильник помилок."""
        session = SessionMemory()
        session.track_error()
        assert session.error_count == 1

    def test_add_file_path_tracks_unique(self):
        """add_file_path відстежує унікальні шляхи."""
        session = SessionMemory()
        session.add_file_path("/path/to/file1.txt")
        session.add_file_path("/path/to/file2.txt")
        session.add_file_path("/path/to/file1.txt")  # Дублікат
        assert len(session.file_paths) == 2

    def test_session_stats(self):
        """get_stats повертає правильну статистику."""
        session = SessionMemory()
        session.track_command()
        session.track_command()
        session.track_error()
        session.add_file_path("test.txt")

        stats = session.get_stats()
        assert stats["commands"] == 2
        assert stats["errors"] == 1
        assert len(stats["files_created"]) == 1


class TestTaskMemory:
    """Тести для TaskMemory."""

    def test_task_creation(self):
        """Задача створюється з правильними полями."""
        task = TaskMemory("test_task", "Створи файл test.txt")
        assert task.task_id == "test_task"
        assert task.task_text == "Створи файл test.txt"
        assert task.status == "running"
        assert task.plan == []

    def test_record_step_adds_step(self):
        """record_step додає крок в історію."""
        task = TaskMemory("task1", "test")
        task.record_step({
            "action": "create_file",
            "status": "ok",
            "result": "success"
        })
        assert len(task.step_results) == 1
        assert task.step_results[0]["action"] == "create_file"

    def test_finish_task(self):
        """finish змінює статус задачі."""
        task = TaskMemory("task1", "test")
        task.finish("success")
        assert task.status == "success"
        assert task.finished_at is not None


class TestMemoryManager:
    """Тести для MemoryManager."""

    def test_init_creates_memory(self):
        """Ініціалізація створює структуру пам'яті."""
        mm = MemoryManager()
        assert mm.memory is not None
        assert "history" in mm.memory
        assert "task_summaries" in mm.memory

    def test_start_task_creates_task(self):
        """start_task створює TaskMemory."""
        mm = MemoryManager()
        task_id = mm.start_task("Створи файл")
        assert task_id in mm.tasks
        assert mm.current_task_id == task_id

    def test_finish_task_without_llm(self):
        """finish_task працює без LLM caller."""
        mm = MemoryManager()
        task_id = mm.start_task("Тестова задача")
        mm.record_task_plan([{"action": "test", "args": {}}])
        mm.record_task_step({
            "action": "test",
            "status": "ok",
            "result": "success"
        })

        finished = mm.finish_task("success")
        assert finished is not None
        assert finished.status == "success"

    def test_get_recent_history_empty(self):
        """get_recent_history повертає порожній список без історії."""
        mm = MemoryManager()
        recent = mm.get_recent_history()
        assert recent == []

    def test_get_recent_history_with_items(self):
        """get_recent_history повертає останні items."""
        mm = MemoryManager()
        mm.record_to_history("user", "команда 1")
        mm.record_to_history("assistant", "відповідь 1")
        mm.record_to_history("user", "команда 2")

        recent = mm.get_recent_history(count=2)
        assert len(recent) == 2
        assert recent[0]["role"] == "assistant"

    def test_fallback_summary(self):
        """fallback summary працює без LLM."""
        mm = MemoryManager()
        task = TaskMemory("task1", "Тест")
        task.step_results = [
            {"action": "step1", "status": "ok"},
            {"action": "step2", "status": "error"},
        ]
        task.finish("partial")

        summary = mm._fallback_task_summary(task)
        assert "Кроків: 2" in summary
        assert "успішних: 1" in summary


class TestMemoryIntegration:
    """Інтеграційні тести пам'яті."""

    def test_full_task_lifecycle(self):
        """Повний життєвий цикл задачі."""
        mm = MemoryManager()

        # Старт
        task_id = mm.start_task("Створи калькулятор")
        assert mm.current_task_id == task_id

        # План
        mm.record_task_plan([
            {"action": "create_file", "args": {"filename": "calc.py"}},
            {"action": "execute_python", "args": {"code": "2+2"}},
        ])

        # Кроки
        mm.record_task_step({
            "action": "create_file",
            "status": "ok",
            "result": "Файл створено"
        })
        mm.record_task_step({
            "action": "execute_python",
            "status": "ok",
            "result": "4"
        })

        # Фініш
        task = mm.finish_task("success")
        assert task.status == "success"

        # Перевірка сесії
        assert mm.session.command_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
