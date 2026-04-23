"""Unit tests for logic_expectations (Phase 12.1)."""
from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from functions.logic_expectations import (
    EXPECT_FILE_CONTAINS,
    EXPECT_FILE_EXISTS,
    EXPECT_FILE_LINES_AT_LEAST,
    EXPECT_FILE_MISSING,
    EXPECT_FILE_NOT_CONTAINS,
    EXPECT_FILE_SIZE_BETWEEN,
    EXPECT_JSON_VALID,
    EXPECT_NO_ERROR_IN_REPORT,
    EXPECT_OK_COUNT_AT_LEAST,
    EXPECT_PROCESS_NOT_RUNNING,
    EXPECT_PROCESS_RUNNING,
    EXPECT_PYTHON_PARSEABLE,
    EXPECT_REGEX_MATCH,
    EXPECT_RETURN_CODE,
    EXPECT_STDERR_CONTAINS,
    EXPECT_STDOUT_CONTAINS,
    EXPECT_WINDOW_TITLE_CONTAINS,
    ExpectationResult,
    ExpectContext,
    ExpectRegistry,
    ExpectSpec,
    all_ok,
    failures,
    parse_expect_list,
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class TestExpectSpec:
    def test_from_dict_basic(self):
        spec = ExpectSpec.from_dict({"kind": "file_exists", "path": "/tmp/x"})
        assert spec.kind == "file_exists"
        assert spec.params == {"path": "/tmp/x"}

    def test_from_dict_missing_kind(self):
        with pytest.raises(ValueError):
            ExpectSpec.from_dict({"path": "x"})

    def test_to_dict_roundtrip(self):
        spec = ExpectSpec(kind="file_exists", params={"path": "/tmp/x"})
        assert spec.to_dict() == {"kind": "file_exists", "path": "/tmp/x"}


class TestParseExpectList:
    def test_none(self):
        assert parse_expect_list(None) == []

    def test_single_dict(self):
        out = parse_expect_list({"kind": "file_exists", "path": "/x"})
        assert len(out) == 1
        assert out[0].kind == "file_exists"

    def test_list_of_dicts(self):
        out = parse_expect_list([
            {"kind": "file_exists", "path": "/a"},
            {"kind": "stdout_contains", "value": "ok"},
        ])
        assert [s.kind for s in out] == ["file_exists", "stdout_contains"]

    def test_list_passthrough_expectspec(self):
        spec = ExpectSpec(kind="x", params={})
        out = parse_expect_list([spec])
        assert out[0] is spec

    def test_bad_type(self):
        with pytest.raises(ValueError):
            parse_expect_list("not a list")

    def test_bad_entry(self):
        with pytest.raises(ValueError):
            parse_expect_list([42])


# ---------------------------------------------------------------------------
# Built-in evaluators
# ---------------------------------------------------------------------------


def _ctx(**kw) -> ExpectContext:
    return ExpectContext(**kw)


class TestFileEvaluators:
    def test_file_exists_ok(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_FILE_EXISTS, params={"path": str(f)}),
            _ctx(),
        )
        assert res.ok
        assert res.details["path"] == str(f)

    def test_file_exists_relative_to_cwd(self, tmp_path):
        (tmp_path / "rel.txt").write_text("x")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_EXISTS, params={"path": "rel.txt"}
            ),
            _ctx(cwd=str(tmp_path)),
        )
        assert res.ok

    def test_file_exists_fail(self, tmp_path):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_EXISTS,
                params={"path": str(tmp_path / "none.txt")},
            ),
            _ctx(),
        )
        assert not res.ok
        assert "not found" in res.reason

    def test_file_exists_missing_path_param(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_FILE_EXISTS, params={}), _ctx()
        )
        assert not res.ok
        assert "missing" in res.reason

    def test_file_missing_ok(self, tmp_path):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_MISSING,
                params={"path": str(tmp_path / "nope")},
            ),
            _ctx(),
        )
        assert res.ok

    def test_file_missing_fail(self, tmp_path):
        p = tmp_path / "here.txt"
        p.write_text("1")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_FILE_MISSING, params={"path": str(p)}),
            _ctx(),
        )
        assert not res.ok
        assert "unexpectedly" in res.reason


