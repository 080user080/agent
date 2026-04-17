# core_gui.py
"""Графічний інтерфейс голосового асистента"""
import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import queue
import time
from datetime import datetime
import sys
import os

# Додаємо шлях до functions для імпорту конфігурації
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Імпортуємо конфігурацію
try:
    from functions.config import ASSISTANT_NAME, ASSISTANT_EMOJI
    ASSISTANT_TITLE = f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}"
except ImportError:
    ASSISTANT_NAME = "МАРК"
    ASSISTANT_EMOJI = "⚡"
    ASSISTANT_TITLE = f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}"

class LLMEndpointsEditor:
    """Редактор списку LLM-ендпоїнтів для вкладки налаштувань.

    Рендерить по одному LabelFrame на кожен ендпоїнт (ім'я, URL, модель, API key,
    role, type, rate limit, script). Повертає список словників через `.get()`.
    """

    # Опис полів: (key, label, width, widget_type, choices)
    FIELDS = [
        ("name",              "Назва",              24, "entry",   None),
        ("enabled",           "Активний",            0, "check",   None),
        ("role",              "Роль",               12, "combo",   ["primary", "secondary", "fallback", "alternative"]),
        ("type",              "Тип",                18, "combo",   ["openai_compatible", "script"]),
        ("url",               "URL",                38, "entry",   None),
        ("model",             "Модель",             20, "entry",   None),
        ("api_key",           "API Key",            24, "entry",   None),
        ("temperature",       "Temperature",         6, "entry",   None),
        ("max_tokens",        "Max tokens",          6, "entry",   None),
        ("timeout",           "Timeout (c)",         5, "entry",   None),
        ("script_command",    "Script command",     28, "entry",   None),
        ("script_output_file","Output file",        20, "entry",   None),
        ("rate_limit_mode",   "Rate mode",          12, "combo",   ["unlimited", "rpm", "total"]),
        ("rate_limit_rpm",    "Max RPM",             5, "entry",   None),
        ("rate_limit_total",  "Max total",           6, "entry",   None),
    ]

    INT_KEYS = {"max_tokens", "timeout", "rate_limit_rpm", "rate_limit_total"}
    FLOAT_KEYS = {"temperature"}

    def __init__(self, parent, endpoints: list, row: int):
        self.parent = parent
        self._vars: list[dict] = []  # [{field_key: tk.Variable, ...}, ...]

        # Контейнер для всіх моделей
        container = ttk.Frame(parent)
        container.grid(row=row, column=0, columnspan=3, sticky='ew', padx=20, pady=8)
        container.columnconfigure(0, weight=1)

        for idx, ep in enumerate(endpoints):
            self._render_endpoint(container, idx, ep)

    def _render_endpoint(self, parent, idx: int, ep: dict):
        """Намалювати один ендпоїнт у LabelFrame з grid-розкладкою полів."""
        title = f"{idx + 1}. {ep.get('name', 'Без назви')}  [id={ep.get('id', '?')}]"
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=idx, column=0, sticky='ew', pady=4)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        ep_vars = {"id": ep.get("id", f"llm{idx + 1}")}
        # Два стовпці полів (пари label+entry), щоб не було надто високого фрейму
        row = 0
        col = 0
        for field_key, label, width, wtype, choices in self.FIELDS:
            val = ep.get(field_key, "")

            tk.Label(frame, text=label, font=('Segoe UI', 9)).grid(
                row=row, column=col * 2, sticky='w', padx=(0, 4), pady=2
            )

            if wtype == "check":
                var = tk.BooleanVar(value=bool(val))
                w = ttk.Checkbutton(frame, variable=var)
            elif wtype == "combo":
                var = tk.StringVar(value=str(val))
                w = ttk.Combobox(frame, textvariable=var, values=choices or [],
                                 state='readonly', width=width or 12)
            else:  # entry
                var = tk.StringVar(value=str(val) if val is not None else "")
                show = "*" if field_key == "api_key" and val else None
                w = ttk.Entry(frame, textvariable=var, width=width or 20, show=show)

            w.grid(row=row, column=col * 2 + 1, sticky='ew', padx=(0, 12), pady=2)
            ep_vars[field_key] = var

            # Перехід на другий стовпчик
            col += 1
            if col >= 2:
                col = 0
                row += 1

        self._vars.append(ep_vars)

    def get(self) -> list:
        """Зібрати значення з усіх віджетів у список словників."""
        result = []
        for ep_vars in self._vars:
            ep = {"id": ep_vars["id"]}
            for field_key, _, _, wtype, _ in self.FIELDS:
                raw = ep_vars[field_key].get()
                if wtype == "check":
                    ep[field_key] = bool(raw)
                elif field_key in self.INT_KEYS:
                    try:
                        ep[field_key] = int(raw) if str(raw).strip() else 0
                    except (ValueError, TypeError):
                        ep[field_key] = 0
                elif field_key in self.FLOAT_KEYS:
                    try:
                        ep[field_key] = float(raw) if str(raw).strip() else 0.0
                    except (ValueError, TypeError):
                        ep[field_key] = 0.0
                else:
                    ep[field_key] = str(raw)
            result.append(ep)
        return result


