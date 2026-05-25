# functions/llm/endpoint_client.py
"""Endpoint client for LLM API calls."""
import time
import requests
from typing import Dict, Any, List, Optional, Tuple
from colorama import Fore
from ..config import LM_STUDIO_URL

# =============================================================================
# Словник відомих моделей → max_context_tokens
# =============================================================================
# Джерела: офіційна документація OpenAI, Anthropic, Google, Groq, Meta, Mistral
KNOWN_MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # --- OpenAI ---
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
    "o1": 200000,
    "o1-mini": 128000,
    "o3-mini": 200000,

    # --- Anthropic Claude ---
    "claude-3-5-sonnet": 200000,
    "claude-3-5-haiku": 200000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-4-5-sonnet": 200000,
    "claude-4-5-haiku": 200000,
    "claude-sonnet-4-6": 200000,
    "claude-opus-4-5": 200000,

    # --- Google Gemini ---
    "gemini-2.0-flash": 1048576,
    "gemini-2.0-flash-lite": 1048576,
    "gemini-1.5-pro": 1048576,
    "gemini-1.5-flash": 1048576,
    "gemini-1.5-flash-8b": 1048576,
    "gemini-3.1-flash-lite-preview": 1048576,

    # --- Groq ---
    "llama-3.3-70b": 131072,
    "llama-3.2-90b": 131072,
    "llama-3.2-11b": 131072,
    "llama-3.1-70b": 131072,
    "llama-3.1-8b": 131072,
    "mixtral-8x7b": 32768,
    "gemma2-9b": 8192,

    # --- Meta Llama (загальні) ---
    "llama-3.1-405b": 131072,
    "llama-3.1-70b": 131072,
    "llama-3.1-8b": 131072,
    "llama-3.2-90b": 131072,
    "llama-3.2-11b": 131072,
    "llama-3.2-3b": 131072,
    "llama-3.2-1b": 131072,
    "llama-3.3-70b": 131072,

    # --- Mistral ---
    "mistral-large": 128000,
    "mistral-small": 128000,
    "mistral-7b": 32768,
    "codestral": 256000,
    "ministral-3b": 32768,
    "ministral-8b": 32768,

    # --- DeepSeek ---
    "deepseek-chat": 128000,
    "deepseek-coder": 128000,
    "deepseek-r1": 128000,
    "deepseek-v3": 128000,

    # --- Qwen ---
    "qwen-2.5-72b": 131072,
    "qwen-2.5-32b": 131072,
    "qwen-2.5-14b": 32768,
    "qwen-2.5-7b": 32768,
    "qwen-2-72b": 32768,

    # --- Інші популярні локальні моделі ---
    "phi-4": 16384,
    "phi-3-medium": 128000,
    "phi-3-mini": 128000,
    "nous-hermes-2-mixtral": 32768,
    "dolphin-2.9-llama3": 8192,
    "solar-10.7b": 4096,

    # --- Дефолт для невідомих моделей ---
    "local-model": 4096,  # LM Studio default
}

# Ліміт за замовчуванням, якщо модель не знайдено в словнику
_DEFAULT_CONTEXT_LIMIT = 4096


def get_model_context_limit(model_name: str) -> int:
    """Повертає ліміт контексту (max_context_tokens) для заданої моделі.

    Стратегія пошуку:
    1. Точний збіг у KNOWN_MODEL_CONTEXT_LIMITS
    2. Частковий збіг (модель містить відомий префікс, наприклад "gpt-4o-*")
    3. Запит до /v1/models (для локальних серверів OpenAI-compatible)
    4. Повернення _DEFAULT_CONTEXT_LIMIT, якщо нічого не знайдено

    Args:
        model_name: Назва моделі (наприклад, "gpt-4o", "claude-3-5-sonnet-20241022")

    Returns:
        int: Максимальна кількість токенів контексту
    """
    if not model_name:
        return _DEFAULT_CONTEXT_LIMIT

    # 1. Точний збіг
    exact = KNOWN_MODEL_CONTEXT_LIMITS.get(model_name)
    if exact is not None:
        return exact

    # 2. Частковий збіг: шукаємо за префіксом (наприклад, "gpt-4o" підходить для "gpt-4o-2024-08-06")
    # Сортуємо за довжиною (найдовші префікси першими) для найточнішого збігу
    model_lower = model_name.lower()
    known_names = sorted(KNOWN_MODEL_CONTEXT_LIMITS.keys(), key=len, reverse=True)
    for known in known_names:
        known_lower = known.lower()
        if model_lower.startswith(known_lower):
            return KNOWN_MODEL_CONTEXT_LIMITS[known]
        # Також перевіряємо чи містить модель відому назву (наприклад, "llama-3.1-70b" в "meta/llama-3.1-70b")
        if known_lower in model_lower:
            return KNOWN_MODEL_CONTEXT_LIMITS[known]

    # 3. Для невідомих моделей повертаємо дефолт
    return _DEFAULT_CONTEXT_LIMIT


