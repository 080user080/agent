# core_gui/llm_endpoints_editor.py
"""Редактор списку LLM-ендпоїнтів для вкладки налаштувань."""
import tkinter as tk
from tkinter import ttk


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
