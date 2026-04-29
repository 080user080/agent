"""
Аналіз контексту екрану.

GUI Automation Phase 5 — розуміння поточного стану UI.
Агент аналізує екран, пропонує наступні дії, визначає
перешкоди та перевіряє виконання цілей.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .tools_screen_capture import ScreenCapture
from .tools_ocr import ocr_screen, find_text_on_screen
from .tools_ui_detector import (
    find_button_by_text, find_input_field, find_checkbox,
    find_progress_bar, find_label
)
from .tools_app_recognizer import (
    detect_active_application, detect_application_state,
    detect_file_dialog, detect_error_dialog, detect_context_menu
)


class ScreenElementType(Enum):
    """Типи елементів на екрані."""
    BUTTON = "button"
    INPUT = "input"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    DIALOG = "dialog"
    MENU = "menu"
    TEXT = "text"
    IMAGE = "image"
    PROGRESS = "progress"


@dataclass
class ScreenElement:
    """Елемент, знайдений на екрані."""
    element_type: ScreenElementType
    text: Optional[str] = None
    description: str = ""
    bounds: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h
    confidence: float = 0.8
    state: Optional[str] = None  # "enabled", "disabled", "checked", etc.


@dataclass
class ScreenContext:
    """Контекст поточного екрану."""
    application: Dict[str, Any] = field(default_factory=dict)
    app_state: str = "unknown"  # idle, loading, error, dialog
    elements: List[ScreenElement] = field(default_factory=list)
    available_actions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    raw_text: str = ""
    screenshot_path: Optional[str] = None


@dataclass
class BlockerInfo:
    """Інформація про перешкоду."""
    blocker_type: str  # "dialog", "error", "loading", "unknown_ui"
    description: str
    suggested_fix: str
    severity: str = "medium"  # low, medium, high, critical


class ContextAnalyzer:
    """
    Аналізатор контексту екрану.
    Розуміє що відбувається на екрані та пропонує дії.
    """

    def __init__(self):
        self.screen = ScreenCapture()
        self._last_analysis: Optional[ScreenContext] = None
        self._analysis_history: List[ScreenContext] = []
        self._max_history = 10

    # ==================== АНАЛІЗ ЕКРАНУ ====================

    def analyze_current_context(self) -> Dict[str, Any]:
        """
        Проаналізувати поточний стан екрану.

        Returns:
            {
                "application": {"name", "type", "confidence"},
                "state": "idle|loading|error|dialog",
                "elements": [ScreenElement],
                "available_actions": [str],
                "warnings": [str],
                "message": str
            }
        """
        try:
            context = ScreenContext()

            # 1. Розпізнаємо активну програму
            app = detect_active_application()
            context.application = app

            # 2. Визначаємо стан програми
            state = detect_application_state()
            context.app_state = state.get("state", "unknown")
            context.warnings.extend(state.get("details", []))

            # 3. OCR для отримання тексту
            ocr_result = ocr_screen()
            context.raw_text = ocr_result.get("text", "")

            # 4. Шукаємо UI елементи
            context.elements = self._detect_all_elements()

            # 5. Визначаємо доступні дії
            context.available_actions = self._infer_available_actions(context)

            # 6. Перевіряємо на діалоги та блокери
            file_dialog = detect_file_dialog()
            if file_dialog["detected"]:
                context.app_state = "dialog"
                context.elements.append(ScreenElement(
                    element_type=ScreenElementType.DIALOG,
                    text=file_dialog.get("title"),
                    description=f"File dialog: {file_dialog.get('type', 'unknown')}"
                ))

            error_dialog = detect_error_dialog()
            if error_dialog["detected"]:
                context.app_state = "error"
                context.warnings.append(f"Error dialog: {error_dialog.get('message', '')}")

            # 7. Контекстне меню
            context_menu = detect_context_menu()
            if context_menu["detected"]:
                context.elements.append(ScreenElement(
                    element_type=ScreenElementType.MENU,
                    description=f"Context menu with {context_menu.get('count', 0)} items"
                ))

            # Збережемо в історію
            self._last_analysis = context
            self._analysis_history.append(context)
            if len(self._analysis_history) > self._max_history:
                self._analysis_history.pop(0)

            return {
                "success": True,
                "application": context.application,
                "state": context.app_state,
                "elements_count": len(context.elements),
                "elements": [
                    {
                        "type": e.element_type.value,
                        "text": e.text,
                        "description": e.description,
                        "bounds": e.bounds,
                        "state": e.state
                    }
                    for e in context.elements[:20]  # Ліміт для JSON
                ],
                "available_actions": context.available_actions[:10],
                "warnings": context.warnings,
                "raw_text_preview": context.raw_text[:200] + "..." if len(context.raw_text) > 200 else context.raw_text,
                "message": f"Проаналізовано {len(context.elements)} елементів в {app.get('name', 'невідомій програмі')}"
            }

        except Exception as e:
            return {
                "success": False,
                "application": {},
                "state": "error",
                "elements_count": 0,
                "elements": [],
                "available_actions": [],
                "warnings": [str(e)],
                "message": f"Помилка аналізу: {str(e)}",
                "error": str(e)
            }

    def _detect_all_elements(self) -> List[ScreenElement]:
        """Знайти всі елементи на екрані."""
        elements = []

        # Кнопки (шукаємо типові тексти кнопок)
        common_buttons = ["OK", "Скасувати", "Cancel", "Застосувати", "Apply",
                         "Так", "Yes", "Ні", "No", "Зберегти", "Save",
                         "Відкрити", "Open", "Закрити", "Close", "Далі", "Next",
                         "Назад", "Back", "Готово", "Finish"]

        for button_text in common_buttons:
            result = find_button_by_text(button_text, confidence=0.7)
            if result["success"]:
                elements.append(ScreenElement(
                    element_type=ScreenElementType.BUTTON,
                    text=button_text,
                    bounds=(result["x"], result["y"], 0, 0),
                    confidence=result.get("confidence", 0.7)
                ))

        # Поля вводу
        inputs = find_input_field()
        for inp in inputs:
            elements.append(ScreenElement(
                element_type=ScreenElementType.INPUT,
                bounds=(inp["x"], inp["y"], inp["width"], inp["height"]),
                confidence=0.8
            ))

        # Чекбокси
        checkboxes = find_checkbox()
        for cb in checkboxes:
            elements.append(ScreenElement(
                element_type=ScreenElementType.CHECKBOX,
                bounds=(cb["x"], cb["y"], 0, 0),
                state="checked" if cb.get("checked") else "unchecked",
                confidence=0.8
            ))

        # Прогрес-бар
        progress = find_progress_bar()
        if progress["found"]:
            elements.append(ScreenElement(
                element_type=ScreenElementType.PROGRESS,
                bounds=(progress["x"], progress["y"], progress["width"], progress["height"]),
                description=f"Progress: {progress.get('percent', 0)}%",
                confidence=0.8
            ))

        return elements

    def _infer_available_actions(self, context: ScreenContext) -> List[str]:
        """Визначити які дії доступні на основі контексту."""
        actions = []

        # Дії залежно від елементів
        for element in context.elements:
            if element.element_type == ScreenElementType.BUTTON:
                actions.append(f"click:{element.text}")
            elif element.element_type == ScreenElementType.INPUT:
                actions.append("type_in_field")
            elif element.element_type == ScreenElementType.CHECKBOX:
                actions.append("toggle_checkbox")
            elif element.element_type == ScreenElementType.DROPDOWN:
                actions.append("select_option")
            elif element.element_type == ScreenElementType.DIALOG:
                actions.extend(["handle_dialog:ok", "handle_dialog:cancel"])
            elif element.element_type == ScreenElementType.MENU:
                actions.append("select_menu_item")

        # Дії залежно від стану
        if context.app_state == "loading":
            actions.append("wait_for_loading")
        elif context.app_state == "error":
            actions.extend(["dismiss_error", "retry"])
        elif context.app_state == "dialog":
            actions.extend(["fill_dialog", "cancel_dialog"])

        # Стандартні дії
        actions.extend([
            "take_screenshot",
            "analyze_screen",
            "wait"
        ])

        # Видалимо дублікати
        return list(dict.fromkeys(actions))

    # ==================== ПРОПОЗИЦІЇ ТА ЦІЛІ ====================

    def suggest_next_action(self, goal: str) -> Dict[str, Any]:
        """
        Пропонує наступну дію для досягнення цілі.

        Args:
            goal: Опис цілі ("зберегти файл", "закрити програму")

        Returns:
            {
                "action": str,
                "params": dict,
                "confidence": float,
                "reasoning": str,
                "alternatives": [str]
            }
        """
        try:
            # Отримаємо контекст
            context_result = self.analyze_current_context()
            if not context_result["success"]:
                return {
                    "action": None,
                    "params": {},
                    "confidence": 0.0,
                    "reasoning": "Не вдалося проаналізувати контекст",
                    "alternatives": []
                }

            state = context_result["state"]
            available = context_result.get("available_actions", [])
            elements = context_result.get("elements", [])

            # Аналізуємо ціль
            goal_lower = goal.lower()

            # Шаблони цілей та відповідні дії
            suggestions = []

            # Збереження
            if any(word in goal_lower for word in ["зберегти", "save", "записати"]):
                if "click:Зберегти" in available or "click:Save" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "Зберегти", "element_type": "button"},
                        "confidence": 0.9,
                        "reasoning": "Знайдено кнопку 'Зберегти'"
                    })
                elif "click:OK" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "OK", "element_type": "button"},
                        "confidence": 0.7,
                        "reasoning": "Діалог збереження — підтвердити"
                    })
                else:
                    suggestions.append({
                        "action": "keyboard_hotkey",
                        "params": {"keys": ["ctrl", "s"]},
                        "confidence": 0.8,
                        "reasoning": "Гаряча клавіша Ctrl+S"
                    })

            # Відкриття
            elif any(word in goal_lower for word in ["відкрити", "open", "завантажити"]):
                if "click:Відкрити" in available or "click:Open" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "Відкрити", "element_type": "button"},
                        "confidence": 0.9
                    })
                else:
                    suggestions.append({
                        "action": "keyboard_hotkey",
                        "params": {"keys": ["ctrl", "o"]},
                        "confidence": 0.8,
                        "reasoning": "Гаряча клавіша Ctrl+O"
                    })

            # Закриття
            elif any(word in goal_lower for word in ["закрити", "close", "вийти", "exit"]):
                if state == "dialog":
                    suggestions.append({
                        "action": "handle_dialog",
                        "params": {"action": "ok"},
                        "confidence": 0.7,
                        "reasoning": "Закрити діалог спочатку"
                    })
                elif "click:Закрити" in available or "click:Close" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "Закрити"},
                        "confidence": 0.9
                    })
                else:
                    suggestions.append({
                        "action": "keyboard_hotkey",
                        "params": {"keys": ["alt", "f4"]},
                        "confidence": 0.7,
                        "reasoning": "Alt+F4 для закриття вікна"
                    })

            # Скасування
            elif any(word in goal_lower for word in ["скасувати", "cancel", "назад"]):
                if "click:Скасувати" in available or "click:Cancel" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "Скасувати"},
                        "confidence": 0.95
                    })
                elif "click:Назад" in available or "click:Back" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "Назад"},
                        "confidence": 0.8
                    })

            # Підтвердження
            elif any(word in goal_lower for word in ["підтвердити", "ok", "так", "yes", "готово"]):
                if "click:OK" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "OK"},
                        "confidence": 0.95
                    })
                elif "click:Так" in available or "click:Yes" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "Так"},
                        "confidence": 0.95
                    })
                elif "click:Готово" in available or "click:Finish" in available:
                    suggestions.append({
                        "action": "click_element",
                        "params": {"description": "Готово"},
                        "confidence": 0.9
                    })

            # Очікування завантаження
            elif state == "loading":
                suggestions.append({
                    "action": "wait",
                    "params": {"seconds": 2.0},
                    "confidence": 0.9,
                    "reasoning": "Програма завантажується — потрібно зачекати"
                })

            # Якщо немає конкретних пропозицій
            if not suggestions:
                # Запропонуємо що-небудь з доступних дій
                if available:
                    first_action = available[0]
                    suggestions.append({
                        "action": first_action,
                        "params": {},
                        "confidence": 0.3,
                        "reasoning": f"Найбільш доступна дія: {first_action}"
                    })

            # Виберемо найкращу пропозицію
            if suggestions:
                best = max(suggestions, key=lambda x: x["confidence"])
                alternatives = [s["action"] for s in suggestions if s != best][:3]

                return {
                    "action": best["action"],
                    "params": best.get("params", {}),
                    "confidence": best["confidence"],
                    "reasoning": best.get("reasoning", "На основі аналізу контексту"),
                    "alternatives": alternatives,
                    "context": {
                        "app": context_result.get("application", {}),
                        "state": state,
                        "available_actions_count": len(available)
                    }
                }

            return {
                "action": None,
                "params": {},
                "confidence": 0.0,
                "reasoning": "Не вдалося визначити дію для цілі",
                "alternatives": [],
                "context": context_result
            }

        except Exception as e:
            return {
                "action": None,
                "params": {},
                "confidence": 0.0,
                "reasoning": f"Помилка: {str(e)}",
                "error": str(e),
                "alternatives": []
            }

    def explain_screen(self, detail_level: str = "normal") -> str:
        """
        Створити текстовий опис поточного екрану для LLM.

        Args:
            detail_level: "brief", "normal", "detailed"

        Returns:
            Текстовий опис екрану
        """
        try:
            context_result = self.analyze_current_context()

            if not context_result["success"]:
                return f"Не вдалося проаналізувати екран: {context_result.get('message', '')}"

            app = context_result.get("application", {})
            state = context_result.get("state", "unknown")
            elements = context_result.get("elements", [])
            warnings = context_result.get("warnings", [])

            lines = []

            # Заголовок
            app_name = app.get("name", "Невідома програма")
            lines.append(f"Відкрита програма: {app_name}")
            lines.append(f"Стан: {state}")

            if detail_level == "brief":
                # Короткий опис
                element_summary = {}
                for e in elements:
                    et = e.get("type", "unknown")
                    element_summary[et] = element_summary.get(et, 0) + 1

                if element_summary:
                    lines.append(f"Елементи: {', '.join(f'{k}:{v}' for k, v in element_summary.items())}")

                if warnings:
                    lines.append(f"Попередження: {len(warnings)}")

            else:
                # Детальний опис елементів
                if elements:
                    lines.append(f"\nЗнайдено {len(elements)} елементів:")

                    # Групуємо за типом
                    by_type = {}
                    for e in elements:
                        et = e.get("type", "unknown")
                        if et not in by_type:
                            by_type[et] = []
                        by_type[et].append(e)

                    for etype, elems in by_type.items():
                        lines.append(f"\n{etype.upper()}:")
                        for i, e in enumerate(elems[:5], 1):  # Ліміт 5 на тип
                            text = e.get("text", "")
                            desc = e.get("description", "")
                            state = e.get("state", "")

                            parts = []
                            if text:
                                parts.append(f'"{text}"')
                            if desc:
                                parts.append(desc)
                            if state:
                                parts.append(f"[{state}]")

                            if parts:
                                lines.append(f"  {i}. {' — '.join(parts)}")

                        if len(elems) > 5:
                            lines.append(f"  ... ще {len(elems) - 5}")

                # Доступні дії
                actions = context_result.get("available_actions", [])
                if actions and detail_level == "detailed":
                    lines.append(f"\nДоступні дії: {', '.join(actions[:10])}")

                # Попередження
                if warnings:
                    lines.append(f"\nПопередження:")
                    for w in warnings:
                        lines.append(f"  ⚠ {w}")

                # Сирий текст (тільки для detailed)
                if detail_level == "detailed":
                    raw = context_result.get("raw_text_preview", "")
                    if raw:
                        lines.append(f"\nРозпізнаний текст на екрані:\n{raw}")

            return "\n".join(lines)

        except Exception as e:
            return f"Помилка створення опису: {str(e)}"

    def detect_user_goal_completion(self, goal_description: str) -> Dict[str, Any]:
        """
        Перевірити чи виконана ціль користувача.

        Args:
            goal_description: Опис цілі

        Returns:
            {"completed": bool, "confidence": float, "evidence": [str]}
        """
        try:
            # Отримаємо контекст
            context_result = self.analyze_current_context()
            if not context_result["success"]:
                return {
                    "completed": False,
                    "confidence": 0.0,
                    "evidence": ["Не вдалося проаналізувати екран"]
                }

            raw_text = context_result.get("raw_text_preview", "").lower()
            state = context_result.get("state", "")
            elements = context_result.get("elements", [])
            goal_lower = goal_description.lower()

            evidence = []
            completed = False
            confidence = 0.0

            # Перевіряємо ознаки виконання для різних типів цілей

            # Збереження файлу
            if any(word in goal_lower for word in ["зберегти", "save"]):
                if "збережено" in raw_text or "saved" in raw_text:
                    completed = True
                    confidence = 0.9
                    evidence.append("Знайдено текст 'збережено' на екрані")
                elif state == "idle" and "click:Зберегти" not in str(elements):
                    # Діалог збереження зник
                    completed = True
                    confidence = 0.7
                    evidence.append("Діалог збереження закрито, програма в стані idle")

            # Відкриття файлу
            elif any(word in goal_lower for word in ["відкрити", "open", "завантажити"]):
                if "завантажено" in raw_text or "loaded" in raw_text or "відкрито" in raw_text:
                    completed = True
                    confidence = 0.85
                    evidence.append("Знайдено підтвердження відкриття")
                elif state == "idle":
                    completed = True
                    confidence = 0.6
                    evidence.append("Програма готова — ймовірно файл відкрито")

            # Закриття програми/вікна
            elif any(word in goal_lower for word in ["закрити", "close", "вийти", "exit"]):
                # Перевіримо чи програма ще активна
                app = context_result.get("application", {})
                if not app.get("name"):
                    completed = True
                    confidence = 0.95
                    evidence.append("Програма більше не активна")

            # Підтвердження дії
            elif any(word in goal_lower for word in ["підтвердити", "прийняти", "accept"]):
                if state != "dialog":
                    completed = True
                    confidence = 0.8
                    evidence.append("Діалог закрито — дія підтверджена")

            # Скасування
            elif any(word in goal_lower for word in ["скасувати", "cancel", "відмінити"]):
                if state != "dialog":
                    completed = True
                    confidence = 0.8
                    evidence.append("Діалог закрито — дія скасована")

            # Якщо немає специфічних ознак — перевіримо загальні
            if not completed:
                # Перевіримо чи немає помилок
                if state == "error":
                    evidence.append("Виявлено стан помилки — ціль можливо не виконана")
                    confidence = 0.1
                elif state == "loading":
                    evidence.append("Програма ще завантажується")
                    confidence = 0.3
                else:
                    evidence.append("Ознаки виконання не виявлені однозначно")
                    confidence = 0.5

            return {
                "completed": completed,
                "confidence": confidence,
                "evidence": evidence,
                "goal": goal_description,
                "current_state": state
            }

        except Exception as e:
            return {
                "completed": False,
                "confidence": 0.0,
                "evidence": [f"Помилка перевірки: {str(e)}"],
                "error": str(e)
            }

    def detect_blocker(self) -> Optional[Dict[str, Any]]:
        """
        Виявити що заважає виконанню задачі.

        Returns:
            {"type", "description", "suggested_fix", "severity"} або None
        """
        try:
            context_result = self.analyze_current_context()
            if not context_result["success"]:
                return {
                    "type": "unknown",
                    "description": "Не вдалося проаналізувати екран",
                    "suggested_fix": "Спробуйте ще раз або перевірте чи програма активна",
                    "severity": "medium"
                }

            state = context_result.get("state", "")
            warnings = context_result.get("warnings", [])

            # Перевіримо стан
            if state == "error":
                return {
                    "type": "error",
                    "description": warnings[0] if warnings else "Виявлено помилку в програмі",
                    "suggested_fix": "Обробіть діалог помилки або перезапустіть програму",
                    "severity": "high"
                }

            if state == "loading":
                return {
                    "type": "loading",
                    "description": "Програма завантажується або виконує операцію",
                    "suggested_fix": "Зачекайте завершення операції",
                    "severity": "low"
                }

            if state == "dialog":
                # Перевіримо чи це файловий діалог
                file_dialog = detect_file_dialog()
                if file_dialog["detected"]:
                    return {
                        "type": "file_dialog",
                        "description": f"Відкрито файловий діалог: {file_dialog.get('title', '')}",
                        "suggested_fix": "Заповніть шлях до файлу та підтвердіть або скасуйте",
                        "severity": "medium"
                    }

                error_dialog = detect_error_dialog()
                if error_dialog["detected"]:
                    return {
                        "type": "error_dialog",
                        "description": f"Помилка: {error_dialog.get('message', '')}",
                        "suggested_fix": "Прочитайте повідомлення та натисніть OK або зв'яжіться з підтримкою",
                        "severity": "high"
                    }

                return {
                    "type": "dialog",
                    "description": "Відкрито модальне вікно що блокує взаємодію",
                    "suggested_fix": "Обробіть діалог натиснувши OK, Cancel, або іншу доступну кнопку",
                    "severity": "medium"
                }

            # Контекстне меню
            context_menu = detect_context_menu()
            if context_menu["detected"]:
                return {
                    "type": "context_menu",
                    "description": f"Відкрито контекстне меню з {context_menu.get('count', 0)} пунктами",
                    "suggested_fix": "Виберіть пункт меню або натисніть Escape для закриття",
                    "severity": "low"
                }

            # Перевіримо чи програма взагалі активна
            app = context_result.get("application", {})
            if not app.get("name"):
                return {
                    "type": "no_active_app",
                    "description": "Немає активної програми для взаємодії",
                    "suggested_fix": "Активуйте вікно програми клікнувши по ньому",
                    "severity": "medium"
                }

            # Немає блокерів
            return None

        except Exception as e:
            return {
                "type": "error",
                "description": f"Помилка виявлення блокера: {str(e)}",
                "suggested_fix": "Перевірте логи та спробуйте знову",
                "severity": "low"
            }

    # ==================== ІСТОРІЯ ТА ПОРІВНЯННЯ ====================

    def get_context_changes(self, steps_back: int = 1) -> Dict[str, Any]:
        """
        Отримати зміни в контексті порівняно з попереднім аналізом.

        Args:
            steps_back: На скільки кроків назад порівнювати

        Returns:
            {"changed": bool, "added": [str], "removed": [str], "modified": [str]}
        """
        if len(self._analysis_history) < steps_back + 1:
            return {
                "changed": False,
                "message": "Недостатньо історії для порівняння",
                "added": [],
                "removed": [],
                "modified": []
            }

        current = self._analysis_history[-1]
        previous = self._analysis_history[-(steps_back + 1)]

        # Порівняємо елементи
        current_elements = {(e.element_type.value, e.text) for e in current.elements}
        previous_elements = {(e.element_type.value, e.text) for e in previous.elements}

        added = current_elements - previous_elements
        removed = previous_elements - current_elements

        # Порівняємо стан
        state_changed = current.app_state != previous.app_state

        return {
            "changed": bool(added or removed or state_changed),
            "state_changed": state_changed,
            "old_state": previous.app_state,
            "new_state": current.app_state,
            "added_elements": [f"{e[0]}: {e[1]}" for e in added],
            "removed_elements": [f"{e[0]}: {e[1]}" for e in removed],
            "app_changed": current.application != previous.application
        }


# ==================== ПУБЛІЧНИЙ API ====================

_analyzer = None


def get_analyzer() -> ContextAnalyzer:
    """Отримати singleton екземпляр ContextAnalyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ContextAnalyzer()
    return _analyzer


# Зручні функції

def analyze_current_context() -> Dict[str, Any]:
    """Проаналізувати поточний контекст."""
    return get_analyzer().analyze_current_context()


def suggest_next_action(goal: str) -> Dict[str, Any]:
    """Запропонувати наступну дію."""
    return get_analyzer().suggest_next_action(goal)


def explain_screen(detail_level: str = "normal") -> str:
    """Отримати текстовий опис екрану."""
    return get_analyzer().explain_screen(detail_level)


def detect_user_goal_completion(goal_description: str) -> Dict[str, Any]:
    """Перевірити чи виконана ціль."""
    return get_analyzer().detect_user_goal_completion(goal_description)


def detect_blocker() -> Optional[Dict[str, Any]]:
    """Виявити перешкоду."""
    return get_analyzer().detect_blocker()


def get_context_changes(steps_back: int = 1) -> Dict[str, Any]:
    """Отримати зміни в контексті."""
    return get_analyzer().get_context_changes(steps_back)
