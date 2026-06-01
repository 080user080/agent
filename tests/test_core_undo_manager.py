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

        manager = UndoManager()
        assert manager is not None
        assert manager._max_stack_size == 50
        assert manager._max_snapshots == 10

    def test_add_to_undo_stack(self):
        """Тест додавання дії в undo stack."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.add_to_undo_stack("mouse_click", {"x": 100, "y": 200})

        stack = manager.get_undo_stack()
        assert len(stack) == 1
        assert stack[0]["original_action"] == "mouse_click"
        assert stack[0]["reversible"] == True

    def test_add_multiple_to_undo_stack(self):
        """Тест додавання кількох дій."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.add_to_undo_stack("mouse_click", {"x": 100, "y": 200})
        manager.add_to_undo_stack("keyboard_type", {"text": "hello"})
        manager.add_to_undo_stack("mouse_click", {"x": 300, "y": 400})

        stack = manager.get_undo_stack()
        assert len(stack) == 3

    def test_undo_last(self):
        """Тест undo_last."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.add_to_undo_stack("mouse_click", {"x": 100, "y": 200})
        manager.add_to_undo_stack("keyboard_type", {"text": "hello"})

        result = manager.undo_last(count=1)
        assert result["actions_undone"] == 1

        stack = manager.get_undo_stack()
        assert len(stack) == 1

    def test_undo_all(self):
        """Тест undo всіх дій."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.add_to_undo_stack("mouse_click", {"x": 100, "y": 200})
        manager.add_to_undo_stack("keyboard_type", {"text": "hello"})

        result = manager.undo_last(count=2)
        assert result["actions_undone"] == 2

        stack = manager.get_undo_stack()
        assert len(stack) == 0

    def test_max_stack_size_limit(self):
        """Тест обмеження розміру undo stack."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        # Максимум 50, додамо 60
        for i in range(60):
            manager.add_to_undo_stack(f"action_{i}", {"i": i})

        stack = manager.get_undo_stack()
        assert len(stack) <= 50

    def test_clear_undo_stack(self):
        """Тест очищення undo stack."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.add_to_undo_stack("mouse_click", {"x": 100, "y": 200})
        manager.clear_undo_stack()

        stack = manager.get_undo_stack()
        assert len(stack) == 0

    def test_undo_irreversible(self):
        """Тест undo незворотної дії."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.add_to_undo_stack("file_delete", {"path": "test.txt"}, reversible=False, irreversible_reason="Файли з кошика не відновлюються")

        result = manager.undo_last(count=1)
        assert result["actions_undone"] == 0
        assert len(result["errors"]) > 0

    def test_save_snapshot(self):
        """Тест збереження snapshot."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        result = manager.save_snapshot(label="test_snapshot")

        assert result["success"] == True
        assert result["snapshot_id"] is not None

    def test_save_and_list_snapshots(self):
        """Тест збереження та списку snapshots."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        manager.save_snapshot(label="snapshot_1")
        manager.save_snapshot(label="snapshot_2")

        snapshots = manager.list_snapshots()
        assert len(snapshots) == 2

    def test_save_and_restore_snapshot(self):
        """Тест збереження та відновлення snapshot."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        result = manager.save_snapshot(label="restore_test")
        snapshot_id = result["snapshot_id"]

        restore_result = manager.restore_snapshot(snapshot_id)
        assert restore_result["success"] == True

    def test_restore_nonexistent_snapshot(self):
        """Тест відновлення неіснуючого snapshot."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        result = manager.restore_snapshot("nonexistent_id")

        assert result["success"] == False

    def test_register_undoable_handler(self):
        """Тест реєстрації undo handler."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()

        def custom_handler(params):
            return {"success": True, "message": "Custom undo executed"}

        manager.register_undoable("custom_action", custom_handler)
        manager.add_to_undo_stack("custom_action", {"test": True})

        result = manager.undo_last(count=1)
        assert result["actions_undone"] == 1

    def test_undo_to_snapshot(self):
        """Тест undo до snapshot."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        result = manager.save_snapshot(label="test")
        snapshot_id = result["snapshot_id"]

        undo_result = manager.undo_to_snapshot(snapshot_id)
        assert undo_result["success"] == True

    def test_api_functions(self):
        """Тест публічних API функцій."""
        from functions.runtime.core_undo_manager import (
            get_undo_manager, save_snapshot, list_snapshots,
            undo_last, add_to_undo_stack, get_undo_stack, clear_undo_stack
        )

        manager = get_undo_manager()
        assert manager is not None

        # Тест save_snapshot
        result = save_snapshot("api_test")
        assert result["success"] == True

        # Тест list_snapshots
        snapshots = list_snapshots()
        assert len(snapshots) >= 1

        # Тест add_to_undo_stack
        add_to_undo_stack("test_action", {"test": True})

        # Тест get_undo_stack
        stack = get_undo_stack()
        assert len(stack) >= 1

        # Тест undo_last
        undo_result = undo_last(1)
        assert undo_result["success"] == True

        # Тест clear_undo_stack
        clear_undo_stack()
        stack = get_undo_stack()
        assert len(stack) == 0

    def test_max_snapshots_limit(self):
        """Тест обмеження кількості snapshot."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        # Максимум 10, додамо 15
        for i in range(15):
            manager.save_snapshot(label=f"snapshot_{i}")

        snapshots = manager.list_snapshots()
        assert len(snapshots) <= 10

    def test_get_undo_stack_empty(self):
        """Тест отримання пустого undo stack."""
        from functions.runtime.core_undo_manager import UndoManager

        manager = UndoManager()
        stack = manager.get_undo_stack()
        assert len(stack) == 0


class TestSnapshotContext:
    """Тести для класу SnapshotContext."""

    def test_snapshot_context_success(self):
        """Тест SnapshotContext при успіху."""
        from functions.runtime.core_undo_manager import SnapshotContext

        with SnapshotContext(label="test_context") as ctx:
            assert ctx.snapshot_id is not None

    def test_snapshot_context_restore(self):
        """Тест ручного відновлення SnapshotContext."""
        from functions.runtime.core_undo_manager import SnapshotContext

        ctx = SnapshotContext(label="manual_restore")
        ctx.__enter__()
        assert ctx.snapshot_id is not None

        result = ctx.restore()
        assert result["success"] == True


class TestUndoDataClasses:
    """Тести для dataclasses."""

    def test_state_snapshot_creation(self):
        """Тест створення StateSnapshot."""
        from functions.runtime.core_undo_manager import StateSnapshot

        snapshot = StateSnapshot(
            id="test_id",
            timestamp="2024-01-01",
            label="test"
        )
        assert snapshot.id == "test_id"
        assert snapshot.label == "test"

    def test_undo_action_creation(self):
        """Тест створення UndoAction."""
        from functions.runtime.core_undo_manager import UndoAction

        action = UndoAction(
            original_action="test_action",
            undo_function="_undo_test",
            undo_params={"test": True}
        )
        assert action.original_action == "test_action"
        assert action.reversible == True

    def test_undo_result_creation(self):
        """Тест створення UndoResult."""
        from functions.runtime.core_undo_manager import UndoResult

        result = UndoResult(
            success=True,
            action_undone="test_action",
            message="Test undone"
        )
        assert result.success == True
        assert result.action_undone == "test_action"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])