"""Сервіс самолікування планів (RepairLoop + StepRepairer).

Виділено з core_planner.py для ізоляції логіки відновлення після невдалих
кроків плану. Використовує ``PlannerPromptBuilder`` для формування промптів.

Структура керування стратегіями:
    RETRY  — повторити крок з модифікованими аргументами
    SKIP   — пропустити крок (якщо некритичний)
    REPLAN — перебудувати решту плану
    STOP   — зупинити виконання (фатальна помилка / вичерпано ліміти)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from .planner_prompt_builder import PlannerPromptBuilder

logger = logging.getLogger("planner_repair")

# ─── Константи лімітів ────────────────────────────────────────────────────────

MAX_REPAIR_ATTEMPTS = 3
"""Жорсткий ліміт на кількість repair-спроб, щоб уникнути нескінченних
викликів LLM у Windows-середовищі."""

MAX_REPLAN_ATTEMPTS = 2
"""Ліміт на кількість перепланувань решти плану."""


class RepairStats:
    """Лічильники спроб самолікування."""

    def __init__(self) -> None:
        self.repair_attempts = 0
        self.replan_attempts = 0

    @property
    def repair_exhausted(self) -> bool:
        """Чи вичерпано ліміт repair-спроб."""
        return self.repair_attempts >= MAX_REPAIR_ATTEMPTS

    @property
    def replan_exhausted(self) -> bool:
        """Чи вичерпано ліміт replan-спроб."""
        return self.replan_attempts >= MAX_REPLAN_ATTEMPTS

    @property
    def any_exhausted(self) -> bool:
        """Чи вичерпано хоча б один ліміт."""
        return self.repair_exhausted or self.replan_exhausted

    def increment_repair(self) -> None:
        self.repair_attempts += 1

    def increment_replan(self) -> None:
        self.replan_attempts += 1

    def reset(self) -> None:
        self.repair_attempts = 0
        self.replan_attempts = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "repair_attempts": self.repair_attempts,
            "replan_attempts": self.replan_attempts,
        }


class StepRepairer:
    """Аналізує невдалий крок плану та пропонує коригувальну дію.

    Працює на рівні ``Planner`` — приймає ``(task, failed_step, result, context)``
    та повертає один repair-крок або None (якщо треба abort/replan).

    Має жорсткий ліміт ``max_repairs`` (default 3) на кількість repair-спроб
    в одній сесії планування.
    """

    DEFAULT_MAX_REPAIRS = 3

    def __init__(
        self,
        ask_llm_fn,
        available_actions_fn,
        max_repairs: int = DEFAULT_MAX_REPAIRS,
    ):
        """
        Args:
            ask_llm_fn: callable(prompt: str) -> str — функція запиту до LLM
            available_actions_fn: callable() -> str — опис доступних дій
            max_repairs: максимальна кількість repair-спроб (default 3)
        """
        self._ask_llm = ask_llm_fn
        self._available_actions_fn = available_actions_fn
        self._max_repairs = max_repairs
        self._repairs_used = 0

    # ── Управління бюджетом ──────────────────────────────────────────────

    @property
    def repairs_remaining(self) -> int:
        return max(0, self._max_repairs - self._repairs_used)

    @property
    def is_available(self) -> bool:
        """Чи можна ще робити repair (бюджет + наявність LLM)."""
        if self._repairs_used >= self._max_repairs:
            return False
        if self._ask_llm is None:
            return False
        return True

    def reset(self) -> None:
        """Скинути лічильник (новий запуск AgentLoop)."""
        self._repairs_used = 0

    # ── Основний метод repair ─────────────────────────────────────────────

    def repair(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Спробувати отримати один repair-крок після невдалого виконання.

        Args:
            task: оригінальна задача
            failed_step: словник кроку що провалився
            result: текст помилки / результату
            context: поточний контекст виконання

        Returns:
            Dict з одним repair-кроком (з ``is_repair=True``),
            або None якщо repair неможливий (abort / вичерпано бюджет).
        """
        if not self.is_available:
            logger.warning(
                "StepRepairer: бюджет вичерпано (%s/%s) або немає LLM",
                self._repairs_used, self._max_repairs,
            )
            return None

        self._repairs_used += 1
        available_actions = self._available_actions_fn()
        artifacts = context.get("artifacts_summary", "Немає артефактів")

        prompt = PlannerPromptBuilder.build_repair_prompt(
            task=task,
            failed_step=failed_step,
            result=result,
            artifacts_summary=artifacts,
            available_actions=available_actions,
        )

        response = self._ask_llm(prompt)
        parsed = self._extract_single_step(response)
        if parsed is None:
            logger.info("StepRepairer: LLM повернув abort — repair неможливий")
            return None

        parsed["is_repair"] = True
        logger.info(
            "StepRepairer: repair крок #%s → %s | args=%s",
            self._repairs_used, parsed.get("action", "?"), parsed.get("args", {}),
        )
        return parsed

    def _extract_single_step(self, response: str) -> Optional[Dict[str, Any]]:
        """Витягнути один JSON-об'єкт з відповіді LLM."""
        try:
            # Спроба звичайного парсингу
            data = json.loads(response.strip())
        except json.JSONDecodeError:
            # Спроба через extract_json
            from .planner_validator import PlannerValidator
            result = PlannerValidator.extract_json(response)
            data = result.data if result else None

        if not isinstance(data, dict):
            return None

        action = str(data.get("action", "")).strip()
        args = data.get("args", {})
        if not action or not isinstance(args, dict):
            return None
        if action == "abort":
            return None

        return {
            "action": action,
            "args": args,
            "goal": str(data.get("goal", "")).strip(),
            "validation": str(data.get("validation", "")).strip(),
        }


