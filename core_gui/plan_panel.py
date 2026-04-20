# core_gui/plan_panel.py
"""Міксин для панелі плану виконання з прогресом і статусами кроків."""
import tkinter as tk
from tkinter import ttk


class PlanPanelMixin:
    """Логіка панелі плану (кроки, прогрес, статуси).

    Очікує атрибути (створені в AssistantGUI.create_widgets):
    - self.plan_frame, self.plan_steps_container
    - self.plan_title_var, self.plan_progress_var, self.plan_collapse_btn
    - self.input_container
    """

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
        self._plan_steps = []

        for idx, step_info in enumerate(steps_info):
            action = step_info.get('action', 'unknown')
            goal = step_info.get('goal', '')

            step_frame = ttk.Frame(self.plan_steps_container)
            step_frame.pack(fill='x', pady=1)

            status_icon = "⏳"
            status_color = "#ffa726"

            status_label = ttk.Label(
                step_frame,
                text=status_icon,
                font=('Segoe UI', 9),
                foreground=status_color,
            )
            status_label.pack(side='left', padx=(0, 5))

            action_label = ttk.Label(
                step_frame,
                text=f"{idx + 1}. {action}",
                font=('Segoe UI', 9, 'bold'),
                foreground='#333333',
            )
            action_label.pack(side='left')

            if goal:
                goal_label = ttk.Label(
                    step_frame,
                    text=f" — {goal}",
                    font=('Segoe UI', 8),
                    foreground='#666666',
                )
                goal_label.pack(side='left')

            self._plan_steps.append({
                'frame': step_frame,
                'status_label': status_label,
                'action': action,
                'goal': goal,
            })
            self._plan_step_labels.append(status_label)

        # Показати панель в chat_frame під чатом (bottom)
        if not self.plan_frame.winfo_ismapped():
            self.plan_frame.pack(fill='x', side='bottom', pady=(5, 5))
        self._plan_expanded = True
        self.plan_collapse_btn.config(text="▼")

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

        # Перевіряємо чи widget ще існує
        try:
            label.winfo_exists()
        except Exception:
            # Widget знищено, пропускаємо оновлення
            return

        icon, color = self._STATUS_ICONS.get(status, ("•", "#555555"))
        text = f"  {icon}  {idx + 1}. {action}"
        if goal:
            text += f" — {goal}"
        if detail and status in ("error", "blocked"):
            text += f"  [{detail[:60]}]"
        try:
            label.config(text=text, foreground=color)
        except Exception:
            # Fallback для tk.Label (не ttk)
            try:
                label.config(text=text, fg=color)
            except Exception:
                label.config(text=text)

        # Підрахунок прогресу
        done_count = sum(
            1 for i, _step in enumerate(self._plan_steps)
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

        label = self._plan_step_labels[idx]

        # Перевіряємо чи widget ще існує
        try:
            label.winfo_exists()
        except Exception:
            return "pending"

        try:
            color = label.cget("foreground")
        except Exception:
            try:
                color = label.cget("fg")
            except Exception:
                return "pending"
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
