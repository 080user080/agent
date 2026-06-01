"""observe — фаза спостереження AgentLoop.

Містить логіку збору системного контексту: скріншоти, OCR, UI-елементи,
UIA-дерево, активне вікно та Vision-LM опис.

Трансформовано з AgentLoop.observe() для модульності (Issue #Phase2).
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("observe")

# ─── Кешування імпортів для продуктивності ─────────────────────────────────────

_SCREEN_CAPTURE_AVAILABLE = False
try:
    from functions.tools.tools_screen_capture import take_screenshot
    from functions.tools.tools_ocr import ocr_image
    from functions.tools.tools_ui_accessibility import get_uia_wrapper

    _SCREEN_CAPTURE_AVAILABLE = True
except ImportError:
    take_screenshot = None  # type: ignore[assignment]
    ocr_image = None  # type: ignore[assignment]
    get_uia_wrapper = None  # type: ignore[assignment]


# ─── Конфігурація фази спостереження ──────────────────────────────────────────


@dataclass
class ObserveConfig:
    """Конфігурація для observe() — які канали збору інформації ввімкнено."""

    enable_ocr: bool = True
    """Чи виконувати OCR зі скріншоту."""

    enable_uia: bool = False
    """Чи збирати UIA-дерево активного вікна."""

    enable_vision: bool = False
    """Чи використовувати Vision-LM модель для опису екрану."""

    enable_ui_elements: bool = True
    """Чи збирати список видимих UI-елементів (кнопки, поля вводу)."""

    skip_observe_for_simple: bool = False
    """Якщо True — пропускати скріншоти для задач, що не потребують екрану."""


# ─── Результат спостереження ──────────────────────────────────────────────────


@dataclass
class Observation:
    """Результат observe() — поточний стан системи.

    Зберігає всю інформацію, зібрану під час фази спостереження:
    скріншот, OCR-текст, UI-елементи, UIA-дерево, Vision-опис тощо.
    """

    screenshot_path: str = ""
    """Шлях до файлу зі скріншотом екрану."""

    ocr_text: str = ""
    """Текст, розпізнаний зі скріншоту через OCR."""

    screen_hash: str = ""
    """MD5 хеш файлу скріншоту для швидкого порівняння."""

    timestamp: float = 0.0
    """Unix timestamp моменту створення спостереження."""

    active_window_title: str = ""
    """Заголовок активного вікна."""

    ui_elements: List[Dict[str, Any]] = field(default_factory=list)
    """Список знайдених UI-елементів (кнопки, поля вводу)."""

    uia_tree: Optional[Dict[str, Any]] = None
    """UIA-дерево активного вікна (опційно)."""

    vision_description: str = ""
    """Текстовий опис екрану від Vision-LM моделі."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Додаткові метадані (помилки, довжина OCR, тощо)."""


# ─── Допоміжні функції ────────────────────────────────────────────────────────


def hash_screenshot(path: str) -> str:
    """Порахувати MD5 хеш файлу скріншоту.

    Оптимізація: читаємо файл частинами по 8KB для великих файлів.

    Args:
        path: Шлях до файлу скріншоту.

    Returns:
        MD5 хеш файлу або порожній рядок при помилці.
    """
    try:
        hash_md5 = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""


def get_active_window_title() -> str:
    """Повернути заголовок активного вікна.

    Використовує два fallback-механізми:
    1. pygetwindow (чистий Python)
    2. win32gui (Windows API)

    Returns:
        Заголовок активного вікна або порожній рядок.
    """
    try:
        import pygetwindow  # type: ignore

        w = pygetwindow.getActiveWindow()
        if w:
            return str(getattr(w, "title", "") or "")
    except Exception:
        pass
    try:
        import win32gui  # type: ignore

        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            return str(win32gui.GetWindowText(hwnd) or "")
    except Exception:
        pass
    return ""


