"""MainWindowPyQt6 — головне вікно МАРК на PyQt6, модульна версія.

Архітектура:
- QMainWindow з QTabWidget (6 вкладок)
- Жодних міксинів — кожна вкладка це окремий клас BaseTab
- Публічний API повністю зворотно сумісний з run_assistant_qt.py
- Thread-safe message queue через Qt signal

Вкладки:
1. Чат (ChatTab)
2. План (PlanTab)
3. Логи (LogsTab)
4. Статистика (StatsTab)
5. Інструменти (ToolsTab)
6. Налаштування (SettingsTab)
"""
from __future__ import annotations

import sys
from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFrame,
    QTabWidget,
)

from .constants import APP_NAME, APP_VERSION, ASSISTANT_TITLE

# StreamingBuffer для live-оцінки токенів під час стрімінгу
from functions.llm.streaming_buffer import StreamingBuffer

# Вкладки
from .tab_chat import ChatTab
from .tab_plan import PlanTab
from .tab_logs import LogsTab
from .tab_stats import StatsTab
from .tab_tools import ToolsTab
from .tab_settings import SettingsTab

# Підтвердження (без міксину)
from .confirmation_qt import ConfirmationDialog


class MainWindowPyQt6(QMainWindow):
    """Головне вікно асистента на PyQt6 (модульна версія з вкладками)."""

    # Qt-сигнал для потокобезпечного додавання повідомлень з фонового потоку
    message_received = pyqtSignal(str, object)

    def __init__(self, assistant_callback: Optional[Callable] = None):
        super().__init__()
        self.assistant_callback = assistant_callback
        self.assistant: Optional[Any] = None
        self.stt_controller: Optional[Any] = None
        self._is_streaming = False
        self._stream_buffer = ""
        self._last_model: str = ""
        self._last_elapsed: float = 0.0

        # --- StreamingBuffer для live-оцінки токенів ---
        self.streaming_buffer = StreamingBuffer(
            on_status=self._on_streaming_status,
            on_context_update=self._on_streaming_context_update,
        )

        # --- Вкладки ---
        self.chat_tab: ChatTab | None = None
        self.plan_tab: PlanTab | None = None
        self.logs_tab: LogsTab | None = None
        self.stats_tab: StatsTab | None = None
        self.tools_tab: ToolsTab | None = None
        self.settings_tab: SettingsTab | None = None

        # --- Віджети статус-бару ---
        self.status_label: QLabel | None = None
        self.progress_bar: QProgressBar | None = None

        # Відновити геометрію вікна
        geom_restored = False
        try:
            from functions.runtime.core_settings import get_setting
            saved_geom = get_setting("WINDOW_GEOMETRY", None)
            if saved_geom:
                if '+' in saved_geom:
                    geom_parts = saved_geom.split('+')
                    size_part = geom_parts[0]
                    x = int(geom_parts[1])
                    y = int(geom_parts[2])
                    w, h = map(int, size_part.split('x'))
                    self.setGeometry(x, y, w, h)
                    geom_restored = True
                else:
                    w, h = map(int, saved_geom.split('x'))
                    self.resize(w, h)
                    geom_restored = True
        except Exception:
            pass

        self.setWindowTitle("МАРК — Асистент (PyQt6)")

        if not geom_restored:
            self.setGeometry(100, 100, 1100, 750)

        self._init_ui()
        self._apply_styles()

        # Відновити активну вкладку та налаштування інтерфейсу
        self._restore_interface_state()

        # Прив'язуємо сигнал до слоту
        self.message_received.connect(self._on_message)

        # Автоматично зберігати інтерфейс при перемиканні вкладок
        self.notebook.currentChanged.connect(self._on_tab_interface_changed)

    def closeEvent(self, event) -> None:
        """Зберегти геометрію вікна та стан інтерфейсу при закритті."""
        try:
            from functions.runtime.core_settings import get_settings
            geom = self.geometry()
            w, h = geom.width(), geom.height()
            x, y = geom.x(), geom.y()
            geom_str = f"{w}x{h}+{x}+{y}"
            get_settings().set("WINDOW_GEOMETRY", geom_str, persist=True)
        except Exception:
            pass
        # Зберегти активну вкладку
        self._save_interface_state()
        # Зберегти розміри splitter вкладки налаштувань
        try:
            if self.settings_tab and hasattr(self.settings_tab, '_get_splitter_sizes'):
                sizes = self.settings_tab._get_splitter_sizes()
                if sizes:
                    from functions.runtime.core_settings import get_settings
                    get_settings().set("SETTINGS_SPLITTER_SIZES", sizes, persist=True)
        except Exception:
            pass
        super().closeEvent(event)

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # Заголовок
        title = QLabel(ASSISTANT_TITLE)
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # QTabWidget з 6 вкладками
        self.notebook = QTabWidget()
        root_layout.addWidget(self.notebook, stretch=1)

        # --- 1. Чат ---
        self.chat_tab = ChatTab()
        self.chat_tab.set_main_window(self)
        self.chat_tab.setup_ui()
        self.chat_tab.command_submitted.connect(self._on_command_submitted)
        self.notebook.addTab(self.chat_tab, self.chat_tab.get_title())

        # --- 2. План ---
        self.plan_tab = PlanTab()
        self.plan_tab.set_main_window(self)
        self.plan_tab.setup_ui()
        self.notebook.addTab(self.plan_tab, self.plan_tab.get_title())

        # --- 3. Логи ---
        self.logs_tab = LogsTab()
        self.logs_tab.set_main_window(self)
        self.logs_tab.setup_ui()
        self.notebook.addTab(self.logs_tab, self.logs_tab.get_title())

        # --- 4. Статистика ---
        self.stats_tab = StatsTab()
        self.stats_tab.set_main_window(self)
        self.stats_tab.setup_ui()
        self.notebook.addTab(self.stats_tab, self.stats_tab.get_title())

        # --- 5. Інструменти ---
        self.tools_tab = ToolsTab()
        self.tools_tab.set_main_window(self)
        self.tools_tab.setup_ui()
        self.notebook.addTab(self.tools_tab, self.tools_tab.get_title())

        # --- 6. Налаштування ---
        self.settings_tab = SettingsTab()
        self.settings_tab.set_main_window(self)
        self.settings_tab.setup_ui()
        self.notebook.addTab(self.settings_tab, self.settings_tab.get_title())

        # Перемикання вкладок — refresh
        self.notebook.currentChanged.connect(self._on_tab_changed)

        # --- Тонкий QProgressBar контексту LLM ---
        self.context_progress_bar = QProgressBar()
        self.context_progress_bar.setFixedHeight(6)
        self.context_progress_bar.setMaximum(100)
        self.context_progress_bar.setValue(0)
        self.context_progress_bar.setTextVisible(False)
        self.context_progress_bar.setObjectName("context_progress_bar")
        self.context_progress_bar.hide()
        root_layout.addWidget(self.context_progress_bar)

        # --- Статус-бар з прогресом ---
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel(f"✅ {APP_NAME} v{APP_VERSION} — Готовий до роботи")
        self.status_label.setObjectName("status_label")
        status_layout.addWidget(self.status_label, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(180)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        status_layout.addWidget(self.progress_bar)

        root_layout.addWidget(status_frame)

    def _apply_styles(self) -> None:
        """QSS — єдина тема кольорів."""
        self.setStyleSheet("""
            QMainWindow { background: #2d2d2d; }
            QWidget { color: #1976d2; background: #2d2d2d; }
            QTextEdit#chat_history {
                background: #1e1e1e; color: #1976d2; border: 1px solid #444; border-radius: 4px;
                padding: 8px;
            }
            QTextEdit { background: #1e1e1e; color: #1976d2; border: 1px solid #444; border-radius: 4px; }
            QLineEdit { background: #1e1e1e; color: #1976d2; border: 1px solid #444; border-radius: 4px; padding: 4px; }
            QLabel { color: #1976d2; }
            QGroupBox { color: #1976d2; border: 1px solid #444; border-radius: 4px; margin-top: 8px; font-weight: bold; background: #2d2d2d; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            QListWidget { background: #1e1e1e; color: #1976d2; border: 1px solid #444; border-radius: 4px; }
            QTabWidget::pane { border: 1px solid #444; background: #2d2d2d; }
            QTabBar::tab {
                background: #3d3d3d; color: #1976d2; border: 1px solid #444; padding: 8px 16px;
            }
            QTabBar::tab:selected { background: #2d2d2d; border-bottom: 2px solid #1976d2; }
            QPushButton {
                background: #1976d2; color: white;
                font: bold 12pt 'Segoe UI'; border: none; border-radius: 4px;
            }
            QPushButton:hover  { background: #1565c0; }
            QPushButton:pressed{ background: #0d47a1; }
            QPushButton#mic_button   { background: #9e9e9e; }
            QPushButton#mic_button:hover  { background: #757575; }
            QPushButton#restart_button { background: #ff9800; }
            QPushButton#restart_button:hover { background: #f57c00; }
            QPushButton#agent_button {
                background: #0f6f73;
                color: #f4fbfb;
                font: bold 11pt 'Segoe UI';
            }
            QPushButton#agent_button:hover { background: #0b5f63; }
            QPushButton#agent_button:pressed { background: #084b4f; }
            QPushButton#stop_button, QPushButton#plan_stop_btn { background: #e65100; }
            QPushButton#stop_button:hover, QPushButton#plan_stop_btn:hover { background: #bf360c; }
            QPushButton#plan_run_btn { background: #2e7d32; }
            QListWidget#plan_list { background: #1e1e1e; color: #1976d2; border: 1px solid #444; border-radius: 4px; }
            QLabel#status_label { color: #555; padding: 4px; }
            QProgressBar { border: 1px solid #ccc; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background: #1976d2; }
        """)

    # ─── Робота з прихованими вкладками ───────────────────────────────────

    def _restore_interface_state(self) -> None:
        """Відновити інтерфейс: активна вкладка, приховані вкладки."""
        try:
            from functions.runtime.core_settings import get_setting

            # 1. Застосувати приховані вкладки
            hidden_tabs = get_setting("HIDDEN_TABS", [])
            if not isinstance(hidden_tabs, list):
                hidden_tabs = []
            self._apply_hidden_tabs(hidden_tabs)

            # 2. Відновити активну вкладку
            saved_tab_index = get_setting("ACTIVE_TAB_INDEX", 0)
            try:
                saved_tab_index = int(saved_tab_index)
            except (ValueError, TypeError):
                saved_tab_index = 0
            if self.notebook and 0 <= saved_tab_index < self.notebook.count():
                self.notebook.setCurrentIndex(saved_tab_index)
        except Exception:
            pass

    # Вкладки, які не можна приховати
    _PROTECTED_TABS = {"💬 Чат", "⚙️ Налаштування"}

    def _apply_hidden_tabs(self, hidden_tabs: list) -> None:
        """Приховати вкладки зі списку hidden_tabs. Чат та Налаштування не приховуються."""
        if not self.notebook:
            return
        tab_map = {
            "💬 Чат": 0,
            "📋 План": 1,
            "📜 Логи": 2,
            "📊 Статистика": 3,
            "🔧 Інструменти": 4,
            "⚙️ Налаштування": 5,
        }
        # Спочатку показати всі вкладки
        for _tab_name, tab_index in tab_map.items():
            if tab_index < self.notebook.count():
                self.notebook.setTabVisible(tab_index, True)
        # Приховати вказані, крім захищених
        for tab_name in hidden_tabs:
            if tab_name in self._PROTECTED_TABS:
                continue  # не можна приховати
            idx = tab_map.get(tab_name)
            if idx is not None and idx < self.notebook.count():
                self.notebook.setTabVisible(idx, False)

    def _save_interface_state(self) -> None:
        """Зберегти стан інтерфейсу (активна вкладка)."""
        try:
            from functions.runtime.core_settings import get_settings
            if self.notebook:
                current_index = self.notebook.currentIndex()
                get_settings().set("ACTIVE_TAB_INDEX", current_index, persist=True)
        except Exception:
            pass

    def _on_tab_interface_changed(self, index: int) -> None:
        """Автоматично зберігати активну вкладку при перемиканні."""
        self._save_interface_state()

    # ─── Перемикання вкладок ──────────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        """Оновити активну вкладку при перемиканні."""
        tabs = [
            self.chat_tab,
            self.plan_tab,
            self.logs_tab,
            self.stats_tab,
            self.tools_tab,
            self.settings_tab,
        ]
        if 0 <= index < len(tabs):
            tab = tabs[index]
            if tab:
                tab.refresh()

    # ─── Команда з чату ──────────────────────────────────────────────────

    def _on_command_submitted(self, command: str) -> None:
        """Отримано команду з поля вводу чату."""
        if not command or not self.assistant_callback:
            return

        command_lower = command.strip().lower()
        if command_lower.startswith("voice_input"):
            self.assistant_callback("run_agent", command)
        else:
            self.assistant_callback("process_text", command)

    # ─── API: відправка команди (сумісність) ──────────────────────────────

    def send_text_command(self) -> None:
        """Відправити команду з поля вводу (для зворотної сумісності)."""
        if self.chat_tab:
            self.chat_tab._send_text_command()

    def on_send_clicked(self) -> None:
        if self.chat_tab:
            self.chat_tab._on_send_clicked()

    def on_agent_clicked(self) -> None:
        if self.chat_tab:
            self.chat_tab._on_agent_clicked()

    def on_stop_clicked(self) -> None:
        self.stop_execution()

    def on_restart_clicked(self) -> None:
        if self.assistant_callback:
            self.assistant_callback("restart", None)

    def stop_execution(self) -> None:
        if self.assistant_callback:
            self.assistant_callback("stop_execution", None)
            self.assistant_callback("stop_plan", None)
        self.hide_stop_button()

    def on_mic_clicked(self) -> None:
        if self.chat_tab:
            self.chat_tab._on_mic_clicked()

    # ─── API: повідомлення в чат ─────────────────────────────────────────

    def add_message(self, sender: str, message: Any) -> None:
        """Додати повідомлення в чат (делегує ChatTab)."""
        if message is None:
            return
        if self.chat_tab:
            self.chat_tab.add_message(sender, message)

    # ─── API: streaming ──────────────────────────────────────────────────

    def start_stream_message(self) -> None:
        if self.chat_tab:
            self.chat_tab.start_stream_message()

    def append_stream_chunk(self, chunk: str) -> None:
        if self.chat_tab:
            self.chat_tab.append_stream_chunk(chunk)
        # Live-оновлення бару контексту через StreamingBuffer
        self.streaming_buffer.add_chunk(chunk)

    def end_stream_message(self) -> None:
        if self.chat_tab:
            self.chat_tab.end_stream_message()
        # Зберігаємо час відповіді
        self._last_elapsed = self.streaming_buffer._elapsed
        # Статус-бар НЕ перезаписуємо — він вже оновлений через _update_status_after_llm
        # з реальним часом LLM (наприклад "✅ Gemini (12.8с)")
        # Виклик streaming_buffer.finish() викидав статус з _elapsed=0.0 (якщо стрімінгу не було),
        # що перезаписувало правильний час
        self.streaming_buffer.reset()

    def _on_streaming_status(self, status_text: str) -> None:
        """Callback для оновлення статус-бару під час стрімінгу."""
        self.update_progress(0, status_text)

    def _on_streaming_context_update(self, used: int, limit: int, model: str) -> None:
        """Callback для live-оновлення бару контексту під час стрімінгу."""
        if model:
            self._last_model = model
        self._update_context_bar(used, limit, model)
        # Також передаємо в StatsTab для оновлення статистики
        if self.stats_tab:
            self.stats_tab.update_stats({
                "used": used,
                "limit": limit,
                "model": model,
            })

    def update_streaming_context_limits(self, context_limit: int, model: str) -> None:
        """Оновити ліміти контексту для StreamingBuffer (при старті стрімінгу)."""
        self.streaming_buffer.update_context_limits(context_limit, model)

    def focus_input(self) -> None:
        if self.chat_tab:
            self.chat_tab.focus_input()

    # ─── API: статус та прогрес ─────────────────────────────────────────

    def _update_context_bar(self, used: int, limit: int, model: str = "") -> None:
        """Оновити тонкий QProgressBar контексту LLM з кольором і tooltip."""
        if not self.context_progress_bar:
            return
        if limit <= 0:
            self.context_progress_bar.hide()
            return

        percent = (used / limit) * 100.0
        percent = max(0.0, min(100.0, percent))
        self.context_progress_bar.setValue(int(percent))
        self.context_progress_bar.show()

        # Форматування чисел: "12 450 / 200 000 tokens (model)"
        used_str = f"{used:,}".replace(",", " ")
        limit_str = f"{limit:,}".replace(",", " ")
        tooltip = f"{used_str} / {limit_str} tokens"
        if model:
            tooltip += f" ({model})"
        self.context_progress_bar.setToolTip(tooltip)

        # Колір в залежності від відсотка
        if percent < 60:
            color = "#4caf50"  # зелений
        elif percent < 80:
            color = "#ffeb3b"  # жовтий
        elif percent < 95:
            color = "#ff9800"  # помаранчевий
        else:
            color = "#f44336"  # червоний

        self.context_progress_bar.setStyleSheet(
            f"QProgressBar#context_progress_bar {{"
            f"  border: 1px solid #555; border-radius: 3px; background: #1e1e1e;"
            f"  text-align: center;"
            f"}}"
            f"QProgressBar#context_progress_bar::chunk {{"
            f"  background: {color}; border-radius: 3px;"
            f"}}"
        )

    def _reset_context_bar(self) -> None:
        """Скинути бар контексту до 0 і сховати."""
        if self.context_progress_bar:
            self.context_progress_bar.setValue(0)
            self.context_progress_bar.hide()
            self.context_progress_bar.setToolTip("")

    def update_progress(self, progress: int, status_text: str = "") -> None:
        if status_text and self.status_label:
            self.status_label.setText(status_text)
        if progress > 0 and self.progress_bar:
            self.progress_bar.show()
            self.progress_bar.setValue(min(int(progress), 100))
        elif self.progress_bar:
            self.progress_bar.hide()

    def show_stop_button(self) -> None:
        if self.chat_tab:
            self.chat_tab.send_button.hide()
            self.chat_tab.mic_button.hide()
            self.chat_tab.restart_button.hide()
            self.chat_tab.stop_button.show()
        if self.status_label:
            self.status_label.setText("⏳ Виконання... (Стоп для переривання)")

    def hide_stop_button(self) -> None:
        if self.chat_tab:
            self.chat_tab.stop_button.hide()
            self.chat_tab.mic_button.show()
            self.chat_tab.send_button.show()
            self.chat_tab.restart_button.show()
        if self.progress_bar:
            self.progress_bar.hide()
        if self.status_label:
            self.status_label.setText(f"✅ {APP_NAME} v{APP_VERSION} — Готовий до роботи")

    # ─── API: план-панель ───────────────────────────────────────────────

    def show_plan_panel(self, steps: Any) -> None:
        if self.plan_tab:
            self.plan_tab.show_plan_panel(steps or [])

    def update_plan_step(self, data: Any) -> None:
        if self.plan_tab and isinstance(data, dict):
            self.plan_tab.update_plan_step(data)

    def finish_plan_panel(self, data: Any = None) -> None:
        if self.plan_tab:
            self.plan_tab.finish_plan_panel(data)

    def on_plan_execution_started(self) -> None:
        if self.plan_tab:
            self.plan_tab.on_plan_execution_started()

    def on_plan_execution_finished(self) -> None:
        if self.plan_tab:
            self.plan_tab.on_plan_execution_finished()

    # ─── API: підтвердження ─────────────────────────────────────────────

    def show_confirmation(self, question: str, callback: Callable[[bool], None]) -> None:
        """Показати діалог підтвердження (без міксину)."""
        reply = ConfirmationDialog(question, parent=self)
        result = reply.get_result()
        try:
            callback(result if result is not None else False)
        except Exception:
            pass

    # ─── API: thread-safe message queue (Qt signal) ──────────────────────

    def queue_message(self, msg_type: str, data: Any = None) -> None:
        """Потокобезпечне додавання повідомлення (викликається з фонових потоків)."""
        self.message_received.emit(msg_type, data)

    def _on_message(self, msg_type: str, data: Any) -> None:
        """Слот, що виконується у GUI-потоці. Маршрутизує повідомлення."""
        try:
            if msg_type == "add_message":
                sender, text = data
                self.add_message(sender, text)
            elif msg_type == "show_confirmation":
                question, cb = data
                self.show_confirmation(question, cb)
            elif msg_type == "stream_start":
                self.start_stream_message()
                # При старті стрімінгу — встановлюємо ліміти контексту
                # з активного endpoint, якщо є
                try:
                    from functions.llm.endpoint_client import get_primary_endpoint, get_model_context_limit
                    ep = get_primary_endpoint()
                    if ep:
                        model = ep.get("model", "")
                        limit = get_model_context_limit(model)
                        if limit > 0:
                            self.update_streaming_context_limits(limit, model)
                except Exception:
                    pass
            elif msg_type == "stream_chunk":
                self.append_stream_chunk(data)
            elif msg_type == "stream_end":
                self.end_stream_message()
            elif msg_type == "update_status":
                print(f"[GUI] _on_message update_status: {data}")
                self.update_progress(0, data)
            elif msg_type == "update_progress":
                progress, status_text = data
                self.update_progress(progress, status_text)
            elif msg_type == "mic_finished":
                if self.chat_tab:
                    self.chat_tab.on_mic_finished(data)
            elif msg_type == "stt_segment_added":
                segment_text = data.get("text", "") if isinstance(data, dict) else ""
                if segment_text and self.chat_tab and self.chat_tab.input_text:
                    current_text = self.chat_tab.input_text.toPlainText()
                    if current_text:
                        self.chat_tab.input_text.setText(current_text + " " + segment_text)
                    else:
                        self.chat_tab.input_text.setText(segment_text)
                    if self.status_label:
                        self.status_label.setText(f"✅ Сегмент {data.get('segment', 0)} додано")
                    self.chat_tab.input_text.setFocus()
            elif msg_type == "stt_segment_recognizing":
                if self.status_label:
                    seg = data.get("segment", 0) if isinstance(data, dict) else 0
                    self.status_label.setText(f"🔍 Розпізнавання сегменту {seg}...")
            elif msg_type == "execution_started":
                self.show_stop_button()
                self.on_plan_execution_started()
                self._reset_context_bar()
            elif msg_type == "execution_finished":
                self.hide_stop_button()
                self.on_plan_execution_finished()
            elif msg_type == "plan_started":
                self.show_plan_panel(data)
            elif msg_type == "step_update":
                self.update_plan_step(data)
            elif msg_type == "plan_finished":
                self.finish_plan_panel(data)
            elif msg_type == "context_update":
                if self.stats_tab and isinstance(data, dict):
                    self.stats_tab.update_stats(data)
                if isinstance(data, dict):
                    used = data.get("used", 0)
                    limit = data.get("limit", 0)
                    model = data.get("model", "")
                    self._update_context_bar(used, limit, model)
        except Exception as e:
            print(f"[PyQt6 GUI] Помилка обробки повідомлення {msg_type}: {e}")

    # ─── API: інтеграція з ядром ────────────────────────────────────────

    def set_assistant(self, assistant: Any) -> None:
        self.assistant = assistant

    def set_stt_controller(self, stt_controller: Any) -> None:
        self.stt_controller = stt_controller

    def run(self) -> None:
        """Запустити GUI mainloop."""
        self.show()
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication має бути створений ДО виклику run()")
        app.exec()

    def showEvent(self, event):
        """Встановити фокус на поле вводу при показі."""
        super().showEvent(event)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.focus_input())


def create_pyqt6_gui(assistant_callback: Optional[Callable] = None) -> MainWindowPyQt6:
    """Створити PyQt6 GUI. Створює QApplication якщо ще не існує."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    window = MainWindowPyQt6(assistant_callback)
    return window
