"""Сумісний runtime для структурованих результатів інструментів."""
from typing import Any, Dict, Optional

SAFE = "safe"
CONFIRM_REQUIRED = "confirm_required"
BLOCKED = "blocked"

TOOL_POLICIES: Dict[str, Dict[str, Any]] = {
    "create_file": {"risk": SAFE},
    "edit_file": {"risk": SAFE},
    "execute_python": {"risk": SAFE},
    "execute_python_code": {"risk": SAFE},
    "execute_python_file": {"risk": SAFE},
    "debug_python_code": {"risk": SAFE},
    "list_sandbox_scripts": {"risk": SAFE},
    "open_browser": {"risk": SAFE},
    "show_sandbox_status": {"risk": SAFE},
    "voice_input": {"risk": SAFE},
    "confirm_action": {"risk": SAFE},
    "open_program": {"risk": CONFIRM_REQUIRED},
    "close_program": {"risk": CONFIRM_REQUIRED},
    "add_allowed_program": {"risk": CONFIRM_REQUIRED},
    "enable_auto_confirm": {"risk": CONFIRM_REQUIRED},
    "disable_auto_confirm": {"risk": CONFIRM_REQUIRED},
    "create_skill": {"risk": CONFIRM_REQUIRED},
}


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