def fetch_local_model_context_limit(
    base_url: str,
    api_key: str = "",
    timeout: int = 10,
) -> Optional[int]:
    """Спроба отримати ліміт контексту для локальної моделі через /v1/models.

    Використовується для LM Studio, Ollama, або будь-якого OpenAI-compatible
    сервера, що підтримує ендпоінт GET /v1/models.

    Args:
        base_url: Базовий URL сервера (наприклад, "http://localhost:1234")
        api_key: API ключ (якщо потрібен)
        timeout: Таймаут запиту в секундах

    Returns:
        Optional[int]: Ліміт контексту або None, якщо не вдалося отримати
    """
    try:
        # Формуємо URL для /v1/models
        models_url = base_url.rstrip("/")
        if models_url.endswith("/chat/completions"):
            models_url = models_url.replace("/chat/completions", "/models")
        elif models_url.endswith("/chat"):
            models_url = models_url.replace("/chat", "/models")
        else:
            models_url = models_url + "/models"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = requests.get(
            models_url,
            headers=headers,
            timeout=timeout,
        )

        if response.status_code != 200:
            return None

        data = response.json()

        # OpenAI-compatible формат: {"data": [{"id": "...", "max_context_length": N}]}
        models = data.get("data", [])
        for model_info in models:
            # Пробуємо різні поля, які можуть містити ліміт контексту
            for field in ("max_context_length", "context_length", "max_context_tokens",
                          "max_total_tokens", "context_window", "max_model_len"):
                val = model_info.get(field)
                if val is not None:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass

        # Ollama формат: {"models": [{"name": "...", "details": {"parameter_size": "...", ...}}]}
        # В Ollama ліміт не повертається через API, тому повертаємо None
        models = data.get("models", [])
        for model_info in models:
            for field in ("max_context_length", "context_length"):
                val = model_info.get(field)
                if val is not None:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass

        return None
    except Exception:
        return None


# =============================================================================
# Решта функцій (без змін)
# =============================================================================


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
        "timeout": ep.get("timeout", 180) or 180,
        "name": ep.get("name", "LLM"),  # Зберігаємо назву endpoint
    }


def get_endpoint_by_role(role: str, default: Optional[Dict] = None) -> Optional[Dict]:
    """Отримати активний LLM endpoint з певною роллю з налаштувань.

    Args:
        role: Роль endpoint'у (наприклад, "primary", "secondary", "fallback", "alternative" або "1", "2", "3", "4")
        default: Дефолтне значення, якщо endpoint не знайдено

    Returns:
        Dict з url, model, api_key, temperature, max_tokens, timeout або default або None
    """
    try:
        from ..runtime.core_settings import get_setting
        endpoints = get_setting("LLM_ENDPOINTS", [])

        # Шукаємо endpoint за role напряму (чи то число, чи то текст)
        for ep in endpoints:
            if (ep.get("enabled") and ep.get("role") == role
                and ep.get("model") and ep.get("url")):
                return _normalize_endpoint(ep)

        # Якщо не знайдено за role, пробуємо мапінг для сумісності зі старими даними
        role_map = {"1": "primary", "2": "secondary", "3": "fallback", "4": "alternative"}
        # Якщо role — це число, пробуємо знайти за текстовим еквівалентом
        target_role = role_map.get(role)
        if target_role:
            for ep in endpoints:
                if (ep.get("enabled") and ep.get("role") == target_role
                    and ep.get("model") and ep.get("url")):
                    return _normalize_endpoint(ep)

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
    try:
        from ..runtime.core_settings import get_setting
        endpoints = get_setting("LLM_ENDPOINTS", [])

        # Шукаємо endpoint з role="1"
        primary = get_endpoint_by_role("1", None)
        if primary:
            return primary

        # Якщо не знайдено role="1", шукаємо endpoint з найменшим цифровим role
        enabled_endpoints = [ep for ep in endpoints if ep.get("enabled") and ep.get("model") and ep.get("url")]
        if enabled_endpoints:
            # Сортуємо за цифровим role
            def get_role_order(ep):
                try:
                    return int(ep.get("role", 999)) if ep.get("role") else 999
                except (ValueError, TypeError):
                    # Для сумісності зі старими текстовими role
                    role_map = {"primary": 1, "secondary": 2, "fallback": 3, "alternative": 4}
                    return role_map.get(ep.get("role"), 999)

            enabled_endpoints.sort(key=get_role_order)
            result = _normalize_endpoint(enabled_endpoints[0])
            print(f"[DEBUG] Using endpoint with smallest role: {enabled_endpoints[0].get('role')} - {enabled_endpoints[0].get('name', 'unknown')}")
            return result
        print(f"[DEBUG] No enabled endpoints with model and url found")
    except Exception as e:
        print(f"[DEBUG] Exception in get_primary_endpoint: {e}")

    # Дефолтне значення
    print(f"[DEBUG] Using default LM Studio endpoint")
    return {
        "url": LM_STUDIO_URL,
        "model": "local-model",
        "api_key": "",
        "temperature": 0.1,
        "max_tokens": 1024,
        "timeout": 180,
    }


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
            # DEBUG: перевірка розміру system prompt
            print(f"[DEBUG] system_prompt chars: {len(messages[0]['content'])}")
        
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