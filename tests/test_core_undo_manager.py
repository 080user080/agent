"""
Тести для модуля core_undo_manager.py

GUI Automation Phase 6 — Undo/Redo менеджер.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestUndoManager:
    """Тести для класу UndoManager."""

    def test_init(self):
        """Тест ініціалізації UndoManager."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager(max_history=100)
        assert manager is not None
        assert manager.max_history == 100

    def test_record_action(self):
        """Тест запису дії."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.record_action("mouse_click", {"x": 100, "y": 200}, undo_fn=lambda: None)

        assert len(manager.history) == 1

    def test_undo(self):
        """Тест undo дії."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        undo_called = False

        def undo_fn():
            nonlocal undo_called
            undo_called = True

        manager.record_action("test", {}, undo_fn=undo_fn)
        manager.undo()

        assert undo_called

    def test_redo(self):
        """Тест redo дії."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        redo_called = False

        def redo_fn():
            nonlocal redo_called
            redo_called = True

        manager.record_action("test", {}, undo_fn=lambda: None, redo_fn=redo_fn)
        manager.undo()
        manager.redo()

        assert redo_called

    def test_max_history_limit(self):
        """Тест обмеження історії."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager(max_history=5)
        for i in range(10):
            manager.record_action(f"action_{i}", {}, undo_fn=lambda: None)

        assert len(manager.history) <= 5

    def test_clear(self):
        """Тест очищення історії."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.record_action("test", {}, undo_fn=lambda: None)
        manager.clear()

        assert len(manager.history) == 0


class TestActionStack:
    """Тести для класу ActionStack."""

    def test_init(self):
        """Тест ініціалізації ActionStack."""
        from functions.runtime.core_undo_manager import ActionStack

        stack = ActionStack()
        assert stack is not None

    def test_push(self):
        """Тест додавання дії в стек."""
        from functions.runtime.core_undo_manager import ActionStack

        stack = ActionStack()
        stack.push({"action": "test"})

        assert len(stack.items) == 1

    def test_pop(self):
        """Тест видалення дії зі стеку."""
        from functions.runtime.core_undo_manager import ActionStack

        stack = ActionStack()
        stack.push({"action": "test"})
        result = stack.pop()

        assert result is not None
        assert len(stack.items) == 0

    def test_peek(self):
        """Тест перегляду верхнього елемента."""
        from functions.runtime.core_undo_manager import ActionStack

        stack = ActionStack()
        stack.push({"action": "test"})
        result = stack.peek()

        assert result is not None
        assert len(stack.items) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
