"""
Керування вікнами Windows через win32 API.

Модуль для GUI Automation Phase 1.
Забезпечує пошук, активацію та керування вікнами Windows.
"""

import time
import re
from typing import Dict, Any, List, Optional, Callable
import psutil

# win32 API
import win32gui
import win32con
import win32process


class WindowManager:
    """Менеджер для роботи з вікнами Windows."""

    def __init__(self):
        self._window_cache = {}  # Кеш для швидкого пошуку

    # ==================== ПОШУК ТА СПИСОК ВІКОН ====================

    def list_windows(self, include_hidden: bool = False) -> List[Dict[str, Any]]:
        """
        Отримати список всіх вікон.

        Args:
            include_hidden: Включати приховані вікна

        Returns:
            [{hwnd, title, process_name, pid, rect, visible}]
        """
        windows = []

        def enum_callback(hwnd, _):
            if not include_hidden and not win32gui.IsWindowVisible(hwnd):
                return

            # Отримуємо заголовок
            title = win32gui.GetWindowText(hwnd)

            # Пропускаємо вікна без заголовка (за бажанням)
            if not title and not include_hidden:
                return

            # Отримуємо процес
            pid = self._get_window_pid(hwnd)
            process_name = self._get_process_name(pid) if pid else "unknown"

            # Отримуємо розміри
            rect = win32gui.GetWindowRect(hwnd)

            windows.append({
                "hwnd": hwnd,
                "title": title,
                "process_name": process_name,
                "pid": pid,
                "rect": {
                    "x": rect[0],
                    "y": rect[1],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1]
                },
                "visible": win32gui.IsWindowVisible(hwnd)
            })

        win32gui.EnumWindows(enum_callback, None)
        return windows

    def find_window_by_title(self, pattern: str, exact: bool = False) -> Optional[int]:
        """
        Знайти вікно за заголовком.

        Args:
            pattern: Текст або regex для пошуку
            exact: Точний збіг (True) або частковий (False)

        Returns:
            hwnd або None
        """
        windows = self.list_windows()

        for win in windows:
            title = win["title"]
            if exact:
                if title == pattern:
                    return win["hwnd"]
            else:
                # Regex або частковий збіг
                try:
                    if re.search(pattern, title, re.IGNORECASE):
                        return win["hwnd"]
                except re.error:
                    # Якщо не валідний regex — шукаємо частковий збіг
                    if pattern.lower() in title.lower():
                        return win["hwnd"]

        return None

    def find_window_by_process(self, process_name: str) -> List[int]:
        """
        Знайти всі вікна процесу.

        Args:
            process_name: Назва процесу (без .exe)

        Returns:
            [hwnd, ...]
        """
        windows = self.list_windows()
        result = []

        for win in windows:
            if win["process_name"].lower() == process_name.lower():
                result.append(win["hwnd"])
            elif win["process_name"].lower().startswith(process_name.lower()):
                result.append(win["hwnd"])

        return result

    def find_window_by_class(self, class_name: str) -> List[int]:
        """
        Знайти вікна за класом Windows.

        Args:
            class_name: Ім'я класу вікна (напр. "Notepad", "Chrome_WidgetWin_1")

        Returns:
            [hwnd, ...]
        """
        result = []

        def enum_callback(hwnd, _):
            try:
                win_class = win32gui.GetClassName(hwnd)
                if win_class == class_name:
                    result.append(hwnd)
            except:
                pass

        win32gui.EnumWindows(enum_callback, None)
        return result

    def get_active_window(self) -> Dict[str, Any]:
        """
        Отримати активне (foreground) вікно.

        Returns:
            {hwnd, title, process_name, rect}
        """
        hwnd = win32gui.GetForegroundWindow()

        if hwnd == 0:
            return {"error": "No active window found"}

        title = win32gui.GetWindowText(hwnd)
        pid = self._get_window_pid(hwnd)
        process_name = self._get_process_name(pid) if pid else "unknown"
        rect = win32gui.GetWindowRect(hwnd)

        return {
            "hwnd": hwnd,
            "title": title,
            "process_name": process_name,
            "pid": pid,
            "rect": {
                "x": rect[0],
                "y": rect[1],
                "width": rect[2] - rect[0],
                "height": rect[3] - rect[1]
            }
        }

    # ==================== КЕРУВАННЯ СТАНОМ ВІКОН ====================

    def activate_window(self, hwnd: int) -> Dict[str, Any]:
        """
        Перевести вікно на передній план (SetForegroundWindow).

        Args:
            hwnd: Handle вікна

        Returns:
            {"success": True, "hwnd": hwnd}
        """
        try:
            # Спочатку відновлюємо, якщо згорнуте
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Для SetForegroundWindow потрібно вікно мати фокус
            # Спочатку отримуємо поточний thread
            current_thread = win32process.GetCurrentThreadId()
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

            # Прикріплюємо input
            win32process.AttachThreadInput(current_thread, target_thread, True)

            # Тепер можемо встановити foreground
            win32gui.SetForegroundWindow(hwnd)

            # Відкріплюємо
            win32process.AttachThreadInput(current_thread, target_thread, False)

            return {"success": True, "hwnd": hwnd}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def minimize_window(self, hwnd: int) -> Dict[str, Any]:
        """Згорнути вікно."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return {"success": True, "hwnd": hwnd, "action": "minimize"}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def maximize_window(self, hwnd: int) -> Dict[str, Any]:
        """Розгорнути вікно на весь екран."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return {"success": True, "hwnd": hwnd, "action": "maximize"}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def restore_window(self, hwnd: int) -> Dict[str, Any]:
        """Відновити вікно з мінімізованого/максимізованого стану."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            return {"success": True, "hwnd": hwnd, "action": "restore"}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def close_window(self, hwnd: int, force: bool = False) -> Dict[str, Any]:
        """
        Закрити вікно.

        Args:
            hwnd: Handle вікна
            force: True = TerminateProcess, False = WM_CLOSE
        """
        try:
            if force:
                # Жорстке закриття
                pid = self._get_window_pid(hwnd)
                if pid:
                    process = psutil.Process(pid)
                    process.terminate()
                    return {"success": True, "hwnd": hwnd, "action": "force_close", "pid": pid}
            else:
                # М'яке закриття (WM_CLOSE)
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return {"success": True, "hwnd": hwnd, "action": "close"}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def hide_window(self, hwnd: int) -> Dict[str, Any]:
        """Приховати вікно."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            return {"success": True, "hwnd": hwnd, "action": "hide"}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def show_window(self, hwnd: int) -> Dict[str, Any]:
        """Показати приховане вікно."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            return {"success": True, "hwnd": hwnd, "action": "show"}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    # ==================== ПОЗИЦІЯ ТА РОЗМІР ====================

    def move_window(self, hwnd: int, x: int, y: int) -> Dict[str, Any]:
        """Перемістити вікно (зберігаючи розмір)."""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            win32gui.MoveWindow(hwnd, x, y, width, height, True)
            return {"success": True, "hwnd": hwnd, "position": {"x": x, "y": y}}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def resize_window(self, hwnd: int, width: int, height: int) -> Dict[str, Any]:
        """Змінити розмір вікна (зберігаючи позицію)."""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            x = rect[0]
            y = rect[1]

            win32gui.MoveWindow(hwnd, x, y, width, height, True)
            return {"success": True, "hwnd": hwnd, "size": {"width": width, "height": height}}
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def move_resize_window(self, hwnd: int, x: int, y: int,
                         width: int, height: int) -> Dict[str, Any]:
        """Одночасно перемістити та змінити розмір вікна."""
        try:
            win32gui.MoveWindow(hwnd, x, y, width, height, True)
            return {
                "success": True,
                "hwnd": hwnd,
                "position": {"x": x, "y": y},
                "size": {"width": width, "height": height}
            }
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def get_window_rect(self, hwnd: int) -> Dict[str, Any]:
        """Отримати координати та розмір вікна."""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            return {
                "x": rect[0],
                "y": rect[1],
                "width": rect[2] - rect[0],
                "height": rect[3] - rect[1]
            }
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    def center_window(self, hwnd: int) -> Dict[str, Any]:
        """Відцентрувати вікно на екрані."""
        try:
            import ctypes
            # Отримуємо розмір екрану
            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)

            # Отримуємо розмір вікна
            rect = win32gui.GetWindowRect(hwnd)
            win_width = rect[2] - rect[0]
            win_height = rect[3] - rect[1]

            # Розраховуємо центр
            x = (screen_width - win_width) // 2
            y = (screen_height - win_height) // 2

            win32gui.MoveWindow(hwnd, x, y, win_width, win_height, True)

            return {
                "success": True,
                "hwnd": hwnd,
                "position": {"x": x, "y": y}
            }
        except Exception as e:
            return {"success": False, "error": str(e), "hwnd": hwnd}

    # ==================== ДОПОМІЖНІ ФУНКЦІЇ ====================

    def is_window_visible(self, hwnd: int) -> bool:
        """Чи видиме вікно."""
        try:
            return win32gui.IsWindowVisible(hwnd)
        except:
            return False

    def is_window_minimized(self, hwnd: int) -> bool:
        """Чи вікно згорнуте."""
        try:
            return win32gui.IsIconic(hwnd)
        except:
            return False

    def is_window_maximized(self, hwnd: int) -> bool:
        """Чи вікно розгорнуте на весь екран."""
        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            return placement[1] == win32con.SW_SHOWMAXIMIZED
        except:
            return False

    def wait_for_window(self, title_pattern: str, timeout: float = 10.0) -> Optional[int]:
        """
        Очікувати появи вікна.

        Args:
            title_pattern: Шаблон заголовка
            timeout: Максимальний час очікування (сек)

        Returns:
            hwnd або None
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            hwnd = self.find_window_by_title(title_pattern)
            if hwnd:
                return hwnd
            time.sleep(0.5)
        return None

    def wait_window_close(self, hwnd: int, timeout: float = 30.0) -> bool:
        """
        Очікувати закриття вікна.

        Args:
            hwnd: Handle вікна
            timeout: Максимальний час очікування (сек)

        Returns:
            True якщо вікно закрилось, False якщо timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not win32gui.IsWindow(hwnd):
                return True
            time.sleep(0.5)
        return False

    def bring_all_to_top(self, process_name: str) -> Dict[str, Any]:
        """
        Підняти всі вікна процесу на передній план.

        Args:
            process_name: Назва процесу

        Returns:
            {"success": True, "activated": [hwnd, ...]}
        """
        try:
            hwnds = self.find_window_by_process(process_name)
            activated = []

            for hwnd in hwnds:
                result = self.activate_window(hwnd)
                if result.get("success"):
                    activated.append(hwnd)

            return {
                "success": True,
                "process": process_name,
                "found": len(hwnds),
                "activated": activated
            }
        except Exception as e:
            return {"success": False, "error": str(e), "process": process_name}

    # ==================== ПРИВАТНІ МЕТОДИ ====================

    def _get_window_pid(self, hwnd: int) -> Optional[int]:
        """Отримати PID процесу вікна."""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return pid
        except:
            return None

    def _get_process_name(self, pid: int) -> str:
        """Отримати назву процесу за PID."""
        try:
            process = psutil.Process(pid)
            return process.name()
        except:
            return "unknown"


# ==================== Функції для інтеграції в TOOL_POLICIES ====================

_manager = WindowManager()


def list_windows(include_hidden: bool = False, format_output: bool = True) -> str:
    """Список всіх вікон у читабельному форматі."""
    windows = _manager.list_windows(include_hidden)

    if not windows:
        return "❌ Не знайдено жодного вікна"

    if not format_output:
        return str(windows)

    # Форматуємо у читабельний список
    lines = [f"📋 Знайдено {len(windows)} вікон:", ""]

    for i, w in enumerate(windows, 1):
        title = w.get('title', 'Без назви')
        process = w.get('process_name', 'невідомо')
        pid = w.get('pid', 0)
        visible = "👁️" if w.get('visible') else "🙈"
        rect = w.get('rect', {})
        size = f"{rect.get('width', 0)}x{rect.get('height', 0)}"

        lines.append(f"{i}. {visible} **{title}**")
        lines.append(f"   🖥️ {process} (PID: {pid}) — {size}")
        lines.append("")

    return "\n".join(lines)


def find_window_by_title(pattern: str, exact: bool = False) -> Optional[int]:
    """Знайти вікно за заголовком."""
    return _manager.find_window_by_title(pattern, exact)


def find_window_by_process(process_name: str) -> List[int]:
    """Знайти вікна процесу."""
    return _manager.find_window_by_process(process_name)


def find_window_by_class(class_name: str) -> List[int]:
    """Знайти вікна за класом."""
    return _manager.find_window_by_class(class_name)


def get_active_window() -> Dict[str, Any]:
    """Активне вікно."""
    return _manager.get_active_window()


def activate_window(hwnd: int) -> Dict[str, Any]:
    """Активувати вікно."""
    return _manager.activate_window(hwnd)


def minimize_window(hwnd: int) -> Dict[str, Any]:
    """Згорнути вікно."""
    return _manager.minimize_window(hwnd)


def maximize_window(hwnd: int) -> Dict[str, Any]:
    """Розгорнути вікно."""
    return _manager.maximize_window(hwnd)


def restore_window(hwnd: int) -> Dict[str, Any]:
    """Відновити вікно."""
    return _manager.restore_window(hwnd)


def close_window(hwnd: int, force: bool = False) -> Dict[str, Any]:
    """Закрити вікно."""
    return _manager.close_window(hwnd, force)


def hide_window(hwnd: int) -> Dict[str, Any]:
    """Приховати вікно."""
    return _manager.hide_window(hwnd)


def show_window(hwnd: int) -> Dict[str, Any]:
    """Показати вікно."""
    return _manager.show_window(hwnd)


def move_window(hwnd: int, x: int, y: int) -> Dict[str, Any]:
    """Перемістити вікно."""
    return _manager.move_window(hwnd, x, y)


def resize_window(hwnd: int, width: int, height: int) -> Dict[str, Any]:
    """Змінити розмір вікна."""
    return _manager.resize_window(hwnd, width, height)


def move_resize_window(hwnd: int, x: int, y: int, width: int, height: int) -> Dict[str, Any]:
    """Перемістити та змінити розмір."""
    return _manager.move_resize_window(hwnd, x, y, width, height)


def get_window_rect(hwnd: int) -> Dict[str, Any]:
    """Отримати координати вікна."""
    return _manager.get_window_rect(hwnd)


def center_window(hwnd: int) -> Dict[str, Any]:
    """Відцентрувати вікно."""
    return _manager.center_window(hwnd)


def is_window_visible(hwnd: int) -> bool:
    """Чи видиме вікно."""
    return _manager.is_window_visible(hwnd)


def is_window_minimized(hwnd: int) -> bool:
    """Чи згорнуте вікно."""
    return _manager.is_window_minimized(hwnd)


def is_window_maximized(hwnd: int) -> bool:
    """Чи розгорнуте вікно."""
    return _manager.is_window_maximized(hwnd)


def wait_for_window(title_pattern: str, timeout: float = 10.0) -> Optional[int]:
    """Очікувати появи вікна."""
    return _manager.wait_for_window(title_pattern, timeout)


def wait_window_close(hwnd: int, timeout: float = 30.0) -> bool:
    """Очікувати закриття вікна."""
    return _manager.wait_window_close(hwnd, timeout)


def bring_all_to_top(process_name: str) -> Dict[str, Any]:
    """Підняти всі вікна процесу."""
    return _manager.bring_all_to_top(process_name)
