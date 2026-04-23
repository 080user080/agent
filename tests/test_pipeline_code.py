"""Тести для functions/pipeline_code.py — Phase 13 S7."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.core_plan_compiler import (  # noqa: E402
    Pipeline,
    compile_plan_from_spec,
    make_default_registry,
)
from functions.core_task_intake import (  # noqa: E402
    DOMAIN_CODE,
    DOMAIN_MIXED,
    BudgetHints,
    TaskSpec,
)
from functions.logic_expectations import (  # noqa: E402
    EXPECT_FILE_EXISTS,
    EXPECT_RETURN_CODE,
)
from functions.logic_task_runner import ON_ERROR_SKIP, ON_ERROR_STOP, Plan  # noqa: E402
from functions.pipeline_code import (  # noqa: E402
    DEFAULT_OUTPUT_DIR_PREFIX,
    CodePipeline,
    _derive_filename,
    _file_path_join,
    _resolve_output_dir,
    _scaffold_content,
    _wants_lint,
    _wants_tests,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestDeriveFilename:
    def test_extracts_py_file_from_deliverable(self):
        assert _derive_filename("add models.py with User model", 1) == "models.py"

    def test_extracts_md_file(self):
        assert _derive_filename("write docs README.md", 2) == "README.md"

    def test_extracts_json(self):
        assert _derive_filename("update config.json", 3) == "config.json"

    def test_keeps_relative_path(self):
        assert _derive_filename("apps/users/views.py", 1) == "apps/users/views.py"

    def test_falls_back_to_slug(self):
        fn = _derive_filename("Some generic deliverable no file here", 5)
        assert fn.endswith(".py")
        assert fn.startswith("deliverable_5_")
        assert "some_generic_deliverable" in fn or "some_generic" in fn

    def test_fallback_no_tokens(self):
        fn = _derive_filename("!!!", 7)
        assert fn == "deliverable_7_module.py"

    def test_slug_truncated(self):
        long = " ".join(["word"] * 50)
        fn = _derive_filename(long, 1)
        assert len(fn) <= 80


class TestScaffoldContent:
    def test_py_file_contains_docstring_and_todo(self):
        spec = TaskSpec(goal="goal G", domain=DOMAIN_CODE, deliverables=["x.py"])
        content = _scaffold_content("x.py", spec, "x.py")
        assert content.startswith('"""')
        assert "Goal: goal G" in content
        assert "NotImplementedError" in content
        assert "TODO" in content

    def test_md_file_markdown(self):
        spec = TaskSpec(goal="G", domain=DOMAIN_CODE)
        content = _scaffold_content("Documentation", spec, "README.md")
        assert content.startswith("# ")
        assert "Goal: G" in content

    def test_generic_fallback(self):
        spec = TaskSpec(goal="G", domain=DOMAIN_CODE)
        content = _scaffold_content("notes", spec, "notes.txt")
        assert "Deliverable: notes" in content
        assert "Goal: G" in content

    def test_escapes_quotes_in_goal(self):
        spec = TaskSpec(goal='has "quotes" in', domain=DOMAIN_CODE)
        content = _scaffold_content("x", spec, "x.py")
        # Module docstring uses triple-double-quotes; single double-quotes
        # inside the goal must be stripped or escaped so the file parses.
        assert 'has ' in content
        # Easiest invariant: Python should be able to parse the scaffold.
        compile(content, "<scaffold>", "exec")


class TestResolveOutputDir:
    def test_uses_spec_output_dir(self):
        spec = TaskSpec(goal="g", output_dir="/tmp/out")
        assert _resolve_output_dir(spec) == "/tmp/out"

    def test_strips_trailing_slash(self):
        spec = TaskSpec(goal="g", output_dir="/tmp/out/")
        assert _resolve_output_dir(spec) == "/tmp/out"

    def test_defaults_to_workspace_prefix(self):
        spec = TaskSpec(goal="g", output_dir="", task_id="tid123")
        assert _resolve_output_dir(spec) == f"{DEFAULT_OUTPUT_DIR_PREFIX}/tid123"


class TestFilePathJoin:
    def test_basic(self):
        assert _file_path_join("a", "b.py") == "a/b.py"

    def test_strips_separators(self):
        assert _file_path_join("a/", "/b.py") == "a/b.py"

    def test_nested(self):
        assert _file_path_join("out", "apps/users/m.py") == "out/apps/users/m.py"


