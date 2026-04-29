# functions/llm/__init__.py
"""LLM integration module - refactored from logic_llm.py."""
from typing import Dict, Any, List, Optional, Tuple
from colorama import Fore

# Import from endpoint_client
from .endpoint_client import (
    _normalize_endpoint,
    get_endpoint_by_role,
    get_primary_endpoint,
    get_secondary_endpoint,
    call_endpoint,
)

# Import from response_parser
from .response_parser import (
    sanitize_json_string,
    safe_json_loads,
    clean_llm_tokens,
    extract_json_from_text,
    extract_all_json_actions,
    process_llm_response,
)

# Export main functions
__all__ = [
    # Endpoint functions
    "_normalize_endpoint",
    "get_endpoint_by_role",
    "get_primary_endpoint",
    "get_secondary_endpoint",
    "call_endpoint",
    # Response parser functions
    "sanitize_json_string",
    "safe_json_loads",
    "clean_llm_tokens",
    "extract_json_from_text",
    "extract_all_json_actions",
    "process_llm_response",
]


def ask_llm(user_message: str, conversation_history: List[Dict[str, str]], system_prompt: str) -> str:
    """Відправити запит до активного LLM endpoint (1 → 2 → 3 → 4 → ...).

    Args:
        user_message: Повідомлення користувача
        conversation_history: Історія розмови
        system_prompt: Системний промпт

    Returns:
        Відповідь від LLM або повідомлення про помилку
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    # Уникнути дублювання
    last = conversation_history[-1] if conversation_history else None
    if not (last and last.get("role") == "user" and last.get("content") == user_message):
        messages.append({"role": "user", "content": user_message})

    # Отримуємо всі enabled endpoints в порядку цифрового role
    from .core_settings import get_setting
    endpoints = get_setting("LLM_ENDPOINTS", [])

    # Сортуємо endpoints за цифровим role (1, 2, 3, ...)
    def get_role_order(role):
        try:
            return int(role) if role else 999
        except (ValueError, TypeError):
            # Для сумісності зі старими текстовими role
            role_map = {"primary": 1, "secondary": 2, "fallback": 3, "alternative": 4}
            return role_map.get(role, 999)

    enabled_endpoints = [ep for ep in endpoints if ep.get("enabled") and ep.get("model") and ep.get("url")]
    enabled_endpoints.sort(key=lambda ep: get_role_order(ep.get("role")))

    last_error = None

    for ep in enabled_endpoints:
        try:
            from .endpoint_client import _normalize_endpoint
            endpoint = _normalize_endpoint(ep)
            role = ep.get("role", "unknown")
            name = ep.get("name", "LLM")

            ok, result = call_endpoint(endpoint, messages)
            if ok:
                return result

            last_error = result
            print(f"{Fore.YELLOW}⚠️ {name} (порядок {role}) не вдалося: {result[:100]}...")
        except Exception as e:
            last_error = str(e)
            print(f"{Fore.YELLOW}⚠️ Помилка при виклику {ep.get('name', 'LLM')}: {e}")

    # Усі спроби провалились — повернути помилку
    if last_error:
        if "connection" in str(last_error).lower() or "refused" in str(last_error).lower():
            return (
                "❌ **Не вдається підключитися до LLM**\n\n"
                "Перевірте:\n"
                "1. API ключі та налаштування endpoints\n"
                "2. Налаштування в редакторі LLM endpoints\n\n"
                f"Остання помилка: {last_error[:200]}"
            )
        return f"❌ Помилка LLM: {last_error[:200]}"

    return "❌ Немає налаштованих LLM endpoints"


# Backward compatibility: keep old function names
_call_endpoint = call_endpoint
