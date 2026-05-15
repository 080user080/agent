# functions/core_memory.py
"""Менеджер пам'яті для агента: довготривала (файл) + сесійна + задачна."""
import json
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional


class SessionMemory:
    """Пам'ять поточної сесії (в RAM, не зберігається на диск).

    Тримає тимчасові дані: активні файли, поточний контекст, лічильники.
    """

    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.started_at = datetime.now().isoformat()
        self.current_task: Optional[str] = None
        self.active_files: List[str] = []
        self.counters: Dict[str, int] = {"commands": 0, "plans": 0, "errors": 0}
        self.ephemeral: Dict[str, Any] = {}  # будь-які тимчасові дані

    def track_command(self) -> None:
        self.counters["commands"] += 1

    def track_plan(self) -> None:
        self.counters["plans"] += 1

    def track_error(self) -> None:
        self.counters["errors"] += 1

    def set_current_task(self, task: str) -> None:
        self.current_task = task

    def add_active_file(self, path: str) -> None:
        if path and path not in self.active_files:
            self.active_files.append(path)

    def snapshot(self) -> Dict[str, Any]:
        """Поточний стан сесії."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "current_task": self.current_task,
            "active_files": list(self.active_files),
            "counters": dict(self.counters),
        }


class TaskMemory:
    """Пам'ять однієї задачі: план, кроки, артефакти, проміжні результати."""

    def __init__(self, task_id: str, task_text: str):
        self.task_id = task_id
        self.task_text = task_text
        self.started_at = datetime.now().isoformat()
        self.finished_at: Optional[str] = None
        self.plan: List[Dict[str, Any]] = []
        self.step_results: List[Dict[str, Any]] = []
        self.artifacts: Dict[str, Any] = {}
        self.status: str = "running"  # running / success / error / aborted

    def record_plan(self, plan: List[Dict[str, Any]]) -> None:
        self.plan = plan

    def record_step(self, step_result: Dict[str, Any]) -> None:
        self.step_results.append({
            **step_result,
            "recorded_at": datetime.now().isoformat(),
        })

    def set_artifact(self, key: str, value: Any) -> None:
        self.artifacts[key] = value

    def finish(self, status: str = "success") -> None:
        self.status = status
        self.finished_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_text": self.task_text,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "plan": self.plan,
            "step_results": self.step_results,
            "artifacts": self.artifacts,
        }


