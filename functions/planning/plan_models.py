"""Pydantic v2 моделі для планових структур.

Валідація:
- рядкові поля не можуть бути порожніми (min_length=1)
- числові поля (індекси, пріоритети) >= 0
- enum поля — тільки допустимі значення з оригінального коду
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    # Заглушки для CI/Linux без pydantic
    class BaseModel:  # type: ignore[no-redef]
        """Заглушка BaseModel для оточень без pydantic."""
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def Field(*args, **kwargs):  # type: ignore[no-redef]
        return kwargs.get("default")

    def field_validator(*args, **kwargs):  # type: ignore[no-redef]
        def decorator(func):
            return func
        return decorator

logger = logging.getLogger("plan_models")

# ---------------------------------------------------------------------------
# Enum екваivalentи з оригінального коду
# ---------------------------------------------------------------------------


class DomainEnum(str, Enum):
    """DomainEnum — еквівалент Domain з task_spec.py."""

    CODE = "code"
    PHOTO = "photo"
    PRESENTATION = "presentation"
    WEB = "web"
    DESKTOP = "desktop"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class PriorityEnum(str, Enum):
    """PriorityEnum — еквівалент Priority з task_spec.py."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# TaskSpec / CompiledPlan (task_spec.py)
# ---------------------------------------------------------------------------


class TaskSpecPydantic(BaseModel):
    """Pydantic-еквівалент TaskSpec."""

    description: str = Field(min_length=1)
    domain: DomainEnum = DomainEnum.UNKNOWN
    priority: PriorityEnum = PriorityEnum.MEDIUM
    deliverables: List[str] = Field(default_factory=list)
    max_duration_seconds: float = 3600.0
    max_budget_tokens: int = 100000
    files_to_modify: List[str] = Field(default_factory=list)
    tools_allowed: List[str] = Field(default_factory=list)
    tools_forbidden: List[str] = Field(default_factory=list)
    milestones: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: float = 0.0

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("description must not be empty")
        return v.strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "domain": self.domain.value,
            "priority": self.priority.value,
            "deliverables": self.deliverables,
            "max_duration_seconds": self.max_duration_seconds,
            "max_budget_tokens": self.max_budget_tokens,
            "files_to_modify": self.files_to_modify,
            "tools_allowed": self.tools_allowed,
            "tools_forbidden": self.tools_forbidden,
            "milestones": self.milestones,
            "tags": self.tags,
        }


class CompiledPlanPydantic(BaseModel):
    """Pydantic-еквівалент CompiledPlan."""

    task_spec: TaskSpecPydantic
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    milestones: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_duration_seconds: float = 0.0
    estimated_tokens: int = 0
    validation_rules: List[str] = Field(default_factory=list)

    @field_validator("estimated_duration_seconds")
    @classmethod
    def duration_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("estimated_duration_seconds must be >= 0")
        return v

    @field_validator("estimated_tokens")
    @classmethod
    def tokens_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("estimated_tokens must be >= 0")
        return v

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_spec": self.task_spec.to_dict(),
            "steps": self.steps,
            "milestones": self.milestones,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "estimated_tokens": self.estimated_tokens,
            "validation_rules": self.validation_rules,
        }


# ---------------------------------------------------------------------------
# Task / Plan / TaskContext / RunResult (logic_task_runner.py)
# ---------------------------------------------------------------------------


class TaskPydantic(BaseModel):
    """Pydantic-еквівалент Task."""

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    on_error: str = "stop"
    max_retries: int = 2
    retry_delay_s: float = 1.0
    depends_on: List[str] = Field(default_factory=list)
    precheck: List[Any] = Field(default_factory=list)
    expect: List[Any] = Field(default_factory=list)

    @field_validator("id", "kind")
    @classmethod
    def id_kind_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("id and kind must not be empty")
        return v.strip()

    @field_validator("max_retries")
    @classmethod
    def max_retries_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("max_retries must be >= 0")
        return v

    @field_validator("retry_delay_s")
    @classmethod
    def retry_delay_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("retry_delay_s must be >= 0")
        return v


