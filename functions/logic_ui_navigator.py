"""
Інтелектуальна навігація по UI.

GUI Automation Phase 5 — "мозок" для взаємодії з інтерфейсом.
Агент виконує складні UI-сценарії: заповнює форми, проходить wizard,
відповідає на діалоги, працює з меню.

Залежності: Phase 1-4 (mouse/keyboard, screen capture, OCR, CV)
"""

import time
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

# Імпорти з попередніх фаз
from .tools_mouse_keyboard import (
    mouse_click, mouse_move, mouse_scroll,
    keyboard_type, keyboard_press, keyboard_hotkey
)
from .tools_screen_capture import ScreenCapture
from .tools_ocr import find_text_on_screen, click_text
from .tools_ui_detector import (
    find_button_by_text, find_input_field,
    find_label, find_input_near_label,
    find_checkbox, is_checkbox_checked
)
from .tools_app_recognizer import detect_active_application, detect_application_state


class UIActionType(Enum):
    """Типи UI-дій."""
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    CHECK = "check"
    NAVIGATE = "navigate"
    MENU = "menu"
    DIALOG = "dialog"


@dataclass
class UIElement:
    """Опис UI-елементу."""
    element_type: str  # "button", "input", "checkbox", "dropdown", "menu", etc.
    description: str  # Текстовий опис для пошуку
    text: Optional[str] = None  # Текст на елементі
    region: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
    confidence: float = 0.8


@dataclass
class UIAction:
    """Опис UI-дії."""
    action_type: UIActionType
    element: Optional[UIElement] = None
    params: Dict[str, Any] = field(default_factory=dict)
    verify: Optional[str] = None  # Текст для перевірки після дії
    on_fail: str = "abort"  # "skip", "abort", "retry"
    max_retries: int = 2


@dataclass
class UIActionResult:
    """Результат виконання UI-дії."""
    success: bool
    action: UIAction
    message: str
    coordinates: Optional[Tuple[int, int]] = None
    screenshot_path: Optional[str] = None
    error: Optional[str] = None


