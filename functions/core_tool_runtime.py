"""Сумісний runtime для структурованих результатів інструментів."""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Рівні ризику
SAFE = "safe"                        # Можна виконувати без підтвердження
CONFIRM_REQUIRED = "confirm_required"  # Потрібне підтвердження користувача
BLOCKED = "blocked"                   # Заборонено для planner (але LLM може викликати)

# Категорії інструментів
CATEGORY_FILE = "file"
CATEGORY_CODE = "code"
CATEGORY_SYSTEM = "system"
CATEGORY_BROWSER = "browser"
CATEGORY_MEDIA = "media"
CATEGORY_META = "meta"

TOOL_POLICIES: Dict[str, Dict[str, Any]] = {
    # --- Безпечні файлові операції (тільки Desktop) ---
    "create_file": {"risk": SAFE, "category": CATEGORY_FILE, "description": "Створення txt файлу на Desktop"},
    "edit_file": {"risk": SAFE, "category": CATEGORY_FILE, "description": "Редагування файлу з бекапом"},

    # --- Python sandbox (безпечний) ---
    "execute_python": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Виконання Python в пісочниці"},
    "execute_python_code": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Alias для execute_python"},
    "execute_python_file": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Виконання файлу з пісочниці"},
    "debug_python_code": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Автовиправлення Python коду"},
    "list_sandbox_scripts": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Список скриптів пісочниці"},

    # --- Браузер і медіа ---
    "open_browser": {"risk": SAFE, "category": CATEGORY_BROWSER, "description": "Відкриття URL у браузері"},
    "voice_input": {"risk": SAFE, "category": CATEGORY_MEDIA, "description": "Голосовий ввід"},

    # --- Мета-дії ---
    "show_sandbox_status": {"risk": SAFE, "category": CATEGORY_META, "description": "Показати стан пісочниці"},
    "confirm_action": {"risk": SAFE, "category": CATEGORY_META, "description": "Запит підтвердження"},

    # --- Code tools (читання безпечно, git-операції також) ---
    "read_code_file": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Читання файлу з кодом"},
    "search_in_code": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Пошук у файлах"},
    "list_directory": {"risk": SAFE, "category": CATEGORY_FILE, "description": "Вміст директорії"},
    "git_status": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Git status"},
    "git_diff": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Git diff"},

    # --- Системні дії (потрібне підтвердження) ---
    "open_program": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Відкрити програму"},
    "close_program": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Закрити програму"},
    "add_allowed_program": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Додати в whitelist"},
    "enable_auto_confirm": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Увімкнути автопідтвердження"},
    "disable_auto_confirm": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Вимкнути автопідтвердження"},
    "create_skill": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_META, "description": "Створення нової навички"},
}

# Патерни небезпечних дій у планах
DANGEROUS_PATTERNS: List[str] = [
    "rm -rf",
    "format c:",
    "del /f /s /q",
    "rmdir /s",
    "powershell -enc",
    "shutdown",
    "reg delete",
    "taskkill /f",
    "net user",
    "curl http",  # Потенційне віддалене виконання
    "wget http",
    "invoke-webrequest",
    "base64",
]

# Патерни двозначних дій (потрібна додаткова обережність)
AMBIGUOUS_PATTERNS: List[str] = [
    "system32",
    "windows/",
    "program files",
    "appdata",
    "startup",
    "hosts",
]


class AuditLog:
    """Журнал аудиту виконаних дій."""

    def __init__(self, log_dir: Optional[Path] = None, max_entries: int = 1000):
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True, parents=True)
        self.log_file = log_dir / "audit.jsonl"
        self.max_entries = max_entries
        self._entries: List[Dict[str, Any]] = []

    def log(self, action: str, params: Dict[str, Any], result: Dict[str, Any], risk: str) -> None:
        """Записати дію в аудит."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "risk": risk,
            "ok": result.get("ok"),
            "error": result.get("error"),
            "params_summary": self._summarize_params(params),
        }
        self._entries.append(entry)

        # Записуємо у файл
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Не ламаємо виконання через проблеми з логом

        # Обмежуємо кількість в пам'яті
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

    def _summarize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Скоротити великі параметри (напр. code) для логу."""
        summary = {}
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 200:
                summary[key] = value[:200] + f"... [{len(value)} chars]"
            else:
                summary[key] = value
        return summary

    def get_recent(self, count: int = 10) -> List[Dict[str, Any]]:
        """Отримати останні записи з аудиту."""
        return self._entries[-count:]


# Глобальний аудит
_audit = AuditLog()


def get_audit_log() -> AuditLog:
    """Отримати глобальний аудит."""
    return _audit


def check_dangerous_content(content: str) -> Optional[str]:
    """Перевірити текст на небезпечні патерни. Повертає патерн, якщо знайдений."""
    content_lower = content.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in content_lower:
            return pattern
    return None


def check_ambiguous_content(content: str) -> Optional[str]:
    """Перевірити текст на двозначні патерни."""
    content_lower = content.lower()
    for pattern in AMBIGUOUS_PATTERNS:
        if pattern in content_lower:
            return pattern
    return None


def make_tool_result(
    ok: bool,
    message: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    needs_confirmation: bool = False,
    retryable: bool = False,
) -> Dict[str, Any]:
    """Побудувати єдиний формат результату інструмента."""
    return {
        "ok": ok,
        "message": message,
        "data": data or {},
        "error": error,
        "needs_confirmation": needs_confirmation,
        "retryable": retryable,
    }


def normalize_tool_result(raw_result: Any) -> Dict[str, Any]:
    """Звести довільний результат до єдиного формату."""
    if isinstance(raw_result, dict) and "ok" in raw_result and "message" in raw_result:
        return {
            "ok": bool(raw_result.get("ok")),
            "message": str(raw_result.get("message", "")),
            "data": raw_result.get("data", {}) or {},
            "error": raw_result.get("error"),
            "needs_confirmation": bool(raw_result.get("needs_confirmation", False)),
            "retryable": bool(raw_result.get("retryable", False)),
        }

    if isinstance(raw_result, dict):
        status = str(raw_result.get("status", "")).lower()
        ok = status in {"confirmed", "ok", "success"}
        needs_confirmation = status == "timeout"
        message = raw_result.get("message")
        if not message:
            if status:
                message = f"Статус: {status}"
            else:
                message = str(raw_result)
        return make_tool_result(
            ok=ok,
            message=message,
            data=raw_result,
            error=None if ok else message,
            needs_confirmation=needs_confirmation,
            retryable=not ok,
        )

    text = str(raw_result)
    ok = not text.startswith("❌") and "помилка" not in text.lower()
    return make_tool_result(
        ok=ok,
        message=text,
        data={},
        error=None if ok else text,
        retryable=not ok,
    )


def get_tool_policy(action: str) -> Dict[str, Any]:
    """Отримати політику інструмента."""
    return TOOL_POLICIES.get(action, {"risk": BLOCKED})


def get_tool_risk(action: str) -> str:
    """Отримати risk-level для інструмента."""
    return get_tool_policy(action).get("risk", BLOCKED)
