"""Тести для verify_edit, rollback_edit, verify_and_maybe_rollback
в functions/planning/self_code_patcher.py

Phase: Self-Coding Agent Pipeline — Фаза 3.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, mock_open

import pytest


# ── verify_edit ──────────────────────────────────────────────────────────────


class TestVerifyEdit:
    """Тести для verify_edit()."""

    def test_verify_edit_ok_valid_syntax(self, tmp_path: Path):
        """Файл з коректним синтаксисом → ok=True."""
        from functions.planning.self_code_patcher import verify_edit

        test_file = tmp_path / "test_module.py"
        test_file.write_text("def hello():\n    return 42\n", encoding="utf-8")

        with patch(
            "functions.planning.self_code_patcher._read_file_content",
            return_value="def hello():\n    return 42\n",
        ), patch(
            "functions.planning.self_code_patcher._update_repo_map",
            return_value=True,
        ):
            result = verify_edit(str(test_file), "Додати функцію hello")

        assert result["ok"] is True
        assert "summary" in result
        assert isinstance(result["warnings"], list)
        assert len(result["warnings"]) == 0

    def test_verify_edit_fail_file_not_found(self, tmp_path: Path):
        """Файл не знайдено → ok=False з попередженням."""
        from functions.planning.self_code_patcher import verify_edit

        nonexistent = str(tmp_path / "nonexistent.py")

        with patch(
            "functions.planning.self_code_patcher._read_file_content",
            return_value=None,
        ):
            result = verify_edit(nonexistent, "Змінити файл")

        assert result["ok"] is False
        assert len(result["warnings"]) > 0
        assert "не знайдено" in result["warnings"][0].lower() or "нечитабельний" in result["warnings"][0].lower()

    def test_verify_edit_fail_syntax_error(self, tmp_path: Path):
        """Файл з синтаксичною помилкою → ok=False."""
        from functions.planning.self_code_patcher import verify_edit

        test_file = tmp_path / "bad_syntax.py"
        bad_content = "def broken(:\n    pass\n"

        with patch(
            "functions.planning.self_code_patcher._read_file_content",
            return_value=bad_content,
        ), patch(
            "functions.planning.self_code_patcher._update_repo_map",
            return_value=True,
        ):
            result = verify_edit(str(test_file), "Зламати синтаксис")

        assert result["ok"] is False
        assert any("синтаксична помилка" in w.lower() for w in result["warnings"])

    def test_verify_edit_with_llm_ok(self, tmp_path: Path):
        """LLM підтверджує що зміна коректна → ok=True."""
        from functions.planning.self_code_patcher import verify_edit

        test_file = tmp_path / "llm_ok.py"
        content = "def greet():\n    return 'hi'\n"

        llm_response = json.dumps({
            "ok": True,
            "summary": "Зміна коректна",
            "warnings": [],
        })

        def mock_llm(messages):
            return llm_response

        with patch(
            "functions.planning.self_code_patcher._read_file_content",
            return_value=content,
        ), patch(
            "functions.planning.self_code_patcher._update_repo_map",
            return_value=True,
        ):
            result = verify_edit(str(test_file), "Додати функцію greet", llm_callback=mock_llm)

        assert result["ok"] is True
        assert "Зміна коректна" in result["summary"]

    def test_verify_edit_with_llm_reject(self, tmp_path: Path):
        """LLM відхиляє зміну → ok=False."""
        from functions.planning.self_code_patcher import verify_edit

        test_file = tmp_path / "llm_reject.py"
        content = "def greet():\n    return 'hi'\n"

        llm_response = json.dumps({
            "ok": False,
            "summary": "Функція не відповідає задачі",
            "warnings": ["Відсутній docstring", "Невірний тип повернення"],
        })

        def mock_llm(messages):
            return llm_response

        with patch(
            "functions.planning.self_code_patcher._read_file_content",
            return_value=content,
        ), patch(
            "functions.planning.self_code_patcher._update_repo_map",
            return_value=True,
        ):
            result = verify_edit(str(test_file), "Додати функцію greet", llm_callback=mock_llm)

        assert result["ok"] is False
        assert len(result["warnings"]) >= 2

    def test_verify_edit_with_llm_error_fallback(self, tmp_path: Path):
        """LLM падає → fallback на базову перевірку."""
        from functions.planning.self_code_patcher import verify_edit

        test_file = tmp_path / "llm_error.py"
        content = "x = 42\n"

        def broken_llm(messages):
            raise RuntimeError("LLM unavailable")

        with patch(
            "functions.planning.self_code_patcher._read_file_content",
            return_value=content,
        ), patch(
            "functions.planning.self_code_patcher._update_repo_map",
            return_value=True,
        ):
            result = verify_edit(str(test_file), "Задача", llm_callback=broken_llm)

        assert result["ok"] is True  # fallback: syntax OK
        assert any("LLM" in w for w in result["warnings"])

    def test_verify_edit_updates_repo_map(self, tmp_path: Path):
        """verify_edit викликає _update_repo_map."""
        from functions.planning.self_code_patcher import verify_edit

        test_file = tmp_path / "repo_map.py"
        content = "x = 1\n"

        with patch(
            "functions.planning.self_code_patcher._read_file_content",
            return_value=content,
        ), patch(
            "functions.planning.self_code_patcher._update_repo_map",
            return_value=True,
        ) as mock_update:
            verify_edit(str(test_file), "Задача")

        mock_update.assert_called_once_with(str(test_file))


# ── rollback_edit ────────────────────────────────────────────────────────────


class TestRollbackEdit:
    """Тести для rollback_edit()."""

    def test_rollback_edit_success(self):
        """Успішний rollback з існуючим snapshot."""
        from functions.planning.self_code_patcher import rollback_edit

        mock_undo = MagicMock()
        mock_undo.restore_snapshot.return_value = {
            "success": True,
            "message": "Snapshot відновлено",
        }

        mock_learner = MagicMock()

        verify_result = {
            "ok": False,
            "summary": "LLM відхилив",
            "warnings": ["Не та функція"],
        }

        with patch(
            "functions.runtime.core_undo_manager.get_undo_manager",
            return_value=mock_undo,
        ), patch(
            "functions.runtime.self_learning.get_self_learning",
            return_value=mock_learner,
        ):
            result = rollback_edit(
                file_path="test.py",
                snapshot_id="snap123",
                task="Тестова задача",
                verify_result=verify_result,
            )

        assert result["ok"] is True
        assert result["restored"] is True
        assert "snap123" in result["summary"]
        mock_undo.restore_snapshot.assert_called_once_with("snap123")
        mock_learner.log_execution.assert_called_once()

        # Перевіряємо що log_execution викликано з правильними параметрами
        log_call = mock_learner.log_execution.call_args
        assert log_call.kwargs["success"] is False
        assert "Тестова задача" in log_call.kwargs["task"]

    def test_rollback_edit_no_snapshot(self):
        """Rollback з неіснуючим snapshot → restored=False."""
        from functions.planning.self_code_patcher import rollback_edit

        mock_undo = MagicMock()
        mock_undo.restore_snapshot.return_value = {
            "success": False,
            "message": "Snapshot не знайдено",
        }

        mock_learner = MagicMock()
        verify_result = {"ok": False, "summary": "Error", "warnings": ["test"]}

        with patch(
            "functions.runtime.core_undo_manager.get_undo_manager",
            return_value=mock_undo,
        ), patch(
            "functions.runtime.self_learning.get_self_learning",
            return_value=mock_learner,
        ):
            result = rollback_edit(
                file_path="test.py",
                snapshot_id="nonexistent",
                task="Задача",
                verify_result=verify_result,
            )

        assert result["ok"] is False
        assert result["restored"] is False
        assert result["error"] is not None

    def test_rollback_edit_undo_manager_unavailable(self):
        """UndoManager недоступний → ok=False з помилкою."""
        from functions.planning.self_code_patcher import rollback_edit

        mock_learner = MagicMock()
        verify_result = {"ok": False, "summary": "Error", "warnings": ["test"]}

        with patch(
            "functions.runtime.core_undo_manager.get_undo_manager",
            side_effect=ImportError("No module"),
        ), patch(
            "functions.runtime.self_learning.get_self_learning",
            return_value=mock_learner,
        ):
            result = rollback_edit(
                file_path="test.py",
                snapshot_id="snap1",
                task="Задача",
                verify_result=verify_result,
            )

        assert result["ok"] is False
        assert result["restored"] is False
        assert "UndoManager" in result["error"]

    def test_rollback_edit_logs_failure(self):
        """Rollback залоговує невдалу спробу через SelfLearning."""
        from functions.planning.self_code_patcher import rollback_edit

        mock_undo = MagicMock()
        mock_undo.restore_snapshot.return_value = {"success": True, "message": "OK"}

        mock_learner = MagicMock()
        verify_result = {
            "ok": False,
            "summary": "Test fail",
            "warnings": ["warn1", "warn2"],
        }

        with patch(
            "functions.runtime.core_undo_manager.get_undo_manager",
            return_value=mock_undo,
        ), patch(
            "functions.runtime.self_learning.get_self_learning",
            return_value=mock_learner,
        ):
            rollback_edit(
                file_path="test.py",
                snapshot_id="snap42",
                task="Test task",
                verify_result=verify_result,
            )

        mock_learner.log_execution.assert_called_once()
        kwargs = mock_learner.log_execution.call_args.kwargs
        assert kwargs["success"] is False
        assert kwargs["error"] is not None
        assert kwargs["metadata"]["file_path"] == "test.py"
        assert kwargs["metadata"]["snapshot_id"] == "snap42"

    def test_rollback_edit_includes_verify_result(self):
        """Rollback повертає оригінальний verify_result."""
        from functions.planning.self_code_patcher import rollback_edit

        mock_undo = MagicMock()
        mock_undo.restore_snapshot.return_value = {"success": True, "message": "OK"}

        mock_learner = MagicMock()
        verify_result = {"ok": False, "summary": "X", "warnings": ["Y"]}

        with patch(
            "functions.runtime.core_undo_manager.get_undo_manager",
            return_value=mock_undo,
        ), patch(
            "functions.runtime.self_learning.get_self_learning",
            return_value=mock_learner,
        ):
            result = rollback_edit("test.py", "s1", "task", verify_result)

        assert result["verify_result"] is verify_result


# ── verify_and_maybe_rollback ───────────────────────────────────────────────


class TestVerifyAndMaybeRollback:
    """Тести для verify_and_maybe_rollback()."""

    def test_no_rollback_when_ok(self, tmp_path: Path):
        """verify_edit ok=True → rollback НЕ викликається."""
        from functions.planning.self_code_patcher import verify_and_maybe_rollback

        test_file = tmp_path / "ok.py"

        with patch(
            "functions.planning.self_code_patcher.verify_edit",
            return_value={"ok": True, "summary": "All good", "warnings": []},
        ) as mock_verify, patch(
            "functions.planning.self_code_patcher.rollback_edit",
        ) as mock_rollback:
            result = verify_and_maybe_rollback(
                str(test_file), "Task", "snap1"
            )

        assert result["verified"] is True
        assert result["rolled_back"] is False
        assert result["rollback_result"] is None
        mock_rollback.assert_not_called()

    def test_rollback_when_not_ok(self, tmp_path: Path):
        """verify_edit ok=False → rollback ВИКЛИКАЄТЬСЯ."""
        from functions.planning.self_code_patcher import verify_and_maybe_rollback

        test_file = tmp_path / "bad.py"
        verify_result = {"ok": False, "summary": "Bad", "warnings": ["err"]}
        rollback_result = {
            "ok": True,
            "restored": True,
            "summary": "Rollback done",
            "verify_result": verify_result,
            "error": None,
        }

        with patch(
            "functions.planning.self_code_patcher.verify_edit",
            return_value=verify_result,
        ), patch(
            "functions.planning.self_code_patcher.rollback_edit",
            return_value=rollback_result,
        ) as mock_rollback:
            result = verify_and_maybe_rollback(
                str(test_file), "Task", "snap1"
            )

        assert result["verified"] is False
        assert result["rolled_back"] is True
        assert result["rollback_result"]["summary"] == "Rollback done"
        mock_rollback.assert_called_once_with(
            file_path=str(test_file),
            snapshot_id="snap1",
            task="Task",
            verify_result=verify_result,
        )

    def test_returns_all_fields(self, tmp_path: Path):
        """verify_and_maybe_rollback повертає всі передбачені поля."""
        from functions.planning.self_code_patcher import verify_and_maybe_rollback

        test_file = tmp_path / "fields.py"

        with patch(
            "functions.planning.self_code_patcher.verify_edit",
            return_value={"ok": True, "summary": "OK", "warnings": []},
        ):
            result = verify_and_maybe_rollback(str(test_file), "Task", "snap1")

        assert "verified" in result
        assert "rolled_back" in result
        assert "verify_result" in result
        assert "rollback_result" in result


# ── _parse_verify_response ──────────────────────────────────────────────────


class TestParseVerifyResponse:
    """Тести для _parse_verify_response()."""

    def test_parse_valid_json(self):
        from functions.planning.self_code_patcher import _parse_verify_response

        text = '{"ok": true, "summary": "Good", "warnings": ["w1"]}'
        result = _parse_verify_response(text)
        assert result is not None
        assert result["ok"] is True
        assert result["summary"] == "Good"
        assert result["warnings"] == ["w1"]

    def test_parse_json_with_markdown_wrapper(self):
        from functions.planning.self_code_patcher import _parse_verify_response

        text = '```json\n{"ok": false, "summary": "Bad", "warnings": []}\n```'
        result = _parse_verify_response(text)
        assert result is not None
        assert result["ok"] is False

    def test_parse_json_embedded_in_text(self):
        from functions.planning.self_code_patcher import _parse_verify_response

        text = 'Here is the result:\n{"ok": true, "summary": "OK", "warnings": []}\nDone.'
        result = _parse_verify_response(text)
        assert result is not None
        assert result["ok"] is True

    def test_parse_invalid_text(self):
        from functions.planning.self_code_patcher import _parse_verify_response

        text = "This is not JSON at all"
        result = _parse_verify_response(text)
        assert result is None

    def test_parse_empty_json_object(self):
        from functions.planning.self_code_patcher import _parse_verify_response

        text = "{}"
        result = _parse_verify_response(text)
        assert result is not None
        assert result["ok"] is False  # default
        assert result["summary"] == ""


# ── _update_repo_map ────────────────────────────────────────────────────────


class TestUpdateRepoMap:
    """Тести для _update_repo_map()."""

    def test_update_repo_map_success(self):
        from functions.planning.self_code_patcher import _update_repo_map

        with patch(
            "functions.project_indexer.update_file_in_map",
            return_value=True,
        ) as mock_update:
            result = _update_repo_map("functions/test.py")

        assert result is True
        mock_update.assert_called_once_with("functions/test.py")

    def test_update_repo_map_import_error(self):
        from functions.planning.self_code_patcher import _update_repo_map

        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module"),
        ):
            result = _update_repo_map("test.py")

        assert result is False

    def test_update_repo_map_exception(self):
        from functions.planning.self_code_patcher import _update_repo_map

        with patch(
            "functions.project_indexer.update_file_in_map",
            side_effect=RuntimeError("disk error"),
        ):
            result = _update_repo_map("test.py")

        assert result is False