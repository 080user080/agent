"""Тести для functions/core_app_profile.py."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.core_app_profile import (  # noqa: E402
    AppProfile,
    AppProfileRegistry,
    UIElement,
    Workflow,
)


class TestAppProfileDataclass:
    def test_create_minimal(self):
        profile = AppProfile(app_name="test")
        assert profile.app_name == "test"
        assert profile.known_elements == []
        assert profile.workflows == []
        assert profile.common_shortcuts == {}

    def test_add_shortcut(self):
        profile = AppProfile(app_name="test")
        profile.add_shortcut("save", "ctrl+s")
        assert profile.common_shortcuts["save"] == "ctrl+s"

    def test_add_element_dedup(self):
        profile = AppProfile(app_name="test")
        profile.add_element(UIElement(name="save_btn", description="v1"))
        profile.add_element(UIElement(name="save_btn", description="v2"))
        assert len(profile.known_elements) == 1
        assert profile.known_elements[0].description == "v2"

    def test_add_workflow_dedup(self):
        profile = AppProfile(app_name="test")
        profile.add_workflow(Workflow(name="flow", description="v1"))
        profile.add_workflow(Workflow(name="flow", description="v2"))
        assert len(profile.workflows) == 1
        assert profile.workflows[0].description == "v2"

    def test_find_element_and_workflow(self):
        profile = AppProfile(app_name="test")
        profile.add_element(UIElement(name="btn1"))
        profile.add_workflow(Workflow(name="wf1"))
        assert profile.find_element("btn1").name == "btn1"
        assert profile.find_workflow("wf1").name == "wf1"
        assert profile.find_element("missing") is None
        assert profile.find_workflow("missing") is None

    def test_roundtrip_to_dict_from_dict(self):
        profile = AppProfile(
            app_name="notepad",
            exe_path="notepad.exe",
            common_shortcuts={"save": "ctrl+s"},
            known_elements=[UIElement(name="e1", hints={"ocr": "Save"})],
            workflows=[Workflow(name="w1", steps=[{"action": "mouse_click", "params": {}}])],
            notes="hello",
        )
        data = profile.to_dict()
        restored = AppProfile.from_dict(data)
        assert restored == profile


class TestAppProfileRegistry:
    def test_seeds_available_without_disk(self, tmp_path):
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        # Навіть без файлів — мають бути seeds (notepad/explorer/chrome/paint).
        profile = registry.get("notepad")
        assert profile is not None
        assert "ctrl+s" in profile.common_shortcuts.values()

    def test_list_includes_all_seeds(self, tmp_path):
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        names = {p.app_name for p in registry.list_profiles()}
        assert {"notepad", "explorer", "chrome", "paint"}.issubset(names)

    def test_save_profile_writes_json(self, tmp_path):
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        profile = AppProfile(
            app_name="myapp",
            exe_path="myapp.exe",
            common_shortcuts={"save": "ctrl+s"},
        )
        path = registry.save_profile(profile)
        assert path.exists()

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["app_name"] == "myapp"
        assert data["common_shortcuts"]["save"] == "ctrl+s"

    def test_disk_overrides_seed(self, tmp_path):
        """Якщо на диску є 'notepad', він перевизначає seed."""
        # Запишемо власну версію notepad на диск.
        custom = {
            "app_name": "notepad",
            "exe_path": "custom.exe",
            "window_title_pattern": "",
            "common_shortcuts": {"unique": "ctrl+unique"},
            "known_elements": [],
            "workflows": [],
            "notes": "custom",
        }
        (tmp_path / "notepad.json").write_text(
            json.dumps(custom), encoding="utf-8"
        )

        registry = AppProfileRegistry(profiles_dir=tmp_path)
        profile = registry.get("notepad")
        assert profile.exe_path == "custom.exe"
        assert profile.common_shortcuts == {"unique": "ctrl+unique"}
        assert profile.notes == "custom"

    def test_delete_profile(self, tmp_path):
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        profile = AppProfile(app_name="deleteme")
        registry.save_profile(profile)
        assert registry.get("deleteme") is not None

        assert registry.delete_profile("deleteme") is True
        assert registry.get("deleteme") is None
        assert not (tmp_path / "deleteme.json").exists()

    def test_delete_missing_returns_false(self, tmp_path):
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        assert registry.delete_profile("missing") is False

    def test_case_insensitive_lookup(self, tmp_path):
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        assert registry.get("NOTEPAD") is not None
        assert registry.get("Notepad") is not None

    def test_broken_json_skipped(self, tmp_path):
        (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        # Seeds все одно доступні.
        assert registry.get("notepad") is not None

    def test_learn_from_interaction_creates_if_missing(self, tmp_path):
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        profile = registry.learn_from_interaction(
            "newapp",
            action="mouse_click",
            params={"x": 10, "y": 20},
            success=True,
        )
        assert profile.app_name == "newapp"
        assert "mouse_click" in profile.notes
        assert registry.get("newapp") is not None

    def test_learn_from_interaction_appends_note(self, tmp_path):
        registry = AppProfileRegistry(profiles_dir=tmp_path)
        registry.learn_from_interaction("notepad", "save", {"path": "a.txt"})
        registry.learn_from_interaction("notepad", "open", {"path": "b.txt"})
        profile = registry.get("notepad")
        assert "save" in profile.notes
        assert "open" in profile.notes


class TestUIElementAndWorkflow:
    def test_ui_element_defaults(self):
        e = UIElement(name="btn")
        assert e.hints == {}
        assert e.description == ""

    def test_workflow_steps_default(self):
        wf = Workflow(name="flow")
        assert wf.steps == []