def collect_ui_elements() -> List[Dict[str, Any]]:
    """Зібрати список видимих UI-елементів через ui_detector/app_recognizer.

    Returns:
        Список знайдених елементів з типом, текстом та координатами.
        Порожній список при помилці або недоступності модулів.
    """
    elements: List[Dict[str, Any]] = []
    # Спроба через tools_ui_detector
    try:
        from functions.tools.tools_ui_detector import (
            find_button_by_text,
            find_input_field,
        )

        buttons = find_button_by_text(text="*")
        if isinstance(buttons, dict) and buttons.get("ok"):
            for b in buttons.get("matches", []) or []:
                elements.append(
                    {
                        "type": "button",
                        "text": b.get("text", ""),
                        "x": b.get("x"),
                        "y": b.get("y"),
                        "w": b.get("w"),
                        "h": b.get("h"),
                    }
                )
        inputs = find_input_field()
        if isinstance(inputs, dict) and inputs.get("ok"):
            for i in inputs.get("matches", []) or []:
                elements.append(
                    {
                        "type": "input",
                        "text": i.get("label", ""),
                        "x": i.get("x"),
                        "y": i.get("y"),
                        "w": i.get("w"),
                        "h": i.get("h"),
                    }
                )
    except Exception as e:
        logger.debug("collect_ui_elements: tools_ui_detector unavailable: %s", e)
    return elements


def safe_uia_dict(element) -> Dict[str, Any]:
    """Безпечне dict-представлення UIA-елемента.

    Args:
        element: UIA-елемент (comtypes object).

    Returns:
        Словник з основними властивостями елемента.
    """
    try:
        rect = getattr(element, "rect", None)
        return {
            "name": getattr(element, "name", ""),
            "control_type": getattr(element, "control_type", ""),
            "rect": rect.__dict__ if rect and hasattr(rect, "__dict__") else None,
            "is_enabled": getattr(element, "is_enabled", None),
            "is_visible": getattr(element, "is_visible", None),
        }
    except Exception:
        return {}


def build_uia_tree(uia) -> Optional[Dict[str, Any]]:
    """Зібрати скорочене UIA-дерево активного вікна для LLM.

    Args:
        uia: UIA wrapper об'єкт з методом get_ui_tree().

    Returns:
        Словник дерева або focused-element fallback.
        None при помилці або недоступності.
    """
    try:
        if hasattr(uia, "get_ui_tree"):
            tree = uia.get_ui_tree()
            if isinstance(tree, dict):
                return tree
        # Fallback — просто focused
        focused = uia.get_focused_element()
        if focused:
            return {"focused": safe_uia_dict(focused)}
    except Exception:
        return None
    return None


def needs_screen_observation(task: str) -> bool:
    """Чи потрібен скріншот для цієї задачі?

    Аналізує текст задачі на наявність індикаторів GUI-взаємодії.

    Args:
        task: Текст задачі.

    Returns:
        True якщо задача потребує аналізу екрану.
    """
    # Normalize for performance: to lower once, not per word
    lower = task.lower()
    gui_indicators = [
        "екран",
        "вікно",
        "кнопк",
        "клік",
        "програм",
        "screen",
        "window",
        "button",
        "click",
        "app",
        "знайди на",
        "відкрий браузер",
        "натисни",
    ]
    return any(ind in lower for ind in gui_indicators)


# ─── Основна функція спостереження ────────────────────────────────────────────


