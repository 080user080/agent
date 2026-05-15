"""Image processing tool using Pillow (Phase 10).

Provides functions for:
- Opening, reading, saving images
- Resizing, cropping, rotating images
- Converting between formats
- Applying filters and effects
- Adding text to images
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    PILLOW_AVAILABLE = True
except Exception:
    PILLOW_AVAILABLE = False


def open_image(file_path: str) -> Dict[str, Any]:
    """Відкрити зображення.

    Args:
        file_path: Шлях до файлу зображення

    Returns:
        dict з success, image_object, width, height, mode, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний (pip install Pillow)"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        img = Image.open(file_path)
        return {
            "success": True,
            "image": img,
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format
        }
    except Exception as e:
        return {"success": False, "error": f"Помилка відкриття: {str(e)}"}


def save_image(img: Any, file_path: str, quality: int = 95) -> Dict[str, Any]:
    """Зберегти зображення.

    Args:
        img: PIL Image об'єкт
        file_path: Шлях для збереження
        quality: Якість для JPEG (1-100)

    Returns:
        dict з success, file_path, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        # Створити директорію якщо не існує
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Визначити формат по розширенню
        ext = Path(file_path).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            img.save(file_path, quality=quality, optimize=True)
        else:
            img.save(file_path)
        
        return {"success": True, "file_path": file_path}
    except Exception as e:
        return {"success": False, "error": f"Помилка збереження: {str(e)}"}


def resize_image(img: Any, width: int, height: Optional[int] = None, maintain_aspect: bool = True) -> Dict[str, Any]:
    """Змінити розмір зображення.

    Args:
        img: PIL Image об'єкт
        width: Нова ширина
        height: Нова висота (якщо None, обчислюється автоматично)
        maintain_aspect: Зберігати співвідношення сторін

    Returns:
        dict з success, resized_image, new_width, new_height, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        if maintain_aspect and height is None:
            ratio = width / img.width
            height = int(img.height * ratio)
        
        resized = img.resize((width, height), Image.Resampling.LANCZOS)
        return {
            "success": True,
            "image": resized,
            "width": width,
            "height": height
        }
    except Exception as e:
        return {"success": False, "error": f"Помилка зміни розміру: {str(e)}"}


def crop_image(img: Any, left: int, top: int, right: int, bottom: int) -> Dict[str, Any]:
    """Обрізати зображення.

    Args:
        img: PIL Image об'єкт
        left: Ліва межа
        top: Верхня межа
        right: Права межа
        bottom: Нижня межа

    Returns:
        dict з success, cropped_image, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        cropped = img.crop((left, top, right, bottom))
        return {"success": True, "image": cropped}
    except Exception as e:
        return {"success": False, "error": f"Помилка обрізки: {str(e)}"}


def rotate_image(img: Any, degrees: float) -> Dict[str, Any]:
    """Повернути зображення.

    Args:
        img: PIL Image об'єкт
        degrees: Кут повороту в градусах (проти годинникової стрілки)

    Returns:
        dict з success, rotated_image, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        rotated = img.rotate(degrees, expand=True)
        return {"success": True, "image": rotated}
    except Exception as e:
        return {"success": False, "error": f"Помилка повороту: {str(e)}"}


def convert_format(img: Any, target_format: str) -> Dict[str, Any]:
    """Конвертувати зображення в інший формат.

    Args:
        img: PIL Image об'єкт
        target_format: Цільовий формат (RGB, RGBA, L, CMYK)

    Returns:
        dict з success, converted_image, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        converted = img.convert(target_format)
        return {"success": True, "image": converted, "mode": converted.mode}
    except Exception as e:
        return {"success": False, "error": f"Помилка конвертації: {str(e)}"}


def apply_blur(img: Any, radius: float = 2.0) -> Dict[str, Any]:
    """Застосувати розмиття.

    Args:
        img: PIL Image об'єкт
        radius: Радіус розмиття

    Returns:
        dict з success, blurred_image, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        blurred = img.filter(ImageFilter.GaussianBlur(radius))
        return {"success": True, "image": blurred}
    except Exception as e:
        return {"success": False, "error": f"Помилка розмиття: {str(e)}"}


def adjust_brightness(img: Any, factor: float = 1.0) -> Dict[str, Any]:
    """Налаштувати яскравість.

    Args:
        img: PIL Image об'єкт
        factor: Фактор яскравості (1.0 = без змін, >1.0 = яскравіше, <1.0 = темніше)

    Returns:
        dict з success, adjusted_image, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        enhancer = ImageEnhance.Brightness(img)
        adjusted = enhancer.enhance(factor)
        return {"success": True, "image": adjusted}
    except Exception as e:
        return {"success": False, "error": f"Помилка яскравості: {str(e)}"}


def adjust_contrast(img: Any, factor: float = 1.0) -> Dict[str, Any]:
    """Налаштувати контраст.

    Args:
        img: PIL Image об'єкт
        factor: Фактор контрасту (1.0 = без змін, >1.0 = більше контрасту, <1.0 = менше контрасту)

    Returns:
        dict з success, adjusted_image, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        enhancer = ImageEnhance.Contrast(img)
        adjusted = enhancer.enhance(factor)
        return {"success": True, "image": adjusted}
    except Exception as e:
        return {"success": False, "error": f"Помилка контрасту: {str(e)}"}


def add_text_to_image(
    img: Any,
    text: str,
    position: Tuple[int, int] = (10, 10),
    size: int = 20,
    color: str = "white"
) -> Dict[str, Any]:
    """Додати текст на зображення.

    Args:
        img: PIL Image об'єкт
        text: Текст для додавання
        position: Позиція тексту (x, y)
        size: Розмір шрифту
        color: Колір тексту

    Returns:
        dict з success, image_with_text, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        # Створити копію для уникнення модифікації оригіналу
        img_copy = img.copy()
        draw = ImageDraw.Draw(img_copy)
        
        # Спробувати використати дефолтний шрифт
        try:
            font = ImageFont.truetype("arial.ttf", size)
        except:
            font = ImageFont.load_default()
        
        draw.text(position, text, fill=color, font=font)
        return {"success": True, "image": img_copy}
    except Exception as e:
        return {"success": False, "error": f"Помилка додавання тексту: {str(e)}"}


def get_image_info(img: Any) -> Dict[str, Any]:
    """Отримати інформацію про зображення.

    Args:
        img: PIL Image об'єкт

    Returns:
        dict з success, width, height, mode, format, size_bytes, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        return {
            "success": True,
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
            "size_bytes": len(img.tobytes()) if hasattr(img, 'tobytes') else 0
        }
    except Exception as e:
        return {"success": False, "error": f"Помилка отримання інформації: {str(e)}"}


def create_thumbnail(img: Any, size: Tuple[int, int] = (128, 128)) -> Dict[str, Any]:
    """Створити ескіз зображення.

    Args:
        img: PIL Image об'єкт
        size: Розмір ескізу (width, height)

    Returns:
        dict з success, thumbnail_image, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний"}

    try:
        img_copy = img.copy()
        img_copy.thumbnail(size, Image.Resampling.LANCZOS)
        return {
            "success": True,
            "image": img_copy,
            "width": img_copy.width,
            "height": img_copy.height
        }
    except Exception as e:
        return {"success": False, "error": f"Помилка створення ескізу: {str(e)}"}
