"""core_plan_compiler — Phase 13.2/13.4 skeleton.

Перетворює `TaskSpec` у `Plan` через pipeline-реєстр. У S6 тут є лише
skeleton-пайплайн, який повертає placeholder-Plan (один `log_task_spec`
Task) — це доводить наскрізний шлях `ТЗ → TaskSpec → Plan`. Реальні
pipeline-и (`code_pipeline`, `photo_batch_pipeline`, ...) приходять у
S7–S11 і реєструються у тому самому `PipelineRegistry`.

Контракти:
- `Pipeline` — Protocol: `.name`, `.compile(spec) -> Plan`,
  `.required_tools(spec) -> list[str]`.
- `PipelineRegistry` — реєструє pipeline-и по ключу (`domain`).
- `compile_plan_from_spec(spec, registry=None)` — обирає pipeline за
  `spec.domain`, fallback на `mixed` для невідомих доменів.

У S6 всі домени мапляться на `SkeletonPipeline`, бо реальних pipeline-ів
ще нема. Це дає робочий наскрізний потік і чіткий TODO-маркер у плані
(`placeholder_step=True`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .core_task_intake import (
    ALLOWED_DOMAINS,
    DOMAIN_CODE,
    DOMAIN_MIXED,
    DOMAIN_PHOTO_BATCH,
    DOMAIN_PRESENTATION,
    DOMAIN_UNKNOWN,
    DOMAIN_WEB_RESEARCH,
    TaskSpec,
)
from .logic_task_runner import Plan, Task


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Pipeline(Protocol):
    """Контракт pipeline-а: знає як скомпілювати Plan для одного домену."""

    name: str

    def compile(self, spec: TaskSpec) -> Plan: ...

    def required_tools(self, spec: TaskSpec) -> List[str]: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class PipelineRegistryError(RuntimeError):
    """Помилки реєстру (дубль ключа тощо)."""


class PipelineRegistry:
    """Реєстр pipeline-ів за доменом.

    Ключі — значення з `ALLOWED_DOMAINS` (див. `core_task_intake`). Якщо
    у реєстрі нема pipeline-а для конкретного домену — `resolve()` бере
    pipeline для `DOMAIN_MIXED` як fallback. Якщо й того нема — падає.
    """

    def __init__(self) -> None:
        self._pipelines: Dict[str, Pipeline] = {}

    def register(self, domain: str, pipeline: Pipeline, *, overwrite: bool = False) -> None:
        if domain not in ALLOWED_DOMAINS:
            raise PipelineRegistryError(
                f"Unknown domain {domain!r}; allowed={ALLOWED_DOMAINS}"
            )
        if not overwrite and domain in self._pipelines:
            raise PipelineRegistryError(f"domain {domain!r} already registered")
        self._pipelines[domain] = pipeline

    def unregister(self, domain: str) -> None:
        self._pipelines.pop(domain, None)

    def get(self, domain: str) -> Optional[Pipeline]:
        return self._pipelines.get(domain)

    def resolve(self, domain: str) -> Pipeline:
        """Повернути pipeline для домену з fallback на mixed/unknown."""
        if domain in self._pipelines:
            return self._pipelines[domain]
        if DOMAIN_MIXED in self._pipelines:
            return self._pipelines[DOMAIN_MIXED]
        if DOMAIN_UNKNOWN in self._pipelines:
            return self._pipelines[DOMAIN_UNKNOWN]
        raise PipelineRegistryError(
            f"no pipeline for domain={domain!r} and no mixed/unknown fallback"
        )

    def list_domains(self) -> List[str]:
        return sorted(self._pipelines.keys())


# ---------------------------------------------------------------------------
# Skeleton pipeline
# ---------------------------------------------------------------------------


@dataclass
class SkeletonPipeline:
    """Placeholder pipeline — повертає Plan з одним `log_task_spec` Task-ом.

    Використовується поки реальний pipeline для цього домену не написано
    (S6 MVP). Plan позначений `metadata.placeholder=True` + у Task-і
    `params.placeholder_step=True`, щоб подальша перевірка/ревью могли
    легко відрізнити.
    """

    name: str = "skeleton"

    def compile(self, spec: TaskSpec) -> Plan:
        task = Task(
            id="t1",
            kind="log_task_spec",
            name=f"[skeleton] {spec.goal}"[:200],
            params={
                "placeholder_step": True,
                "spec_task_id": spec.task_id,
                "spec_domain": spec.domain,
                "spec_domain_sub": spec.domain_sub,
                "spec_goal": spec.goal,
                "spec_deliverables": list(spec.deliverables),
                "spec_constraints": list(spec.constraints),
                "spec_preferred_ai_order": list(spec.preferred_ai_order),
                "spec_permission_mode": spec.permission_mode,
                "spec_input_files": list(spec.input_files),
                "spec_output_dir": spec.output_dir,
            },
        )
        metadata: Dict[str, Any] = {
            "placeholder": True,
            "pipeline": self.name,
            "task_id": spec.task_id,
            "domain": spec.domain,
            "domain_sub": spec.domain_sub,
            "created_at": spec.created_at,
            "s6_note": (
                "Skeleton plan: Phase 13.1/13.4 MVP. Реальні pipeline-и "
                "(code/photo/presentation) прийдуть у S7-S11."
            ),
        }
        return Plan(
            name=f"Skeleton plan for: {spec.goal}"[:200],
            tasks=[task],
            metadata=metadata,
        )

    def required_tools(self, spec: TaskSpec) -> List[str]:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make_default_registry() -> PipelineRegistry:
    """Створити реєстр з pipeline-ами під усі відомі домени.

    Стан реєстру по спринтах:

    - S6 (PR #25) — всі домени мапились на `SkeletonPipeline`.
    - S7 (поточний) — `DOMAIN_CODE` переключений на реальний
      `CodePipeline` (pipeline_code). Решта — ще `SkeletonPipeline`.
    - S8-S11 — інші домени переключатимуться аналогічно без змін
      API (`DOMAIN_PHOTO_BATCH` → `PhotoBatchPipeline` тощо).
    """
    # Локальний імпорт щоб уникнути циклу `pipeline_code → ... → core_plan_compiler`.
    from .pipeline_code import CodePipeline

    registry = PipelineRegistry()
    skeleton = SkeletonPipeline(name="skeleton")
    registry.register(DOMAIN_CODE, CodePipeline())
    for domain in (
        DOMAIN_PHOTO_BATCH,
        DOMAIN_PRESENTATION,
        DOMAIN_WEB_RESEARCH,
        DOMAIN_MIXED,
        DOMAIN_UNKNOWN,
    ):
        registry.register(domain, skeleton)
    return registry


def compile_plan_from_spec(
    spec: TaskSpec,
    *,
    registry: Optional[PipelineRegistry] = None,
) -> Plan:
    """Обрати pipeline за `spec.domain` і повернути `Plan`.

    Якщо `registry=None` — створюється дефолтний (`make_default_registry`).
    """
    reg = registry if registry is not None else make_default_registry()
    pipeline = reg.resolve(spec.domain)
    plan = pipeline.compile(spec)
    plan.metadata.setdefault("pipeline", getattr(pipeline, "name", ""))
    plan.metadata.setdefault("task_id", spec.task_id)
    plan.metadata.setdefault("domain", spec.domain)
    return plan