class TestStdoutStderrEvaluators:
    def test_stdout_contains_ok(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_STDOUT_CONTAINS, params={"value": "hello"}
            ),
            _ctx(handler_result={"stdout_tail": "say hello world"}),
        )
        assert res.ok

    def test_stdout_contains_fail(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_STDOUT_CONTAINS, params={"value": "no"}),
            _ctx(handler_result={"stdout_tail": "something else"}),
        )
        assert not res.ok

    def test_stdout_contains_missing_value(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_STDOUT_CONTAINS, params={}),
            _ctx(handler_result={"stdout_tail": "x"}),
        )
        assert not res.ok
        assert "missing" in res.reason

    def test_stderr_contains_ok(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_STDERR_CONTAINS, params={"value": "err"}),
            _ctx(handler_result={"error": "boom err here"}),
        )
        assert res.ok


class TestReturnCode:
    def test_return_code_default_zero_ok(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_RETURN_CODE, params={}),
            _ctx(handler_result={"metadata": {"return_code": 0}}),
        )
        assert res.ok

    def test_return_code_mismatch(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_RETURN_CODE, params={"value": 0}),
            _ctx(handler_result={"metadata": {"return_code": 1}}),
        )
        assert not res.ok
        assert "expected return_code=0" in res.reason

    def test_return_code_absent_metadata(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_RETURN_CODE, params={"value": 0}),
            _ctx(handler_result={}),
        )
        assert not res.ok
        assert "did not report" in res.reason


class TestReportTotals:
    def test_no_error_ok(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_NO_ERROR_IN_REPORT, params={}),
            _ctx(report_totals={"ok": 2, "error": 0}),
        )
        assert res.ok

    def test_no_error_fail(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_NO_ERROR_IN_REPORT, params={}),
            _ctx(report_totals={"ok": 1, "error": 2}),
        )
        assert not res.ok
        assert "2 error" in res.reason

    def test_ok_count_at_least_pass(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_OK_COUNT_AT_LEAST, params={"value": 3}),
            _ctx(report_totals={"ok": 5}),
        )
        assert res.ok

    def test_ok_count_at_least_fail(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_OK_COUNT_AT_LEAST, params={"value": 3}),
            _ctx(report_totals={"ok": 1}),
        )
        assert not res.ok
        assert "need >= 3" in res.reason


# ---------------------------------------------------------------------------
# Windows-specific evaluators (mocked modules)
# ---------------------------------------------------------------------------


class TestWindowTitleContains:
    def test_pygetwindow_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pygetwindow", None)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_WINDOW_TITLE_CONTAINS, params={"value": "Excel"}
            ),
            _ctx(),
        )
        assert not res.ok
        assert "unavailable" in res.reason

    def test_window_match(self, monkeypatch):
        fake = MagicMock()
        fake.getAllWindows.return_value = [
            SimpleNamespace(title="Foo"),
            SimpleNamespace(title="Microsoft Excel — Book1"),
        ]
        monkeypatch.setitem(sys.modules, "pygetwindow", fake)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_WINDOW_TITLE_CONTAINS, params={"value": "Excel"}
            ),
            _ctx(),
        )
        assert res.ok
        assert res.details["match_count"] == 1

    def test_window_no_match(self, monkeypatch):
        fake = MagicMock()
        fake.getAllWindows.return_value = [SimpleNamespace(title="Other")]
        monkeypatch.setitem(sys.modules, "pygetwindow", fake)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_WINDOW_TITLE_CONTAINS, params={"value": "Excel"}
            ),
            _ctx(),
        )
        assert not res.ok
        assert "no window" in res.reason

    def test_enumeration_raises(self, monkeypatch):
        fake = MagicMock()
        fake.getAllWindows.side_effect = RuntimeError("boom")
        monkeypatch.setitem(sys.modules, "pygetwindow", fake)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_WINDOW_TITLE_CONTAINS, params={"value": "X"}
            ),
            _ctx(),
        )
        assert not res.ok
        assert "enumeration failed" in res.reason

    def test_missing_value(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_WINDOW_TITLE_CONTAINS, params={}),
            _ctx(),
        )
        assert not res.ok