class PlanPydantic(BaseModel):
    """Pydantic-еквівалент Plan."""

    name: str = Field(min_length=1)
    tasks: List[TaskPydantic] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("plan name must not be empty")
        return v.strip()


class TaskContextPydantic(BaseModel):
    """Pydantic-еквівалент TaskContext."""

    task: TaskPydantic
    runner: Any = None
    report: Any = None
    gate: Any = None
    previous_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class RunResultPydantic(BaseModel):
    """Pydantic-еквівалент RunResult."""

    report: Any = None
    all_ok: bool = False
    stopped_early: bool = False
    stop_reason: str = ""


# ---------------------------------------------------------------------------
# ExpectSpec / ExpectationResult / ExpectContext (logic_expectations.py)
# ---------------------------------------------------------------------------


class ExpectSpecPydantic(BaseModel):
    """Pydantic-еквівалент ExpectSpec."""

    kind: str = Field(min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def kind_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("kind must not be empty")
        return v.strip()


class ExpectationResultPydantic(BaseModel):
    """Pydantic-еквівалент ExpectationResult."""

    kind: str = Field(min_length=1)
    ok: bool = False
    reason: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def kind_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("kind must not be empty")
        return v.strip()


class ExpectContextPydantic(BaseModel):
    """Pydantic-еквівалент ExpectContext."""

    task_id: str = ""
    task_kind: str = ""
    handler_result: Dict[str, Any] = Field(default_factory=dict)
    report_totals: Dict[str, Any] = Field(default_factory=dict)
    previous_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    cwd: Optional[str] = None
    extras: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# StepReport / ExecutionReport (logic_execution_report.py)
# ---------------------------------------------------------------------------


class StepReportPydantic(BaseModel):
    """Pydantic-еквівалент StepReport."""

    task_id: str = Field(min_length=1)
    task_name: str = ""
    kind: str = Field(min_length=1)
    status: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_s: float = 0.0
    summary: str = ""
    stdout_tail: str = ""
    error: str = ""
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_id", "kind", "status")
    @classmethod
    def required_fields_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("required fields must not be empty")
        return v.strip()

    @field_validator("duration_s", "cost_usd")
    @classmethod
    def non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("field must be >= 0")
        return v

    @field_validator("prompt_tokens", "completion_tokens")
    @classmethod
    def tokens_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("tokens must be >= 0")
        return v


class ExecutionReportEventPydantic(BaseModel):
    """Pydantic-еквівалент ExecutionReportEvent."""

    time: float = 0.0
    summary: str = ""


class ReportFooterPydantic(BaseModel):
    """Pydantic-еквівалент ReportFooter."""

    total_steps: int = 0
    total_ok: int = 0
    total_failed: int = 0
    total_time: float = 0.0


class ReportSummaryPydantic(BaseModel):
    """Pydantic-еквівалент ReportSummary."""

    plan_name: str = ""
    status: str = "ok"
    duration_seconds: float = 0.0
    total_steps: int = 0
    ok_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    total_cost_usd: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_estimated_cost_usd: float = 0.0
    total_estimated_prompt_tokens: int = 0
    total_estimated_completion_tokens: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# PlanExecutor (plan_executor.py)
# ---------------------------------------------------------------------------


class PlanExecutionConfigPydantic(BaseModel):
    """Pydantic-еквівалент PlanExecutionConfig."""

    plan_name: str = Field(min_length=1)
    dry_run: bool = False
    max_steps: int = 100
    max_retries: int = 3
    on_error: str = "stop"
    max_duration_seconds: float = 3600.0
    track_cost: bool = True
    track_tokens: bool = True


class PlanExecutionStatePydantic(BaseModel):
    """Pydantic-еквівалент PlanExecutionState."""

    plan_name: str = ""
    current_step: int = 0
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    current_step_name: str = ""
    last_error: str = ""
    total_cost_usd: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    started_at: float = 0.0
    ended_at: float = 0.0


# ---------------------------------------------------------------------------
# PlanCritic / CritiqueResult (logic_plan_critic.py)
# ---------------------------------------------------------------------------


class ConcernPydantic(BaseModel):
    """Pydantic-еквівалент Concern."""

    concern_type: str = ""
    severity: int = 0
    description: str = ""
    impact: str = ""
    suggestion: str = ""


class CritiqueResultPydantic(BaseModel):
    """Pydantic-еквівалент CritiqueResult."""

    is_valid: bool = False
    concerns: List[ConcernPydantic] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# TaskPattern (logic_task_learner.py)
# ---------------------------------------------------------------------------


class TaskPatternPydantic(BaseModel):
    """Pydantic-еквівалент TaskPattern."""

    pattern_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    expected_duration: float = 0.0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    typical_steps: List[str] = Field(default_factory=list)
    typical_params: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RepairLoop (logic_repair_loop.py)
# ---------------------------------------------------------------------------


class RepairProposalPydantic(BaseModel):
    """Pydantic-еквівалент RepairProposal."""

    failed_task_id: str = ""
    failed_step_index: int = 0
    repair_action: str = ""
    new_params: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class RepairDecisionPydantic(BaseModel):
    """Pydantic-еквівалент RepairDecision."""

    repair_needed: bool = False
    repair_action: str = ""
    modified_args: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CorePlanner (core_planner.py)
# ---------------------------------------------------------------------------


class LegacyCritiqueResultPydantic(BaseModel):
    """Pydantic-еквівалент LegacyCritiqueResult."""

    success: bool = False
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LegacyRunResultPydantic(BaseModel):
    """Pydantic-еквівалент LegacyRunResult."""

    success: bool = False
    report: Any = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# SkeletonPipeline (core_plan_compiler.py)
# ---------------------------------------------------------------------------


class SkeletonPipelinePydantic(BaseModel):
    """Pydantic-еквівалент SkeletonPipeline."""

    name: str = Field(min_length=1)
    steps: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AgentState / AgentLoopConfig (agent_loop.py)
# ---------------------------------------------------------------------------


class AgentStatePydantic(BaseModel):
    """Pydantic-еквівалент AgentState."""

    status: str = "idle"
    current_plan: Optional["PlanPydantic"] = None
    current_step: int = 0
    total_steps: int = 0
    last_result: Optional["ActorResultPydantic"] = None
    error: str = ""


class AgentLoopConfigPydantic(BaseModel):
    """Pydantic-еквівалент AgentLoopConfig."""

    auto_save_checkpoints: bool = True
    max_steps: int = 100
    max_retries: int = 3
    checkpoint_interval: int = 5
    state_file: str = "agent_state.json"
    log_level: str = "INFO"


# ---------------------------------------------------------------------------
# ActorResult (ai_actors.py)
# ---------------------------------------------------------------------------


class ProviderEnum(str, Enum):
    """ProviderEnum — еквівалент Provider з ai_actors.py."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    CUSTOM = "custom"


class ActorResultPydantic(BaseModel):
    """Pydantic-еквівалент ActorResult."""

    provider: ProviderEnum = ProviderEnum.OPENAI
    success: bool = False
    response: Optional[str] = None
    error: str = ""
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CodePipeline (pipeline_code.py)
# ---------------------------------------------------------------------------


class CodePipelinePydantic(BaseModel):
    """Pydantic-еквівалент CodePipeline."""

    name: str = Field(min_length=1)
    description: str = ""
    source_code: str = ""
    test_code: str = ""
    lint_command: str = ""
    test_command: str = ""
    build_command: str = ""
    requirements: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# ScreenContext (logic_context_analyzer.py)
# ---------------------------------------------------------------------------


class ScreenElementTypeEnum(str, Enum):
    """ScreenElementTypeEnum — еквівалент ScreenElementType з logic_context_analyzer.py."""

    BUTTON = "button"
    TEXT = "text"
    INPUT = "input"
    CHECKBOX = "checkbox"
    COMBOBOX = "combobox"
    TREE_ITEM = "tree_item"
    WINDOW = "window"
    CUSTOM = "custom"


class ScreenElementPydantic(BaseModel):
    """Pydantic-еквівалент ScreenElement."""

    element_type: ScreenElementTypeEnum = ScreenElementTypeEnum.CUSTOM
    text: str = ""
    coordinates: Dict[str, int] = Field(default_factory=dict)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    parent_id: Optional[str] = None
    children: List[str] = Field(default_factory=list)


class ScreenContextPydantic(BaseModel):
    """Pydantic-еквівалент ScreenContext."""

    elements: List[ScreenElementPydantic] = Field(default_factory=list)
    blockers: List["BlockerInfoPydantic"] = Field(default_factory=list)


class BlockerInfoPydantic(BaseModel):
    """Pydantic-еквівалент BlockerInfo."""

    blocker_type: str = ""
    description: str = ""
    affected_elements: List[str] = Field(default_factory=list)
    severity: int = 0


# ---------------------------------------------------------------------------
# TaskSpec (core_task_intake.py) — NOTE: different from task_spec.py TaskSpec
# ---------------------------------------------------------------------------


class BudgetHintsPydantic(BaseModel):
    """Pydantic-еквівалент BudgetHints."""

    max_duration: float = 0.0
    max_tokens: int = 0
    max_cost_usd: float = 0.0
    max_steps: int = 0


class ClarificationPydantic(BaseModel):
    """Pydantic-еквівалент Clarification."""

    question: str = ""
    options: List[str] = Field(default_factory=list)
    default_answer: int = 0


class IntakeResultPydantic(BaseModel):
    """Pydantic-еквівалент IntakeResult."""

    clarification: Optional[ClarificationPydantic] = None
    task_spec: Optional["TaskSpecPydantic"] = None
    plan: Optional["CompiledPlanPydantic"] = None


__all__ = [
    # Enum еквіваленти
    "DomainEnum",
    "PriorityEnum",
    "ProviderEnum",
    "ScreenElementTypeEnum",
    # TaskSpec / CompiledPlan
    "TaskSpecPydantic",
    "CompiledPlanPydantic",
    # TaskRunner
    "TaskPydantic",
    "PlanPydantic",
    "TaskContextPydantic",
    "RunResultPydantic",
    # Expectations
    "ExpectSpecPydantic",
    "ExpectationResultPydantic",
    "ExpectContextPydantic",
    # ExecutionReport
    "StepReportPydantic",
    "ExecutionReportEventPydantic",
    "ReportFooterPydantic",
    "ReportSummaryPydantic",
    # PlanExecutor
    "PlanExecutionConfigPydantic",
    "PlanExecutionStatePydantic",
    # PlanCritic
    "ConcernPydantic",
    "CritiqueResultPydantic",
    # TaskLearner
    "TaskPatternPydantic",
    # RepairLoop
    "RepairProposalPydantic",
    "RepairDecisionPydantic",
    # CorePlanner
    "LegacyCritiqueResultPydantic",
    "LegacyRunResultPydantic",
    # CorePlanCompiler
    "SkeletonPipelinePydantic",
    # AgentLoop
    "AgentStatePydantic",
    "AgentLoopConfigPydantic",
    # AiActors
    "ActorResultPydantic",
    # CodePipeline
    "CodePipelinePydantic",
    # ContextAnalyzer
    "ScreenElementPydantic",
    "ScreenContextPydantic",
    "BlockerInfoPydantic",
    # CoreTaskIntake
    "BudgetHintsPydantic",
    "ClarificationPydantic",
    "IntakeResultPydantic",
]
