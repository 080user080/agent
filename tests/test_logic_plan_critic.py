"""Тести до `logic_plan_critic`.

CallableProvider дозволяє вбудувати будь-який JSON-вердикт у відповідь,
не роблячи HTTP-викликів.
"""

from __future__ import annotations

import json
from typing import List

import pytest

from functions.logic_ai_adapter import (
    CallableProvider,
    ChatRequest,
    ChatResponse,
    ProviderCapabilities,
    UsageInfo,
)
from functions.logic_plan_critic import (
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    VERDICT_APPROVE,
    VERDICT_CONCERNS,
    VERDICT_REDO,
    Concern,
    CritiqueResult,
    PlanCritic,
    build_critic_messages,
    parse_critic_response,
    parse_critique_payload,
    review_and_run_plan,
    serialize_plan,
)
from functions.logic_provider_registry import ProviderRegistry
from functions.logic_task_runner import Plan, Task, TaskRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan(name: str = "demo", kinds: List[str] | None = None) -> Plan:
    kinds = kinds or ["noop", "log"]
    tasks = [
        Task(id=f"t{i + 1}", kind=k, name=f"step {i + 1}", params={"index": i})
        for i, k in enumerate(kinds)
    ]
    return Plan(name=name, tasks=tasks, metadata={"source": "test"})