class TestWantsTests:
    def test_hint_in_deliverable(self):
        spec = TaskSpec(goal="g", deliverables=["test_users.py"])
        assert _wants_tests(spec)

    def test_hint_in_constraint(self):
        spec = TaskSpec(goal="g", constraints=["must pass pytest"])
        assert _wants_tests(spec)

    def test_hint_in_goal(self):
        spec = TaskSpec(goal="Add unit tests for parser")
        assert _wants_tests(spec)

    def test_no_hint(self):
        spec = TaskSpec(goal="generate hello world", deliverables=["hello.py"])
        assert not _wants_tests(spec)

    def test_filename_pattern(self):
        spec = TaskSpec(goal="g", deliverables=["module_test.py"])
        assert _wants_tests(spec)


class TestWantsLint:
    def test_lint_in_constraint(self):
        spec = TaskSpec(goal="g", constraints=["ruff clean"])
        assert _wants_lint(spec)

    def test_style_in_constraint(self):
        spec = TaskSpec(goal="g", constraints=["follow PEP 8 style"])
        assert _wants_lint(spec)

    def test_no_lint_hint(self):
        spec = TaskSpec(goal="generate code")
        assert not _wants_lint(spec)


# ---------------------------------------------------------------------------
# CodePipeline.compile
# ---------------------------------------------------------------------------


