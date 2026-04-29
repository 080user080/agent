"""
Журнал GUI-дій (Action Recorder).

GUI Automation Phase 6 — аудит та відстеження всіх дій агента.
Автоматичний запис кожної дії зі скріншотами до/після.
"""

import json
import time
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import threading

from .tools_screen_capture import ScreenCapture


@dataclass
class ActionRecord:
    """Запис про виконану дію."""
    timestamp: str
    action_type: str
    function_name: str
    params: Dict[str, Any]
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    result: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    duration_ms: float = 0.0
    application: str = ""  # Назва програми де виконано дію
    session_id: str = ""


class ActionRecorder:
    """
    Recorder для GUI дій.
    Singleton, автоматично записує всі дії зі скріншотами.
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

    def __init__(self, logs_dir: str = "logs"):
        if self._initialized:
            return

        self._initialized = True
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

        # Піддиректорії
        self.screenshots_dir = self.logs_dir / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)

        self.actions_file = self.logs_dir / "gui_actions.jsonl"

        # Поточна сесія
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = time.time()

        # Ліміти
        self.max_records = 500
        self.retention_days = 7

        # Кеш дій в пам'яті
        self._actions_cache: List[ActionRecord] = []
        self._max_cache_size = 50

        # Screen capture
        self._screen = ScreenCapture()

        # Лічильники
        self._action_counter = 0
        self._lock = threading.Lock()

        # Очищення старих записів
        self._cleanup_old_records()

    def _cleanup_old_records(self):
        """Видалити записи старші за retention_days."""
        try:
            cutoff = time.time() - (self.retention_days * 24 * 3600)

            if self.actions_file.exists():
                # Читаємо тільки свіжі записи
                fresh_records = []
                with open(self.actions_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            ts = record.get("timestamp", "")
                            if ts:
                                record_time = datetime.fromisoformat(ts).timestamp()
                                if record_time > cutoff:
                                    fresh_records.append(record)
                        except:
                            continue

                # Переписуємо файл
                with open(self.actions_file, "w", encoding="utf-8") as f:
                    for record in fresh_records:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

            # Очищення старих скріншотів
            if self.screenshots_dir.exists():
                for file in self.screenshots_dir.iterdir():
                    if file.is_file():
                        if file.stat().st_mtime < cutoff:
                            try:
                                file.unlink()
                            except:
                                pass

        except Exception as e:
            print(f"[ActionRecorder] Cleanup error: {e}")

    def _generate_screenshot_filename(self, action_type: str, before: bool) -> str:
        """Генерувати ім'я файлу для скріншоту."""
        with self._lock:
            self._action_counter += 1
            counter = self._action_counter

        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
        prefix = "before" if before else "after"
        filename = f"{self.session_id}_{counter:04d}_{action_type}_{prefix}.png"
        return str(self.screenshots_dir / filename)

    def record_action(
        self,
        action_type: str,
        function_name: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        capture_screenshots: bool = True
    ) -> ActionRecord:
        """
        Записати дію зі скріншотами.

        Args:
            action_type: Тип дії ("click", "type", "screenshot", etc.)
            function_name: Назва функції
            params: Параметри виклику
            result: Результат виконання
            capture_screenshots: Чи робити скріншоти

        Returns:
            ActionRecord
        """
        start_time = time.time()

        # Скріншот до
        screenshot_before = None
        if capture_screenshots:
            try:
                screenshot_before = self._generate_screenshot_filename(action_type, True)
                self._screen.take_screenshot(screenshot_before)
            except Exception as e:
                screenshot_before = None
                print(f"[ActionRecorder] Before screenshot error: {e}")

        # Затримка для запису результату дії
        time.sleep(0.1)

        # Скріншот після
        screenshot_after = None
        if capture_screenshots:
            try:
                screenshot_after = self._generate_screenshot_filename(action_type, False)
                self._screen.take_screenshot(screenshot_after)
            except Exception as e:
                screenshot_after = None
                print(f"[ActionRecorder] After screenshot error: {e}")

        # Визначаємо програму
        try:
            from .tools_app_recognizer import detect_active_application
            app = detect_active_application()
            app_name = app.get("name", "unknown")
        except:
            app_name = "unknown"

        duration_ms = (time.time() - start_time) * 1000

        # Створюємо запис
        record = ActionRecord(
            timestamp=datetime.now().isoformat(),
            action_type=action_type,
            function_name=function_name,
            params=params,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
            result=result,
            success=result.get("success", False),
            duration_ms=duration_ms,
            application=app_name,
            session_id=self.session_id
        )

        # Зберігаємо
        self._save_record(record)

        return record

    def _save_record(self, record: ActionRecord):
        """Зберегти запис у файл та кеш."""
        # Додаємо в кеш
        self._actions_cache.append(record)
        if len(self._actions_cache) > self._max_cache_size:
            self._actions_cache.pop(0)

        # Записуємо в файл
        try:
            with open(self.actions_file, "a", encoding="utf-8") as f:
                record_dict = asdict(record)
                # Обмежуємо розмір параметрів для JSON
                record_dict["params"] = self._truncate_params(record.params)
                record_dict["result"] = self._truncate_params(record.result)
                f.write(json.dumps(record_dict, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[ActionRecorder] Save error: {e}")

    def _truncate_params(self, params: Dict[str, Any], max_len: int = 500) -> Dict[str, Any]:
        """Обмежити розмір параметрів для запису."""
        result = {}
        for key, value in params.items():
            str_value = str(value)
            if len(str_value) > max_len:
                str_value = str_value[:max_len] + "..."
            result[key] = str_value
        return result

    def get_recent_actions(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Отримати останні N дій.

        Args:
            count: Кількість дій

        Returns:
            Список записів
        """
        # Спочатку дивимось в кеш (найновіші)
        if len(self._actions_cache) >= count:
            return [asdict(r) for r in self._actions_cache[-count:]]

        # Читаємо з файлу
        try:
            if not self.actions_file.exists():
                return []

            records = []
            with open(self.actions_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        if record.get("session_id") == self.session_id:
                            records.append(record)
                    except:
                        continue

            return records[-count:] if records else []

        except Exception as e:
            return [{"error": str(e)}]

    def export_session_log(self, format: str = "json") -> str:
        """
        Експортувати лог поточної сесії.

        Args:
            format: "json" або "text"

        Returns:
            Лог у вказаному форматі
        """
        try:
            actions = self.get_recent_actions(1000)  # Всі дії сесії

            if format == "json":
                return json.dumps({
                    "session_id": self.session_id,
                    "start_time": datetime.fromtimestamp(self.session_start).isoformat(),
                    "duration_seconds": time.time() - self.session_start,
                    "action_count": len(actions),
                    "actions": actions
                }, indent=2, ensure_ascii=False)

            elif format == "text":
                lines = [
                    f"GUI Automation Session: {self.session_id}",
                    f"Started: {datetime.fromtimestamp(self.session_start).isoformat()}",
                    f"Duration: {time.time() - self.session_start:.1f}s",
                    f"Actions: {len(actions)}",
                    "=" * 50,
                    ""
                ]

                for i, action in enumerate(actions, 1):
                    lines.append(f"{i}. [{action.get('timestamp', '?')[11:19]}] {action.get('action_type', '?')}")
                    lines.append(f"   Function: {action.get('function_name', '?')}")
                    lines.append(f"   App: {action.get('application', '?')}")
                    lines.append(f"   Success: {action.get('success', False)}")
                    lines.append(f"   Duration: {action.get('duration_ms', 0):.1f}ms")
                    if action.get('screenshot_before'):
                        lines.append(f"   Screenshot: {action.get('screenshot_before')}")
                    lines.append("")

                return "\n".join(lines)

            else:
                return f"Unknown format: {format}"

        except Exception as e:
            return f"Export error: {str(e)}"

    def generate_action_report(self) -> str:
        """
        Згенерувати читабельний звіт.

        Returns:
            Текстовий звіт
        """
        try:
            actions = self.get_recent_actions(1000)

            if not actions:
                return "No actions recorded in current session."

            # Статистика
            total = len(actions)
            successful = sum(1 for a in actions if a.get("success"))
            failed = total - successful

            # Типи дій
            action_types = {}
            for a in actions:
                t = a.get("action_type", "unknown")
                action_types[t] = action_types.get(t, 0) + 1

            # Програми
            apps = {}
            for a in actions:
                app = a.get("application", "unknown")
                apps[app] = apps.get(app, 0) + 1

            lines = [
                "GUI Automation Action Report",
                "=" * 40,
                f"Session: {self.session_id}",
                f"Duration: {time.time() - self.session_start:.1f}s",
                "",
                "Summary:",
                f"  Total actions: {total}",
                f"  Successful: {successful} ({100*successful/total:.1f}%)",
                f"  Failed: {failed} ({100*failed/total:.1f}%)",
                "",
                "Action Types:"
            ]

            for t, c in sorted(action_types.items(), key=lambda x: -x[1]):
                lines.append(f"  {t}: {c}")

            lines.extend(["", "Applications:"])
            for app, c in sorted(apps.items(), key=lambda x: -x[1]):
                lines.append(f"  {app}: {c}")

            # Останні дії
            lines.extend(["", "Recent Actions:"])
            for a in actions[-5:]:
                status = "✅" if a.get("success") else "❌"
                lines.append(f"  {status} {a.get('action_type', '?')} in {a.get('application', '?')}")

            return "\n".join(lines)

        except Exception as e:
            return f"Report error: {str(e)}"

    def search_actions(
        self,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Пошук дій за фільтром.

        Args:
            filter_dict: Фільтр {"action_type": "click", "success": True, ...}

        Returns:
            Відфільтровані записи
        """
        filter_dict = filter_dict or {}
        results = []

        try:
            if not self.actions_file.exists():
                return []

            with open(self.actions_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())

                        # Перевіряємо фільтр
                        match = True
                        for key, value in filter_dict.items():
                            if record.get(key) != value:
                                match = False
                                break

                        if match:
                            results.append(record)

                    except:
                        continue

            return results[-self.max_records:]

        except Exception as e:
            return [{"error": str(e)}]


# ==================== ПУБЛІЧНИЙ API ====================

_recorder = None


def get_recorder() -> ActionRecorder:
    """Отримати singleton екземпляр ActionRecorder."""
    global _recorder
    if _recorder is None:
        _recorder = ActionRecorder()
    return _recorder


def record_action(
    action_type: str,
    function_name: str,
    params: Dict[str, Any],
    result: Dict[str, Any],
    capture_screenshots: bool = True
) -> Dict[str, Any]:
    """Записати дію."""
    recorder = get_recorder()
    record = recorder.record_action(
        action_type=action_type,
        function_name=function_name,
        params=params,
        result=result,
        capture_screenshots=capture_screenshots
    )
    return asdict(record)


def get_recent_actions(count: int = 10) -> List[Dict[str, Any]]:
    """Отримати останні дії."""
    return get_recorder().get_recent_actions(count)


def export_session_log(format: str = "json") -> str:
    """Експортувати лог сесії."""
    return get_recorder().export_session_log(format)


def generate_action_report() -> str:
    """Згенерувати звіт."""
    return get_recorder().generate_action_report()


def search_actions(filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Пошук дій."""
    return get_recorder().search_actions(filter_dict)


# Декоратор для автоматичного запису

def recordable(action_type: str, capture_screenshots: bool = True):
    """
    Декоратор для автоматичного запису функцій.

    Usage:
        @recordable("click")
        def mouse_click(x, y):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Виконуємо функцію
            result = func(*args, **kwargs)

            # Записуємо
            try:
                params = {"args": str(args), "kwargs": str(kwargs)}
                if isinstance(result, dict):
                    record_result = result
                else:
                    record_result = {"success": result is not None, "value": str(result)}

                get_recorder().record_action(
                    action_type=action_type,
                    function_name=func.__name__,
                    params=params,
                    result=record_result,
                    capture_screenshots=capture_screenshots
                )
            except Exception as e:
                print(f"[recordable] Recording error: {e}")

            return result

        return wrapper
    return decorator