class TestProcessRunning:
    def test_psutil_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "psutil", None)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_PROCESS_RUNNING, params={"name": "notepad.exe"}
            ),
            _ctx(),
        )
        assert not res.ok
        assert "unavailable" in res.reason

    def test_process_running_match(self, monkeypatch):
        fake = MagicMock()
        fake.process_iter.return_value = [
            SimpleNamespace(info={"name": "init"}),
            SimpleNamespace(info={"name": "NOTEPAD.EXE"}),
        ]
        monkeypatch.setitem(sys.modules, "psutil", fake)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_PROCESS_RUNNING, params={"name": "notepad.exe"}
            ),
            _ctx(),
        )
        assert res.ok
        assert res.details["count"] == 1

    def test_process_running_no_match(self, monkeypatch):
        fake = MagicMock()
        fake.process_iter.return_value = [
            SimpleNamespace(info={"name": "bash"}),
        ]
        monkeypatch.setitem(sys.modules, "psutil", fake)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_PROCESS_RUNNING, params={"name": "notepad.exe"}
            ),
            _ctx(),
        )
        assert not res.ok

    def test_process_not_running_ok(self, monkeypatch):
        fake = MagicMock()
        fake.process_iter.return_value = [
            SimpleNamespace(info={"name": "bash"}),
        ]
        monkeypatch.setitem(sys.modules, "psutil", fake)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_PROCESS_NOT_RUNNING,
                params={"name": "notepad.exe"},
            ),
            _ctx(),
        )
        assert res.ok

    def test_process_not_running_fail(self, monkeypatch):
        fake = MagicMock()
        fake.process_iter.return_value = [
            SimpleNamespace(info={"name": "notepad.exe"}),
        ]
        monkeypatch.setitem(sys.modules, "psutil", fake)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_PROCESS_NOT_RUNNING,
                params={"name": "notepad.exe"},
            ),
            _ctx(),
        )
        assert not res.ok

    def test_process_iter_item_raises(self, monkeypatch):
        broken = MagicMock()
        type(broken).info = MagicMock(side_effect=RuntimeError("nope"))

        good = SimpleNamespace(info={"name": "target"})
        fake = MagicMock()
        fake.process_iter.return_value = [broken, good]
        monkeypatch.setitem(sys.modules, "psutil", fake)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_PROCESS_RUNNING, params={"name": "target"}
            ),
            _ctx(),
        )
        assert res.ok


# ---------------------------------------------------------------------------
# Registry extensibility
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_kinds_has_builtins(self):
        reg = ExpectRegistry()
        kinds = reg.kinds()
        for k in [
            EXPECT_FILE_EXISTS,
            EXPECT_FILE_MISSING,
            EXPECT_STDOUT_CONTAINS,
            EXPECT_RETURN_CODE,
            EXPECT_NO_ERROR_IN_REPORT,
        ]:
            assert k in kinds

    def test_unknown_kind(self):
        reg = ExpectRegistry()
        res = reg.evaluate(ExpectSpec(kind="__nope__", params={}), _ctx())
        assert not res.ok
        assert "unknown" in res.reason

    def test_evaluator_exception_captured(self):
        reg = ExpectRegistry()

        def boom(spec, ctx):
            raise RuntimeError("bang")

        reg.register("boomy", boom)
        res = reg.evaluate(ExpectSpec(kind="boomy", params={}), _ctx())
        assert not res.ok
        assert "RuntimeError" in res.reason

    def test_register_and_unregister(self):
        reg = ExpectRegistry()

        def ok_fn(spec, ctx):
            return ExpectationResult(kind=spec.kind, ok=True)

        reg.register("custom", ok_fn)
        assert reg.get("custom") is ok_fn
        assert reg.unregister("custom") is True
        assert reg.get("custom") is None

    def test_evaluate_all(self, tmp_path):
        reg = ExpectRegistry()
        p = tmp_path / "f.txt"
        p.write_text("x")
        specs = [
            ExpectSpec(kind=EXPECT_FILE_EXISTS, params={"path": str(p)}),
            ExpectSpec(
                kind=EXPECT_FILE_EXISTS,
                params={"path": str(tmp_path / "nope")},
            ),
        ]
        out = reg.evaluate_all(specs, _ctx())
        assert [r.ok for r in out] == [True, False]


