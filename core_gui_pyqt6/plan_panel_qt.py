"""PlanPanelQtMixin — логіка панелі плану виконання для PyQt6.

Порт core_gui/plan_panel.py (Tkinter) на PyQt6.
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QListWidget,
    QListWidgetItem,
)


class PlanPanelQtMixin:
    """Міксин для панелі плану (кроки, прогрес, статуси).

    Очікує атрибути:
        - self.plan_list: QListWidget (список кроків)
        - self.plan_run_btn: QPushButton
        - self.plan_stop_btn: QPushButton
        - self.assistant_callback: callable (optional)
    """

    _STATUS_ICONS = {
        "pending": ("⏳", QColor("#888888")),
        "running": ("▶️", QColor("#1976d2")),
        "ok": ("✅", QColor("#2e7d32")),
        "error": ("❌", QColor("#c62828")),
        "blocked": ("⛔", QColor("#b71c1c")),
        "needs_confirmation": ("❓", QColor("#ef6c00")),
        "skipped": ("⏭️", QColor("#9e9e9e")),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._plan_steps: list[dict] = []
        self._plan_expanded = True
        self._plan_auto_hide_timer = None

    # ---------- Публічні методи ----------

    def show_plan_panel(self, steps_info: list) -> None:
        """Показати панель плану з переліком кроків (status = pending)."""
        self.plan_list.clear()
        self._plan_steps = []

        for idx, step_info in enumerate(steps_info):
            action = step_info.get('action', 'unknown')
            goal = step_info.get('goal', '')

            icon, color = self._STATUS_ICONS["pending"]
            text = f"{icon} {idx + 1}. {action}"
            if goal:
                text += f" — {goal}"

            item = QListWidgetItem(text)
            item.setForeground(color)
            self.plan_list.addItem(item)

            self._plan_steps.append({
                'item': item,
                'action': action,
                'goal': goal,
                'status': 'pending',
            })

        # Прокрутити до початку
        self.plan_list.scrollToTop()

    def update_plan_step(self, data: dict) -> None:
        """Оновити статус конкретного кроку."""
        if not isinstance(data, dict):
            return

        idx = data.get("index", -1)
        status = data.get("status", "pending")
        action = data.get("action", "")
        goal = data.get("goal", "")
        detail = data.get("detail", "")

        if idx < 0 or idx >= len(self._plan_steps):
            return

        step = self._plan_steps[idx]
        item = step['item']
        step['status'] = status

        icon, color = self._STATUS_ICONS.get(status, ("•", QColor("#555555")))
        text = f"{icon} {idx + 1}. {action}"
        if goal:
            text += f" — {goal}"
        if detail and status in ("error", "blocked"):
            text += f"  [{detail[:60]}]"

        item.setText(text)
        item.setForeground(color)

        # Прокрутити до поточного кроку
        self.plan_list.scrollToItem(item)

        # Оновити заголовок (якщо є)
        self._update_progress_display()

    def finish_plan_panel(self, stats: dict) -> None:
        """Закінчити план - показати фінальний статус."""
        if not isinstance(stats, dict):
            stats = {}

        total = stats.get("total", 0)
        ok = stats.get("ok", 0)
        err = stats.get("error", 0)
        blocked = stats.get("blocked", 0)
        confirm = stats.get("needs_confirmation", 0)

        if blocked:
            title = f"⛔ План зупинено: {blocked} заблоковано ({ok}/{total} успішно)"
        elif err:
            title = f"⚠️ План із помилками: {err} помилок ({ok}/{total} успішно)"
        elif confirm:
            title = f"❓ План не завершено: {confirm} не підтверджено ({ok}/{total} успішно)"
        else:
            title = f"✅ План виконано ({ok}/{total})"

        # Оновити статус (якщо є QLabel)
        if hasattr(self, 'status_label'):
            self.status_label.setText(title)

        # Повернути кнопку "Виконати"
        self.on_plan_execution_finished()

        # Автоматично приховати панель через 8 секунд, якщо все ок
        if ok == total and not (err or blocked or confirm):
            if self._plan_auto_hide_timer:
                self._plan_auto_hide_timer.stop()
            self._plan_auto_hide_timer = QTimer.singleShot(8000, self._auto_hide_plan_panel)

    # ---------- Приватні методи ----------

    def _update_progress_display(self) -> None:
        """Оновити відображення прогресу."""
        total = len(self._plan_steps)
        if total == 0:
            return

        done_count = sum(
            1 for step in self._plan_steps
            if step['status'] in ("ok", "error", "blocked", "skipped")
        )
        progress_pct = int((done_count / total) * 100)

        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(progress_pct)

        if hasattr(self, 'status_label'):
            self.status_label.setText(f"📋 План виконання ({done_count}/{total})")

    def _auto_hide_plan_panel(self) -> None:
        """Автоматично приховати панель, якщо план успішно завершений."""
        # У PyQt6 план завжди видимий у правій панелі, тому просто очистити
        self.plan_list.clear()
        self._plan_steps = []

    # ---------- Обробники кнопок ----------

    def _on_run_plan(self) -> None:
        """Обробник кнопки 'Виконати план'."""
        if self.assistant_callback:
            self.plan_run_btn.hide()
            self.plan_stop_btn.show()
            self.assistant_callback('run_plan', None)

    def _on_stop_plan(self) -> None:
        """Обробник кнопки 'Стоп план'."""
        if self.assistant_callback:
            self.assistant_callback('stop_plan', None)
        # Повертаємо кнопку Виконати
        self.plan_stop_btn.hide()
        self.plan_run_btn.show()

    def on_plan_execution_started(self) -> None:
        """Викликається коли план почав виконуватися."""
        try:
            self.plan_run_btn.hide()
            self.plan_stop_btn.show()
        except Exception:
            pass

    def on_plan_execution_finished(self) -> None:
        """Викликається коли план завершив виконання."""
        try:
            self.plan_stop_btn.hide()
            self.plan_run_btn.show()
        except Exception:
            pass
