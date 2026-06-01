"""ChatPanelQtMixin — логіка чат-панелі для PyQt6.

Порт core_gui/chat_panel.py (Tkinter) на PyQt6.
"""
from __future__ import annotations

import re
from typing import Any

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QClipboard, QKeySequence
from PyQt6.QtWidgets import (
    QWidget,
    QTextEdit,
    QMenu,
    QApplication,
)

ASSISTANT_TITLE = "⚡ МАРК"
ASSISTANT_EMOJI = "⚡"
ASSISTANT_NAME = "МАРК"
USER_TITLE = "👑 ВИ"


class ChatPanelQtMixin:
    """Міксин для чат-панелі (історія, ввід, clipboard, стрімінг, контекстні меню).

    Очікує атрибути:
        - self.chat_history: QTextEdit (read-only)
        - self.input_text: QTextEdit (editable)
        - self.assistant_callback: callable (optional)
        - self.status_label: QLabel (optional)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_streaming = False
        self._stream_buffer = ""
        self._stream_has_content = False
        self._last_sent_command = None
        self._last_sent_time = 0.0
        self._input_active = False
        self._awaiting_confirmation = False

        # Setup clipboard та context menus
        self._setup_clipboard_and_menus()

    # ---------- Базові методи ----------

    def focus_input(self) -> None:
        """Встановити фокус на поле вводу."""
        self.input_text.setFocus()

    def add_message(self, sender: str, message: Any) -> None:
        """Додати повідомлення до чату (чистить ANSI/LLM токени)."""
        # Захист від None
        if message is None:
            message = ""
        # Захист від випадкової передачі кортежу
        if isinstance(message, (tuple, list)):
            message = " ".join(str(item) for item in message)

        # Очистити ANSI escape-коди
        message = re.sub(r'\x1b\[[0-9;]*m', '', str(message))
        message = re.sub(r'\[\d{1,3}(?:;\d{1,3})*m', '', message)

        # Прибрати сирі LLM-токени
        if sender == "assistant" and ('<|' in message or 'channel' in message.lower()):
            try:
                from functions.logic_llm import clean_llm_tokens
                cleaned = clean_llm_tokens(message)
                if cleaned:
                    message = cleaned
            except Exception:
                message = re.sub(r'<\|[^|]*\|>', '', message)

        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_history.setTextCursor(cursor)

        # Очищаємо подвійні префікси
        if sender == "assistant":
            prefixes_to_remove = [
                f"{ASSISTANT_TITLE}: ",
                f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}: ",
                "⚡ МАРК: ",
                "МАРК: ",
            ]
            for prefix in prefixes_to_remove:
                if message.startswith(prefix):
                    message = message[len(prefix):].strip()
                    break

        # Розпізнаємо та парсимо JSON відповіді замість того, щоб їх ковтати
        if sender == "assistant":
            stripped_msg = message.strip()
            # Логування для відстеження
            import datetime
            log_msg = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] chat_panel_qt add_message: sender={sender}, message={stripped_msg[:100]}...\n"
            with open(r"d:\Python\agent\debug_logs\chat_panel_qt.log", "a", encoding="utf-8") as f:
                f.write(log_msg)

            # Спроба розпарсити JSON-повідомлення замість ігнорування
            parsed_text = None
            try:
                import json
                # Перевіряємо markdown json блок (```json ... ```)
                if stripped_msg.startswith('```json'):
                    # Видаляємо markdown-обгортку
                    json_content = stripped_msg
                    if json_content.startswith('```json'):
                        json_content = json_content[7:]  # прибираємо ```json
                    if json_content.endswith('```'):
                        json_content = json_content[:-3]  # прибираємо ```
                    json_content = json_content.strip()
                    if json_content:
                        data = json.loads(json_content)
                        if isinstance(data, dict) and "response" in data:
                            parsed_text = str(data["response"])
                # Перевіряємо чистий JSON
                elif stripped_msg.startswith('{'):
                    data = json.loads(stripped_msg)
                    if isinstance(data, dict) and "response" in data:
                        parsed_text = str(data["response"])
            except json.JSONDecodeError:
                # Не вдалося розпарсити — залишаємо оригінальний текст
                pass
            except Exception:
                pass

            if parsed_text is not None:
                log_msg = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] chat_panel_qt: JSON розпарсено, text={parsed_text[:100]}...\n"
                with open(r"d:\Python\agent\debug_logs\chat_panel_qt.log", "a", encoding="utf-8") as f:
                    f.write(log_msg)
                message = parsed_text
            else:
                # Якщо це був JSON, але не вдалося розпарсити — показуємо сирий текст
                if stripped_msg.startswith('{"response":') or stripped_msg.startswith('{"response"') or stripped_msg.startswith('```json'):
                    log_msg = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] chat_panel_qt: JSON не розпарсено, показую сирий текст: {stripped_msg[:100]}...\n"
                    with open(r"d:\Python\agent\debug_logs\chat_panel_qt.log", "a", encoding="utf-8") as f:
                        f.write(log_msg)

        # Додаємо роздільник (або об'єднуємо JSON-блоки)
        current_text = self.chat_history.toPlainText().strip()
        skip_separator = False
        if current_text and sender == "assistant" and message.strip().startswith('{'):
            lines = current_text.split('\n')
            last_nonempty = None
            for line in reversed(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('⚡') and not stripped.startswith('👑'):
                    last_nonempty = stripped
                    break
            if last_nonempty and last_nonempty.startswith('{'):
                skip_separator = True

        # Пропускаємо роздільник для коротких системних повідомлень
        if current_text and sender == "assistant":
            if message.strip().startswith(('🔊', '✅', '⚡')):
                lines = current_text.split('\n')
                last_line = lines[-1].strip() if lines else ''
                if last_line.startswith(('🔊', '✅', '⚡')):
                    skip_separator = True

        if current_text:
            if skip_separator:
                cursor.insertText("\n")
            else:
                cursor.insertText("\n" + "-" * 50 + "\n")

        # Відправник
        if not skip_separator:
            if sender == "user":
                prefix = f"{USER_TITLE}: "
            else:
                prefix = f"{ASSISTANT_TITLE}: "

            # Bold формат для префіксу
            fmt = QTextCharFormat()
            fmt.setFontWeight(QTextCharFormat.Weight.Bold)
            cursor.insertText(prefix, fmt)

        cursor.insertText(message + "\n")
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

        # Оновити статус (тільки для user-повідомлень)
        # Для assistant статус вже оновлено через _update_status_after_llm
        # з реальним часом LLM (наприклад "✅ Gemini (12.8с)")
        if sender == "user" and hasattr(self, 'status_label'):
            import time as _time
            ts = _time.strftime('%H:%M:%S')
            self.status_label.setText(f"✅ Відповідь готова | {ts}")

    # ---------- Стрім-повідомлення ----------

    def start_stream_message(self) -> None:
        """Почати нове повідомлення асистента для стрімінгу."""
        if self._is_streaming:
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
            last_nonempty = None
            for line in reversed(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('⚡') and not stripped.startswith('👑'):
                    last_nonempty = stripped
                    break
            if last_nonempty and last_nonempty.startswith('{'):
                skip_separator = True

            if skip_separator:
                cursor.insertText("\n")
            else:
                cursor.insertText("\n" + "-" * 50 + "\n")

        # Зберігаємо позицію префіксу для можливого видалення
        self._stream_start_pos = cursor.position()

        if not skip_separator:
            prefix = f"{ASSISTANT_TITLE}: "
            fmt = QTextCharFormat()
            fmt.setFontWeight(QTextCharFormat.Weight.Bold)
            cursor.insertText(prefix, fmt)

        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def append_stream_chunk(self, text: str) -> None:
        """Додати фрагмент тексту до стрімінгового повідомлення."""
        if text and text.strip():
            self._stream_has_content = True
        self._stream_buffer += text

        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def end_stream_message(self) -> None:
        """Завершити стрімінг (додати новий рядок).
        
        Не перезаписує статус-бар — він вже оновлений через _update_status_after_llm
        з реальним часом відповіді LLM (наприклад, "✅ Gemini (0.9с)").
        """
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if not self._stream_has_content:
            # Видаляємо пустий префікс
            if hasattr(self, '_stream_start_pos'):
                cursor.setPosition(self._stream_start_pos, QTextCursor.MoveMode.MoveAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()

            error_msg = f"\n{ASSISTANT_TITLE}: ⚠️ Порожня відповідь (можливо, перевантажено контекст LLM)\n"
            fmt = QTextCharFormat()
            fmt.setFontWeight(QTextCharFormat.Weight.Bold)
            cursor.insertText(error_msg, fmt)
        else:
            cursor.insertText("\n")
            # Додати зелений ✅ в кінці
            fmt = QTextCharFormat()
            fmt.setForeground(Qt.GlobalColor.green)
            cursor.insertText(" ✅", fmt)

        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

        self._is_streaming = False
        self._stream_buffer = ""
        # Статус-бар не перезаписуємо — він вже містить час LLM
        # (оновлюється через _update_status_after_llm в logic_commands.py)

    # ---------- Clipboard та контекстні меню ----------

    def _setup_clipboard_and_menus(self) -> None:
        """Налаштувати clipboard та контекстні меню."""
        # Context menu для input_text
        self.input_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.input_text.customContextMenuRequested.connect(self._show_input_context_menu)

        # Context menu для chat_history
        self.chat_history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_history.customContextMenuRequested.connect(self._show_chat_context_menu)

    def _show_input_context_menu(self, pos) -> None:
        """Показати контекстне меню для поля вводу (editable)."""
        menu = QMenu(self)

        has_sel = bool(self.input_text.textCursor().selectedText())
        clip = QApplication.clipboard()
        has_clip = bool(clip.text(QClipboard.Mode.Clipboard))

        cut_action = menu.addAction("Вирізати (Ctrl+X)")
        cut_action.setEnabled(has_sel)
        cut_action.triggered.connect(self._clipboard_cut)

        copy_action = menu.addAction("Копіювати (Ctrl+C)")
        copy_action.setEnabled(has_sel)
        copy_action.triggered.connect(self._clipboard_copy)

        paste_action = menu.addAction("Вставити (Ctrl+V)")
        paste_action.setEnabled(has_clip)
        paste_action.triggered.connect(self._clipboard_paste)

        menu.addSeparator()

        select_all_action = menu.addAction("Виділити все (Ctrl+A)")
        select_all_action.triggered.connect(self._clipboard_select_all)

        menu.exec(self.input_text.mapToGlobal(pos))

    def _show_chat_context_menu(self, pos) -> None:
        """Показати контекстне меню для історії чату (read-only)."""
        menu = QMenu(self)

        has_sel = bool(self.chat_history.textCursor().selectedText())

        copy_action = menu.addAction("Копіювати (Ctrl+C)")
        copy_action.setEnabled(has_sel)
        copy_action.triggered.connect(lambda: self._clipboard_copy(self.chat_history))

        menu.addSeparator()

        select_all_action = menu.addAction("Виділити все (Ctrl+A)")
        select_all_action.triggered.connect(lambda: self._clipboard_select_all(self.chat_history))

        menu.exec(self.chat_history.mapToGlobal(pos))

    def _clipboard_copy(self, widget: QTextEdit = None) -> None:
        """Копіювати виділений текст у буфер обміну."""
        if widget is None:
            widget = self.chat_history
        selected = widget.textCursor().selectedText()
        if not selected:
            return
        QApplication.clipboard().setText(selected)

    def _clipboard_cut(self) -> None:
        """Вирізати виділений текст у буфер обміну."""
        selected = self.input_text.textCursor().selectedText()
        if not selected:
            return
        QApplication.clipboard().setText(selected)
        cursor = self.input_text.textCursor()
        cursor.removeSelectedText()

    def _clipboard_paste(self) -> None:
        """Вставити текст з буфера обміну в позицію курсора."""
        text = QApplication.clipboard().text(QClipboard.Mode.Clipboard)
        if not text:
            return
        cursor = self.input_text.textCursor()
        cursor.insertText(text)

    def _clipboard_select_all(self, widget: QTextEdit = None) -> None:
        """Виділити весь текст у віджеті."""
        if widget is None:
            widget = self.chat_history
        cursor = widget.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        widget.setTextCursor(cursor)
