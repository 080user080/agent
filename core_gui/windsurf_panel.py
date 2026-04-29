# core_gui/windsurf_panel.py
"""Міксин для панелі Windsurf Watcher (Phase 12.5)."""
import tkinter as tk
from tkinter import ttk


class WindsurfPanelMixin:
    """Логіка панелі Windsurf Watcher (статус, кнопки start/stop).

    Очікує атрибути (створені в AssistantGUI.create_widgets):
    - self.root: tk.Tk
    - self.assistant_callback: callable
    """

    def create_windsurf_panel(self):
        """Створити панель Windsurf Watcher."""
        # Фрейм для Windsurf Watcher (створюється в chat_frame)
        if not hasattr(self, 'chat_frame'):
            return  # Якщо chat_frame ще не створено
        self.windsurf_frame = ttk.Frame(self.chat_frame)
        self.windsurf_frame.pack(fill='x', padx=5, pady=(5, 0))

        # Заголовок
        windsurf_header = ttk.Frame(self.windsurf_frame)
        windsurf_header.pack(fill='x')

        self.windsurf_title_var = tk.StringVar(value="🌊 Windsurf Watcher")
        windsurf_title = ttk.Label(
            windsurf_header,
            textvariable=self.windsurf_title_var,
            font=('Segoe UI', 10, 'bold'),
        )
        windsurf_title.pack(side='left')

        # Кнопка "Стоп" (прихована за замовчуванням)
        self.windsurf_stop_btn = ttk.Button(
            windsurf_header,
            text="⏹ Стоп",
            width=8,
            command=self._on_stop_windsurf,
            style='Stop.TButton',
        )

        # Кнопка "Старт"
        self.windsurf_start_btn = ttk.Button(
            windsurf_header,
            text="▶ Старт",
            width=12,
            command=self._on_start_windsurf,
            style='Confirm.TButton',
        )
        self.windsurf_start_btn.pack(side='right', padx=(0, 5))

        # Статус
        self.windsurf_status_var = tk.StringVar(value="Очікує...")
        windsurf_status = ttk.Label(
            windsurf_header,
            textvariable=self.windsurf_status_var,
            font=('Segoe UI', 9),
            foreground='#666666',
        )
        windsurf_status.pack(side='right', padx=(10, 0))

        # Контейнер для статистики
        self.windsurf_stats_frame = ttk.Frame(self.windsurf_frame)
        self.windsurf_stats_frame.pack(fill='x', padx=5, pady=(5, 0))

        self.windsurf_responses_var = tk.StringVar(value="Відповідей: 0")
        windsurf_responses = ttk.Label(
            self.windsurf_stats_frame,
            textvariable=self.windsurf_responses_var,
            font=('Segoe UI', 9),
        )
        windsurf_responses.pack(side='left', padx=(0, 10))

        self.windsurf_snapshots_var = tk.StringVar(value="Снапшотів: 0")
        windsurf_snapshots = ttk.Label(
            self.windsurf_stats_frame,
            textvariable=self.windsurf_snapshots_var,
            font=('Segoe UI', 9),
        )
        windsurf_snapshots.pack(side='left', padx=(0, 10))

        # Приховуємо панель за замовчуванням
        self.windsurf_frame.pack_forget()

        # Стан
        self._windsurf_running = False

    def show_windsurf_panel(self):
        """Показати панель Windsurf Watcher."""
        self.windsurf_frame.pack(fill='x', padx=5, pady=(5, 0))

    def hide_windsurf_panel(self):
        """Приховати панель Windsurf Watcher."""
        self.windsurf_frame.pack_forget()

    def _on_start_windsurf(self):
        """Обробник кнопки 'Старт'."""
        if self.assistant_callback:
            # Показуємо кнопку Стоп, ховаємо Старт
            self.windsurf_start_btn.pack_forget()
            self.windsurf_stop_btn.pack(side='right', padx=(0, 5))
            self.windsurf_status_var.set("🔄 Запуск...")
            self.assistant_callback('start_windsurf_watch', None)

    def _on_stop_windsurf(self):
        """Обробник кнопки 'Стоп'."""
        if self.assistant_callback:
            self.assistant_callback('stop_windsurf_watch', None)
            # Повертаємо кнопку Старт
            self.windsurf_stop_btn.pack_forget()
            self.windsurf_start_btn.pack(side='right', padx=(0, 5))
            self.windsurf_status_var.set("⏹ Зупинено")

    def on_windsurf_started(self, data):
        """Викликається коли Windsurf Watcher запущено."""
        self._windsurf_running = True
        self.windsurf_status_var.set("🔄 Слухаю Windsurf...")
        self.windsurf_title_var.set("🌊 Windsurf Watcher (активний)")

    def on_windsurf_stopped(self, data):
        """Викликається коли Windsurf Watcher зупинено."""
        self._windsurf_running = False
        reason = data.get('reason', 'manual')
        self.windsurf_status_var.set(f"⏹ Зупинено: {reason}")
        self.windsurf_title_var.set("🌊 Windsurf Watcher")
        # Повертаємо кнопку Старт
        self.windsurf_stop_btn.pack_forget()
        self.windsurf_start_btn.pack(side='right', padx=(0, 5))

    def on_windsurf_response(self, data):
        """Викликається коли отримано нову відповідь."""
        responses = data.get('responses_captured', 0)
        snapshots = data.get('snapshots_taken', 0)
        self.windsurf_responses_var.set(f"Відповідей: {responses}")
        self.windsurf_snapshots_var.set(f"Снапшотів: {snapshots}")
        self.windsurf_status_var.set(f"📝 Отримано відповідь #{responses}")

    def on_windsurf_error(self, data):
        """Викликається при помилці Windsurf Watcher."""
        error = data.get('error', 'Невідома помилка')
        self.windsurf_status_var.set(f"❌ Помилка: {error}")
        # Повертаємо кнопку Старт
        self.windsurf_stop_btn.pack_forget()
        self.windsurf_start_btn.pack(side='right', padx=(0, 5))

    def _toggle_windsurf_panel(self):
        """Перемкнути видимість панелі Windsurf Watcher."""
        if self.windsurf_frame.winfo_ismapped():
            self.hide_windsurf_panel()
        else:
            self.show_windsurf_panel()
