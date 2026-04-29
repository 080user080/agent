"""
Тести для модуля core_action_recorder.py

GUI Automation Phase 2 — Аудит дій.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os
from datetime import datetime

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestActionRecorder:
    """Тести для класу ActionRecorder."""

    def test_init(self):
        """Тест ініціалізації ActionRecorder."""
        from functions.core_action_recorder import ActionRecorder

        recorder = ActionRecorder()
        assert recorder is not None
        assert len(recorder.actions) == 0

    def test_record_action(self):
        """Тест запису дії."""
        from functions.core_action_recorder import ActionRecorder

        recorder = ActionRecorder()
        recorder.record_action("mouse_click", {"x": 100, "y": 200})

        assert len(recorder.actions) == 1
        assert recorder.actions[0]["action"] == "mouse_click"
        assert recorder.actions[0]["args"]["x"] == 100

    def test_record_multiple_actions(self):
        """Тест запису кількох дій."""
        from functions.core_action_recorder import ActionRecorder

        recorder = ActionRecorder()
        recorder.record_action("mouse_click", {"x": 100, "y": 200})
        recorder.record_action("keyboard_type", {"text": "hello"})
        recorder.record_action("mouse_click", {"x": 300, "y": 400})

        assert len(recorder.actions) == 3

    def test_clear(self):
        """Тест очищення записів."""
        from functions.core_action_recorder import ActionRecorder

        recorder = ActionRecorder()
        recorder.record_action("mouse_click", {"x": 100, "y": 200})
        recorder.clear()

        assert len(recorder.actions) == 0

    def test_get_actions(self):
        """Тест отримання списку дій."""
        from functions.core_action_recorder import ActionRecorder

        recorder = ActionRecorder()
        recorder.record_action("mouse_click", {"x": 100, "y": 200})

        actions = recorder.get_actions()
        assert len(actions) == 1
        assert actions[0]["action"] == "mouse_click"

    def test_save_to_file(self):
        """Тест збереження у файл."""
        from functions.core_action_recorder import ActionRecorder

        recorder = ActionRecorder()
        recorder.record_action("mouse_click", {"x": 100, "y": 200})

        with patch('functions.core_action_recorder.Path') as mock_path:
            mock_file = MagicMock()
            mock_path.return_value.__truediv__.return_value = mock_file

            recorder.save_to_file("test_actions.json")
            mock_file.write_text.assert_called_once()

    def test_load_from_file(self):
        """Тест завантаження з файлу."""
        from functions.core_action_recorder import ActionRecorder

        recorder = ActionRecorder()

        with patch('functions.core_action_recorder.Path') as mock_path:
            mock_file = MagicMock()
            mock_path.return_value.__truediv__.return_value = mock_file
            mock_file.read_text.return_value = '[{"action": "test", "args": {}}]'

            recorder.load_from_file("test_actions.json")
            assert len(recorder.actions) == 1


class TestActionBuffer:
    """Тести для ActionBuffer."""

    def test_init(self):
        """Тест ініціалізації ActionBuffer."""
        from functions.core_action_recorder import ActionBuffer

        buffer = ActionBuffer(max_size=100)
        assert buffer is not None
        assert buffer.max_size == 100

    def test_add_action(self):
        """Тест додавання дії в буфер."""
        from functions.core_action_recorder import ActionBuffer

        buffer = ActionBuffer(max_size=100)
        buffer.add_action("mouse_click", {"x": 100, "y": 200})

        assert len(buffer.actions) == 1

    def test_max_size_limit(self):
        """Тест обмеження розміру буфера."""
        from functions.core_action_recorder import ActionBuffer

        buffer = ActionBuffer(max_size=5)
        for i in range(10):
            buffer.add_action("test", {"i": i})

        assert len(buffer.actions) <= 5


class TestConvertBufferToMacro:
    """Тести для конвертації буфера в макрос."""

    @patch('functions.core_action_recorder.MacroStore')
    def test_convert_buffer_to_macro(self, mock_store):
        """Тест конвертації буфера дій у макрос."""
        from functions.core_action_recorder import ActionRecorder, convert_buffer_to_macro

        recorder = ActionRecorder()
        recorder.record_action("mouse_click", {"x": 100, "y": 200})
        recorder.record_action("keyboard_type", {"text": "hello"})

        mock_macro = MagicMock()
        mock_store.return_value.save_macro.return_value = mock_macro

        result = convert_buffer_to_macro(recorder, "test_macro")
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
