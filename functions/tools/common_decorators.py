# functions/common_decorators.py
"""Спільні декоратори для LLM функцій"""
from typing import Callable, Dict, Any


def llm_function(name: str, description: str, parameters: Dict[str, Any]) -> Callable:
    """Декоратор для реєстрації LLM функцій.

    Args:
        name: Назва функції
        description: Опис функції
        parameters: Параметри функції

    Returns:
        Декоратор функції
    """
    def decorator(func: Callable) -> Callable:
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator
