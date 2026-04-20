# core_gui/main_window.py
"""Головне вікно асистента AssistantGUI."""
import queue
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Optional

from .chat_panel import ChatPanelMixin
from .confirmation import ConfirmationMixin
from .constants import ASSISTANT_NAME, ASSISTANT_TITLE
from .plan_panel import PlanPanelMixin
from .settings_tab import SettingsTabMixin
from .styles import apply_styles


class AssistantGUI(
    ChatPanelMixin,
    ConfirmationMixin,
    PlanPanelMixin,
    SettingsTabMixin,
):
    """Головне вікно асистента.

    Композиція поведінки через Mixin-класи:
    - ChatPanelMixin: чат, введення, clipboard, стрімінг, контекстні меню
    - ConfirmationMixin: діалог підтвердження з таймаутом
    - PlanPanelMixin: панель плану виконання з прогресом
    - SettingsTabMixin: вкладка налаштувань (SETTINGS_SCHEMA)
    """

    def __init__(self, assistant_callback):
        self.root = tk.Tk()
        self.root.title(f"Асистент {ASSISTANT_NAME}")
        self.assistant_callback = assistant_callback
        self.message_queue = queue.Queue()
        self.confirmation_callback = None
        self.awaiting_confirmation = False
        self.input_active = False
        self.idle_timeout = 300  # 5 хвилин
        self.last_input_time = time.time()

        # Налаштування вікна (збережена геометрія або дефолт)
        try:
            from functions.core_settings import get_setting
            saved_geom = get_setting("WINDOW_GEOMETRY", None)
        except Exception:
            saved_geom = None
        self.root.geometry(saved_geom if saved_geom else "500x400")
        self.root.configure(bg='#f0f0f0')
        self.root.resizable(True, True)
        # Прозорість вимкнена — повна непрозорість
        self.root.attributes('-alpha', 1.0)
        self.root.minsize(450, 550)  # Мінімальний розмір
        # Зберегти геометрію при закритті
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Стилі
        self.style = ttk.Style()
        apply_styles(self.style)

        # Створення інтерфейсу
        self.create_widgets()
        self.setup_window()

        # Запуск обробки черги повідомлень
        self.process_queue()

        # Слідкування за активністю
        self.check_idle()

    # ============================================================
    # ВІДЖЕТИ
    # ============================================================

    def create_widgets(self):
        """Створення віджетів інтерфейсу."""
        # Заголовок
        title_frame = ttk.Frame(self.root, style='Title.TLabel')
        title_frame.pack(fill='x', side='top', pady=(0, 5))

        title_label = ttk.Label(
            title_frame,
            text=ASSISTANT_TITLE,
            style='Title.TLabel',
        )
        title_label.pack()

        # Головний контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=5, pady=5)

        # Notebook (вкладки): Чат / Налаштування
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill='both', expand=True, pady=(0, 10))

        # --- Вкладка Чат ---
        chat_frame = ttk.Frame(self.notebook)
        self.notebook.add(chat_frame, text='💬 Чат')

        # Історія чату з прокруткою
        self.chat_history = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg='#fafafa',
            fg='#333333',
            state='disabled',
            relief='flat',
            borderwidth=1,
            height=20,
        )
        self.chat_history.pack(fill='both', expand=True)

        # --- Вкладка Налаштування ---
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text='⚙️ Налаштування')
        # Ліниве заповнення при першому відкритті
        self._settings_built = False
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

        # --- Панель плану виконання (всередині вкладки Чат, під чатом) ---
        self.plan_frame = ttk.Frame(chat_frame, relief='solid', borderwidth=1)

        plan_header = ttk.Frame(self.plan_frame)
        plan_header.pack(fill='x', padx=5, pady=(5, 2))

        self.plan_title_var = tk.StringVar(value="📋 План виконання")
        plan_title = ttk.Label(
            plan_header,
            textvariable=self.plan_title_var,
            font=('Segoe UI', 9, 'bold'),
            foreground='#2c3e50',
        )
        plan_title.pack(side='left')

        self.plan_collapse_btn = ttk.Button(
            plan_header,
            text="▼",
            width=3,
            command=self._toggle_plan_panel,
        )
        self.plan_collapse_btn.pack(side='right')

        # Контейнер для списку кроків з обмеженою висотою і прокруткою
        plan_scroll_frame = ttk.Frame(self.plan_frame)
        plan_scroll_frame.pack(fill='x', padx=5, pady=(0, 5))

        plan_canvas = tk.Canvas(plan_scroll_frame, height=150, highlightthickness=0)
        plan_scrollbar = ttk.Scrollbar(plan_scroll_frame, orient='vertical', command=plan_canvas.yview)
        self.plan_steps_container = ttk.Frame(plan_canvas)

        plan_canvas.configure(yscrollcommand=plan_scrollbar.set)
        plan_canvas.pack(side='left', fill='x', expand=True)
        plan_scrollbar.pack(side='right', fill='y')

        plan_canvas.create_window((0, 0), window=self.plan_steps_container, anchor='nw')
        self.plan_steps_container.bind('<Configure>', lambda e: plan_canvas.configure(scrollregion=plan_canvas.bbox('all')))

        # Прогрес-бар у панелі плану
        self.plan_progress_var = tk.IntVar()
        self.plan_progress_bar = ttk.Progressbar(
            self.plan_frame,
            variable=self.plan_progress_var,
            maximum=100,
            mode='determinate',
        )
        self.plan_progress_bar.pack(fill='x', padx=5, pady=(0, 5))

        # Стан панелі плану
        self._plan_steps: list = []
        self._plan_step_labels: list = []
        self._plan_expanded = True

        # Фрейм для підтвердження (прихований за замовчуванням)
        self.confirmation_frame = ttk.Frame(main_container)

        self.confirmation_label = ttk.Label(
            self.confirmation_frame,
            text="",
            font=('Segoe UI', 10, 'bold'),
            foreground='#d32f2f',
            wraplength=400,
        )
        self.confirmation_label.pack(pady=(10, 5))

        button_frame = ttk.Frame(self.confirmation_frame)
        button_frame.pack(pady=5)

        self.yes_button = ttk.Button(
            button_frame,
            text="ТАК",
            style='Confirm.TButton',
            command=self.on_yes_clicked,
        )
        self.yes_button.pack(side='left', padx=8)

        self.no_button = ttk.Button(
            button_frame,
            text="НІ",
            style='Cancel.TButton',
            command=self.on_no_clicked,
        )
        self.no_button.pack(side='left', padx=8)

        # Третя кнопка - увімкнути автопідтвердження всіх дій
        self.auto_button = ttk.Button(
            button_frame,
            text="АВТОМАТИЧНО (всі дозволено)",
            style='Confirm.TButton',
            command=self.on_auto_clicked,
        )
        self.auto_button.pack(side='left', padx=8)

        # Контейнер для поля вводу
        self.input_container = ttk.Frame(main_container)
        self.input_container.pack(fill='x', side='bottom', pady=(5, 0))

        # Фрейм для вводу з grid менеджером
        input_frame = ttk.Frame(self.input_container)
        input_frame.pack(fill='x', expand=True)

        # Налаштування grid
        input_frame.columnconfigure(0, weight=1)  # Поле вводу розтягується
        input_frame.columnconfigure(1, weight=0)  # Кнопка мікрофона фіксована
        input_frame.columnconfigure(2, weight=0)  # Кнопка відправки фіксована

        # Поле вводу
        self.input_text = tk.Text(
            input_frame,
            height=3,
            font=('Segoe UI', 10),
            wrap=tk.WORD,
            bg='white',
            fg='#333333',
            relief='solid',
            borderwidth=1,
        )
        self.input_text.grid(row=0, column=0, sticky='nsew', padx=(0, 5))

        # --- Кнопка мікрофона (STT) ---
        self.mic_button = ttk.Button(
            input_frame,
            text="🎤",
            width=3,
            command=self.on_mic_clicked,
            style='Mic.TButton',
        )
        self.mic_button.grid(row=0, column=1, sticky='ns', padx=(0, 3))

        # Індикатор статусу STT (прихований за замовчуванням)
        self.mic_status_label = ttk.Label(
            input_frame,
            text="",
            font=('Segoe UI', 9),
            foreground='#e74c3c',
        )
        self.mic_status_label.grid(row=0, column=1, sticky='nsew', padx=(0, 3))
        self.mic_status_label.grid_remove()  # Приховуємо

        # Кнопка відправки
        self.send_button = ttk.Button(
            input_frame,
            text="➤",
            width=3,
            command=self.send_text_command,
            style='Send.TButton',
        )
        self.send_button.grid(row=0, column=2, sticky='ns')

        # Кнопка «Стоп» (спочатку прихована)
        self.stop_button = ttk.Button(
            input_frame,
            text="⬛ СТОП",
            command=self.stop_execution,
            style='Stop.TButton',
        )

        # Підказка
        self.input_text.insert(1.0, "Введіть команду...")
        self.input_text.configure(fg='#999999')

        # Обробка клавіш
        self.input_text.bind('<Return>', self.on_enter_pressed)
        self.input_text.bind('<Shift-Return>', self.on_shift_enter)
        self.input_text.bind('<FocusIn>', self.on_input_focus)
        self.input_text.bind('<FocusOut>', self.on_input_blur)
        self.input_text.bind('<Key>', self.on_input_key)
        # Зупинка виконання через Esc (Ctrl+C конфліктує з копіюванням)
        self.root.bind('<Escape>', lambda e: self.stop_execution())

        # Налаштування copy/paste/cut з підтримкою будь-якої розкладки
        self._setup_clipboard_bindings(self.input_text, editable=True)
        self._setup_clipboard_bindings(self.chat_history, editable=False)

        # Контекстні меню (правий клік)
        self._create_context_menu_input()
        self._create_context_menu_chat()

        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("✅ Готовий до роботи")

        status_bar = ttk.Label(
            main_container,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=('Segoe UI', 9),
            padding=5,
        )
        status_bar.pack(fill='x', side='bottom', pady=(5, 0))

        # Прогрес-бар (прихований за замовчуванням)
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(
            main_container,
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
        )
        self.progress_bar.pack(fill='x', side='bottom', pady=(2, 0))
        self.progress_bar.pack_forget()  # приховати спочатку

    # ============================================================
    # ВІКНО (події)
    # ============================================================

    def setup_window(self):
        """Налаштування поведінки вікна."""
        self.root.bind('<Configure>', self.on_resize)
        self.root.after(100, self.focus_input)

    def on_resize(self, event=None):
        """Обробка зміни розміру вікна."""
        self.root.update_idletasks()

    def check_idle(self):
        """Перевірка простою."""
        if self.input_active:
            idle_time = time.time() - self.last_input_time
            if idle_time > self.idle_timeout:
                self.on_input_blur()
                self.add_message("system", "⏳ Автоматичне відновлення аудіо")

        self.root.after(1000, self.check_idle)

    # ============================================================
    # ЧЕРГА ПОВІДОМЛЕНЬ
    # ============================================================

    def process_queue(self):
        """Обробка черги повідомлень від core."""
        try:
            while True:
                message = self.message_queue.get_nowait()
                msg_type, data = message

                if msg_type == 'add_message':
                    sender, text = data
                    self.root.after(0, self.add_message, sender, text)
                elif msg_type == 'show_confirmation':
                    question, callback = data
                    self.root.after(0, self.show_confirmation, question, callback)
                elif msg_type == 'stream_start':
                    self.root.after(0, self.start_stream_message)
                elif msg_type == 'stream_chunk':
                    self.root.after(0, self.append_stream_chunk, data)
                elif msg_type == 'stream_end':
                    self.root.after(0, self.end_stream_message)
                elif msg_type == 'update_status':
                    status = data
                    self.root.after(0, self.status_var.set, status)
                elif msg_type == 'update_progress':
                    progress, status_text = data
                    self.root.after(0, self.update_progress, progress, status_text)
                elif msg_type == 'execution_started':
                    self.root.after(0, self.show_stop_button)
                elif msg_type == 'execution_finished':
                    self.root.after(0, self.hide_stop_button)
                elif msg_type == 'plan_started':
                    self.root.after(0, self.show_plan_panel, data)
                elif msg_type == 'step_update':
                    self.root.after(0, self.update_plan_step, data)
                elif msg_type == 'plan_finished':
                    self.root.after(0, self.finish_plan_panel, data)

        except queue.Empty:
            pass

        self.root.after(100, self.process_queue)

    def queue_message(self, msg_type, data):
        """Додати повідомлення до черги."""
        self.message_queue.put((msg_type, data))

    # ============================================================
    # ПРОГРЕС / КНОПКИ
    # ============================================================

    def update_progress(self, progress: int, status_text: str):
        """Оновити статус-текст (progress-bar тепер у панелі плану)."""
        if status_text:
            self.status_var.set(status_text)
            # Запускаємо анімацію крапок якщо статус "Думаю"
            if "думаю" in status_text.lower() or "thinking" in status_text.lower():
                self._start_thinking_animation()
            else:
                self._stop_thinking_animation()
        self.root.update_idletasks()

    def _start_thinking_animation(self):
        """Запустити анімацію крапок для 'Думаю...'."""
        if hasattr(self, '_thinking_animation_active') and self._thinking_animation_active:
            return
        self._thinking_animation_active = True
        self._thinking_dots = 0
        self._animate_thinking_dots()

    def _stop_thinking_animation(self):
        """Зупинити анімацію крапок."""
        self._thinking_animation_active = False

    def _animate_thinking_dots(self):
        """Анімувати крапки 'Думаю...' -> 'Думаю..' -> 'Думаю.' -> 'Думаю...'"""
        if not self._thinking_animation_active:
            return
        
        dots = ["   ", ".  ", ".. ", "..."]
        self._thinking_dots = (self._thinking_dots + 1) % len(dots)
        dots_str = dots[self._thinking_dots]
        
        # Оновлюємо статус з анімованими крапками
        base_text = "🤔 Думаю"
        self.status_var.set(f"{base_text}{dots_str}")
        
        # Продовжуємо анімацію кожні 500мс
        self.root.after(500, self._animate_thinking_dots)

    def show_stop_button(self):
        """Показати кнопку «Стоп» і приховати кнопку відправки та мікрофон."""
        self.send_button.grid_remove()
        self.mic_button.grid_remove()
        self.stop_button.grid(row=0, column=2, sticky='ns')
        self.status_var.set("⏳ Виконання... (Esc або Стоп для переривання)")

    def hide_stop_button(self):
        """Приховати кнопку «Стоп» і показати кнопку відправки та мікрофон."""
        self.stop_button.grid_remove()
        self.mic_button.grid()
        self.send_button.grid(row=0, column=2, sticky='ns')
        self.progress_bar.pack_forget()
        self.status_var.set("✅ Готовий до роботи")

    def stop_execution(self):
        """Обробник натискання кнопки «Стоп»."""
        if self.assistant_callback:
            self.assistant_callback('stop_execution', None)
        self.hide_stop_button()

    # ============================================================
    # STT / ГОЛОСОВИЙ ВВІД
    # ============================================================

    def set_stt_controller(self, stt_controller):
        """Встановити STT контролер (викликається з main.py)."""
        self.stt_controller = stt_controller
        # Оновлюємо callback для статусу
        if hasattr(self.stt_controller, 'listener'):
            self.stt_controller.status_callback = self._on_stt_status_change

    def on_mic_clicked(self):
        """Обробник натискання кнопки мікрофона."""
        if not hasattr(self, 'stt_controller') or self.stt_controller is None:
            from tkinter import messagebox
            messagebox.showwarning(
                "Голосовий ввід",
                "STT не ініціалізовано.\n\nПеревірте налаштування:\nНалаштування → Розпізнавання мови → Увімкнути STT"
            )
            return

        # Якщо вже слухаємо — зупинити
        if getattr(self, '_is_listening_mic', False):
            self._stop_mic_listening()
            return

        # Почати слухання
        self._start_mic_listening()

    def _start_mic_listening(self):
        """Почати запис з мікрофона."""
        self._is_listening_mic = True

        # Оновити UI
        self.mic_button.configure(text="⏹️", style='MicRecording.TButton')
        self.mic_status_label.configure(text="● Слухаю...", foreground='#e74c3c')
        self.mic_status_label.grid()
        self.status_var.set("🎤 Слухаю... говоріть вашу команду")

        # Запустити в окремому потоці щоб не блокувати GUI
        self._mic_thread = threading.Thread(target=self._mic_listen_worker, daemon=True)
        self._mic_thread.start()

    def _stop_mic_listening(self):
        """Зупинити запис (викликається автоматично після розпізнавання)."""
        self._is_listening_mic = False

        # Оновити UI
        self.mic_button.configure(text="🎤", style='Mic.TButton')
        self.mic_status_label.grid_remove()

    def _mic_listen_worker(self):
        """Потік для запису та розпізнавання."""
        try:
            # Слухаємо
            text = self.stt_controller.toggle_listening()

            # Повернутися в головний потік для оновлення UI
            self.root.after(0, lambda: self._on_mic_finished(text))

        except Exception as e:
            print(f"❌ Помилка мікрофона: {e}")
            self.root.after(0, lambda: self._on_mic_finished(None))

    def _on_mic_finished(self, text: Optional[str]):
        """Викликається коли розпізнавання завершено."""
        self._stop_mic_listening()

        if text:
            # Вставляємо текст в поле вводу
            self.input_text.delete(1.0, tk.END)
            self.input_text.insert(1.0, text)
            self.input_text.configure(fg='#333333')

            # Показуємо розпізнаний текст
            self.status_var.set(f"🎤 Розпізнано: {text[:50]}...")

            # Автоматично відправляємо команду
            self.send_text_command()
        else:
            self.status_var.set("⚠️ Не розпізнано мову")

    def _on_stt_status_change(self, status: str, data=None):
        """Обробник зміни статусу STT."""
        # Цей метод викликається з STT Listener в іншому потоці
        # Тому використовуємо root.after для оновлення UI

        def update_ui():
            if status == "listening":
                self.mic_status_label.configure(text="● Слухаю...", foreground='#e74c3c')
            elif status == "processing":
                self.mic_status_label.configure(text="◌ Розпізнаю...", foreground='#f39c12')
            elif status == "recognized":
                text = data.get("text", "") if data else ""
                self.mic_status_label.configure(text=f"✓ {text[:20]}...", foreground='#27ae60')
            elif status == "error":
                self.mic_status_label.configure(text="✗ Помилка", foreground='#e74c3c')

        self.root.after(0, update_ui)

    # ============================================================
    # ЗАПУСК
    # ============================================================

    def _on_close(self):
        """Зберегти геометрію вікна перед закриттям."""
        try:
            from functions.core_settings import get_settings
            geom = self.root.geometry()
            get_settings().set("WINDOW_GEOMETRY", geom, persist=True)
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        """Запустити GUI (mainloop)."""
        self.root.mainloop()


def run_gui(assistant_callback):
    """Запуск GUI (utility-функція для зворотної сумісності)."""
    gui = AssistantGUI(assistant_callback)
    gui.run()