def observe(
    config: ObserveConfig,
    assistant=None,
    task: str = "",
) -> Observation:
    """Отримати поточний стан системи.

    Збирає скріншот, OCR-текст, UI-елементи, UIA-дерево та Vision-LM опис
    відповідно до переданої конфігурації.

    Args:
        config: Конфігурація фази спостереження (які канали ввімкнено).
        assistant: Assistant object для Vision-LM провайдера (опційно).
        task: Текст поточної задачі (для skip_observe_for_simple).

    Returns:
        Observation з усіма зібраними даними.
    """
    logger.info("observe() called")
    obs = Observation(timestamp=time.time())

    # Якщо задача не потребує екрану — повернути мінімальне спостереження
    if config.skip_observe_for_simple and task:
        if not needs_screen_observation(task):
            print("[observe] ⏭️ Скріншот пропущено — задача не потребує екрану")
            obs.metadata["skipped"] = True
            obs.metadata["skip_reason"] = "task does not need screen"
            return obs

    try:
        # 1. Скріншот (тільки якщо потрібен для vision/OCR)
        if (config.enable_vision or config.enable_ocr) and _SCREEN_CAPTURE_AVAILABLE:
            result = take_screenshot()
            if result.get("ok") and result.get("path"):
                obs.screenshot_path = result["path"]
                obs.screen_hash = hash_screenshot(obs.screenshot_path)

        # 2. Активне вікно (для контексту LLM)
        try:
            obs.active_window_title = get_active_window_title()
        except Exception as e:
            logger.debug("observe: active window detection error: %s", e)
            obs.metadata["active_window_error"] = str(e)

        # 3. OCR
        if config.enable_ocr and obs.screenshot_path and _SCREEN_CAPTURE_AVAILABLE:
            try:
                result_ocr = ocr_image({"image_path": obs.screenshot_path})
                if result_ocr.get("ok") and result_ocr.get("text"):
                    obs.ocr_text = result_ocr["text"]
                    obs.metadata["ocr_length"] = len(obs.ocr_text)
            except Exception as e:
                logger.debug("observe: OCR error: %s", e)
                obs.metadata["ocr_error"] = str(e)

        # 4. UI елементи (кнопки + поля вводу)
        if config.enable_ui_elements and obs.screenshot_path:
            try:
                obs.ui_elements = collect_ui_elements()
            except Exception as e:
                logger.debug("observe: ui_elements collection error: %s", e)
                obs.metadata["ui_elements_error"] = str(e)

        # 5. UIA дерево
        if config.enable_uia and _SCREEN_CAPTURE_AVAILABLE:
            try:
                uia = get_uia_wrapper()
                if uia and uia.is_available():
                    focused = uia.get_focused_element()
                    if focused:
                        obs.metadata["uia_focused"] = safe_uia_dict(focused)
                    try:
                        tree = build_uia_tree(uia)
                        if tree:
                            obs.uia_tree = tree
                    except Exception as e:
                        logger.debug("observe: uia tree error: %s", e)
                        obs.metadata["uia_tree_error"] = str(e)
            except Exception as e:
                logger.debug("observe: UIA error: %s", e)
                obs.metadata["uia_error"] = str(e)

        # 6. Vision-LM (якщо ввімкнено і доступно)
        if config.enable_vision and obs.screenshot_path:
            try:
                from functions.llm.providers_vision import get_vision_provider

                vision = get_vision_provider(assistant) if assistant else None
                if vision and vision.is_available():
                    # Текстовий опис екрану
                    try:
                        desc = vision.describe(
                            obs.screenshot_path,
                            "Опиши що бачиш на екрані одним абзацом.",
                        )
                        if desc:
                            obs.vision_description = str(desc)[:1000]
                    except Exception as e:
                        logger.debug("observe: vision describe error: %s", e)
                        obs.metadata["vision_describe_error"] = str(e)
                    # Елементи (опційно — резерв)
                    try:
                        elements = vision.detect_ui_elements(obs.screenshot_path)
                        if elements:
                            obs.metadata["vision_elements"] = elements
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("observe: Vision-LM error: %s", e)
                obs.metadata["vision_error"] = str(e)

    except Exception as e:
        logger.error("observe() error: %s", e)
        obs.metadata["error"] = str(e)

    logger.debug(
        "observe: screen_hash=%s, ocr_len=%d, ui_elements=%d, window=%s",
        obs.screen_hash[:8] if obs.screen_hash else "",
        len(obs.ocr_text),
        len(obs.ui_elements),
        obs.active_window_title[:40] if obs.active_window_title else "",
    )
    return obs


__all__ = [
    "ObserveConfig",
    "Observation",
    "hash_screenshot",
    "get_active_window_title",
    "collect_ui_elements",
    "safe_uia_dict",
    "build_uia_tree",
    "needs_screen_observation",
    "observe",
]