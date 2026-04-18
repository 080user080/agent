# core_gui/settings_tab.py
"""Міксин для вкладки 'Налаштування' (SETTINGS_SCHEMA)."""
import json
import os
import tkinter as tk
from tkinter import ttk

from .llm_endpoints_editor import LLMEndpointsEditor


class SettingsTabMixin:
    """Вкладка Налаштування: рендер SETTINGS_SCHEMA, збереження, скидання.

    Очікує атрибути:
    - self.settings_frame: ttk.Frame (контейнер вкладки)
    - self.notebook: ttk.Notebook
    - self._settings_built: bool
    """

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

        clear_cache_btn = ttk.Button(
            btn_frame,
            text="🗑️ Очистити кеш команд",
            style='Cancel.TButton',
            command=self._clear_command_cache,
        )
        clear_cache_btn.pack(side='left', padx=5)

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
                raise ValueError("невалідний вибір")
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

    def _clear_command_cache(self):
        """Очистити кеш команд (functions/cache_data.json)."""
        # Шукаємо cache_data.json у functions/ відносно кореня проєкту
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_file = os.path.join(root_dir, "functions", "cache_data.json")
        try:
            count = 0
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                count = len(data)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False)
            self._settings_status.config(
                text=f"🗑️ Кеш команд очищено ({count} записів).",
                foreground='#1976d2',
            )
        except Exception as e:
            self._settings_status.config(
                text=f"❌ Помилка очищення кешу: {e}",
                foreground='#d32f2f',
            )