class TestHelpers:
    def test_all_ok(self):
        assert all_ok([])
        assert all_ok([ExpectationResult(kind="x", ok=True)])
        assert not all_ok(
            [ExpectationResult(kind="x", ok=True),
             ExpectationResult(kind="y", ok=False)]
        )

    def test_failures(self):
        rs = [
            ExpectationResult(kind="a", ok=True),
            ExpectationResult(kind="b", ok=False, reason="no"),
        ]
        out = failures(rs)
        assert len(out) == 1
        assert out[0].kind == "b"


# ---------------------------------------------------------------------------
# Phase 13 S10 — universal validators
# ---------------------------------------------------------------------------


class TestFileSizeBetween:
    def test_ok_within_range(self, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"x" * 500)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_SIZE_BETWEEN,
                params={"path": str(f), "min_bytes": 100, "max_bytes": 1000},
            ),
            _ctx(),
        )
        assert res.ok
        assert res.details["size"] == 500

    def test_below_min(self, tmp_path):
        f = tmp_path / "small.bin"
        f.write_bytes(b"x")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_SIZE_BETWEEN,
                params={"path": str(f), "min_bytes": 100},
            ),
            _ctx(),
        )
        assert not res.ok
        assert "min_bytes" in res.reason

    def test_above_max(self, tmp_path):
        f = tmp_path / "big.bin"
        f.write_bytes(b"x" * 5000)
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_SIZE_BETWEEN,
                params={"path": str(f), "max_bytes": 1000},
            ),
            _ctx(),
        )
        assert not res.ok
        assert "max_bytes" in res.reason

    def test_missing_file(self, tmp_path):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_SIZE_BETWEEN,
                params={"path": str(tmp_path / "nope.bin"), "min_bytes": 1},
            ),
            _ctx(),
        )
        assert not res.ok
        assert "not found" in res.reason

    def test_missing_path_param(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_FILE_SIZE_BETWEEN, params={"min_bytes": 1}),
            _ctx(),
        )
        assert not res.ok


class TestFileLinesAtLeast:
    def test_ok(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("a\nb\nc\n")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_LINES_AT_LEAST,
                params={"path": str(f), "value": 3},
            ),
            _ctx(),
        )
        assert res.ok
        assert res.details["lines"] == 3

    def test_empty_lines_excluded(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("a\n\n\nb\n")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_LINES_AT_LEAST,
                params={"path": str(f), "value": 3},
            ),
            _ctx(),
        )
        assert not res.ok
        assert "2" in res.reason

    def test_missing_file(self, tmp_path):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_LINES_AT_LEAST,
                params={"path": str(tmp_path / "nope.txt"), "value": 1},
            ),
            _ctx(),
        )
        assert not res.ok


class TestFileContains:
    def test_ok(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hello WORLD")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_CONTAINS,
                params={"path": str(f), "substring": "world", "case_insensitive": True},
            ),
            _ctx(),
        )
        assert res.ok

    def test_fail_case_sensitive(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hello WORLD")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_CONTAINS,
                params={"path": str(f), "substring": "world"},
            ),
            _ctx(),
        )
        assert not res.ok

    def test_missing_substring(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_FILE_CONTAINS, params={"path": str(f)}),
            _ctx(),
        )
        assert not res.ok


