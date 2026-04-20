"""
Система відкату дій (Undo Manager).

GUI Automation Phase 6 — можливість відкатити дії агента.
Snapshots стану, undo логіка для різних типів дій.
"""

import json
import time
import os
import shutil
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import threading
import uuid

from .tools_screen_capture import ScreenCapture


@dataclass
class StateSnapshot:
    """Snapshot стану системи."""
    id: str
    timestamp: str
    label: str
    screenshot_path: Optional[str] = None
    clipboard_text: Optional[str] = None
    active_window: Dict[str, Any] = field(default_factory=dict)
    mouse_position: Tuple[int, int] = field(default_factory=lambda: (0, 0))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UndoAction:
    """Опис зворотної дії."""
    original_action: str
    undo_function: str
    undo_params: Dict[str, Any] = field(default_factory=dict)
    reversible: bool = True
    irreversible_reason: Optional[str] = None


@dataclass
class UndoResult:
    """Результат undo операції."""
    success: bool
    action_undone: str
    message: str
    error: Optional[str] = None


class UndoManager:
    """
    Менеджер відкату дій.
    Зберігає snapshots та виконує undo операції.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, snapshots_dir: str = "logs/snapshots"):
        if self._initialized:
            return

        self._initialized = True
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        # Історія undoable дій
        self._undo_stack: List[UndoAction] = []
        self._max_stack_size = 50

        # Snapshots
        self._snapshots: Dict[str, StateSnapshot] = {}
        self._max_snapshots = 10

        # Undo handlers для різних типів дій
        self._undo_handlers: Dict[str, Callable] = {
            "mouse_click": self._undo_mouse_click,
            "keyboard_type": self._undo_keyboard_type,
            "file_move": self._undo_file_move,
            "file_delete": self._undo_file_delete,
            "window_close": self._undo_window_close,
            "fill_form": self._undo_fill_form,
        }

        # Screen capture для скріншотів
        self._screen = ScreenCapture()

        # Блокування
        self._lock = threading.Lock()

    # ==================== SNAPSHOTS ====================

    def save_snapshot(self, label: str = "") -> Dict[str, Any]:
        """
        Зберегти поточний стан.

        Args:
            label: Опис snapshot

        Returns:
            {"success": bool, "snapshot_id": str, "path": str}
        """
        try:
            snapshot_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().isoformat()

            # Скріншот
            screenshot_path = str(self.snapshots_dir / f"snapshot_{snapshot_id}.png")
            try:
                self._screen.take_screenshot(screenshot_path)
            except Exception as e:
                screenshot_path = None
                print(f"[UndoManager] Screenshot error: {e}")

            # Кліпборд
            clipboard_text = None
            try:
                from .tools_mouse_keyboard import clipboard_get_text
                clipboard_text = clipboard_get_text()
            except:
                pass

            # Активне вікно
            active_window = {}
            try:
                from .tools_window_manager import get_active_window
                active_window = get_active_window()
            except:
                pass

            # Позиція миші
            mouse_pos = (0, 0)
            try:
                import pyautogui
                mouse_pos = pyautogui.position()
            except:
                pass

            # Створюємо snapshot
            snapshot = StateSnapshot(
                id=snapshot_id,
                timestamp=timestamp,
                label=label or f"Snapshot {timestamp}",
                screenshot_path=screenshot_path,
                clipboard_text=clipboard_text,
                active_window=active_window,
                mouse_position=mouse_pos,
                metadata={
                    "created_by": "UndoManager",
                    "system_time": time.time()
                }
            )

            # Зберігаємо
            with self._lock:
                self._snapshots[snapshot_id] = snapshot

                # Обмежуємо кількість
                if len(self._snapshots) > self._max_snapshots:
                    oldest = min(self._snapshots.keys(),
                               key=lambda k: self._snapshots[k].timestamp)
                    old_snapshot = self._snapshots.pop(oldest)
                    # Видаляємо файл скріншоту
                    if old_snapshot.screenshot_path and os.path.exists(old_snapshot.screenshot_path):
                        try:
                            os.remove(old_snapshot.screenshot_path)
                        except:
                            pass

            # Зберігаємо в файл
            snapshot_file = self.snapshots_dir / f"snapshot_{snapshot_id}.json"
            with open(snapshot_file, "w", encoding="utf-8") as f:
                json.dump({
                    "id": snapshot.id,
                    "timestamp": snapshot.timestamp,
                    "label": snapshot.label,
                    "screenshot_path": snapshot.screenshot_path,
                    "clipboard_text": snapshot.clipboard_text,
                    "active_window": snapshot.active_window,
                    "mouse_position": snapshot.mouse_position,
                    "metadata": snapshot.metadata
                }, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "snapshot_id": snapshot_id,
                "path": str(snapshot_file),
                "message": f"Snapshot '{label}' збережено"
            }

        except Exception as e:
            return {
                "success": False,
                "snapshot_id": None,
                "path": None,
                "message": f"Помилка збереження: {str(e)}",
                "error": str(e)
            }

    def restore_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """
        Відновити стан з snapshot.

        Args:
            snapshot_id: ID snapshot

        Returns:
            {"success": bool, "message": str}
        """
        try:
            with self._lock:
                snapshot = self._snapshots.get(snapshot_id)

            if not snapshot:
                # Спробуємо завантажити з файлу
                snapshot_file = self.snapshots_dir / f"snapshot_{snapshot_id}.json"
                if snapshot_file.exists():
                    with open(snapshot_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        snapshot = StateSnapshot(**data)
                else:
                    return {
                        "success": False,
                        "message": f"Snapshot {snapshot_id} не знайдено"
                    }

            # Відновлюємо кліпборд
            if snapshot.clipboard_text:
                try:
                    from .tools_mouse_keyboard import clipboard_copy_text
                    clipboard_copy_text(snapshot.clipboard_text)
                except Exception as e:
                    print(f"[UndoManager] Clipboard restore error: {e}")

            # Відновлюємо позицію миші
            if snapshot.mouse_position:
                try:
                    import pyautogui
                    pyautogui.moveTo(snapshot.mouse_position[0], snapshot.mouse_position[1])
                except Exception as e:
                    print(f"[UndoManager] Mouse restore error: {e}")

            # Активне вікно
            if snapshot.active_window.get("hwnd"):
                try:
                    from .tools_window_manager import activate_window
                    activate_window(snapshot.active_window["hwnd"])
                except Exception as e:
                    print(f"[UndoManager] Window restore error: {e}")

            return {
                "success": True,
                "message": f"Snapshot '{snapshot.label}' відновлено",
                "restored_elements": ["clipboard", "mouse_position", "active_window"]
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Помилка відновлення: {str(e)}",
                "error": str(e)
            }

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """
        Отримати список доступних snapshots.

        Returns:
            [{"id", "label", "timestamp"}]
        """
        try:
            snapshots = []
            for snapshot_id, snapshot in self._snapshots.items():
                snapshots.append({
                    "id": snapshot.id,
                    "label": snapshot.label,
                    "timestamp": snapshot.timestamp,
                    "has_screenshot": snapshot.screenshot_path is not None,
                    "has_clipboard": snapshot.clipboard_text is not None
                })

            return sorted(snapshots, key=lambda x: x["timestamp"], reverse=True)

        except Exception as e:
            return [{"error": str(e)}]

    # ==================== UNDO ЛОГІКА ====================

    def register_undoable(
        self,
        action: str,
        undo_fn: Callable,
        reversible: bool = True,
        irreversible_reason: Optional[str] = None
    ):
        """
        Зареєструвати undo handler для типу дії.

        Args:
            action: Тип дії
            undo_fn: Функція undo
            reversible: Чи можна відкатити
            irreversible_reason: Причина якщо не можна
        """
        self._undo_handlers[action] = undo_fn

    def undo_last(self, count: int = 1) -> Dict[str, Any]:
        """
        Відкатити останні N дій.

        Args:
            count: Кількість дій для undo

        Returns:
            {"success": bool, "actions_undone": int, "errors": [str]}
        """
        undone = 0
        errors = []

        with self._lock:
            for _ in range(count):
                if not self._undo_stack:
                    break

                action = self._undo_stack.pop()

                if not action.reversible:
                    errors.append(f"{action.original_action}: {action.irreversible_reason}")
                    continue

                try:
                    handler = self._undo_handlers.get(action.original_action)
                    if handler:
                        result = handler(action.undo_params)
                        if result.get("success"):
                            undone += 1
                        else:
                            errors.append(f"{action.original_action}: {result.get('message', 'Unknown error')}")
                    else:
                        errors.append(f"{action.original_action}: Немає undo handler")
                except Exception as e:
                    errors.append(f"{action.original_action}: {str(e)}")

        return {
            "success": undone > 0,
            "actions_undone": undone,
            "requested": count,
            "errors": errors,
            "message": f"Відкатано {undone}/{count} дій"
        }

    def undo_to_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """
        Відкатити до конкретного snapshot.

        Args:
            snapshot_id: ID snapshot

        Returns:
            {"success": bool, "message": str}
        """
        return self.restore_snapshot(snapshot_id)

    def add_to_undo_stack(
        self,
        action: str,
        params: Dict[str, Any],
        reversible: bool = True,
        irreversible_reason: Optional[str] = None
    ):
        """
        Додати дію в undo stack.

        Args:
            action: Тип дії
            params: Параметри для undo
            reversible: Чи можна відкатити
            irreversible_reason: Причина якщо не можна
        """
        undo_action = UndoAction(
            original_action=action,
            undo_function=f"_undo_{action}",
            undo_params=params,
            reversible=reversible,
            irreversible_reason=irreversible_reason
        )

        with self._lock:
            self._undo_stack.append(undo_action)
            if len(self._undo_stack) > self._max_stack_size:
                self._undo_stack.pop(0)

    def clear_undo_stack(self):
        """Очистити undo stack."""
        with self._lock:
            self._undo_stack.clear()

    def get_undo_stack(self) -> List[Dict[str, Any]]:
        """
        Отримати поточний undo stack.

        Returns:
            Список undo actions
        """
        return [
            {
                "original_action": a.original_action,
                "reversible": a.reversible,
                "irreversible_reason": a.irreversible_reason
            }
            for a in self._undo_stack
        ]

    # ==================== UNDO HANDLERS ====================

    def _undo_mouse_click(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Undo для кліку миші — просто інформуємо."""
        return {
            "success": True,
            "message": "Клік не можна 'відкатити', але це безпечна дія",
            "note": "Undo для кліку — інформаційний"
        }

    def _undo_keyboard_type(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Undo для введення тексту — видаляємо текст."""
        try:
            text = params.get("text", "")
            field = params.get("field", "")

            # Видаляємо введений текст
            if text:
                # Клік по полю
                from .logic_ui_navigator import click_element
                click_element(field, "input")

                # Видаляємо текст
                from .tools_mouse_keyboard import keyboard_hotkey
                keyboard_hotkey("ctrl", "a")
                time.sleep(0.1)

                # Можна видалити або відновити попереднє значення
                # Тут просто видаляємо
                from .tools_mouse_keyboard import keyboard_press
                keyboard_press("delete")

            return {
                "success": True,
                "message": f"Текст у полі '{field}' видалено"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Помилка undo type: {str(e)}",
                "error": str(e)
            }

    def _undo_file_move(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Undo для переміщення файлу — повертаємо назад."""
        try:
            src = params.get("source_path")
            dst = params.get("destination_path")

            if src and dst and os.path.exists(dst):
                shutil.move(dst, src)
                return {
                    "success": True,
                    "message": f"Файл повернуто: {dst} → {src}"
                }

            return {
                "success": False,
                "message": "Не вдалося відновити файл — файл не знайдено"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Помилка undo move: {str(e)}",
                "error": str(e)
            }

    def _undo_file_delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Undo для видалення файлу — відновлюємо з кошика або backup."""
        # Відновлення з кошика Windows — складна операція
        # Потребує COM або спеціальних утиліт
        return {
            "success": False,
            "message": "Undo для видалення файлу не реалізовано — перевірте Кошик вручну",
            "note": "Файли видалені без кошика не можна відновити"
        }

    def _undo_window_close(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Undo для закриття вікна — відкриваємо заново."""
        try:
            app_name = params.get("application", "")
            exe_path = params.get("exe_path", "")

            if exe_path and os.path.exists(exe_path):
                import subprocess
                subprocess.Popen(exe_path)
                return {
                    "success": True,
                    "message": f"Програму {app_name} перезапущено"
                }

            return {
                "success": False,
                "message": f"Не вдалося перезапустити {app_name} — шлях не знайдено"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Помилка undo close: {str(e)}",
                "error": str(e)
            }

    def _undo_fill_form(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Undo для заповнення форми — очищаємо поля."""
        try:
            fields = params.get("fields", [])

            for field in fields:
                from .logic_ui_navigator import click_element, keyboard_hotkey, keyboard_press
                click_element(field, "input")
                time.sleep(0.1)
                keyboard_hotkey("ctrl", "a")
                time.sleep(0.1)
                keyboard_press("delete")

            return {
                "success": True,
                "message": f"Очищено {len(fields)} полів форми"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Помилка undo fill: {str(e)}",
                "error": str(e)
            }


# ==================== ПУБЛІЧНИЙ API ====================

_undo_manager = None


def get_undo_manager() -> UndoManager:
    """Отримати singleton екземпляр UndoManager."""
    global _undo_manager
    if _undo_manager is None:
        _undo_manager = UndoManager()
    return _undo_manager


def save_snapshot(label: str = "") -> Dict[str, Any]:
    """Зберегти snapshot."""
    return get_undo_manager().save_snapshot(label)


def restore_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Відновити snapshot."""
    return get_undo_manager().restore_snapshot(snapshot_id)


def list_snapshots() -> List[Dict[str, Any]]:
    """Список snapshots."""
    return get_undo_manager().list_snapshots()


def undo_last(count: int = 1) -> Dict[str, Any]:
    """Відкатити останні дії."""
    return get_undo_manager().undo_last(count)


def undo_to_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Відкатити до snapshot."""
    return get_undo_manager().undo_to_snapshot(snapshot_id)


def add_to_undo_stack(
    action: str,
    params: Dict[str, Any],
    reversible: bool = True,
    irreversible_reason: Optional[str] = None
):
    """Додати в undo stack."""
    get_undo_manager().add_to_undo_stack(action, params, reversible, irreversible_reason)


def get_undo_stack() -> List[Dict[str, Any]]:
    """Отримати undo stack."""
    return get_undo_manager().get_undo_stack()


def clear_undo_stack():
    """Очистити undo stack."""
    get_undo_manager().clear_undo_stack()


# Контекстний менеджер для snapshot

class SnapshotContext:
    """Контекстний менеджер для автоматичного snapshot."""

    def __init__(self, label: str = ""):
        self.label = label
        self.snapshot_id = None
        self.undo_manager = get_undo_manager()

    def __enter__(self):
        result = self.undo_manager.save_snapshot(self.label)
        if result["success"]:
            self.snapshot_id = result["snapshot_id"]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and self.snapshot_id:
            # Була помилка — відкатуємо
            self.undo_manager.restore_snapshot(self.snapshot_id)
        return False  # Не пригнічуємо виняток

    def restore(self):
        """Відновити snapshot вручну."""
        if self.snapshot_id:
            return self.undo_manager.restore_snapshot(self.snapshot_id)
        return {"success": False, "message": "No snapshot to restore"}
