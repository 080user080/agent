"""
Порівняння станів екрану та візуальний diff.

GUI Automation Phase 4 — відстеження змін на екрані.
Зберігає еталонні скріншоти, порівнює з поточним станом,
виявляє різницю між "до" та "після".
"""

import cv2
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw
import time
import os
from pathlib import Path

from functions.tools_screen_capture import ScreenCapture


class VisualDiff:
    """Порівняння зображень та виявлення змін на екрані."""

    def __init__(self, baseline_dir: str = "logs/baselines", screen_capture: Optional[ScreenCapture] = None):
        self.capture = screen_capture or ScreenCapture()
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self._baselines = {}  # Кеш завантажених еталонів

    # ==================== БАЗОВЕ ПОРІВНЯННЯ ====================

    def compare_images(self, image1: Image.Image, image2: Image.Image,
                       threshold: float = 0.05) -> Dict[str, Any]:
        """
        Порівняти два зображення.

        Args:
            image1: Перше зображення (базове)
            image2: Друге зображення (поточне)
            threshold: Поріг значущої зміни (0.0-1.0)

        Returns:
            {"identical": bool, "diff_percent": float, "diff_regions": [...]}
        """
        try:
            # Переводимо в numpy arrays
            arr1 = np.array(image1.convert('RGB'))
            arr2 = np.array(image2.convert('RGB'))

            # Перевіряємо розміри
            if arr1.shape != arr2.shape:
                # Масштабуємо друге зображення до розміру першого
                arr2 = cv2.resize(arr2, (arr1.shape[1], arr1.shape[0]))

            # Обчислюємо різницю
            diff = cv2.absdiff(arr1, arr2)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)

            # Підраховуємо змінені пікселі
            _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
            changed_pixels = np.sum(thresh > 0)
            total_pixels = thresh.size
            diff_percent = (changed_pixels / total_pixels) * 100

            # Знаходимо регіони змін
            diff_regions = self._find_diff_regions(thresh)

            return {
                "success": True,
                "identical": diff_percent < (threshold * 100),
                "diff_percent": round(diff_percent, 2),
                "changed_pixels": int(changed_pixels),
                "total_pixels": int(total_pixels),
                "diff_regions": diff_regions,
                "threshold_used": threshold
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def compare_with_baseline(self, name: str, current_image: Optional[Image.Image] = None,
                              threshold: float = 0.05) -> Dict[str, Any]:
        """
        Порівняти поточний стан з еталонним.

        Args:
            name: Ім'я еталону
            current_image: Поточне зображення (None = зняти скріншот)
            threshold: Поріг значущої зміни

        Returns:
            {"changed": bool, "diff_regions": [...], "diff_percent": float}
        """
        try:
            # Завантажуємо еталон
            baseline_path = self.baseline_dir / f"{name}.png"
            if not baseline_path.exists():
                return {
                    "success": False,
                    "error": f"Baseline '{name}' not found. Create it first with capture_baseline()."
                }

            baseline = Image.open(baseline_path)

            # Отримуємо поточне зображення
            if current_image is None:
                result = self.capture.take_screenshot()
                if not result.get("success"):
                    return {"success": False, "error": "Failed to capture screenshot"}
                current_image = result.get("image")

            # Порівнюємо
            comparison = self.compare_images(baseline, current_image, threshold)

            if not comparison.get("success"):
                return comparison

            return {
                "success": True,
                "baseline_name": name,
                "changed": not comparison["identical"],
                "diff_percent": comparison["diff_percent"],
                "diff_regions": comparison["diff_regions"],
                "changed_pixels": comparison["changed_pixels"],
                "threshold_used": threshold
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def highlight_changes(self, before: Image.Image, after: Image.Image,
                          highlight_color: Tuple[int, int, int] = (255, 0, 0)) -> Image.Image:
        """
        Створити зображення з підсвіченими змінами.

        Args:
            before: Зображення "до"
            after: Зображення "після"
            highlight_color: Колір підсвічування (R, G, B)

        Returns:
            PIL.Image з виділеними змінами
        """
        try:
            arr1 = np.array(before.convert('RGB'))
            arr2 = np.array(after.convert('RGB'))

            # Масштабуємо якщо потрібно
            if arr1.shape != arr2.shape:
                arr2 = cv2.resize(arr2, (arr1.shape[1], arr1.shape[0]))

            # Обчислюємо різницю
            diff = cv2.absdiff(arr1, arr2)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)

            # Маска змін
            _, mask = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)

            # Розширюємо маску для кращої видимості
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=2)

            # Створюємо результат — зображення "після" з підсвічуванням
            result = arr2.copy()

            # Червона підсвітка змін
            overlay = np.full_like(result, highlight_color)
            alpha = 0.4

            # Застосовуємо підсвітку до змінених областей
            mask_3channel = np.stack([mask / 255.0] * 3, axis=-1)
            result = result * (1 - mask_3channel * alpha) + overlay * (mask_3channel * alpha)

            return Image.fromarray(result.astype(np.uint8))

        except Exception as e:
            # Повертаємо оригінал у разі помилки
            return after

    # ==================== ЕТАЛОНИ (BASELINES) ====================

    def capture_baseline(self, name: str, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Зберегти еталонний скріншот.

        Args:
            name: Ім'я еталону
            region: Область для захоплення (None = весь екран)

        Returns:
            {"success": bool, "path": str}
        """
        try:
            if region:
                result = self.capture.capture_region(*region)
            else:
                result = self.capture.take_screenshot()

            if not result.get("success"):
                return {"success": False, "error": result.get("error", "Capture failed")}

            image = result.get("image")
            if not image:
                return {"success": False, "error": "No image captured"}

            # Зберігаємо
            path = self.baseline_dir / f"{name}.png"
            image.save(path)

            # Оновлюємо кеш
            self._baselines[name] = image

            return {
                "success": True,
                "path": str(path),
                "name": name,
                "size": image.size
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_baseline(self, name: str) -> Dict[str, Any]:
        """Видалити еталон."""
        try:
            path = self.baseline_dir / f"{name}.png"
            if path.exists():
                path.unlink()
                self._baselines.pop(name, None)
                return {"success": True, "message": f"Baseline '{name}' deleted"}
            return {"success": False, "error": f"Baseline '{name}' not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_baselines(self) -> List[Dict[str, Any]]:
        """Отримати список всіх еталонів."""
        baselines = []
        for path in self.baseline_dir.glob("*.png"):
            stat = path.stat()
            baselines.append({
                "name": path.stem,
                "path": str(path),
                "created": stat.st_mtime,
                "size_bytes": stat.st_size
            })
        return baselines

    # ==================== ОЧІКУВАННЯ ЗМІН ====================

    def wait_for_visual_change(self, region: Optional[Tuple[int, int, int, int]] = None,
                                timeout: float = 10.0, interval: float = 0.5,
                                threshold: float = 0.02) -> Dict[str, Any]:
        """
        Очікувати будь-яку зміну на екрані.

        Args:
            region: Область для моніторингу
            timeout: Максимальний час очікування (сек)
            interval: Інтервал між перевірками (сек)
            threshold: Поріг значущої зміни

        Returns:
            {"changed": bool, "diff_percent": float, "wait_time": float}
        """
        try:
            # Початковий скріншот
            if region:
                result = self.capture.capture_region(*region)
            else:
                result = self.capture.take_screenshot()

            if not result.get("success"):
                return {"success": False, "error": "Failed to capture initial screenshot"}

            baseline_image = result.get("image")
            start_time = time.time()

            while time.time() - start_time < timeout:
                time.sleep(interval)

                # Новий скріншот
                if region:
                    result = self.capture.capture_region(*region)
                else:
                    result = self.capture.take_screenshot()

                if not result.get("success"):
                    continue

                current_image = result.get("image")
                comparison = self.compare_images(baseline_image, current_image, threshold)

                if not comparison.get("success"):
                    continue

                if not comparison["identical"]:
                    return {
                        "success": True,
                        "changed": True,
                        "diff_percent": comparison["diff_percent"],
                        "diff_regions": comparison["diff_regions"],
                        "wait_time": round(time.time() - start_time, 2)
                    }

            return {
                "success": True,
                "changed": False,
                "wait_time": round(time.time() - start_time, 2),
                "message": "No visual change detected within timeout"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def wait_for_visual_stable(self, region: Optional[Tuple[int, int, int, int]] = None,
                                stable_time: float = 1.0, timeout: float = 15.0,
                                interval: float = 0.3, threshold: float = 0.01) -> Dict[str, Any]:
        """
        Очікувати стабільності (відсутності змін) на екрані.

        Args:
            region: Область для моніторингу
            stable_time: Час без змін для вважання "стабільним"
            timeout: Максимальний час очікування
            interval: Інтервал між перевірками
            threshold: Поріг значущої зміни

        Returns:
            {"stable": bool, "stable_duration": float, "wait_time": float}
        """
        try:
            stable_start = None
            last_image = None
            start_time = time.time()

            while time.time() - start_time < timeout:
                # Скріншот
                if region:
                    result = self.capture.capture_region(*region)
                else:
                    result = self.capture.take_screenshot()

                if not result.get("success"):
                    time.sleep(interval)
                    continue

                current_image = result.get("image")

                if last_image is not None:
                    comparison = self.compare_images(last_image, current_image, threshold)

                    if comparison.get("success") and comparison["identical"]:
                        # Немає змін
                        if stable_start is None:
                            stable_start = time.time()
                        else:
                            stable_duration = time.time() - stable_start
                            if stable_duration >= stable_time:
                                return {
                                    "success": True,
                                    "stable": True,
                                    "stable_duration": round(stable_duration, 2),
                                    "wait_time": round(time.time() - start_time, 2)
                                }
                    else:
                        # Є зміни — скидаємо таймер
                        stable_start = None

                last_image = current_image
                time.sleep(interval)

            return {
                "success": True,
                "stable": False,
                "wait_time": round(time.time() - start_time, 2),
                "message": f"Screen did not stabilize within {timeout}s"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def wait_for_element_appear(self, element_checker: callable,
                                 timeout: float = 10.0, interval: float = 0.5) -> Dict[str, Any]:
        """
        Очікувати появи елемента (за допомогою callback функції).

        Args:
            element_checker: Функція яка повертає True якщо елемент знайдено
            timeout: Максимальний час очікування
            interval: Інтервал між перевірками

        Returns:
            {"found": bool, "wait_time": float}
        """
        try:
            start_time = time.time()

            while time.time() - start_time < timeout:
                if element_checker():
                    return {
                        "success": True,
                        "found": True,
                        "wait_time": round(time.time() - start_time, 2)
                    }
                time.sleep(interval)

            return {
                "success": True,
                "found": False,
                "wait_time": round(time.time() - start_time, 2)
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== ДОПОМІЖНІ МЕТОДИ ====================

    def _find_diff_regions(self, thresh: np.ndarray, min_area: int = 100) -> List[Dict[str, Any]]:
        """Знайти регіони змін на бінаризованому зображенні."""
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h

            if area >= min_area:
                regions.append({
                    "x": int(x),
                    "y": int(y),
                    "width": int(w),
                    "height": int(h),
                    "area": int(area)
                })

        # Сортуємо за площею (спадання)
        regions.sort(key=lambda r: r["area"], reverse=True)

        return regions


# ==================== PUBLIC API ====================

_visual_diff = None

def get_visual_diff() -> VisualDiff:
    """Отримати глобальний екземпляр VisualDiff."""
    global _visual_diff
    if _visual_diff is None:
        _visual_diff = VisualDiff()
    return _visual_diff


# Функції для реєстрації в TOOL_POLICIES

def capture_baseline(name: str, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    """Зберегти еталонний скріншот."""
    return get_visual_diff().capture_baseline(name, region)


def delete_baseline(name: str) -> Dict[str, Any]:
    """Видалити еталон."""
    return get_visual_diff().delete_baseline(name)


def list_baselines() -> Dict[str, Any]:
    """Отримати список еталонів."""
    baselines = get_visual_diff().list_baselines()
    return {"success": True, "baselines": baselines, "count": len(baselines)}


def compare_with_baseline(name: str, threshold: float = 0.05) -> Dict[str, Any]:
    """Порівняти поточний стан з еталоном."""
    return get_visual_diff().compare_with_baseline(name, None, threshold)


def highlight_changes(before_path: str, after_path: str,
                      save_path: Optional[str] = None) -> Dict[str, Any]:
    """Створити зображення з підсвіченими змінами."""
    try:
        before = Image.open(before_path)
        after = Image.open(after_path)

        result = get_visual_diff().highlight_changes(before, after)

        if save_path:
            result.save(save_path)
            return {"success": True, "path": save_path}

        return {"success": True, "image": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def wait_for_visual_change(region: Optional[Tuple[int, int, int, int]] = None,
                            timeout: float = 10.0, threshold: float = 0.02) -> Dict[str, Any]:
    """Очікувати будь-яку зміну на екрані."""
    return get_visual_diff().wait_for_visual_change(region, timeout, 0.5, threshold)


def wait_for_visual_stable(region: Optional[Tuple[int, int, int, int]] = None,
                            stable_time: float = 1.0, timeout: float = 15.0,
                            threshold: float = 0.01) -> Dict[str, Any]:
    """Очікувати стабільності на екрані."""
    return get_visual_diff().wait_for_visual_stable(region, stable_time, timeout, 0.3, threshold)
