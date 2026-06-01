"""LogsTab — вкладка логів для PyQt6.

Читає реальні файли з runtime/logs/, підтримує QueueHandler для real-time логування.
Оптимізована: макс. 50 рядків, читання з кінця файлу, rolling window.
"""
from __future__ import annotations

import glob
import logging
import os
from typing import Any
from queue import Queue
from logging.handlers import QueueHandler

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit, QPushButton, QLabel, QFrame,
)

from .base_tab import BaseTab
from .constants import COLOR_DEBUG, COLOR_INFO, COLOR_WARNING, COLOR_ERROR


_LOG_DIR = r"d:\Python\agent\runtime\logs"
_MAX_LOG_ROWS = 50


class LogsTab(BaseTab):
    """Вкладка логів: таблиця, фільтр, пошук, real-time оновлення."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_queue: Queue | None = None
        self._queue_handler: QueueHandler | None = None
        self._refresh_timer: QTimer | None = None
        self._all_rows: list[dict] = []  # (level, module, message, timestamp)
        self._placeholder_label: QLabel | None = None

        # Створюються в setup_ui
        self.table: QTableWidget | None = None
        self.level_filter: QComboBox | None = None
        self.search_edit: QLineEdit | None = None

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Верхня панель — фільтр + пошук
        top_frame = QFrame()
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_layout.addWidget(QLabel("Рівень:"))
        self.level_filter = QComboBox()
        self.level_filter.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_filter.currentTextChanged.connect(self._apply_filters)
        top_layout.addWidget(self.level_filter)

        top_layout.addWidget(QLabel("Пошук:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Фільтр по тексту...")
        self.search_edit.textChanged.connect(self._apply_filters)
        top_layout.addWidget(self.search_edit, stretch=1)

        clear_btn = QPushButton("Очистити")
        clear_btn.clicked.connect(self._clear_logs)
        top_layout.addWidget(clear_btn)

        refresh_btn = QPushButton("Оновити")
        refresh_btn.clicked.connect(self._load_from_files)
        top_layout.addWidget(refresh_btn)

        layout.addWidget(top_frame)

        # Таблиця логів — спочатку порожня
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Час", "Рівень", "Модуль", "Повідомлення"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        # Плейсхолдер поверх таблиці (поки даних немає)
        self._placeholder_label = QLabel(
            "Натисніть \"Оновити\" щоб завантажити останні 50 записів"
        )
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet(
            "color: #666; font-size: 14px; padding: 40px;"
        )
        self._placeholder_label.setVisible(True)
        layout.addWidget(self._placeholder_label)

        # Приховуємо плейсхолдер коли таблиця не порожня
        self.table.model().rowsInserted.connect(self._update_placeholder_visibility)
        self.table.model().rowsRemoved.connect(self._update_placeholder_visibility)
        self.table.model().modelReset.connect(self._update_placeholder_visibility)

        # Налаштувати QueueHandler для Python logging
        self._setup_queue_handler()

    def _update_placeholder_visibility(self) -> None:
        """Показати/сховати плейсхолдер залежно від кількості рядків."""
        if self._placeholder_label and self.table:
            has_rows = self.table.rowCount() > 0
            self._placeholder_label.setVisible(not has_rows)

    def get_title(self) -> str:
        return "📄 Логи"

    def refresh(self) -> None:
        """При перемиканні на вкладку — нічого не завантажуємо автоматично.
        
        Таблиця залишається порожньою з підказкою натиснути 'Оновити'.
        """
        # Не викликаємо _load_from_files() — економимо ресурси
        self._update_placeholder_visibility()

    # ─── Читання з кінця файлу ────────────────────────────────────────────────

    def _read_tail(self, filepath: str, max_lines: int) -> list[str]:
        """Прочитати останні max_lines рядків з файлу (з кінця)."""
        lines: list[str] = []
        try:
            with open(filepath, "rb") as f:
                f.seek(0, 2)  # в кінець
                file_size = f.tell()
                chunk_size = 4096
                pos = file_size
                collected = b""
                while len(lines) <= max_lines and pos > 0:
                    read_size = min(chunk_size, pos)
                    pos -= read_size
                    f.seek(pos)
                    chunk = f.read(read_size)
                    collected = chunk + collected
                    # Розбити на рядки
                    parts = collected.split(b"\n")
                    if len(parts) > 1:
                        # Перший елемент може бути неповним рядком — залишаємо в collected
                        collected = parts[0]
                        # Інші — це повні рядки (в зворотньому порядку)
                        full_lines = parts[1:]
                        for bline in reversed(full_lines):
                            try:
                                line_str = bline.decode("utf-8", errors="replace").strip()
                                if line_str:
                                    lines.append(line_str)
                            except Exception:
                                pass
                # Не забути останній шматок
                if collected:
                    try:
                        line_str = collected.decode("utf-8", errors="replace").strip()
                        if line_str:
                            lines.append(line_str)
                    except Exception:
                        pass
        except (OSError, IOError):
            pass
        # Повернути в правильному порядку (від найстарішого до найновішого)
        lines.reverse()
        return lines[-max_lines:]

    # ─── Завантаження з файлів ────────────────────────────────────────────────

    def _load_from_files(self) -> None:
        """Прочитати останні 50 записів з лог-файлів (читає з кінця)."""
        self._all_rows.clear()
        if not os.path.isdir(_LOG_DIR):
            self._apply_filters()
            self._update_placeholder_visibility()
            return

        log_files = glob.glob(os.path.join(_LOG_DIR, "*.log")) + \
                    glob.glob(os.path.join(_LOG_DIR, "*.jsonl"))

        # Збираємо не більше ніж _MAX_LOG_ROWS рядків з усіх файлів
        # Спочатку читаємо трохи більше з кожного файлу, потім об'єднуємо
        all_candidates: list[tuple[str, int, dict]] = []  # (timestamp_sort_key, seq, entry)

        seq = 0
        for filepath in sorted(log_files):
            try:
                # Читаємо останні рядки з файлу
                file_lines = self._read_tail(filepath, _MAX_LOG_ROWS)
                for line in file_lines:
                    entry = self._parse_log_line(line)
                    if entry:
                        # Для сортування використовуємо timestamp (якщо є)
                        ts = entry.get("timestamp", "")
                        all_candidates.append((ts, seq, entry))
                        seq += 1
            except Exception:
                pass

        # Сортуємо за часом (найновіші останні) і беремо останні _MAX_LOG_ROWS
        all_candidates.sort(key=lambda x: (x[0], x[1]))
        self._all_rows = [entry for _, _, entry in all_candidates[-_MAX_LOG_ROWS:]]

        self._apply_filters()
        self._update_placeholder_visibility()

    def _parse_log_line(self, line: str) -> dict | None:
        """Спроба розпарсити рядок логу."""
        import re
        # Формат: [2026-05-24 12:34:56] [INFO] [module] message
        m = re.match(
            r'\[([^\]]+)\]\s*\[([^\]]+)\]\s*\[([^\]]+)\]\s*(.*)',
            line
        )
        if m:
            return {
                "timestamp": m.group(1).strip(),
                "level": m.group(2).strip().upper(),
                "module": m.group(3).strip(),
                "message": m.group(4).strip(),
            }
        # Формат: [Час] РівЕНЬ: message
        m2 = re.match(
            r'\[([^\]]+)\]\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*:?\s*(.*)',
            line
        )
        if m2:
            return {
                "timestamp": m2.group(1).strip(),
                "level": m2.group(2).strip().upper(),
                "module": "-",
                "message": m2.group(3).strip(),
            }
        # Якщо не вдалося — просто message
        return {
            "timestamp": "-",
            "level": "INFO",
            "module": "-",
            "message": line,
        }

    # ─── QueueHandler (real-time логування) ───────────────────────────────────

    def _setup_queue_handler(self) -> None:
        """Підключити QueueHandler до кореневого логера."""
        try:
            self._log_queue = Queue()
            self._queue_handler = QueueHandler(self._log_queue)
            self._queue_handler.setLevel(logging.DEBUG)

            root_logger = logging.getLogger()
            # Додаємо тільки якщо ще не додано
            existing = any(
                isinstance(h, QueueHandler) for h in root_logger.handlers
            )
            if not existing:
                root_logger.addHandler(self._queue_handler)

            # Таймер для читання черги
            self._refresh_timer = QTimer()
            self._refresh_timer.timeout.connect(self._poll_log_queue)
            self._refresh_timer.start(500)  # кожні 500мс
        except Exception:
            pass

    def _poll_log_queue(self) -> None:
        """Прочитати нові логи з черги і додати в таблицю (rolling window)."""
        if self._log_queue is None:
            return
        added = 0
        while not self._log_queue.empty():
            try:
                record = self._log_queue.get_nowait()
                entry = {
                    "timestamp": self._format_time(record),
                    "level": record.levelname,
                    "module": record.name or record.module or "-",
                    "message": record.getMessage(),
                }
                self._all_rows.append(entry)
                added += 1
            except Exception:
                break

        if added > 0:
            # Rolling window: якщо більше ніж _MAX_LOG_ROWS — видаляємо найстаріші
            while len(self._all_rows) > _MAX_LOG_ROWS:
                self._all_rows.pop(0)
            self._apply_filters()

    def _format_time(self, record: logging.LogRecord) -> str:
        import time
        return time.strftime('%H:%M:%S', time.localtime(record.created))

    # ─── Додавання логів програмно ───────────────────────────────────────────

    def add_log_entry(self, level: str, module: str, message: str) -> None:
        """Додати рядок логу програмно (наприклад, з ядра)."""
        import datetime
        entry = {
            "timestamp": datetime.datetime.now().strftime('%H:%M:%S'),
            "level": level.upper(),
            "module": module,
            "message": message,
        }
        self._all_rows.append(entry)
        # Rolling window
        while len(self._all_rows) > _MAX_LOG_ROWS:
            self._all_rows.pop(0)
        self._apply_filters()

    # ─── Фільтрація та відображення ───────────────────────────────────────────

    def _apply_filters(self) -> None:
        """Застосувати фільтр рівня + пошук."""
        if not self.table or not self.level_filter or not self.search_edit:
            return

        level = self.level_filter.currentText()
        query = self.search_edit.text().strip().lower()

        # Визначити числовий рівень
        level_map = {
            "ALL": 0, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40,
        }
        min_level = level_map.get(level, 0)

        filtered = [
            row for row in self._all_rows
            if self._level_to_int(row.get("level", "INFO")) >= min_level
            and (not query or query in row.get("message", "").lower()
                 or query in row.get("module", "").lower())
        ]

        self.table.setRowCount(len(filtered))
        for i, row in enumerate(filtered):
            self._set_row(i, row)
        self.table.resizeRowsToContents()
        self._update_placeholder_visibility()

    def _level_to_int(self, level: str) -> int:
        m = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        return m.get(level.upper(), 20)

    def _set_row(self, row_idx: int, entry: dict) -> None:
        """Заповнити рядок таблиці з кольорами."""
        if not self.table:
            return
        ts_item = QTableWidgetItem(entry.get("timestamp", ""))
        lvl_item = QTableWidgetItem(entry.get("level", ""))
        mod_item = QTableWidgetItem(entry.get("module", ""))
        msg_item = QTableWidgetItem(entry.get("message", ""))

        color = self._level_color(entry.get("level", "INFO"))
        for item in (ts_item, lvl_item, mod_item, msg_item):
            item.setForeground(color)

        self.table.setItem(row_idx, 0, ts_item)
        self.table.setItem(row_idx, 1, lvl_item)
        self.table.setItem(row_idx, 2, mod_item)
        self.table.setItem(row_idx, 3, msg_item)

    def _level_color(self, level: str) -> QColor:
        level = level.upper()
        colors = {
            "DEBUG": QColor(COLOR_DEBUG),
            "INFO": QColor(COLOR_INFO),
            "WARNING": QColor(COLOR_WARNING),
            "ERROR": QColor(COLOR_ERROR),
            "CRITICAL": QColor(COLOR_ERROR),
        }
        return colors.get(level, QColor(COLOR_INFO))

    def _clear_logs(self) -> None:
        """Очистити таблицю (не файли)."""
        self._all_rows.clear()
        if self.table:
            self.table.setRowCount(0)
        self._update_placeholder_visibility()