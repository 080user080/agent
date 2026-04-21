"""
Глобальний conftest.py для тестів.

Мокає Windows/GUI-специфічні залежності, щоб модулі functions/tools_* можна
було імпортувати на Linux-CI (де pyautogui→mouseinfo→tkinter недоступні,
а win32* взагалі відсутні). Самі тести усередині використовують @patch,
тож функціональна логіка перевіряється незалежно від платформи.

ВАЖЛИВО: conftest.py виконується ПЕРЕД збором/імпортом тестів.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


class _AutoMockModule(types.ModuleType):
    """Модуль-заглушка: будь-який запитаний атрибут повертає MagicMock.

    Це потрібно, щоб `unittest.mock.patch('win32gui.GetWindowText')` не
    падав з AttributeError на платформах, де реальний модуль відсутній.
    """

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        value = MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, value)
        return value


def _install_stub(name: str, *, auto_mock: bool = True) -> types.ModuleType:
    """Створити модуль-заглушку та зареєструвати у sys.modules."""
    if name in sys.modules:
        return sys.modules[name]
    cls = _AutoMockModule if auto_mock else types.ModuleType
    stub = cls(name)
    sys.modules[name] = stub
    return stub


# --- Windows-only модулі (pywin32) ---
for _win_mod in (
    "win32gui",
    "win32con",
    "win32process",
    "win32ui",
    "win32api",
    "win32clipboard",
    "pywintypes",
):
    _install_stub(_win_mod)

# Реальні числові значення win32con-констант, які використовуються у
# functions/tools_window_manager.py. Тести перевіряють конкретні коди
# (наприклад `ShowWindow(hwnd, 6)` для SW_MINIMIZE) — якщо лишити
# MagicMock-заглушки, `assert_called_once_with(..., 6)` не пройде.
_win32con = sys.modules["win32con"]
_win32con.SW_HIDE = 0
_win32con.SW_SHOWNORMAL = 1
_win32con.SW_SHOWMINIMIZED = 2
_win32con.SW_MAXIMIZE = 3
_win32con.SW_SHOWMAXIMIZED = 3
_win32con.SW_SHOW = 5
_win32con.SW_MINIMIZE = 6
_win32con.SW_SHOWMINNOACTIVE = 7
_win32con.SW_SHOWNA = 8
_win32con.SW_RESTORE = 9
_win32con.WM_CLOSE = 0x0010  # 16

# --- pyautogui / mouseinfo (потребують tkinter/display на Linux) ---
_install_stub("pyautogui")
_install_stub("mouseinfo")

# --- Решта залежностей, які можуть бути відсутні на CI ---
for _mod in (
    "pyperclip",
    "mss",
    "pytesseract",
    "easyocr",
    "sounddevice",
    "soundfile",
    "noisereduce",
):
    _install_stub(_mod)


# ============================================================
# Історична довідка: раніше цей файл карантинив 22 «застарілі» тести, які
# посилалися на рефакторену поверхню SessionMemory / MemoryManager /
# TaskExecutor / OCREngine / WindowManager. Їх оживили у PR B1 під актуальне
# API, тож механізм skip-списку більше не потрібен.
#
# Якщо в майбутньому з'являться тимчасово зламані тести — краще виправити
# причину, а не додавати сюди ще один skip-фільтр.
# ============================================================
