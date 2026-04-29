"""Windows UI Automation (UIA) tools — стійкий UI-контроль (V1).

Це Phase V1 — базовий wrapper для Windows Accessibility API.
Дозволяє агенту бачити структуру UI (кнопки, поля, меню) замість лише пікселів.

Бекенди:
- uiautomation (основний) — швидкий, глибокий доступ для складних агентів
- pywinauto (fallback) — для старих Win32 додатків
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ui_accessibility")

try:
    from uiautomation import ControlType
except ImportError:
    # Fallback якщо uiautomation не встановлено
    ControlType = None


@dataclass
class UIElement:
    """Елемент UI з Accessibility API."""
    name: str
    control_type: str  # Button, Edit, Window, etc.
    automation_id: str = ""
    class_name: str = ""
    rect: Dict[str, int] = None  # {"left": x, "top": y, "width": w, "height": h}
    is_enabled: bool = True
    is_visible: bool = True
    children: List["UIElement"] = None
    parent: Optional["UIElement"] = None

    def __post_init__(self):
        if self.rect is None:
            self.rect = {}
        if self.children is None:
            self.children = []


class UIAWrapper:
    """Wrapper для Windows UI Automation API.

    MVP — базовий інтерфейс, який можна розширити з pywinauto або IUIAutomation.
    """

    def __init__(self):
        self._available = False
        self._init_uia()

    def _init_uia(self):
        """Ініціалізувати UIA з uiautomation (основний) + pywinauto fallback."""
        try:
            # Спробуємо uiautomation як основний
            from uiautomation import GetRootControl

            # uiautomation має вбудовану підтримку COM ініціалізації
            # Якщо не працює в потоці, треба використовувати UIAutomationInitializerInThread
            self._root = GetRootControl()
            self._backend = "uiautomation"
            self._available = True
            logger.info("UIA initialized with uiautomation")
        except ImportError:
            logger.warning("uiautomation not installed - trying pywinauto fallback")
            try:
                from pywinauto import Desktop

                self._desktop = Desktop(backend="uia")
                self._backend = "pywinauto"
                self._available = True
                logger.info("UIA initialized with pywinauto fallback")
            except ImportError:
                logger.warning("pywinauto not installed - UIA unavailable")
                self._available = False
            except Exception as e:
                logger.warning("pywinauto fallback failed: %s", e)
                self._available = False
        except Exception as e:
            logger.warning("uiautomation initialization failed: %s", e)
            self._available = False

    def is_available(self) -> bool:
        """Перевірити чи UIA доступний."""
        return self._available

    def get_root_element(self) -> Optional[UIElement]:
        """Отримати кореневий елемент (desktop)."""
        if not self._available:
            return None

        try:
            if self._backend == "uiautomation":
                root = self._root
                rect = root.BoundingRectangle
                return UIElement(
                    name=root.Name,
                    control_type=ControlType.ToString(root.ControlTypeName),
                    automation_id=root.AutomationId,
                    class_name=root.ClassName,
                    rect={"left": rect.left, "top": rect.top, "width": rect.width(), "height": rect.height()},
                    is_enabled=True,
                    is_visible=True,
                )
            else:  # pywinauto fallback
                desktop = self._desktop
                return UIElement(
                    name="Desktop",
                    control_type="Desktop",
                    automation_id="",
                    class_name="",
                    rect={},
                    is_enabled=True,
                    is_visible=True,
                )
        except Exception as e:
            logger.error("get_root_element error: %s", e)
            return None

    def get_focused_element(self) -> Optional[UIElement]:
        """Отримати фокований елемент."""
        if not self._available:
            return None

        try:
            if self._backend == "uiautomation":
                from uiautomation import GetFocusedElement

                elem = GetFocusedElement()
                if elem:
                    rect = elem.BoundingRectangle
                    return UIElement(
                        name=elem.Name,
                        control_type=ControlType.ToString(elem.ControlTypeName),
                        automation_id=elem.AutomationId,
                        class_name=elem.ClassName,
                        rect={"left": rect.left, "top": rect.top, "width": rect.width(), "height": rect.height()},
                        is_enabled=elem.IsEnabled,
                        is_visible=elem.IsOffscreen is False,
                    )
            # pywinauto fallback не підтримує get_focused_element
            return None
        except Exception as e:
            logger.error("get_focused_element error: %s", e)
            return None

    def find_element_by_name(self, name: str, root: Optional[UIElement] = None) -> Optional[UIElement]:
        """Знайти елемент за іменем."""
        if not self._available:
            return None

        try:
            if self._backend == "uiautomation":
                from uiautomation import FindControl, TreeScope

                elem = FindControl(self._root, lambda c: name.lower() in c.Name.lower(), TreeScope.Descendants)
                if elem:
                    rect = elem.BoundingRectangle
                    return UIElement(
                        name=elem.Name,
                        control_type=ControlType.ToString(elem.ControlTypeName),
                        automation_id=elem.AutomationId,
                        class_name=elem.ClassName,
                        rect={"left": rect.left, "top": rect.top, "width": rect.width(), "height": rect.height()},
                        is_enabled=elem.IsEnabled,
                        is_visible=elem.IsOffscreen is False,
                    )
            else:  # pywinauto fallback
                for window in self._desktop.windows():
                    if name.lower() in window.window_text().lower():
                        rect = window.rectangle()
                        return UIElement(
                            name=window.window_text(),
                            control_type="Window",
                            automation_id="",
                            class_name=window.class_name(),
                            rect={"left": rect.left, "top": rect.top, "width": rect.width(), "height": rect.height()},
                            is_enabled=True,
                            is_visible=True,
                        )
            return None
        except Exception as e:
            logger.error("find_element_by_name error: %s", e)
            return None

    def find_element_by_automation_id(self, automation_id: str, root: Optional[UIElement] = None) -> Optional[UIElement]:
        """Знайти елемент за AutomationId."""
        if not self._available:
            return None

        try:
            if self._backend == "uiautomation":
                from uiautomation import FindControl, TreeScope

                elem = FindControl(self._root, lambda c: c.AutomationId == automation_id, TreeScope.Descendants)
                if elem:
                    rect = elem.BoundingRectangle
                    return UIElement(
                        name=elem.Name,
                        control_type=ControlType.ToString(elem.ControlTypeName),
                        automation_id=elem.AutomationId,
                        class_name=elem.ClassName,
                        rect={"left": rect.left, "top": rect.top, "width": rect.width(), "height": rect.height()},
                        is_enabled=elem.IsEnabled,
                        is_visible=elem.IsOffscreen is False,
                    )
            else:  # pywinauto fallback
                for window in self._desktop.windows():
                    try:
                        element = window.descendants(auto_id=automation_id)
                        if element:
                            elem = element[0]
                            rect = elem.rectangle()
                            return UIElement(
                                name=elem.window_text(),
                                control_type=elem.element_info.control_type,
                                automation_id=elem.element_info.automation_id,
                                class_name=elem.element_info.class_name,
                                rect={"left": rect.left, "top": rect.top, "width": rect.width(), "height": rect.height()},
                                is_enabled=elem.is_enabled(),
                                is_visible=elem.is_visible(),
                            )
                    except Exception:
                        continue
            return None
        except Exception as e:
            logger.error("find_element_by_automation_id error: %s", e)
            return None

    def get_children(self, element: UIElement) -> List[UIElement]:
        """Отримати дочірні елементи."""
        if not self._available or not element:
            return []

        try:
            if self._backend == "uiautomation":
                # Для MVP повертаємо порожній список — потребує зберігання uiautomation об'єкта в UIElement
                return []
            else:  # pywinauto fallback
                return []
        except Exception as e:
            logger.error("get_children error: %s", e)
            return []

    def click_element(self, element: UIElement) -> Dict[str, Any]:
        """Клікнути на елемент через UIA (більш надійно ніж пікселі)."""
        if not self._available or not element:
            return {"ok": False, "error": "UIA недоступний або елемент None"}

        try:
            if self._backend == "uiautomation":
                # Для MVP використовуємо fallback на pyautogui через rect coordinates
                # Реалізація через uiautomation Click() потребує зберігання об'єкта в UIElement
                import pyautogui

                rect = element.rect
                if rect and "left" in rect and "top" in rect:
                    x = rect["left"] + rect.get("width", 0) // 2
                    y = rect["top"] + rect.get("height", 0) // 2
                    pyautogui.click(x, y)
                    return {"ok": True, "result": f"clicked at ({x}, {y})"}
                return {"ok": False, "error": "No rect coordinates"}
            else:  # pywinauto fallback
                import pyautogui

                rect = element.rect
                if rect and "left" in rect and "top" in rect:
                    x = rect["left"] + rect.get("width", 0) // 2
                    y = rect["top"] + rect.get("height", 0) // 2
                    pyautogui.click(x, y)
                    return {"ok": True, "result": f"clicked at ({x}, {y})"}
                return {"ok": False, "error": "No rect coordinates"}
        except Exception as e:
            logger.error("click_element error: %s", e)
            return {"ok": False, "error": str(e)}

    def set_text(self, element: UIElement, text: str) -> Dict[str, Any]:
        """Встановити текст в елемент (Edit, ComboBox тощо)."""
        if not self._available or not element:
            return {"ok": False, "error": "UIA недоступний або елемент None"}

        try:
            if self._backend == "uiautomation":
                # Для MVP використовуємо fallback на pyperclip + Ctrl+V через rect coordinates
                # Реалізація через uiautomation ValuePattern потребує зберігання об'єкта в UIElement
                import pyperclip
                import pyautogui

                rect = element.rect
                if rect and "left" in rect and "top" in rect:
                    x = rect["left"] + rect.get("width", 0) // 2
                    y = rect["top"] + rect.get("height", 0) // 2
                    pyautogui.click(x, y)
                    pyperclip.copy(text)
                    pyautogui.hotkey("ctrl", "v")
                    return {"ok": True, "result": f"text set to {text}"}
                return {"ok": False, "error": "No rect coordinates"}
            else:  # pywinauto fallback
                import pyperclip
                import pyautogui

                rect = element.rect
                if rect and "left" in rect and "top" in rect:
                    x = rect["left"] + rect.get("width", 0) // 2
                    y = rect["top"] + rect.get("height", 0) // 2
                    pyautogui.click(x, y)
                    pyperclip.copy(text)
                    pyautogui.hotkey("ctrl", "v")
                    return {"ok": True, "result": f"text set to {text}"}
                return {"ok": False, "error": "No rect coordinates"}
        except Exception as e:
            logger.error("set_text error: %s", e)
            return {"ok": False, "error": str(e)}


# ─── Singleton instance ────────────────────────────────────────────────────────

_uia_instance: Optional[UIAWrapper] = None


def get_uia_wrapper() -> UIAWrapper:
    """Отримати singleton UIA wrapper."""
    global _uia_instance
    if _uia_instance is None:
        _uia_instance = UIAWrapper()
    return _uia_instance


# ─── LLM tools ─────────────────────────────────────────────────────────────────

def uia_list_elements(args: Dict[str, Any]) -> Dict[str, Any]:
    """Отримати список UI елементів з активного вікна.

    Args:
        args: {"window_title": "optional window title"}

    Returns:
        {"ok": bool, "elements": [...], "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    # TODO: Реалізація
    return {"ok": True, "elements": [], "count": 0}


def uia_find_button(args: Dict[str, Any]) -> Dict[str, Any]:
    """Знайти кнопку за іменем.

    Args:
        args: {"name": "button name", "window_title": "optional"}

    Returns:
        {"ok": bool, "element": {...}, "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    name = args.get("name", "")
    if not name:
        return {"ok": False, "error": "name required"}

    # TODO: Реалізація
    return {"ok": False, "error": "Not implemented yet"}


def uia_click_element(args: Dict[str, Any]) -> Dict[str, Any]:
    """Клікнути на UI елемент через Accessibility API.

    Args:
        args: {"automation_id": "..."} або {"name": "..."}

    Returns:
        {"ok": bool, "result": "...", "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    # TODO: Реалізація
    return {"ok": False, "error": "Not implemented yet"}


def uia_set_text(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ввести текст в поле через UIA.

    Args:
        args: {"automation_id": "...", "text": "..."} або {"name": "...", "text": "..."}

    Returns:
        {"ok": bool, "result": "...", "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    text = args.get("text", "")
    if not text:
        return {"ok": False, "error": "text required"}

    # TODO: Реалізація
    return {"ok": False, "error": "Not implemented yet"}


def uia_get_focused_element(args: Dict[str, Any]) -> Dict[str, Any]:
    """Отримати фокований елемент.

    Returns:
        {"ok": bool, "element": {...}, "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    element = wrapper.get_focused_element()
    if element:
        return {"ok": True, "element": element.__dict__}
    return {"ok": False, "error": "No focused element"}
