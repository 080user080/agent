"""self_code_safety — Захисні обмеження для само-редагування (Phase 5.1).

SELF_EDIT_BLACKLIST — файли які агент НЕ може змінювати.
Функція is_edit_allowed() перевіряє чи файл дозволено для редагування.

Phase: Self-Coding Agent Pipeline — Фаза 5.
"""
from __future__ import annotations

import os
import logging
from typing import Tuple

logger = logging.getLogger("self_code_safety")

# ── Blacklist ────────────────────────────────────────────────────────────────

SELF_EDIT_BLACKLIST: Tuple[str, ...] = (
    "core_safety_sandbox.py",
    "logic_permission_gate.py",
    "core_tool_runtime.py",
    "main.py",
    "run.py",
    "self_code_safety.py",  # сам себе
)

"""Кортеж імен файлів, які агент НЕ може змінювати.

Всі порівняння регістро-незалежні (Windows-сумісність).
Використовується в is_edit_allowed() та може імпортуватись
в analyze_gap() (self_code_context.py) та SelfCodingPipeline.
"""


# ── Перевірка ───────────────────────────────────────────────────────────────


def is_edit_allowed(file_path: str) -> Tuple[bool, str]:
    """Перевірити чи дозволено редагувати файл.

    Використовує ``SELF_EDIT_BLACKLIST`` — файли з цього списку
    не можна змінювати. Порівняння регістро-незалежне та за
    базовим іменем (без шляху).

    Args:
        file_path: Абсолютний або відносний шлях до файлу.

    Returns:
        Tuple[bool, str]:
          - (True, "") — дозволено.
          - (False, "Причина заборони") — заборонено.
    """
    if not file_path or not isinstance(file_path, str):
        return False, f"Некоректний file_path: {file_path!r}"

    # Витягти базове ім'я файлу (наприклад, "run.py" з "d:/Python/agent/run.py")
    basename = os.path.basename(file_path).lower()

    if not basename:
        return False, f"Не вдалося визначити ім'я файлу з {file_path!r}"

    if basename in SELF_EDIT_BLACKLIST:
        return False, (
            f"Файл '{basename}' знаходиться в SELF_EDIT_BLACKLIST. "
            f"Редагування заборонено для захисту критичних модулів."
        )

    return True, ""


# ── Експорт ─────────────────────────────────────────────────────────────────


__all__ = [
    "SELF_EDIT_BLACKLIST",
    "is_edit_allowed",
]