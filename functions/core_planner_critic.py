"""Інтеграція `PlanCritic` (Phase 11.5) з legacy `core_planner.Planner`.

`core_planner.Planner.create_plan()` повертає **список словників** у форматі:

    [
        {"action": "create_file", "args": {"path": "a.txt", "content": "hi"},
         "goal": "створити файл", "validation": "файл існує"},
        ...
    ]

А `PlanCritic.review()` очікує `Plan` / `Task`-и з `logic_task_runner`
(новий формат з `id`/`kind`/`params`/`depends_on`).

Цей модуль — **чистий bridge + helper-и** без залежності від конкретного
провайдера / мережі. Його задача:

1. Конвертувати legacy-список-словників у `Plan` (`legacy_plan_to_plan`).
2. Дати зручний one-liner для критики (`review_legacy_plan`).
3. Дати повний цикл з replan (`review_and_replan_legacy`): критик → якщо
   `blocking` і є `replan_fn` → переписати план → критик ще раз.
4. Дати factory (`make_planner_replan_fn`), який будує `ReplanFn` на основі
   існуючого `Planner.create_plan()` — у такий спосіб можна одразу
   підключити PlanCritic у legacy-потік без змін у `Planner`.

Модуль **не чіпає** `Planner` (зберігаємо backward-compat) і **не виконує**
план — це лише передвиконавчий шар. Виконання залишається за `core_executor`.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from functions.logic_plan_critic import CritiqueResult, PlanCritic, SEVERITY_BLOCK
from functions.logic_task_runner import ON_ERROR_STOP, Plan, Task


# ---------------------------------------------------------------------------
# Legacy → Plan conversion
# ---------------------------------------------------------------------------


def legacy_step_to_task(step: Mapping[str, Any], idx: int) -> Task:
    """Перетворити один запис legacy-плану на `Task`.

    Правила:
        - `step["action"]` → `Task.kind` (fallback `"step_{idx}"`).
        - `step["args"]` → `Task.params` (deep-copied dict).
        - `step.get("goal")` → `Task.name` (або `kind`, якщо порожнє).
        - Зберігаємо допоміжні поля (`goal`, `validation`) у
          `Task.params["_legacy"]`, щоб критик міг на них дивитись.
    """
    action = str(step.get("action", "")).strip()
    kind = action or f"step_{idx}"
    args_raw = step.get("args") or {}
    params: Dict[str, Any] = (
        copy.deepcopy(dict(args_raw)) if isinstance(args_raw, Mapping) else {}
    )

    goal = str(step.get("goal") or "").strip()
    validation = str(step.get("validation") or "").strip()
    name = goal or kind

    legacy_meta: Dict[str, Any] = {}
    if goal:
        legacy_meta["goal"] = goal
    if validation:
        legacy_meta["validation"] = validation
    if legacy_meta:
        params.setdefault("_legacy", legacy_meta)

    return Task(
        id=f"step_{idx + 1}",
        kind=kind,
        name=name,
        params=params,
        on_error=ON_ERROR_STOP,
        depends_on=[],
    )


def legacy_plan_to_plan(
    legacy: Sequence[Mapping[str, Any]],
    *,
    name: str = "legacy_plan",
    metadata: Optional[Mapping[str, Any]] = None,
) -> Plan:
    """Конвертує `List[Dict]` з `Planner.create_plan()` у `Plan`."""
    tasks = [legacy_step_to_task(step, i) for i, step in enumerate(legacy or [])]
    return Plan(name=name, tasks=tasks, metadata=dict(metadata or {}))


# ---------------------------------------------------------------------------
# Review helpers
# ---------------------------------------------------------------------------


#: Функція перепланування: `(legacy_plan, critique) -> new_legacy_plan | None`.
#: Якщо повертає `None` — цикл завершується з `blocking`-вердиктом.
ReplanFn = Callable[
    [List[Dict[str, Any]], CritiqueResult], Optional[List[Dict[str, Any]]]
]


@dataclass
class LegacyCritiqueResult:
    """Результат `review_and_replan_legacy()` — фінальний план і критика."""

    plan: List[Dict[str, Any]] = field(default_factory=list)
    critique: CritiqueResult = field(default_factory=CritiqueResult)
    approved: bool = False
    attempts: int = 0
    stop_reason: str = ""

    @property
    def blocking(self) -> bool:
        return not self.approved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan": list(self.plan),
            "critique": self.critique.to_dict(),
            "approved": self.approved,
            "attempts": self.attempts,
            "stop_reason": self.stop_reason,
        }


def review_legacy_plan(
    legacy: Sequence[Mapping[str, Any]],
    *,
    critic: PlanCritic,
    task_description: str = "",
    policies: Optional[Mapping[str, Any]] = None,
    plan_name: str = "legacy_plan",
) -> CritiqueResult:
    """One-shot критика legacy-плану.

    Просто конвертує план → `Plan` → викликає `critic.review()`.
    Не робить replan; повертає `CritiqueResult` як є.
    """
    plan_obj = legacy_plan_to_plan(legacy, name=plan_name)
    return critic.review(
        plan_obj,
        context=task_description,
        policies=dict(policies) if policies else None,
    )


def review_and_replan_legacy(
    legacy: Sequence[Mapping[str, Any]],
    *,
    critic: PlanCritic,
    task_description: str = "",
    policies: Optional[Mapping[str, Any]] = None,
    replan_fn: Optional[ReplanFn] = None,
    max_redos: int = 1,
    plan_name: str = "legacy_plan",
) -> LegacyCritiqueResult:
    """Повний цикл: критика → (опційно replan) → критика → до `max_redos`.

    Args:
        legacy: Початковий план у legacy-форматі.
        critic: Сконфігурований `PlanCritic`.
        task_description: Контекст-рядок для критика (що юзер просив).
        policies: Мета-інформація для критика (tool_policies, project_root).
        replan_fn: Якщо `blocking`-вердикт — викликаємо цю функцію для нового плану.
        max_redos: Скільки разів дозволено перечитувати (1 = ще одна спроба).
        plan_name: Назва для серіалізованого плану у промпті критика.

    Returns:
        `LegacyCritiqueResult` з фінальним планом, останньою критикою,
        прапором `approved` та кількістю спроб.
    """
    current: List[Dict[str, Any]] = [dict(s) for s in (legacy or [])]
    attempts = 0
    last: CritiqueResult = CritiqueResult()

    while True:
        attempts += 1
        last = review_legacy_plan(
            current,
            critic=critic,
            task_description=task_description,
            policies=policies,
            plan_name=plan_name,
        )

        if not last.blocking:
            return LegacyCritiqueResult(
                plan=current,
                critique=last,
                approved=True,
                attempts=attempts,
            )

        if attempts > max_redos or replan_fn is None:
            return LegacyCritiqueResult(
                plan=current,
                critique=last,
                approved=False,
                attempts=attempts,
                stop_reason=(
                    f"critic blocked plan; verdict={last.verdict}, "
                    f"concerns={len(last.concerns)}, "
                    f"replan_fn={'none' if replan_fn is None else 'exhausted'}"
                ),
            )

        replanned = replan_fn(current, last)
        if replanned is None:
            return LegacyCritiqueResult(
                plan=current,
                critique=last,
                approved=False,
                attempts=attempts,
                stop_reason="replan_fn returned None",
            )
        current = [dict(s) for s in replanned]


# ---------------------------------------------------------------------------
# Replan factory — обгортає Planner.create_plan() як ReplanFn
# ---------------------------------------------------------------------------


def _format_concerns_for_prompt(critique: CritiqueResult) -> str:
    """Готує текстовий блок зауважень критика для інʼєкції у новий промпт."""
    lines: List[str] = []
    if critique.summary:
        lines.append(f"КРИТИК СКАЗАВ: {critique.summary}")
    for c in critique.concerns:
        prefix = {
            SEVERITY_BLOCK: "BLOCK",
            "warn": "WARN",
            "info": "INFO",
        }.get(c.severity, c.severity.upper())
        suffix = f" (порада: {c.suggestion})" if c.suggestion else ""
        task_ref = f" [{c.task_id}]" if c.task_id else ""
        lines.append(f"- {prefix}{task_ref}: {c.message}{suffix}")
    return "\n".join(lines)


def make_planner_replan_fn(
    planner: Any,
    task_description: str,
    *,
    context: Optional[Mapping[str, Any]] = None,
) -> ReplanFn:
    """Factory: повертає `ReplanFn`, яка викликає `planner.create_plan()` з
    інʼєкцією зауважень критика у формулювання задачі.

    Використовує public API `Planner.create_plan(task, context=None)` і
    нічого не чіпає у самому планері.
    """

    def _replan(
        _plan: List[Dict[str, Any]], critique: CritiqueResult
    ) -> Optional[List[Dict[str, Any]]]:
        concerns_block = _format_concerns_for_prompt(critique)
        extended_task = (
            f"{task_description}\n\n"
            f"УВАГА: Попередній план забракований критиком. Врахуй зауваження "
            f"та створи новий, безпечніший план.\n{concerns_block}"
        )
        try:
            new_plan = planner.create_plan(
                extended_task, context=dict(context) if context else None
            )
        except Exception:
            return None
        if not isinstance(new_plan, list):
            return None
        return new_plan

    return _replan


__all__ = [
    "LegacyCritiqueResult",
    "ReplanFn",
    "legacy_plan_to_plan",
    "legacy_step_to_task",
    "make_planner_replan_fn",
    "review_and_replan_legacy",
    "review_legacy_plan",
]
