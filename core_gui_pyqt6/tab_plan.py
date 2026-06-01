"""PlanTab — вкладка плану виконання для PyQt6.

Перенесено з PlanPanelQtMixin + закоментований план-код з main_window.py.
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem,
)

from .base_tab import BaseTab


class PlanTab(BaseTab):
    """Вкладка плану: список кроків, кнопки запуску/зупинки."""

    _STATUS_ICONS = {
        "pending": ("⏳", QColor("#888888")),
        "running": ("▶️", QColor("#1976d2")),
        "success": ("✅", QColor("#2e7d32")),
        "ok": ("✅", QColor("#2e7d32")),
        "error": ("❌", QColor("#c62828")),
        "blocked": ("⛔", QColor("#b71c1c")),
        "needs_confirmation": ("❓", QColor("#ef6c00")),
        "skipped": ("⏭️", QColor("#9e9e9e")),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plan_steps: list[dict] = []
        self._plan_auto_hide_timer: QTimer | None = None

        # Створюються в setup_ui
        self.plan_list: QListWidget | None = None
        self.plan_run_btn: QPushButton | None = None
        self.plan_stop_btn: QPushButton | None = None

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Кнопки запуску/зупинки плану
        btn_layout = QHBoxLayout()

        self.plan_run_btn = QPushButton("▶ Виконати")
        self.plan_run_btn.setObjectName("plan_run_btn")
        self.plan_run_btn.clicked.connect(self._on_run_plan)
        btn_layout.addWidget(self.plan_run_btn)

        self.plan_stop_btn = QPushButton("⏹ Зупинити")
        self.plan_stop_btn.setObjectName("plan_stop_btn")
        self.plan_stop_btn.clicked.connect(self._on_stop_plan)
        self.plan_stop_btn.hide()
        btn_layout.addWidget(self.plan_stop_btn)

        layout.addLayout(btn_layout)

        # Список кроків плану
        self.plan_list = QListWidget()
        self.plan_list.setObjectName("plan_list")
        layout.addWidget(self.plan_list, stretch=1)

    def get_title(self) -> str:
        return "📋 План"

    # ─── Публічні методи ──────────────────────────────────────────────────────

    def show_plan_panel(self, steps_info: list) -> None:
        """Показати панель плану з переліком кроків."""
        if not self.plan_list:
            return
        self.plan_list.clear()
        self._plan_steps = []

        for idx, step_info in enumerate(steps_info):
            action = step_info.get('action') or step_info.get('description') or 'unknown'
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

        self.plan_list.scrollToTop()

    def update_plan_step(self, data: dict) -> None:
        """Оновити статус конкретного кроку."""
        if not isinstance(data, dict) or not self.plan_list:
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
        self.plan_list.scrollToItem(item)

        self._update_progress_display()

    def finish_plan_panel(self, stats: dict | None = None) -> None:
        """Закінчити план — показати фінальний статус."""
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

        mw = self._main_window
        if mw and hasattr(mw, 'status_label'):
            mw.status_label.setText(title)

        self.on_plan_execution_finished()

        # Автоматично приховати через 8с, якщо все ок
        if ok == total and not (err or blocked or confirm):
            if self._plan_auto_hide_timer:
                self._plan_auto_hide_timer.stop()
            self._plan_auto_hide_timer = QTimer.singleShot(
                8000, self._auto_hide_plan_panel
            )

    def on_plan_execution_started(self) -> None:
        """Викликається коли план почав виконуватися."""
        try:
            if self.plan_run_btn and self.plan_stop_btn:
                self.plan_run_btn.hide()
                self.plan_stop_btn.show()
        except Exception:
            pass

    def on_plan_execution_finished(self) -> None:
        """Викликається коли план завершив виконання."""
        try:
            if self.plan_stop_btn and self.plan_run_btn:
                self.plan_stop_btn.hide()
                self.plan_run_btn.show()
        except Exception:
            pass

    # ─── Приватні методи ──────────────────────────────────────────────────────

    def _update_progress_display(self) -> None:
        """Оновити відображення прогресу."""
        total = len(self._plan_steps)
        if total == 0:
            return

        done_count = sum(
            1 for step in self._plan_steps
            if step['status'] in ("ok", "success", "error", "blocked", "skipped")
        )

        mw = self._main_window
        if mw and hasattr(mw, 'progress_bar'):
            mw.progress_bar.setValue(int((done_count / total) * 100))
        if mw and hasattr(mw, 'status_label'):
            mw.status_label.setText(f"📋 План виконання ({done_count}/{total})")

    def _auto_hide_plan_panel(self) -> None:
        """Автоматично приховати панель після успішного виконання."""
        if self.plan_list:
            self.plan_list.clear()
        self._plan_steps = []

    # ─── Обробники кнопок ─────────────────────────────────────────────────────

    def _on_run_plan(self) -> None:
        """Обробник кнопки 'Виконати план'."""
        mw = self._main_window
        if mw and hasattr(mw, 'assistant_callback') and mw.assistant_callback:
            self.on_plan_execution_started()
            mw.assistant_callback('run_plan', None)

    def _on_stop_plan(self) -> None:
        """Обробник кнопки 'Стоп план'."""
        mw = self._main_window
        if mw and hasattr(mw, 'assistant_callback') and mw.assistant_callback:
            mw.assistant_callback('stop_plan', None)
        self.on_plan_execution_finished()