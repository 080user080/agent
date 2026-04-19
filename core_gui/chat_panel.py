# core_gui/chat_panel.py
"""Міксин для чату: історія, ввід, clipboard, стрімінг, контекстні меню."""
import re
import time
import tkinter as tk

from .constants import ASSISTANT_TITLE, ASSISTANT_EMOJI, ASSISTANT_NAME


class ChatPanelMixin:
    """Логіка чат-панелі (історія повідомлень, поле вводу, буфер обміну).

    Очікує атрибути (створені в AssistantGUI.create_widgets):
    - self.root: tk.Tk
    - self.chat_history: scrolledtext.ScrolledText
    - self.input_text: tk.Text
    - self.input_active: bool
    - self.last_input_time: float
    - self.assistant_callback: callable
    - self.status_var: tk.StringVar
    - self.awaiting_confirmation: bool
    """

    # Windows virtual key codes для C, V, X, A, Insert
    _KEYCODE_C = 67
    _KEYCODE_V = 86
    _KEYCODE_X = 88
    _KEYCODE_A = 65
    _KEYCODE_INSERT = 45

    # ---------- базові методи ----------

    def focus_input(self):
        """Встановити фокус на поле вводу."""
        self.input_text.focus_set()

    def add_message(self, sender, message):
        """Додати повідомлення до чату (чистить ANSI/LLM токени)."""
        # Захист від None
        if message is None:
            message = ""
        # Захист від випадкової передачі кортежу
        if isinstance(message, (tuple, list)):
            message = " ".join(str(item) for item in message)

        # Очистити ANSI escape-коди (типу \x1b[31m, [31m)
        message = re.sub(r'\x1b\[[0-9;]*m', '', str(message))
        message = re.sub(r'\[\d{1,3}(?:;\d{1,3})*m', '', message)

        # Прибрати сирі LLM-токени (gpt-oss формат), якщо раптом потрапили в чат
        if sender == "assistant" and ('<|' in message or 'channel' in message.lower()):
            try:
                from functions.logic_llm import clean_llm_tokens
                cleaned = clean_llm_tokens(message)
                if cleaned:
                    message = cleaned
            except Exception:
                message = re.sub(r'<\|[^|]*\|>', '', message)

        self.chat_history.configure(state='normal')

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

        # Додаємо роздільник
        current_text = self.chat_history.get(1.0, tk.END).strip()
        if current_text:
            self.chat_history.insert(tk.END, "\n" + "-" * 50 + "\n")

        # Відправник
        if sender == "user":
            prefix = "👑 ВИ: "
        else:
            prefix = f"{ASSISTANT_TITLE}: "

        self.chat_history.insert(tk.END, prefix, ('bold',))
        self.chat_history.insert(tk.END, message + "\n")

        # Форматування
        self.chat_history.tag_configure('bold', font=('Segoe UI', 10, 'bold'))

        # Прокручуємо до кінця
        self.chat_history.see(tk.END)
        if sender == "assistant":
            import time as _time
            self.chat_history.configure(state='normal')
            self.chat_history.tag_configure('done_mark', foreground='#4CAF50', font=('Segoe UI', 9))
            self.chat_history.insert(tk.END, "  ✅\n", ('done_mark',))
            self.chat_history.see(tk.END)
            ts = _time.strftime('%H:%M:%S')
            if hasattr(self, 'status_var'):
                self.status_var.set(f"✅ Відповідь готова | {ts}")
        self.chat_history.configure(state='disabled')

    # ---------- Поле вводу ----------

    def on_input_focus(self, event=None):
        """Коли поле вводу отримує фокус."""
        current_text = self.input_text.get(1.0, tk.END).strip()
        if current_text == "Введіть команду...":
            self.input_text.delete(1.0, tk.END)
            self.input_text.configure(fg='#333333')

        self.input_active = True
        self.status_var.set("⌨️  Ввід тексту | 🎤 вимк.")

        if self.assistant_callback:
            self.assistant_callback('pause_listening')

    def on_input_blur(self, event=None):
        """Коли поле вводу втрачає фокус."""
        current_text = self.input_text.get(1.0, tk.END).strip()
        if not current_text:
            self.input_text.insert(1.0, "Введіть команду...")
            self.input_text.configure(fg='#999999')

        self.input_active = False
        self.last_input_time = time.time()

        if self.assistant_callback:
            self.assistant_callback('resume_listening')

    def on_input_key(self, event=None):
        """Коли натискається клавіша."""
        self.last_input_time = time.time()

    def on_enter_pressed(self, event=None):
        """Обробка Enter."""
        if not self.awaiting_confirmation:
            self.send_text_command()
            return 'break'
        return None

    def on_shift_enter(self, event=None):
        """Обробка Shift+Enter."""
        self.input_text.insert(tk.INSERT, '\n')
        return 'break'

    def send_text_command(self):
        """Відправити текстову команду."""
        command = self.input_text.get(1.0, tk.END).strip()

        if not command or command == "Введіть команду...":
            return

        self.input_text.delete(1.0, tk.END)

        if self.assistant_callback:
            self.assistant_callback('process_text', command)

    # ---------- Стрім-повідомлення ----------

    def start_stream_message(self):
        """Почати нове повідомлення асистента для стрімінгу."""
        self.chat_history.configure(state='normal')
        current_text = self.chat_history.get(1.0, tk.END).strip()
        if current_text:
            self.chat_history.insert(tk.END, "\n" + "-" * 50 + "\n")
        prefix = f"{ASSISTANT_TITLE}: "
        self.chat_history.insert(tk.END, prefix, ('bold',))
        self.stream_insert_pos = self.chat_history.index(tk.INSERT)
        self.chat_history.configure(state='disabled')

    def append_stream_chunk(self, text):
        """Додати фрагмент тексту до стрімінгового повідомлення."""
        self.chat_history.configure(state='normal')
        self.chat_history.mark_set(tk.INSERT, self.stream_insert_pos)
        self.chat_history.insert(tk.INSERT, text)
        self.stream_insert_pos = self.chat_history.index(tk.INSERT)
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')

    def end_stream_message(self):
        """Завершити стрімінг (додати новий рядок і мітку готовності)."""
        import time as _time
        self.chat_history.configure(state='normal')
        self.chat_history.tag_configure('done_mark', foreground='#4CAF50', font=('Segoe UI', 9))
        self.chat_history.insert(self.stream_insert_pos, "  ✅\n", ('done_mark',))
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')
        ts = _time.strftime('%H:%M:%S')
        if hasattr(self, 'status_var'):
            self.status_var.set(f"✅ Відповідь готова | {ts}")

    # ============================================================
    # CLIPBOARD: універсальне копіювання/вставка/вирізання
    # Підтримка будь-якої розкладки (UA/EN/RU) через keycode
    # ============================================================

    def _setup_clipboard_bindings(self, widget, editable: bool):
        """Прив'язати копіювання/вставку/вирізання до віджета.

        Робимо прив'язку до `<Control-Key>` і перевіряємо `event.keycode`,
        щоб працювало з будь-якою розкладкою клавіатури.
        """
        def on_ctrl_key(event):
            # event.state: 0x4 = Control
            if not (event.state & 0x4):
                return None
            kc = event.keycode
            if kc == self._KEYCODE_C:
                return self._clipboard_copy(widget)
            if kc == self._KEYCODE_A:
                return self._clipboard_select_all(widget)
            if not editable:
                return None
            if kc == self._KEYCODE_V:
                return self._clipboard_paste(widget)
            if kc == self._KEYCODE_X:
                return self._clipboard_cut(widget)
            if kc == self._KEYCODE_INSERT:  # Ctrl+Insert = copy
                return self._clipboard_copy(widget)
            return None

        widget.bind('<Control-KeyPress>', on_ctrl_key)

        # Shift+Insert = paste (класична Windows-комбінація)
        if editable:
            def on_shift_insert(event):
                if event.state & 0x1:  # Shift
                    return self._clipboard_paste(widget)
                return None
            widget.bind('<Shift-KeyPress-Insert>', on_shift_insert)

        # Віртуальні події (працюють з меню та деяких систем)
        widget.bind('<<Copy>>', lambda e: self._clipboard_copy(widget))
        widget.bind('<<SelectAll>>', lambda e: self._clipboard_select_all(widget))
        if editable:
            widget.bind('<<Paste>>', lambda e: self._clipboard_paste(widget))
            widget.bind('<<Cut>>', lambda e: self._clipboard_cut(widget))

    def _get_selected_text(self, widget):
        """Безпечно отримати виділений текст з Text-віджета."""
        try:
            if widget.tag_ranges(tk.SEL):
                return widget.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        return ""

    def _set_clipboard(self, text: str):
        """Записати текст у системний буфер обміну Windows надійно."""
        if not text:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            # Ключове для Windows: потрібен update, інакше буфер
            # очистится при закритті/зміні фокусу tkinter
            self.root.update_idletasks()
        except tk.TclError as e:
            print(f"⚠️ Помилка запису у буфер: {e}")

    def _get_clipboard(self) -> str:
        """Прочитати текст з системного буфера обміну."""
        # Спочатку - tkinter
        for attempt in (
            lambda: self.root.clipboard_get(),
            lambda: self.root.clipboard_get(type='STRING'),
            lambda: self.root.clipboard_get(type='UTF8_STRING'),
        ):
            try:
                value = attempt()
                if value:
                    return value
            except tk.TclError:
                continue

        # Fallback: Windows API через ctypes
        try:
            import ctypes
            CF_UNICODETEXT = 13
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if user32.OpenClipboard(0):
                try:
                    handle = user32.GetClipboardData(CF_UNICODETEXT)
                    if handle:
                        ptr = kernel32.GlobalLock(handle)
                        try:
                            text = ctypes.c_wchar_p(ptr).value or ""
                            return text
                        finally:
                            kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
        except Exception as e:
            print(f"⚠️ Windows clipboard fallback помилка: {e}")

        return ""

    def _clipboard_copy(self, widget):
        """Копіювати виділений текст у буфер обміну."""
        selected = self._get_selected_text(widget)
        if not selected:
            return 'break'
        self._set_clipboard(selected)
        return 'break'

    def _clipboard_cut(self, widget):
        """Вирізати виділений текст у буфер обміну."""
        selected = self._get_selected_text(widget)
        if not selected:
            return 'break'
        self._set_clipboard(selected)
        try:
            widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        return 'break'

    def _clipboard_paste(self, widget):
        """Вставити текст з буфера обміну в позицію курсора."""
        text = self._get_clipboard()
        if not text:
            return 'break'

        # Якщо це поле вводу з placeholder - спочатку очистити
        if widget is self.input_text:
            current = widget.get(1.0, tk.END).strip()
            if current == "Введіть команду...":
                widget.delete(1.0, tk.END)
                widget.configure(fg='#333333')

        # Видалити виділене, якщо є
        try:
            if widget.tag_ranges(tk.SEL):
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass

        # Вставити на позицію курсора
        try:
            widget.insert(tk.INSERT, text)
        except tk.TclError as e:
            print(f"⚠️ Помилка вставки: {e}")
        return 'break'

    def _clipboard_select_all(self, widget):
        """Виділити весь текст у віджеті."""
        try:
            widget.tag_add(tk.SEL, "1.0", "end-1c")
            widget.mark_set(tk.INSERT, "1.0")
            widget.see(tk.INSERT)
        except tk.TclError:
            pass
        return 'break'

    # ---------- Контекстні меню (правий клік) ----------

    def _create_context_menu_input(self):
        """Створити контекстне меню для поля вводу (editable)."""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Вирізати (Ctrl+X)",
                         command=lambda: self._clipboard_cut(self.input_text))
        menu.add_command(label="Копіювати (Ctrl+C)",
                         command=lambda: self._clipboard_copy(self.input_text))
        menu.add_command(label="Вставити (Ctrl+V)",
                         command=lambda: self._clipboard_paste(self.input_text))
        menu.add_separator()
        menu.add_command(label="Виділити все (Ctrl+A)",
                         command=lambda: self._clipboard_select_all(self.input_text))
        self._input_menu = menu

        def show_menu(event):
            self.input_text.focus_set()
            has_sel = bool(self._get_selected_text(self.input_text))
            has_clip = bool(self._get_clipboard())
            menu.entryconfig("Вирізати (Ctrl+X)",
                             state=tk.NORMAL if has_sel else tk.DISABLED)
            menu.entryconfig("Копіювати (Ctrl+C)",
                             state=tk.NORMAL if has_sel else tk.DISABLED)
            menu.entryconfig("Вставити (Ctrl+V)",
                             state=tk.NORMAL if has_clip else tk.DISABLED)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return 'break'

        self.input_text.bind('<Button-3>', show_menu)

    def _create_context_menu_chat(self):
        """Створити контекстне меню для історії чату (read-only)."""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Копіювати (Ctrl+C)",
                         command=lambda: self._clipboard_copy(self.chat_history))
        menu.add_separator()
        menu.add_command(label="Виділити все (Ctrl+A)",
                         command=lambda: self._clipboard_select_all(self.chat_history))
        self._chat_menu = menu

        def show_menu(event):
            has_sel = bool(self._get_selected_text(self.chat_history))
            menu.entryconfig("Копіювати (Ctrl+C)",
                             state=tk.NORMAL if has_sel else tk.DISABLED)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return 'break'

        self.chat_history.bind('<Button-3>', show_menu)
