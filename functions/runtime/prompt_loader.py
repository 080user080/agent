"""prompt_loader — завантаження JSON-шаблонів системних промптів.

Винесено з FunctionRegistry.get_system_prompt() (Phase 7.3).
Шаблони зберігаються в ``runtime/prompts/*.json`` та можуть
перезавантажуватися без перезапуску програми.

Usage::

    from functions.runtime.prompt_loader import load_prompt_template
    template = load_prompt_template("voice_prompt")
    prompt = template.format(ASSISTANT_NAME="Марк", ...)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("prompt_loader")

# Директорія з JSON-шаблонами промптів
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "runtime" / "prompts"

# Кеш завантажених шаблонів (щоб не читати файл кожного разу)
_template_cache: dict[str, str] = {}


def load_prompt_template(name: str, *, force_reload: bool = False) -> str:
    """Завантажити шаблон системного промпту з JSON-файлу.

    Args:
        name: Назва шаблону (без розширення .json).
              Наприклад, ``"voice_prompt"`` або ``"coding_prompt"``.
        force_reload: Якщо True — ігнорувати кеш та перечитати файл.

    Returns:
        Текст шаблону (поле ``"template"`` з JSON).

    Raises:
        FileNotFoundError: Якщо JSON-файл не знайдено.
        KeyError: Якщо поле ``"template"`` відсутнє у JSON.
    """
    if not force_reload and name in _template_cache:
        return _template_cache[name]

    path = PROMPTS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    template = data.get("template")
    if template is None:
        raise KeyError(f"Field 'template' not found in {path}")

    _template_cache[name] = template
    logger.debug("Loaded prompt template '%s' (%d chars)", name, len(template))
    return template


def reload_prompt_template(name: str) -> str:
    """Перезавантажити шаблон з файлу (очистити кеш).

    Args:
        name: Назва шаблону (без .json).

    Returns:
        Оновлений текст шаблону.
    """
    return load_prompt_template(name, force_reload=True)


def clear_cache() -> None:
    """Очистити кеш усіх шаблонів."""
    _template_cache.clear()
    logger.debug("Prompt template cache cleared")


__all__ = [
    "load_prompt_template",
    "reload_prompt_template",
    "clear_cache",
    "PROMPTS_DIR",
]