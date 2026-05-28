"""ChatTab — вкладка чату для PyQt6.

Злиття ChatPanelQtMixin + чат-частини MainWindowPyQt6.
"""
from __future__ import annotations

import datetime
import os
import re
import threading
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QClipboard
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QFrame, QMenu, QApplication,
)

from .base_tab import BaseTab
from .constants import (
    APP_NAME, ASSISTANT_TITLE, USER_TITLE,
    COLOR_USER, COLOR_ASSISTANT, COLOR_SYSTEM,
    INPUT_MIN_HEIGHT, INPUT_MAX_HEIGHT,
)


class ChatTab(BaseTab):
    """Вкладка чату: історія, ввід, кнопки, стрімінг, clipboard, STT."""

    command_submitted = pyqtSignal(str)  # команда з поля вводу

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._is_streaming = False
        self._stream_buffer = ""
        self._stream_has_content = False
        self._stream_start_pos = 0
        self._is_listening_mic = False
        self._mic_thread: threading.Thread | None = None

        # Атрибути для кнопок — створюються в setup_ui
        self.chat_history: QTextEdit | None = None
        self.input_text: QTextEdit | None = None
        self.mic_button: QPushButton | None = None
        self.send_button: QPushButton | None = None
        self.agent_button: QPushButton | None = None
        self.stop_button: QPushButton | None = None
        self.restart_button: QPushButton | None = None

    # ─── BaseTab ──────────────────────────────────────────────────────────────

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Історія чату
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setFont(QFont("Segoe UI", 10))
        self.chat_history.setObjectName("chat_history")
        layout.addWidget(self.chat_history, stretch=1)

        # Поле вводу + кнопки
        input_frame = QFrame()
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 4, 0, 0)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "Введіть команду... (Enter = відправити, Shift+Enter = новий рядок)"
        )
        self.input_text.setFont(QFont("Segoe UI", 10))
        self.input_text.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.input_text.setMaximumHeight(INPUT_MAX_HEIGHT)
        self.input_text.installEventFilter(self)
        self.input_text.textChanged.connect(self._update_input_height)
        self.input_text.setFixedHeight(INPUT_MIN_HEIGHT)
        input_layout.addWidget(self.input_text, stretch=1)

        # Кнопка мікрофон
        self.mic_button = QPushButton("🎤")
        self.mic_button.setObjectName("mic_button")
        self.mic_button.setFixedSize(48, 48)
        self.mic_button.clicked.connect(self._on_mic_clicked)
        input_layout.addWidget(self.mic_button)

        # Кнопка відправки
        self.send_button = QPushButton("➤")
        self.send_button.setObjectName("send_button")
        self.send_button.setFixedSize(48, 48)
        self.send_button.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self.send_button)

        # Кнопка агента
        self.agent_button = QPushButton("⚡AI")
        self.agent_button.setObjectName("agent_button")
        self.agent_button.setToolTip("Запустити агентний режим")
        self.agent_button.setFixedSize(58, 48)
        self.agent_button.clicked.connect(self._on_agent_clicked)
        input_layout.addWidget(self.agent_button)

        # Кнопка стоп
        self.stop_button = QPushButton("⬛")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.setFixedSize(48, 48)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.hide()
        input_layout.addWidget(self.stop_button)

        # Кнопка перезавантаження
        self.restart_button = QPushButton("🔄")
        self.restart_button.setObjectName("restart_button")
        self.restart_button.setFixedSize(48, 48)
        self.restart_button.clicked.connect(self._on_restart_clicked)
        input_layout.addWidget(self.restart_button)

        layout.addWidget(input_frame)

        # Налаштувати контекстні меню
        self._setup_clipboard_and_menus()

    def get_title(self) -> str:
        return "💬 Чат"

    def refresh(self) -> None:
        """При перемиканні на чат — фокус на ввід."""
        if self.input_text:
            self.input_text.setFocus()

    # ─── Event filter (Enter = send) ──────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if obj is self.input_text and event.type() == QEvent.Type.KeyPress:
            from PyQt6.QtCore import Qt as QtCore
            if event.key() in (QtCore.Key.Key_Return, QtCore.Key.Key_Enter):
                if event.modifiers() & QtCore.KeyboardModifier.ShiftModifier:
                    return False  # Shift+Enter = новий рядок
                self._send_text_command()
                return True
        return super().eventFilter(obj, event)

    # ─── Відправка команди ────────────────────────────────────────────────────

    def _send_text_command(self) -> None:
        if not self.input_text:
            return
        command = self.input_text.toPlainText().strip()
        if not command:
            return
        self.input_text.clear()
        self.command_submitted.emit(command)

    def _on_send_clicked(self) -> None:
        self._send_text_command()

    def _on_agent_clicked(self) -> None:
        if not self.input_text:
            return
        command = self.input_text.toPlainText().strip()
        if not command:
            return
        self.input_text.clear()
        # Агент — команда з типом "run_agent"
        mw = self._main_window
        if mw and hasattr(mw, 'assistant_callback') and mw.assistant_callback:
            mw.assistant_callback("run_agent", command)

    def _on_stop_clicked(self) -> None:
        mw = self._main_window
        if mw:
            mw.stop_execution()

    def _on_restart_clicked(self) -> None:
        mw = self._main_window
        if mw and hasattr(mw, 'assistant_callback') and mw.assistant_callback:
            mw.assistant_callback("restart", None)

    # ─── Динамічна висота поля вводу ──────────────────────────────────────────

    def _update_input_height(self) -> None:
        if not self.input_text:
            return
        doc_height = int(
            self.input_text.document().documentLayout().documentSize().height()
        )
        target = doc_height + 15
        new_height = max(INPUT_MIN_HEIGHT, min(INPUT_MAX_HEIGHT, target))
        self.input_text.setFixedHeight(new_height)

    # ─── Мікрофон (STT) ───────────────────────────────────────────────────────

    def _on_mic_clicked(self) -> None:
        if self._is_listening_mic:
            self._stop_mic_listening()
        else:
            self._start_mic_listening()

    def _start_mic_listening(self) -> None:
        self._is_listening_mic = True
        if self.mic_button:
            self.mic_button.setText("⏹")

        mw = self._main_window
        if mw and hasattr(mw, 'status_label'):
            mw.status_label.setText("🎤 Слухаю... говоріть вашу команду")
            mw.status_label.setStyleSheet("color: #e74c3c;")

        # Перевірити чи є STT контролер
        if mw and (not hasattr(mw, 'stt_controller') or mw.stt_controller is None):
            if mw and hasattr(mw, 'status_label'):
                mw.status_label.setText("❌ STT не ініціалізовано")
                mw.status_label.setStyleSheet("color: #c62828;")
            self._is_listening_mic = False
            if self.mic_button:
                self.mic_button.setText("🎤")
            return

        self._mic_thread = threading.Thread(
            target=self._mic_listen_worker, daemon=True
        )
        self._mic_thread.start()

    def _stop_mic_listening(self) -> None:
        self._is_listening_mic = False
        mw = self._main_window

        # Зупинити STT
        if mw and hasattr(mw, 'stt_controller') and mw.stt_controller:
            try:
                if hasattr(mw.stt_controller, '_stop_event') and mw.stt_controller._stop_event:
                    mw.stt_controller._stop_event.set()
                if hasattr(mw.stt_controller, 'listener'):
                    mw.stt_controller.listener.is_listening = False
            except Exception as e:
                print(f"[ChatTab] Помилка зупинки STT: {e}")

        if self.mic_button:
            self.mic_button.setText("🎤")

        if mw and hasattr(mw, 'status_label'):
            mw.status_label.setText("✅ Готовий до роботи")
            mw.status_label.setStyleSheet("")

    def _mic_listen_worker(self) -> None:
        mw = self._main_window
        try:
            if not mw or not hasattr(mw, 'stt_controller') or mw.stt_controller is None:
                if mw:
                    mw.queue_message('mic_finished', None)
                return
            text = mw.stt_controller.toggle_listening()
            mw.queue_message('mic_finished', text)
        except Exception as e:
            print(f"❌ Помилка мікрофона: {e}")
            import traceback
            traceback.print_exc()
            if mw:
                mw.queue_message('mic_finished', None)

    def on_mic_finished(self, text: str | None) -> None:
        """Викликається коли розпізнавання завершено."""
        self._stop_mic_listening()
        if text and self.input_text:
            # Вставити розпізнаний текст у поле вводу
            current_text = self.input_text.toPlainText()
            if current_text:
                self.input_text.setText(current_text + " " + text)
            else:
                self.input_text.setText(text)
            mw = self._main_window
            if mw and hasattr(mw, 'status_label'):
                mw.status_label.setText("✅ Розпізнано текст")
                mw.status_label.setStyleSheet("")
            if self.input_text:
                self.input_text.setFocus()
                # Перемістити курсор у кінець
                cursor = self.input_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.input_text.setTextCursor(cursor)

    # ─── Повідомлення в чат ───────────────────────────────────────────────────

    def _should_skip_json_message(self, text: str) -> bool:
        """Перевірити чи повідомлення є JSON/markdown, який слід пропустити."""
        stripped = text.strip()
        if stripped.startswith('{"response":') or stripped.startswith('{"response"') or stripped.startswith('```json') or stripped.startswith('```'):
            log_msg = (
                f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"chat_tab: Пропускаємо JSON/markdown: {stripped[:50]}...\n"
            )
            debug_dir = r"d:\Python\agent\debug_logs"
            os.makedirs(debug_dir, exist_ok=True)
            with open(os.path.join(debug_dir, "chat_tab.log"), "a", encoding="utf-8") as f:
                f.write(log_msg)
            return True
        return False

    def add_message(self, sender: str, message: Any) -> None:
        """Додати повідомлення до чату (чистить ANSI/LLM токени)."""
        if message is None:
            return
        if isinstance(message, (tuple, list)):
            message = " ".join(str(item) for item in message)

        # Очистити ANSI escape-коди
        message = re.sub(r'\x1b\[[0-9;]*m', '', str(message))
        message = re.sub(r'\[\d{1,3}(?:;\d{1,3})*m', '', message)

        # Прибрати сирі LLM-токени
        if sender == "assistant" and ('<|' in message or 'channel' in message.lower()):
            try:
                from functions.logic_llm import clean_llm_tokens  # type: ignore
                cleaned = clean_llm_tokens(message)
                if cleaned:
                    message = cleaned
            except Exception:
                message = re.sub(r'<\|[^|]*\|>', '', message)

        if not self.chat_history:
            return

        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_history.setTextCursor(cursor)

        # Очищаємо подвійні префікси
        if sender == "assistant":
            prefixes_to_remove = [
                f"{ASSISTANT_TITLE}: ",
                "⚡ МАРК: ",
                "МАРК: ",
            ]
            for prefix in prefixes_to_remove:
                if message.startswith(prefix):
                    message = message[len(prefix):].strip()
                    break

        # Пропускаємо JSON відповіді
        if sender == "assistant" and self._should_skip_json_message(message):
            return

        # Роздільник
        current_text = self.chat_history.toPlainText().strip()
        skip_separator = False

        if current_text and sender == "assistant" and message.strip().startswith('{'):
            lines = current_text.split('\n')
            for line in reversed(lines):
                s = line.strip()
                if s and not s.startswith('⚡') and not s.startswith('👑'):
                    if s.startswith('{'):
                        skip_separator = True
                    break

        if current_text and sender == "assistant":
            if message.strip().startswith(('🔊', '✅', '⚡')):
                lines = current_text.split('\n')
                last_line = lines[-1].strip() if lines else ''
                if last_line.startswith(('🔊', '✅', '⚡')):
                    skip_separator = True

        if current_text:
            cursor.insertText("\n" if skip_separator else "\n" + "-" * 50 + "\n")

        # Префікс відправника
        if not skip_separator:
            if sender == "user":
                prefix = f"{USER_TITLE}: "
            else:
                prefix = f"{ASSISTANT_TITLE}: "
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.Bold)
            cursor.insertText(prefix, fmt)

        cursor.insertText(message + "\n")
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

        # Оновити статус (тільки для user-повідомлень)
        mw = self._main_window
        if sender == "user" and mw and hasattr(mw, 'status_label'):
            import time as _time
            ts = _time.strftime('%H:%M:%S')
            mw.status_label.setText(f"✅ Відповідь готова | {ts}")
        # Для assistant статус вже оновлено через _update_status_after_llm
        # з реальним часом LLM (наприклад "✅ Gemini (12.8с)")

    # ─── Стрімінг ─────────────────────────────────────────────────────────────

    def start_stream_message(self) -> None:
        if self._is_streaming or not self.chat_history:
            return
        self._is_streaming = True
        self._stream_buffer = ""
        self._stream_has_content = False

        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_history.setTextCursor(cursor)

        current_text = self.chat_history.toPlainText().strip()
        skip_separator = False
        if current_text:
            lines = current_text.split('\n')
            for line in reversed(lines):
                s = line.strip()
                if s and not s.startswith('⚡') and not s.startswith('👑'):
                    if s.startswith('{'):
                        skip_separator = True
                    break
            cursor.insertText("\n" if skip_separator else "\n" + "-" * 50 + "\n")

        self._stream_start_pos = cursor.position()

        if not skip_separator:
            prefix = f"{ASSISTANT_TITLE}: "
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.Bold)
            cursor.insertText(prefix, fmt)

        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def append_stream_chunk(self, chunk: str) -> None:
        if not self._is_streaming:
            self.start_stream_message()
        if not self.chat_history:
            return

        if chunk and chunk.strip():
            self._stream_has_content = True

        # Фільтрація JSON чанків
        if self._should_skip_json_message(chunk):
            self._stream_buffer += chunk
            return

        self._stream_buffer += chunk
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def end_stream_message(self) -> None:
        if not self.chat_history:
            return

        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if not self._stream_has_content:
            # Видаляємо пустий префікс
            cursor.setPosition(self._stream_start_pos, QTextCursor.MoveMode.MoveAnchor)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            error_msg = f"\n{ASSISTANT_TITLE}: ⚠️ Порожня відповідь (можливо, перевантажено контекст LLM)\n"
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.Bold)
            cursor.insertText(error_msg, fmt)
        else:
            cursor.insertText("\n")
            fmt = QTextCharFormat()
            fmt.setForeground(Qt.GlobalColor.green)
            cursor.insertText(" ✅", fmt)

        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

        self._is_streaming = False
        self._stream_buffer = ""
        # Статус-бар не перезаписуємо — він вже містить час LLM
        # (оновлюється через _update_status_after_llm в logic_commands.py)

    def focus_input(self) -> None:
        """Встановити фокус на поле вводу."""
        if self.input_text:
            self.input_text.setFocus()

    # ─── Clipboard та контекстні меню ─────────────────────────────────────────

    def _setup_clipboard_and_menus(self) -> None:
        if not self.input_text or not self.chat_history:
            return
        self.input_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.input_text.customContextMenuRequested.connect(self._show_input_context_menu)

        self.chat_history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_history.customContextMenuRequested.connect(self._show_chat_context_menu)

    def _show_input_context_menu(self, pos) -> None:
        menu = QMenu(self)
        has_sel = bool(self.input_text.textCursor().selectedText())
        clip = QApplication.clipboard()
        has_clip = bool(clip.text(QClipboard.Mode.Clipboard))

        cut_action = menu.addAction("Вирізати (Ctrl+X)")
        cut_action.setEnabled(has_sel)
        cut_action.triggered.connect(self._clipboard_cut)

        copy_action = menu.addAction("Копіювати (Ctrl+C)")
        copy_action.setEnabled(has_sel)
        copy_action.triggered.connect(lambda: self._clipboard_copy(self.input_text))

        paste_action = menu.addAction("Вставити (Ctrl+V)")
        paste_action.setEnabled(has_clip)
        paste_action.triggered.connect(self._clipboard_paste)

        menu.addSeparator()
        select_all_action = menu.addAction("Виділити все (Ctrl+A)")
        select_all_action.triggered.connect(lambda: self._clipboard_select_all(self.input_text))

        menu.exec(self.input_text.mapToGlobal(pos))

    def _show_chat_context_menu(self, pos) -> None:
        menu = QMenu(self)
        has_sel = bool(self.chat_history.textCursor().selectedText())

        copy_action = menu.addAction("Копіювати (Ctrl+C)")
        copy_action.setEnabled(has_sel)
        copy_action.triggered.connect(lambda: self._clipboard_copy(self.chat_history))

        menu.addSeparator()
        select_all_action = menu.addAction("Виділити все (Ctrl+A)")
        select_all_action.triggered.connect(lambda: self._clipboard_select_all(self.chat_history))

        menu.exec(self.chat_history.mapToGlobal(pos))

    def _clipboard_copy(self, widget: QTextEdit | None = None) -> None:
        if widget is None:
            widget = self.chat_history
        if not widget:
            return
        selected = widget.textCursor().selectedText()
        if not selected:
            return
        QApplication.clipboard().setText(selected)

    def _clipboard_cut(self) -> None:
        if not self.input_text:
            return
        selected = self.input_text.textCursor().selectedText()
        if not selected:
            return
        QApplication.clipboard().setText(selected)
        cursor = self.input_text.textCursor()
        cursor.removeSelectedText()

    def _clipboard_paste(self) -> None:
        if not self.input_text:
            return
        text = QApplication.clipboard().text(QClipboard.Mode.Clipboard)
        if not text:
            return
        cursor = self.input_text.textCursor()
        cursor.insertText(text)

    def _clipboard_select_all(self, widget: QTextEdit | None = None) -> None:
        if widget is None:
            widget = self.chat_history
        if not widget:
            return
        cursor = widget.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        widget.setTextCursor(cursor)
