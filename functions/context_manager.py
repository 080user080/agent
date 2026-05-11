"""Context Manager — стиснення історії дій для економії токенів.

Цей модуль реалізує логіку "ковзного вікна з підсумовуванням":
- Кожні N кроків старі дії стискаються в короткий підсумок
- Останні кроки залишаються детальними для вирішення поточних проблем
- Підсумок передається в системний промпт для збереження глобального контексту
"""

from typing import List, Dict, Any, Optional, Callable


def summarize_progress(
    old_actions: List[Dict[str, Any]],
    current_summary: str,
    ask_llm_fn: Callable[[str, Optional[str]], str]
) -> str:
    """
    Перетворює список старих дій у короткий список досягнень.
    
    Args:
        old_actions: Список старих дій для підсумовування
        current_summary: Поточний підсумок виконання
        ask_llm_fn: Функція для виклику LLM (повинна приймати prompt і system_prompt)
        
    Returns:
        Оновлений підсумок виконання завдання
    """
    if not old_actions:
        return current_summary

    prompt = f"""Поточний підсумок виконання завдання: {current_summary}

Нові виконані кроки:
{format_actions_for_summary(old_actions)}

Твоє завдання: Онови підсумок виконання завдання. 
Напиши лише список завершених етапів (achievement list). 
Не пиши технічні деталі (координати, OCR), тільки суть: "Крок Х: [Дія] -- Виконано".
Якщо була помилка, вкажи її коротко.
"""
    
    try:
        new_summary = ask_llm_fn(
            prompt,
            system_prompt="Ти — менеджер пам'яті агента Марк. Пиши коротко, тезами. Не пиши зайвого тексту."
        )
        return new_summary.strip()
    except Exception:
        # Fallback: просте об'єднання якщо LLM недоступний
        fallback = current_summary + "\n" + format_actions_for_summary(old_actions)
        return fallback[:1000]  # Обмежити довжину


def format_actions_for_summary(actions: List[Dict[str, Any]]) -> str:
    """
    Форматує список дій для підсумовування.
    
    Args:
        actions: Список дій
        
    Returns:
        Форматований текст для підсумовування
    """
    formatted = []
    for i, act in enumerate(actions):
        # Беремо тільки суть дії та результат, ігноруємо сирий OCR/UIA
        action_type = act.get('action', 'unknown')
        result = act.get('result', 'no result')
        # Обрізаємо результат до 100 символів
        result_str = str(result)[:100] if result else 'no result'
        formatted.append(f"- Крок {i+1}: {action_type}, Результат: {result_str}")
    return "\n".join(formatted)


def should_summarize(
    actions_count: int,
    threshold: int = 7,
    keep_recent: int = 3
) -> bool:
    """
    Перевіряє чи потрібно робити підсумовування.
    
    Args:
        actions_count: Поточна кількість дій
        threshold: Порог для підсумовування (за замовчуванням 7)
        keep_recent: Скільки останніх дій залишити (за замовчуванням 3)
        
    Returns:
        True якщо потрібно підсумовувати
    """
    return actions_count > (threshold + keep_recent)
