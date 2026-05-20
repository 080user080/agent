"""Web conditions for Watcher (Phase 8.3).

Доступні умови для моніторингу веб-ресурсів та API.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:
    import requests
except Exception:  # noqa: BLE001
    requests = None  # type: ignore


def condition_url_response_contains(
    url: str,
    pattern: str,
    timeout: float = 30.0,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
) -> bool:
    """Перевірити, що HTTP-відповідь з `url` містить `pattern`.

    Args:
        url: Адреса для запиту.
        pattern: Регулярний вираз або підстрока для пошуку в тілі відповіді.
        timeout: Максимальний час очікування відповіді (секунди).
        headers: Додаткові HTTP-заголовки.
        method: HTTP метод (GET, POST, ...).

    Returns:
        True якщо запит успішний і тіло відповіді містить pattern.
    """
    if requests is None:
        return False
    try:
        req_headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentBot/1.0)"}
        if headers:
            req_headers.update(headers)
        response = requests.request(method, url, headers=req_headers, timeout=timeout)
        response.raise_for_status()
        return bool(re.search(pattern, response.text))
    except Exception:  # noqa: BLE001
        return False


def condition_url_status_ok(url: str, timeout: float = 30.0) -> bool:
    """Перевірити, що URL повертає HTTP 200."""
    if requests is None:
        return False
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgentBot/1.0)"},
            timeout=timeout,
        )
        return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def condition_chat_idle(chat_provider, idle_seconds: float = 5.0) -> bool:
    """Перевірити, що інший ШІ-асистент (chat_provider) закінчив відповідь.

    Args:
        chat_provider: Об'єкт з методом `is_responding() -> bool`.
        idle_seconds: Час без відповіді (секунди).

    Returns:
        True якщо chat_provider не відповідає щонайменше `idle_seconds`.
    """
    try:
        if hasattr(chat_provider, "is_responding"):
            if not chat_provider.is_responding():
                return True
            time.sleep(idle_seconds)
            return not chat_provider.is_responding()
        if hasattr(chat_provider, "last_response_time"):
            last = getattr(chat_provider, "last_response_time", 0)
            return (time.time() - last) >= idle_seconds
    except Exception:  # noqa: BLE001
        pass
    return False
