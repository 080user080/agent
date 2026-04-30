"""OpenAI tool-calling schema для AgentLoop.

Цей модуль описує всі дії, які агент може виконати на комп'ютері,
у форматі OpenAI `tools` (`type=function`). Використовується `ActionDecider`
у `agent_loop.py`, щоб LLM повертав структуровані `tool_calls` замість
самописного JSON.

Групи інструментів:

- ``AGENT_TOOLS`` — базові GUI-дії: миша, клавіатура, скрін, OCR,
  пошук UI-елементів, керування програмами, спеціальний інструмент ``done``.
- ``VISION_TOOLS`` — vision-LM дії (опис екрану, пошук за описом, перевірка стану).
- ``UIA_TOOLS`` — Windows UI Automation (структурні кліки, ввід тексту, читання значення).
- ``BROWSER_TOOLS`` — браузерна автоматизація через Playwright/CDP.

``ALL_AGENT_TOOLS`` — повна об'єднана збірка всіх інструментів.
``TOOL_NAME_ALIASES`` — мапа alias → реальне ім'я в `FunctionRegistry`,
бо деякі імена в registry відрізняються від «зручних» імен для LLM.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

# --------------------------------------------------------------------------- #
# Helper                                                                       #
# --------------------------------------------------------------------------- #


def _tool(
    name: str,
    description: str,
    properties: Optional[Mapping[str, Any]] = None,
    required: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Зібрати один OpenAI tool-spec."""
    params: Dict[str, Any] = {
        "type": "object",
        "properties": dict(properties or {}),
    }
    if required:
        params["required"] = list(required)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": params,
        },
    }


# --------------------------------------------------------------------------- #
# AGENT_TOOLS — базові GUI-дії                                                #
# --------------------------------------------------------------------------- #

AGENT_TOOLS: List[Dict[str, Any]] = [
    _tool(
        name="mouse_click",
        description="Клікнути мишею у вказані координати екрану.",
        properties={
            "x": {"type": "integer", "description": "X-координата (пікселі)."},
            "y": {"type": "integer", "description": "Y-координата (пікселі)."},
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "default": "left",
                "description": "Кнопка миші.",
            },
            "clicks": {
                "type": "integer",
                "default": 1,
                "description": "Кількість кліків (1 для звичайного, 2 для double).",
            },
        },
        required=["x", "y"],
    ),
    _tool(
        name="mouse_move",
        description="Перемістити курсор у вказані координати без кліку.",
        properties={
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "duration": {"type": "number", "default": 0.2},
        },
        required=["x", "y"],
    ),
    _tool(
        name="mouse_scroll",
        description="Прокрутити колесо миші.",
        properties={
            "clicks": {
                "type": "integer",
                "description": "Додатне = вгору, від'ємне = вниз.",
            },
            "x": {"type": "integer", "description": "X (опційно)."},
            "y": {"type": "integer", "description": "Y (опційно)."},
        },
        required=["clicks"],
    ),
    _tool(
        name="keyboard_type",
        description="Ввести текст з клавіатури в активне поле.",
        properties={
            "text": {"type": "string", "description": "Текст для вводу."},
            "interval": {
                "type": "number",
                "default": 0.02,
                "description": "Затримка між символами (сек).",
            },
        },
        required=["text"],
    ),
    _tool(
        name="keyboard_press",
        description="Натиснути одну клавішу (Enter, Tab, Escape, F1...).",
        properties={
            "key": {"type": "string", "description": "Назва клавіші."},
        },
        required=["key"],
    ),
    _tool(
        name="keyboard_hotkey",
        description="Натиснути комбінацію клавіш, наприклад ['ctrl', 's'].",
        properties={
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список клавіш у послідовності натискання.",
            },
        },
        required=["keys"],
    ),
    _tool(
        name="take_screenshot",
        description="Зробити скріншот всього екрану. Повертає шлях до файлу.",
        properties={},
    ),
    _tool(
        name="ocr_screen",
        description="Прочитати весь видимий текст з екрану через OCR.",
        properties={
            "lang": {
                "type": "string",
                "default": "ukr+eng",
                "description": "Мови OCR.",
            },
        },
    ),
    _tool(
        name="find_text_on_screen",
        description="Знайти координати тексту на екрані через OCR.",
        properties={
            "text": {"type": "string", "description": "Текст для пошуку."},
            "lang": {"type": "string", "default": "ukr+eng"},
        },
        required=["text"],
    ),
    _tool(
        name="click_text",
        description="Знайти текст на екрані (OCR/UIA) і клікнути по ньому.",
        properties={
            "text": {"type": "string", "description": "Текст для пошуку та кліку."},
        },
        required=["text"],
    ),
    _tool(
        name="find_button_by_text",
        description="Знайти кнопку за текстом і повернути її координати.",
        properties={
            "text": {"type": "string"},
            "confidence": {"type": "number", "default": 0.7},
        },
        required=["text"],
    ),
    _tool(
        name="find_input_field",
        description="Знайти поле вводу (за міткою або поряд з текстом).",
        properties={
            "label": {"type": "string", "description": "Мітка біля поля."},
        },
    ),
    _tool(
        name="open_program",
        description="Відкрити програму за назвою (notepad, chrome, code...).",
        properties={
            "program_name": {
                "type": "string",
                "description": "Назва програми або шлях до .exe.",
            },
            "args": {
                "type": "string",
                "default": "",
                "description": "Аргументи командного рядка.",
            },
        },
        required=["program_name"],
    ),
    _tool(
        name="close_program",
        description="Закрити програму за назвою або PID.",
        properties={
            "program_name": {"type": "string"},
        },
        required=["program_name"],
    ),
    _tool(
        name="activate_window_by_title",
        description="Активувати (винести наперед) вікно за заголовком.",
        properties={
            "title": {"type": "string", "description": "Підрядок або повний заголовок."},
        },
        required=["title"],
    ),
    _tool(
        name="wait_for_text",
        description="Чекати поки на екрані з'явиться вказаний текст.",
        properties={
            "text": {"type": "string"},
            "timeout": {"type": "number", "default": 10.0},
            "poll_interval": {"type": "number", "default": 0.5},
        },
        required=["text"],
    ),
    _tool(
        name="wait_seconds",
        description="Просто зачекати вказану кількість секунд.",
        properties={
            "seconds": {"type": "number"},
        },
        required=["seconds"],
    ),
    _tool(
        name="fill_form",
        description="Заповнити форму набором пар «мітка → значення».",
        properties={
            "fields": {
                "type": "object",
                "description": "Словник {label: value}.",
                "additionalProperties": {"type": "string"},
            },
        },
        required=["fields"],
    ),
    _tool(
        name="done",
        description=(
            "Викликати коли задача виконана. Це завершує AgentLoop. "
            "Поле `summary` має містити коротке резюме, що було зроблено."
        ),
        properties={
            "summary": {
                "type": "string",
                "description": "Резюме виконаної роботи (1–3 речення).",
            },
            "success": {
                "type": "boolean",
                "default": True,
                "description": "True — успіх, False — задача провалена.",
            },
        },
        required=["summary"],
    ),
    _tool(
        name="ask_user",
        description=(
            "Запитати користувача коли потрібна додаткова інформація. "
            "AgentLoop призупиниться до отримання відповіді."
        ),
        properties={
            "question": {"type": "string"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Опційний список варіантів відповіді.",
            },
        },
        required=["question"],
    ),
]