class TestFileNotContains:
    def test_ok_no_forbidden(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("def main(): pass\n")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_NOT_CONTAINS,
                params={
                    "path": str(f),
                    "substrings": ["TODO", "FIXME", "XXX"],
                },
            ),
            _ctx(),
        )
        assert res.ok

    def test_fail_has_forbidden(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("# TODO: implement\nx=1\n")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_NOT_CONTAINS,
                params={"path": str(f), "substrings": ["TODO", "FIXME"]},
            ),
            _ctx(),
        )
        assert not res.ok
        assert "TODO" in res.reason

    def test_case_insensitive_hit(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("# todo here\n")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_FILE_NOT_CONTAINS,
                params={
                    "path": str(f),
                    "substrings": ["TODO"],
                    "case_insensitive": True,
                },
            ),
            _ctx(),
        )
        assert not res.ok

    def test_missing_list(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_FILE_NOT_CONTAINS, params={"path": str(f)}),
            _ctx(),
        )
        assert not res.ok


class TestRegexMatch:
    def test_stdout_match(self):
        reg = ExpectRegistry()
        ctx = _ctx(handler_result={"stdout": "7 tests passed"})
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_REGEX_MATCH,
                params={"pattern": r"(\d+) tests passed"},
            ),
            ctx,
        )
        assert res.ok

    def test_stderr_match(self):
        reg = ExpectRegistry()
        ctx = _ctx(handler_result={"stderr": "ERROR: bad"})
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_REGEX_MATCH,
                params={"pattern": r"ERROR", "where": "stderr"},
            ),
            ctx,
        )
        assert res.ok

    def test_file_match(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("line1\nWARN: something\nline3")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_REGEX_MATCH,
                params={"pattern": r"^WARN", "where": "file", "path": str(f), "flags": "m"},
            ),
            _ctx(),
        )
        assert res.ok

    def test_invert_no_match_ok(self):
        reg = ExpectRegistry()
        ctx = _ctx(handler_result={"stdout": "all good"})
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_REGEX_MATCH,
                params={"pattern": r"ERROR", "invert": True},
            ),
            ctx,
        )
        assert res.ok

    def test_invert_match_fails(self):
        reg = ExpectRegistry()
        ctx = _ctx(handler_result={"stdout": "has ERROR"})
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_REGEX_MATCH,
                params={"pattern": r"ERROR", "invert": True},
            ),
            ctx,
        )
        assert not res.ok

    def test_missing_pattern(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_REGEX_MATCH, params={}),
            _ctx(),
        )
        assert not res.ok

    def test_invalid_regex(self):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_REGEX_MATCH, params={"pattern": "["}),
            _ctx(),
        )
        assert not res.ok
        assert "invalid regex" in res.reason


class TestJsonValid:
    def test_ok(self, tmp_path):
        f = tmp_path / "a.json"
        f.write_text('{"k": 1}')
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_JSON_VALID, params={"path": str(f)}),
            _ctx(),
        )
        assert res.ok

    def test_malformed(self, tmp_path):
        f = tmp_path / "a.json"
        f.write_text("{not valid")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_JSON_VALID, params={"path": str(f)}),
            _ctx(),
        )
        assert not res.ok
        assert "JSON parse error" in res.reason

    def test_root_type_match(self, tmp_path):
        f = tmp_path / "a.json"
        f.write_text("[1,2,3]")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_JSON_VALID,
                params={"path": str(f), "root_type": "array"},
            ),
            _ctx(),
        )
        assert res.ok

    def test_root_type_mismatch(self, tmp_path):
        f = tmp_path / "a.json"
        f.write_text("[1,2,3]")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_JSON_VALID,
                params={"path": str(f), "root_type": "object"},
            ),
            _ctx(),
        )
        assert not res.ok


class TestPythonParseable:
    def test_ok(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("def hello():\n    return 1\n")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_PYTHON_PARSEABLE, params={"path": str(f)}),
            _ctx(),
        )
        assert res.ok

    def test_syntax_error(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("def broken(:\n")
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(kind=EXPECT_PYTHON_PARSEABLE, params={"path": str(f)}),
            _ctx(),
        )
        assert not res.ok
        assert "SyntaxError" in res.reason

    def test_missing_file(self, tmp_path):
        reg = ExpectRegistry()
        res = reg.evaluate(
            ExpectSpec(
                kind=EXPECT_PYTHON_PARSEABLE,
                params={"path": str(tmp_path / "nope.py")},
            ),
            _ctx(),
        )
        assert not res.ok
