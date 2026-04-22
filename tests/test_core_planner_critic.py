"""Unit tests for `functions/core_planner_critic.py` — legacy Planner ↔ PlanCritic bridge.

Використовує `CallableProvider` для симуляції відповідей LLM без мережі.
Не залежить від реального `Planner` — замість нього використовуємо dummy-обʼєкт
з `.create_plan()` методом у тестах replan-логіки.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from functions.core_planner_critic import (
    LegacyCritiqueResult,
    legacy_plan_to_plan,
    legacy_step_to_task,
    make_planner_replan_fn,
    review_and_replan_legacy,
    review_legacy_plan,
)
from functions.logic_ai_adapter import (
    CallableProvider,
    ChatRequest,
    ChatResponse,
    ProviderCapabilities,
    UsageInfo,
)
from functions.logic_plan_critic import (
    CritiqueResult,
    PlanCritic,
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    VERDICT_APPROVE,
    VERDICT_CONCERNS,
    VERDICT_REDO,
)
from functions.logic_provider_registry import ProviderRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry_with_responses(*payloads: str) -> ProviderRegistry:
    """ProviderRegistry з `CallableProvider`, що по черзі повертає задані payload-и.

    Після вичерпання списку — повертає останній.
    """

    state = {"idx": 0}

    def fn(_req: ChatRequest) -> ChatResponse:
        idx = min(state["idx"], len(payloads) - 1)
        state["idx"] += 1
        return ChatResponse(
            content=payloads[idx],
            provider="critic",
            model="test-model",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    registry = ProviderRegistry()
    registry.register(
        CallableProvider(
            fn,
            name="critic",
            capabilities=ProviderCapabilities(offline=True),
        )
    )
    return registry


def _critic_with_responses(*payloads: str) -> PlanCritic:
    return PlanCritic(registry=_registry_with_responses(*payloads))


def _sample_legacy_plan() -> List[Dict[str, Any]]:
    return [
        {
            "action": "create_file",
            "args": {"path": "a.txt", "content": "hi"},
            "goal": "створити файл a",
            "validation": "a.txt існує",
        },
        {
            "action": "execute_python",
            "args": {"code": "print('hi')"},
            "goal": "запустити скрипт",
            "validation": "вивід містить hi",
        },
    ]


# ---------------------------------------------------------------------------
# legacy_step_to_task
# ---------------------------------------------------------------------------


class TestLegacyStepToTask:
    def test_basic_conversion(self) -> None:
        step = {
            "action": "create_file",
            "args": {"path": "a.txt"},
            "goal": "створити файл",
            "validation": "файл існує",
        }
        task = legacy_step_to_task(step, 0)
        assert task.kind == "create_file"
        assert task.id == "step_1"
        assert task.name == "створити файл"
        assert task.params["path"] == "a.txt"
        assert task.params["_legacy"]["goal"] == "створити файл"
        assert task.params["_legacy"]["validation"] == "файл існує"
        assert task.on_error == "stop"
        assert task.depends_on == []

    def test_fallback_kind_when_action_missing(self) -> None:
        task = legacy_step_to_task({"args": {"x": 1}}, 3)
        assert task.kind == "step_3"
        assert task.id == "step_4"

    def test_name_defaults_to_kind_when_goal_absent(self) -> None:
        task = legacy_step_to_task({"action": "noop", "args": {}}, 0)
        assert task.name == "noop"

    def test_args_not_a_dict_defaults_to_empty(self) -> None:
        task = legacy_step_to_task({"action": "x", "args": "bad"}, 0)
        assert task.params == {}

    def test_no_legacy_meta_when_goal_and_validation_empty(self) -> None:
        task = legacy_step_to_task({"action": "x", "args": {"y": 1}}, 0)
        assert "_legacy" not in task.params

    def test_only_goal_populates_legacy(self) -> None:
        task = legacy_step_to_task(
            {"action": "x", "args": {}, "goal": "g"}, 0
        )
        assert task.params["_legacy"] == {"goal": "g"}

    def test_params_are_copied_not_shared(self) -> None:
        args = {"mutable": [1, 2]}
        task = legacy_step_to_task({"action": "x", "args": args}, 0)
        task.params["mutable"].append(3)
        assert args["mutable"] == [1, 2]


# ---------------------------------------------------------------------------
# legacy_plan_to_plan
# ---------------------------------------------------------------------------


class TestLegacyPlanToPlan:
    def test_empty_list_produces_empty_plan(self) -> None:
        plan = legacy_plan_to_plan([])
        assert plan.tasks == []
        assert plan.name == "legacy_plan"

    def test_none_safe(self) -> None:
        plan = legacy_plan_to_plan(None)  # type: ignore[arg-type]
        assert plan.tasks == []

    def test_converts_two_steps(self) -> None:
        legacy = _sample_legacy_plan()
        plan = legacy_plan_to_plan(legacy, name="my_plan")
        assert plan.name == "my_plan"
        assert [t.kind for t in plan.tasks] == ["create_file", "execute_python"]
        assert [t.id for t in plan.tasks] == ["step_1", "step_2"]

    def test_metadata_is_passed_through(self) -> None:
        plan = legacy_plan_to_plan(
            _sample_legacy_plan(), metadata={"source": "legacy"}
        )
        assert plan.metadata == {"source": "legacy"}


# ---------------------------------------------------------------------------
# review_legacy_plan
# ---------------------------------------------------------------------------


class TestReviewLegacyPlan:
    def test_calls_critic_and_returns_approve(self) -> None:
        critic = _critic_with_responses('{"verdict":"approve","summary":"ok"}')
        result = review_legacy_plan(
            _sample_legacy_plan(),
            critic=critic,
            task_description="створи файл і запусти скрипт",
        )
        assert isinstance(result, CritiqueResult)
        assert result.verdict == VERDICT_APPROVE
        assert result.summary == "ok"
        assert not result.blocking

    def test_redo_verdict_marked_blocking(self) -> None:
        critic = _critic_with_responses(
            '{"verdict":"redo","summary":"unsafe","concerns":['
            '{"message":"rm -rf","severity":"block"}]}'
        )
        result = review_legacy_plan(
            _sample_legacy_plan(), critic=critic
        )
        assert result.verdict == VERDICT_REDO
        assert result.blocking

    def test_concerns_with_block_severity_becomes_blocking(self) -> None:
        critic = _critic_with_responses(
            '{"verdict":"concerns","concerns":['
            '{"message":"дуже ризиковано","severity":"block"}]}'
        )
        result = review_legacy_plan(
            _sample_legacy_plan(), critic=critic
        )
        assert result.blocking

    def test_empty_legacy_plan_still_reviewed(self) -> None:
        critic = _critic_with_responses('{"verdict":"approve"}')
        result = review_legacy_plan([], critic=critic)
        assert result.verdict == VERDICT_APPROVE


# ---------------------------------------------------------------------------
# review_and_replan_legacy
# ---------------------------------------------------------------------------


class TestReviewAndReplanLegacy:
    def test_approve_first_attempt(self) -> None:
        critic = _critic_with_responses('{"verdict":"approve"}')
        out = review_and_replan_legacy(
            _sample_legacy_plan(), critic=critic
        )
        assert isinstance(out, LegacyCritiqueResult)
        assert out.approved is True
        assert out.attempts == 1
        assert out.blocking is False

    def test_redo_without_replan_fn_returns_blocked(self) -> None:
        critic = _critic_with_responses('{"verdict":"redo"}')
        out = review_and_replan_legacy(
            _sample_legacy_plan(), critic=critic
        )
        assert out.approved is False
        assert out.attempts == 1
        assert out.blocking is True
        assert "replan_fn=none" in out.stop_reason

    def test_redo_then_approve_after_replan(self) -> None:
        critic = _critic_with_responses(
            '{"verdict":"redo","concerns":[{"message":"bad path","severity":"block"}]}',
            '{"verdict":"approve","summary":"ok"}',
        )

        def replan(
            _plan: List[Dict[str, Any]], _critique: CritiqueResult
        ) -> List[Dict[str, Any]]:
            return [{"action": "noop", "args": {}}]

        out = review_and_replan_legacy(
            _sample_legacy_plan(), critic=critic, replan_fn=replan, max_redos=1
        )
        assert out.approved is True
        assert out.attempts == 2
        assert out.plan == [{"action": "noop", "args": {}}]

    def test_replan_returns_none_stops_cycle(self) -> None:
        critic = _critic_with_responses('{"verdict":"redo"}')

        def replan(
            _plan: List[Dict[str, Any]], _critique: CritiqueResult
        ) -> Optional[List[Dict[str, Any]]]:
            return None

        out = review_and_replan_legacy(
            _sample_legacy_plan(), critic=critic, replan_fn=replan, max_redos=3
        )
        assert out.approved is False
        assert "returned None" in out.stop_reason

    def test_max_redos_zero_short_circuits(self) -> None:
        critic = _critic_with_responses('{"verdict":"redo"}', '{"verdict":"approve"}')
        called: List[int] = []

        def replan(
            _plan: List[Dict[str, Any]], _critique: CritiqueResult
        ) -> List[Dict[str, Any]]:
            called.append(1)
            return [{"action": "noop", "args": {}}]

        out = review_and_replan_legacy(
            _sample_legacy_plan(), critic=critic, replan_fn=replan, max_redos=0
        )
        assert out.approved is False
        assert out.attempts == 1
        assert called == []  # replan never called when max_redos=0

    def test_redo_twice_exhausts_attempts(self) -> None:
        critic = _critic_with_responses(
            '{"verdict":"redo"}', '{"verdict":"redo"}', '{"verdict":"redo"}'
        )

        def replan(
            plan: List[Dict[str, Any]], _critique: CritiqueResult
        ) -> List[Dict[str, Any]]:
            return plan  # unchanged

        out = review_and_replan_legacy(
            _sample_legacy_plan(), critic=critic, replan_fn=replan, max_redos=1
        )
        assert out.approved is False
        assert out.attempts == 2
        assert "exhausted" in out.stop_reason

    def test_plan_is_copied_not_shared(self) -> None:
        critic = _critic_with_responses('{"verdict":"approve"}')
        original = _sample_legacy_plan()
        out = review_and_replan_legacy(original, critic=critic)
        out.plan[0]["action"] = "MUTATED"
        assert original[0]["action"] == "create_file"


# ---------------------------------------------------------------------------
# make_planner_replan_fn
# ---------------------------------------------------------------------------


class _DummyPlanner:
    """Fake Planner з тим же публічним API (`create_plan(task, context=None)`)."""

    def __init__(self, response: List[Dict[str, Any]]) -> None:
        self.response = response
        self.calls: List[Dict[str, Any]] = []

    def create_plan(
        self, task: str, context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        self.calls.append({"task": task, "context": context})
        return list(self.response)


class TestMakePlannerReplanFn:
    def test_calls_create_plan_with_concerns_block(self) -> None:
        dummy = _DummyPlanner([{"action": "noop", "args": {}}])
        replan = make_planner_replan_fn(dummy, "створи щось безпечно")
        critique = CritiqueResult(
            verdict=VERDICT_REDO,
            summary="план небезпечний",
        )
        critique.concerns.append(
            __import__("functions.logic_plan_critic", fromlist=["Concern"]).Concern(
                message="шлях містить rm -rf",
                severity=SEVERITY_BLOCK,
                suggestion="використати cleanup_tmp",
                task_id="step_2",
            )
        )
        result = replan([{"action": "bad", "args": {}}], critique)
        assert result == [{"action": "noop", "args": {}}]
        assert len(dummy.calls) == 1
        payload = dummy.calls[0]["task"]
        assert "створи щось безпечно" in payload
        assert "BLOCK" in payload
        assert "шлях містить rm -rf" in payload
        assert "cleanup_tmp" in payload
        assert "step_2" in payload

    def test_passes_context_through(self) -> None:
        dummy = _DummyPlanner([{"action": "noop", "args": {}}])
        replan = make_planner_replan_fn(
            dummy, "задача", context={"artifacts_summary": "foo"}
        )
        replan([], CritiqueResult(verdict=VERDICT_REDO))
        assert dummy.calls[0]["context"] == {"artifacts_summary": "foo"}

    def test_non_list_response_returns_none(self) -> None:
        dummy = _DummyPlanner([])
        dummy.create_plan = lambda task, context=None: None  # type: ignore[assignment]
        replan = make_planner_replan_fn(dummy, "задача")
        assert replan([], CritiqueResult(verdict=VERDICT_REDO)) is None

    def test_exception_returns_none(self) -> None:
        dummy = _DummyPlanner([])

        def raise_(*_a: Any, **_kw: Any) -> Any:
            raise RuntimeError("planner broken")

        dummy.create_plan = raise_  # type: ignore[assignment]
        replan = make_planner_replan_fn(dummy, "задача")
        assert replan([], CritiqueResult(verdict=VERDICT_REDO)) is None

    def test_full_cycle_via_review_and_replan(self) -> None:
        critic = _critic_with_responses(
            '{"verdict":"redo","concerns":[{"message":"погано","severity":"block"}]}',
            '{"verdict":"approve","summary":"безпечно"}',
        )
        dummy = _DummyPlanner([{"action": "safe_alt", "args": {}}])
        replan = make_planner_replan_fn(dummy, "оригінальна задача")
        out = review_and_replan_legacy(
            [{"action": "risky", "args": {}}],
            critic=critic,
            replan_fn=replan,
            max_redos=1,
        )
        assert out.approved is True
        assert out.attempts == 2
        assert out.plan == [{"action": "safe_alt", "args": {}}]
        assert dummy.calls[0]["task"].startswith("оригінальна задача")


# ---------------------------------------------------------------------------
# Cross-checks with real PlanCritic behaviour
# ---------------------------------------------------------------------------


class TestIntegrationWithRealPlanCritic:
    def test_serialized_plan_contains_goal_and_validation_in_legacy_meta(
        self,
    ) -> None:
        """Критик повинен мати доступ до `goal`/`validation` через params._legacy."""
        from functions.logic_plan_critic import serialize_plan

        plan = legacy_plan_to_plan(_sample_legacy_plan())
        serialized = serialize_plan(plan)
        assert serialized["tasks"][0]["params"]["_legacy"]["goal"] == "створити файл a"
        assert (
            serialized["tasks"][1]["params"]["_legacy"]["validation"]
            == "вивід містить hi"
        )

    def test_concerns_verdict_with_no_block_severity_is_approved(self) -> None:
        critic = _critic_with_responses(
            '{"verdict":"concerns","concerns":['
            '{"message":"дрібниця","severity":"warn"}]}'
        )
        out = review_and_replan_legacy(
            _sample_legacy_plan(), critic=critic
        )
        assert out.approved is True
        assert out.critique.verdict == VERDICT_CONCERNS
        assert out.critique.concerns[0].severity == SEVERITY_WARN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
