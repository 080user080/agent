"""SettingsTab — вкладка налаштувань для PyQt6.

Перероблена: ліва панель (категорії) + права панель (поля обраної категорії).
"""
from __future__ import annotations

import json
import os
from functools import partial
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QSplitter,
    QLabel, QLineEdit, QCheckBox, QComboBox, QSpinBox,
    QDoubleSpinBox, QPushButton, QToolButton, QGroupBox,
    QTextEdit, QListWidget, QListWidgetItem, QSizePolicy,
)

from .base_tab import BaseTab
from .llm_endpoints_editor_qt import LLMEndpointsEditor


class SettingsTab(BaseTab):
    """Вкладка налаштувань (SETTINGS_SCHEMA) на PyQt6.

    Ліва панель — список категорій.
    Права панель — QScrollArea з полями обраної категорії (lazy build).
    """

    settings_status_updated = pyqtSignal(str, str)  # (text, color)

    # Мапа категорій: іконки (необов'язково)
    CATEGORY_ICONS: dict[str, str] = {
        "Асистент": "🤖",
        "Безпека": "🔒",
        "Продуктивність": "⚡",
        "LLM": "🧠",
        "LLM Моделі": "📡",
        "Розпізнавання мови": "🎤",
        "Vision-LM": "👁️",
        "Аудіо": "🔊",
        "Озвучення": "🗣️",
        "GUI": "🖥️",
        "Global Voice Input": "🌍",
        "Аудіо-фільтри": "🎚️",
        "Інше": "📦",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings_built = False
        self._settings_vars: dict[str, Any] = {}
        self._settings_rows: dict[str, list[QWidget]] = {}
        self._group_headers: dict[str, dict] = {}
        self._category_keys: dict[str, list[str]] = {}
        self._category_widgets: dict[str, QWidget] = {}  # lazy cache
        self._categories_ordered: list[str] = []

        # Створюються в setup_ui
        self._settings_search_edit: QLineEdit | None = None
        self._watcher_status_text: QTextEdit | None = None
        self._settings_status: QLabel | None = None
        self._category_list: QListWidget | None = None
        self._right_scroll: QScrollArea | None = None
        self._right_container: QWidget | None = None
        self._right_layout: QVBoxLayout | None = None

    def setup_ui(self) -> None:
        """Побудувати UI вкладки налаштувань."""
        self._build_settings_tab()
        self._settings_built = True

    def get_title(self) -> str:
        return "⚙️ Налаштування"

    def refresh(self) -> None:
        """Оновити статус Watcher-ів при перемиканні."""
        mw = self._main_window
        if mw and hasattr(mw, 'assistant') and mw.assistant:
            self.update_watcher_status(mw.assistant)

    # ─── Будівництво UI ───────────────────────────────────────────────────────

    def _build_settings_tab(self) -> None:
        from functions.runtime.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        self._settings_vars = {}
        self._settings_rows = {}
        self._group_headers = {}
        self._category_keys = {}
        self._category_widgets = {}
        self._categories_ordered = []

        # Зібрати категорії зі схеми
        groups: dict[str, list[tuple[str, dict]]] = {}
        for key, schema in SETTINGS_SCHEMA.items():
            if schema.get("hidden") or schema.get("group") == "_hidden":
                continue
            group = schema.get("group", "Інше")
            groups.setdefault(group, []).append((key, schema))

        self._categories_ordered = list(groups.keys())
        for group_name, items in groups.items():
            self._category_keys[group_name] = [k for k, _ in items]

        # Головний layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Splitter: ліва панель | права панель ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # --- Ліва панель: пошук + список категорій ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(4)

        # Пошук
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

        left_layout.addWidget(search_frame)

        # Список категорій
        self._category_list = QListWidget()
        self._category_list.setFixedWidth(160)
        self._category_list.setMinimumWidth(120)
        self._category_list.setMaximumWidth(200)
        self._category_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #444;
                border-radius: 4px;
                background: #252526;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background: #094771;
                color: white;
            }
            QListWidget::item:hover {
                background: #2a2d2e;
            }
        """)
        font = QFont("Segoe UI", 10)
        self._category_list.setFont(font)

        for cat_name in self._categories_ordered:
            icon = self.CATEGORY_ICONS.get(cat_name, "📄")
            item = QListWidgetItem(f"{icon} {cat_name}")
            item.setData(Qt.ItemDataRole.UserRole, cat_name)
            self._category_list.addItem(item)

        self._category_list.currentRowChanged.connect(self._on_category_changed)
        left_layout.addWidget(self._category_list, stretch=1)

        splitter.addWidget(left_panel)

        # --- Права панель: scroll area + контент ---
        right_panel = QWidget()
        right_main_layout = QVBoxLayout(right_panel)
        right_main_layout.setContentsMargins(0, 0, 0, 0)
        right_main_layout.setSpacing(0)

        self._right_scroll = QScrollArea()
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._right_container = QWidget()
        self._right_layout = QVBoxLayout(self._right_container)
        self._right_layout.setSpacing(4)
        self._right_layout.setContentsMargins(8, 8, 8, 8)

        # Додаємо stretch спочатку, щоб контент був зверху, а кнопки внизу
        self._right_layout.addStretch(1)

        # --- Нижня частина правої панелі: Watcher статус + кнопки ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(4, 4, 4, 4)
        bottom_layout.setSpacing(4)

        # Watcher статус
        watcher_group = QGroupBox("Активні Watcher-и")
        watcher_layout = QVBoxLayout(watcher_group)
        self._watcher_status_text = QTextEdit()
        self._watcher_status_text.setReadOnly(True)
        self._watcher_status_text.setFixedHeight(80)
        self._watcher_status_text.setStyleSheet(
            "background: #1e1e1e; color: #1976d2; border: 1px solid #444;"
        )
        watcher_layout.addWidget(self._watcher_status_text)
        bottom_layout.addWidget(watcher_group)

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

        bottom_layout.addWidget(btn_frame)

        # Статус
        self._settings_status = QLabel(
            "Зміни деяких налаштувань (STT/TTS/аудіо) застосуються після перезапуску."
        )
        self._settings_status.setFont(QFont("Segoe UI", 8, -1, True))
        self._settings_status.setStyleSheet("color: #888888;")
        self._settings_status.setWordWrap(True)
        bottom_layout.addWidget(self._settings_status)

        self._right_layout.addWidget(bottom_widget)

        self._right_scroll.setWidget(self._right_container)
        right_main_layout.addWidget(self._right_scroll, stretch=1)

        splitter.addWidget(right_panel)

        # Налаштування розмірів splitter
        splitter.setSizes([160, 600])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # Вибрати першу категорію за замовчуванням
        if self._categories_ordered and self._category_list:
            self._category_list.setCurrentRow(0)

    # ─── Перемикання категорії ────────────────────────────────────────────────

    def _on_category_changed(self, row: int) -> None:
        """Обрана нова категорія зліва — будуємо/показуємо її поля справа."""
        if row < 0 or row >= len(self._categories_ordered):
            return
        cat_name = self._categories_ordered[row]

        # Видалити старий контент (крім stretch і bottom_widget)
        self._clear_right_content()

        # Lazy build: створити контент категорії, якщо ще не створено
        if cat_name not in self._category_widgets:
            self._build_category_content(cat_name)

        # Вставити контент категорії в праву панель
        cat_widget = self._category_widgets[cat_name]
        # Вставляємо перед stretch (який завжди останній після очищення)
        if self._right_layout is not None:
            self._right_layout.insertWidget(
                self._right_layout.count() - 1, cat_widget
            )
            cat_widget.setVisible(True)

    def _clear_right_content(self) -> None:
        """Видалити всі віджети категорій з правої панелі (крім bottom)."""
        if self._right_layout is None:
            return
        # Проходимо з кінця, щоб не збивати індекси
        for i in range(self._right_layout.count() - 1, -1, -1):
            item = self._right_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                # Перевіряємо чи це не bottom_widget (останні два: stretch + bottom)
                # bottom_widget — це QGroupBox або QFrame з кнопками, він має бути останнім
                if isinstance(w, QGroupBox) or (
                    isinstance(w, QFrame) and w.layout() and 
                    any(isinstance(w.layout().itemAt(j).widget(), QPushButton) 
                        for j in range(w.layout().count()) if w.layout().itemAt(j))
                ):
                    continue
                # Видаляємо віджет з layout
                self._right_layout.removeWidget(w)
                w.setParent(None)
        # Перевіряємо чи залишився stretch
        if self._right_layout.count() > 0:
            last = self._right_layout.itemAt(self._right_layout.count() - 1)
            if last and last.widget() is None:
                pass  # це stretch, все добре
            else:
                self._right_layout.addStretch(1)

    def _build_category_content(self, cat_name: str) -> QWidget:
        """Створити контент для однієї категорії (lazy)."""
        from functions.runtime.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        keys = self._category_keys.get(cat_name, [])

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 4, 4, 4)
        container_layout.setSpacing(4)

        for key in keys:
            schema = SETTINGS_SCHEMA.get(key, {})
            current_value = settings.get(key)
            row_widgets: list[QWidget] = []
            widget = self._create_settings_widget(
                container, key, schema, current_value, row_widgets
            )
            self._settings_vars[key] = widget
            self._settings_rows[key] = row_widgets

            # llm_endpoints займає більше місця
            if schema.get("type") == "llm_endpoints":
                spacer = QFrame()
                spacer.setFixedHeight(10)
                container_layout.addWidget(spacer)
                row_widgets.append(spacer)

        container_layout.addStretch()

        self._category_widgets[cat_name] = container
        return container

    # ─── Створення віджета налаштування ───────────────────────────────────────

    def _create_settings_widget(
        self, parent: QWidget, key: str, schema: dict,
        value: Any, row_widgets: list
    ) -> QWidget:
        """Створити віджет для одного налаштування."""
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
        widget: QWidget | None = None
        if wtype == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.stateChanged.connect(partial(self._auto_save_setting, key))
        elif wtype == "choice":
            widget = QComboBox()
            choices = schema.get("choices", [])
            widget.addItems(choices)
            widget.setCurrentText(str(value) if value else "")
            widget.currentTextChanged.connect(partial(self._auto_save_setting, key))
        elif wtype == "multi_choice":
            # Множинний вибір — чекбокси для кожного варіанту
            choices = schema.get("choices", [])
            widget = QWidget()
            mc_layout = QVBoxLayout(widget)
            mc_layout.setContentsMargins(0, 0, 0, 0)
            mc_layout.setSpacing(2)
            selected = set(value) if isinstance(value, list) else set()
            for choice in choices:
                cb = QCheckBox(choice)
                cb.setChecked(choice in selected)
                cb.stateChanged.connect(partial(self._auto_save_setting, key))
                mc_layout.addWidget(cb)
            # Сховати wrapper label
            mc_layout.setSpacing(2)
        elif wtype == "int":
            widget = QSpinBox()
            widget.setRange(schema.get("min", -999999), schema.get("max", 999999))
            widget.setValue(int(value) if value is not None else 0)
            widget.valueChanged.connect(partial(self._auto_save_setting, key))
        elif wtype == "float":
            widget = QDoubleSpinBox()
            widget.setDecimals(4)
            widget.setRange(schema.get("min", -999999.0), schema.get("max", 999999.0))
            widget.setSingleStep(0.001)
            widget.setValue(float(value) if value is not None else 0.0)
            widget.valueChanged.connect(partial(self._auto_save_setting, key))
        elif wtype == "llm_endpoints":
            widget = LLMEndpointsEditor(value or [])
            widget.changed.connect(partial(self._auto_save_setting, key))
        else:  # str
            widget = QLineEdit()
            widget.setText(str(value) if value else "")
            widget.editingFinished.connect(partial(self._auto_save_setting, key))

        if widget:
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

        parent.layout().addWidget(row)
        return widget

    # ─── Фільтр (глобальний, по всіх категоріях) ──────────────────────────────

    def _apply_settings_filter(self) -> None:
        """При пошуку — показати результати в правій панелі."""
        from functions.runtime.core_settings import SETTINGS_SCHEMA

        query = self._settings_search_edit.text().strip().lower() if self._settings_search_edit else ""
        
        if not query:
            # Якщо пошук порожній — повернутися до обраної категорії
            if self._category_list:
                current_row = self._category_list.currentRow()
                self._on_category_changed(current_row)
            return

        # Пошук по всіх категоріях: знайти всі поля, що підходять
        matched_keys: list[str] = []
        for key, schema in SETTINGS_SCHEMA.items():
            if schema.get("hidden") or schema.get("group") == "_hidden":
                continue
            haystack = " ".join([
                key.lower(),
                str(schema.get("label", "")).lower(),
                str(schema.get("desc", "")).lower(),
            ])
            if query in haystack:
                matched_keys.append(key)

        # Показати результати в правій панелі
        self._clear_right_content()

        # Побудувати flat список полів, що підійшли
        from functions.runtime.core_settings import get_settings
        settings = get_settings()

        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 4, 4, 4)
        results_layout.setSpacing(4)

        if not matched_keys:
            no_results = QLabel(
                f"Нічого не знайдено за запитом \"{query}\""
            )
            no_results.setStyleSheet("color: #888; font-size: 12px; padding: 20px;")
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            results_layout.addWidget(no_results)
        else:
            header = QLabel(f"🔍 Результати пошуку: {len(matched_keys)}")
            header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            header.setStyleSheet("color: #1976d2; padding: 4px 0;")
            results_layout.addWidget(header)

            for key in matched_keys:
                schema = SETTINGS_SCHEMA.get(key, {})
                current_value = settings.get(key)
                row_widgets: list[QWidget] = []
                widget = self._create_settings_widget(
                    results_widget, key, schema, current_value, row_widgets
                )
                self._settings_vars[key] = widget
                self._settings_rows[key] = row_widgets

                if schema.get("type") == "llm_endpoints":
                    spacer = QFrame()
                    spacer.setFixedHeight(10)
                    results_layout.addWidget(spacer)
                    row_widgets.append(spacer)

        results_layout.addStretch()

        if self._right_layout is not None:
            self._right_layout.insertWidget(
                self._right_layout.count() - 1, results_widget
            )

    # ─── Автоматичне збереження ──────────────────────────────────────────────

    def _auto_save_setting(self, key: str) -> None:
        """Зберігає одне налаштування за ключем одразу після зміни."""
        from functions.runtime.core_settings import get_settings, SETTINGS_SCHEMA

        widget = self._settings_vars.get(key)
        if widget is None:
            return

        schema = SETTINGS_SCHEMA.get(key, {})
        wtype = schema.get("type", "str")
        try:
            value = self._get_widget_value(widget, wtype, schema)
            settings = get_settings()
            settings.set(key, value, persist=not schema.get("user_only", False))
            # Короткочасний статус "збережено"
            self._update_settings_status(
                f"💾 {schema.get('label', key)} збережено.", "#2e7d32"
            )
        except (ValueError, TypeError) as e:
            self._update_settings_status(
                f"⚠️ {schema.get('label', key)}: {e}", "#c62828"
            )

    def _update_settings_status(self, text: str, color: str) -> None:
        """Оновити текст статусу, безпечно обробляючи видалений QLabel."""
        try:
            if self._settings_status is not None:
                self._settings_status.setText(text)
                self._settings_status.setStyleSheet(f"color: {color};")
        except RuntimeError:
            # QLabel був видалений — скидаємо посилання
            self._settings_status = None

    # ─── Збереження ───────────────────────────────────────────────────────────

    def _save_all_settings(self) -> None:
        from functions.runtime.core_settings import get_settings, SETTINGS_SCHEMA

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

        if self._settings_status:
            if errors:
                self._settings_status.setText(
                    f"⚠️ Помилки у {len(errors)} полях: {'; '.join(errors[:3])}"
                )
                self._settings_status.setStyleSheet("color: #c62828;")
            else:
                self._settings_status.setText(f"✅ Збережено {saved} налаштувань.")
                self._settings_status.setStyleSheet("color: #2e7d32;")

    def _get_widget_value(self, widget: QWidget, wtype: str, schema: dict) -> Any:
        if wtype == "bool":
            return widget.isChecked()
        if wtype == "choice":
            val = widget.currentText()
            if schema.get("choices") and val not in schema["choices"]:
                raise ValueError("невалідний вибір")
            return val
        if wtype == "multi_choice":
            # Зібрати всі вибрані чекбокси
            selected = []
            for child in widget.findChildren(QCheckBox):
                if child.isChecked():
                    selected.append(child.text())
            return selected
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

    # ─── Скидання ─────────────────────────────────────────────────────────────

    def _reset_all_settings(self) -> None:
        from functions.runtime.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        for key in SETTINGS_SCHEMA:
            settings.reset(key)
        self._reload_settings_tab()
        if self._settings_status:
            self._settings_status.setText("↺ Налаштування скинуто до config.py.")
            self._settings_status.setStyleSheet("color: #1976d2;")

    # ─── Перезавантаження вкладки ─────────────────────────────────────────────

    def _reload_settings_tab(self) -> None:
        layout = self.layout()
        if layout is None:
            return
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._settings_built = False
        self._build_settings_tab()
        self._settings_built = True

    # ─── Очищення кешу ────────────────────────────────────────────────────────

    def _clear_command_cache(self) -> None:
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
            if self._settings_status:
                self._settings_status.setText(
                    f"🗑️ Кеш команд очищено ({count} записів)."
                )
                self._settings_status.setStyleSheet("color: #1976d2;")
        except Exception as e:
            if self._settings_status:
                self._settings_status.setText(f"❌ Помилка очищення кешу: {e}")
                self._settings_status.setStyleSheet("color: #d32f2f;")

    # ─── Перезавантаження агента ──────────────────────────────────────────────

    def _restart_agent(self) -> None:
        if self._settings_status:
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

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self.close)

    # ─── Watcher статус ───────────────────────────────────────────────────────

    def update_watcher_status(self, engine: Any = None) -> None:
        if not self._watcher_status_text:
            return
        text = self._watcher_status_text
        text.clear()
        if engine is None or not hasattr(engine, "list_watchers"):
            text.append("Немає активних Watcher-ів.")
        else:
            watcher_states = engine.list_watchers()
            if not watcher_states:
                text.append("Немає активних Watcher-ів.")
            else:
                for state in watcher_states:
                    status = "active" if state.running else "idle"
                    text.append(
                        f"• {state.name}: {status} "
                        f"(passes: {state.loop_passes}, actions: {state.actions_fired})"
                    )