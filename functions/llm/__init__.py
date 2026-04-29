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
    """Відправити запит до активного LLM endpoint (primary → secondary).
    
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

    # 1. Спробувати primary
    primary = get_primary_endpoint()
    ok, result = call_endpoint(primary, messages)
    if ok:
        return result

    print(f"{Fore.YELLOW}⚠️ Primary не вдалося ({result}), пробую secondary...")

    # 2. Fallback на secondary
    secondary = get_secondary_endpoint()
    if secondary:
        ok2, result2 = call_endpoint(secondary, messages)
        if ok2:
            return result2
        print(f"{Fore.YELLOW}⚠️ Secondary теж не вдалося: {result2}")
    else:
        print(f"{Fore.YELLOW}⚠️ Secondary endpoint не налаштовано")

    # 3. Усі спроби провалились — повернути помилку
    if "connection" in str(result).lower() or "refused" in str(result).lower():
        return (
            "❌ **Не вдається підключитися до LLM**\n\n"
            "Перевірте:\n"
            "1. Primary (Gemini): API ключ та модель\n"
            "2. Secondary (DeepSeek): чи запущено LM Studio?\n"
            "3. Налаштування в редакторі LLM endpoints\n\n"
            f"Остання помилка: {result[:200]}"
        )
    return f"❌ Помилка LLM: {result[:200]}"


# Backward compatibility: keep old function names
_call_endpoint = call_endpoint
