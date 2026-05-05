"""Вкладка чату для спілкування з LLM."""
from datetime import datetime
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QTextCursor, QFont
from PyQt6.QtWidgets import (
    QTextEdit,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
)

from .base_tab import BaseTab
from .constants import ROLE_COLORS, QUICK_COMMANDS


class ChatTab(BaseTab):
    """Вкладка чату для спілкування з LLM."""

    def _build_content(self, layout):
        """Побудувати контент вкладки чату."""
        # Історія повідомлень
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.chat_history)

        # Введення повідомлення
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введіть повідомлення...")
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input)

        self.send_button = QPushButton("Надіслати")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        layout.addLayout(input_layout)

        # Кнопки швидких команд
        quick_commands = QHBoxLayout()
        for cmd in QUICK_COMMANDS:
            btn = QPushButton(cmd)
            btn.clicked.connect(lambda checked, c=cmd: self.quick_command(c))
            quick_commands.addWidget(btn)
        layout.addLayout(quick_commands)

        self.add_message("system", "Чат готовий до роботи. Введіть повідомлення або скористайтесь швидкими командами.")

    def send_message(self):
        """Надіслати повідомлення."""
        text = self.message_input.text().strip()
        if not text:
            return

        self.add_message("user", text)
        self.message_input.clear()

        # Симуляція відповіді LLM
        QTimer.singleShot(500, lambda: self.add_message("assistant", f"Відповідь на: {text}"))

    def quick_command(self, command: str):
        """Виконати швидку команду."""
        self.message_input.setText(command)
        self.send_message()

    def add_message(self, role: str, text: str):
        """Додати повідомлення в історію."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = ROLE_COLORS.get(role, "#000000")

        self.chat_history.moveCursor(QTextCursor.MoveOperation.End)
        self.chat_history.insertHtml(f'<span style="color: gray;">[{timestamp}]</span> ')
        self.chat_history.insertHtml(f'<span style="color: {color}; font-weight: bold;">{role}:</span> ')
        self.chat_history.insertHtml(f'{text}<br>')
        self.chat_history.moveCursor(QTextCursor.MoveOperation.End)
