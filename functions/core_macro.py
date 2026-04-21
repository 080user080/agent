"""Macro — запис і відтворення послідовностей дій (Phase 7 фундамент).

Фокус на мінімальному MVP:
- `MacroStep` / `Macro` — data-layer, без залежностей від Windows.
- `MacroRecorder` — record/play API, що працює через ін'єкцію callable-а
  `executor` (сигнатура: `executor(action: str, params: dict) -> dict`).
  Це дозволяє юніт-тестувати без реальних `aaa_*`/`tools_*` викликів.
- `MacroStore` — JSON-персистенція у `macros_dir/*.json`.

Інтеграція з `core_action_recorder` (Phase 6) очікується на наступному кроці:
recorder уже збирає `{action, params}` — ми просто читаємо його буфер.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MacroStep:
    """Один крок макросу.

    Attributes:
        action: Назва функції в TOOL_POLICIES (наприклад `mouse_click`).
        params: Параметри (як передавались би в executor).
        delay_before: Затримка перед кроком, сек (для швидкості/стабільності).
        on_fail: Стратегія при помилці: `abort` | `skip` | `retry`.
        max_retries: Скільки разів повторити при `on_fail='retry'`.
    """

    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    delay_before: float = 0.0
    on_fail: str = "abort"
    max_retries: int = 0
    comment: str = ""


@dataclass
class Macro:
    """Макрос — іменована послідовність кроків."""

    name: str
    description: str = ""
    steps: List[MacroStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Macro":
        steps = [MacroStep(**s) for s in data.get("steps", [])]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            steps=steps,
            variables=dict(data.get("variables", {})),
            created_at=data.get("created_at", time.time()),
        )


@dataclass
class MacroRunResult:
    """Результат відтворення макросу."""

    success: bool
    steps_completed: int
    steps_total: int
    errors: List[str] = field(default_factory=list)
    step_results: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class MacroStore:
    """JSON-сховище макросів (один файл = один макрос)."""

    def __init__(self, macros_dir: str | Path = "macros"):
        self.macros_dir = Path(macros_dir)
        self.macros_dir.mkdir(parents=True, exist_ok=True)

    def save(self, macro: Macro) -> Path:
        path = self.macros_dir / f"{macro.name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(macro.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load(self, name: str) -> Optional[Macro]:
        path = self.macros_dir / f"{name}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Macro.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            print(f"[MacroStore] Cannot load {path}: {exc}")
            return None

    def list_names(self) -> List[str]:
        return sorted(p.stem for p in self.macros_dir.glob("*.json"))

    def delete(self, name: str) -> bool:
        path = self.macros_dir / f"{name}.json"
        if not path.exists():
            return False
        path.unlink()
        return True


# ---------------------------------------------------------------------------
# Recorder / Player
# ---------------------------------------------------------------------------


class MacroRecorder:
    """Запис та відтворення макросів.

    Запис — це явний виклик `record_step()` з місця, де агент виконує
    інструмент. Паралельно можна скористатися буфером `core_action_recorder`,
    але прямий API дозволяє контрольовано формувати послідовності у тестах.
    """

    def __init__(self, store: Optional[MacroStore] = None):
        self.store = store or MacroStore()
        self._recording: Optional[Macro] = None
        self._pause = False

    # ----- Recording ------------------------------------------------------

    def start(self, name: str, description: str = "") -> Macro:
        """Почати запис нового макросу."""
        if self._recording is not None:
            raise RuntimeError(
                f"Macro '{self._recording.name}' is already being recorded"
            )
        self._recording = Macro(name=name, description=description)
        self._pause = False
        return self._recording

    def pause(self) -> None:
        if self._recording is None:
            raise RuntimeError("No macro is being recorded")
        self._pause = True

    def resume(self) -> None:
        if self._recording is None:
            raise RuntimeError("No macro is being recorded")
        self._pause = False

    def record_step(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        delay_before: float = 0.0,
        on_fail: str = "abort",
        max_retries: int = 0,
        comment: str = "",
    ) -> None:
        """Додати крок у поточний запис (ігнорується, якщо pause)."""
        if self._recording is None:
            raise RuntimeError("Call start() before recording steps")
        if self._pause:
            return
        self._recording.steps.append(
            MacroStep(
                action=action,
                params=dict(params or {}),
                delay_before=delay_before,
                on_fail=on_fail,
                max_retries=max_retries,
                comment=comment,
            )
        )

    def stop(self, *, save: bool = True) -> Macro:
        """Завершити запис; за замовч. зберегти на диск."""
        if self._recording is None:
            raise RuntimeError("No macro is being recorded")
        macro = self._recording
        self._recording = None
        self._pause = False
        if save:
            self.store.save(macro)
        return macro

    @property
    def is_recording(self) -> bool:
        return self._recording is not None

    # ----- Playback -------------------------------------------------------

    def play(
        self,
        macro: Macro | str,
        executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        variables: Optional[Dict[str, Any]] = None,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> MacroRunResult:
        """Відтворити макрос через callable `executor`.

        `executor(action, params) -> {"success": bool, ...}`.
        Не робить жодних GUI-викликів самостійно — все через executor.
        """
        if isinstance(macro, str):
            loaded = self.store.load(macro)
            if loaded is None:
                return MacroRunResult(
                    success=False,
                    steps_completed=0,
                    steps_total=0,
                    errors=[f"Macro '{macro}' not found"],
                )
            macro = loaded

        merged_vars = {**macro.variables, **(variables or {})}
        result = MacroRunResult(success=True, steps_completed=0, steps_total=len(macro.steps))

        for index, step in enumerate(macro.steps):
            if step.delay_before > 0:
                sleep_fn(step.delay_before)

            params = _substitute_vars(step.params, merged_vars)
            attempt = 0
            last_error: Optional[str] = None

            while True:
                attempt += 1
                try:
                    step_result = executor(step.action, params) or {}
                except Exception as exc:  # noqa: BLE001
                    step_result = {"success": False, "error": str(exc)}

                if step_result.get("success", False):
                    result.step_results.append(step_result)
                    result.steps_completed += 1
                    break

                last_error = step_result.get("error", "unknown")
                if step.on_fail == "retry" and attempt <= step.max_retries:
                    continue

                # abort / skip
                result.step_results.append(step_result)
                result.errors.append(
                    f"step {index} ({step.action}): {last_error}"
                )
                if step.on_fail == "skip":
                    break
                # abort
                result.success = False
                return result

        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _substitute_vars(params: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Підставляє `{{var}}` у str-значеннях params."""
    if not variables:
        return dict(params)

    def _subst(value: Any) -> Any:
        if isinstance(value, str):
            for key, val in variables.items():
                value = value.replace("{{" + key + "}}", str(val))
            return value
        if isinstance(value, list):
            return [_subst(v) for v in value]
        if isinstance(value, dict):
            return {k: _subst(v) for k, v in value.items()}
        return value

    return {k: _subst(v) for k, v in params.items()}
