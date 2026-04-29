# core_gui/confirmation.py
"""Міксин діалогу підтвердження (ТАК / НІ / АВТОМАТИЧНО)."""
import threading
import tkinter as tk

from .constants import ASSISTANT_TITLE


class ConfirmationMixin:
    """Логіка підтвердження дій з таймаутом 30 сек.

    Очікує атрибути (створені в AssistantGUI.create_widgets):
    - self.confirmation_frame, self.confirmation_label
    - self.yes_button, self.no_button, self.auto_button
    - self.input_container
    - self.status_var
    - self.awaiting_confirmation, self.confirmation_callback
    """

    def show_confirmation(self, question, callback):
        """Показати діалог підтвердження із зворотним відліком."""
        self.awaiting_confirmation = True
        self.confirmation_callback = callback

        self.confirmation_label.config(text=f"{ASSISTANT_TITLE}: {question}")

        self.input_container.pack_forget()
        self.confirmation_frame.pack(fill='x', side='bottom', pady=(5, 0))

        # Зворотний відлік 30 сек, оновлюється щосекунди
        self._confirmation_seconds_left = 30
        self._update_confirmation_countdown()

        self.confirmation_timer = threading.Timer(30.0, self.on_confirmation_timeout)
        self.confirmation_timer.start()

        # Фокус на кнопку ТАК + біндинг клавіш Y/N/A/Enter/Esc
        self.root.after(50, self.yes_button.focus_set)
        self.root.bind('<KeyPress-y>', lambda e: self.on_yes_clicked())
        self.root.bind('<KeyPress-Y>', lambda e: self.on_yes_clicked())
        self.root.bind('<KeyPress-n>', lambda e: self.on_no_clicked())
        self.root.bind('<KeyPress-N>', lambda e: self.on_no_clicked())
        self.root.bind('<KeyPress-a>', lambda e: self.on_auto_clicked())
        self.root.bind('<KeyPress-A>', lambda e: self.on_auto_clicked())
        self.root.bind('<Return>', lambda e: self.on_yes_clicked())
        self._esc_confirmation_binding = self.root.bind(
            '<Escape>', lambda e: self.on_no_clicked(), add='+'
        )

        self.status_var.set("❓ Підтвердження: Y=так, N=ні, A=автоматично, Enter=так, Esc=ні")

    def _update_confirmation_countdown(self):
        """Оновлювати зворотний відлік у заголовку кнопок."""
        if not self.awaiting_confirmation:
            return
        secs = self._confirmation_seconds_left
        try:
            self.yes_button.config(text=f"ТАК ({secs}с)")
        except tk.TclError:
            return
        if secs > 0:
            self._confirmation_seconds_left -= 1
            self.root.after(1000, self._update_confirmation_countdown)

    def hide_confirmation(self):
        """Приховати діалог підтвердження та очистити клавіатурні біндинги."""
        if hasattr(self, 'confirmation_timer'):
            self.confirmation_timer.cancel()

        self.awaiting_confirmation = False
        self.confirmation_callback = None

        # Відновити оригінальний текст кнопки
        try:
            self.yes_button.config(text="ТАК")
        except tk.TclError:
            pass

        # Зняти клавіатурні біндинги
        for key in ('<KeyPress-y>', '<KeyPress-Y>', '<KeyPress-n>',
                    '<KeyPress-N>', '<KeyPress-a>', '<KeyPress-A>', '<Return>'):
            try:
                self.root.unbind(key)
            except tk.TclError:
                pass
        # Повернути <Escape> на stop_execution
        self.root.bind('<Escape>', lambda e: self.stop_execution())

        self.confirmation_frame.pack_forget()
        self.input_container.pack(fill='x', side='bottom', pady=(5, 0))

        self.status_var.set("✅ Готовий до роботи")

    def on_yes_clicked(self):
        """Коли натиснуто ТАК (один раз)."""
        if self.confirmation_callback:
            self.confirmation_callback(True)
        self.hide_confirmation()

    def on_no_clicked(self):
        """Коли натиснуто НІ."""
        if self.confirmation_callback:
            self.confirmation_callback(False)
        self.hide_confirmation()

    def on_auto_clicked(self):
        """Коли натиснуто АВТОМАТИЧНО — увімкнути auto_approve_all і підтвердити."""
        if self.confirmation_callback:
            self.confirmation_callback("auto")
        self.hide_confirmation()

    def on_confirmation_timeout(self):
        """Таймаут підтвердження."""
        if self.awaiting_confirmation:
            self.root.after(0, self.timeout_confirmation)

    def timeout_confirmation(self):
        """Обробка таймауту в головному потоці."""
        if self.awaiting_confirmation:
            self.add_message("assistant", "⏰ Час очікування вийшов. Дію скасовано.")
            if self.confirmation_callback:
                self.confirmation_callback(False)
            self.hide_confirmation()
