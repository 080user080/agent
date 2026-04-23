"""Тести для functions/core_plan_compiler.py — Phase 13.2/13.4 skeleton."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.core_plan_compiler import (  # noqa: E402
    Pipeline,
    PipelineRegistry,
    PipelineRegistryError,
    SkeletonPipeline,
    compile_plan_from_spec,
    make_default_registry,
)
from functions.core_task_intake import (  # noqa: E402
    DOMAIN_CODE,
    DOMAIN_MIXED,
    DOMAIN_PHOTO_BATCH,
    DOMAIN_PRESENTATION,
    DOMAIN_UNKNOWN,
    DOMAIN_WEB_RESEARCH,
    TaskSpec,
)
from functions.logic_task_runner import Plan  # noqa: E402


# ---------------------------------------------------------------------------
# SkeletonPipeline
# ---------------------------------------------------------------------------


class TestSkeletonPipeline:
    def test_compile_returns_plan_with_one_task(self):
        spec = TaskSpec(
            goal="Django CRUD",
            domain=DOMAIN_CODE,
            domain_sub="django",
            deliverables=["models.py"],
        )
        pipe = SkeletonPipeline()
        plan = pipe.compile(spec)
        assert isinstance(plan, Plan)
        assert len(plan.tasks) == 1
        task = plan.tasks[0]
        assert task.kind == "log_task_spec"
        assert task.params["placeholder_step"] is True
        assert task.params["spec_domain"] == DOMAIN_CODE
        assert task.params["spec_goal"] == "Django CRUD"
        assert task.params["spec_deliverables"] == ["models.py"]
        assert plan.metadata["placeholder"] is True
        assert plan.metadata["pipeline"] == "skeleton"
        assert plan.metadata["task_id"] == spec.task_id

    def test_long_goal_truncated_in_names(self):
        long_goal = "x" * 500
        spec = TaskSpec(goal=long_goal)
        plan = SkeletonPipeline().compile(spec)
        assert len(plan.name) <= 200
        assert len(plan.tasks[0].name) <= 200

    def test_required_tools_empty(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE)
        assert SkeletonPipeline().required_tools(spec) == []

    def test_custom_name(self):
        pipe = SkeletonPipeline(name="custom_skel")
        spec = TaskSpec(goal="g")
        plan = pipe.compile(spec)
        assert plan.metadata["pipeline"] == "custom_skel"

    def test_protocol_satisfied(self):
        pipe = SkeletonPipeline()
        assert isinstance(pipe, Pipeline)


# ---------------------------------------------------------------------------
# PipelineRegistry
# ---------------------------------------------------------------------------


class _FakePipeline:
    def __init__(self, name="fake"):
        self.name = name

    def compile(self, spec: TaskSpec) -> Plan:
        return Plan(name=f"fake:{spec.goal}", metadata={"pipeline": self.name})

    def required_tools(self, spec: TaskSpec):
        return ["fake_tool"]


class TestPipelineRegistry:
    def test_register_and_get(self):
        reg = PipelineRegistry()
        fake = _FakePipeline()
        reg.register(DOMAIN_CODE, fake)
        assert reg.get(DOMAIN_CODE) is fake

    def test_register_unknown_domain_raises(self):
        reg = PipelineRegistry()
        with pytest.raises(PipelineRegistryError):
            reg.register("martian", _FakePipeline())

    def test_register_duplicate_raises(self):
        reg = PipelineRegistry()
        reg.register(DOMAIN_CODE, _FakePipeline())
        with pytest.raises(PipelineRegistryError):
            reg.register(DOMAIN_CODE, _FakePipeline())

    def test_register_overwrite(self):
        reg = PipelineRegistry()
        p1 = _FakePipeline("one")
        p2 = _FakePipeline("two")
        reg.register(DOMAIN_CODE, p1)
        reg.register(DOMAIN_CODE, p2, overwrite=True)
        assert reg.get(DOMAIN_CODE) is p2

    def test_unregister(self):
        reg = PipelineRegistry()
        reg.register(DOMAIN_CODE, _FakePipeline())
        reg.unregister(DOMAIN_CODE)
        assert reg.get(DOMAIN_CODE) is None
        # повторне unregister — без помилки
        reg.unregister(DOMAIN_CODE)

    def test_resolve_direct_match(self):
        reg = PipelineRegistry()
        p = _FakePipeline("code_one")
        reg.register(DOMAIN_CODE, p)
        assert reg.resolve(DOMAIN_CODE) is p

    def test_resolve_falls_back_to_mixed(self):
        reg = PipelineRegistry()
        mixed = _FakePipeline("mixed_one")
        reg.register(DOMAIN_MIXED, mixed)
        assert reg.resolve(DOMAIN_PHOTO_BATCH) is mixed

    def test_resolve_falls_back_to_unknown(self):
        reg = PipelineRegistry()
        unk = _FakePipeline("unknown_one")
        reg.register(DOMAIN_UNKNOWN, unk)
        assert reg.resolve(DOMAIN_CODE) is unk

    def test_resolve_no_fallback_raises(self):
        reg = PipelineRegistry()
        with pytest.raises(PipelineRegistryError):
            reg.resolve(DOMAIN_CODE)

    def test_list_domains_sorted(self):
        reg = PipelineRegistry()
        reg.register(DOMAIN_CODE, _FakePipeline())
        reg.register(DOMAIN_MIXED, _FakePipeline())
        reg.register(DOMAIN_PHOTO_BATCH, _FakePipeline())
        assert reg.list_domains() == sorted(
            [DOMAIN_CODE, DOMAIN_MIXED, DOMAIN_PHOTO_BATCH]
        )


# ---------------------------------------------------------------------------
# make_default_registry
# ---------------------------------------------------------------------------


class TestDefaultRegistry:
    def test_covers_all_known_domains(self):
        reg = make_default_registry()
        for d in (
            DOMAIN_CODE,
            DOMAIN_PHOTO_BATCH,
            DOMAIN_PRESENTATION,
            DOMAIN_WEB_RESEARCH,
            DOMAIN_MIXED,
            DOMAIN_UNKNOWN,
        ):
            assert reg.get(d) is not None

    def test_all_domains_use_skeleton(self):
        reg = make_default_registry()
        for d in reg.list_domains():
            assert isinstance(reg.get(d), SkeletonPipeline)


# ---------------------------------------------------------------------------
# compile_plan_from_spec
# ---------------------------------------------------------------------------


class TestCompilePlanFromSpec:
    def test_uses_default_registry(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE)
        plan = compile_plan_from_spec(spec)
        assert len(plan.tasks) == 1
        assert plan.tasks[0].kind == "log_task_spec"
        assert plan.metadata["pipeline"] == "skeleton"
        assert plan.metadata["domain"] == DOMAIN_CODE
        assert plan.metadata["task_id"] == spec.task_id

    def test_custom_registry(self):
        reg = PipelineRegistry()
        reg.register(DOMAIN_CODE, _FakePipeline("my_fake"))
        reg.register(DOMAIN_MIXED, _FakePipeline("fallback"))
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE)
        plan = compile_plan_from_spec(spec, registry=reg)
        assert plan.metadata["pipeline"] == "my_fake"

    def test_unknown_domain_falls_back_to_mixed(self):
        reg = PipelineRegistry()
        reg.register(DOMAIN_MIXED, _FakePipeline("fallback"))
        spec = TaskSpec(goal="g", domain=DOMAIN_PRESENTATION)
        plan = compile_plan_from_spec(spec, registry=reg)
        assert plan.metadata["pipeline"] == "fallback"

    def test_metadata_not_overwritten_if_set_by_pipeline(self):
        class _Keeper:
            name = "keeper"

            def compile(self, spec):
                return Plan(
                    name="k",
                    metadata={"pipeline": "overridden", "extra": 1},
                )

            def required_tools(self, spec):
                return []

        reg = PipelineRegistry()
        reg.register(DOMAIN_CODE, _Keeper())
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE)
        plan = compile_plan_from_spec(spec, registry=reg)
        # pipeline-ім'я не перетирається
        assert plan.metadata["pipeline"] == "overridden"
        assert plan.metadata["extra"] == 1
        # task_id підставляється якщо pipeline не виставив
        assert plan.metadata["task_id"] == spec.task_id
