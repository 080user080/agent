# core_gui/constants.py
"""Спільні константи GUI."""
import sys
import os

# Дозволити імпорт з functions/ (на випадок, якщо пакет запустили окремо)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

try:
    from functions.config import ASSISTANT_NAME, ASSISTANT_EMOJI  # type: ignore
except ImportError:
    ASSISTANT_NAME = "МАРК"
    ASSISTANT_EMOJI = "⚡"

ASSISTANT_TITLE = f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}"