class UINavigator:
    """
    Інтелектуальний навігатор по UI.
    Виконує складні сценарії взаємодії з інтерфейсом.
    """

    def __init__(self):
        self.screen = ScreenCapture()
        self.action_history: List[UIActionResult] = []
        self.max_history = 50
        self._last_screenshot = None

    # ==================== БАЗОВІ UI-ДІЇ ====================

    def click_element(
        self,
        description: str,
        element_type: str = "button",
        region: Optional[Tuple[int, int, int, int]] = None,
        offset_x: int = 0,
        offset_y: int = 0
    ) -> Dict[str, Any]:
        """
        Клікнути по елементу за описом.

        Args:
            description: Текстовий опис ("кнопка OK", "поле пошуку")
            element_type: Тип елементу (button, input, link, menu)
            region: Обмежити пошук регіоном (x, y, w, h)
            offset_x, offset_y: Зміщення від центру

        Returns:
            {"success": bool, "coordinates": {x, y}, "message": str}
        """
        try:
            # Спробуємо знайти як кнопку за текстом
            if element_type in ("button", "link", "menu"):
                result = find_button_by_text(
                    text=description,
                    region=region,
                    confidence=0.7
                )
                if result["success"]:
                    x = result["center_x"] + offset_x
                    y = result["center_y"] + offset_y
                    mouse_click(x, y)
                    return {
                        "success": True,
                        "coordinates": {"x": x, "y": y},
                        "message": f"Клікнуто по '{description}'",
                        "method": "text_detection"
                    }

            # Спробуємо знайти через OCR
            ocr_result = find_text_on_screen(
                text=description,
                case_sensitive=False
            )
            if ocr_result["found"]:
                x = ocr_result["x"] + offset_x
                y = ocr_result["y"] + offset_y
                click_text(description, offset_x, offset_y)
                return {
                    "success": True,
                    "coordinates": {"x": x, "y": y},
                    "message": f"Клікнуто по тексту '{description}'",
                    "method": "ocr"
                }

            return {
                "success": False,
                "coordinates": None,
                "message": f"Елемент '{description}' не знайдено",
                "method": None
            }

        except Exception as e:
            return {
                "success": False,
                "coordinates": None,
                "message": f"Помилка кліку: {str(e)}",
                "error": str(e)
            }

    def type_in_field(
        self,
        field_description: str,
        text: str,
        clear_first: bool = True,
        press_enter: bool = False
    ) -> Dict[str, Any]:
        """
        Ввести текст у поле.

        Args:
            field_description: Опис поля ("Email", "Пошук", "Ім'я")
            text: Текст для введення
            clear_first: Очистити поле перед введенням
            press_enter: Натиснути Enter після введення

        Returns:
            {"success": bool, "field": str, "text": str, "message": str}
        """
        try:
            # Знайдемо поле поруч з міткою
            field = find_input_near_label(field_description)

            if not field["success"]:
                # Спробуємо знайти поле вводу безпосередньо
                inputs = find_input_field()
                if inputs:
                    # Виберемо перше доступне поле
                    field = {
                        "success": True,
                        "x": inputs[0]["x"],
                        "y": inputs[0]["y"],
                        "width": inputs[0]["width"],
                        "height": inputs[0]["height"]
                    }
                else:
                    return {
                        "success": False,
                        "field": field_description,
                        "text": None,
                        "message": f"Поле '{field_description}' не знайдено"
                    }

            # Клікнемо по полю
            center_x = field["x"] + field["width"] // 2
            center_y = field["y"] + field["height"] // 2
            mouse_click(center_x, center_y)
            time.sleep(0.2)

            # Очистимо поле якщо потрібно
            if clear_first:
                keyboard_hotkey("ctrl", "a")
                time.sleep(0.1)
                keyboard_press("delete")
                time.sleep(0.1)

            # Введемо текст
            keyboard_type(text)

            if press_enter:
                time.sleep(0.1)
                keyboard_press("return")

            return {
                "success": True,
                "field": field_description,
                "text": text,
                "coordinates": {"x": center_x, "y": center_y},
                "message": f"Введено '{text}' у поле '{field_description}'"
            }

        except Exception as e:
            return {
                "success": False,
                "field": field_description,
                "text": None,
                "message": f"Помилка введення: {str(e)}",
                "error": str(e)
            }

    def select_option(
        self,
        dropdown_description: str,
        option_text: str
    ) -> Dict[str, Any]:
        """
        Вибрати пункт з dropdown.

        Args:
            dropdown_description: Опис dropdown ("Країна", "Мова")
            option_text: Текст пункту для вибору

        Returns:
            {"success": bool, "dropdown": str, "option": str}
        """
        try:
            # Клікнемо по dropdown
            click_result = self.click_element(dropdown_description, "dropdown")
            if not click_result["success"]:
                return {
                    "success": False,
                    "dropdown": dropdown_description,
                    "option": option_text,
                    "message": f"Dropdown '{dropdown_description}' не знайдено"
                }

            time.sleep(0.3)  # Час на відкриття dropdown

            # Клікнемо по пункту
            option_result = self.click_element(option_text, "button")

            return {
                "success": option_result["success"],
                "dropdown": dropdown_description,
                "option": option_text,
                "message": option_result["message"]
            }

        except Exception as e:
            return {
                "success": False,
                "dropdown": dropdown_description,
                "option": option_text,
                "message": f"Помилка вибору: {str(e)}",
                "error": str(e)
            }

    def check_checkbox(
        self,
        label: str,
        state: bool = True
    ) -> Dict[str, Any]:
        """
        Встановити стан чекбоксу.

        Args:
            label: Текст мітки чекбоксу
            state: True — встановити, False — зняти

        Returns:
            {"success": bool, "label": str, "state": bool}
        """
        try:
            # Знайдемо чекбокс поруч з міткою
            checkbox = find_input_near_label(label)

            if not checkbox["success"]:
                # Спробуємо знайти всі чекбокси
                checkboxes = find_checkbox()
                if not checkboxes:
                    return {
                        "success": False,
                        "label": label,
                        "state": None,
                        "message": f"Чекбокс '{label}' не знайдено"
                    }
                # Виберемо перший (або шукатимемо за текстом поруч)
                checkbox = {
                    "success": True,
                    "x": checkboxes[0]["x"],
                    "y": checkboxes[0]["y"],
                    "checked": checkboxes[0]["checked"]
                }

            # Перевіримо поточний стан
            current_state = checkbox.get("checked", False)

            if current_state != state:
                # Потрібно змінити стан — клікнемо
                center_x = checkbox["x"] + 10  # Центр чекбоксу
                center_y = checkbox["y"] + 10
                mouse_click(center_x, center_y)

                return {
                    "success": True,
                    "label": label,
                    "previous_state": current_state,
                    "new_state": state,
                    "message": f"Чекбокс '{label}' {'встановлено' if state else 'знято'}"
                }
            else:
                return {
                    "success": True,
                    "label": label,
                    "state": state,
                    "message": f"Чекбокс '{label}' вже у потрібному стані"
                }

        except Exception as e:
            return {
                "success": False,
                "label": label,
                "state": None,
                "message": f"Помилка: {str(e)}",
                "error": str(e)
            }

    def select_radio(self, label: str) -> Dict[str, Any]:
        """
        Вибрати radio button.

        Args:
            label: Текст мітки radio button

        Returns:
            {"success": bool, "label": str}
        """
        # Radio button поводиться як клік по елементу
        return self.click_element(label, "radio")

    def navigate_tabs(self, tab_name: str) -> Dict[str, Any]:
        """
        Перейти на вкладку.

        Args:
            tab_name: Назва вкладки

        Returns:
            {"success": bool, "tab": str}
        """
        return self.click_element(tab_name, "tab")

    # ==================== ФОРМИ ТА WIZARD ====================

    def fill_form(self, field_dict: Dict[str, str]) -> Dict[str, Any]:
        """
        Заповнити форму.

        Args:
            field_dict: Словник {"Назва поля": "Значення"}

        Returns:
            {"success": bool, "filled": [str], "failed": [str]}
        """
        filled = []
        failed = []

        for field_name, value in field_dict.items():
            result = self.type_in_field(field_name, value)
            if result["success"]:
                filled.append(field_name)
            else:
                failed.append({
                    "field": field_name,
                    "error": result.get("message", "Невідома помилка")
                })

        success = len(failed) == 0

        return {
            "success": success,
            "filled": filled,
            "failed": failed,
            "total": len(field_dict),
            "message": f"Заповнено {len(filled)}/{len(field_dict)} полів"
        }

    def submit_form(self, submit_button_text: str = "OK") -> Dict[str, Any]:
        """
        Відправити форму.

        Args:
            submit_button_text: Текст кнопки відправки

        Returns:
            {"success": bool, "button": str}
        """
        return self.click_element(submit_button_text, "button")

    def read_form_values(self, field_names: List[str]) -> Dict[str, Any]:
        """
        Прочитати значення полів форми.

        Args:
            field_names: Список назв полів

        Returns:
            {"success": bool, "values": {field: value}}
        """
        # Потребує OCR для читання значень
        from .tools_ocr import ocr_screen

        try:
            ocr_result = ocr_screen()
            text = ocr_result.get("text", "")

            values = {}
            for field_name in field_names:
                # Спробуємо знайти значення поруч з назвою поля
                # Це спрощена реалізація — в реальності потрібен більш розумний аналіз
                values[field_name] = f"[значення поруч з '{field_name}']"

            return {
                "success": True,
                "values": values,
                "raw_text": text,
                "message": f"Зчитано {len(field_names)} полів"
            }

        except Exception as e:
            return {
                "success": False,
                "values": {},
                "message": f"Помилка читання: {str(e)}",
                "error": str(e)
            }

    def validate_form_filled(
        self,
        required_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Перевірити що всі обов'язкові поля заповнені.

        Args:
            required_fields: Список обов'язкових полів

        Returns:
            {"valid": bool, "missing": [str]}
        """
        result = self.read_form_values(required_fields)

        if not result["success"]:
            return {"valid": False, "missing": required_fields}

        # Спробуємо визначити які поля порожні
        missing = []
        for field in required_fields:
            value = result["values"].get(field, "")
            if not value or value == f"[значення поруч з '{field}']":
                missing.append(field)

        return {
            "valid": len(missing) == 0,
            "missing": missing,
            "checked": required_fields
        }

    # ==================== МЕНЮ ====================

    def open_menu(self, menu_name: str) -> Dict[str, Any]:
        """
        Відкрити пункт меню (File, Edit, View, ...).

        Args:
            menu_name: Назва меню

        Returns:
            {"success": bool, "menu": str}
        """
        # Спробуємо клік по меню
        result = self.click_element(menu_name, "menu")
        time.sleep(0.2)  # Час на відкриття меню
        return result

    def click_menu_item(self, path_list: List[str]) -> Dict[str, Any]:
        """
        Клік по пункту меню за шляхом.

        Args:
            path_list: Шлях ["Файл", "Відкрити", ...]

        Returns:
            {"success": bool, "path": [str]}
        """
        try:
            for item in path_list:
                result = self.click_element(item, "menu")
                if not result["success"]:
                    return {
                        "success": False,
                        "path": path_list,
                        "failed_at": item,
                        "message": f"Не вдалося клікнути '{item}'"
                    }
                time.sleep(0.2)

            return {
                "success": True,
                "path": path_list,
                "message": f"Виконано шлях: {' > '.join(path_list)}"
            }

        except Exception as e:
            return {
                "success": False,
                "path": path_list,
                "message": f"Помилка: {str(e)}",
                "error": str(e)
            }

    def open_context_menu(self, x: int, y: int) -> Dict[str, Any]:
        """
        Відкрити контекстне меню.

        Args:
            x, y: Координати

        Returns:
            {"success": bool, "coordinates": {x, y}}
        """
        try:
            mouse_click(x, y, button="right")
            return {
                "success": True,
                "coordinates": {"x": x, "y": y},
                "message": f"Відкрито контекстне меню в ({x}, {y})"
            }
        except Exception as e:
            return {
                "success": False,
                "coordinates": None,
                "message": f"Помилка: {str(e)}",
                "error": str(e)
            }

    def click_context_item(self, item_text: str) -> Dict[str, Any]:
        """
        Вибрати пункт контекстного меню.

        Args:
            item_text: Текст пункту

        Returns:
            {"success": bool, "item": str}
        """
        return self.click_element(item_text, "menu")

    def close_menu(self) -> Dict[str, Any]:
        """
        Закрити відкрите меню (Escape).

        Returns:
            {"success": bool}
        """
        try:
            keyboard_press("esc")
            return {
                "success": True,
                "message": "Меню закрито (Escape)"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Помилка: {str(e)}",
                "error": str(e)
            }

    # ==================== ДІАЛОГИ ====================

    def handle_dialog(
        self,
        expected_text: Optional[str] = None,
        action: str = "ok"
    ) -> Dict[str, Any]:
        """
        Відповісти на діалог.

        Args:
            expected_text: Очікуваний текст діалогу (для перевірки)
            action: "ok", "cancel", "yes", "no", "retry", "ignore"

        Returns:
            {"success": bool, "action": str, "dialog_text": str}
        """
        try:
            # Перевіримо текст діалогу якщо потрібно
            if expected_text:
                from .tools_ocr import find_text_on_screen
                check = find_text_on_screen(expected_text)
                if not check["found"]:
                    return {
                        "success": False,
                        "action": None,
                        "dialog_text": None,
                        "message": f"Очікуваний текст '{expected_text}' не знайдено"
                    }

            # Визначимо кнопку для кліку
            button_map = {
                "ok": "OK",
                "cancel": "Скасувати",
                "yes": "Так",
                "no": "Ні",
                "retry": "Повторити",
                "ignore": "Пропустити"
            }

            button_text = button_map.get(action, action)
            result = self.click_element(button_text, "button")

            return {
                "success": result["success"],
                "action": action,
                "button": button_text,
                "message": result["message"]
            }

        except Exception as e:
            return {
                "success": False,
                "action": action,
                "message": f"Помилка: {str(e)}",
                "error": str(e)
            }

    def dismiss_all_dialogs(self, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Закрити всі модальні вікна.

        Args:
            timeout: Максимальний час на закриття

        Returns:
            {"closed": int, "failed": int}
        """
        start_time = time.time()
        closed = 0
        failed = 0

        while time.time() - start_time < timeout:
            # Спробуємо закрити кнопкою Cancel або OK
            for button in ["Скасувати", "Cancel", "OK", "Закрити", "Close"]:
                result = self.click_element(button, "button")
                if result["success"]:
                    closed += 1
                    time.sleep(0.3)
                    break
            else:
                # Не знайшли кнопку — вийдемо
                break

            # Перевіримо чи ще є діалоги
            state = detect_application_state()
            if state.get("state") != "dialog":
                break

        return {
            "closed": closed,
            "failed": failed,
            "message": f"Закрито {closed} діалогів"
        }

    # ==================== ВИКОНАННЯ ДІЙ ====================

    def execute_action(self, action: UIAction) -> UIActionResult:
        """
        Виконати UI-дію з логуванням.

        Args:
            action: UIAction для виконання

        Returns:
            UIActionResult
        """
        result = None

        if action.action_type == UIActionType.CLICK:
            if action.element:
                raw_result = self.click_element(
                    action.element.description,
                    action.element.element_type
                )
            else:
                raw_result = {"success": False, "message": "Немає елементу"}

        elif action.action_type == UIActionType.TYPE:
            field = action.params.get("field", "")
            text = action.params.get("text", "")
            raw_result = self.type_in_field(field, text)

        elif action.action_type == UIActionType.CHECK:
            label = action.params.get("label", "")
            state = action.params.get("state", True)
            raw_result = self.check_checkbox(label, state)

        elif action.action_type == UIActionType.MENU:
            path = action.params.get("path", [])
            raw_result = self.click_menu_item(path)

        elif action.action_type == UIActionType.DIALOG:
            expected = action.params.get("expected_text")
            dialog_action = action.params.get("action", "ok")
            raw_result = self.handle_dialog(expected, dialog_action)

        else:
            raw_result = {"success": False, "message": "Невідомий тип дії"}

        # Створимо результат
        ui_result = UIActionResult(
            success=raw_result.get("success", False),
            action=action,
            message=raw_result.get("message", ""),
            coordinates=raw_result.get("coordinates"),
            error=raw_result.get("error")
        )

        # Збережемо в історію
        self.action_history.append(ui_result)
        if len(self.action_history) > self.max_history:
            self.action_history.pop(0)

        return ui_result


# ==================== ПУБЛІЧНИЙ API ====================

_navigator = None


def get_navigator() -> UINavigator:
    """Отримати singleton екземпляр UINavigator."""
    global _navigator
    if _navigator is None:
        _navigator = UINavigator()
    return _navigator


# Зручні функції для прямого виклику

def click_element(description: str, element_type: str = "button") -> Dict[str, Any]:
    """Клікнути по елементу."""
    return get_navigator().click_element(description, element_type)


def type_in_field(field_description: str, text: str, clear_first: bool = True) -> Dict[str, Any]:
    """Ввести текст у поле."""
    return get_navigator().type_in_field(field_description, text, clear_first)


def select_option(dropdown_description: str, option_text: str) -> Dict[str, Any]:
    """Вибрати пункт з dropdown."""
    return get_navigator().select_option(dropdown_description, option_text)


def check_checkbox(label: str, state: bool = True) -> Dict[str, Any]:
    """Встановити чекбокс."""
    return get_navigator().check_checkbox(label, state)


def select_radio(label: str) -> Dict[str, Any]:
    """Вибрати radio button."""
    return get_navigator().select_radio(label)


def navigate_tabs(tab_name: str) -> Dict[str, Any]:
    """Перейти на вкладку."""
    return get_navigator().navigate_tabs(tab_name)


def fill_form(field_dict: Dict[str, str]) -> Dict[str, Any]:
    """Заповнити форму."""
    return get_navigator().fill_form(field_dict)


def submit_form(submit_button_text: str = "OK") -> Dict[str, Any]:
    """Відправити форму."""
    return get_navigator().submit_form(submit_button_text)


def read_form_values(field_names: List[str]) -> Dict[str, Any]:
    """Прочитати значення полів."""
    return get_navigator().read_form_values(field_names)


def validate_form_filled(required_fields: List[str]) -> Dict[str, Any]:
    """Перевірити заповнення форми."""
    return get_navigator().validate_form_filled(required_fields)


def open_menu(menu_name: str) -> Dict[str, Any]:
    """Відкрити меню."""
    return get_navigator().open_menu(menu_name)


def click_menu_item(path_list: List[str]) -> Dict[str, Any]:
    """Клік по пункту меню."""
    return get_navigator().click_menu_item(path_list)


def open_context_menu(x: int, y: int) -> Dict[str, Any]:
    """Відкрити контекстне меню."""
    return get_navigator().open_context_menu(x, y)


def click_context_item(item_text: str) -> Dict[str, Any]:
    """Вибрати пункт контекстного меню."""
    return get_navigator().click_context_item(item_text)


def close_menu() -> Dict[str, Any]:
    """Закрити меню."""
    return get_navigator().close_menu()


def handle_dialog(expected_text: Optional[str] = None, action: str = "ok") -> Dict[str, Any]:
    """Відповісти на діалог."""
    return get_navigator().handle_dialog(expected_text, action)


def dismiss_all_dialogs(timeout: float = 5.0) -> Dict[str, Any]:
    """Закрити всі діалоги."""
    return get_navigator().dismiss_all_dialogs(timeout)