class TestCodePipelineCompile:
    def test_satisfies_pipeline_protocol(self):
        assert isinstance(CodePipeline(), Pipeline)

    def test_minimal_spec_produces_mkdir_and_scaffold(self):
        spec = TaskSpec(goal="generate hello world", domain=DOMAIN_CODE)
        plan = CodePipeline().compile(spec)
        assert isinstance(plan, Plan)
        assert len(plan.tasks) >= 2
        assert plan.tasks[0].id == "t1_mkdir"
        assert plan.tasks[0].kind == "run_command"
        assert plan.tasks[1].kind == "write_file"

    def test_uses_goal_as_deliverable_if_none(self):
        spec = TaskSpec(goal="build thing", domain=DOMAIN_CODE)
        plan = CodePipeline().compile(spec)
        write_tasks = [t for t in plan.tasks if t.kind == "write_file"]
        assert len(write_tasks) == 1

    def test_one_scaffold_per_deliverable(self):
        spec = TaskSpec(
            goal="X",
            domain=DOMAIN_CODE,
            deliverables=["models.py", "views.py", "serializers.py"],
        )
        plan = CodePipeline().compile(spec)
        write_tasks = [t for t in plan.tasks if t.kind == "write_file"]
        assert len(write_tasks) == 3
        paths = [t.params["path"] for t in write_tasks]
        assert all("models.py" in p or "views.py" in p or "serializers.py" in p for p in paths)

    def test_output_dir_from_spec(self):
        spec = TaskSpec(
            goal="X",
            domain=DOMAIN_CODE,
            output_dir="/tmp/agent_s7_out",
            deliverables=["m.py"],
        )
        plan = CodePipeline().compile(spec)
        # mkdir command references /tmp/agent_s7_out
        assert "/tmp/agent_s7_out" in plan.tasks[0].params["cmd"]
        # write_file path under output_dir
        write_task = [t for t in plan.tasks if t.kind == "write_file"][0]
        assert write_task.params["path"].startswith("/tmp/agent_s7_out/")
        assert plan.metadata["output_dir"] == "/tmp/agent_s7_out"

    def test_output_dir_defaults_to_workspace_task_id(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, task_id="tid_abc")
        plan = CodePipeline().compile(spec)
        assert "workspace/tid_abc" in plan.tasks[0].params["cmd"]

    def test_mkdir_has_return_code_expect(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE)
        plan = CodePipeline().compile(spec)
        mkdir_task = plan.tasks[0]
        assert len(mkdir_task.expect) == 1
        assert mkdir_task.expect[0].kind == EXPECT_RETURN_CODE
        assert mkdir_task.expect[0].params.get("value") == 0

    def test_scaffold_has_file_exists_expect(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["x.py"])
        plan = CodePipeline().compile(spec)
        write_task = [t for t in plan.tasks if t.kind == "write_file"][0]
        assert len(write_task.expect) == 1
        assert write_task.expect[0].kind == EXPECT_FILE_EXISTS
        assert write_task.expect[0].params["path"] == write_task.params["path"]

    def test_scaffold_depends_on_mkdir(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["x.py"])
        plan = CodePipeline().compile(spec)
        write_task = [t for t in plan.tasks if t.kind == "write_file"][0]
        assert "t1_mkdir" in write_task.depends_on

    def test_includes_pytest_when_tests_requested(self):
        spec = TaskSpec(
            goal="g",
            domain=DOMAIN_CODE,
            deliverables=["test_users.py"],
        )
        plan = CodePipeline().compile(spec)
        kinds = [t.kind for t in plan.tasks]
        cmds = [t.params.get("cmd", "") for t in plan.tasks if t.kind == "run_command"]
        assert any("pytest" in c for c in cmds)
        # Last (or one of last) tasks — pytest
        assert "pytest" in cmds[-1] or "pytest" in cmds[-2]
        assert "run_command" in kinds

    def test_skips_pytest_by_default(self):
        spec = TaskSpec(goal="hello world", domain=DOMAIN_CODE, deliverables=["hello.py"])
        plan = CodePipeline().compile(spec)
        cmds = [t.params.get("cmd", "") for t in plan.tasks]
        assert not any("pytest" in c for c in cmds)

    def test_force_tests_overrides(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["m.py"])
        plan = CodePipeline(force_tests=True).compile(spec)
        cmds = [t.params.get("cmd", "") for t in plan.tasks]
        assert any("pytest" in c for c in cmds)

    def test_includes_ruff_when_lint_requested(self):
        spec = TaskSpec(
            goal="g",
            domain=DOMAIN_CODE,
            deliverables=["m.py"],
            constraints=["must be lint-clean with ruff"],
        )
        plan = CodePipeline().compile(spec)
        cmds = [t.params.get("cmd", "") for t in plan.tasks]
        assert any("ruff check" in c for c in cmds)

    def test_force_lint_overrides(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["m.py"])
        plan = CodePipeline(force_lint=True).compile(spec)
        cmds = [t.params.get("cmd", "") for t in plan.tasks]
        assert any("ruff check" in c for c in cmds)

    def test_ruff_task_is_skip_on_error(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["m.py"])
        plan = CodePipeline(force_lint=True).compile(spec)
        ruff_task = next(
            t for t in plan.tasks if "ruff check" in t.params.get("cmd", "")
        )
        assert ruff_task.on_error == ON_ERROR_SKIP

    def test_pytest_task_is_stop_on_error(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["m.py"])
        plan = CodePipeline(force_tests=True).compile(spec)
        pytest_task = next(
            t for t in plan.tasks if "pytest" in t.params.get("cmd", "")
        )
        assert pytest_task.on_error == ON_ERROR_STOP

    def test_custom_pytest_cmd(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["m.py"])
        pipe = CodePipeline(force_tests=True, pytest_cmd="poetry run pytest")
        plan = pipe.compile(spec)
        pytest_cmds = [
            t.params["cmd"] for t in plan.tasks if "pytest" in t.params.get("cmd", "")
        ]
        assert any("poetry run pytest" in c for c in pytest_cmds)

    def test_custom_ruff_cmd_and_timeouts(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["m.py"])
        pipe = CodePipeline(
            force_tests=True,
            force_lint=True,
            ruff_cmd="ruff check --no-cache",
            test_timeout_s=5.0,
            lint_timeout_s=7.0,
        )
        plan = pipe.compile(spec)
        ruff_task = next(
            t for t in plan.tasks if "ruff check" in t.params.get("cmd", "")
        )
        assert "--no-cache" in ruff_task.params["cmd"]
        assert ruff_task.params["timeout"] == 7.0
        pytest_task = next(
            t for t in plan.tasks if "pytest" in t.params.get("cmd", "")
        )
        assert pytest_task.params["timeout"] == 5.0

    def test_metadata_fields(self):
        spec = TaskSpec(
            goal="g",
            domain=DOMAIN_CODE,
            deliverables=["m.py"],
            task_id="tid123",
        )
        plan = CodePipeline(force_tests=True, force_lint=True).compile(spec)
        md = plan.metadata
        assert md["pipeline"] == "code"
        assert md["domain"] == DOMAIN_CODE
        assert md["task_id"] == "tid123"
        assert md["tests_enabled"] is True
        assert md["lint_enabled"] is True
        assert "m.py" in md["filenames"]

    def test_plan_name_truncated(self):
        spec = TaskSpec(goal="x" * 500, domain=DOMAIN_CODE)
        plan = CodePipeline().compile(spec)
        assert len(plan.name) <= 200

    def test_dedup_deliverable_filenames(self):
        spec = TaskSpec(
            goal="g",
            domain=DOMAIN_CODE,
            # Both collapse to "users.py" via _derive_filename
            deliverables=["make users.py nice", "tweak users.py style"],
        )
        plan = CodePipeline().compile(spec)
        write_tasks = [t for t in plan.tasks if t.kind == "write_file"]
        paths = [t.params["path"] for t in write_tasks]
        assert len(paths) == 2
        assert len(set(paths)) == 2  # de-duped

    def test_shell_quoting_for_path_with_spaces(self):
        spec = TaskSpec(
            goal="g",
            domain=DOMAIN_CODE,
            output_dir="/tmp/path with spaces",
            deliverables=["m.py"],
        )
        plan = CodePipeline().compile(spec)
        mkdir_cmd = plan.tasks[0].params["cmd"]
        # shlex.quote will wrap in single quotes
        assert "'/tmp/path with spaces'" in mkdir_cmd


