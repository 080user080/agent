"""ConfirmationQtMixin — логіка діалогу підтвердження для PyQt6.

Порт core_gui/confirmation.py (Tkinter) на PyQt6.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class ConfirmationDialog(QDialog):
    """Кастомний діалог підтвердження з зворотним відліком."""

    def __init__(self, question: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.question = question
        self.result = None
        self._seconds_left = 30
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_countdown)

        self._init_ui()
        self._start_countdown()

    def _init_ui(self) -> None:
        self.setWindowTitle("Підтвердження")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Питання
        self.question_label = QLabel(f"⚡ МАРК: {self.question}")
        self.question_label.setWordWrap(True)
        layout.addWidget(self.question_label)

        # Статус
        self.status_label = QLabel("Натисніть кнопку або чекайте таймаут...")
        layout.addWidget(self.status_label)

        # Кнопки
        btn_layout = QHBoxLayout()

        self.yes_btn = QPushButton("ТАК (30с)")
        self.yes_btn.clicked.connect(self._on_yes)
        self.yes_btn.setStyleSheet("background: #2e7d32; color: white; font-weight: bold;")
        btn_layout.addWidget(self.yes_btn)

        self.no_btn = QPushButton("НІ")
        self.no_btn.clicked.connect(self._on_no)
        self.no_btn.setStyleSheet("background: #c62828; color: white; font-weight: bold;")
        btn_layout.addWidget(self.no_btn)

        self.auto_btn = QPushButton("АВТОМАТИЧНО")
        self.auto_btn.clicked.connect(self._on_auto)
        self.auto_btn.setStyleSheet("background: #1976d2; color: white; font-weight: bold;")
        btn_layout.addWidget(self.auto_btn)

        layout.addLayout(btn_layout)

    def _start_countdown(self) -> None:
        """Почати зворотний відлік."""
        self._timer.start(1000)

    def _update_countdown(self) -> None:
        """Оновити зворотний відлік."""
        self._seconds_left -= 1
        if self._seconds_left > 0:
            self.yes_btn.setText(f"ТАК ({self._seconds_left}с)")
        else:
            self._timer.stop()
            self._on_timeout()

    def _on_yes(self) -> None:
        """Кнопка ТАК."""
        self.result = True
        self.accept()

    def _on_no(self) -> None:
        """Кнопка НІ."""
        self.result = False
        self.reject()

    def _on_auto(self) -> None:
        """Кнопка АВТОМАТИЧНО."""
        self.result = "auto"
        self.accept()

    def _on_timeout(self) -> None:
        """Таймаут — автоматичне скасування."""
        self.result = False
        self.reject()

    def get_result(self) -> Any:
        """Отримати результат діалогу."""
        return self.result


class ConfirmationQtMixin:
    """Міксин для підтвердження дій з таймаутом 30 сек.

    Очікує атрибути:
        - self.assistant_callback: callable (optional)
        - self.awaiting_confirmation: bool
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.awaiting_confirmation = False
        self.confirmation_callback: Optional[Callable] = None
        self._confirmation_dialog: Optional[ConfirmationDialog] = None

    def show_confirmation(self, question: str, callback: Callable) -> None:
        """Показати діалог підтвердження із зворотним відліком."""
        self.awaiting_confirmation = True
        self.confirmation_callback = callback

        self._confirmation_dialog = ConfirmationDialog(question, parent=self)
        self._confirmation_dialog.finished.connect(self._on_dialog_finished)

        if hasattr(self, 'status_label'):
            self.status_label.setText("❓ Підтвердження: Y=так, N=ні, A=автоматично")

        # Показати діалог (модальний)
        self._confirmation_dialog.exec()

    def _on_dialog_finished(self) -> None:
        """Обробка завершення діалогу."""
        if self._confirmation_dialog is None:
            return

        result = self._confirmation_dialog.get_result()
        self._confirmation_dialog = None

        if self.confirmation_callback:
            self.confirmation_callback(result)

        self.hide_confirmation()

    def hide_confirmation(self) -> None:
        """Приховати діалог підтвердження."""
        if self._confirmation_dialog:
            self._confirmation_dialog.reject()
            self._confirmation_dialog = None

        self.awaiting_confirmation = False
        self.confirmation_callback = None

        if hasattr(self, 'status_label'):
            self.status_label.setText("✅ Готовий до роботи")
