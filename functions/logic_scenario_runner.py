"""
Сценарії автоматизації UI.

GUI Automation Phase 5 — "готові сценарії" для типових задач.
Зберігання, завантаження та виконання JSON-сценаріїв автоматизації.
"""

import json
import time
import os
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

from .logic_ui_navigator import (
    UINavigator, UIAction, UIActionType, UIActionResult,
    click_element, type_in_field, select_option, check_checkbox,
    fill_form, submit_form, open_menu, click_menu_item,
    handle_dialog, dismiss_all_dialogs
)
from .tools_window_manager import (
    find_window_by_title, activate_window, get_active_window
)
from .tools_mouse_keyboard import keyboard_hotkey
from .tools_app_recognizer import detect_active_application, is_application_ready


class ScenarioStepType(Enum):
    """Типи кроків сценарію."""
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    CHECK = "check"
    HOTKEY = "hotkey"
    MENU = "menu"
    DIALOG = "dialog"
    WAIT = "wait"
    VERIFY = "verify"
    WINDOW = "window"
    CUSTOM = "custom"


@dataclass
class ScenarioStep:
    """Крок сценарію автоматизації."""
    step_type: str  # Тип кроку
    description: str  # Опис для логування
    params: Dict[str, Any] = field(default_factory=dict)
    verify: Optional[str] = None  # Текст для перевірки
    on_fail: str = "abort"  # "skip", "abort", "retry"
    max_retries: int = 1
    delay_before: float = 0.0  # Затримка перед кроком
    delay_after: float = 0.5  # Затримка після кроку


