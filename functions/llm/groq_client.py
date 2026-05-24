# functions/llm/groq_client.py
"""Groq API client using official SDK."""
from typing import Dict, Any, List, Optional, Tuple
import sys
from colorama import Fore

# Перевіряємо імпорт groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
    print(f"{Fore.GREEN}[Groq] SDK imported successfully{Fore.RESET}")
except ImportError as e:
    GROQ_AVAILABLE = False
    Groq = None
    print(f"{Fore.RED}[Groq] SDK import failed: {e}{Fore.RESET}")


def call_groq_sdk(endpoint: Dict[str, Any], messages: List[Dict[str, str]]) -> Tuple[bool, str]:
    """Викликати Groq API через офіційний SDK.
    
    Args:
        endpoint: Endpoint конфігурація з url, model, api_key, temperature, max_tokens
        messages: Список повідомлень для відправки
        
    Returns:
        Tuple з (success: bool, result_or_error)
    """
    if not GROQ_AVAILABLE:
        print(f"{Fore.RED}[Groq] SDK not installed{Fore.RESET}")
        return False, "groq package not installed"
    
    try:
        print(f"{Fore.LIGHTBLACK_EX}[Groq] Calling SDK with model: {endpoint.get('model')}{Fore.RESET}")
        client = Groq(api_key=endpoint.get("api_key", ""))
        
        # Конвертуємо messages у формат Groq
        groq_messages = []
        for msg in messages:
            groq_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        print(f"{Fore.LIGHTBLACK_EX}[Groq] Sending {len(groq_messages)} messages{Fore.RESET}")
        
        # Викликаємо API з стрімінгом
        completion = client.chat.completions.create(
            model=endpoint["model"],
            messages=groq_messages,
            temperature=endpoint.get("temperature", 0.6),
            max_completion_tokens=endpoint.get("max_tokens", 4096),
            top_p=0.95,
            reasoning_effort="default",
            stream=False,  # Використовуємо non-streaming для простоти
            stop=None
        )
        
        # Отримуємо повну відповідь
        content = completion.choices[0].message.content
        if content and content.strip():
            print(f"{Fore.LIGHTBLACK_EX}[Groq] Got response: {len(content)} chars{Fore.RESET}")
            return True, content
        else:
            print(f"{Fore.RED}[Groq] Empty response from SDK{Fore.RESET}")
            return False, "empty content"
            
    except Exception as e:
        print(f"{Fore.RED}[Groq] Error: {str(e)}{Fore.RESET}")
        return False, str(e)


def stream_groq_sdk(endpoint: Dict[str, Any], messages: List[Dict[str, str]], callback, usage_callback=None) -> bool:
    """Стрімінг відповіді від Groq через офіційний SDK.
    
    Args:
        endpoint: Endpoint конфігурація
        messages: Список повідомлень
        callback: Функція callback(chunk_text) для кожного фрагмента
        usage_callback: Опціональний callback(usage_dict) для отримання реального usage після стріму
        
    Returns:
        True якщо успішно, False інакше
    """
    if not GROQ_AVAILABLE:
        return False
    
    try:
        client = Groq(api_key=endpoint.get("api_key", ""))
        
        # Конвертуємо messages
        groq_messages = []
        for msg in messages:
            groq_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Стрімінг
        completion = client.chat.completions.create(
            model=endpoint["model"],
            messages=groq_messages,
            temperature=endpoint.get("temperature", 0.6),
            max_completion_tokens=endpoint.get("max_tokens", 4096),
            top_p=0.95,
            reasoning_effort="default",
            stream=True,
            stop=None
        )
        
        # Обробляємо chunks
        for chunk in completion:
            if chunk.choices[0].delta.content:
                callback(chunk.choices[0].delta.content)
        
        # Після стріму — отримуємо реальне usage з останнього chunk (якщо є)
        # Groq SDK v1.2.0+: ChatCompletionChunk має поля 'usage' та 'x_groq'
        # usage заповнюється тільки в останньому chunk після завершення стріму
        try:
            usage_info = None
            
            # Пробуємо отримати usage з останнього chunk
            # Groq SDK повертає usage в останньому chunk (після всіх content chunks)
            if chunk.usage is not None:
                # chunk.usage це CompletionUsage об'єкт з prompt_tokens, completion_tokens, total_tokens
                usage_info = {
                    "prompt_tokens": chunk.usage.prompt_tokens or 0,
                    "completion_tokens": chunk.usage.completion_tokens or 0,
                    "total_tokens": chunk.usage.total_tokens or 0,
                }
            elif chunk.x_groq is not None and hasattr(chunk.x_groq, 'usage'):
                # Groq-specific: usage може бути в x_groq.usage
                usage_info = {
                    "prompt_tokens": chunk.x_groq.usage.prompt_tokens or 0,
                    "completion_tokens": chunk.x_groq.usage.completion_tokens or 0,
                    "total_tokens": chunk.x_groq.usage.total_tokens or 0,
                }
            
            if usage_info and usage_callback:
                usage_callback(usage_info)
        except Exception:
            # Не критично — usage може бути недоступний
            pass
        
        return True
        
    except Exception as e:
        print(f"Groq streaming error: {e}")
        return False
