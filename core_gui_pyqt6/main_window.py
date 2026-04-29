"""PyQt6 MainWindow — повноцінний еквівалент Tkinter `core_gui/main_window.py`.

Контракт API (повинен співпадати з Tkinter-аналогом):
    queue_message(msg_type, data)   — потокобезпечне додавання повідомлення
    add_message(sender, message)    — додати повідомлення в чат
    update_progress(progress, text) — оновити прогрес/статус
    show_stop_button() / hide_stop_button()
    start_stream_message() / append_stream_chunk(chunk) / end_stream_message()
    show_plan_panel(steps) / update_plan_step(data) / finish_plan_panel(data)
    show_confirmation(question, callback)
    set_assistant(assistant)
    set_stt_controller(stt_controller)
    run()                           — запустити mainloop

Замість Tkinter `queue.Queue + root.after(100)` використовуємо Qt signal `message_received`,
який автоматично виконує слот у GUI-потоці (thread-safe).
"""
from __future__ import annotations

import sys
from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QTextCursor, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QSplitter, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QFrame, QSizePolicy,
    QTabWidget,
)

from .settings_tab_qt import SettingsTabQtMixin
from .chat_panel_qt import ChatPanelQtMixin
from .plan_panel_qt import PlanPanelQtMixin
from .confirmation_qt import ConfirmationQtMixin


ASSISTANT_TITLE = "⚡ МАРК"
USER_TITLE = "👑 ВИ"


