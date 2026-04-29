# functions/core_executor.py
"""Менеджер виконання завдань у фоновому потоці з оновленням GUI"""
import threading
import time
from typing import Callable, Optional

class TaskExecutor:
    """Керує виконанням тривалих завдань (планів) у фоновому режимі."""
    
    def __init__(self, gui_callback: Optional[Callable] = None):
        self.gui_callback = gui_callback
        self.current_task_thread = None
        self.is_running = False
        self.progress = 0  # 0-100
        self.status = "Готовий"
        self._stop_requested = False
    
    def execute_plan_async(self, plan: list, execute_fn: Callable, on_complete: Optional[Callable] = None):
        """Запустити виконання плану в окремому потоці."""
        if self.is_running:
            if self.gui_callback:
                self.gui_callback('update_status', '⚠️ Вже виконується завдання')
            return
        
        self.is_running = True
        self._stop_requested = False
        self.progress = 0
        self.status = "Виконання плану..."
        self._notify_progress()
        self._notify_execution_started()
        self._notify_plan_started(plan)
        
        def task_wrapper():
            results = []
            active_plan = list(plan)
            i = 0
            while i < len(active_plan):
                if self._stop_requested:
                    # Позначити решту кроків як skipped
                    for skip_i in range(i, len(active_plan)):
                        self._notify_step_update(skip_i, active_plan[skip_i], "skipped", "Зупинено")
                    break
                step = active_plan[i]
                total_steps = max(len(active_plan), 1)
                step_number = i + 1
                self.progress = int((step_number / total_steps) * 100)
                action = step.get('action', '')
                self.status = f"Крок {step_number}/{total_steps}: {action}"
                self._notify_progress()
                # Сповіщення "крок почався"
                self._notify_step_update(i, step, "running", "")
                
                try:
                    # Виконання окремого кроку
                    result = execute_fn(step)
                    results.append(result)

                    # Визначити статус цього кроку для UI
                    step_status = "ok"
                    step_detail = ""
                    if isinstance(result, dict):
                        raw_status = result.get("status", "ok")
                        if raw_status == "blocked":
                            step_status = "blocked"
                        elif raw_status == "needs_confirmation":
                            step_status = "needs_confirmation"
                        elif raw_status == "stopped":
                            step_status = "skipped"
                        elif raw_status == "error":
                            step_status = "error"
                        else:
                            step_status = "ok"
                        step_detail = str(result.get("validation") or result.get("result") or "")[:120]

                        appended_steps = result.get("append_steps") or []
                        replace_remaining = result.get("replace_remaining_steps") or []
                        if replace_remaining:
                            active_plan = active_plan[: step_number] + list(replace_remaining)
                        elif appended_steps:
                            active_plan.extend(appended_steps)

                    self._notify_step_update(i, step, step_status, step_detail)
                except Exception as e:
                    results.append((step.get('action'), 'error', str(e)))
                    self.status = f"Помилка на кроці {step_number}"
                    self._notify_progress()
                    self._notify_step_update(i, step, "error", str(e)[:120])
                    break
                time.sleep(0.2)  # невелика пауза між кроками для стабільності GUI
                i += 1
            
            self.is_running = False
            self.status = "Виконано"
            self._notify_progress()
            self._notify_execution_finished()
            self._notify_plan_finished(results)
            if on_complete:
                on_complete(results)
        
        self.current_task_thread = threading.Thread(target=task_wrapper, daemon=True)
        self.current_task_thread.start()
    
    def _notify_progress(self):
        """Відправити оновлення прогресу в GUI."""
        if self.gui_callback:
            self.gui_callback('update_progress', (self.progress, self.status))
    
    def _notify_execution_started(self):
        if self.gui_callback:
            self.gui_callback('execution_started', None)
    
    def _notify_execution_finished(self):
        if self.gui_callback:
            self.gui_callback('execution_finished', None)

    def _notify_plan_started(self, plan: list):
        """Сповістити GUI про початок плану - передати перелік кроків."""
        if self.gui_callback:
            steps_info = [
                {
                    "index": idx,
                    "action": step.get("action", ""),
                    "goal": step.get("goal", "") or "",
                }
                for idx, step in enumerate(plan)
            ]
            self.gui_callback('plan_started', steps_info)

    def _notify_step_update(self, index: int, step: dict, status: str, detail: str = ""):
        """Сповістити GUI про зміну статусу конкретного кроку.

        status: pending | running | ok | error | blocked | needs_confirmation | skipped
        """
        if self.gui_callback:
            self.gui_callback('step_update', {
                "index": index,
                "action": step.get("action", ""),
                "goal": step.get("goal", "") or "",
                "status": status,
                "detail": detail,
            })

    def _notify_plan_finished(self, results: list):
        """Сповістити GUI про завершення плану (із фінальною статистикою)."""
        if self.gui_callback:
            ok = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "ok")
            err = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "error")
            blocked = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "blocked")
            confirm = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "needs_confirmation")
            self.gui_callback('plan_finished', {
                "total": len(results),
                "ok": ok,
                "error": err,
                "blocked": blocked,
                "needs_confirmation": confirm,
            })
    
    def stop(self):
        """Запросить остановку текущего выполнения."""
        self._stop_requested = True

    @property
    def stop_requested(self):
        """Чи запрошено зупинку поточного виконання."""
        return self._stop_requested
