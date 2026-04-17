"""Планувальник багатокрокових задач для асистента."""
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Set

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
            # Маркери кодових задач
            "знайди",
            "прочитай",
            "відредагуй",
            "зміни код",
            "перевір код",
            "git",
            "refactor",
            "рефактор",
        )
        return len(normalized.split()) >= 6 and any(marker in normalized for marker in markers)

    def _is_coding_task(self, task: str) -> bool:
        """Чи є задача кодовою (передбачає роботу з файлами/кодом)."""
        normalized = task.lower()
        coding_markers = (
            "код", "файл", "функцію", "функції", "клас", "модуль", "скрипт",
            "git", "refactor", "рефактор", "баг", "bug", "помилк", "test",
            "pytest", "import", ".py", ".js", ".ts", ".json", "readme",
            "знайди в", "пошук по", "прочитай файл", "відредагуй файл",
        )
        return any(m in normalized for m in coding_markers)

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

    def create_plan(self, task: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Побудувати план для задачі з врахуванням контексту."""
        available_actions = self._available_actions_description()
        is_coding = self._is_coding_task(task)

        # Додаємо контекст якщо є
        context_section = ""
        if context and context.get("artifacts_summary"):
            context_section = f"""
ДОСТУПНІ АРТЕФАКТИ ВІД ПОПЕРЕДНІХ КРОКІВ:
{context['artifacts_summary']}

Використовуй ці placeholder-и для посилання на артефакти:
- {{previous_file_path}} або {{last_file_path}} — останній створений/змінений файл
- {{last_script_path}} — останній Python скрипт
- {{last_url}} — останній відкритий URL
- {{last_output}} — вивід останнього скрипта
- {{last_program}} — остання відкрита програма
"""

        # Додаємо coding-agent цикл для кодових задач
        coding_section = ""
        if is_coding:
            coding_section = """
ЦЕ КОДОВА ЗАДАЧА. ДОТРИМУЙСЯ ЦИКЛУ:
1. **Пошук** - `search_in_code` або `list_directory` щоб знайти релевантні файли
2. **Читання** - `read_code_file` перед будь-яким редагуванням
3. **Редагування** - `edit_file` (з бекапом) або `create_file`
4. **Верифікація** - `execute_python` або `debug_python_code` щоб перевірити результат
5. **Git** - `git_status` або `git_diff` після змін (опціонально)

ВАЖЛИВО: завжди читай файл (`read_code_file`) перед тим як його редагувати.
"""

        prompt = f"""
Ти planner локального асистента. Розбий задачу на безпечні послідовні кроки.

ВИКОРИСТОВУЙ ЛИШЕ ЦІ ФУНКЦІЇ:
{available_actions}
{context_section}{coding_section}
ПРАВИЛА:
- Поверни ТІЛЬКИ JSON-масив.
- Кожен елемент має формат:
  {{"action":"назва_функції","args":{{...}},"goal":"що має статись","validation":"як зрозуміти що крок успішний"}}
- Використовуй placeholder-и для посилання на файли з попередніх кроків (див. вище).
- Не вигадуй функцій, яких немає у списку.
- Не додавай небезпечні або зайві дії.

Задача користувача:
{task}
"""
        response = self._ask_llm(prompt)
        print(f"{Fore.YELLOW}📋 [Planner{'/coding' if is_coding else ''}] Відповідь LLM:\n{response}{Fore.RESET}")

        parsed = self._extract_json(response)
        plan = self.normalize_plan(parsed)
        return plan

    def validate_plan_safety(self, plan: List[Dict[str, Any]], task: str) -> Tuple[bool, str]:
        """Перевірити план на безпеку з використанням централізованих політик."""
        from .core_tool_runtime import check_dangerous_content, check_ambiguous_content

        if not plan:
            return False, "План порожній або не згенерувався."

        if not hasattr(self.assistant, "registry") or not self.assistant.registry:
            return False, "Недоступний реєстр функцій."

        available = set(self.assistant.registry.functions.keys())
        ambiguous_warnings = []

        for idx, step in enumerate(plan, 1):
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

            # Централізована перевірка небезпечного контенту
            raw_text = json.dumps(step, ensure_ascii=False)
            dangerous = check_dangerous_content(raw_text)
            if dangerous:
                return False, f"У кроці #{idx} '{action}' знайдено небезпечний патерн: '{dangerous}'"

            # М'яке попередження для двозначних дій
            ambiguous = check_ambiguous_content(raw_text)
            if ambiguous:
                ambiguous_warnings.append(f"крок #{idx} '{action}' (патерн: '{ambiguous}')")
                # Примусово підвищуємо рівень підтвердження
                step["requires_confirmation"] = True
                step["ambiguous_pattern"] = ambiguous

        summary = f"План із {len(plan)} кроків пройшов перевірку."
        if ambiguous_warnings:
            summary += f" ⚠️ Двозначні дії потребують підтвердження: {', '.join(ambiguous_warnings)}"

        return True, summary

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

    # Placeholder-и які підтримуються для підстановки з контексту
    _PLACEHOLDER_PATTERNS: Set[str] = {
        "{{previous_file_path}}", "{previous_file_path}",
        "{{last_file_path}}", "{last_file_path}",
        "{{last_script_path}}", "{last_script_path}",
        "{{last_url}}", "{last_url}",
        "{{last_output}}", "{last_output}",
        "{{last_program}}", "{last_program}",
    }

    def _resolve_placeholders(self, value: Any, context: Dict[str, Any]) -> Any:
        """Замінити placeholder-и в значенні на реальні дані з контексту."""
        if not isinstance(value, str):
            return value

        value = value.strip()

        # Мапінг placeholder -> ключ в контексті
        placeholder_map = {
            "{{previous_file_path}}": "last_file_path",
            "{previous_file_path}": "last_file_path",
            "{{last_file_path}}": "last_file_path",
            "{last_file_path}": "last_file_path",
            "{{last_script_path}}": "last_script_path",
            "{last_script_path}": "last_script_path",
            "{{last_url}}": "last_url",
            "{last_url}": "last_url",
            "{{last_output}}": "last_output",
            "{last_output}": "last_output",
            "{{last_program}}": "last_program",
            "{last_program}": "last_program",
            "{{last_voice_text}}": "last_voice_text",
            "{last_voice_text}": "last_voice_text",
        }

        for placeholder, context_key in placeholder_map.items():
            if placeholder in value:
                context_value = context.get(context_key)
                if context_value:
                    value = value.replace(placeholder, str(context_value))

        return value

    def prepare_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Підготувати крок до виконання з урахуванням контексту та артефактів."""
        action = step.get("action")
        args = dict(step.get("args", {}))
        prepared = dict(step)

        # --- Заміна placeholder-ів в аргументах ---
        for key, value in list(args.items()):
            args[key] = self._resolve_placeholders(value, context)

        # --- Автоматичні підстановки для специфічних дій ---
        # Якщо виконуємо Python і є останній файл .py - використовуємо його як script_name
        if action in ("execute_python", "execute_python_code") and context.get("last_file_path", "").endswith(".py"):
            args.setdefault("script_name", os.path.basename(context["last_file_path"]))

        # Якщо відкриваємо програму і є останній файл - автоматично додаємо file_path
        if action == "open_program" and context.get("last_file_path"):
            args.setdefault("file_path", context["last_file_path"])

        # Якщо редагуємо файл і немає filepath але є last_file_path
        if action == "edit_file" and not args.get("filepath") and context.get("last_file_path"):
            args.setdefault("filepath", context["last_file_path"])

        prepared["args"] = args

        # --- Додаємо контекст/артефакти для передачі в LLM при repair/replan ---
        if context.get("artifacts_summary"):
            prepared["_context_hint"] = context["artifacts_summary"]

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
        """Оновити контекст після виконання кроку зі збереженням артефактів."""
        action = step.get("action")
        args = step.get("args", {})
        tool_meta = None
        if hasattr(self.assistant, "registry") and self.assistant.registry:
            tool_meta = getattr(self.assistant.registry, "last_tool_result", None)

        tool_data = tool_meta.get("data", {}) if tool_meta else {}
        step_artifacts = {
            "action": action,
            "args": args,
            "result_text": result,
            "tool_data": tool_data,
            "timestamp": time.time(),
        }

        # --- Файлові операції ---
        if action in ("create_file", "edit_file"):
            file_path = tool_data.get("file_path") or args.get("filepath") or args.get("filename")
            if file_path and not os.path.isabs(file_path) and action == "edit_file":
                file_path = os.path.join(os.path.expanduser("~"), "Desktop", file_path)
            if file_path:
                context["last_file_path"] = file_path
                context.setdefault("created_files", []).append(file_path)
                step_artifacts["file_path"] = file_path

        # --- Відкриття файлів через програми ---
        if action == "open_program":
            file_path = args.get("file_path") or tool_data.get("file_path")
            program = tool_data.get("program_name") or args.get("program_name")
            if file_path:
                context["last_file_path"] = file_path
                step_artifacts["file_path"] = file_path
            if program:
                context["last_program"] = program
                step_artifacts["program"] = program

        # --- Виконання Python ---
        if action in ("execute_python", "execute_python_code", "execute_python_file"):
            script_path = tool_data.get("script_path") or tool_data.get("log_path")
            output = tool_data.get("output", "")
            if script_path:
                context["last_script_path"] = script_path
                step_artifacts["script_path"] = script_path
            if output:
                context["last_output"] = output
                step_artifacts["output"] = output
            context["last_execution_time"] = tool_data.get("execution_time")

        # --- Виправлення коду ---
        if action == "debug_python_code":
            fixed_code = tool_data.get("fixed_code")
            if fixed_code:
                context["last_fixed_code"] = fixed_code
                step_artifacts["fixed_code"] = fixed_code

        # --- Браузер ---
        if action == "open_browser":
            url = tool_data.get("url") or args.get("url")
            if url:
                context["last_url"] = url
                step_artifacts["url"] = url

        # --- Голосовий ввід ---
        if action == "voice_input":
            text = tool_data.get("text")
            if text:
                context["last_voice_text"] = text
                step_artifacts["voice_text"] = text

        # --- Скрипти в пісочниці ---
        if action == "list_sandbox_scripts":
            scripts = tool_data.get("scripts", [])
            if scripts:
                context["last_scripts_list"] = scripts
                step_artifacts["scripts"] = scripts

        # --- Архітектор (створення навичок) ---
        if action == "create_skill":
            filename = tool_data.get("filename")
            skill_path = tool_data.get("path")
            if filename:
                context["last_created_skill"] = filename
                step_artifacts["skill_file"] = filename
                step_artifacts["skill_path"] = skill_path

        # Зберегти артефакти кроку
        context.setdefault("step_artifacts", []).append(step_artifacts)

        # Оновити основні змінні
        context["last_action"] = action
        context["last_result"] = result
        context["last_tool_data"] = tool_data

        # Зберегти всі змінні для передачі між кроками
        context["artifacts_summary"] = self._build_artifacts_summary(context)

        return context

    def _build_artifacts_summary(self, context: Dict[str, Any]) -> str:
        """Побудувати текстове summary артефактів для передачі в LLM."""
        parts = []

        if context.get("last_file_path"):
            parts.append(f"Останній файл: {context['last_file_path']}")
        if context.get("last_program"):
            parts.append(f"Остання програма: {context['last_program']}")
        if context.get("last_url"):
            parts.append(f"Останній URL: {context['last_url']}")
        if context.get("last_output"):
            output = context["last_output"]
            preview = output[:200] + "..." if len(output) > 200 else output
            parts.append(f"Останній вивід: {preview}")
        if context.get("created_files"):
            parts.append(f"Створені файли: {', '.join(context['created_files'])}")

        return "\n".join(parts) if parts else "Немає артефактів"

    def propose_repair_step(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Спробувати отримати один repair-крок після невдалого виконання."""
        available_actions = self._available_actions_description()
        artifacts = context.get("artifacts_summary", "Немає артефактів")

        prompt = f"""
Ти repair-planner. Поточна задача: {task}

Провалився крок:
{json.dumps(failed_step, ensure_ascii=False, indent=2)}

Результат/помилка:
{result}

ДОСТУПНІ АРТЕФАКТИ (використовуй placeholder-и типу {{{{last_file_path}}}}):
{artifacts}

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
        artifacts = context.get("artifacts_summary", "Немає артефактів")

        prompt = f"""
Ти replanner локального асистента.

Початкова задача:
{task}

Невдалий крок:
{json.dumps(failed_step, ensure_ascii=False, indent=2)}

Результат невдачі:
{result}

ДОСТУПНІ АРТЕФАКТИ (використовуй placeholder-и типу {{{{last_file_path}}}}):
{artifacts}

Кількість виконаних кроків: {context.get('completed_steps', 0)}
Кількість спроб repair: {context.get('repair_attempts', 0)}
Кількість replan: {context.get('replan_attempts', 0)}

Поточний хвіст плану (якщо є):
{json.dumps(remaining_steps, ensure_ascii=False, indent=2)}

Доступні функції:
{available_actions}

ПРАВИЛА:
- Поверни ТІЛЬКИ JSON-масив нового хвоста плану.
- Використовуй лише доступні функції та placeholder-и для артефактів.
- Не повторюй безглуздо крок, який щойно провалився, якщо немає нових аргументів.
- Якщо задачу безпечно продовжити неможливо, поверни [].
"""
        response = self._ask_llm(prompt)
        parsed = self._extract_json(response)
        return self.normalize_plan(parsed)

    def build_execution_context(self, task: str, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Створити початковий контекст виконання з усіма необхідними полями."""
        return {
            # Основна інформація
            "task": task,
            "plan_length": len(plan),
            "execution_start_time": time.time(),

            # Файлові артефакти
            "last_file_path": None,
            "created_files": [],
            "edited_files": [],

            # Програмні артефакти
            "last_program": None,
            "last_script_path": None,

            # Вивід та результати
            "last_result": None,
            "last_output": None,
            "last_execution_time": None,

            # Специфічні артефакти
            "last_url": None,
            "last_voice_text": None,
            "last_fixed_code": None,
            "last_scripts_list": [],
            "last_created_skill": None,

            # Метадані виконання
            "last_action": None,
            "last_tool_data": {},
            "step_artifacts": [],
            "artifacts_summary": "",

            # Лічильники
            "repair_attempts": 0,
            "replan_attempts": 0,
            "completed_steps": 0,
        }
