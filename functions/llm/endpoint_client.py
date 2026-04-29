# functions/llm/endpoint_client.py
"""Endpoint client for LLM API calls."""
import time
import requests
from typing import Dict, Any, List, Optional, Tuple
from colorama import Fore
from ..config import LM_STUDIO_URL


def _is_groq_endpoint(endpoint: Dict[str, Any]) -> bool:
    """Перевірити чи це Groq endpoint."""
    url = endpoint.get("url", "")
    return "api.groq.com" in url


def _normalize_endpoint(ep: Dict[str, Any]) -> Dict[str, Any]:
    """Нормалізувати endpoint dict.
    
    Args:
        ep: Словник з налаштуваннями endpoint (url, model, api_key, тощо)
        
    Returns:
        Нормалізований словник endpoint з повним URL та дефолтними значеннями
    """
    url = ep.get("url", "").rstrip("/")
    # Не додаємо /chat/completions якщо це вже повний URL
    # LM Studio v1: /api/v1/chat - залишаємо як є
    # OpenAI-compatible: /v1/chat/completions - залишаємо як є
    if not url.endswith("/chat/completions") and not url.endswith("/chat"):
        url = url + "/chat/completions"
    return {
        "url": url,
        "model": ep.get("model"),
        "api_key": ep.get("api_key", ""),
        "temperature": ep.get("temperature", 0.1),
        "max_tokens": ep.get("max_tokens", 1024),
        "timeout": ep.get("timeout", 60) or 60,
        "name": ep.get("name", "LLM"),  # Зберігаємо назву endpoint
    }


def get_endpoint_by_role(role: str, default: Optional[Dict] = None) -> Optional[Dict]:
    """Отримати активний LLM endpoint з певною роллю з налаштувань.

    Args:
        role: Роль endpoint'у (наприклад, "primary", "secondary", "fallback", "alternative")
        default: Дефолтне значення, якщо endpoint не знайдено

    Returns:
        Dict з url, model, api_key, temperature, max_tokens, timeout або default або None
    """
    try:
        from ..core_settings import get_setting
        endpoints = get_setting("LLM_ENDPOINTS", [])
        # Якщо role — це "primary", то шукаємо тільки "primary"
        # Якщо role — це "secondary", то шукаємо "secondary", "fallback" або "alternative"
        valid_roles = [role] if role == "primary" else [role, "fallback", "alternative"]
        for ep in endpoints:
            if (ep.get("enabled") and ep.get("role") in valid_roles
                and ep.get("model") and ep.get("url")):
                return _normalize_endpoint(ep)
    except Exception:
        pass
    return default


def get_primary_endpoint():
    """Отримати активний primary LLM endpoint з налаштувань.

    Повертає dict з url, model, api_key, temperature, max_tokens, timeout.
    Якщо primary не налаштовано — повертає дефолт (LM Studio).
    """
    return get_endpoint_by_role("primary", {
        "url": LM_STUDIO_URL,
        "model": "local-model",
        "api_key": "",
        "temperature": 0.1,
        "max_tokens": 1024,
        "timeout": 60,
    })


def get_secondary_endpoint():
    """Отримати активний fallback LLM endpoint з налаштувань.

    Перебирає всі enabled endpoint'и з роллю secondary, fallback або alternative.
    Порядок у списку LLM_ENDPOINTS визначає пріоритет.
    """
    return get_endpoint_by_role("secondary")


def _reload_model(endpoint: Dict[str, Any], headers: Dict[str, str]) -> bool:
    """Перезавантажити модель в LM Studio.
    
    Args:
        endpoint: Endpoint конфігурація
        headers: HTTP headers для запиту
        
    Returns:
        True якщо перезавантаження успішне, False інакше
    """
    # Визначаємо формат API за URL
    is_v1_api = "/api/v1/chat" in endpoint.get("url", "")
    
    try:
        if is_v1_api:
            # LM Studio v1 API format
            base_url = endpoint.get("url", "").replace("/api/v1/chat", "")
            load_url = f"{base_url}/api/v1/models/load"
        else:
            # OpenAI-compatible format - спробуємо завантажити через перший запит
            # LM Studio автоматично завантажує модель при першому запиті
            # Тому просто повертаємо True, щоб повторити запит
            print(f"{Fore.YELLOW}🔄 Спроба завантажити модель {endpoint['model']} через OpenAI-compatible API{Fore.RESET}")
            return True
        
        load_response = requests.post(
            load_url,
            headers=headers,
            json={"model": endpoint["model"]},
            timeout=30
        )
        
        if load_response.status_code == 200:
            print(f"{Fore.YELLOW}🔄 Модель {endpoint['model']} перезавантажено{Fore.RESET}")
            # Чекаємо завантаження
            time.sleep(2)
            return True
        else:
            print(f"{Fore.YELLOW}⚠️ Не вдалося перезавантажити модель: {load_response.status_code}{Fore.RESET}")
            return False
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️ Помилка перезавантаження моделі: {e}{Fore.RESET}")
        return False


