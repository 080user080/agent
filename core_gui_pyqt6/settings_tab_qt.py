"""SettingsTabQtMixin — вкладка Налаштування для PyQt6.

Порт core_gui/settings_tab.py (Tkinter) на PyQt6.
"""
from __future__ import annotations

import json
import os
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLabel,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QToolButton,
    QGroupBox,
    QTextEdit,
    QButtonGroup,
)

from .llm_endpoints_editor_qt import LLMEndpointsEditor


class SettingsTabQtMixin:
    """Міксин для вкладки Налаштування (SETTINGS_SCHEMA) на PyQt6.

    Очікує атрибути:
        - self.settings_container: QWidget (контейнер для вкладки)
        - self.notebook: QTabWidget
        - self._settings_built: bool
    """

    # Сигнал для оновлення статусу (опціонально)
    settings_status_updated = pyqtSignal(str, str)  # (text, color)

    def _on_tab_changed(self, index: int) -> None:
        """Викликається при перемиканні вкладок. Ліниво будує Settings."""
        # Вкладка Settings = індекс 2 (Chat=0, Plan=1, Settings=2)
        if index == 2 and not self._settings_built:
            self._build_settings_tab()
            self._settings_built = True

    def _build_settings_tab(self) -> None:
        """Побудувати UI вкладки Налаштування на основі SETTINGS_SCHEMA."""
        from functions.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        self._settings_vars: dict[str, Any] = {}  # key → widget
        self._settings_rows: dict[str, list[QWidget]] = {}  # key → list widgets
        self._group_headers: dict[str, dict] = {}  # group → {btn, keys, expanded}

        layout = QVBoxLayout(self.settings_container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- Панель пошуку ---
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_label = QLabel("🔍")
        search_label.setFont(QFont("Segoe UI", 10))
        search_layout.addWidget(search_label)

        self._settings_search_edit = QLineEdit()
        self._settings_search_edit.setPlaceholderText("Пошук налаштувань...")
        self._settings_search_edit.textChanged.connect(self._apply_settings_filter)
        search_layout.addWidget(self._settings_search_edit)

        layout.addWidget(search_frame)

        # --- Панель статусу Watcher-ів ---
        watcher_group = QGroupBox("Активні Watcher-и")
        watcher_layout = QVBoxLayout(watcher_group)
        self._watcher_status_text = QTextEdit()
        self._watcher_status_text.setReadOnly(True)
        self._watcher_status_text.setFixedHeight(80)
        self._watcher_status_text.setStyleSheet("background: #1e1e1e; color: #1976d2; border: 1px solid #444;")
        watcher_layout.addWidget(self._watcher_status_text)
        layout.addWidget(watcher_group)

        # --- Scrollable container ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(4, 4, 4, 4)

        # --- Згрупувати по "group" ---
        groups: dict[str, list[tuple[str, dict]]] = {}
        for key, schema in SETTINGS_SCHEMA.items():
            if schema.get("hidden") or schema.get("group") == "_hidden":
                continue
            group = schema.get("group", "Інше")
            groups.setdefault(group, []).append((key, schema))

        # Рендер груп
        first_group = True
        for group_name, items in groups.items():
            expanded = first_group
            arrow = "▼" if expanded else "▶"

            header_frame = QFrame()
            header_layout = QHBoxLayout(header_frame)
            header_layout.setContentsMargins(0, 0, 0, 0)

            toggle_btn = QToolButton()
            toggle_btn.setText(arrow)
            toggle_btn.setFixedSize(24, 24)
            toggle_btn.clicked.connect(lambda checked, g=group_name: self._toggle_group(g))
            header_layout.addWidget(toggle_btn)

            header_label = QLabel(group_name)
            header_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            header_label.setStyleSheet("color: #1976d2;")
            header_layout.addWidget(header_label)

            header_layout.addStretch()
            inner_layout.addWidget(header_frame)

            # Контейнер для віджетів групи
            group_container = QWidget()
            group_container_layout = QVBoxLayout(group_container)
            group_container_layout.setContentsMargins(24, 4, 4, 4)
            group_container_layout.setSpacing(4)

            self._group_headers[group_name] = {
                "btn": toggle_btn,
                "label": header_label,
                "container": group_container,
                "keys": [k for k, _ in items],
                "expanded": expanded,
            }

            # Віджети налаштувань
            for key, schema in items:
                current_value = settings.get(key)
                row_widgets = []
                widget = self._create_settings_widget(group_container, key, schema, current_value, row_widgets)
                self._settings_vars[key] = widget
                self._settings_rows[key] = row_widgets

                # llm_endpoints займає більше місця
                if schema.get("type") == "llm_endpoints":
                    spacer = QFrame()
                    spacer.setFixedHeight(10)
                    group_container_layout.addWidget(spacer)
                    row_widgets.append(spacer)

            inner_layout.addWidget(group_container)

            # Якщо група згорнута — приховати контейнер
            if not expanded:
                group_container.hide()

            first_group = False

        # Кнопки дій
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        save_btn = QPushButton("💾 Зберегти всі")
        save_btn.setStyleSheet("background: #2e7d32; color: white; font-weight: bold;")
        save_btn.clicked.connect(self._save_all_settings)
        btn_layout.addWidget(save_btn)

        reset_btn = QPushButton("↺ Скинути до config.py")
        reset_btn.setStyleSheet("background: #1976d2; color: white; font-weight: bold;")
        reset_btn.clicked.connect(self._reset_all_settings)
        btn_layout.addWidget(reset_btn)

        reload_btn = QPushButton("🔄 Перезавантажити")
        reload_btn.setStyleSheet("background: #555; color: #1976d2; font-weight: bold;")
        reload_btn.clicked.connect(self._reload_settings_tab)
        btn_layout.addWidget(reload_btn)

        clear_cache_btn = QPushButton("🗑️ Очистити кеш команд")
        clear_cache_btn.setStyleSheet("background: #e65100; color: white; font-weight: bold;")
        clear_cache_btn.clicked.connect(self._clear_command_cache)
        btn_layout.addWidget(clear_cache_btn)

        restart_btn = QPushButton("🔁 Перезавантажити агента")
        restart_btn.setStyleSheet("background: #d32f2f; color: white; font-weight: bold;")
        restart_btn.clicked.connect(self._restart_agent)
        btn_layout.addWidget(restart_btn)

        inner_layout.addWidget(btn_frame)

        # Статус
        self._settings_status = QLabel("Зміни деяких налаштувань (STT/TTS/аудіо) застосуються після перезапуску.")
        self._settings_status.setFont(QFont("Segoe UI", 8, -1, True))
        self._settings_status.setStyleSheet("color: #888888;")
        self._settings_status.setWordWrap(True)
        inner_layout.addWidget(self._settings_status)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

    def _create_settings_widget(self, parent: QWidget, key: str, schema: dict, value: Any, row_widgets: list) -> QWidget:
        """Створити віджет для одного налаштування. Повертає головний віджет."""
        from PyQt6.QtGui import QFont

        label_text = schema.get("label", key)
        desc = schema.get("desc", "")
        wtype = schema.get("type", "str")

        # Row container
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(2)

        # Label
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        row_layout.addWidget(lbl)
        row_widgets.append(lbl)
        row_widgets.append(row)

        # Widget за типом
        widget = None
        if wtype == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(value))
        elif wtype == "choice":
            widget = QComboBox()
            choices = schema.get("choices", [])
            widget.addItems(choices)
            widget.setCurrentText(str(value) if value else "")
        elif wtype == "int":
            widget = QSpinBox()
            widget.setRange(schema.get("min", -999999), schema.get("max", 999999))
            widget.setValue(int(value) if value is not None else 0)
        elif wtype == "float":
            widget = QDoubleSpinBox()
            widget.setRange(schema.get("min", -999999.0), schema.get("max", 999999.0))
            widget.setSingleStep(0.1)
            widget.setValue(float(value) if value is not None else 0.0)
        elif wtype == "llm_endpoints":
            widget = LLMEndpointsEditor(value or [])
        else:  # str
            widget = QLineEdit()
            widget.setText(str(value) if value else "")

        row_layout.addWidget(widget)
        row_widgets.append(widget)

        # Desc
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setFont(QFont("Segoe UI", 8))
            desc_lbl.setStyleSheet("color: #888888;")
            desc_lbl.setWordWrap(True)
            row_layout.addWidget(desc_lbl)
            row_widgets.append(desc_lbl)

        # Додати row в parent layout
        parent.layout().addWidget(row)

        return widget

    def _toggle_group(self, group_name: str) -> None:
        """Згорнути/розгорнути групу."""
        info = self._group_headers.get(group_name)
        if not info:
            return
        info["expanded"] = not info["expanded"]
        arrow = "▼" if info["expanded"] else "▶"
        info["btn"].setText(arrow)
        # Ховаємо/показуємо контейнер групи
        if "container" in info:
            info["container"].setVisible(info["expanded"])
        else:
            # Fallback для старого формату
            for key in info["keys"]:
                for w in self._settings_rows.get(key, []):
                    w.setVisible(info["expanded"])

    def update_watcher_status(self, engine: Any = None) -> None:
        """Оновити статус Watcher-ів."""
        if not hasattr(self, "_watcher_status_text"):
            return
        text = self._watcher_status_text
        text.clear()
        if engine is None or not hasattr(engine, "list_watchers"):
            text.appendPlainText("Немає активних Watcher-ів.")
        else:
            watcher_states = engine.list_watchers()
            if not watcher_states:
                text.appendPlainText("Немає активних Watcher-ів.")
            else:
                for state in watcher_states:
                    status = "active" if state.running else "idle"
                    text.appendPlainText(f"• {state.name}: {status} (passes: {state.loop_passes}, actions: {state.actions_fired})")

    def _apply_settings_filter(self) -> None:
        """Фільтрувати налаштування за пошуком."""
        from functions.core_settings import SETTINGS_SCHEMA

        query = self._settings_search_edit.text().strip().lower()

        for group_name, info in self._group_headers.items():
            any_visible = False
            for key in info["keys"]:
                schema = SETTINGS_SCHEMA.get(key, {})
                haystack = " ".join([
                    key.lower(),
                    str(schema.get("label", "")).lower(),
                    str(schema.get("desc", "")).lower(),
                ])
                match = (not query) or (query in haystack)
                for w in self._settings_rows.get(key, []):
                    w.setVisible(match and info["expanded"])
                if match:
                    any_visible = True
            info["btn"].setVisible(any_visible or not query)
            info["label"].setVisible(any_visible or not query)

    def _save_all_settings(self) -> None:
        """Зберегти всі налаштування."""
        from functions.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        saved = 0
        errors = []

        for key, widget in self._settings_vars.items():
            schema = SETTINGS_SCHEMA.get(key, {})
            wtype = schema.get("type", "str")
            try:
                value = self._get_widget_value(widget, wtype, schema)
                settings.set(key, value, persist=not schema.get("user_only", False))
                saved += 1
            except (ValueError, TypeError) as e:
                errors.append(f"{key}: {e}")

        if errors:
            self._settings_status.setText(f"⚠️ Помилки у {len(errors)} полях: {'; '.join(errors[:3])}")
            self._settings_status.setStyleSheet("color: #c62828;")
        else:
            self._settings_status.setText(f"✅ Збережено {saved} налаштувань.")
            self._settings_status.setStyleSheet("color: #2e7d32;")

    def _get_widget_value(self, widget: QWidget, wtype: str, schema: dict) -> Any:
        """Отримати значення з віджета з валідацією."""
        if wtype == "bool":
            return widget.isChecked()
        if wtype == "choice":
            val = widget.currentText()
            if schema.get("choices") and val not in schema["choices"]:
                raise ValueError("невалідний вибір")
            return val
        if wtype == "int":
            v = widget.value()
            if "min" in schema and v < schema["min"]:
                raise ValueError(f">= {schema['min']}")
            if "max" in schema and v > schema["max"]:
                raise ValueError(f"<= {schema['max']}")
            return v
        if wtype == "float":
            v = widget.value()
            if "min" in schema and v < schema["min"]:
                raise ValueError(f">= {schema['min']}")
            if "max" in schema and v > schema["max"]:
                raise ValueError(f"<= {schema['max']}")
            return v
        if wtype == "llm_endpoints":
            return widget.get()
        return widget.text()

    def _reset_all_settings(self) -> None:
        """Скинути до дефолтів config.py."""
        from functions.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        for key in SETTINGS_SCHEMA.keys():
            settings.reset(key)
        self._reload_settings_tab()
        self._settings_status.setText("↺ Налаштування скинуто до config.py.")
        self._settings_status.setStyleSheet("color: #1976d2;")

    def _reload_settings_tab(self) -> None:
        """Перезбудувати вкладку."""
        # Очищаємо контейнер
        layout = self.settings_container.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._settings_built = False
        self._build_settings_tab()
        self._settings_built = True

    def _clear_command_cache(self) -> None:
        """Очистити кеш команд."""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_file = os.path.join(root_dir, "functions", "cache_data.json")
        try:
            count = 0
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                count = len(data)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False)
            self._settings_status.setText(f"🗑️ Кеш команд очищено ({count} записів).")
            self._settings_status.setStyleSheet("color: #1976d2;")
        except Exception as e:
            self._settings_status.setText(f"❌ Помилка очищення кешу: {e}")
            self._settings_status.setStyleSheet("color: #d32f2f;")

    def _restart_agent(self) -> None:
        """Перезавантажити агента (без підтвердження)."""
        self._settings_status.setText("🔁 Перезавантаження агента...")
        self._settings_status.setStyleSheet("color: #1976d2;")

        import subprocess
        import sys

        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        run_script = os.path.join(root_dir, "run.py")

        subprocess.Popen(
            [sys.executable, run_script],
            cwd=root_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )

        # Закрити через 500мс
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self.close)