def _registry_with_response(payload: str, *, error: str = "") -> ProviderRegistry:
    """Реєстр з CallableProvider, що повертає заданий контент."""

    def fn(req: ChatRequest) -> ChatResponse:
        if error:
            return ChatResponse(
                finish_reason="error",
                error=error,
                provider="critic",
            )
        return ChatResponse(
            content=payload,
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


# ---------------------------------------------------------------------------
# serialize_plan
# ---------------------------------------------------------------------------


class TestSerializePlan:
    def test_includes_tasks_and_metadata(self) -> None:
        plan = _plan("p", ["noop", "log", "sleep"])
        data = serialize_plan(plan)
        assert data["name"] == "p"
        assert data["metadata"] == {"source": "test"}
        assert [t["kind"] for t in data["tasks"]] == ["noop", "log", "sleep"]
        assert data["tasks"][0]["id"] == "t1"

    def test_exposes_depends_on_and_on_error(self) -> None:
        plan = Plan(
            name="p",
            tasks=[
                Task(id="a", kind="noop"),
                Task(id="b", kind="log", depends_on=["a"], on_error="skip"),
            ],
        )
        data = serialize_plan(plan)
        assert data["tasks"][1]["depends_on"] == ["a"]
        assert data["tasks"][1]["on_error"] == "skip"


# ---------------------------------------------------------------------------
# build_critic_messages
# ---------------------------------------------------------------------------


class TestBuildCriticMessages:
    def test_returns_system_and_user(self) -> None:
        msgs = build_critic_messages(_plan())
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"
        # план має бути у user-повідомленні JSON-ом
        assert "tasks" in msgs[1].content
        assert "demo" in msgs[1].content

    def test_context_and_policies_included(self) -> None:
        msgs = build_critic_messages(
            _plan(),
            context="project_root=/tmp/foo",
            policies={"allow": ["git status"], "deny": ["rm -rf /"]},
        )
        user = msgs[1].content
        assert "/tmp/foo" in user
        assert "git status" in user
        assert "rm -rf" in user

    def test_custom_system_prompt(self) -> None:
        msgs = build_critic_messages(_plan(), system_prompt="CUSTOM")
        assert msgs[0].content == "CUSTOM"


# ---------------------------------------------------------------------------
# parse_critique_payload
# ---------------------------------------------------------------------------


class TestParseCritiquePayload:
    def test_approve(self) -> None:
        res = parse_critique_payload(
            {"verdict": "approve", "summary": "ok", "concerns": []}
        )
        assert res.verdict == VERDICT_APPROVE
        assert res.summary == "ok"
        assert res.concerns == []

    def test_concerns_with_warn(self) -> None:
        res = parse_critique_payload(
            {
                "verdict": "concerns",
                "summary": "minor",
                "concerns": [
                    {"task_id": "t2", "severity": "warn", "message": "slow step"}
                ],
            }
        )
        assert res.verdict == VERDICT_CONCERNS
        assert len(res.concerns) == 1
        assert res.concerns[0].task_id == "t2"
        assert res.concerns[0].severity == SEVERITY_WARN

    def test_redo_on_block_severity(self) -> None:
        # LLM may output "approve" yet include a block concern → override to redo
        res = parse_critique_payload(
            {
                "verdict": "approve",
                "concerns": [{"severity": "block", "message": "rm -rf /home"}],
            }
        )
        assert res.verdict == VERDICT_REDO

    def test_approve_upgraded_to_concerns_if_has_non_block(self) -> None:
        res = parse_critique_payload(
            {
                "verdict": "approve",
                "concerns": [{"severity": "info", "message": "nit"}],
            }
        )
        assert res.verdict == VERDICT_CONCERNS

    def test_unknown_verdict_defaults_to_concerns(self) -> None:
        res = parse_critique_payload({"verdict": "maybe"})
        assert res.verdict == VERDICT_CONCERNS

    def test_unknown_severity_defaults_to_warn(self) -> None:
        res = parse_critique_payload(
            {
                "verdict": "concerns",
                "concerns": [{"severity": "catastrophic", "message": "x"}],
            }
        )
        assert res.concerns[0].severity == SEVERITY_WARN

    def test_empty_message_skipped(self) -> None:
        res = parse_critique_payload(
            {
                "verdict": "concerns",
                "concerns": [{"severity": "warn", "message": ""}],
            }
        )
        assert res.concerns == []

    def test_non_list_concerns_ignored(self) -> None:
        res = parse_critique_payload(
            {"verdict": "approve", "concerns": "oops"}
        )
        assert res.concerns == []
        assert res.verdict == VERDICT_APPROVE

    def test_non_dict_entries_skipped(self) -> None:
        res = parse_critique_payload(
            {"verdict": "concerns", "concerns": ["text", 42, None]}
        )
        assert res.concerns == []


# ---------------------------------------------------------------------------
# parse_critic_response
# ---------------------------------------------------------------------------


class TestParseCriticResponse:
    def test_bare_json(self) -> None:
        resp = ChatResponse(
            content=json.dumps({"verdict": "approve", "summary": "ok"})
        )
        res = parse_critic_response(resp)
        assert res.verdict == VERDICT_APPROVE
        assert res.parse_error == ""

    def test_fenced_json(self) -> None:
        content = (
            "Sure, here is my analysis:\n"
            "```json\n"
            '{"verdict": "concerns", "summary": "slow", "concerns": []}\n'
            "```"
        )
        res = parse_critic_response(ChatResponse(content=content))
        assert res.verdict == VERDICT_CONCERNS

    def test_extracts_from_prose(self) -> None:
        content = (
            "prefix text\n"
            '{"verdict":"redo","concerns":[{"severity":"block","message":"x"}]}\n'
            "suffix"
        )
        res = parse_critic_response(ChatResponse(content=content))
        assert res.verdict == VERDICT_REDO
        assert res.blocking is True

    def test_invalid_json_sets_parse_error(self) -> None:
        res = parse_critic_response(ChatResponse(content="{not json}"))
        assert res.parse_error != ""
        assert res.verdict == VERDICT_CONCERNS

    def test_no_json_at_all(self) -> None:
        res = parse_critic_response(ChatResponse(content="just free text"))
        assert res.parse_error == "no JSON object found"
        assert res.verdict == VERDICT_CONCERNS

    def test_non_object_payload(self) -> None:
        res = parse_critic_response(ChatResponse(content='[1,2,3]'))
        # _extract_json_block вимагає {...}, масив не пройде
        assert res.parse_error != ""

    def test_provider_error(self) -> None:
        resp = ChatResponse(
            finish_reason="error", error="timeout", provider="x"
        )
        res = parse_critic_response(resp)
        assert res.parse_error == "timeout"
        assert res.verdict == VERDICT_CONCERNS
        assert res.provider == "x"

    def test_usage_propagated(self) -> None:
        resp = ChatResponse(
            content='{"verdict":"approve"}',
            provider="p",
            model="m",
            usage=UsageInfo(prompt_tokens=3, completion_tokens=2, total_tokens=5),
        )
        res = parse_critic_response(resp)
        assert res.usage.total_tokens == 5
        assert res.provider == "p"
        assert res.model == "m"


# ---------------------------------------------------------------------------
# CritiqueResult props
# ---------------------------------------------------------------------------


class TestCritiqueResultProps:
    def test_ok_for_approve(self) -> None:
        assert CritiqueResult(verdict=VERDICT_APPROVE).ok is True
        assert CritiqueResult(verdict=VERDICT_APPROVE).blocking is False

    def test_ok_for_concerns_no_block(self) -> None:
        r = CritiqueResult(verdict=VERDICT_CONCERNS)
        assert r.ok is True
        assert r.blocking is False

    def test_blocking_on_redo(self) -> None:
        r = CritiqueResult(verdict=VERDICT_REDO)
        assert r.ok is False
        assert r.blocking is True

    def test_blocking_on_block_severity(self) -> None:
        r = CritiqueResult(
            verdict=VERDICT_CONCERNS,
            concerns=[Concern(message="x", severity=SEVERITY_BLOCK)],
        )
        assert r.blocking is True

    def test_to_dict_roundtrip(self) -> None:
        r = CritiqueResult(
            verdict=VERDICT_CONCERNS,
            summary="s",
            concerns=[Concern(message="m", severity=SEVERITY_WARN, task_id="a")],
        )
        d = r.to_dict()
        assert d["verdict"] == VERDICT_CONCERNS
        assert d["concerns"][0]["task_id"] == "a"


# ---------------------------------------------------------------------------
# PlanCritic
# ---------------------------------------------------------------------------


class TestPlanCritic:
    def test_review_approve(self) -> None:
        reg = _registry_with_response(
            json.dumps({"verdict": "approve", "summary": "ok"})
        )
        critic = PlanCritic(registry=reg)
        res = critic.review(_plan())
        assert res.verdict == VERDICT_APPROVE
        assert res.provider == "critic"
        assert res.usage.prompt_tokens == 10

    def test_review_redo(self) -> None:
        reg = _registry_with_response(
            json.dumps(
                {
                    "verdict": "redo",
                    "summary": "dangerous",
                    "concerns": [
                        {
                            "task_id": "t1",
                            "severity": "block",
                            "message": "deletes home dir",
                        }
                    ],
                }
            )
        )
        critic = PlanCritic(registry=reg)
        res = critic.review(_plan())
        assert res.verdict == VERDICT_REDO
        assert res.blocking is True
        assert len(res.concerns) == 1

    def test_review_with_provider_error(self) -> None:
        reg = _registry_with_response("", error="boom")
        critic = PlanCritic(registry=reg)
        res = critic.review(_plan())
        assert res.parse_error == "boom"

    def test_context_forwarded_to_messages(self) -> None:
        captured: List[ChatRequest] = []

        def fn(req: ChatRequest) -> ChatResponse:
            captured.append(req)
            return ChatResponse(content='{"verdict":"approve"}')

        reg = ProviderRegistry()
        reg.register(
            CallableProvider(
                fn, name="spy", capabilities=ProviderCapabilities(offline=True)
            )
        )
        PlanCritic(registry=reg).review(
            _plan(), context="root=/x", policies={"k": "v"}
        )
        assert len(captured) == 1
        user = captured[0].messages[1].content
        assert "root=/x" in user
        assert '"k"' in user

    def test_metadata_on_request(self) -> None:
        seen: List[ChatRequest] = []

        def fn(req: ChatRequest) -> ChatResponse:
            seen.append(req)
            return ChatResponse(content='{"verdict":"approve"}')

        reg = ProviderRegistry()
        reg.register(
            CallableProvider(
                fn, name="spy", capabilities=ProviderCapabilities(offline=True)
            )
        )
        PlanCritic(registry=reg).review(_plan("my-plan"))
        assert seen[0].metadata["purpose"] == "plan_critic"
        assert seen[0].metadata["plan_name"] == "my-plan"


# ---------------------------------------------------------------------------
# review_and_run_plan
# ---------------------------------------------------------------------------


class TestReviewAndRunPlan:
    def test_approve_then_run(self) -> None:
        reg = _registry_with_response(json.dumps({"verdict": "approve"}))
        critic = PlanCritic(registry=reg)
        runner = TaskRunner()
        res = review_and_run_plan(_plan(), critic=critic, runner=runner)
        assert res.executed is True
        assert res.attempts == 1
        assert res.run_result is not None
        assert res.run_result.all_ok is True

    def test_blocking_without_replan_aborts(self) -> None:
        reg = _registry_with_response(
            json.dumps(
                {
                    "verdict": "redo",
                    "concerns": [{"severity": "block", "message": "nope"}],
                }
            )
        )
        critic = PlanCritic(registry=reg)
        runner = TaskRunner()
        res = review_and_run_plan(_plan(), critic=critic, runner=runner)
        assert res.executed is False
        assert res.attempts == 1
        assert "critic blocked" in res.stop_reason

    def test_blocking_with_successful_replan(self) -> None:
        # Critic says redo once, then approve.
        responses = iter(
            [
                json.dumps(
                    {
                        "verdict": "redo",
                        "concerns": [{"severity": "block", "message": "x"}],
                    }
                ),
                json.dumps({"verdict": "approve"}),
            ]
        )

        def fn(req: ChatRequest) -> ChatResponse:
            return ChatResponse(content=next(responses), provider="critic")

        reg = ProviderRegistry()
        reg.register(
            CallableProvider(
                fn,
                name="critic",
                capabilities=ProviderCapabilities(offline=True),
            )
        )

        def replan(old: Plan, _crit: CritiqueResult) -> Plan:
            return Plan(
                name=old.name + "-fixed",
                tasks=[Task(id="safe", kind="noop")],
            )

        res = review_and_run_plan(
            _plan(),
            critic=PlanCritic(registry=reg),
            runner=TaskRunner(),
            max_redos=1,
            replan_fn=replan,
        )
        assert res.executed is True
        assert res.attempts == 2
        assert res.final_plan.name.endswith("-fixed")

    def test_replan_returns_none_aborts(self) -> None:
        reg = _registry_with_response(
            json.dumps(
                {
                    "verdict": "redo",
                    "concerns": [{"severity": "block", "message": "x"}],
                }
            )
        )
        res = review_and_run_plan(
            _plan(),
            critic=PlanCritic(registry=reg),
            runner=TaskRunner(),
            max_redos=3,
            replan_fn=lambda p, c: None,
        )
        assert res.executed is False
        assert res.stop_reason == "replan_fn returned None"

    def test_exhausts_redos(self) -> None:
        # критик завжди каже redo
        reg = _registry_with_response(
            json.dumps(
                {
                    "verdict": "redo",
                    "concerns": [{"severity": "block", "message": "x"}],
                }
            )
        )
        attempts: List[int] = []

        def replan(old: Plan, _crit: CritiqueResult) -> Plan:
            attempts.append(1)
            return old  # не покращуємо

        res = review_and_run_plan(
            _plan(),
            critic=PlanCritic(registry=reg),
            runner=TaskRunner(),
            max_redos=2,
            replan_fn=replan,
        )
        # 1-й огляд + 2 replans × по огляду після = 3
        assert res.executed is False
        assert res.attempts == 3
        assert len(attempts) == 2

    def test_concerns_verdict_still_runs(self) -> None:
        reg = _registry_with_response(
            json.dumps(
                {
                    "verdict": "concerns",
                    "concerns": [{"severity": "warn", "message": "slow"}],
                }
            )
        )
        res = review_and_run_plan(
            _plan(), critic=PlanCritic(registry=reg), runner=TaskRunner()
        )
        assert res.executed is True
        assert res.critique.verdict == VERDICT_CONCERNS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