class MemoryManager:
    """Трирівнева пам'ять: довготривала (файл) + сесія (RAM) + задача (RAM+dump)."""

    def __init__(self, storage_path: Optional[Path] = None, llm_caller=None):
        if storage_path is None:
            storage_path = Path(__file__).parent / "agent_memory.json"
        self.storage_path = storage_path
        self.memory: Dict[str, Any] = self._load()

        # Пам'ять сесії (скидається при перезапуску)
        self.session = SessionMemory()

        # Пам'ять задач: task_id -> TaskMemory
        self.tasks: Dict[str, TaskMemory] = {}
        self.current_task_id: Optional[str] = None

        # Опціональний LLM-callable(prompt: str) -> str для summary
        self._llm_caller = llm_caller

    # --- Довготривала пам'ять ---

    def _load(self) -> Dict[str, Any]:
        """Завантажити пам'ять із файлу."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Додати нові поля якщо їх немає у старих файлах
                    data.setdefault("task_summaries", [])
                    data.setdefault("session_summaries", [])
                    return data
            except Exception:
                pass
        return {
            "last_task": None,
            "last_plan": [],
            "last_results": [],
            "variables": {},
            "file_paths": [],
            "history": [],
            "task_summaries": [],     # LLM-based summaries задач
            "session_summaries": [],  # Summary довгих сесій
        }

    def save(self) -> None:
        """Зберегти поточний стан довготривалої пам'яті."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Помилка збереження пам'яті: {e}")

    def update_task(self, task: str, plan: list, results: list) -> None:
        """Оновити інформацію про останнє виконане завдання."""
        self.memory["last_task"] = task
        self.memory["last_plan"] = plan
        self.memory["last_results"] = results
        self.memory["history"].append({
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "plan": plan,
            "results": results,
        })
        if len(self.memory["history"]) > 20:
            self.memory["history"] = self.memory["history"][-20:]
        self.save()

    def add_file_path(self, path: str) -> None:
        """Додати шлях до файлу."""
        if path not in self.memory["file_paths"]:
            self.memory["file_paths"].append(path)
            # Обмежити список
            if len(self.memory["file_paths"]) > 100:
                self.memory["file_paths"] = self.memory["file_paths"][-100:]
            self.save()

    def set_variable(self, key: str, value: Any) -> None:
        self.memory["variables"][key] = value
        self.save()

    def get_variable(self, key: str, default=None) -> Any:
        return self.memory["variables"].get(key, default)

    def get_last_files(self, extension: Optional[str] = None) -> list:
        files = self.memory["file_paths"]
        if extension:
            return [f for f in files if f.endswith(extension)]
        return files

    def clear_memory(self) -> None:
        self.memory = {
            "last_task": None,
            "last_plan": [],
            "last_results": [],
            "variables": {},
            "file_paths": [],
            "history": [],
            "task_summaries": [],
            "session_summaries": [],
        }
        self.save()

    # --- Пам'ять задачі ---

    def start_task(self, task_text: str) -> str:
        """Почати нову задачу. Повертає task_id."""
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + str(uuid.uuid4())[:6]
        self.tasks[task_id] = TaskMemory(task_id, task_text)
        self.current_task_id = task_id
        self.session.set_current_task(task_text)
        self.session.track_plan()
        return task_id

    def current_task(self) -> Optional[TaskMemory]:
        if self.current_task_id:
            return self.tasks.get(self.current_task_id)
        return None

    def record_task_plan(self, plan: List[Dict[str, Any]]) -> None:
        """Записати план у поточну задачу."""
        task = self.current_task()
        if task:
            task.record_plan(plan)

    def record_task_step(self, step_result: Dict[str, Any]) -> None:
        """Записати результат кроку у поточну задачу."""
        task = self.current_task()
        if task:
            task.record_step(step_result)

    def finish_task(self, status: str = "success") -> Optional[TaskMemory]:
        """Завершити поточну задачу. Генерує summary якщо можливо."""
        task = self.current_task()
        if not task:
            return None
        task.finish(status)

        # Генеруємо summary через LLM, якщо доступний
        summary = self._summarize_task(task)
        if summary:
            self.memory["task_summaries"].append({
                "task_id": task.task_id,
                "task_text": task.task_text,
                "status": task.status,
                "summary": summary,
                "timestamp": task.finished_at,
            })
            # Обмежити до 50 summaries
            if len(self.memory["task_summaries"]) > 50:
                self.memory["task_summaries"] = self.memory["task_summaries"][-50:]
            self.save()

        self.current_task_id = None
        return task

    # --- LLM-based summary ---

    def set_llm_caller(self, caller) -> None:
        """Встановити функцію ask_llm(prompt) -> str для генерації summary."""
        self._llm_caller = caller

    def _summarize_task(self, task: TaskMemory) -> Optional[str]:
        """Згенерувати короткий summary задачі через LLM."""
        if not self._llm_caller:
            return self._fallback_task_summary(task)

        try:
            plan_brief = [{"action": s.get("action"), "goal": s.get("goal", "")} for s in task.plan]
            steps_brief = [
                {
                    "action": r.get("action"),
                    "status": r.get("status"),
                    "validation": r.get("validation", "")[:100],
                }
                for r in task.step_results
            ]

            prompt = (
                "Коротко підсумуй виконану задачу (3-5 речень українською).\n\n"
                f"Задача: {task.task_text}\n"
                f"Статус: {task.status}\n"
                f"План: {json.dumps(plan_brief, ensure_ascii=False)}\n"
                f"Результати кроків: {json.dumps(steps_brief, ensure_ascii=False)}\n\n"
                "Відповідай лише підсумком без преамбули."
            )
            summary = self._llm_caller(prompt)
            if summary and isinstance(summary, str):
                return summary.strip()[:800]
        except Exception as e:
            print(f"⚠️ Помилка LLM-summary: {e}")

        return self._fallback_task_summary(task)

    def _fallback_task_summary(self, task: TaskMemory) -> str:
        """Просте текстове summary, якщо LLM недоступний."""
        ok_count = sum(1 for r in task.step_results if r.get("status") == "ok")
        total = len(task.step_results)
        return (
            f"Задача: '{task.task_text[:100]}'. "
            f"Статус: {task.status}. Кроків: {total}, успішних: {ok_count}."
        )

    def summarize_conversation(self, messages: List[Dict[str, str]], max_messages: int = 5) -> str:
        """Створити summary перших N повідомлень через LLM."""
        if not messages:
            return ""

        to_summarize = messages[:max_messages]
        if not self._llm_caller:
            return f"[Попередня розмова: {len(to_summarize)} повідомлень]"

        try:
            dialogue = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')[:300]}" for m in to_summarize
            )
            prompt = (
                "Стисни цей діалог у 2-3 речення українською. "
                "Зберігай факти, імена файлів, команди.\n\n"
                f"{dialogue}\n\n"
                "Відповідай лише підсумком."
            )
            summary = self._llm_caller(prompt)
            if summary and isinstance(summary, str):
                return f"[Summary: {summary.strip()[:400]}]"
        except Exception as e:
            print(f"⚠️ Помилка LLM summary діалогу: {e}")

        return f"[Попередня розмова: {len(to_summarize)} повідомлень]"

    def get_task_summaries(self, count: int = 10) -> List[Dict[str, Any]]:
        """Отримати останні summaries задач."""
        return self.memory.get("task_summaries", [])[-count:]

    def get_session_info(self) -> Dict[str, Any]:
        """Інформація про поточну сесію."""
        return self.session.snapshot()