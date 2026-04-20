# core_gui/styles.py
"""ttk стилі для асистента."""
import tkinter as tk
from tkinter import ttk


def apply_styles(style: ttk.Style) -> None:
    """Налаштувати всі кастомні ttk-стилі для GUI."""
    # Windows-теми (vista/xpnative) ігнорують background у ttk.Button.
    # 'clam' підтримує власні кольори — примусово ставимо її.
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass

    # Темна тема для заголовка
    style.configure(
        'Title.TLabel',
        background='#3c3c3c',
        foreground='white',
        font=('Segoe UI', 12, 'bold'),
        padding=10,
    )

    # --- Кнопка ПІДТВЕРДИТИ (зелена) ---
    style.configure(
        'Confirm.TButton',
        background='#4CAF50',
        foreground='white',
        font=('Segoe UI', 10, 'bold'),
        padding=10,
        borderwidth=0,
    )
    style.map(
        'Confirm.TButton',
        background=[('active', '#45a049'), ('pressed', '#3d8b40'), ('!active', '#4CAF50')],
        foreground=[('active', 'white'), ('!active', 'white')],
    )

    # --- Кнопка СКАСУВАТИ (червона) ---
    style.configure(
        'Cancel.TButton',
        background='#f44336',
        foreground='white',
        font=('Segoe UI', 10, 'bold'),
        padding=10,
        borderwidth=0,
    )
    style.map(
        'Cancel.TButton',
        background=[('active', '#d73026'), ('pressed', '#b71c1c'), ('!active', '#f44336')],
        foreground=[('active', 'white'), ('!active', 'white')],
    )

    # --- Кнопка ВІДПРАВИТИ (синя) ---
    style.configure(
        'Send.TButton',
        background='#1976d2',
        foreground='white',
        font=('Segoe UI', 12, 'bold'),
        padding=(15, 10),
        borderwidth=0,
    )
    style.map(
        'Send.TButton',
        background=[('active', '#1565c0'), ('pressed', '#0d47a1'), ('!active', '#1976d2')],
        foreground=[('active', 'white'), ('!active', 'white')],
    )

    # --- Кнопка СТОП (оранжева) ---
    style.configure(
        'Stop.TButton',
        background='#e65100',
        foreground='white',
        font=('Segoe UI', 12, 'bold'),
        padding=(15, 10),
        borderwidth=0,
    )
    style.map(
        'Stop.TButton',
        background=[('active', '#bf360c'), ('pressed', '#8c2400'), ('!active', '#e65100')],
        foreground=[('active', 'white'), ('!active', 'white')],
    )

    # --- Кнопка МІКРОФОН (сіра, неактивна / червона при записі) ---
    style.configure(
        'Mic.TButton',
        background='#9e9e9e',
        foreground='white',
        font=('Segoe UI', 12, 'bold'),
        padding=(10, 10),
        borderwidth=0,
    )
    style.map(
        'Mic.TButton',
        background=[('active', '#757575'), ('pressed', '#616161'), ('!active', '#9e9e9e')],
        foreground=[('active', 'white'), ('!active', 'white')],
    )
    # Стиль при записі (червоний)
    style.configure(
        'MicRecording.TButton',
        background='#e74c3c',
        foreground='white',
        font=('Segoe UI', 12, 'bold'),
        padding=(10, 10),
        borderwidth=0,
    )
    style.map(
        'MicRecording.TButton',
        background=[('active', '#c0392b'), ('pressed', '#a93226'), ('!active', '#e74c3c')],
        foreground=[('active', 'white'), ('!active', 'white')],
    )
