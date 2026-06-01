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
        from functions.runtime.core_action_recorder import ActionRecorder
        
        # Скидаємо singleton для тесту
        recorder = ActionRecorder()
        assert recorder is not None
        assert hasattr(recorder, '_actions_cache')

    def test_record_action(self):
        """Тест запису дії."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        record = recorder.record_action("click", "mouse_click", {"x": 100, "y": 200}, {"success": True})
        
        assert record is not None
        assert record.action_type == "click"
        assert record.function_name == "mouse_click"
        assert record.params == {"x": 100, "y": 200}
        assert record.success == True

    def test_record_multiple_actions(self):
        """Тест запису кількох дій."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        recorder.record_action("click", "mouse_click", {"x": 100, "y": 200}, {"success": True})
        recorder.record_action("type", "keyboard_type", {"text": "hello"}, {"success": True})
        recorder.record_action("click", "mouse_click", {"x": 300, "y": 400}, {"success": True})
        
        actions = recorder.get_recent_actions(10)
        assert len(actions) >= 3

    def test_get_recent_actions(self):
        """Тест отримання списку дій."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        recorder.record_action("click", "mouse_click", {"x": 100, "y": 200}, {"success": True})
        
        actions = recorder.get_recent_actions(10)
        assert len(actions) >= 1
        assert actions[-1]["action_type"] == "click"

    def test_export_session_log_json(self):
        """Тест експорту логу в JSON."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        recorder.record_action("click", "mouse_click", {"x": 100, "y": 200}, {"success": True})
        
        log = recorder.export_session_log(format="json")
        import json
        data = json.loads(log)
        assert data["session_id"] == recorder.session_id
        assert len(data["actions"]) >= 1

    def test_export_session_log_text(self):
        """Тест експорту логу в текст."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        recorder.record_action("click", "mouse_click", {"x": 100, "y": 200}, {"success": True})
        
        log = recorder.export_session_log(format="text")
        assert "GUI Automation Session" in log
        assert "mouse_click" in log

    def test_generate_action_report(self):
        """Тест генерації звіту."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        recorder.record_action("click", "mouse_click", {"x": 100, "y": 200}, {"success": True})
        
        report = recorder.generate_action_report()
        assert "Action Report" in report
        assert "Total actions" in report

    def test_search_actions(self):
        """Тест пошуку дій."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        recorder.record_action("click", "mouse_click", {"x": 100, "y": 200}, {"success": True})
        recorder.record_action("type", "keyboard_type", {"text": "hello"}, {"success": False})
        
        results = recorder.search_actions({"action_type": "click"})
        assert len(results) >= 1
        assert all(r["action_type"] == "click" for r in results)

    def test_record_action_with_screenshots_disabled(self):
        """Тест запису без скріншотів."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        record = recorder.record_action("click", "mouse_click", {"x": 100}, {"success": True}, capture_screenshots=False)
        
        assert record.screenshot_before is None
        assert record.screenshot_after is None

    def test_session_id_generated(self):
        """Тест генерації session_id."""
        from functions.runtime.core_action_recorder import ActionRecorder
        
        recorder = ActionRecorder()
        assert recorder.session_id is not None
        assert len(recorder.session_id) > 0

    def test_recordable_decorator(self):
        """Тест декоратора recordable."""
        from functions.runtime.core_action_recorder import recordable
        
        @recordable("test_action", capture_screenshots=False)
        def dummy_function(value):
            return {"success": True, "value": value}
        
        result = dummy_function("hello")
        assert result["success"] == True
        assert result["value"] == "hello"

    def test_api_functions(self):
        """Тест публічних API функцій."""
        from functions.runtime.core_action_recorder import (
            record_action, get_recent_actions, export_session_log,
            generate_action_report, search_actions, get_recorder
        )
        
        # Тест get_recorder
        recorder = get_recorder()
        assert recorder is not None
        
        # Тест record_action
        record = record_action("click", "test_func", {"x": 1}, {"success": True}, capture_screenshots=False)
        assert record is not None
        assert record["action_type"] == "click"
        
        # Тест get_recent_actions
        actions = get_recent_actions(5)
        assert len(actions) >= 1
        
        # Тест export_session_log
        log = export_session_log("json")
        import json
        data = json.loads(log)
        assert "session_id" in data
        
        # Тест generate_action_report
        report = generate_action_report()
        assert report is not None
        
        # Тест search_actions
        found = search_actions({"action_type": "click"})
        assert len(found) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])