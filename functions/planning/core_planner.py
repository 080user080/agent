"""Планувальник багатокрокових задач для асистента (Фасад)."""
from __future__ import annotations

import json
import os
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple, Set

from colorama import Fore
from ..runtime.core_tool_runtime import check_dangerous_content, check_ambiguous_content
from .planner_prompt_builder import PlannerPromptBuilder
from .planner_validator import PlannerValidator, ValidationResult
from .planner_repair import StepRepairer, RepairLoop

logger = logging.getLogger("core_planner")


class Planner:
    """Фасад планування: агрегує PromptBuilder, Validator та Repairer.

    Конструктор приймає зовнішній об'єкт Assistant та опційні екземпляри
    компонентів. Якщо компоненти не передано — створюються всередині
    з безпечною ініціалізацією. Усі методи — лінійна диспетчеризація
    до агрегованих інструментів.
    """

    # Делегування констант до PlannerPromptBuilder для зворотної сумісності
    _PLACEHOLDER_PATTERNS: Set[str] = PlannerPromptBuilder.PLACEHOLDER_PATTERNS

    def __init__(
        self,
        assistant,
        prompt_builder: Optional[PlannerPromptBuilder] = None,
        validator: Optional[PlannerValidator] = None,
        repairer: Optional[StepRepairer] = None,
        repair_loop: Optional[RepairLoop] = None,
    ):
        """Ініціалізація фасаду планувальника.

        Args:
            assistant: Екземпляр AssistantCore / VoiceAssistant.
            prompt_builder: Опційний PlannerPromptBuilder.
            validator: Опційний PlannerValidator.
            repairer: Опційний StepRepairer.
            repair_loop: Опційний RepairLoop (якщо не задано — створюється з repairer).
        """
        self.assistant = assistant
        self._prompt_builder: PlannerPromptBuilder
        self._validator: PlannerValidator
        self._repair_loop: RepairLoop

        # Безпечне зв'язування компонентів
        try:
            self._prompt_builder = prompt_builder or PlannerPromptBuilder()
            self._validator = validator or PlannerValidator()

            if repair_loop is not None:
                self._repair_loop = repair_loop
            elif repairer is not None:
                self._repair_loop = RepairLoop(
                    repairer=repairer,
                    ask_llm_fn=self._ask_llm,
                    available_actions_fn=self._available_actions_description,
                )
            else:
                _repairer = StepRepairer(
                    ask_llm_fn=self._ask_llm,
                    available_actions_fn=self._available_actions_description,
                )
                self._repair_loop = RepairLoop(
                    repairer=_repairer,
                    ask_llm_fn=self._ask_llm,
                    available_actions_fn=self._available_actions_description,
                )

            logger.info(f"{Fore.GREEN}✅ Planner: компоненти ініціалізовано{Fore.RESET}")
        except Exception as exc:
            logger.error(f"{Fore.RED}❌ Planner: помилка ініціалізації компонентів: {exc}{Fore.RESET}")
            raise

    @property
    def validator(self) -> PlannerValidator:
        """Доступ до валідатора (зворотна сумісність)."""
        return self._validator

    @property
    def repair_loop(self) -> RepairLoop:
        """Доступ до repair-циклу (зворотна сумісність)."""
        return self._repair_loop

    @property
    def prompt_builder(self) -> PlannerPromptBuilder:
        """Доступ до prompt builder (зворотна сумісність)."""
        return self._prompt_builder

    def _ask_llm(self, prompt: str) -> str:
        """Спрощений доступ до LLM через асистента."""
        if hasattr(self.assistant, "ask_llm"):
            return self.assistant.ask_llm(prompt)
        return ""

    def _detect_llm_error(self, response: str, task: str) -> bool:
        """Детектувати помилки моделі або з'єднання.

        Args:
            response: Відповідь від LLM
            task: Оригінальна задача

        Returns:
            True якщо це помилка (помилка вже залогована)
        """
        # Делегуємо до PlannerValidator (зворотна сумісність)
        return PlannerValidator.detect_llm_error(response, task)

    def should_plan(self, task: str) -> bool:
        """Чи схожа задача на багатокрокову."""
        # 🔥 Спеціальна обробка voice_input (Qt модифікує текст "voice_input 5" -> "_ 5")
        normalized = task.lower().strip()
        if normalized.startswith("_") and re.match(r'^_\s*\d+$', normalized):
            print(f"{Fore.CYAN}🎤 [Planner should_plan] Виявлено модифіковану voice_input команду: '{task}'")
            return True
        return PlannerPromptBuilder.should_plan_check(task)

    def _is_coding_task(self, task: str) -> bool:
        """Чи є задача кодовою (передбачає роботу з файлами/кодом)."""
        return PlannerPromptBuilder.is_coding_task(task)

    def _available_actions_description(self) -> str:
        """Зібрати доступні функції з реєстру (скорочений список для планера)."""
        registry = getattr(self.assistant, "registry", None)
        return PlannerPromptBuilder.available_actions_description(registry)

    def _extract_json(self, text: str) -> Optional[Any]:
        """Витягнути JSON-масив або об'єкт з відповіді LLM.

        Підтримує:
        - Прибирання токенів `<|channel|>`, `<|message|>` тощо.
        - Код у блоках ```json ... ```.
        - Список об'єктів без зовнішніх `[]`: `{...}, {...}` → `[{...}, {...}]`.

        Делегує до ``PlannerValidator.extract_json`` (зворотна сумісність).
        """
        result = PlannerValidator.extract_json(text)
        return result.data

    def normalize_plan(self, raw_plan: Any) -> List[Dict[str, Any]]:
        """Нормалізувати план до списку кроків.

        Делегує до ``PlannerValidator.normalize_plan`` (зворотна сумісність).
        """
        return PlannerValidator.normalize_plan(raw_plan)

    def _recent_history_section(self, limit: int = 3) -> str:
        """Взяти останні N повідомлень з діалогу для контексту planner-а."""
        history = getattr(self.assistant, "conversation_history", None) or []
        return PlannerPromptBuilder.recent_history_section(history, limit)

    def create_plan(self, task: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Побудувати план для задачі з врахуванням контексту."""
        # 🔥 Спеціальна обробка voice_input (Qt модифікує текст "voice_input 5" -> "_ 5")
        task_lower = task.lower().strip()
        if task_lower.startswith("_") and re.match(r'^_\s*\d+$', task_lower):
            # Якщо текст модифікований Qt (наприклад "_ 5")
            # Повертаємо пряме виклик voice_input
            print(f"{Fore.CYAN}🎤 [Planner] Виявлено модифіковану voice_input команду: '{task}'")
            # Витягуємо duration з тексту
            duration_match = re.search(r'\d+', task)
            duration = int(duration_match.group()) if duration_match else 10
            return [{"action": "voice_input", "args": {"duration": duration}}]

        available_actions = self._available_actions_description()
        is_coding = self._is_coding_task(task)
        history_section = self._recent_history_section()

        # Промпт через PlannerPromptBuilder
        prompt = PlannerPromptBuilder.build_initial_plan_prompt(
            task=task,
            available_actions=available_actions,
            history_section=history_section,
            context=context,
            is_coding=is_coding,
        )

        # Спроба 1: звичайний промпт
        response = self._ask_llm(prompt)
        print(f"{Fore.YELLOW}📋 [Planner{'/coding' if is_coding else ''}] Відповідь LLM:\n{response[:200]}...{Fore.RESET}")

        # Перевірка на помилки з'єднання/моделі
        if self._detect_llm_error(response, task):
            # Помилка вже залогована, повертаємо None для fallback на прямий LLM
            return None

        parsed = self._extract_json(response)
        plan = self.normalize_plan(parsed)

        # Спроба 2: якщо не вдалося — ще раз з жорсткішим промптом
        if not plan:
            print(f"{Fore.YELLOW}⚠️ Планер: перша спроба не вдалася, повторюю...{Fore.RESET}")
            retry_prompt = PlannerPromptBuilder.build_retry_plan_prompt(
                task=task,
                available_actions=available_actions,
            )
            response2 = self._ask_llm(retry_prompt)
            print(f"{Fore.YELLOW}📋 [Planner retry] Відповідь:\n{response2[:200]}...{Fore.RESET}")
            parsed2 = self._extract_json(response2)
            plan = self.normalize_plan(parsed2)

        return plan

    def validate_plan_safety(self, plan: List[Dict[str, Any]], task: str) -> Tuple[bool, str]:
        """Перевірити план на безпеку з використанням централізованих політик."""
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

            # Заборона time.sleep в execute_python
            if action in ("execute_python", "execute_python_code"):
                code = args.get("code", "")
                if "time.sleep" in code or "import time" in code:
                    return False, f"У кроці #{idx} '{action}' знайдено time.sleep - використовуйте keyboard_type/keyboard_press для взаємодії з вікнами"

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

    def _resolve_placeholders(self, value: Any, context: Dict[str, Any]) -> Any:
        """Замінити placeholder-и в значенні на реальні дані з контексту."""
        return PlannerPromptBuilder.resolve_placeholders(value, context)

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

        if action == "list_directory":
            # list_directory успішний якщо результат не починається з помилки
            return not result.startswith("❌"), result

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
        return PlannerPromptBuilder.build_artifacts_summary(context)

    def propose_repair_step(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Спробувати отримати один repair-крок після невдалого виконання.

        Делегує до ``planner_repair.StepRepairer`` (зворотна сумісність).
        """
        return self.repair_loop.repairer.repair(task, failed_step, result, context)

    def propose_replan(
        self,
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
        remaining_steps: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Перебудувати решту плану після проваленого repair-кроку.

        Делегує до ``planner_repair.RepairLoop.try_replan`` (зворотна сумісність).
        """
        return self.repair_loop.try_replan(task, failed_step, result, context, remaining_steps)

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
