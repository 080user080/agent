"""pipeline_self_coding — Self-coding pipeline для Phase 13 S7.

Перетворює `TaskSpec` з контексту self-coding у виконуваний `Plan`
з handler-ів `TaskRunner`. Pipeline реалізує послідовність:

    build_self_context → analyze_gap → confirm_action →
    save_snapshot → generate_patch → verify_edit → (rollback)

Де:
- `build_self_context`  — збирає контекст проєкту (repo map, relevant files)
- `analyze_gap`         — через LLM визначає що треба змінити/додати
- `confirm_action`      — опційне підтвердження користувача (PermissionGate)
- `save_snapshot`       — snapshot через UndoManager перед записом
- `generate_patch`      — генерація та запис патчу для файлу
- `verify_edit`         — верифікація зміни (синтаксис + LLM)
- `rollback`            — автоматичний відкат якщо verify не пройшов

Всі кроки з `kind="self_*"` реєструються в TaskRunner як handler-и
(аналогічно тому як `run_command` / `write_file` handler-и вже існують).

Контракти pipeline-а: див. `functions.core_plan_compiler.Pipeline`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from functions.planning.core_task_intake import TaskSpec
from functions.planning.logic_expectations import (
    EXPECT_NO_ERROR_IN_REPORT,
    ExpectSpec,
)
from functions.planning.logic_task_runner import ON_ERROR_SKIP, ON_ERROR_STOP, Plan, Task

logger = logging.getLogger("pipeline_self_coding")


# ---------------------------------------------------------------------------
# SelfCodingPipeline
# ---------------------------------------------------------------------------


@dataclass
class SelfCodingPipeline:
    """Pipeline для self-coding (Phase 13 S7 / Pipeline 4.1).

    Будує Plan з кроків:
        1. build_self_context
        2. analyze_gap
        3. confirm_action (опційно — залежить від `confirm_each`)
        4. save_snapshot
        5. generate_patch
        6. verify_edit
        7. rollback (conditional — якщо verify не пройшов)

    Config-прапори:
    - `use_llm`       — використовувати LLM для gap-аналізу та генерації патчів.
                        Якщо False — тільки заглушки (для тестування/дебагу).
    - `confirm_each`  — запитувати підтвердження користувача перед кожним записом.
                        True за замовчуванням (безпека).
    - `llm_callback`  — функція ``(messages) -> str`` для виклику LLM.
                        Якщо None — handler-и використовують системний LLM.
    """

    name: str = "self_coding"
    use_llm: bool = True
    confirm_each: bool = True
    allow_snapshot_skip: bool = True
    """Якщо True — snapshot не є критичним (on_error=ON_ERROR_SKIP).
    Якщо False — pipeline зупиниться якщо snapshot не вдалося зробити."""

    def compile(self, spec: TaskSpec) -> Plan:
        """Скомпілювати Plan для self-coding pipeline.

        Args:
            spec: TaskSpec з описом задачі (goal, deliverables, constraints).

        Returns:
            Plan з послідовністю Task-ів.
        """
        tasks: List[Task] = []
        goal = spec.goal
        task_id = spec.task_id

        # ------------------------------------------------------------------
        # 1) build_self_context
        # ------------------------------------------------------------------
        tasks.append(Task(
            id="t1_build_context",
            kind="self_context_build",
            name=f"Build self-context: {goal[:120]}",
            params={
                "task": goal,
                "task_id": task_id,
                "use_llm": self.use_llm,
            },
            expect=[ExpectSpec(kind=EXPECT_NO_ERROR_IN_REPORT)],
            on_error=ON_ERROR_STOP,
        ))

        # ------------------------------------------------------------------
        # 2) analyze_gap
        # ------------------------------------------------------------------
        tasks.append(Task(
            id="t2_analyze_gap",
            kind="self_analyze_gap",
            name=f"Analyze gap: {goal[:120]}",
            params={
                "task": goal,
                "task_id": task_id,
                "use_llm": self.use_llm,
            },
            depends_on=["t1_build_context"],
            expect=[ExpectSpec(kind=EXPECT_NO_ERROR_IN_REPORT)],
            on_error=ON_ERROR_STOP,
        ))

        # ------------------------------------------------------------------
        # 3) confirm_action (опційно)
        # ------------------------------------------------------------------
        if self.confirm_each:
            tasks.append(Task(
                id="t3_confirm_action",
                kind="confirm_action",
                name=f"Confirm self-edit: {goal[:120]}",
                params={
                    "task": goal,
                    "task_id": task_id,
                    "files_source_task_id": "t2_analyze_gap",
                    "prompt": (
                        f"Self-Coding Pipeline визначив файли для зміни за ТЗ:\n"
                        f"«{goal}»\n\n"
                        f"Дозволити запис змін?"
                    ),
                },
                depends_on=["t2_analyze_gap"],
                on_error=ON_ERROR_STOP,
            ))

        # ------------------------------------------------------------------
        # 4) save_snapshot
        # ------------------------------------------------------------------
        snapshot_deps = (
            ["t3_confirm_action"]
            if self.confirm_each
            else ["t2_analyze_gap"]
        )
        tasks.append(Task(
            id="t4_save_snapshot",
            kind="save_snapshot",
            name="Save snapshot before self-edit",
            params={
                "task_id": task_id,
                "reason": f"self_coding_pipeline: {goal[:100]}",
            },
            depends_on=snapshot_deps,
            on_error=ON_ERROR_SKIP if self.allow_snapshot_skip else ON_ERROR_STOP,
        ))

        # ------------------------------------------------------------------
        # 5) generate_patch
        # ------------------------------------------------------------------
        tasks.append(Task(
            id="t5_generate_patch",
            kind="self_generate_patch",
            name=f"Generate & apply patch: {goal[:120]}",
            params={
                "task": goal,
                "task_id": task_id,
                "use_llm": self.use_llm,
                "files_source_task_id": "t2_analyze_gap",
                "snapshot_task_id": "t4_save_snapshot",
            },
            depends_on=["t4_save_snapshot"],
            expect=[ExpectSpec(kind=EXPECT_NO_ERROR_IN_REPORT)],
            on_error=ON_ERROR_STOP,
        ))

        # ------------------------------------------------------------------
        # 6) verify_edit
        # ------------------------------------------------------------------
        tasks.append(Task(
            id="t6_verify_edit",
            kind="self_verify_edit",
            name=f"Verify edit: {goal[:120]}",
            params={
                "task": goal,
                "task_id": task_id,
                "use_llm": self.use_llm,
                "patch_task_id": "t5_generate_patch",
            },
            depends_on=["t5_generate_patch"],
            expect=[ExpectSpec(kind=EXPECT_NO_ERROR_IN_REPORT)],
            on_error=ON_ERROR_SKIP,
        ))

        # ------------------------------------------------------------------
        # 7) rollback (conditional — додається завжди, handler вирішує
        #    чи потрібен відкат на основі результату t6)
        # ------------------------------------------------------------------
        tasks.append(Task(
            id="t7_rollback",
            kind="self_rollback",
            name="Rollback if verification failed",
            params={
                "task": goal,
                "task_id": task_id,
                "verify_task_id": "t6_verify_edit",
                "snapshot_task_id": "t4_save_snapshot",
            },
            depends_on=["t6_verify_edit"],
            on_error=ON_ERROR_SKIP,
        ))

        # ------------------------------------------------------------------
        # Metadata
        # ------------------------------------------------------------------
        metadata: Dict[str, Any] = {
            "pipeline": self.name,
            "domain": spec.domain,
            "domain_sub": spec.domain_sub,
            "task_id": task_id,
            "goal": goal,
            "deliverables": list(spec.deliverables),
            "constraints": list(spec.constraints),
            "use_llm": self.use_llm,
            "confirm_each": self.confirm_each,
            "allow_snapshot_skip": self.allow_snapshot_skip,
            "step_count": len(tasks),
            "pipeline_note": (
                "Self-coding pipeline Phase 4.1: self-context → gap analysis → "
                "confirm → snapshot → patch → verify → rollback. "
                "Handler-и (self_*) реєструються в TaskRunner окремо."
            ),
        }

        return Plan(
            name=f"self-coding plan: {goal[:200]}",
            tasks=tasks,
            metadata=metadata,
        )

    def required_tools(self, spec: TaskSpec) -> List[str]:
        """Повернути список необхідних tool kind-ів."""
        tools: List[str] = [
            "self_context_build",
            "self_analyze_gap",
            "save_snapshot",
            "self_generate_patch",
            "self_verify_edit",
            "self_rollback",
        ]
        if self.confirm_each:
            tools.append("confirm_action")
        return tools


__all__ = [
    "SelfCodingPipeline",
]