"""StatsTab — вкладка статистики для PyQt6.

Читає дані з SessionBudget.snapshot() або з runtime/logs/ як fallback.
Не хардкодить нулі — показує прочерк якщо дані недоступні.
"""
from __future__ import annotations

import os
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QGroupBox,
)

from .base_tab import BaseTab
from .constants import APP_VERSION


class StatsTab(BaseTab):
    """Вкладка статистики: метрики використання LLM, планів, контексту."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats_data: dict[str, Any] = {}

        # Labels для метрик — створюються в setup_ui
        self._labels: dict[str, QLabel] = {}

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Заголовок ---
        title = QLabel(f"Статистика роботи {APP_VERSION}")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # --- Панель з кнопкою оновлення ---
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        refresh_btn = QPushButton("🔄 Оновити")
        refresh_btn.clicked.connect(self._refresh_stats)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addWidget(btn_frame)

        # --- Сітка метрик ---
        metrics_frame = QFrame()
        grid = QGridLayout(metrics_frame)
        grid.setSpacing(12)

        metrics = [
            ("LLM запити", "llm_requests"),
            ("Prompt токени", "prompt_tokens"),
            ("Completion токени", "completion_tokens"),
            ("Всього токенів", "total_tokens"),
            ("Середній час відповіді", "avg_response_time"),
            ("Виконано планів", "plans_completed"),
            ("Виконано кроків", "steps_completed"),
            ("Використання контексту", "context_usage"),
        ]

        for i, (label, key) in enumerate(metrics):
            row, col = divmod(i, 2)
            col_offset = col * 2

            lbl_name = QLabel(f"{label}:")
            lbl_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lbl_name, row, col_offset)

            lbl_value = QLabel("—")
            lbl_value.setFont(QFont("Segoe UI", 10))
            lbl_value.setObjectName(f"stat_{key}")
            grid.addWidget(lbl_value, row, col_offset + 1)

            self._labels[key] = lbl_value

        layout.addWidget(metrics_frame)

        # --- Прогрес-бар контексту ---
        context_group = QGroupBox("Використання контексту")
        context_layout = QVBoxLayout(context_group)

        self.context_bar = QProgressBar()
        self.context_bar.setMaximum(100)
        self.context_bar.setValue(0)
        self.context_bar.setTextVisible(True)
        context_layout.addWidget(self.context_bar)

        self.context_label = QLabel("—")
        self.context_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        context_layout.addWidget(self.context_label)

        layout.addWidget(context_group)
        layout.addStretch()

        # Завантажити початкові дані
        self._refresh_stats()

    def get_title(self) -> str:
        return "📊 Статистика"

    def refresh(self) -> None:
        """Оновити при перемиканні вкладки."""
        self._refresh_stats()

    def update_stats(self, stats: dict) -> None:
        """Оновити метрики з ядра."""
        self._stats_data.update(stats)
        self._update_display()

    # ─── Завантаження даних ───────────────────────────────────────────────────

    def _refresh_stats(self) -> None:
        """Спроба отримати реальні дані з SessionBudget або логів."""
        data = {}

        # 1. Спроба отримати з SessionBudget
        try:
            from functions.runtime.logic_core import SessionBudget  # type: ignore
            budget = SessionBudget()
            snapshot = budget.snapshot() if hasattr(budget, 'snapshot') else {}
            data.update(snapshot)
        except Exception:
            pass

        # 2. Спроба отримати з ядра через main_window
        mw = self._main_window
        if mw and hasattr(mw, 'assistant') and mw.assistant:
            try:
                core = mw.assistant
                if hasattr(core, 'stats') and core.stats:
                    data.update(core.stats)
            except Exception:
                pass

        # 3. Fallback — спроба прочитати з файлу метрик
        metrics_file = os.path.join(
            r"d:\Python\agent\runtime", "metrics.json"
        )
        if os.path.isfile(metrics_file):
            try:
                import json
                with open(metrics_file, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                if isinstance(file_data, dict):
                    data.update(file_data)
            except Exception:
                pass

        self._stats_data = data
        self._update_display()

    def _update_display(self) -> None:
        """Оновити UI з поточними даними."""
        d = self._stats_data

        self._set_label("llm_requests", d.get("total_requests", d.get("llm_requests")))
        self._set_label("prompt_tokens", d.get("total_prompt_tokens", d.get("prompt_tokens")))
        self._set_label("completion_tokens", d.get("total_completion_tokens", d.get("completion_tokens")))

        total_t = d.get("total_tokens")
        if total_t is None:
            pt = d.get("total_prompt_tokens", d.get("prompt_tokens"))
            ct = d.get("total_completion_tokens", d.get("completion_tokens"))
            if pt is not None and ct is not None:
                total_t = pt + ct
        self._set_label("total_tokens", total_t)

        avg_time = d.get("avg_response_time")
        if avg_time is not None:
            self._labels["avg_response_time"].setText(f"{avg_time:.2f}с")
        else:
            self._labels["avg_response_time"].setText("—")

        self._set_label("plans_completed", d.get("plans_completed"))
        self._set_label("steps_completed", d.get("steps_completed"))

        # Прогрес-бар контексту
        used = d.get("context_tokens_used", d.get("used"))
        limit = d.get("context_limit", d.get("limit"))
        model = d.get("model", "")

        if used is not None and limit and limit > 0:
            pct = min(int((used / limit) * 100), 100)
            self.context_bar.setValue(pct)
            self.context_bar.setFormat(f"{pct}%")
            self.context_label.setText(f"{used:,} / {limit:,} токенів" + (f" ({model})" if model else ""))

            # Колір прогрес-бару
            if pct <= 60:
                color = "green"
            elif pct <= 80:
                color = "#ff9800"  # жовтий
            elif pct <= 95:
                color = "#e65100"  # помаранчевий
            else:
                color = "#c62828"  # червоний
            self.context_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: {color}; }}"
            )
        else:
            self.context_bar.setValue(0)
            self.context_bar.setFormat("—")
            self.context_label.setText("Дані недоступні")

    def _set_label(self, key: str, value: Any) -> None:
        """Встановити текст label, або прочерк якщо значення None."""
        lbl = self._labels.get(key)
        if lbl is None:
            return
        if value is None:
            lbl.setText("—")
        else:
            lbl.setText(str(value))