class RepairLoop:
    """Цикл самолікування плану з жорсткими лімітами.

    Координує послідовність repair → replan → stop на основі стратегій,
    запропонованих ``StepRepairer``.

    Використовується ``Planner`` для:
    1. Спроба repair через ``StepRepairer`` (з лімітом MAX_REPAIR_ATTEMPTS)
    2. Якщо repair не допоміг — replan через ``propose_replan`` (з лімітом MAX_REPLAN_ATTEMPTS)
    3. Якщо replan не допоміг — STOP
    """

    def __init__(
        self,
        repairer: StepRepairer,
        ask_llm_fn,
        available_actions_fn,
    ):
        """
        Args:
            repairer: екземпляр StepRepairer
            ask_llm_fn: callable(prompt: str) -> str — функція запиту до LLM
            available_actions_fn: callable() -> str — опис доступних дій
        """
        self._repairer = repairer
        self._ask_llm = ask_llm_fn
        self._available_actions_fn = available_actions_fn
        self._stats = RepairStats()

    @property
    def stats(self) -> RepairStats:
        return self._stats

    @property
    def repairer(self) -> StepRepairer:
        return self._repairer

    def reset_stats(self) -> None:
        """Скинути всі лічильники (новий запуск планування)."""
        self._stats.reset()
        self._repairer.reset()

    def try_repair(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Спроба repair: якщо ліміт не вичерпано — викликає StepRepairer.

        Returns:
            repair-крок або None.
        """
        if self._stats.repair_exhausted:
            logger.warning("RepairLoop: ліміт repair спроб вичерпано")
            return None

        self._stats.increment_repair()
        logger.info(
            "RepairLoop: repair спроба %s/%s",
            self._stats.repair_attempts, MAX_REPAIR_ATTEMPTS,
        )
        return self._repairer.repair(task, failed_step, result, context)

    def try_replan(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
        remaining_steps: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Спроба replan: перебудувати решту плану.

        Args:
            task: оригінальна задача
            failed_step: крок що провалився
            result: текст помилки
            context: поточний контекст
            remaining_steps: хвіст плану що залишився

        Returns:
            Новий список кроків (може бути [] якщо replan неможливий).
        """
        if self._stats.replan_exhausted:
            logger.warning("RepairLoop: ліміт replan спроб вичерпано")
            return []

        self._stats.increment_replan()
        available_actions = self._available_actions_fn()
        artifacts = context.get("artifacts_summary", "Немає артефактів")

        prompt = PlannerPromptBuilder.build_replan_prompt(
            task=task,
            failed_step=failed_step,
            result=result,
            artifacts_summary=artifacts,
            available_actions=available_actions,
            completed_steps=context.get("completed_steps", 0),
            repair_attempts=self._stats.repair_attempts,
            replan_attempts=self._stats.replan_attempts,
            remaining_steps=remaining_steps,
        )

        response = self._ask_llm(prompt)

        # Нормалізація плану через PlannerValidator
        from .planner_validator import PlannerValidator
        parsed = PlannerValidator.extract_json(response)
        plan = PlannerValidator.normalize_plan(parsed.data if parsed else None)

        logger.info(
            "RepairLoop: replan спроба %s/%s → %s кроків",
            self._stats.replan_attempts, MAX_REPLAN_ATTEMPTS, len(plan),
        )
        return plan

    def decide(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
        remaining_steps: List[Dict[str, Any]],
    ) -> Tuple[str, Optional[Any]]:
        """Повний цикл decision-making: repair → replan → stop.

        Returns:
            (strategy, payload) де strategy: "retry" | "replan" | "stop"
            - "retry": payload = repair-крок (Dict)
            - "replan": payload = новий план (List[Dict])
            - "stop": payload = причина зупинки (str)
        """
        # 1. Спроба repair
        repair_step = self.try_repair(task, failed_step, result, context)
        if repair_step is not None:
            return "retry", repair_step

        # 2. Якщо repair не допоміг — спроба replan
        new_plan = self.try_replan(task, failed_step, result, context, remaining_steps)
        if new_plan:
            return "replan", new_plan

        # 3. Нічого не допомогло — STOP
        reason = (
            f"Всі repair спроби ({self._stats.repair_attempts}) та "
            f"replan спроби ({self._stats.replan_attempts}) вичерпано."
        )
        logger.warning("RepairLoop: %s", reason)
        return "stop", reason