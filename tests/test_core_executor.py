"""Тести для core_executor.py

Запуск: python -m pytest tests/test_core_executor.py -v
"""
import pytest
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.core_executor import TaskExecutor


class TestTaskExecutorInit:
    """Тести ініціалізації."""

    def test_executor_init(self):
        """Ініціалізація створює executor з правильними значеннями."""
        executor = TaskExecutor()
        assert executor.is_running is False
        assert executor.progress == 0
        assert executor.status == "Готовий"

    def test_executor_with_callback(self):
        """Executor приймає callback."""
        calls = []
        def callback(msg_type, data):
            calls.append((msg_type, data))

        executor = TaskExecutor(gui_callback=callback)
        assert executor.gui_callback is not None


class TestTaskExecutorBasic:
    """Базові тести виконання."""

    def test_simple_plan_execution(self):
        """Виконання простого плану."""
        executor = TaskExecutor()
        results = []

        def execute_fn(step):
            return {
                "action": step.get("action"),
                "status": "ok",
                "result": f"Executed {step.get('action')}"
            }

        def on_complete(r):
            results.extend(r)

        plan = [
            {"action": "step1", "args": {}},
            {"action": "step2", "args": {}},
        ]

        executor.execute_plan_async(plan, execute_fn, on_complete)
        time.sleep(0.5)  # Дати час на виконання

        assert len(results) == 2
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "ok"

    def test_stop_execution(self):
        """Зупинка виконання."""
        executor = TaskExecutor()
        executor.stop()
        assert executor.stop_requested is True


class TestTaskExecutorStepResults:
    """Тести обробки результатів кроків."""

    def test_error_step_handling(self):
        """Обробка помилки в кроці."""
        executor = TaskExecutor()
        results = []

        def execute_fn(step):
            if step.get("action") == "fail_step":
                return {"action": "fail_step", "status": "error", "result": "Error!"}
            return {"action": step.get("action"), "status": "ok"}

        def on_complete(r):
            results.extend(r)

        plan = [
            {"action": "ok_step", "args": {}},
            {"action": "fail_step", "args": {}},
        ]

        executor.execute_plan_async(plan, execute_fn, on_complete)
        time.sleep(0.5)

        assert results[1]["status"] == "error"

    def test_blocked_step_handling(self):
        """Обробка заблокованого кроку."""
        executor = TaskExecutor()

        def execute_fn(step):
            return {"action": step.get("action"), "status": "blocked"}

        plan = [{"action": "blocked_step", "args": {}}]

        executor.execute_plan_async(plan, execute_fn)
        time.sleep(0.3)


class TestTaskExecutorNotifications:
    """Тести нотифікацій."""

    def test_progress_notifications(self):
        """Перевірка прогресу."""
        executor = TaskExecutor()
        notifications = []

        def callback(msg_type, data):
            if msg_type == "update_progress":
                notifications.append(data)

        executor.gui_callback = callback

        def execute_fn(step):
            return {"action": step.get("action"), "status": "ok"}

        plan = [{"action": "step1", "args": {}}]
        executor.execute_plan_async(plan, execute_fn)
        time.sleep(0.3)


class TestTaskExecutorEdgeCases:
    """Граничні випадки."""

    def test_empty_plan(self):
        """Виконання порожнього плану."""
        executor = TaskExecutor()
        results = []

        def on_complete(r):
            results.extend(r)

        executor.execute_plan_async([], lambda s: {}, on_complete)
        time.sleep(0.2)

        assert len(results) == 0

    def test_single_step_plan(self):
        """План з одним кроком."""
        executor = TaskExecutor()
        results = []

        def execute_fn(step):
            return {"action": step.get("action"), "status": "ok"}

        def on_complete(r):
            results.extend(r)

        executor.execute_plan_async([{"action": "only_step"}], execute_fn, on_complete)
        time.sleep(0.3)

        assert len(results) == 1

    def test_already_running_prevents_double(self):
        """Подвійний запуск запобігається."""
        executor = TaskExecutor()
        executor.is_running = True

        def callback(msg_type, data):
            pass

        executor.gui_callback = callback

        # Спроба запуску під час виконання
        executor.execute_plan_async([{"action": "test"}], lambda s: {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
