"""Task Learner — адаптивна автоматизація та виявлення патернів (Phase 7.3).

Функції:
- `detect_repeated_pattern` — шукає повторювані послідовності в історії дій.
- `suggest_automation` — генерує пропозицію створення макросу.
- `create_macro_from_pattern` — конвертує патерн у Macro.
- `adaptive_click` — перебирає fallback-селектори до першого успіху.
- `learn_from_scenario` — вивчення з успішних сценаріїв.
- `find_patterns` — виявлення повторюваних послідовностей.
- `auto_generate_macro` — автоматична генерація макросу.
- `update_profile_with_learned` — оновлення профілю з навченими патернами.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .core_macro import Macro, MacroStep
from .core_app_profile import AppProfile


@dataclass
class TaskPattern:
    """Виявлений повторюваний патерн дій."""

    name: str
    steps: List[Dict[str, Any]]
    frequency: int = 0
    last_seen: float = field(default_factory=time.time)


def detect_repeated_pattern(
    action_history: List[Dict[str, Any]],
    min_occurrences: int = 3,
    max_sequence_len: int = 10,
) -> Optional[TaskPattern]:
    """Шукає повторювані послідовності дій в історії.

    Args:
        action_history: Список дій у форматі `{action, params}`.
        min_occurrences: Мінімальна кількість повторень для визнання патерну.
        max_sequence_len: Максимальна довжина послідовності для пошуку.

    Returns:
        TaskPattern або None, якщо патерн не знайдено.
    """
    if len(action_history) < min_occurrences * 2:
        return None

    # Спростити історію до строк "action:param_key"
    simplified = []
    for act in action_history:
        key = act.get("action", "")
        # Додати ключі параметрів для кращого розрізнення
        params = act.get("params", {})
        if params:
            key += ":" + ",".join(sorted(params.keys()))
        simplified.append(key)

    n = len(simplified)
    best_pattern: Optional[TaskPattern] = None
    best_score = 0

    # Перебирати можливі довжини послідовностей (від 2 до max_sequence_len)
    for seq_len in range(2, min(max_sequence_len + 1, n // min_occurrences + 1)):
        # Перебирати стартові позиції
        for start in range(n - seq_len * min_occurrences + 1):
            seq = tuple(simplified[start : start + seq_len])
            count = 1
            idx = start + seq_len
            # Підрахувати повторення
            while idx + seq_len <= n:
                if tuple(simplified[idx : idx + seq_len]) == seq:
                    count += 1
                    idx += seq_len
                else:
                    idx += 1
            if count >= min_occurrences:
                score = count * seq_len
                if score > best_score:
                    best_score = score
                    steps = action_history[start : start + seq_len]
                    best_pattern = TaskPattern(
                        name=f"auto_pattern_{seq_len}x{count}_{int(time.time())}",
                        steps=[dict(s) for s in steps],
                        frequency=count,
                    )

    return best_pattern


def suggest_automation(pattern: TaskPattern) -> str:
    """Повертає текстову пропозицію створення макросу з патерну."""
    steps_summary = "\n".join(
        f"  {i+1}. {step.get('action', '?')} — {step.get('params', {})}"
        for i, step in enumerate(pattern.steps)
    )
    return (
        f"Виявлено повторюваний патерн '{pattern.name}' "
        f"({pattern.frequency} разів).\n"
        f"Кроки ({len(pattern.steps)}):\n{steps_summary}\n"
        f"Рекомендація: створити макрос для автоматизації."
    )


def create_macro_from_pattern(
    pattern: TaskPattern, name: str = "", description: str = ""
) -> Macro:
    """Конвертує TaskPattern у Macro."""
    macro_name = name or pattern.name
    macro_steps = [
        MacroStep(
            action=step.get("action", "unknown"),
            params=dict(step.get("params", {})),
            comment=f"auto from pattern {pattern.name}",
        )
        for step in pattern.steps
    ]
    return Macro(
        name=macro_name,
        description=description or f"Auto-generated from detected pattern (freq={pattern.frequency})",
        steps=macro_steps,
    )


def adaptive_click(
    description: str,
    fallback_list: List[Tuple[str, str]],
    selector_type: str = "description",
) -> Dict[str, Any]:
    """Перебирає fallback-селектори до першого успіху.

    Args:
        description: Опис елемента (для логування).
        fallback_list: Список кортежів (selector_type, selector_value).
            Наприклад [("image", "button_ok.png"), ("text", "OK")].
        selector_type: Тип селектора за замовчуванням (якщо fallback_list порожній).

    Returns:
        dict з `success`, `used_selector`, `selector_type`.
    """
    import importlib

    try:
        tools_wm = importlib.import_module(".tools.tools_window_manager", package=__package__)
        click_fn = getattr(tools_wm, "click_image_on_screen", None)
    except Exception:  # noqa: BLE001
        click_fn = None

    for sel_type, sel_value in fallback_list:
        try:
            if sel_type == "image" and click_fn:
                result = click_fn(sel_value)
                if result.get("success"):
                    return {
                        "success": True,
                        "used_selector": sel_value,
                        "selector_type": sel_type,
                        "description": description,
                    }
            elif sel_type == "text":
                # Placeholder for text-based click (future: pyautogui.click with OCR)
                continue
            elif sel_type == "coordinates":
                # Placeholder for coordinate-based click
                continue
        except Exception:
            continue

    return {
        "success": False,
        "error": f"Жоден fallback-селектор не спрацював для '{description}'",
        "attempted": len(fallback_list),
        "description": description,
    }


class ScenarioLearner:
    """Клас для навчання на сценаріях виконання."""

    def __init__(self):
        self.scenarios: List[Dict[str, Any]] = []
        self.patterns: List[TaskPattern] = []

    def learn_from_scenario(self, scenario: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Вивчення з успішного сценарію.

        Args:
            scenario: Сценарій виконання (план + результати)
            result: Результат виконання (success/failure)
        """
        if result.get("success"):
            self.scenarios.append({
                "scenario": scenario,
                "result": result,
                "timestamp": time.time()
            })

    def find_patterns(self, min_occurrences: int = 3) -> List[TaskPattern]:
        """Виявлення повторюваних послідовностей в історії сценаріїв.

        Args:
            min_occurrences: Мінімальна кількість повторень

        Returns:
            Список виявлених патернів
        """
        all_actions = []
        for sc in self.scenarios:
            plan = sc.get("scenario", {}).get("plan", [])
            for step in plan:
                all_actions.append({
                    "action": step.get("action", ""),
                    "params": step.get("args", {})
                })

        pattern = detect_repeated_pattern(all_actions, min_occurrences=min_occurrences)
        if pattern:
            self.patterns.append(pattern)
            return [pattern]
        return []

    def auto_generate_macro(self, pattern: TaskPattern, name: str = "") -> Optional[Macro]:
        """Автоматична генерація макросу з патерну.

        Args:
            pattern: Виявлений патерн
            name: Назва макросу (опційно)

        Returns:
            Macro або None якщо не вдалося створити
        """
        try:
            return create_macro_from_pattern(pattern, name=name)
        except Exception:
            return None

    def update_profile_with_learned(self, profile: AppProfile) -> AppProfile:
        """Оновлення профілю з навченими патернами.

        Args:
            profile: Профіль програми для оновлення

        Returns:
            Оновлений профіль
        """
        for pattern in self.patterns:
            # Додати патерн як common_action в профіль
            macro = self.auto_generate_macro(pattern)
            if macro:
                profile.common_actions[pattern.name] = {
                    "macro": macro.name,
                    "frequency": pattern.frequency,
                    "last_seen": pattern.last_seen
                }
        return profile