def call_endpoint(endpoint: Dict[str, Any], messages: List[Dict[str, str]]) -> Tuple[bool, str]:
    """Виконати HTTP запит до LLM endpoint. Повертає (success: bool, result_or_error).
    
    Підтримує два формати:
    - OpenAI-compatible: /v1/chat/completions з messages
    - LM Studio v1: /api/v1/chat з input
    
    Args:
        endpoint: Endpoint конфігурація
        messages: Список повідомлень для відправки
        
    Returns:
        Tuple з (success: bool, result_or_error)
    """
    headers = {"Content-Type": "application/json"}
    if endpoint.get("api_key"):
        headers["Authorization"] = f"Bearer {endpoint['api_key']}"
    
    # Визначаємо формат API за URL
    is_v1_api = "/api/v1/chat" in endpoint.get("url", "")
    
    try:
        start_time = time.time()
        
        if is_v1_api:
            # LM Studio v1 API format
            # Конвертуємо messages в один input (останнє повідомлення користувача)
            user_messages = [m["content"] for m in messages if m.get("role") == "user"]
            input_text = user_messages[-1] if user_messages else ""
            
            payload = {
                "model": endpoint["model"],
                "input": input_text,
            }
        else:
            # OpenAI-compatible format
            payload = {
                "model": endpoint["model"],
                "messages": messages,
                "temperature": endpoint.get("temperature", 0.1),
                "max_tokens": endpoint.get("max_tokens", 1024),
                "stream": False
            }
        
        response = requests.post(
            endpoint["url"],
            headers=headers,
            json=payload,
            timeout=40  # Фіксований таймаут 40 секунд
        )
        elapsed = time.time() - start_time
        print(f"{Fore.LIGHTBLACK_EX}⏱️  LLM час: {elapsed:.1f}с")
        
        if response.status_code != 200:
            error_text = response.text[:300]
            
            # Перевіряємо чи це помилка вивантаженої моделі
            if "Cannot find model" in error_text or "model.*unloaded" in error_text.lower() or "already been unloaded" in error_text.lower():
                print(f"{Fore.YELLOW}⚠️ Модель вивантажено, пробую перезавантажити...{Fore.RESET}")
                if _reload_model(endpoint, headers):
                    # Повторюємо запит після перезавантаження
                    start_time = time.time()
                    response = requests.post(
                        endpoint["url"],
                        headers=headers,
                        json=payload,
                        timeout=40
                    )
                    elapsed = time.time() - start_time
                    print(f"{Fore.LIGHTBLACK_EX}⏱️  LLM час (retry): {elapsed:.1f}с")
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result.get("content", "")
                        if content and content.strip():
                            return True, content
            
            return False, f"HTTP {response.status_code}: {error_text}"
        
        result = response.json()
        
        if is_v1_api:
            # LM Studio v1 API response format
            content = result.get("content", "")
            if not content or not content.strip():
                return False, "empty content"
        else:
            # OpenAI-compatible response format
            if 'choices' not in result or not result['choices']:
                print(f"{Fore.LIGHTBLACK_EX}[DEBUG] LLM response (no choices): {str(result)[:500]}")
                return False, "empty choices"
            message = result['choices'][0].get('message', {})
            content = message.get('content', '')
            if not content or not content.strip():
                # Можливо контент в delta (для stream=False деякі API повертають delta)
                delta = result['choices'][0].get('delta', {})
                content = delta.get('content', '')
                if not content or not content.strip():
                    print(f"{Fore.LIGHTBLACK_EX}[DEBUG] LLM response (empty content): message={message}, delta={delta}")
                    return False, "empty content"
        
        return True, content
    except requests.exceptions.ConnectionError:
        return False, "connection error"
    except Exception as e:
        return False, str(e)