# --------------------------------------------------------------------------- #
# VISION_TOOLS — Vision-LM                                                    #
# --------------------------------------------------------------------------- #

VISION_TOOLS: List[Dict[str, Any]] = [
    _tool(
        name="describe_screen",
        description=(
            "Подивитися на екран через Vision-LM і отримати текстовий опис того, "
            "що відображається. Корисно коли OCR не вистачає для розуміння UI."
        ),
        properties={
            "prompt": {
                "type": "string",
                "default": "Опиши що бачиш на екрані.",
                "description": "Інструкція для vision-моделі.",
            },
        },
    ),
    _tool(
        name="find_element_by_description",
        description=(
            "Знайти елемент на екрані за описом природною мовою (через Vision-LM). "
            "Повертає bbox {x, y, w, h} знайденого елемента."
        ),
        properties={
            "description": {
                "type": "string",
                "description": "Опис елемента, наприклад 'синя кнопка Зберегти'.",
            },
        },
        required=["description"],
    ),
    _tool(
        name="is_screen_correct",
        description=(
            "Перевірити чи екран відповідає очікуваному стану (через Vision-LM). "
            "Повертає {ok: bool, reason: str}."
        ),
        properties={
            "expected_state": {
                "type": "string",
                "description": "Опис очікуваного стану екрану.",
            },
        },
        required=["expected_state"],
    ),
]


# --------------------------------------------------------------------------- #
# UIA_TOOLS — Windows UI Automation                                           #
# --------------------------------------------------------------------------- #

UIA_TOOLS: List[Dict[str, Any]] = [
    _tool(
        name="uia_click_by_name",
        description=(
            "Клікнути по елементу через Windows UI Automation за його name. "
            "Стійке до DPI/тем/локалізації порівняно з OCR-кліком."
        ),
        properties={
            "name": {"type": "string", "description": "Name елемента у дереві UIA."},
            "control_type": {
                "type": "string",
                "description": "Опційно: Button, MenuItem, ListItem...",
            },
        },
        required=["name"],
    ),
    _tool(
        name="uia_type_in_element",
        description="Ввести текст в елемент за його name через UIA.",
        properties={
            "name": {"type": "string"},
            "text": {"type": "string"},
        },
        required=["name", "text"],
    ),
    _tool(
        name="uia_get_value",
        description="Отримати значення елемента (текст у полі вводу) через UIA.",
        properties={
            "name": {"type": "string"},
        },
        required=["name"],
    ),
    _tool(
        name="uia_list_buttons",
        description="Повернути список усіх кнопок активного вікна через UIA.",
        properties={},
    ),
    _tool(
        name="uia_list_inputs",
        description="Повернути список усіх полів вводу активного вікна через UIA.",
        properties={},
    ),
    _tool(
        name="uia_wait_for_element",
        description="Чекати появи елемента за name (UIA).",
        properties={
            "name": {"type": "string"},
            "timeout": {"type": "number", "default": 10.0},
        },
        required=["name"],
    ),
]


