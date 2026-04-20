"""Тести для functions/core_macro.py."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.core_macro import (  # noqa: E402
    Macro,
    MacroRecorder,
    MacroStep,
    MacroStore,
    _substitute_vars,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class TestDataModel:
    def test_step_defaults(self):
        step = MacroStep(action="mouse_click")
        assert step.params == {}
        assert step.delay_before == 0.0
        assert step.on_fail == "abort"
        assert step.max_retries == 0

    def test_macro_roundtrip(self):
        macro = Macro(
            name="demo",
            description="demo macro",
            steps=[
                MacroStep(action="mouse_click", params={"x": 1}),
                MacroStep(action="keyboard_type", params={"text": "hi"}, delay_before=0.5),
            ],
            variables={"target": "foo"},
        )
        data = macro.to_dict()
        restored = Macro.from_dict(data)
        assert restored.name == "demo"
        assert len(restored.steps) == 2
        assert restored.steps[0].action == "mouse_click"
        assert restored.variables == {"target": "foo"}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class TestMacroStore:
    def test_save_and_load(self, tmp_path):
        store = MacroStore(macros_dir=tmp_path)
        macro = Macro(name="m1", steps=[MacroStep(action="x")])
        path = store.save(macro)
        assert path.exists()

        loaded = store.load("m1")
        assert loaded is not None
        assert loaded.name == "m1"
        assert loaded.steps[0].action == "x"

    def test_load_missing(self, tmp_path):
        store = MacroStore(macros_dir=tmp_path)
        assert store.load("missing") is None

    def test_list_names(self, tmp_path):
        store = MacroStore(macros_dir=tmp_path)
        store.save(Macro(name="a"))
        store.save(Macro(name="b"))
        assert store.list_names() == ["a", "b"]

    def test_delete(self, tmp_path):
        store = MacroStore(macros_dir=tmp_path)
        store.save(Macro(name="m"))
        assert store.delete("m") is True
        assert store.load("m") is None
        assert store.delete("m") is False

    def test_load_broken_json(self, tmp_path):
        (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
        store = MacroStore(macros_dir=tmp_path)
        assert store.load("broken") is None


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


class TestRecorder:
    def test_start_stop_records_steps(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        recorder.start("demo")
        recorder.record_step("mouse_click", {"x": 1, "y": 2})
        recorder.record_step("keyboard_type", {"text": "hi"})
        macro = recorder.stop()

        assert macro.name == "demo"
        assert len(macro.steps) == 2
        assert (tmp_path / "demo.json").exists()

    def test_record_without_start_raises(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        with pytest.raises(RuntimeError):
            recorder.record_step("x")

    def test_double_start_raises(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        recorder.start("first")
        with pytest.raises(RuntimeError):
            recorder.start("second")

    def test_stop_without_start_raises(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        with pytest.raises(RuntimeError):
            recorder.stop()

    def test_pause_resume(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        recorder.start("paused")
        recorder.record_step("step1")
        recorder.pause()
        recorder.record_step("skipped")  # ignored
        recorder.resume()
        recorder.record_step("step2")
        macro = recorder.stop(save=False)

        assert [s.action for s in macro.steps] == ["step1", "step2"]

    def test_stop_no_save(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        recorder.start("nosave")
        recorder.record_step("x")
        recorder.stop(save=False)
        assert not (tmp_path / "nosave.json").exists()

    def test_is_recording_flag(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        assert recorder.is_recording is False
        recorder.start("m")
        assert recorder.is_recording is True
        recorder.stop(save=False)
        assert recorder.is_recording is False


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------


def _make_executor(responses):
    """Створити fake executor, що повертає по черзі задані відповіді."""
    iterator = iter(responses)
    calls = []

    def executor(action, params):
        calls.append((action, dict(params)))
        return next(iterator)

    executor.calls = calls  # type: ignore[attr-defined]
    return executor


class TestPlayback:
    def test_all_steps_success(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        macro = Macro(
            name="m",
            steps=[
                MacroStep(action="mouse_click", params={"x": 1}),
                MacroStep(action="keyboard_type", params={"text": "hi"}),
            ],
        )
        executor = _make_executor(
            [{"success": True}, {"success": True}]
        )
        result = recorder.play(macro, executor, sleep_fn=lambda s: None)

        assert result.success is True
        assert result.steps_completed == 2
        assert result.steps_total == 2
        assert executor.calls[0] == ("mouse_click", {"x": 1})
        assert executor.calls[1] == ("keyboard_type", {"text": "hi"})

    def test_abort_on_failure(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        macro = Macro(
            name="m",
            steps=[
                MacroStep(action="a", on_fail="abort"),
                MacroStep(action="b"),
            ],
        )
        executor = _make_executor(
            [{"success": False, "error": "boom"}]
        )
        result = recorder.play(macro, executor, sleep_fn=lambda s: None)

        assert result.success is False
        assert result.steps_completed == 0
        assert "boom" in result.errors[0]
        # b не викликали.
        assert len(executor.calls) == 1

    def test_skip_on_failure_continues(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        macro = Macro(
            name="m",
            steps=[
                MacroStep(action="a", on_fail="skip"),
                MacroStep(action="b"),
            ],
        )
        executor = _make_executor(
            [{"success": False, "error": "oops"}, {"success": True}]
        )
        result = recorder.play(macro, executor, sleep_fn=lambda s: None)

        # success=True, бо skip — не критично; але 'a' не completed.
        assert result.success is True
        assert result.steps_completed == 1
        assert len(result.errors) == 1

    def test_retry_on_failure(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        macro = Macro(
            name="m",
            steps=[
                MacroStep(action="flaky", on_fail="retry", max_retries=2),
            ],
        )
        executor = _make_executor(
            [
                {"success": False, "error": "1st"},
                {"success": False, "error": "2nd"},
                {"success": True},
            ]
        )
        result = recorder.play(macro, executor, sleep_fn=lambda s: None)

        assert result.success is True
        assert result.steps_completed == 1
        assert len(executor.calls) == 3

    def test_retry_exceeded_aborts(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        macro = Macro(
            name="m",
            steps=[
                MacroStep(action="flaky", on_fail="retry", max_retries=1),
            ],
        )
        executor = _make_executor(
            [{"success": False}, {"success": False}]
        )
        result = recorder.play(macro, executor, sleep_fn=lambda s: None)

        assert result.success is False
        assert len(executor.calls) == 2

    def test_executor_exception_counts_as_failure(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))

        def executor(action, params):
            raise ValueError("boom")

        macro = Macro(
            name="m",
            steps=[MacroStep(action="x", on_fail="abort")],
        )
        result = recorder.play(macro, executor, sleep_fn=lambda s: None)

        assert result.success is False
        assert "boom" in result.errors[0]

    def test_delay_before_uses_sleep_fn(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        macro = Macro(
            name="m",
            steps=[MacroStep(action="x", delay_before=1.5)],
        )
        executor = _make_executor([{"success": True}])
        slept = []

        recorder.play(macro, executor, sleep_fn=lambda s: slept.append(s))
        assert slept == [1.5]

    def test_play_by_name_loads_from_store(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        recorder.store.save(Macro(name="saved", steps=[MacroStep(action="x")]))

        executor = _make_executor([{"success": True}])
        result = recorder.play("saved", executor, sleep_fn=lambda s: None)
        assert result.success is True
        assert result.steps_completed == 1

    def test_play_by_name_missing(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        result = recorder.play(
            "missing", lambda a, p: {"success": True}, sleep_fn=lambda s: None
        )
        assert result.success is False
        assert "not found" in result.errors[0]


# ---------------------------------------------------------------------------
# Variable substitution
# ---------------------------------------------------------------------------


class TestSubstituteVars:
    def test_simple_substitute(self):
        out = _substitute_vars({"path": "{{dir}}/a.txt"}, {"dir": "/tmp"})
        assert out == {"path": "/tmp/a.txt"}

    def test_nested_structures(self):
        params = {
            "items": ["{{name}}", 42, {"nested": "{{name}}"}],
            "literal": 10,
        }
        out = _substitute_vars(params, {"name": "Foo"})
        assert out == {
            "items": ["Foo", 42, {"nested": "Foo"}],
            "literal": 10,
        }

    def test_no_vars_returns_copy(self):
        params = {"x": 1}
        out = _substitute_vars(params, {})
        assert out == params
        # Має бути копією, не тим самим об'єктом.
        out["x"] = 999
        assert params["x"] == 1

    def test_substitute_in_playback(self, tmp_path):
        recorder = MacroRecorder(store=MacroStore(macros_dir=tmp_path))
        macro = Macro(
            name="m",
            steps=[MacroStep(action="create_file", params={"path": "{{dir}}/x.txt"})],
            variables={"dir": "/default"},
        )

        captured = []

        def executor(action, params):
            captured.append(params)
            return {"success": True}

        # Передані змінні перевизначають дефолтні.
        recorder.play(macro, executor, variables={"dir": "/custom"}, sleep_fn=lambda s: None)
        assert captured[0] == {"path": "/custom/x.txt"}


# ---------------------------------------------------------------------------
# JSON on-disk format
# ---------------------------------------------------------------------------


class TestJsonFormat:
    def test_saved_macro_is_valid_json_with_expected_keys(self, tmp_path):
        store = MacroStore(macros_dir=tmp_path)
        macro = Macro(
            name="fmt",
            description="d",
            steps=[MacroStep(action="x", params={"y": 1})],
            variables={"v": "w"},
        )
        path = store.save(macro)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "fmt"
        assert data["steps"][0]["action"] == "x"
        assert data["steps"][0]["params"] == {"y": 1}
        assert data["variables"] == {"v": "w"}