class TestCodePipelineRequiredTools:
    def test_minimal(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE)
        tools = CodePipeline().required_tools(spec)
        assert "run_command" in tools
        assert "write_file" in tools
        assert "pytest" not in tools
        assert "ruff" not in tools

    def test_with_tests(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, deliverables=["test_x.py"])
        tools = CodePipeline().required_tools(spec)
        assert "pytest" in tools

    def test_with_lint(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE, constraints=["ruff clean"])
        tools = CodePipeline().required_tools(spec)
        assert "ruff" in tools

    def test_force_flags(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_CODE)
        tools = CodePipeline(force_tests=True, force_lint=True).required_tools(spec)
        assert "pytest" in tools
        assert "ruff" in tools


# ---------------------------------------------------------------------------
# Integration: compile_plan_from_spec with default registry
# ---------------------------------------------------------------------------


class TestDefaultRegistryIntegration:
    def test_code_domain_hits_code_pipeline(self):
        spec = TaskSpec(
            goal="django user CRUD",
            domain=DOMAIN_CODE,
            deliverables=["models.py", "views.py"],
        )
        plan = compile_plan_from_spec(spec)
        assert plan.metadata["pipeline"] == "code"
        # mkdir + 2 scaffolds = 3 tasks minimum (no tests/lint unless hinted)
        assert len(plan.tasks) == 3

    def test_mixed_domain_still_skeleton(self):
        spec = TaskSpec(goal="g", domain=DOMAIN_MIXED)
        plan = compile_plan_from_spec(spec)
        assert plan.metadata["pipeline"] == "skeleton"

    def test_default_registry_lists_code_pipeline_instance(self):
        reg = make_default_registry()
        from functions.pipeline_code import CodePipeline

        assert isinstance(reg.get(DOMAIN_CODE), CodePipeline)

    def test_budget_in_spec_does_not_break_compile(self):
        spec = TaskSpec(
            goal="g",
            domain=DOMAIN_CODE,
            deliverables=["m.py"],
            budget=BudgetHints(max_hours=1.5, max_cost_usd=0.5),
        )
        plan = CodePipeline().compile(spec)
        # pipeline не зобов'язаний інтегрувати budget (це робить TaskRunner),
        # але compile не повинен падати
        assert plan.tasks


# ---------------------------------------------------------------------------
# End-to-end smoke: compile, then execute against TaskRunner (tmp dir)
# ---------------------------------------------------------------------------


class TestCodePipelineEndToEnd:
    def test_plan_executes_against_real_runner(self, tmp_path):
        """Компільований Plan має запускатися через TaskRunner.

        Використовуємо реальний subprocess (для `mkdir`) і реальний
        `write_file`, без expect-перевірок (щоб тест не залежав від
        pytest/ruff у PATH). Перевіряємо що файл дійсно створено.
        """
        from functions.logic_permission_gate import PermissionGate, always_allow
        from functions.logic_task_runner import TaskRunner

        out = tmp_path / "s7_out"
        spec = TaskSpec(
            goal="smoke-run scaffold generation",
            domain=DOMAIN_CODE,
            deliverables=["smoke.py"],
            output_dir=str(out),
        )
        plan = CodePipeline().compile(spec)
        gate = PermissionGate(ask_fn=always_allow())
        runner = TaskRunner(gate=gate)
        result = runner.run(plan)
        # mkdir + scaffold повинні пройти
        assert result.all_ok, (
            f"run failed: stop={result.stop_reason} steps="
            + str([(s.task_id, s.status) for s in result.report.steps])
        )
        assert (out / "smoke.py").exists()
        content = (out / "smoke.py").read_text(encoding="utf-8")
        assert "smoke-run scaffold generation" in content