# --------------------------------------------------------------------------- #
# BROWSER_TOOLS — Playwright / CDP                                             #
# --------------------------------------------------------------------------- #

BROWSER_TOOLS: List[Dict[str, Any]] = [
    _tool(
        name="browser_open_url",
        description="Відкрити URL у браузері (підключеному через CDP).",
        properties={
            "url": {"type": "string"},
        },
        required=["url"],
    ),
    _tool(
        name="browser_click_text",
        description="Клікнути по елементу з вказаним текстом у браузері.",
        properties={
            "text": {"type": "string"},
        },
        required=["text"],
    ),
    _tool(
        name="browser_fill",
        description="Заповнити поле за міткою/селектором.",
        properties={
            "selector_or_label": {
                "type": "string",
                "description": "Мітка поля або CSS-селектор.",
            },
            "text": {"type": "string"},
        },
        required=["selector_or_label", "text"],
    ),
    _tool(
        name="browser_screenshot",
        description="Зробити скріншот поточної сторінки браузера.",
        properties={
            "path": {
                "type": "string",
                "default": "",
                "description": "Куди зберегти (порожньо = автогенерація).",
            },
        },
    ),
    _tool(
        name="browser_extract_text",
        description="Витягти весь текст зі сторінки (innerText body).",
        properties={},
    ),
    _tool(
        name="browser_wait_for",
        description="Чекати появи тексту на сторінці.",
        properties={
            "text": {"type": "string"},
            "timeout": {"type": "number", "default": 10.0},
        },
        required=["text"],
    ),
]


# --------------------------------------------------------------------------- #
# Об'єднання + alias-мапа                                                     #
# --------------------------------------------------------------------------- #

ALL_AGENT_TOOLS: List[Dict[str, Any]] = (
    AGENT_TOOLS + VISION_TOOLS + UIA_TOOLS + BROWSER_TOOLS
)


# Деякі «зручні» імена в схемі не збігаються з фактичними іменами у
# `FunctionRegistry`. Тут — мапа alias → реальне ім'я. Розширюй за потребою.
TOOL_NAME_ALIASES: Dict[str, str] = {
    # take_screenshot як інструмент → registry виконує функцію з тим же ім'ям
    "take_screenshot": "take_screenshot",
    "ocr_screen": "ocr_screen",
    "find_text_on_screen": "find_text_on_screen",
    "click_text": "click_text",
    "find_button_by_text": "find_button_by_text",
    "find_input_field": "find_input_field",
    "wait_for_text": "wait_for_text",
    "wait_seconds": "wait_seconds",
    "fill_form": "fill_form",
    # vision
    "describe_screen": "vision_describe_screen",
    "find_element_by_description": "vision_find_element",
    "is_screen_correct": "vision_check_state",
    # UIA
    "uia_click_by_name": "uia_click_element",
    "uia_type_in_element": "uia_set_text",
    "uia_get_value": "uia_get_value",
    "uia_list_buttons": "uia_list_buttons",
    "uia_list_inputs": "uia_list_inputs",
    "uia_wait_for_element": "uia_wait_for_element",
    # Browser
    "browser_open_url": "cdp_open_tab",
    "browser_click_text": "cdp_click",
    "browser_fill": "cdp_type_text",
    "browser_screenshot": "cdp_screenshot",
    "browser_extract_text": "cdp_get_page_text",
    "browser_wait_for": "cdp_wait_for_text",
}


# Спеціальні «псевдо-інструменти» — не виконуються через registry,
# а обробляються самим AgentLoop.
SPECIAL_TOOLS = frozenset({"done", "ask_user"})


def get_tools_for_capabilities(
    *,
    enable_vision: bool = False,
    enable_uia: bool = False,
    enable_browser: bool = False,
) -> List[Dict[str, Any]]:
    """Повернути збірку інструментів відповідно до доступних capabilities.

    Базовий набір (`AGENT_TOOLS`) повертається завжди. Додаткові групи —
    тільки коли відповідний capability ввімкнений.
    """
    tools: List[Dict[str, Any]] = list(AGENT_TOOLS)
    if enable_vision:
        tools.extend(VISION_TOOLS)
    if enable_uia:
        tools.extend(UIA_TOOLS)
    if enable_browser:
        tools.extend(BROWSER_TOOLS)
    return tools


__all__ = [
    "AGENT_TOOLS",
    "VISION_TOOLS",
    "UIA_TOOLS",
    "BROWSER_TOOLS",
    "ALL_AGENT_TOOLS",
    "TOOL_NAME_ALIASES",
    "SPECIAL_TOOLS",
    "get_tools_for_capabilities",
]
