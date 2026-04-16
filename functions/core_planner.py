"""Планувальник багатокрокових задач для асистента."""
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from colorama import Fore


class Planner:
    """Планує, перевіряє, виконує та переплановує багатокрокові задачі."""

    def __init__(self, assistant):
        self.assistant = assistant

    def _ask_llm(self, prompt: str) -> str:
        """Спрощений доступ до LLM через асистента."""
        if hasattr(self.assistant, "ask_llm"):
            return self.assistant.ask_llm(prompt)
        return ""

    def should_plan(self, task: str) -> bool:
        """Чи схожа задача на багатокрокову."""
        normalized = task.lower().strip()
        markers = (
            "план",
            "потім",
            "після цього",
            "спочатку",
            "далі",
            "зроби файл",
            "створи файл",
            "відкрий",
            "виконай",
            "виправ",
        )
        return len(normalized.split()) >= 6 and any(marker in normalized for marker in markers)

    def _available_actions_description(self) -> str:
        """Зібрати доступні функції з реєстру."""
        if not hasattr(self.assistant, "registry") or not self.assistant.registry:
            return ""

        lines = []
        for name, func_info in sorted(self.assistant.registry.functions.items()):
            description = func_info.get("description", "")
            parameters = func_info.get("parameters", {})
            params_text = ", ".join(parameters.keys()) if parameters else "без параметрів"
            risk = self.assistant.registry.get_tool_risk(name)
            lines.append(f"- {name}({params_text}) — {description} [risk={risk}]")
        return "\n".join(lines)

    def _extract_json(self, text: str) -> Optional[Any]:
        """Витягнути JSON-масив або об'єкт з відповіді LLM."""
        if not text:
            return None

        candidates: List[str] = []
        for start_char, end_char in (("[", "]"), ("{", "}")):
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end > start:
                candidates.append(text[start : end + 1])

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception:
                continue
        return None

    def normalize_plan(self, raw_plan: Any) -> List[Dict[str, Any]]:
        """Нормалізувати план до списку кроків."""
        if not isinstance(raw_plan, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for step in raw_plan:
            if not isinstance(step, dict):
                continue

            action = str(step.get("action", "")).strip()
            args = step.get("args", {})
            if not action or not isinstance(args, dict):
                continue

            normalized.append(
                {
                    "action": action,
                    "args": args,
                    "goal": str(step.get("goal", "")).strip(),
                    "validation": str(step.get("validation", "")).strip(),
                }
            )
        return normalized

    def create_plan(self, task: str) -> List[Dict[str, Any]]:
        """Побудувати план для задачі."""
        available_actions = self._available_actions_description()
        prompt = f"""
Ти planner локального асистента. Розбий задачу на безпечні послідовні кроки.

ВИКОРИСТОВУЙ ЛИШЕ ЦІ ФУНКЦІЇ:
{available_actions}

ПРАВИЛА:
- Поверни ТІЛЬКИ JSON-масив.
- Кожен елемент має формат:
  {{"action":"назва_функції","args":{{...}},"goal":"що має статись","validation":"як зрозуміти що крок успішний"}}
- Якщо треба використати шлях попереднього файлу, передай:
  "filepath": "{{previous_file_path}}"
  або "file_path": "{{previous_file_path}}"
- Не вигадуй функцій, яких немає у списку.
- Не додавай небезпечні або зайві дії.

Задача користувача:
{task}
"""
        response = self._ask_llm(prompt)
        print(f"{Fore.YELLOW}📋 [Planner] Відповідь LLM:\n{response}{Fore.RESET}")

        parsed = self._extract_json(response)
        plan = self.normalize_plan(parsed)
        return plan

    def validate_plan_safety(self, plan: List[Dict[str, Any]], task: str) -> Tuple[bool, str]:
        """Перевірити план на базову безпеку перед виконанням."""
        if not plan:
            return False, "План порожній або не згенерувався."

        if not hasattr(self.assistant, "registry") or not self.assistant.registry:
            return False, "Недоступний реєстр функцій."

        available = set(self.assistant.registry.functions.keys())

        for step in plan:
            action = step.get("action", "")
            if action not in available:
                return False, f"У плані є невідома функція: {action}"

            args = step.get("args", {})
            if not isinstance(args, dict):
                return False, f"Некоректні параметри у кроці {action}"

            risk = self.assistant.registry.get_tool_risk(action)
            step["risk"] = risk

            if risk == "confirm_required":
                step["requires_confirmation"] = True

            if risk == "blocked":
                return False, f"Функція {action} заблокована політикою runtime."

            raw_text = json.dumps(step, ensure_ascii=False).lower()
            blocked_patterns = [
                "rm -rf",
                "format c:",
                "del /f /s /q",
                "rmdir /s",
                "powershell -enc",
            ]
            if any(pattern in raw_text for pattern in blocked_patterns):
                return False, f"У плані виявлено потенційно небезпечний патерн у кроці {action}."

        return True, f"План із {len(plan)} кроків пройшов базову перевірку."

    def _extract_file_path(self, result_text: str) -> Optional[str]:
        """Спробувати витягти шлях або назву створеного файлу."""
        if not result_text:
            return None

        match = re.search(r"✅ Файл створено:\s*([^\n]+?)(?:\s+на робочому столі)?$", result_text.strip(), re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            if not os.path.isabs(path):
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                path = os.path.join(desktop, path)
            return path
        return None

    def prepare_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Підготувати крок до виконання з урахуванням контексту."""
        action = step.get("action")
        args = dict(step.get("args", {}))
        prepared = dict(step)

        for placeholder_key in ("filepath", "file_path"):
            if placeholder_key in args and str(args[placeholder_key]).strip() in ("{{previous_file_path}}", "{previous_file_path}"):
                if context.get("last_file_path"):
                    args[placeholder_key] = context["last_file_path"]

        if action in {"execute_python", "execute_python_code"} and context.get("last_file_path", "").endswith(".py"):
            args.setdefault("script_name", os.path.basename(context["last_file_path"]))

        prepared["args"] = args
        return prepared

    def _validate_step(self, action: str, args: Dict[str, Any], result: str, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Перевірити, чи крок відпрацював успішно."""
        tool_meta = None
        if hasattr(self.assistant, "registry") and self.assistant.registry:
            tool_meta = getattr(self.assistant.registry, "last_tool_result", None)

        if tool_meta and tool_meta.get("action") == action:
            if tool_meta.get("ok"):
                return True, tool_meta.get("message", "Крок успішний.")
            if tool_meta.get("needs_confirmation"):
                return False, tool_meta.get("error") or "Крок потребує підтвердження користувача."
            return False, tool_meta.get("error") or tool_meta.get("message", "Крок завершився помилкою.")

        if not isinstance(result, str):
            return False, "Результат кроку не є текстом."

        if result.startswith("❌") or "помилка" in result.lower():
            return False, result

        if action == "create_file":
            file_path = self._extract_file_path(result)
            if file_path and os.path.exists(file_path):
                return True, "Файл створено."
            return False, "Файл не підтверджено на диску."

        if action == "edit_file":
            filepath = args.get("filepath")
            if filepath and not os.path.isabs(filepath):
                filepath = os.path.join(os.path.expanduser("~"), "Desktop", filepath)
            if filepath and os.path.exists(filepath):
                return True, "Файл відредаговано."
            return "✅" in result, "Результат редагування не підтверджено."

        if action in {"execute_python", "execute_python_code", "execute_python_file", "debug_python_code"}:
            return True, "Python-крок завершився без явної помилки."

        if action == "open_program":
            return ("✅" in result or "Відкрив" in result or "Відкрито" in result), result

        if action == "close_program":
            return ("успішно" in result.lower() or "закрита" in result.lower()), result

        if action == "confirm_action":
            return ('"status": "confirmed"' in result or "confirmed" in result.lower() or "cancelled" in result.lower()), result

        return True, "Крок не потребує додаткової перевірки."

    def update_context_from_result(self, step: Dict[str, Any], result: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Оновити контекст після виконання кроку."""
        action = step.get("action")
        args = step.get("args", {})
        tool_meta = None
        if hasattr(self.assistant, "registry") and self.assistant.registry:
            tool_meta = getattr(self.assistant.registry, "last_tool_result", None)

        if action == "create_file":
            file_path = None
            if tool_meta and tool_meta.get("data"):
                file_path = tool_meta["data"].get("file_path")
            if not file_path:
                file_path = self._extract_file_path(result)
            if file_path:
                context["last_file_path"] = file_path
                context.setdefault("created_files", []).append(file_path)

        if action == "edit_file":
            filepath = None
            if tool_meta and tool_meta.get("data"):
                filepath = tool_meta["data"].get("file_path")
            if not filepath:
                filepath = args.get("filepath")
            if filepath:
                if not os.path.isabs(filepath):
                    filepath = os.path.join(os.path.expanduser("~"), "Desktop", filepath)
                context["last_file_path"] = filepath

        if action == "open_program" and args.get("file_path"):
            context["last_file_path"] = args["file_path"]

        context["last_action"] = action
        context["last_result"] = result
        if tool_meta:
            context["last_tool_data"] = tool_meta.get("data", {})
        return context

    def propose_repair_step(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Спробувати отримати один repair-крок після невдалого виконання."""
        available_actions = self._available_actions_description()
        prompt = f"""
Ти repair-planner. Поточна задача: {task}

Провалився крок:
{json.dumps(failed_step, ensure_ascii=False, indent=2)}

Результат/помилка:
{result}

Контекст:
{json.dumps(context, ensure_ascii=False, indent=2)}

Доступні функції:
{available_actions}

Поверни ТІЛЬКИ JSON-об'єкт одного альтернативного кроку у форматі:
{{"action":"назва_функції","args":{{...}},"goal":"...","validation":"..."}}

Якщо безпечного repair-кроку немає, поверни:
{{"action":"abort","args":{{}},"goal":"stop","validation":"stop"}}
"""
        response = self._ask_llm(prompt)
        parsed = self._extract_json(response)
        if not isinstance(parsed, dict):
            return None

        action = str(parsed.get("action", "")).strip()
        args = parsed.get("args", {})
        if not action or not isinstance(args, dict):
            return None
        if action == "abort":
            return None
        return {
            "action": action,
            "args": args,
            "goal": str(parsed.get("goal", "")).strip(),
            "validation": str(parsed.get("validation", "")).strip(),
            "is_repair": True,
        }

    def propose_replan(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
        remaining_steps: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Перебудувати решту плану після проваленого repair-кроку."""
        available_actions = self._available_actions_description()
        prompt = f"""
Ти replanner локального асистента.

Початкова задача:
{task}

Невдалий крок:
{json.dumps(failed_step, ensure_ascii=False, indent=2)}

Результат невдачі:
{result}

Поточний контекст:
{json.dumps(context, ensure_ascii=False, indent=2)}

Поточний хвіст плану:
{json.dumps(remaining_steps, ensure_ascii=False, indent=2)}

Доступні функції:
{available_actions}

ПРАВИЛА:
- Поверни ТІЛЬКИ JSON-масив нового хвоста плану.
- Використовуй лише доступні функції.
- Не повторюй безглуздо крок, який щойно провалився, якщо немає нових аргументів.
- Якщо задачу безпечно продовжити неможливо, поверни [].
"""
        response = self._ask_llm(prompt)
        parsed = self._extract_json(response)
        return self.normalize_plan(parsed)

    def build_execution_context(self, task: str, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Створити початковий контекст виконання."""
        return {
            "task": task,
            "plan_length": len(plan),
            "last_file_path": None,
            "last_action": None,
            "last_result": None,
            "created_files": [],
            "repair_attempts": 0,
            "replan_attempts": 0,
        }
