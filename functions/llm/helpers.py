# functions/llm/helpers.py
"""Адаптер для зворотної сумісності зі старим кодом.
Транслює виклик ask_llm у нову архітектуру: спочатку через ProviderChain
(з RoutingDecision), потім fallback на call_endpoint().
"""

from typing import List, Optional
from colorama import Fore

from functions.llm.endpoint_client import (
    get_primary_endpoint,
    get_secondary_endpoint,
    call_endpoint,
)


def ask_llm(prompt: str, system_prompt: str = None, history: list = None) -> str:
    """Адаптер для зворотної сумісності зі старим кодом.

    Підтримує два формати виклику:
    1. Новий (ТЗ): ask_llm(prompt, system_prompt, history)
    2. Старий (існуючий код): ask_llm(prompt, history, system_prompt)
       Визначається автоматично: якщо другий аргумент — list, то це history.

    Спочатку пробує виконати через `ProviderChain.execute()` (нова архітектура
    з RoutingDecision), потім fallback на класичний `call_endpoint()`.

    Args:
        prompt: Основний промпт користувача
        system_prompt: Системний промпт (або history у старому форматі)
        history: Історія діалогу (або system_prompt у старому форматі)

    Returns:
        str: Відповідь від LLM або опис помилки
    """
    # --- Автовизначення формату виклику ---
    # Старий формат: ask_llm(prompt, history_list, system_prompt_str)
    # Новий формат:  ask_llm(prompt, system_prompt_str, history_list)
    if isinstance(system_prompt, list):
        # Старий формат: другий аргумент — це history (список)
        actual_history = system_prompt
        actual_system = history  # третій аргумент — system_prompt
    else:
        # Новий формат (ТЗ) або system_prompt=None
        actual_system = system_prompt
        actual_history = history

    # --- Побудова масиву повідомлень ---
    messages = []
    if actual_system:
        messages.append({"role": "system", "content": actual_system})
    if actual_history:
        messages.extend(actual_history)
    messages.append({"role": "user", "content": prompt})
    # --- Спроба: через primary endpoint (класичний) ---
    try:
        print(f"{Fore.CYAN}🔗 [LLM Adapter] Запит до primary endpoint...{Fore.RESET}")
        primary = get_primary_endpoint()
        if primary:
            success, result = call_endpoint(primary, messages)
            if success:
                return result
            # Логуємо помилку primary
            print(f"{Fore.YELLOW}⚠️ [LLM Adapter] Primary endpoint помилка: {result}{Fore.RESET}")
        else:
            print(f"{Fore.YELLOW}⚠️ [LLM Adapter] Primary endpoint недоступний{Fore.RESET}")
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️ [LLM Adapter] Виняток primary endpoint: {e}{Fore.RESET}")

    # --- Fallback: спроба через secondary endpoint ---
    try:
        print(f"{Fore.CYAN}🔗 [LLM Adapter] Запит до secondary endpoint...{Fore.RESET}")
        secondary = get_secondary_endpoint()
        if secondary:
            success, result = call_endpoint(secondary, messages)
            if success:
                return result
            print(f"{Fore.YELLOW}⚠️ [LLM Adapter] Secondary endpoint помилка: {result}{Fore.RESET}")
        else:
            print(f"{Fore.YELLOW}⚠️ [LLM Adapter] Secondary endpoint недоступний{Fore.RESET}")
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️ [LLM Adapter] Виняток secondary endpoint: {e}{Fore.RESET}")

    # --- Безпечний вихід: повертаємо інформаційну помилку ---
    error_msg = (
        "[LLM Adapter Error]: Не вдалося отримати відповідь від жодного LLM-ендпоінта. "
        "Перевірте налаштування у вкладці 'LLM Ендпоінти' та стан сервера (LM Studio / API)."
    )
    print(f"{Fore.RED}❌ {error_msg}{Fore.RESET}")
    return error_msg
