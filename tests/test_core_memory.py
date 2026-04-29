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
        assert session.counters["commands"] == 0
        assert session.counters["errors"] == 0
        assert session.counters["plans"] == 0
        assert session.active_files == []
        assert session.current_task is None

    def test_track_command_increments_count(self):
        """track_command збільшує лічильник."""
        session = SessionMemory()
        session.track_command()
        session.track_command()
        assert session.counters["commands"] == 2

    def test_track_error_increments_count(self):
        """track_error збільшує лічильник помилок."""
        session = SessionMemory()
        session.track_error()
        assert session.counters["errors"] == 1

    def test_add_active_file_tracks_unique(self):
        """add_active_file відстежує унікальні шляхи."""
        session = SessionMemory()
        session.add_active_file("/path/to/file1.txt")
        session.add_active_file("/path/to/file2.txt")
        session.add_active_file("/path/to/file1.txt")  # Дублікат
        assert len(session.active_files) == 2

    def test_snapshot_returns_full_state(self):
        """snapshot() повертає повний стан сесії."""
        session = SessionMemory()
        session.track_command()
        session.track_command()
        session.track_error()
        session.add_active_file("test.txt")
        session.set_current_task("Тестова задача")

        snap = session.snapshot()
        assert snap["counters"]["commands"] == 2
        assert snap["counters"]["errors"] == 1
        assert snap["active_files"] == ["test.txt"]
        assert snap["current_task"] == "Тестова задача"
        assert "session_id" in snap
        assert "started_at" in snap


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

    def test_init_creates_memory(self, tmp_path):
        """Ініціалізація створює структуру пам'яті."""
        mm = MemoryManager(storage_path=tmp_path / "memory.json")
        assert mm.memory is not None
        assert "history" in mm.memory
        assert "task_summaries" in mm.memory

    def test_start_task_creates_task(self, tmp_path):
        """start_task створює TaskMemory."""
        mm = MemoryManager(storage_path=tmp_path / "memory.json")
        task_id = mm.start_task("Створи файл")
        assert task_id in mm.tasks
        assert mm.current_task_id == task_id

    def test_finish_task_without_llm(self, tmp_path):
        """finish_task працює без LLM caller."""
        mm = MemoryManager(storage_path=tmp_path / "memory.json")
        mm.start_task("Тестова задача")
        mm.record_task_plan([{"action": "test", "args": {}}])
        mm.record_task_step({
            "action": "test",
            "status": "ok",
            "result": "success"
        })

        finished = mm.finish_task("success")
        assert finished is not None
        assert finished.status == "success"

    def test_history_empty_by_default(self, tmp_path):
        """Без update_task історія порожня."""
        mm = MemoryManager(storage_path=tmp_path / "memory.json")
        assert mm.memory["history"] == []

    def test_update_task_appends_to_history(self, tmp_path):
        """update_task додає запис до history."""
        mm = MemoryManager(storage_path=tmp_path / "memory.json")
        mm.update_task("задача 1", [{"action": "a"}], [{"status": "ok"}])
        mm.update_task("задача 2", [{"action": "b"}], [{"status": "ok"}])

        history = mm.memory["history"]
        assert len(history) == 2
        assert history[-1]["task"] == "задача 2"
        assert mm.memory["last_task"] == "задача 2"

    def test_history_capped_at_20(self, tmp_path):
        """History обмежена 20 елементами."""
        mm = MemoryManager(storage_path=tmp_path / "memory.json")
        for i in range(25):
            mm.update_task(f"задача {i}", [], [])
        assert len(mm.memory["history"]) == 20
        assert mm.memory["history"][-1]["task"] == "задача 24"

    def test_fallback_summary(self, tmp_path):
        """fallback summary працює без LLM."""
        mm = MemoryManager(storage_path=tmp_path / "memory.json")
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

        # Перевірка сесії: start_task збільшує лічильник планів
        assert mm.session.counters["plans"] >= 1
        assert mm.session.current_task == "Створи калькулятор"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
