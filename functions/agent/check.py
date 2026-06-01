"""Check — фаза перевірки та валідації результатів AgentLoop.

Phase 12.1 / Крок 2.4. Виділення логіки верифікації успішності кроку:
- Оцінка виконаних очікувань (expectations) через ExpectRegistry
- Взаємодія з LoopDetector для виявлення зациклень
- Оновлення лічильників послідовних помилок
- Створення точок відновлення стану (Checkpoints)

Відокремлено від AgentLoop.check() для модульності.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("check")

# ─── Набір дій, що не змінюють екран фізично ──────────────────────────────────

NON_VISUAL_ACTIONS: set = {
    "take_screenshot", "ocr_screen", "find_text_on_screen",
    "find_button_by_text", "find_input_field", "describe_screen",
    "find_element_by_description", "is_screen_correct",
    "wait_seconds", "done", "ask_user", "noop",
    "uia_get_value", "uia_list_buttons", "uia_list_inputs",
    "browser_extract_text", "browser_screenshot",
}

# ─── Типи даних ────────────────────────────────────────────────────────────────


@dataclass
class CheckConfig:
    """Конфігурація фази перевірки."""
    enable_checkpoint: bool = True
    """Чи зберігати чекпоїнти."""
    checkpoint_interval_steps: int = 5
    """Інтервал між чекпоїнтами (в кроках)."""
    screen_diff_threshold: float = 0.01
    """Поріг зміни скріншоту (не використовується в поточній реалізації)."""


@dataclass
class CheckResult:
    """Результат перевірки кроку."""
    success: bool = False
    screen_changed: bool = False
    retry: bool = False
    detail: str = ""
    expectation_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CheckState:
    """Мутований стан фази перевірки між ітераціями.

    Зберігає:
    - prev_screen_hash / prev_screen_path для порівняння скріншотів
    - Кеш ExpectRegistry для уникнення повторної ініціалізації
    """
    prev_screen_hash: str = ""
    prev_screen_path: str = ""
    _expect_registry: Optional[Any] = None  # ExpectRegistry (lazy init)


# ─── Перевірка очікувань ──────────────────────────────────────────────────────


def run_expectations(
    expectations: List[Dict[str, Any]],
    obs: Any,
    act_result: Dict[str, Any],
    task_id: str = "default_task",
    registry_cache: Optional[CheckState] = None,
) -> List[Dict[str, Any]]:
    """Виконати список ExpectSpec через ExpectRegistry.

    Args:
        expectations: Список {"kind": "...", "params": {...}}
        obs: Observation — поточний стан (для ocr_text, screenshot_path, тощо)
        act_result: Результат виконання дії
        task_id: Ідентифікатор задачі
        registry_cache: CheckState для кешування ExpectRegistry

    Returns:
        Список {"kind": str, "ok": bool, "reason": str}
    """
    out: List[Dict[str, Any]] = []
    try:
        from functions.planning.logic_expectations import (
            ExpectSpec, ExpectContext, ExpectRegistry,
        )

        # Лінива ініціалізація ExpectRegistry через кеш стану
        registry: Optional[ExpectRegistry] = None
        if registry_cache is not None:
            if registry_cache._expect_registry is None:
                registry_cache._expect_registry = ExpectRegistry()
            registry = registry_cache._expect_registry
        else:
            registry = ExpectRegistry()

        ctx = ExpectContext(
            task_id=task_id,
            handler_result=dict(act_result or {}),
            extras={"observation": {
                "ocr_text": getattr(obs, "ocr_text", ""),
                "active_window_title": getattr(obs, "active_window_title", ""),
                "screenshot_path": getattr(obs, "screenshot_path", ""),
            }},
        )
        for e in expectations:
            if not isinstance(e, dict):
                continue
            spec = ExpectSpec(
                kind=str(e.get("kind", "")),
                params=dict(e.get("params") or {}),
            )
            if not spec.kind:
                continue
            try:
                res = registry.evaluate(spec, ctx)
                out.append({
                    "kind": res.kind,
                    "ok": res.ok,
                    "reason": res.reason,
                })
            except Exception as exc:  # noqa: BLE001
                out.append({
                    "kind": spec.kind,
                    "ok": False,
                    "reason": f"evaluator error: {exc}",
                })
    except Exception as exc:  # noqa: BLE001
        logger.debug("ExpectRegistry unavailable: %s", exc)
    return out


# ─── Основний check() ─────────────────────────────────────────────────────────


def check(
    action: str,
    obs: Any,
    state: CheckState,
    act_result: Optional[Dict[str, Any]] = None,
    expectations: Optional[List[Dict[str, Any]]] = None,
    task_id: str = "default_task",
) -> CheckResult:
    """Перевірити чи дія спрацювала.

    Перевірки (по черзі):
    1. Якщо act_result явно повернув ok=False — fail.
    2. Якщо передані expectations — перевірити через ExpectRegistry.
    3. Інакше — порівняти screen_hash зі попереднім.

    Args:
        action: Назва виконаної дії
        obs: Поточне спостереження (Observation)
        state: Мутований стан чекера (оновлює screen_hash/path)
        act_result: Результат виконання дії (опційно)
        expectations: Список ExpectSpec для перевірки (опційно)
        task_id: Ідентифікатор задачі

    Returns:
        CheckResult з результатами перевірки
    """
    result = CheckResult()

    # 1) act_result безпосередній провал
    if act_result is not None:
        ok_flag = act_result.get("ok") if isinstance(act_result, dict) else None
        if ok_flag is False:
            result.success = False
            result.retry = True
            result.detail = (
                f"Дія повернула ok=False: {act_result.get('error', '')[:120]}"
            )
            state.prev_screen_hash = getattr(obs, "screen_hash", "")
            state.prev_screen_path = getattr(obs, "screenshot_path", "")
            return result

    # 2) Expectations через ExpectRegistry
    if expectations:
        expect_results = run_expectations(
            expectations, obs, act_result or {},
            task_id=task_id,
            registry_cache=state,
        )
        result.expectation_results = expect_results
        failed = [r for r in expect_results if not r.get("ok", False)]
        if failed:
            result.success = False
            result.retry = True
            result.detail = (
                "Не пройшли перевірки: "
                + ", ".join(f"{r.get('kind')}({r.get('reason')})" for r in failed[:3])
            )
            state.prev_screen_hash = getattr(obs, "screen_hash", "")
            state.prev_screen_path = getattr(obs, "screenshot_path", "")
            return result

    # 3) Порівняння screen_hash (базовий fallback)
    obs_screen_hash = getattr(obs, "screen_hash", "") or ""
    obs_screen_path = getattr(obs, "screenshot_path", "") or ""

    if state.prev_screen_hash and obs_screen_hash:
        if state.prev_screen_hash != obs_screen_hash:
            result.screen_changed = True
            result.success = True
            result.detail = "Скріншот змінився"
        else:
            result.screen_changed = False
            # Не-візуальні дії не падають при незмінному екрані
            if action in NON_VISUAL_ACTIONS:
                result.success = True
                result.detail = "Дія не змінює екран — OK"
            else:
                result.success = False
                result.retry = True
                result.detail = "Скріншот не змінився — можливо дія не спрацювала"
    else:
        result.success = True
        result.detail = "Перша ітерація / немає базового скріншоту"

    # Оновлюємо стан для наступної ітерації
    state.prev_screen_hash = obs_screen_hash
    state.prev_screen_path = obs_screen_path
    return result


# ─── Checkpoints ──────────────────────────────────────────────────────────────


def save_checkpoint(
    state: CheckState,
    agent_state: Any,
    task_id: str,
    task_description: str = "",
    total_steps: int = 0,
    config: Optional[Dict[str, Any]] = None,
    enabled: bool = True,
) -> None:
    """Зберегти чекпоїнт виконання.

    Args:
        state: Поточний стан чекера (prev_screen_hash/path)
        agent_state: AgentState — стан агента (step, actions_history)
        task_id: Ідентифікатор задачі
        task_description: Опис задачі
        total_steps: Загальна кількість кроків
        config: Конфігурація для метаданих чекпоїнта
        enabled: Чи ввімкнено чекпоїнти

    Збої при записі не призводять до аварійного завершення.
    """
    if not enabled:
        return

    try:
        from functions.runtime.core_checkpoint import CheckpointData, get_checkpoint_manager

        manager = get_checkpoint_manager()
        checkpoint = CheckpointData(
            task_id=task_id,
            task_description=task_description,
            current_step=agent_state.step,
            total_steps=total_steps,
            state={
                "prev_screen_hash": state.prev_screen_hash,
                "prev_screen_path": state.prev_screen_path,
                "actions_history": agent_state.actions_history,
            },
            metadata={"config": dict(config or {})},
        )
        manager.save(checkpoint)
        logger.debug("Checkpoint saved at step %d", agent_state.step)
    except Exception as e:
        logger.warning("Failed to save checkpoint: %s", e)


def load_checkpoint(
    task_id: str,
    enabled: bool = True,
) -> Optional[Dict[str, Any]]:
    """Завантажити чекпоїнт.

    Args:
        task_id: Ідентифікатор задачі
        enabled: Чи ввімкнено чекпоїнти

    Returns:
        Dict з станом чекпоїнта або None
    """
    if not enabled:
        return None

    try:
        from functions.runtime.core_checkpoint import get_checkpoint_manager

        manager = get_checkpoint_manager()
        checkpoint = manager.load(task_id)

        if checkpoint:
            logger.info(
                "Checkpoint loaded: step %d/%d",
                checkpoint.current_step,
                checkpoint.total_steps,
            )
            return {
                "current_step": checkpoint.current_step,
                "total_steps": checkpoint.total_steps,
                "prev_screen_hash": checkpoint.state.get("prev_screen_hash", ""),
                "prev_screen_path": checkpoint.state.get("prev_screen_path", ""),
                "actions_history": checkpoint.state.get("actions_history", []),
            }
    except Exception as e:
        logger.warning("Failed to load checkpoint: %s", e)

    return None


def cleanup_checkpoint(task_id: str, enabled: bool = True) -> None:
    """Видалити чекпоїнт після завершення."""
    if not enabled:
        return

    try:
        from functions.runtime.core_checkpoint import get_checkpoint_manager

        manager = get_checkpoint_manager()
        manager.delete(task_id)
        logger.info("Checkpoint deleted after completion")
    except Exception as e:
        logger.warning("Failed to delete checkpoint: %s", e)


__all__ = [
    "CheckConfig",
    "CheckResult",
    "CheckState",
    "NON_VISUAL_ACTIONS",
    "check",
    "run_expectations",
    "save_checkpoint",
    "load_checkpoint",
    "cleanup_checkpoint",
]