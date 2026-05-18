"""Tests for TaskSpec (S3: TaskSpec → compile() MVP)."""
from unittest.mock import MagicMock

import pytest

from functions.planning.task_spec import CompiledPlan, Domain, Priority, TaskSpec, TaskSpecCompiler


# ─── Helpers ──────────────────────────────────────────────────────────────────

class FakeAssistant:
    """Мінімальний stub для VoiceAssistant."""
    def __init__(self):
        self.planner = None


class FakeRegistry:
    """Мінімальний stub для FunctionRegistry."""
    pass


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestTaskSpec:
    def test_initial_state(self):
        spec = TaskSpec(description="test task")
        assert spec.description == "test task"
        assert spec.domain == Domain.UNKNOWN
        assert spec.priority == Priority.MEDIUM
        assert spec.deliverables == []
        assert spec.created_at > 0

    def test_with_domain(self):
        spec = TaskSpec(
            description="write code",
            domain=Domain.CODE,
            priority=Priority.HIGH,
        )
        assert spec.domain == Domain.CODE
        assert spec.priority == Priority.HIGH

    def test_to_dict(self):
        spec = TaskSpec(
            description="test",
            domain=Domain.PHOTO,
            deliverables=["photo.jpg"],
        )
        d = spec.to_dict()
        assert d["description"] == "test"
        assert d["domain"] == "photo"
        assert d["deliverables"] == ["photo.jpg"]


class TestCompiledPlan:
    def test_initial_state(self):
        spec = TaskSpec(description="test")
        plan = CompiledPlan(task_spec=spec)
        assert plan.task_spec == spec
        assert plan.steps == []
        assert plan.milestones == []


class TestTaskSpecCompilerDetectDomain:
    def test_detect_code_domain(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        assert compiler._detect_domain("напиши функцію на Python") == Domain.CODE
        assert compiler._detect_domain("refactor code") == Domain.CODE
        assert compiler._detect_domain("write tests") == Domain.CODE

    def test_detect_photo_domain(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        assert compiler._detect_domain("оброби фото") == Domain.PHOTO
        assert compiler._detect_domain("resize image") == Domain.PHOTO
        assert compiler._detect_domain("comfyui workflow") == Domain.PHOTO

    def test_detect_presentation_domain(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        assert compiler._detect_domain("зроби презентацію") == Domain.PRESENTATION
        assert compiler._detect_domain("слайди для звіту") == Domain.PRESENTATION

    def test_detect_unknown_domain(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        assert compiler._detect_domain("just random text") == Domain.UNKNOWN


class TestTaskSpecCompilerParse:
    def test_parse_basic(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        spec = compiler.parse("напиши код")
        assert spec.description == "напиши код"
        assert spec.domain == Domain.CODE  # auto-detected

    def test_parse_with_context(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        context = {
            "deliverables": ["file.py"],
            "milestones": ["write", "test"],
        }
        spec = compiler.parse("task", context=context)
        assert spec.deliverables == ["file.py"]
        assert spec.milestones == ["write", "test"]


class TestTaskSpecCompilerCompile:
    def test_compile_no_planner(self):
        assistant = FakeAssistant()  # без planner
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        spec = TaskSpec(description="test")
        plan = compiler.compile(spec)

        assert plan.task_spec == spec
        assert plan.steps == []  # порожній бо нема planner

    def test_compile_with_planner_mock(self):
        assistant = FakeAssistant()
        assistant.planner = MagicMock()
        assistant.planner.create_plan.return_value = [
            {"action": "step1", "args": {}, "goal": "first"},
            {"action": "step2", "args": {}, "goal": "second"},
        ]

        compiler = TaskSpecCompiler(assistant, FakeRegistry())
        spec = TaskSpec(description="test", milestones=["m1", "m2"])
        plan = compiler.compile(spec)

        assert len(plan.steps) == 2
        assert plan.estimated_duration_seconds > 0
        assert plan.estimated_tokens > 0

    def test_compile_with_milestones(self):
        assistant = FakeAssistant()
        assistant.planner = MagicMock()
        assistant.planner.create_plan.return_value = [
            {"action": "step1", "args": {}, "goal": "first"},
            {"action": "step2", "args": {}, "goal": "second"},
        ]

        compiler = TaskSpecCompiler(assistant, FakeRegistry())
        spec = TaskSpec(description="test", milestones=["milestone1", "milestone2"])
        plan = compiler.compile(spec)

        assert len(plan.milestones) == 2
        assert plan.milestones[0]["name"] == "milestone1"
        assert plan.milestones[0]["step_index"] == 0


class TestTaskSpecCompilerValidate:
    def test_validate_empty_plan(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        spec = TaskSpec(description="test")
        plan = CompiledPlan(task_spec=spec, steps=[])

        is_valid, msg = compiler.validate_plan(plan)
        assert is_valid is False
        assert "порожній" in msg.lower()

    def test_validate_too_many_steps(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        spec = TaskSpec(description="test")
        plan = CompiledPlan(task_spec=spec, steps=[{}] * 101)

        is_valid, msg = compiler.validate_plan(plan)
        assert is_valid is False
        assert "100" in msg

    def test_validate_duration_limit(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        spec = TaskSpec(description="test", max_duration_seconds=10)
        plan = CompiledPlan(
            task_spec=spec,
            steps=[{"action": "x"}],
            estimated_duration_seconds=100,  # більше ліміту
        )

        is_valid, msg = compiler.validate_plan(plan)
        assert is_valid is False
        assert "перевищує" in msg.lower()

    def test_validate_valid_plan(self):
        assistant = FakeAssistant()
        compiler = TaskSpecCompiler(assistant, FakeRegistry())

        spec = TaskSpec(description="test")
        plan = CompiledPlan(
            task_spec=spec,
            steps=[{"action": "x"}],
            estimated_duration_seconds=30,
        )

        is_valid, msg = compiler.validate_plan(plan)
        assert is_valid is True
        assert "валідний" in msg.lower()