@dataclass
class Scenario:
    """Сценарій автоматизації."""
    name: str
    description: str
    steps: List[ScenarioStep]
    version: str = "1.0"
    author: str = ""
    created: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    timeout_per_step: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        """Конвертувати в словник."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "created": self.created,
            "variables": self.variables,
            "timeout_per_step": self.timeout_per_step,
            "steps": [
                {
                    "step_type": s.step_type,
                    "description": s.description,
                    "params": s.params,
                    "verify": s.verify,
                    "on_fail": s.on_fail,
                    "max_retries": s.max_retries,
                    "delay_before": s.delay_before,
                    "delay_after": s.delay_after
                }
                for s in self.steps
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scenario":
        """Створити з словника."""
        steps = [
            ScenarioStep(
                step_type=s["step_type"],
                description=s["description"],
                params=s.get("params", {}),
                verify=s.get("verify"),
                on_fail=s.get("on_fail", "abort"),
                max_retries=s.get("max_retries", 1),
                delay_before=s.get("delay_before", 0.0),
                delay_after=s.get("delay_after", 0.5)
            )
            for s in data.get("steps", [])
        ]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            steps=steps,
            version=data.get("version", "1.0"),
            author=data.get("author", ""),
            created=data.get("created", ""),
            variables=data.get("variables", {}),
            timeout_per_step=data.get("timeout_per_step", 30.0)
        )


@dataclass
class ScenarioResult:
    """Результат виконання сценарію."""
    success: bool
    scenario_name: str
    steps_completed: int
    steps_total: int
    duration: float
    error: Optional[str] = None
    failed_step: Optional[int] = None
    step_results: List[Dict[str, Any]] = field(default_factory=list)


class ScenarioRunner:
    """
    Виконавець сценаріїв автоматизації.
    Завантажує, валідує та виконує JSON-сценарії.
    """

    def __init__(self, scenarios_dir: str = "scenarios"):
        self.scenarios_dir = Path(scenarios_dir)
        self.scenarios_dir.mkdir(exist_ok=True)
        self.navigator = UINavigator()
        self._step_handlers: Dict[str, Callable] = {
            "click": self._handle_click,
            "type": self._handle_type,
            "select": self._handle_select,
            "check": self._handle_check,
            "hotkey": self._handle_hotkey,
            "menu": self._handle_menu,
            "dialog": self._handle_dialog,
            "wait": self._handle_wait,
            "verify": self._handle_verify,
            "window": self._handle_window,
            "custom": self._handle_custom
        }

    # ==================== УПРАВЛІННЯ СЦЕНАРІЯМИ ====================

    def save_scenario(self, scenario: Scenario, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Зберегти сценарій у файл.

        Args:
            scenario: Сценарій для збереження
            filename: Ім'я файлу (якщо None — використовується scenario.name)

        Returns:
            {"success": bool, "path": str}
        """
        try:
            if filename is None:
                filename = f"{scenario.name.lower().replace(' ', '_')}.json"

            path = self.scenarios_dir / filename

            with open(path, "w", encoding="utf-8") as f:
                json.dump(scenario.to_dict(), f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "path": str(path),
                "message": f"Сценарій '{scenario.name}' збережено"
            }

        except Exception as e:
            return {
                "success": False,
                "path": None,
                "message": f"Помилка збереження: {str(e)}",
                "error": str(e)
            }

    def load_scenario(self, filename: str) -> Dict[str, Any]:
        """
        Завантажити сценарій з файлу.

        Args:
            filename: Ім'я файлу

        Returns:
            {"success": bool, "scenario": Scenario, "message": str}
        """
        try:
            path = self.scenarios_dir / filename

            if not path.exists():
                return {
                    "success": False,
                    "scenario": None,
                    "message": f"Файл '{filename}' не знайдено"
                }

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            scenario = Scenario.from_dict(data)

            return {
                "success": True,
                "scenario": scenario,
                "message": f"Сценарій '{scenario.name}' завантажено"
            }

        except Exception as e:
            return {
                "success": False,
                "scenario": None,
                "message": f"Помилка завантаження: {str(e)}",
                "error": str(e)
            }

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """
        Отримати список доступних сценаріїв.

        Returns:
            [{"name": str, "description": str, "path": str}]
        """
        scenarios = []

        for path in self.scenarios_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                scenarios.append({
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                    "version": data.get("version", "1.0"),
                    "path": str(path),
                    "steps_count": len(data.get("steps", []))
                })
            except:
                continue

        return scenarios

    def delete_scenario(self, filename: str) -> Dict[str, Any]:
        """
        Видалити сценарій.

        Args:
            filename: Ім'я файлу

        Returns:
            {"success": bool, "message": str}
        """
        try:
            path = self.scenarios_dir / filename
            if path.exists():
                path.unlink()
                return {
                    "success": True,
                    "message": f"Сценарій '{filename}' видалено"
                }
            return {
                "success": False,
                "message": f"Сценарій '{filename}' не знайдено"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Помилка видалення: {str(e)}"
            }

    # ==================== ВИКОНАННЯ СЦЕНАРІЇВ ====================

    def run_scenario(
        self,
        scenario: Scenario,
        variables: Optional[Dict[str, Any]] = None
    ) -> ScenarioResult:
        """
        Виконати сценарій.

        Args:
            scenario: Сценарій для виконання
            variables: Змінні для підстановки (перекривають сценарійні)

        Returns:
            ScenarioResult
        """
        start_time = time.time()
        step_results = []

        # Об'єднаємо змінні
        merged_vars = {**scenario.variables, **(variables or {})}

        for i, step in enumerate(scenario.steps):
            step_start = time.time()

            # Затримка перед кроком
            if step.delay_before > 0:
                time.sleep(step.delay_before)

            # Підставимо змінні в параметри
            params = self._substitute_variables(step.params, merged_vars)

            # Виконаємо крок
            handler = self._step_handlers.get(step.step_type, self._handle_custom)

            retries = 0
            step_success = False
            step_error = None
            step_output = None

            while retries <= step.max_retries and not step_success:
                try:
                    step_output = handler(params)
                    step_success = step_output.get("success", False)

                    # Перевірка verify
                    if step_success and step.verify:
                        verify_result = self._verify_text(step.verify)
                        if not verify_result:
                            step_success = False
                            step_error = f"Перевірка не пройдена: '{step.verify}'"

                except Exception as e:
                    step_error = str(e)
                    step_success = False

                if not step_success:
                    retries += 1
                    if retries <= step.max_retries:
                        time.sleep(1)

            # Затримка після кроку
            if step.delay_after > 0:
                time.sleep(step.delay_after)

            step_duration = time.time() - step_start

            step_result = {
                "step_index": i,
                "step_type": step.step_type,
                "description": step.description,
                "success": step_success,
                "duration": step_duration,
                "retries": retries,
                "output": step_output,
                "error": step_error
            }
            step_results.append(step_result)

            # Обробка помилки
            if not step_success:
                if step.on_fail == "abort":
                    return ScenarioResult(
                        success=False,
                        scenario_name=scenario.name,
                        steps_completed=i,
                        steps_total=len(scenario.steps),
                        duration=time.time() - start_time,
                        error=step_error or f"Крок {i+1} не виконано",
                        failed_step=i,
                        step_results=step_results
                    )
                elif step.on_fail == "skip":
                    continue
                # "retry" вже оброблено в циклі

        return ScenarioResult(
            success=True,
            scenario_name=scenario.name,
            steps_completed=len(scenario.steps),
            steps_total=len(scenario.steps),
            duration=time.time() - start_time,
            step_results=step_results
        )

    def run_scenario_from_file(
        self,
        filename: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> ScenarioResult:
        """
        Завантажити та виконати сценарій з файлу.

        Args:
            filename: Ім'я файлу сценарію
            variables: Змінні для підстановки

        Returns:
            ScenarioResult
        """
        load_result = self.load_scenario(filename)

        if not load_result["success"]:
            return ScenarioResult(
                success=False,
                scenario_name=filename,
                steps_completed=0,
                steps_total=0,
                duration=0.0,
                error=load_result.get("message", "Не вдалося завантажити"),
                step_results=[]
            )

        return self.run_scenario(load_result["scenario"], variables)

    def validate_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        """
        Перевірити сценарій без виконання.

        Args:
            scenario: Сценарій для перевірки

        Returns:
            {"valid": bool, "warnings": [str], "errors": [str]}
        """
        warnings = []
        errors = []

        # Перевірка на порожні поля
        if not scenario.name:
            errors.append("Назва сценарію не може бути порожньою")

        if not scenario.steps:
            warnings.append("Сценарій не містить кроків")

        # Перевірка кроків
        valid_step_types = set(self._step_handlers.keys())

        for i, step in enumerate(scenario.steps):
            if step.step_type not in valid_step_types:
                errors.append(f"Крок {i+1}: невідомий тип '{step.step_type}'")

            if not step.description:
                warnings.append(f"Крок {i+1}: відсутній опис")

            # Перевірка параметрів для відомих типів
            if step.step_type == "click" and "description" not in step.params:
                warnings.append(f"Крок {i+1} (click): відсутній параметр 'description'")

            if step.step_type == "type" and ("field" not in step.params or "text" not in step.params):
                warnings.append(f"Крок {i+1} (type): відсутні параметри 'field' або 'text'")

        return {
            "valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors
        }

    # ==================== ОБРОБНИКИ КРОКІВ ====================

    def _handle_click(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник кліку."""
        return click_element(
            description=params["description"],
            element_type=params.get("element_type", "button")
        )

    def _handle_type(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник введення тексту."""
        return type_in_field(
            field_description=params["field"],
            text=params["text"],
            clear_first=params.get("clear_first", True)
        )

    def _handle_select(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник вибору з dropdown."""
        return select_option(
            dropdown_description=params["dropdown"],
            option_text=params["option"]
        )

    def _handle_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник чекбоксу."""
        return check_checkbox(
            label=params["label"],
            state=params.get("state", True)
        )

    def _handle_hotkey(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник гарячих клавіш."""
        try:
            keys = params["keys"]
            if isinstance(keys, str):
                keys = keys.split("+")
            keyboard_hotkey(*keys)
            return {
                "success": True,
                "message": f"Натиснуто {'+'.join(keys)}"
            }
        except Exception as e:
            return {"success": False, "message": str(e), "error": str(e)}

    def _handle_menu(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник меню."""
        path = params.get("path", [])
        if isinstance(path, str):
            path = [path]
        return click_menu_item(path)

    def _handle_dialog(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник діалогу."""
        return handle_dialog(
            expected_text=params.get("expected"),
            action=params.get("action", "ok")
        )

    def _handle_wait(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник очікування."""
        seconds = params.get("seconds", 1.0)
        time.sleep(seconds)
        return {
            "success": True,
            "message": f"Очікування {seconds}с"
        }

    def _handle_verify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник перевірки."""
        text = params.get("text", "")
        found = self._verify_text(text)
        return {
            "success": found,
            "message": f"Перевірка '{text}': {'знайдено' if found else 'не знайдено'}"
        }

    def _handle_window(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник вікна."""
        action = params.get("action", "activate")
        title = params.get("title", "")

        if action == "activate":
            hwnd = find_window_by_title(title)
            if hwnd:
                activate_window(hwnd)
                return {"success": True, "message": f"Активовано вікно '{title}'"}
            return {"success": False, "message": f"Вікно '{title}' не знайдено"}

        elif action == "wait_ready":
            timeout = params.get("timeout", 10)
            start = time.time()
            while time.time() - start < timeout:
                if is_application_ready(0):  # 0 = активне вікно
                    return {"success": True, "message": "Програма готова"}
                time.sleep(0.5)
            return {"success": False, "message": "Час очікування вичерпано"}

        return {"success": False, "message": f"Невідома дія: {action}"}

    def _handle_custom(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Обробник кастомних дій."""
        return {
            "success": False,
            "message": f"Кастомні дії не реалізовано: {params}"
        }

    # ==================== ДОПОМІЖНІ МЕТОДИ ====================

    def _substitute_variables(
        self,
        params: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Підставити змінні в параметри."""
        result = {}
        for key, value in params.items():
            if isinstance(value, str):
                # Підставимо {{variable_name}}
                for var_name, var_value in variables.items():
                    placeholder = f"{{{{{var_name}}}}}"
                    if placeholder in value:
                        value = value.replace(placeholder, str(var_value))
            result[key] = value
        return result

    def _verify_text(self, text: str) -> bool:
        """Перевірити наявність тексту на екрані."""
        from .tools_ocr import find_text_on_screen
        result = find_text_on_screen(text, case_sensitive=False)
        return result.get("found", False)


# ==================== ПУБЛІЧНИЙ API ====================

_runner = None


def get_runner(scenarios_dir: str = "scenarios") -> ScenarioRunner:
    """Отримати singleton екземпляр ScenarioRunner."""
    global _runner
    if _runner is None:
        _runner = ScenarioRunner(scenarios_dir)
    return _runner


# Зручні функції

def run_scenario(scenario: Scenario, variables: Optional[Dict[str, Any]] = None) -> ScenarioResult:
    """Виконати сценарій."""
    return get_runner().run_scenario(scenario, variables)


def run_scenario_from_file(filename: str, variables: Optional[Dict[str, Any]] = None) -> ScenarioResult:
    """Виконати сценарій з файлу."""
    return get_runner().run_scenario_from_file(filename, variables)


def save_scenario(scenario: Scenario, filename: Optional[str] = None) -> Dict[str, Any]:
    """Зберегти сценарій."""
    return get_runner().save_scenario(scenario, filename)


def load_scenario(filename: str) -> Dict[str, Any]:
    """Завантажити сценарій."""
    return get_runner().load_scenario(filename)


def list_scenarios() -> List[Dict[str, Any]]:
    """Список сценаріїв."""
    return get_runner().list_scenarios()


def delete_scenario(filename: str) -> Dict[str, Any]:
    """Видалити сценарій."""
    return get_runner().delete_scenario(filename)


def validate_scenario(scenario: Scenario) -> Dict[str, Any]:
    """Перевірити сценарій."""
    return get_runner().validate_scenario(scenario)


# ==================== ВБУДОВАНІ СЦЕНАРІЇ ====================

def scenario_save_file(window_title: Optional[str] = None) -> ScenarioResult:
    """
    Сценарій: Зберегти файл.
    Ctrl+S → обробка діалогу (якщо з'явився).
    """
    steps = [
        ScenarioStep("hotkey", "Натиснути Ctrl+S", {"keys": ["ctrl", "s"]}),
        ScenarioStep("wait", "Очікування діалогу", {"seconds": 1.0}),
        ScenarioStep("dialog", "Підтвердити збереження", {"action": "ok"}, verify="Зберегти", on_fail="skip")
    ]

    scenario = Scenario(
        name="save_file",
        description="Зберегти поточний файл",
        steps=steps
    )

    return get_runner().run_scenario(scenario)


def scenario_open_file(window_title: Optional[str] = None, file_path: Optional[str] = None) -> ScenarioResult:
    """
    Сценарій: Відкрити файл.
    Ctrl+O → ввести шлях → Enter.
    """
    steps = [
        ScenarioStep("hotkey", "Натиснути Ctrl+O", {"keys": ["ctrl", "o"]}),
        ScenarioStep("wait", "Очікування діалогу", {"seconds": 1.0}),
    ]

    if file_path:
        steps.append(ScenarioStep("type", "Ввести шлях", {"field": "Ім'я файлу", "text": file_path, "clear_first": True}))
        steps.append(ScenarioStep("wait", "Очікування", {"seconds": 0.5}))

    steps.append(ScenarioStep("dialog", "Підтвердити", {"action": "ok"}, on_fail="skip"))

    scenario = Scenario(
        name="open_file",
        description=f"Відкрити файл {file_path or ''}",
        steps=steps
    )

    return get_runner().run_scenario(scenario)


def scenario_save_as(window_title: Optional[str] = None, save_path: Optional[str] = None) -> ScenarioResult:
    """
    Сценарій: Зберегти як.
    Ctrl+Shift+S → ввести шлях → Enter.
    """
    steps = [
        ScenarioStep("hotkey", "Натиснути Ctrl+Shift+S", {"keys": ["ctrl", "shift", "s"]}),
        ScenarioStep("wait", "Очікування діалогу", {"seconds": 1.0}),
    ]

    if save_path:
        steps.append(ScenarioStep("type", "Ввести шлях", {"field": "Ім'я файлу", "text": save_path, "clear_first": True}))
        steps.append(ScenarioStep("wait", "Очікування", {"seconds": 0.5}))

    steps.append(ScenarioStep("dialog", "Підтвердити", {"action": "ok"}, on_fail="skip"))

    scenario = Scenario(
        name="save_as",
        description=f"Зберегти як {save_path or ''}",
        steps=steps
    )

    return get_runner().run_scenario(scenario)


def scenario_find_in_program(window_title: Optional[str] = None, search_text: Optional[str] = None) -> ScenarioResult:
    """
    Сценарій: Пошук в програмі.
    Ctrl+F → ввести текст → Enter.
    """
    steps = [
        ScenarioStep("hotkey", "Натиснути Ctrl+F", {"keys": ["ctrl", "f"]}),
        ScenarioStep("wait", "Очікування панелі пошуку", {"seconds": 0.5}),
    ]

    if search_text:
        steps.append(ScenarioStep("type", "Ввести текст пошуку", {"field": "Знайти", "text": search_text, "clear_first": True}))

    steps.append(ScenarioStep("hotkey", "Пошук (Enter)", {"keys": ["return"]}))

    scenario = Scenario(
        name="find_in_program",
        description=f"Пошук '{search_text or ''}'",
        steps=steps
    )

    return get_runner().run_scenario(scenario)


def scenario_print(window_title: Optional[str] = None) -> ScenarioResult:
    """
    Сценарій: Друк.
    Ctrl+P → OK в діалозі друку.
    """
    steps = [
        ScenarioStep("hotkey", "Натиснути Ctrl+P", {"keys": ["ctrl", "p"]}),
        ScenarioStep("wait", "Очікування діалогу друку", {"seconds": 1.5}),
        ScenarioStep("dialog", "Підтвердити друк", {"expected": "Друк", "action": "ok"}, on_fail="skip")
    ]

    scenario = Scenario(
        name="print",
        description="Відкрити діалог друку",
        steps=steps
    )

    return get_runner().run_scenario(scenario)


def scenario_undo_redo(window_title: Optional[str] = None, action: str = "undo", count: int = 1) -> ScenarioResult:
    """
    Сценарій: Undo/Redo.
    Ctrl+Z / Ctrl+Y.
    """
    hotkey = "z" if action == "undo" else "y"

    steps = [
        ScenarioStep("hotkey", f"{action.upper()} x{count}", {"keys": ["ctrl", hotkey]})
        for _ in range(count)
    ]

    scenario = Scenario(
        name=f"{action}_redo",
        description=f"{action.upper()} x{count}",
        steps=steps
    )

    return get_runner().run_scenario(scenario)


def scenario_select_all_copy(window_title: Optional[str] = None) -> Dict[str, Any]:
    """
    Сценарій: Виділити все і скопіювати.
    Ctrl+A → Ctrl+C.
    """
    try:
        keyboard_hotkey("ctrl", "a")
        time.sleep(0.2)
        keyboard_hotkey("ctrl", "c")

        return {
            "success": True,
            "message": "Виділено все та скопійовано в буфер",
            "clipboard_ready": True
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Помилка: {str(e)}",
            "error": str(e)
        }