class MainWindowPyQt6(QMainWindow, SettingsTabQtMixin, ChatPanelQtMixin, PlanPanelQtMixin, ConfirmationQtMixin):
    """Головне вікно асистента на PyQt6 (повний еквівалент Tkinter версії)."""

    # Qt-сигнал для потокобезпечного додавання повідомлень з фонового потоку.
    # Аналог `queue.Queue + after(100)` в Tkinter, але без polling.
    message_received = pyqtSignal(str, object)

    def __init__(self, assistant_callback: Optional[Callable] = None):
        super().__init__()
        self.assistant_callback = assistant_callback
        self.assistant: Optional[Any] = None
        self.stt_controller: Optional[Any] = None
        self._is_streaming = False
        self._stream_buffer = ""
        self._settings_built = False
        self._is_listening_mic = False

        # Відновити геометрію вікна до show() як в Tkinter
        geom_restored = False
        try:
            from functions.core_settings import get_setting
            saved_geom = get_setting("WINDOW_GEOMETRY", None)
            if saved_geom:
                # Формат: WxH+X+Y або WxH
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
            pass  # Використовуємо дефолтний розмір

        self.setWindowTitle("МАРК — Асистент (PyQt6)")

        # Встановлюємо дефолтну геометрію тільки якщо не відновлено
        if not geom_restored:
            self.setGeometry(100, 100, 1100, 750)

        self._init_ui()
        self._apply_styles()

        # Прив'язуємо сигнал до слоту: усі повідомлення з фонових потоків
        # автоматично виконуються у GUI-потоці.
        self.message_received.connect(self._on_message)

    def closeEvent(self, event) -> None:
        """Зберегти геометрію вікна при закритті."""
        try:
            from functions.core_settings import get_settings
            geom = self.geometry()
            w, h = geom.width(), geom.height()
            x, y = geom.x(), geom.y()
            geom_str = f"{w}x{h}+{x}+{y}"
            get_settings().set("WINDOW_GEOMETRY", geom_str, persist=True)
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

        # QTabWidget: Chat / Plan / Settings
        self.notebook = QTabWidget()
        root_layout.addWidget(self.notebook, stretch=1)

        # --- Tab 1: Chat (чата з планом) ---
        chat_tab = QWidget()
        chat_layout = QVBoxLayout(chat_tab)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(4)

        # Splitter: чат | план
        splitter = QSplitter(Qt.Orientation.Horizontal)
        chat_layout.addWidget(splitter, stretch=1)

        # Ліва частина: чат
        chat_container = QWidget()
        chat_container_layout = QVBoxLayout(chat_container)
        chat_container_layout.setContentsMargins(0, 0, 0, 0)
        chat_container_layout.setSpacing(4)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setFont(QFont("Segoe UI", 10))
        self.chat_history.setObjectName("chat_history")
        chat_container_layout.addWidget(self.chat_history, stretch=1)

        # Поле вводу + кнопки
        input_frame = QFrame()
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 4, 0, 0)
        input_layout.setSpacing(4)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Введіть команду... (Enter = відправити, Shift+Enter = новий рядок)")
        self.input_text.setFont(QFont("Segoe UI", 10))
        self.input_text.setFixedHeight(80)
        self.input_text.installEventFilter(self)
        input_layout.addWidget(self.input_text, stretch=1)

        # Кнопка мікрофон 🎤
        self.mic_button = QPushButton("🎤")
        self.mic_button.setObjectName("mic_button")
        self.mic_button.setFixedSize(48, 48)
        self.mic_button.clicked.connect(self.on_mic_clicked)
        input_layout.addWidget(self.mic_button)

        # Кнопка агент 🤖
        self.agent_button = QPushButton("🤖")
        self.agent_button.setObjectName("agent_button")
        self.agent_button.setFixedSize(48, 48)
        self.agent_button.setToolTip("Запустити AgentLoop (observe → plan → act → check)")
        self.agent_button.clicked.connect(self.run_agent_loop)
        input_layout.addWidget(self.agent_button)

        # Кнопка відправки ➤
        self.send_button = QPushButton("➤")
        self.send_button.setObjectName("send_button")
        self.send_button.setFixedSize(48, 48)
        self.send_button.clicked.connect(self.send_text_command)
        input_layout.addWidget(self.send_button)

        # Кнопка перезавантаження � (для відладки)
        self.restart_button = QPushButton("🔄")
        self.restart_button.setObjectName("restart_button")
        self.restart_button.setFixedSize(48, 48)
        self.restart_button.setToolTip("Перезавантажити агента (без підтвердження)")
        self.restart_button.clicked.connect(self._on_restart_agent)
        input_layout.addWidget(self.restart_button)

        # Кнопка стоп ⬛
        self.stop_button = QPushButton("⬛ СТОП")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.setFixedHeight(48)
        self.stop_button.clicked.connect(self.stop_execution)
        self.stop_button.hide()
        input_layout.addWidget(self.stop_button)

        chat_container_layout.addWidget(input_frame)
        splitter.addWidget(chat_container)

        # Права частина: план-панель
        plan_container = QWidget()
        plan_layout = QVBoxLayout(plan_container)
        plan_layout.setContentsMargins(4, 0, 0, 0)

        plan_header = QLabel("📋 План")
        plan_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        plan_layout.addWidget(plan_header)

        self.plan_list = QListWidget()
        self.plan_list.setObjectName("plan_list")
        plan_layout.addWidget(self.plan_list, stretch=1)

        plan_buttons = QHBoxLayout()
        self.plan_run_btn = QPushButton("▶ Виконати")
        self.plan_run_btn.setObjectName("plan_run_btn")
        self.plan_run_btn.clicked.connect(self._on_run_plan)
        plan_buttons.addWidget(self.plan_run_btn)

        self.plan_stop_btn = QPushButton("⏹ Стоп")
        self.plan_stop_btn.setObjectName("plan_stop_btn")
        self.plan_stop_btn.clicked.connect(self._on_stop_plan)
        self.plan_stop_btn.hide()
        plan_buttons.addWidget(self.plan_stop_btn)

        plan_layout.addLayout(plan_buttons)
        splitter.addWidget(plan_container)
        splitter.setSizes([750, 350])

        self.notebook.addTab(chat_tab, "💬 Чат")

        # --- Tab 2: Plan (поки що порожньо, план показується в чат-вкладці) ---
        plan_tab = QWidget()
        plan_tab_layout = QVBoxLayout(plan_tab)
        plan_tab_layout.addWidget(QLabel("План-панель доступна у вкладці '💬 Чат' (справа)."))
        self.notebook.addTab(plan_tab, "📋 План")

        # --- Tab 3: Settings ---
        self.settings_container = QWidget()
        self.notebook.addTab(self.settings_container, "⚙️ Налаштування")
        self.notebook.currentChanged.connect(self._on_tab_changed)

        # --- Статус-бар з прогресом ---
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("✅ Готовий до роботи")
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
        """QSS — єдина тема кольорів (синій шрифт, чорний фон як в акордеонах)."""
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
            QPushButton#agent_button { background: #2e7d32; }
            QPushButton#agent_button:hover { background: #1b5e20; }
            QPushButton#restart_button { background: #ff9800; }
            QPushButton#restart_button:hover { background: #f57c00; }
            QPushButton#stop_button, QPushButton#plan_stop_btn { background: #e65100; }
            QPushButton#stop_button:hover, QPushButton#plan_stop_btn:hover { background: #bf360c; }
            QPushButton#plan_run_btn { background: #2e7d32; }
            QListWidget#plan_list { background: #1e1e1e; color: #1976d2; border: 1px solid #444; border-radius: 4px; }
            QLabel#status_label { color: #555; padding: 4px; }
            QProgressBar { border: 1px solid #ccc; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background: #1976d2; }
        """)

    # ─── Подія Enter у полі вводу ─────────────────────────────────────────────

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.input_text and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False  # Shift+Enter — новий рядок
                self.send_text_command()
                return True
        return super().eventFilter(obj, event)

    # ─── API: відправка команди ───────────────────────────────────────────────

    def send_text_command(self) -> None:
        command = self.input_text.toPlainText().strip()
        if not command:
            return
        self.input_text.clear()
        if self.assistant_callback:
            self.assistant_callback("process_text", command)

    def run_agent_loop(self) -> None:
        """Запустити AgentLoop напряму для тексту з поля вводу."""
        command = self.input_text.toPlainText().strip()
        if not command:
            return
        self.input_text.clear()
        if self.assistant_callback:
            self.assistant_callback("run_agent", command)

    def stop_execution(self) -> None:
        if self.assistant_callback:
            self.assistant_callback("stop_execution", None)
            self.assistant_callback("stop_plan", None)
        self.hide_stop_button()

    def on_mic_clicked(self) -> None:
        """Обробник натискання кнопки мікрофона."""
        print(f"[DEBUG] on_mic_clicked called, stt_controller: {self.stt_controller}")

        if not self.stt_controller or not hasattr(self.stt_controller, "toggle_listening"):
            print(f"[DEBUG] stt_controller is None or has no toggle_listening method")
            self.add_message("system", "❌ STT контролер не налаштовано")
            return

        # Якщо вже слухаємо — зупинити
        if getattr(self, '_is_listening_mic', False):
            self._stop_mic_listening()
            return

        # Почати слухання
        self._start_mic_listening()

    def _start_mic_listening(self) -> None:
        """Почати запис з мікрофона."""
        import threading
        self._is_listening_mic = True

        # Оновити UI - перемкнути кнопку
        self.mic_button.hide()
        self.mic_button.setText("⏹")
        self.mic_button.show()

        self.status_label.setText("🎤 Слухаю... говоріть вашу команду")
        self.status_label.setStyleSheet("color: #e74c3c;")

        # Запустити в окремому потоці щоб не блокувати GUI
        self._mic_thread = threading.Thread(target=self._mic_listen_worker, daemon=True)
        self._mic_thread.start()

    def _stop_mic_listening(self) -> None:
        """Зупинити запис (викликається автоматично після розпізнавання)."""
        self._is_listening_mic = False

        # Оновити UI - повернути кнопку
        self.mic_button.hide()
        self.mic_button.setText("🎤")
        self.mic_button.show()

        self.status_label.setText("✅ Готовий до роботи")
        self.status_label.setStyleSheet("")

    def _mic_listen_worker(self) -> None:
        """Потік для запису та розпізнавання."""
        try:
            # Слухаємо
            text = self.stt_controller.toggle_listening()

            # Повернутися в GUI потік через Qt signal
            self.queue_message('mic_finished', text)

        except Exception as e:
            print(f"❌ Помилка мікрофона: {e}")
            self.queue_message('mic_finished', None)

    def _on_mic_finished(self, text: str | None) -> None:
        """Викликається коли розпізнавання завершено."""
        self._stop_mic_listening()

        if text:
            current_text = self.input_text.toPlainText()
            if current_text:
                # Додаємо пробіл якщо текст не порожній
                self.input_text.setText(current_text + " " + text)
            else:
                self.input_text.setText(text)
            self.input_text.setFocus()
            self.status_label.setText("✅ Розпізнано текст")
            self.status_label.setStyleSheet("")

    def _on_run_plan(self) -> None:
        if self.assistant_callback:
            self.plan_run_btn.hide()
            self.plan_stop_btn.show()
            self.assistant_callback("run_plan", None)

    def _on_stop_plan(self) -> None:
        if self.assistant_callback:
            self.assistant_callback("stop_plan", None)
        self.plan_stop_btn.hide()
        self.plan_run_btn.show()

    # ─── API: повідомлення в чат ──────────────────────────────────────────────

    def add_message(self, sender: str, message: Any) -> None:
        if message is None:
            return
        text = str(message)
        if sender == "user":
            prefix = f"\n{USER_TITLE}: "
        elif sender == "system":
            prefix = "\n• "
        else:
            prefix = f"\n{ASSISTANT_TITLE}: "
        self.chat_history.append(prefix + text)
        self._scroll_chat_to_end()

    def _scroll_chat_to_end(self) -> None:
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_history.setTextCursor(cursor)

    # ─── API: streaming ───────────────────────────────────────────────────────

    def start_stream_message(self) -> None:
        if self._is_streaming:
            return
        self._is_streaming = True
        self._stream_buffer = ""
        self.chat_history.append(f"\n{ASSISTANT_TITLE}: ")

    def append_stream_chunk(self, chunk: str) -> None:
        if not self._is_streaming:
            self.start_stream_message()
        self._stream_buffer += chunk
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self._scroll_chat_to_end()

    def end_stream_message(self) -> None:
        self._is_streaming = False
        self._stream_buffer = ""

    # ─── API: статус та прогрес ───────────────────────────────────────────────

    def update_progress(self, progress: int, status_text: str = "") -> None:
        if status_text:
            self.status_label.setText(status_text)
        if progress > 0:
            self.progress_bar.show()
            self.progress_bar.setValue(min(int(progress), 100))
        else:
            self.progress_bar.hide()

    def show_stop_button(self) -> None:
        self.send_button.hide()
        self.mic_button.hide()
        self.agent_button.hide()
        self.restart_button.hide()
        self.stop_button.show()
        self.status_label.setText("⏳ Виконання... (Стоп для переривання)")

    def hide_stop_button(self) -> None:
        self.stop_button.hide()
        self.mic_button.show()
        self.agent_button.show()
        self.send_button.show()
        self.restart_button.show()
        self.progress_bar.hide()
        self.status_label.setText("✅ Готовий до роботи")

    def _on_restart_agent(self) -> None:
        """Перезавантажити агента (без підтвердження)."""
        self.add_message("system", "🔁 Перезавантаження агента...")

        import subprocess
        import os
        import sys

        # Отримуємо шлях до run.py
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        run_script = os.path.join(root_dir, "run.py")

        # Запускаємо новий процес з тим же Python інтерпретатором
        subprocess.Popen([sys.executable, run_script])

        # Закриваємо поточний процес
        QApplication.quit()
        sys.exit(0)

    # ─── API: план-панель ─────────────────────────────────────────────────────

    def show_plan_panel(self, steps: Any) -> None:
        self.plan_list.clear()
        if not steps:
            return
        for i, step in enumerate(steps, 1):
            if isinstance(step, dict):
                desc = step.get("description") or step.get("action") or str(step)
            else:
                desc = str(step)
            item = QListWidgetItem(f"⏸  {i}. {desc}")
            self.plan_list.addItem(item)

    def update_plan_step(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        idx = data.get("index")
        status = data.get("status", "running")
        if idx is None or idx < 0 or idx >= self.plan_list.count():
            return
        icons = {"running": "▶", "success": "✅", "error": "❌", "skipped": "⏭"}
        icon = icons.get(status, "•")
        item = self.plan_list.item(idx)
        text = item.text()
        # Замінити тільки перший символ-іконку
        parts = text.split(" ", 1)
        if len(parts) == 2:
            item.setText(f"{icon} {parts[1]}")

    def finish_plan_panel(self, data: Any = None) -> None:
        self.plan_stop_btn.hide()
        self.plan_run_btn.show()

    def on_plan_execution_started(self) -> None:
        self.plan_run_btn.hide()
        self.plan_stop_btn.show()

    def on_plan_execution_finished(self) -> None:
        self.plan_stop_btn.hide()
        self.plan_run_btn.show()

    # ─── API: підтвердження ───────────────────────────────────────────────────

    def show_confirmation(self, question: str, callback: Callable[[bool], None]) -> None:
        reply = QMessageBox.question(
            self, "Підтвердження", question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        result = reply == QMessageBox.StandardButton.Yes
        try:
            callback(result)
        except Exception:
            pass

    # ─── API: thread-safe message queue (Qt signal) ───────────────────────────

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
            elif msg_type == "stream_chunk":
                self.append_stream_chunk(data)
            elif msg_type == "stream_end":
                self.end_stream_message()
            elif msg_type == "update_status":
                self.update_progress(0, data)
            elif msg_type == "update_progress":
                progress, status_text = data
                self.update_progress(progress, status_text)
            elif msg_type == "mic_finished":
                self._on_mic_finished(data)
            elif msg_type == "execution_started":
                self.show_stop_button()
                self.on_plan_execution_started()
            elif msg_type == "execution_finished":
                self.hide_stop_button()
                self.on_plan_execution_finished()
            elif msg_type == "plan_started":
                self.show_plan_panel(data)
            elif msg_type == "step_update":
                self.update_plan_step(data)
            elif msg_type == "plan_finished":
                self.finish_plan_panel(data)
        except Exception as e:
            print(f"[PyQt6 GUI] Помилка обробки повідомлення {msg_type}: {e}")

    # ─── API: інтеграція з ядром ──────────────────────────────────────────────

    def set_assistant(self, assistant: Any) -> None:
        self.assistant = assistant

    def set_stt_controller(self, stt_controller: Any) -> None:
        self.stt_controller = stt_controller

    def run(self) -> None:
        """Запустити GUI mainloop. Має бути викликаний у головному потоці."""
        self.show()
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication має бути створений ДО виклику run()")
        app.exec()


def create_pyqt6_gui(assistant_callback: Optional[Callable] = None) -> MainWindowPyQt6:
    """Створити PyQt6 GUI. Створює QApplication якщо ще не існує."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    window = MainWindowPyQt6(assistant_callback)
    return window
