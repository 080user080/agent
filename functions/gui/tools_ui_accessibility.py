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

    def get_children(self, element: UIElement, max_depth: int = 1) -> List[UIElement]:
        """Отримати дочірні елементи (рекурсивно до max_depth)."""
        if not self._available or not element or max_depth < 1:
            return []

        try:
            if self._backend == "uiautomation":
                # Повертаємо порожній список для MVP — потребує зберігання uiautomation об'єкта в UIElement
                # Повноцінна реалізація потребує зберігання посилання на uiautomation Control
                return []
            else:  # pywinauto fallback
                return []
        except Exception as e:
            logger.error("get_children error: %s", e)
            return []

    def get_ui_tree(self, hwnd: Optional[int] = None, depth: int = 3) -> Optional[Dict[str, Any]]:
        """Отримати UIA-дерево для вікна (JSON-friendly для LLM).

        Args:
            hwnd: HWND вікна (опційно, якщо None — активне вікно)
            depth: Глибина обходу дерева (за замовчуванням 3)

        Returns:
            Dict з деревом елементів або None при помилці.
        """
        if not self._available:
            return None

        try:
            if self._backend == "uiautomation":
                from uiautomation import GetFocusedControl, FindControl, TreeScope, ControlType

                # Якщо hwnd не задано — беремо фокований елемент або його вікно
                if hwnd is None:
                    try:
                        elem = GetFocusedElement()
                        if elem:
                            root = elem.GetParentControl()
                            # Піднімаємося до Window
                            while root and root.ControlTypeName != "Window":
                                root = root.GetParentControl()
                                if not root:
                                    break
                            if not root:
                                root = elem
                        else:
                            root = self._root
                    except Exception:
                        root = self._root
                else:
                    # TODO: реалізувати пошук вікна за hwnd через pywinauto/win32gui
                    root = self._root

                if not root:
                    return None

                def _build_tree(node, current_depth: int) -> Dict[str, Any]:
                    if node is None or current_depth > depth:
                        return None
                    try:
                        rect = node.BoundingRectangle
                        tree_node = {
                            "name": node.Name or "",
                            "control_type": ControlType.ToString(node.ControlTypeName),
                            "automation_id": node.AutomationId or "",
                            "class_name": node.ClassName or "",
                            "rect": {"left": rect.left, "top": rect.top, "width": rect.width(), "height": rect.height()},
                            "is_enabled": node.IsEnabled,
                            "is_visible": node.IsOffscreen is False,
                        }
                        if current_depth < depth:
                            children = []
                            try:
                                for child in node.GetChildren():
                                    child_tree = _build_tree(child, current_depth + 1)
                                    if child_tree:
                                        children.append(child_tree)
                            except Exception:
                                pass
                            if children:
                                tree_node["children"] = children[:20]  # Обмежуємо кількість дітей
                        return tree_node
                    except Exception:
                        return None

                return _build_tree(root, 0)
            else:  # pywinauto fallback — обмежена реалізація
                return {"backend": "pywinauto", "note": "full tree not implemented for fallback"}
        except Exception as e:
            logger.error("get_ui_tree error: %s", e)
            return None

    def list_all_buttons(self, root: Optional[UIElement] = None, max_count: int = 50) -> List[UIElement]:
        """Отримати список всіх кнопок у вікні/дереві."""
        if not self._available:
            return []

        try:
            if self._backend == "uiautomation":
                from uiautomation import FindControl, TreeScope, ControlType

                base = self._root if root is None else None
                # Для MVP використовуємо FindControl з lambda
                buttons = []
                try:
                    # uiautomation не має простого API для перебору всіх елементів
                    # Використовуємо FindControl з порожнім фільтром (не ідеально)
                    # Повноцінна реалізація потребує перебору через GetChildren()
                    pass
                except Exception:
                    pass
                return buttons
            else:  # pywinauto fallback
                return []
        except Exception as e:
            logger.error("list_all_buttons error: %s", e)
            return []

    def list_all_inputs(self, root: Optional[UIElement] = None, max_count: int = 50) -> List[UIElement]:
        """Отримати список всіх полів вводу (Edit, ComboBox) у вікні/дереві."""
        if not self._available:
            return []

        try:
            if self._backend == "uiautomation":
                # Аналогічно list_all_buttons — потребує повноцінної реалізації
                return []
            else:  # pywinauto fallback
                return []
        except Exception as e:
            logger.error("list_all_inputs error: %s", e)
            return []

    def list_all_checkboxes(self, root: Optional[UIElement] = None, max_count: int = 50) -> List[UIElement]:
        """Отримати список всіх чекбоксів у вікні/дереві."""
        if not self._available:
            return []

        try:
            if self._backend == "uiautomation":
                # Аналогічно list_all_buttons — потребує повноцінної реалізації
                return []
            else:  # pywinauto fallback
                return []
        except Exception as e:
            logger.error("list_all_checkboxes error: %s", e)
            return []

    def get_value(self, element: UIElement) -> Dict[str, Any]:
        """Отримати значення елемента (наприклад текст у полі вводу)."""
        if not self._available or not element:
            return {"ok": False, "error": "UIA недоступний або елемент None"}

        try:
            if self._backend == "uiautomation":
                # Для MVP — повертаємо name (для багатьох елементів це те саме що value)
                # Повноцінна реалізація потребує ValuePattern
                return {"ok": True, "value": element.name}
            else:  # pywinauto fallback
                return {"ok": True, "value": element.name}
        except Exception as e:
            logger.error("get_value error: %s", e)
            return {"ok": False, "error": str(e)}

    def wait_for_element(self, name: str, timeout: float = 10.0, poll_interval: float = 0.5) -> Optional[UIElement]:
        """Чекати появи елемента за іменем.

        Args:
            name: Ім'я елемента
            timeout: Максимальний час очікування (секунди)
            poll_interval: Інтервал перевірки (секунди)

        Returns:
            UIElement якщо знайдено, None якщо timeout.
        """
        import time

        if not self._available:
            return None

        start = time.time()
        while time.time() - start < timeout:
            elem = self.find_element_by_name(name)
            if elem:
                return elem
            time.sleep(poll_interval)
        return None

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
        args: {"window_title": "optional window title", "max_count": 50}

    Returns:
        {"ok": bool, "elements": [...], "count": int, "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    max_count = int(args.get("max_count", 50))

    try:
        # Використовуємо get_ui_tree для отримання дерева
        tree = wrapper.get_ui_tree(depth=2)
        if not tree:
            return {"ok": True, "elements": [], "count": 0}

        # Екстрагуємо елементи з дерева
        elements = []

        def _extract_from_tree(node, depth=0):
            if not node or depth > 2:
                return
            elements.append({
                "name": node.get("name", ""),
                "control_type": node.get("control_type", ""),
                "automation_id": node.get("automation_id", ""),
                "rect": node.get("rect", {}),
                "is_enabled": node.get("is_enabled", True),
                "is_visible": node.get("is_visible", True),
            })
            for child in node.get("children", [])[:10]:  # Обмежуємо дітей
                _extract_from_tree(child, depth + 1)

        _extract_from_tree(tree)
        return {"ok": True, "elements": elements[:max_count], "count": len(elements)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def uia_find_button(args: Dict[str, Any]) -> Dict[str, Any]:
    """Знайти кнопку за іменем або automation_id.

    Args:
        args: {"name": "button name", "automation_id": "...", "window_title": "optional"}

    Returns:
        {"ok": bool, "element": {...}, "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    name = args.get("name", "")
    automation_id = args.get("automation_id", "")

    if not name and not automation_id:
        return {"ok": False, "error": "name або automation_id required"}

    try:
        if automation_id:
            elem = wrapper.find_element_by_automation_id(automation_id)
        else:
            elem = wrapper.find_element_by_name(name)

        if elem:
            return {"ok": True, "element": elem.__dict__}
        return {"ok": False, "error": "Element not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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

    name = args.get("name", "")
    automation_id = args.get("automation_id", "")

    if not name and not automation_id:
        return {"ok": False, "error": "name або automation_id required"}

    try:
        if automation_id:
            elem = wrapper.find_element_by_automation_id(automation_id)
        else:
            elem = wrapper.find_element_by_name(name)

        if elem:
            result = wrapper.click_element(elem)
            return result
        return {"ok": False, "error": "Element not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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

    name = args.get("name", "")
    automation_id = args.get("automation_id", "")

    if not name and not automation_id:
        return {"ok": False, "error": "name або automation_id required"}

    try:
        if automation_id:
            elem = wrapper.find_element_by_automation_id(automation_id)
        else:
            elem = wrapper.find_element_by_name(name)

        if elem:
            result = wrapper.set_text(elem, text)
            return result
        return {"ok": False, "error": "Element not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def uia_get_value(args: Dict[str, Any]) -> Dict[str, Any]:
    """Отримати значення елемента.

    Args:
        args: {"automation_id": "..."} або {"name": "..."}

    Returns:
        {"ok": bool, "value": "...", "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    name = args.get("name", "")
    automation_id = args.get("automation_id", "")

    if not name and not automation_id:
        return {"ok": False, "error": "name або automation_id required"}

    try:
        if automation_id:
            elem = wrapper.find_element_by_automation_id(automation_id)
        else:
            elem = wrapper.find_element_by_name(name)

        if elem:
            result = wrapper.get_value(elem)
            return result
        return {"ok": False, "error": "Element not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def uia_wait_for_element(args: Dict[str, Any]) -> Dict[str, Any]:
    """Чекати появи елемента за іменем.

    Args:
        args: {"name": "...", "timeout": 10.0, "poll_interval": 0.5}

    Returns:
        {"ok": bool, "element": {...}, "error": "..."}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    name = args.get("name", "")
    if not name:
        return {"ok": False, "error": "name required"}

    timeout = float(args.get("timeout", 10.0))
    poll_interval = float(args.get("poll_interval", 0.5))

    try:
        elem = wrapper.wait_for_element(name, timeout, poll_interval)
        if elem:
            return {"ok": True, "element": elem.__dict__}
        return {"ok": False, "error": f"Element not found within {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def uia_list_buttons(args: Dict[str, Any]) -> Dict[str, Any]:
    """Отримати список всіх кнопок в активному вікні.

    Args:
        args: {"max_count": 50}

    Returns:
        {"ok": bool, "buttons": [...], "count": int}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    max_count = int(args.get("max_count", 50))

    try:
        buttons = wrapper.list_all_buttons(max_count=max_count)
        return {"ok": True, "buttons": [b.__dict__ for b in buttons], "count": len(buttons)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def uia_list_inputs(args: Dict[str, Any]) -> Dict[str, Any]:
    """Отримати список всіх полів вводу в активному вікні.

    Args:
        args: {"max_count": 50}

    Returns:
        {"ok": bool, "inputs": [...], "count": int}
    """
    wrapper = get_uia_wrapper()
    if not wrapper.is_available():
        return {"ok": False, "error": "UIA недоступний"}

    max_count = int(args.get("max_count", 50))

    try:
        inputs = wrapper.list_all_inputs(max_count=max_count)
        return {"ok": True, "inputs": [i.__dict__ for i in inputs], "count": len(inputs)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