class AssistantGUI:
    """Головне вікно асистента"""
    
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
        
        # Налаштування вікна
        self.root.geometry("500x400")
        self.root.configure(bg='#f0f0f0')
        self.root.resizable(True, True)
        # Прозорість вимкнена — повна непрозорість
        self.root.attributes('-alpha', 1.0)
        self.root.minsize(450, 550)  # Мінімальний розмір
        
        # Стилі
        self.setup_styles()
        
        # Створення інтерфейсу
        self.create_widgets()
        self.setup_window()
        
        # Запуск обробки черги повідомлень
        self.process_queue()
        
        # Слідкування за активністю
        self.check_idle()
    
    def setup_styles(self):
        """Налаштування стилів"""
        self.style = ttk.Style()

        # Примусово використати тему, яка підтримує власні кольори кнопок.
        # Дефолтні Windows-теми ігнорують background у ttk.Button.
        try:
            self.style.theme_use('clam')
        except tk.TclError:
            pass  # якщо clam недоступна — лишаємо дефолт

        # Темна тема для заголовка
        self.style.configure(
            'Title.TLabel',
            background='#3c3c3c',
            foreground='white',
            font=('Segoe UI', 12, 'bold'),
            padding=10
        )

        # --- Кнопка ПІДТВЕРДИТИ (зелена) ---
        self.style.configure(
            'Confirm.TButton',
            background='#4CAF50',
            foreground='white',
            font=('Segoe UI', 10, 'bold'),
            padding=10,
            borderwidth=0,
        )
        self.style.map(
            'Confirm.TButton',
            background=[('active', '#45a049'), ('pressed', '#3d8b40'), ('!active', '#4CAF50')],
            foreground=[('active', 'white'), ('!active', 'white')],
        )

        # --- Кнопка СКАСУВАТИ (червона) ---
        self.style.configure(
            'Cancel.TButton',
            background='#f44336',
            foreground='white',
            font=('Segoe UI', 10, 'bold'),
            padding=10,
            borderwidth=0,
        )
        self.style.map(
            'Cancel.TButton',
            background=[('active', '#d73026'), ('pressed', '#b71c1c'), ('!active', '#f44336')],
            foreground=[('active', 'white'), ('!active', 'white')],
        )

        # --- Кнопка ВІДПРАВИТИ (чорна) ---
        self.style.configure(
            'Send.TButton',
            background='#1976d2',
            foreground='white',
            font=('Segoe UI', 12, 'bold'),
            padding=(15, 10),
            borderwidth=0,
        )
        self.style.map(
            'Send.TButton',
            background=[('active', '#1565c0'), ('pressed', '#0d47a1'), ('!active', '#1976d2')],
            foreground=[('active', 'white'), ('!active', 'white')],
        )

        # --- Кнопка СТОП (оранжева) ---
        self.style.configure(
            'Stop.TButton',
            background='#e65100',
            foreground='white',
            font=('Segoe UI', 12, 'bold'),
            padding=(15, 10),
            borderwidth=0,
        )
        self.style.map(
            'Stop.TButton',
            background=[('active', '#bf360c'), ('pressed', '#8c2400'), ('!active', '#e65100')],
            foreground=[('active', 'white'), ('!active', 'white')],
        )
    
    def create_widgets(self):
        """Створення віджетів інтерфейсу"""
        # Заголовок
        title_frame = ttk.Frame(self.root, style='Title.TLabel')
        title_frame.pack(fill='x', side='top', pady=(0, 5))
        
        title_label = ttk.Label(
            title_frame,
            text=ASSISTANT_TITLE,
            style='Title.TLabel'
        )
        title_label.pack()
        
        # Головний контейнер з прокруткою
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
            height=20
        )
        self.chat_history.pack(fill='both', expand=True)

        # --- Вкладка Налаштування ---
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text='⚙️ Налаштування')
        # Ліниве заповнення при першому відкритті
        self._settings_built = False
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

        # --- Панель плану виконання (прихована за замовчуванням) ---
        self.plan_frame = ttk.Frame(main_container, relief='solid', borderwidth=1)

        plan_header = ttk.Frame(self.plan_frame)
        plan_header.pack(fill='x', padx=5, pady=(5, 2))

        self.plan_title_var = tk.StringVar(value="📋 План виконання")
        plan_title = ttk.Label(
            plan_header,
            textvariable=self.plan_title_var,
            font=('Segoe UI', 9, 'bold'),
            foreground='#2c3e50'
        )
        plan_title.pack(side='left')

        self.plan_collapse_btn = ttk.Button(
            plan_header,
            text="▼",
            width=3,
            command=self._toggle_plan_panel
        )
        self.plan_collapse_btn.pack(side='right')

        # Контейнер для списку кроків
        self.plan_steps_container = ttk.Frame(self.plan_frame)
        self.plan_steps_container.pack(fill='x', padx=5, pady=(0, 5))

        # Прогрес-бар у панелі плану
        self.plan_progress_var = tk.IntVar()
        self.plan_progress_bar = ttk.Progressbar(
            self.plan_frame,
            variable=self.plan_progress_var,
            maximum=100,
            mode='determinate'
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
            wraplength=400
        )
        self.confirmation_label.pack(pady=(10, 5))
        
        button_frame = ttk.Frame(self.confirmation_frame)
        button_frame.pack(pady=5)
        
        self.yes_button = ttk.Button(
            button_frame,
            text="ТАК",
            style='Confirm.TButton',
            command=self.on_yes_clicked
        )
        self.yes_button.pack(side='left', padx=8)

        self.no_button = ttk.Button(
            button_frame,
            text="НІ",
            style='Cancel.TButton',
            command=self.on_no_clicked
        )
        self.no_button.pack(side='left', padx=8)

        # Третя кнопка - увімкнути автопідтвердження всіх дій
        self.auto_button = ttk.Button(
            button_frame,
            text="АВТОМАТИЧНО (всі дозволено)",
            style='Confirm.TButton',
            command=self.on_auto_clicked
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
        input_frame.columnconfigure(1, weight=0)  # Кнопка фіксована
        
        # Поле вводу
        self.input_text = tk.Text(
            input_frame,
            height=3,
            font=('Segoe UI', 10),
            wrap=tk.WORD,
            bg='white',
            fg='#333333',
            relief='solid',
            borderwidth=1
        )
        self.input_text.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        
        # Кнопка відправки
        self.send_button = ttk.Button(
            input_frame,
            text="➤",
            width=3,
            command=self.send_text_command,
            style='Send.TButton'
        )
        self.send_button.grid(row=0, column=1, sticky='ns')
        
        # Кнопка «Стоп» (изначально скрыта)
        self.stop_button = ttk.Button(
            input_frame,
            text="⬛ СТОП",
            command=self.stop_execution,
            style='Stop.TButton'
        )
        # Будет показана при выполнении задачи
        
        # Підказка
        self.input_text.insert(1.0, "Введіть команду...")
        self.input_text.configure(fg='#999999')
        
        # Обробка клавіш
        self.input_text.bind('<Return>', self.on_enter_pressed)
        self.input_text.bind('<Shift-Return>', self.on_shift_enter)
        self.input_text.bind('<FocusIn>', self.on_input_focus)
        self.input_text.bind('<FocusOut>', self.on_input_blur)
        self.input_text.bind('<Key>', self.on_input_key)
        # Привязка для остановки (тільки Esc, бо Ctrl+C конфліктує з копіюванням)
        self.root.bind('<Escape>', lambda e: self.stop_execution())

        # Налаштування копіювання/вставки/вирізання з підтримкою будь-якої
        # розкладки клавіатури (українська, англійська, російська тощо)
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
            padding=5
        )
        status_bar.pack(fill='x', side='bottom', pady=(5, 0))
        
        # Прогрес-бар (прихований за замовчуванням)
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(
            main_container,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill='x', side='bottom', pady=(2, 0))
        self.progress_bar.pack_forget()  # приховати спочатку
        
    
    def setup_window(self):
        """Налаштування поведінки вікна"""
        self.root.bind('<Configure>', self.on_resize)
        self.root.after(100, self.focus_input)
    
    def on_resize(self, event=None):
        """Обробка зміни розміру вікна"""
        self.root.update_idletasks()
    
    def focus_input(self):
        """Встановити фокус на поле вводу"""
        self.input_text.focus_set()
    
    def add_message(self, sender, message):
        """Додати повідомлення до чату"""
        # Захист від None
        if message is None:
            message = ""
        # Захист від випадкової передачі кортежу
        if isinstance(message, (tuple, list)):
            message = " ".join(str(item) for item in message)
        
        self.chat_history.configure(state='normal')
        
        # Очищаємо подвійні префікси
        if sender == "assistant":
            prefixes_to_remove = [
                f"{ASSISTANT_TITLE}: ",
                f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}: ",
                "⚡ МАРК: ",
                "МАРК: "
            ]
            for prefix in prefixes_to_remove:
                if message.startswith(prefix):
                    message = message[len(prefix):].strip()
                    break
        
        # Додаємо роздільник
        current_text = self.chat_history.get(1.0, tk.END).strip()
        if current_text:
            self.chat_history.insert(tk.END, "\n" + "-"*50 + "\n")
        
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
        self.chat_history.configure(state='disabled')
    
    def on_input_focus(self, event=None):
        """Коли поле вводу отримує фокус"""
        current_text = self.input_text.get(1.0, tk.END).strip()
        if current_text == "Введіть команду...":
            self.input_text.delete(1.0, tk.END)
            self.input_text.configure(fg='#333333')
        
        self.input_active = True
        self.status_var.set("⌨️  Режим вводу тексту - аудіо призупинено")
        
        if self.assistant_callback:
            self.assistant_callback('pause_listening')
    
    def on_input_blur(self, event=None):
        """Коли поле вводу втрачає фокус"""
        current_text = self.input_text.get(1.0, tk.END).strip()
        if not current_text:
            self.input_text.insert(1.0, "Введіть команду...")
            self.input_text.configure(fg='#999999')
        
        self.input_active = False
        self.last_input_time = time.time()
        
        if self.assistant_callback:
            self.assistant_callback('resume_listening')
    
    def on_input_key(self, event=None):
        """Коли натискається клавіша"""
        self.last_input_time = time.time()
    
    def on_enter_pressed(self, event=None):
        """Обробка Enter"""
        if not self.awaiting_confirmation:
            self.send_text_command()
            return 'break'
        return None
    
    def on_shift_enter(self, event=None):
        """Обробка Shift+Enter"""
        self.input_text.insert(tk.INSERT, '\n')
        return 'break'
    
    # ============================================================
    # CLIPBOARD: універсальне копіювання/вставка/вирізання
    # Підтримка будь-якої розкладки (UA/EN/RU) через keycode
    # ============================================================

    # Windows virtual key codes для C, V, X, A, Insert
    _KEYCODE_C = 67
    _KEYCODE_V = 86
    _KEYCODE_X = 88
    _KEYCODE_A = 65
    _KEYCODE_INSERT = 45

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

        # Fallback: Windows API через ctypes (якщо tkinter не бачить буфер)
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
        # Для disabled Text-віджетів (chat_history) виділення все одно працює
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

        # Вставити на позицію курсора (без strip - зберігаємо форматування)
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
            # Перед показом меню встановлюємо фокус на віджет
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
    
    def send_text_command(self):
        """Відправити текстову команду"""
        command = self.input_text.get(1.0, tk.END).strip()
        
        if not command or command == "Введіть команду...":
            return
        
        self.input_text.delete(1.0, tk.END)
        
        if self.assistant_callback:
            self.assistant_callback('process_text', command)
    
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
        """Коли натиснуто АВТОМАТИЧНО - увімкнути auto_approve_all і підтвердити."""
        if self.confirmation_callback:
            self.confirmation_callback("auto")
        self.hide_confirmation()
    
    def on_confirmation_timeout(self):
        """Таймаут підтвердження"""
        if self.awaiting_confirmation:
            self.root.after(0, self.timeout_confirmation)
    
    def timeout_confirmation(self):
        """Обробка таймауту в головному потоці"""
        if self.awaiting_confirmation:
            self.add_message("assistant", "⏰ Час очікування вийшов. Дію скасовано.")
            if self.confirmation_callback:
                self.confirmation_callback(False)
            self.hide_confirmation()
    
    def check_idle(self):
        """Перевірка простою"""
        if self.input_active:
            idle_time = time.time() - self.last_input_time
            if idle_time > self.idle_timeout:
                self.on_input_blur()
                self.add_message("system", f"⏳ Автоматичне відновлення аудіо")
        
        self.root.after(1000, self.check_idle)
    
    def process_queue(self):
        """Обробка черги повідомлень"""
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

    # ============================================================
    # ПАНЕЛЬ ПЛАНУ ВИКОНАННЯ
    # ============================================================

    _STATUS_ICONS = {
        "pending":             ("⏳", "#888888"),
        "running":             ("▶️", "#1976d2"),
        "ok":                  ("✅", "#2e7d32"),
        "error":               ("❌", "#c62828"),
        "blocked":             ("⛔", "#b71c1c"),
        "needs_confirmation":  ("❓", "#ef6c00"),
        "skipped":             ("⏭️", "#9e9e9e"),
    }

    def show_plan_panel(self, steps_info: list):
        """Показати панель плану з переліком кроків (status = pending)."""
        # Очистити попередню панель
        for child in self.plan_steps_container.winfo_children():
            child.destroy()
        self._plan_step_labels = []
        self._plan_steps = list(steps_info) if steps_info else []

        total = len(self._plan_steps)
        self.plan_title_var.set(f"📋 План виконання  (0/{total})")
        self.plan_progress_var.set(0)

        # Якщо тут нема кроків - не показувати
        if total == 0:
            return

        # Створити рядки для кожного кроку
        for step in self._plan_steps:
            row = ttk.Frame(self.plan_steps_container)
            row.pack(fill='x', pady=1)
            icon, color = self._STATUS_ICONS["pending"]
            label = tk.Label(
                row,
                text=f"  {icon}  {step.get('index', 0) + 1}. {step.get('action', '')}"
                     + (f" — {step.get('goal', '')}" if step.get('goal') else ""),
                font=('Segoe UI', 9),
                fg=color,
                anchor='w',
                justify='left',
                bg='#f5f5f5',
                padx=5,
                pady=2,
            )
            label.pack(fill='x')
            self._plan_step_labels.append(label)

        # Показати панель перед confirmation_frame/input_container
        if not self.plan_frame.winfo_ismapped():
            # pack перед input_container
            self.plan_frame.pack(
                fill='x', side='bottom', pady=(5, 5), before=self.input_container
            )
        self._plan_expanded = True
        self.plan_collapse_btn.config(text="▼")
        self.plan_steps_container.pack(fill='x', padx=5, pady=(0, 5))

    def update_plan_step(self, data: dict):
        """Оновити статус конкретного кроку."""
        if not isinstance(data, dict):
            return
        idx = data.get("index", -1)
        status = data.get("status", "pending")
        action = data.get("action", "")
        goal = data.get("goal", "")
        detail = data.get("detail", "")

        if idx < 0 or idx >= len(self._plan_step_labels):
            return

        label = self._plan_step_labels[idx]
        icon, color = self._STATUS_ICONS.get(status, ("•", "#555555"))
        text = f"  {icon}  {idx + 1}. {action}"
        if goal:
            text += f" — {goal}"
        if detail and status in ("error", "blocked"):
            text += f"  [{detail[:60]}]"
        label.config(text=text, fg=color)

        # Підрахунок прогресу
        done_count = sum(
            1 for i, step in enumerate(self._plan_steps)
            if i <= idx and self._get_label_status(i) in ("ok", "error", "blocked", "skipped")
        )
        total = len(self._plan_steps)
        if total > 0:
            progress_pct = int((done_count / total) * 100)
            self.plan_progress_var.set(progress_pct)
            self.plan_title_var.set(f"📋 План виконання  ({done_count}/{total})")

    def _get_label_status(self, idx: int) -> str:
        """Визначити статус кроку з кольору label (helper)."""
        if idx >= len(self._plan_step_labels):
            return "pending"
        color = self._plan_step_labels[idx].cget("fg")
        for status, (_, status_color) in self._STATUS_ICONS.items():
            if status_color == color:
                return status
        return "pending"

    def finish_plan_panel(self, stats: dict):
        """Закінчити план - показати фінальний статус."""
        if not isinstance(stats, dict):
            stats = {}
        total = stats.get("total", 0)
        ok = stats.get("ok", 0)
        err = stats.get("error", 0)
        blocked = stats.get("blocked", 0)
        confirm = stats.get("needs_confirmation", 0)

        self.plan_progress_var.set(100)

        if blocked:
            title = f"⛔ План зупинено: {blocked} заблоковано ({ok}/{total} успішно)"
        elif err:
            title = f"⚠️ План із помилками: {err} помилок ({ok}/{total} успішно)"
        elif confirm:
            title = f"❓ План не завершено: {confirm} не підтверджено ({ok}/{total} успішно)"
        else:
            title = f"✅ План виконано  ({ok}/{total})"
        self.plan_title_var.set(title)

        # Автоматично приховати панель через 8 секунд, якщо все ок
        if ok == total and not (err or blocked or confirm):
            self.root.after(8000, self._auto_hide_plan_panel)

    def _auto_hide_plan_panel(self):
        """Автоматично приховати панель, якщо план успішно завершений."""
        try:
            if self.plan_frame.winfo_ismapped():
                self.plan_frame.pack_forget()
        except tk.TclError:
            pass

    def _toggle_plan_panel(self):
        """Згорнути/розгорнути список кроків у панелі."""
        self._plan_expanded = not self._plan_expanded
        if self._plan_expanded:
            self.plan_steps_container.pack(fill='x', padx=5, pady=(0, 5))
            self.plan_collapse_btn.config(text="▼")
        else:
            self.plan_steps_container.pack_forget()
            self.plan_collapse_btn.config(text="▶")

    # ============================================================
    # ВКЛАДКА НАЛАШТУВАНЬ
    # ============================================================

    def _on_tab_changed(self, event=None):
        """Викликається при перемиканні вкладок. Лінивно будує Settings."""
        try:
            current = self.notebook.index(self.notebook.select())
        except tk.TclError:
            return
        # Вкладка Settings = індекс 1
        if current == 1 and not self._settings_built:
            self._build_settings_tab()
            self._settings_built = True

    def _build_settings_tab(self):
        """Побудувати UI вкладки Налаштування на основі SETTINGS_SCHEMA."""
        from functions.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        self._settings_vars = {}  # key → tk.Variable

        # Scrollable container
        canvas = tk.Canvas(self.settings_frame, bg='#fafafa', highlightthickness=0)
        scroll = ttk.Scrollbar(self.settings_frame, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        inner = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_frame_configure(_event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        inner.bind('<Configure>', _on_frame_configure)
        canvas.bind('<Configure>', _on_canvas_configure)

        # Mouse-wheel scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', _on_mousewheel)

        # --- Згрупувати по "group" ---
        groups: dict[str, list[tuple[str, dict]]] = {}
        for key, schema in SETTINGS_SCHEMA.items():
            group = schema.get('group', 'Інше')
            groups.setdefault(group, []).append((key, schema))

        # Рендер груп
        row_idx = 0
        for group_name, items in groups.items():
            # Header групи
            header = ttk.Label(
                inner,
                text=f"▸ {group_name}",
                font=('Segoe UI', 11, 'bold'),
                foreground='#1976d2',
            )
            header.grid(row=row_idx, column=0, columnspan=3, sticky='w', padx=5, pady=(12, 4))
            row_idx += 1

            for key, schema in items:
                current_value = settings.get(key)
                var = self._create_settings_widget(inner, key, schema, current_value, row_idx)
                self._settings_vars[key] = var
                row_idx += 1

        # Кнопки знизу
        btn_frame = ttk.Frame(inner)
        btn_frame.grid(row=row_idx, column=0, columnspan=3, sticky='ew', padx=5, pady=15)

        save_btn = ttk.Button(
            btn_frame,
            text="💾 Зберегти всі",
            style='Confirm.TButton',
            command=self._save_all_settings,
        )
        save_btn.pack(side='left', padx=5)

        reset_btn = ttk.Button(
            btn_frame,
            text="↺ Скинути до config.py",
            command=self._reset_all_settings,
        )
        reset_btn.pack(side='left', padx=5)

        reload_btn = ttk.Button(
            btn_frame,
            text="🔄 Перезавантажити",
            command=self._reload_settings_tab,
        )
        reload_btn.pack(side='left', padx=5)

        # Статус-лейбл
        self._settings_status = ttk.Label(
            inner,
            text="Зміни деяких налаштувань (STT/TTS/аудіо) застосуються після перезапуску.",
            font=('Segoe UI', 8, 'italic'),
            foreground='#888888',
            wraplength=600,
        )
        self._settings_status.grid(row=row_idx + 1, column=0, columnspan=3, sticky='w', padx=5, pady=5)

        inner.columnconfigure(1, weight=1)

    def _create_settings_widget(self, parent, key: str, schema: dict, value, row: int):
        """Створити один віджет для одного налаштування. Повертає tk.Variable."""
        label_text = schema.get('label', key)
        desc = schema.get('desc', '')
        wtype = schema.get('type', 'str')

        # Label (назва)
        lbl = ttk.Label(parent, text=label_text, font=('Segoe UI', 9, 'bold'))
        lbl.grid(row=row, column=0, sticky='nw', padx=(20, 8), pady=4)

        # Widget за типом
        var = None
        if wtype == 'bool':
            var = tk.BooleanVar(value=bool(value))
            widget = ttk.Checkbutton(parent, variable=var)
            widget.grid(row=row, column=1, sticky='w', padx=4, pady=4)
        elif wtype == 'choice':
            choices = schema.get('choices', [])
            var = tk.StringVar(value=str(value) if value is not None else '')
            widget = ttk.Combobox(parent, textvariable=var, values=choices, state='readonly', width=20)
            widget.grid(row=row, column=1, sticky='w', padx=4, pady=4)
        elif wtype == 'int':
            var = tk.StringVar(value=str(value) if value is not None else '0')
            widget = ttk.Entry(parent, textvariable=var, width=15)
            widget.grid(row=row, column=1, sticky='w', padx=4, pady=4)
        elif wtype == 'float':
            var = tk.StringVar(value=str(value) if value is not None else '0.0')
            widget = ttk.Entry(parent, textvariable=var, width=15)
            widget.grid(row=row, column=1, sticky='w', padx=4, pady=4)
        elif wtype == 'llm_endpoints':
            # Спеціальний редактор списку LLM-моделей
            var = LLMEndpointsEditor(parent, value or [], row=row)
            # Desc показуємо під ним
            if desc:
                desc_lbl = ttk.Label(
                    parent,
                    text=desc,
                    font=('Segoe UI', 8),
                    foreground='#888888',
                    wraplength=600,
                )
                desc_lbl.grid(row=row + 1, column=0, columnspan=3, sticky='w', padx=20, pady=(0, 4))
            return var
        else:  # str
            var = tk.StringVar(value=str(value) if value is not None else '')
            widget = ttk.Entry(parent, textvariable=var, width=40)
            widget.grid(row=row, column=1, sticky='ew', padx=4, pady=4)

        # Desc (пояснення)
        if desc:
            desc_lbl = ttk.Label(
                parent,
                text=desc,
                font=('Segoe UI', 8),
                foreground='#888888',
                wraplength=350,
            )
            desc_lbl.grid(row=row, column=2, sticky='w', padx=4, pady=4)

        return var

    def _save_all_settings(self):
        """Зберегти всі значення з віджетів у SettingsManager."""
        from functions.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        saved = 0
        errors = []
        for key, var in self._settings_vars.items():
            schema = SETTINGS_SCHEMA.get(key, {})
            wtype = schema.get('type', 'str')
            try:
                raw = var.get()
                value = self._cast_value(raw, wtype, schema)
                settings.set(key, value, persist=not schema.get('user_only', False))
                saved += 1
            except (ValueError, TypeError) as e:
                errors.append(f"{key}: {e}")

        if errors:
            self._settings_status.config(
                text=f"⚠️ Помилки у {len(errors)} полях: {'; '.join(errors[:3])}",
                foreground='#c62828',
            )
        else:
            self._settings_status.config(
                text=f"✅ Збережено {saved} налаштувань.",
                foreground='#2e7d32',
            )

    def _cast_value(self, raw, wtype: str, schema: dict):
        """Привести значення з tk.Variable до потрібного типу + валідація."""
        if wtype == 'bool':
            return bool(raw)
        if wtype == 'int':
            v = int(raw)
            if 'min' in schema and v < schema['min']:
                raise ValueError(f">= {schema['min']}")
            if 'max' in schema and v > schema['max']:
                raise ValueError(f"<= {schema['max']}")
            return v
        if wtype == 'float':
            v = float(raw)
            if 'min' in schema and v < schema['min']:
                raise ValueError(f">= {schema['min']}")
            if 'max' in schema and v > schema['max']:
                raise ValueError(f"<= {schema['max']}")
            return v
        if wtype == 'choice':
            if schema.get('choices') and raw not in schema['choices']:
                raise ValueError(f"невалідний вибір")
            return str(raw)
        if wtype == 'llm_endpoints':
            # `raw` вже list[dict] з LLMEndpointsEditor.get()
            if not isinstance(raw, list):
                raise ValueError("очікується список моделей")
            return raw
        return str(raw)

    def _reset_all_settings(self):
        """Скинути всі user-налаштування до дефолтів з config.py."""
        from functions.core_settings import get_settings, SETTINGS_SCHEMA

        settings = get_settings()
        for key in SETTINGS_SCHEMA.keys():
            settings.reset(key)
        self._reload_settings_tab()
        self._settings_status.config(
            text="↺ Налаштування скинуто до config.py.",
            foreground='#1976d2',
        )

    def _reload_settings_tab(self):
        """Перезбудувати вкладку налаштувань (щоб побачити скинуті значення)."""
        for child in self.settings_frame.winfo_children():
            child.destroy()
        self._settings_built = False
        self._build_settings_tab()
        self._settings_built = True

    def start_stream_message(self):
        """Почати нове повідомлення асистента для стрімінгу."""
        self.chat_history.configure(state='normal')
        current_text = self.chat_history.get(1.0, tk.END).strip()
        if current_text:
            self.chat_history.insert(tk.END, "\n" + "-"*50 + "\n")
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
        """Завершити стрімінг (додати новий рядок)."""
        self.chat_history.configure(state='normal')
        self.chat_history.insert(self.stream_insert_pos, "\n")
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')

    def update_progress(self, progress: int, status_text: str):
        """Оновити тільки текстовий статус (прогрес-бар тепер у панелі плану)."""
        # Не засмічуємо чат - тільки статус-бар унизу
        if status_text:
            self.status_var.set(status_text)
        self.root.update_idletasks()

    def show_stop_button(self):
        """Показать кнопку «Стоп» и скрыть кнопку отправки."""
        self.send_button.grid_remove()
        self.stop_button.grid(row=0, column=1, sticky='ns')
        self.status_var.set("⏳ Виконання... (Esc або Стоп для переривання)")

    def hide_stop_button(self):
        """Скрыть кнопку «Стоп» и показать кнопку отправки."""
        self.stop_button.grid_remove()
        self.send_button.grid(row=0, column=1, sticky='ns')
        self.progress_bar.pack_forget()
        self.status_var.set("✅ Готовий до роботи")

    def stop_execution(self):
        """Обработчик нажатия кнопки «Стоп»."""
        if self.assistant_callback:
            self.assistant_callback('stop_execution', None)
        # Визуально вернём кнопку отправки
        self.hide_stop_button()

    def queue_message(self, msg_type, data):
        """Додати повідомлення до черги"""
        self.message_queue.put((msg_type, data))
    
    def run(self):
        """Запустити GUI"""
        self.root.mainloop()

def run_gui(assistant_callback):
    """Запуск GUI"""
    gui = AssistantGUI(assistant_callback)
    gui.run()