"""Міст `core_planner` (legacy) ↔ `TaskRunner` (Phase 11).

**Задача:** дати можливість виконувати legacy-план (список словників
з `action`/`args`, який генерує `Planner.create_plan()`) через новий
`TaskRunner` — з усіма його перевагами:

    - `SessionBudget` kill-switch (time / tokens / cost / steps),
    - `PermissionGate` (whitelist / ask_fn) для небезпечних команд,
    - `Task.precheck` / `Task.expect` (Step-Check / Actor-Critic),
    - `ExecutionReport` зі структурованими `StepReport`-ами,
    - `retry` / `skip` / `stop` політика.

**Стратегія:** не переписуємо кожен `aaa_*` tool як окремий `HandlerFn`.
Натомість реєструємо **один generic-handler**, який диспетчеризує
`task.kind` → `FunctionRegistry.execute_function(action, params)` і мапить
результат у формат, який очікує `TaskRunner` (`{"status", "summary",
"data", ...}`).

Це дозволяє за **один виклик** `register_legacy_actions(runner, registry)`
зробити всі існуючі legacy-tools доступними в новому середовищі, зберігши
100% сумісність зі старим `core_executor`.

Весь модуль **чистий pure-Python**; не робить HTTP/файл-операцій; залежить
лише від `logic_task_runner` і duck-typed `FunctionRegistry`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set

from functions.core_planner_critic import (
    LegacyCritiqueResult,
    legacy_plan_to_plan,
    review_and_replan_legacy,
)
from functions.logic_plan_critic import CritiqueResult, PlanCritic
from functions.logic_task_runner import (
    HandlerFn,
    Plan,
    RunResult,
    STATUS_ERROR,
    STATUS_OK,
    TaskContext,
    TaskRunner,
)


#: Ім'я generic-кіnd-а, під яким реєструється диспетчер.
LEGACY_ACTION_KIND = "legacy_action"


# ---------------------------------------------------------------------------
# Generic handler
# ---------------------------------------------------------------------------


def _coerce_status(raw: Mapping[str, Any]) -> str:
    """Витягти `STATUS_OK` / `STATUS_ERROR` з raw-dict-у `last_tool_result`.

    Порядок:
      1. `raw["ok"]` (bool) — формат `make_tool_result` (core_tool_runtime).
      2. `raw["status"]` — якщо функція сама повертає legacy-статус.
      3. За відсутності сигналів — `STATUS_OK` (невдача була б у exception).
    """
    ok = raw.get("ok")
    if isinstance(ok, bool):
        return STATUS_OK if ok else STATUS_ERROR
    status = str(raw.get("status", "")).lower()
    if status in {"error", "fail", "failed", "blocked"}:
        return STATUS_ERROR
    return STATUS_OK


def _extract_tool_result(
    function_registry: Any, fallback_message: Any
) -> Dict[str, Any]:
    """Повернути нормалізований результат останнього виклику tool-а.

    `FunctionRegistry.execute_function()` повертає тільки рядок (`message`),
    а структуровану інформацію зберігає у `self.last_tool_result`. Ми читаємо
    саме її для достовірного `status` / `data` / `error`.
    """
    raw = getattr(function_registry, "last_tool_result", None)
    if isinstance(raw, Mapping):
        return {
            "ok": raw.get("ok"),
            "status": _coerce_status(raw),
            "message": str(raw.get("message", fallback_message)),
            "data": dict(raw.get("data") or {}),
            "error": raw.get("error"),
            "needs_confirmation": bool(raw.get("needs_confirmation", False)),
            "retryable": bool(raw.get("retryable", False)),
        }
    # Registry не оновив last_tool_result (мокнутий / щось сторонне).
    return {
        "ok": None,
        "status": STATUS_OK,
        "message": str(fallback_message),
        "data": {},
        "error": None,
        "needs_confirmation": False,
        "retryable": False,
    }


def make_legacy_action_handler(
    function_registry: Any,
    *,
    auto_create: bool = False,
    name_alias: Optional[Mapping[str, str]] = None,
) -> HandlerFn:
    """Фабрика generic-handler-а для TaskRunner, який диспетчеризує
    `task.kind` → `function_registry.execute_function(action, params)`.

    Args:
        function_registry: обʼєкт з методом `execute_function(action, params,
            auto_create=False)` та атрибутом `last_tool_result`.
        auto_create: чи дозволити Архітектору створювати відсутні функції
            під час виконання (за замовчанням False — для автономних сесій
            це небезпечно).
        name_alias: опційна мапа `{task.kind: real_action_name}` — якщо LLM
            використовує альтернативну назву.

    Returns:
        `HandlerFn`, який можна зареєструвати на TaskRunner-і.
    """
    alias = dict(name_alias or {})

    def _handler(ctx: TaskContext) -> Dict[str, Any]:
        action = alias.get(ctx.task.kind, ctx.task.kind)
        params_raw = ctx.task.params or {}

        # Видаляємо службові legacy-метадані (goal/validation), щоб не
        # плутати real-tool-и.
        params = {k: v for k, v in params_raw.items() if k != "_legacy"}

        try:
            message = function_registry.execute_function(
                action, params, auto_create=auto_create
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "status": STATUS_ERROR,
                "error": f"{type(exc).__name__}: {exc}",
                "summary": f"exception while executing '{action}'",
            }

        result = _extract_tool_result(function_registry, message)
        out: Dict[str, Any] = {
            "status": result["status"],
            "summary": result["message"],
            "data": result["data"],
        }
        if result["error"]:
            out["error"] = str(result["error"])
        if result["needs_confirmation"]:
            out["needs_confirmation"] = True
        if result["retryable"]:
            out["retryable"] = True
        return out

    return _handler


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_legacy_actions(
    runner: TaskRunner,
    function_registry: Any,
    *,
    kinds: Optional[Sequence[str]] = None,
    auto_create: bool = False,
    name_alias: Optional[Mapping[str, str]] = None,
    override: bool = False,
    include_generic: bool = True,
) -> List[str]:
    """Зареєструвати legacy-tools на TaskRunner як окремі `kind`-и.

    Args:
        runner: TaskRunner, де буде зареєстровано handler-и.
        function_registry: `FunctionRegistry` з `.functions: Dict[str, ...]`.
        kinds: Обмежити реєстрацію заданим переліком tool-назв. Якщо `None`
            — зареєструвати всі з `function_registry.functions`.
        auto_create: Прокидається у generic-handler (див. вище).
        name_alias: Передається у generic-handler.
        override: Чи перезаписувати handler, якщо `kind` уже зареєстровано.
        include_generic: Додатково зареєструвати `LEGACY_ACTION_KIND` —
            універсальний kind, який дозволяє LLM генерувати
            `{"kind": "legacy_action", "params": {"action": "...", ...}}`
            без потреби заздалегідь знати всі назви.

    Returns:
        Список `kind`-ів, які успішно зареєстровано в цьому виклику.
    """
    handler = make_legacy_action_handler(
        function_registry, auto_create=auto_create, name_alias=name_alias
    )

    registered: List[str] = []

    available: Set[str] = set()
    try:
        available = set((function_registry.functions or {}).keys())
    except AttributeError:
        available = set()

    target_kinds: Sequence[str]
    if kinds is None:
        target_kinds = sorted(available)
    else:
        target_kinds = list(kinds)

    for kind in target_kinds:
        if not override and kind in runner.handlers:
            continue
        runner.register(kind, handler)
        registered.append(kind)

    if include_generic:
        generic_handler = _make_generic_dispatch_handler(
            function_registry, auto_create=auto_create
        )
        if override or LEGACY_ACTION_KIND not in runner.handlers:
            runner.register(LEGACY_ACTION_KIND, generic_handler)
            registered.append(LEGACY_ACTION_KIND)

    return registered


def _make_generic_dispatch_handler(
    function_registry: Any, *, auto_create: bool
) -> HandlerFn:
    """Handler для `LEGACY_ACTION_KIND`: читає `params["action"]` і диспетчеризує.

    Відрізняється від `make_legacy_action_handler` лише тим, що назва tool-а
    береться не з `task.kind` (який фіксовано `legacy_action`), а з
    `task.params["action"]`, а решта params передається у сам tool.
    """

    def _handler(ctx: TaskContext) -> Dict[str, Any]:
        params_raw = ctx.task.params or {}
        action = str(params_raw.get("action", "")).strip()
        if not action:
            return {
                "status": STATUS_ERROR,
                "error": "missing 'action' in legacy_action params",
                "summary": "legacy_action dispatcher requires 'action' field",
            }

        tool_params = {
            k: v
            for k, v in params_raw.items()
            if k not in {"action", "_legacy"}
        }
        # Вкладений nested-formaт: {"action": "X", "args": {...}}
        nested_args = params_raw.get("args")
        if isinstance(nested_args, Mapping):
            tool_params = dict(nested_args)

        try:
            message = function_registry.execute_function(
                action, tool_params, auto_create=auto_create
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "status": STATUS_ERROR,
                "error": f"{type(exc).__name__}: {exc}",
                "summary": f"exception while executing '{action}'",
            }

        result = _extract_tool_result(function_registry, message)
        out: Dict[str, Any] = {
            "status": result["status"],
            "summary": result["message"],
            "data": result["data"],
            "action": action,
        }
        if result["error"]:
            out["error"] = str(result["error"])
        return out

    return _handler


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------


@dataclass
class LegacyRunResult:
    """Обʼєднаний результат: критика + виконання legacy-плану через TaskRunner."""

    plan: List[Dict[str, Any]] = field(default_factory=list)
    """Фінальний legacy-план (після replan, якщо був)."""

    critique: Optional[CritiqueResult] = None
    """Остання критика (None, якщо `critic` не передавався)."""

    run_result: Optional[RunResult] = None
    """Результат `TaskRunner.run()`; `None` якщо план заблоковано критиком."""

    approved: bool = True
    """True, якщо критик схвалив (або його не було) і можна було виконувати."""

    attempts: int = 1
    """Скільки критик-циклів використано."""

    stop_reason: str = ""
    """Текстовий маркер, чому зупинились (якщо approved=False)."""

    @property
    def executed(self) -> bool:
        return self.run_result is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan": list(self.plan),
            "critique": self.critique.to_dict() if self.critique else None,
            "approved": self.approved,
            "executed": self.executed,
            "attempts": self.attempts,
            "stop_reason": self.stop_reason,
            "run_result": (
                {
                    "all_ok": self.run_result.all_ok,
                    "steps": len(self.run_result.report.steps),
                    "stopped_early": self.run_result.stopped_early,
                    "stop_reason": self.run_result.stop_reason,
                }
                if self.run_result
                else None
            ),
        }


def run_legacy_plan_via_runner(
    legacy_plan: Sequence[Mapping[str, Any]],
    function_registry: Any,
    *,
    runner: Optional[TaskRunner] = None,
    critic: Optional[PlanCritic] = None,
    replan_fn: Optional[
        Callable[
            [List[Dict[str, Any]], CritiqueResult],
            Optional[List[Dict[str, Any]]],
        ]
    ] = None,
    task_description: str = "",
    policies: Optional[Mapping[str, Any]] = None,
    max_redos: int = 1,
    plan_name: str = "legacy_plan",
    metadata: Optional[Mapping[str, Any]] = None,
    auto_create_missing_tools: bool = False,
    include_generic_kind: bool = True,
    report: Any = None,
) -> LegacyRunResult:
    """Повний pipeline: (опц. критика) → конвертація → виконання через TaskRunner.

    Args:
        legacy_plan: Список словників з `Planner.create_plan()`.
        function_registry: `FunctionRegistry` з legacy-tools.
        runner: Якщо `None` — створюється новий порожній `TaskRunner`.
            Якщо передано — використовується як є, tools реєструються в ньому.
        critic: Опційний `PlanCritic`. Якщо задано — план проходить критику
            перед виконанням; якщо `blocking` — спроба replan.
        replan_fn: Функція перепланування (див. `core_planner_critic`).
        task_description: Передається критику як контекст.
        policies: Передається критику як policies.
        max_redos: Скільки разів дозволено перевиконати критика.
        plan_name: Імʼя для серіалізованого Plan-у.
        metadata: Метадані для Plan.
        auto_create_missing_tools: Прокидається у generic-handler.
        include_generic_kind: Реєструвати `LEGACY_ACTION_KIND` чи ні.
        report: `ExecutionReport`, куди пише runner (див. `logic_task_runner`).

    Returns:
        `LegacyRunResult`.
    """
    current_plan: List[Dict[str, Any]] = [dict(s) for s in (legacy_plan or [])]
    critique: Optional[CritiqueResult] = None
    attempts = 1

    # ── 1) Опційна критика + replan ────────────────────────────────────
    if critic is not None:
        legacy_result: LegacyCritiqueResult = review_and_replan_legacy(
            current_plan,
            critic=critic,
            task_description=task_description,
            policies=policies,
            replan_fn=replan_fn,
            max_redos=max_redos,
            plan_name=plan_name,
        )
        current_plan = legacy_result.plan
        critique = legacy_result.critique
        attempts = legacy_result.attempts

        if not legacy_result.approved:
            return LegacyRunResult(
                plan=current_plan,
                critique=critique,
                run_result=None,
                approved=False,
                attempts=attempts,
                stop_reason=legacy_result.stop_reason,
            )

    # ── 2) Конвертація legacy → Plan ──────────────────────────────────
    plan_obj: Plan = legacy_plan_to_plan(
        current_plan, name=plan_name, metadata=metadata
    )

    # ── 3) Виконання через TaskRunner ────────────────────────────────
    task_runner = runner if runner is not None else TaskRunner()
    register_legacy_actions(
        task_runner,
        function_registry,
        auto_create=auto_create_missing_tools,
        include_generic=include_generic_kind,
    )

    run_result = (
        task_runner.run(plan_obj, report=report)
        if report is not None
        else task_runner.run(plan_obj)
    )

    return LegacyRunResult(
        plan=current_plan,
        critique=critique,
        run_result=run_result,
        approved=True,
        attempts=attempts,
    )


__all__ = [
    "LEGACY_ACTION_KIND",
    "LegacyRunResult",
    "make_legacy_action_handler",
    "register_legacy_actions",
    "run_legacy_plan_via_runner",
]
