"""Модуль для корекції координат з урахуванням DPI масштабування Windows.

Цей модуль вирішує проблему коли координати від OCR/UIA бібліотек 
відрізняються від реальних координат кліку через масштабування екрана (125%, 150%).
"""

import ctypes
import logging

logger = logging.getLogger(__name__)

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("pyautogui не встановлено — get_screen_resolution недоступний")


def get_windows_scale_factor() -> float:
    """
    Отримує коефіцієнт масштабування Windows.
    
    Returns:
        float: Коефіцієнт масштабування (наприклад, 1.25 для 125%, 1.5 для 150%)
               Повертає 1.0 якщо не вдалося отримати масштаб.
    """
    try:
        # Встановлюємо DPI awareness для коректної роботи
        # 1 = PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        
        # Отримуємо масштаб для основного монітора (device 0)
        scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
        
        logger.info(f"Windows scale factor: {scale} ({int(scale * 100)}%)")
        return scale
    except Exception as e:
        logger.warning(f"Не вдалося отримати scale factor: {e}")
        return 1.0


def normalize_coordinates(x: int, y: int) -> tuple[int, int]:
    """
    Перетворює координати з OCR-простору в реальні координати кліку.
    
    Args:
        x: Координата X з OCR/UIA
        y: Координата Y з OCR/UIA
        
    Returns:
        tuple[int, int]: Нормалізовані координати для кліку
    """
    scale = get_windows_scale_factor()
    
    # Якщо масштаб 1.0 — немає потреби в корекції
    if scale == 1.0:
        return int(x), int(y)
    
    # Коригуємо координати
    real_x = int(x / scale)
    real_y = int(y / scale)
    
    logger.debug(f"Coordinates normalized: ({x}, {y}) -> ({real_x}, {real_y}) [scale={scale}]")
    return real_x, real_y


def get_screen_resolution() -> tuple[int, int] | None:
    """
    Повертає реальну роздільну здатність екрана.
    
    Returns:
        tuple[int, int] | None: (width, height) або None якщо pyautogui недоступний
    """
    if not PYAUTOGUI_AVAILABLE:
        return None
    
    try:
        width, height = pyautogui.size()
        logger.info(f"Screen resolution: {width}x{height}")
        return width, height
    except Exception as e:
        logger.warning(f"Не вдалося отримати роздільну здатність: {e}")
        return None


def denormalize_coordinates(x: int, y: int) -> tuple[int, int]:
    """
    Зворотна операція: перетворює реальні координати в масштабовані.
    
    Корисно для порівняння з координатами від OCR/UIA.
    
    Args:
        x: Реальна координата X
        y: Реальна координата Y
        
    Returns:
        tuple[int, int]: Масштабовані координати
    """
    scale = get_windows_scale_factor()
    
    if scale == 1.0:
        return int(x), int(y)
    
    scaled_x = int(x * scale)
    scaled_y = int(y * scale)
    
    logger.debug(f"Coordinates denormalized: ({x}, {y}) -> ({scaled_x}, {scaled_y}) [scale={scale}]")
    return scaled_x, scaled_y


if __name__ == "__main__":
    # Тест для перевірки роботи
    print(f"Ваш поточний масштаб Windows: {get_windows_scale_factor() * 100}%")
    
    res = get_screen_resolution()
    if res:
        print(f"Роздільна здатність екрана: {res[0]}x{res[1]}")
    
    # Тест нормалізації
    test_x, test_y = 1000, 500
    norm_x, norm_y = normalize_coordinates(test_x, test_y)
    print(f"Тест нормалізації: ({test_x}, {test_y}) -> ({norm_x}, {norm_y})")
