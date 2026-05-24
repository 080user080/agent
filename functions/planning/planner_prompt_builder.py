"""Побудова промптів та статичних шаблонів для планувальника.

Винесено з core_planner.py для ізоляції логіки формування текстових
інструкцій, JSON-схем та контекстних повідомлень.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Set


class PlannerPromptBuilder:
    """Формує текстові промпти та серіалізує контекст для планувальника.

    Усі методи є статичними або отримують дані через параметри — без
    прямої залежності від `Planner` або `assistant`.
    """

    # Placeholder-и які підтримуються для підстановки з контексту
    PLACEHOLDER_PATTERNS: Set[str] = {
        "{{previous_file_path}}", "{previous_file_path}",
        "{{last_file_path}}", "{last_file_path}",
        "{{last_script_path}}", "{last_script_path}",
        "{{last_url}}", "{last_url}",
        "{{last_output}}", "{last_output}",
        "{{last_program}}", "{last_program}",
        "{{last_voice_text}}", "{last_voice_text}",
    }

    # Мапінг placeholder → ключ контексту
    _PLACEHOLDER_MAP = {
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

    # ─── Маркери задач ──────────────────────────────────────────────

    _CODING_MARKERS = (
        "код", "файл", "функцію", "функції", "клас", "модуль", "скрипт",
        "git", "refactor", "рефактор", "баг", "bug", "помилк", "test",
        "pytest", "import", ".py", ".js", ".ts", ".json", "readme",
        "знайди в", "пошук по", "прочитай файл", "відредагуй файл",
    )

    _PLAN_MARKERS = (
        "план", "потім", "після цього", "спочатку", "далі",
        "зроби файл", "створи файл", "відкрий", "виконай", "виправ",
        "знайди", "прочитай", "відредагуй", "зміни код", "перевір код",
        "проаналізуй", "аналізуй", "аналіз",
        "git", "refactor", "рефактор",
        "контролювати", "моніторинг", "слідкуй", "спостерігай",
        "дивитися", "відповіді", "задавати питання", "рефакторинг",
    )

    # Пріоритетні функції для планера
    _PRIORITY_FUNCS = [
        'execute_python', 'debug_python_code', 'create_file', 'read_file', 'edit',
        'list_directory', 'search_in_code', 'list_sandbox_scripts',
        'open_program', 'close_program', 'mouse_click', 'keyboard_type', 'keyboard_press',
        'take_screenshot', 'ocr_screen', 'click_text', 'find_text_on_screen',
        'analyze_current_context', 'click_element', 'fill_form',
        'create_skill', 'list_windows', 'get_active_window',
        'activate_window', 'activate_window_by_title',
        'ask_user', 'voice_input', 'record_action', 'undo_last',
        'wait_for_response',
    ]

    MAX_PLANNER_FUNCTIONS = 35

    # ─── Класифікація задач ─────────────────────────────────────────

    @staticmethod
    def is_coding_task(task: str) -> bool:
        """Чи є задача кодовою (передбачає роботу з файлами/кодом)."""
        normalized = task.lower()
        return any(m in normalized for m in PlannerPromptBuilder._CODING_MARKERS)

    @staticmethod
    def should_plan_check(task: str) -> bool:
        """Чи схожа задача на багатокрокову (без залежності від Planner)."""
        normalized = task.lower().strip()

        # Спеціальна обробка voice_input (Qt модифікує текст)
        if normalized.startswith("_") and re.match(r'^_\s*\d+$', normalized):
            return True

        # Зменшуємо поріг для команд з шляхами
        if any(c in normalized for c in [":", "\\", "/"]):
            return any(marker in normalized for marker in PlannerPromptBuilder._PLAN_MARKERS)
        return len(normalized.split()) >= 5 and any(
            marker in normalized for marker in PlannerPromptBuilder._PLAN_MARKERS
        )

    # ─── Серіалізація контексту ─────────────────────────────────────

    @staticmethod
    def build_artifacts_summary(context: Dict[str, Any]) -> str:
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

    @staticmethod
    def recent_history_section(conversation_history: List[Dict[str, Any]], limit: int = 3) -> str:
        """Взяти останні N повідомлень з діалогу для контексту planner-а."""
        recent = conversation_history[-(limit + 1):-1] if len(conversation_history) > 1 else []
        if not recent:
            return ""
        lines = []
        for msg in recent:
            role = msg.get("role", "user")
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            if len(content) > 300:
                content = content[:300] + "..."
            label = "Користувач" if role == "user" else "Асистент"
            lines.append(f"{label}: {content}")
        if not lines:
            return ""
        return (
            "\nНЕЩОДАВНІЙ ДІАЛОГ (для контексту, поточна задача — останнє повідомлення користувача):\n"
            + "\n".join(lines) + "\n"
        )

    @staticmethod
    def available_actions_description(registry: Any) -> str:
        """Зібрати доступні функції з реєстру (скорочений список для планера)."""
        if not registry or not hasattr(registry, "functions"):
            return ""

        priority = PlannerPromptBuilder._PRIORITY_FUNCS
        max_funcs = PlannerPromptBuilder.MAX_PLANNER_FUNCTIONS
        lines = []
        added: Set[str] = set()

        # Спочатку priority функції
        for name in priority:
            if name in registry.functions:
                func_info = registry.functions[name]
                description = func_info.get("description", "")[:50]
                lines.append(f"- {name}: {description}")
                added.add(name)

        # Додаємо ще трохи функцій (до MAX_PLANNER_FUNCTIONS загалом)
        for name, func_info in sorted(registry.functions.items()):
            if name not in added and len(added) < max_funcs:
                description = func_info.get("description", "")[:40]
                lines.append(f"- {name}: {description}")
                added.add(name)

        return "\n".join(lines)

    @staticmethod
    def resolve_placeholders(value: Any, context: Dict[str, Any]) -> Any:
        """Замінити placeholder-и в значенні на реальні дані з контексту."""
        if not isinstance(value, str):
            return value

        value = value.strip()
        for placeholder, context_key in PlannerPromptBuilder._PLACEHOLDER_MAP.items():
            if placeholder in value:
                context_value = context.get(context_key)
                if context_value:
                    value = value.replace(placeholder, str(context_value))

        return value

    # ─── Побудова промптів ──────────────────────────────────────────

    @staticmethod
    def build_initial_plan_prompt(
        task: str,
        available_actions: str,
        history_section: str,
        context: Optional[Dict[str, Any]] = None,
        is_coding: bool = False,
    ) -> str:
        """Побудувати промпт для первинного планування задачі."""
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

        coding_section = PlannerPromptBuilder.build_coding_section(is_coding)

        forbidden_section = """
ЗАБОРОНЕНІ ПАТЕРНИ:
- ЗАБОРОНЕНО використовувати `execute_python` з `time.sleep()` для очікування
- ЗАБОРОНЕНО використовувати `execute_python` з `import time` для затримок
- Для взаємодії з вікнами (Windsurf, браузер тощо) використовуй тільки keyboard_type, keyboard_press, mouse_click
- Не додавай зайві кроки очікування - виконуй тільки необхідні дії
"""

        prompt = f"""ТИ — PLANNER (планувальник). Твоя задача: розбити запит користувача на послідовність дій.

ВАЖЛИВО: відповідай ТІЛЬКИ JSON-масивом. БЕЗ пояснень, БЕЗ вступів, БЕЗ привітань.

ДОСТУПНІ ФУНКЦІЇ:
{available_actions}
{history_section}{context_section}{coding_section}{forbidden_section}
ФОРМАТ ВІДПОВІДІ (строго JSON-масив):
[
  {{"action":"назва_функції","args":{{...}},"goal":"що має статись","validation":"як зрозуміти що успіх"}},
  {{"action":"назва_функції","args":{{...}},"goal":"...","validation":"..."}}
]

ПРИКЛАДИ:
1. "Створи файл test.txt з текстом 'hello'"
   [{{"action":"create_file","args":{{"filename":"test.txt","content":"hello"}},"goal":"створити файл","validation":"файл існує"}}]

2. "Проаналізуй код в директорії d:\\Python\\agent\\"
   [{{"action":"list_directory","args":{{"directory":"d:\\Python\\agent\\"}},"goal":"переглянути вміст директорії","validation":"список файлів отримано"}}]

3. "Напиши питання у вікно" / "Задай питання у вікні X"
   [
     {{"action":"activate_window_by_title","args":{{"title":"<назва_вікна>"}},"goal":"активувати вікно","validation":"вікно активне"}},
     {{"action":"keyboard_type","args":{{"text":"<питання>"}},"goal":"ввести текст","validation":"текст введено"}},
     {{"action":"keyboard_press","args":{{"key":"enter"}},"goal":"надіслати","validation":"повідомлення відправлено"}},
     {{"action":"wait_for_response","args":{{"duration":300,"check_interval":25,"check_for_response":true,"use_uia":true}},"goal":"зачекати відповіді","validation":"очікування завершено"}}
   ]

3. "Контролювати/моніторити вікно і задавати питання"
   [
     {{"action":"activate_window_by_title","args":{{"title":"<назва_вікна>"}},"goal":"активувати вікно","validation":"вікно активне"}},
     {{"action":"keyboard_type","args":{{"text":"<питання>"}},"goal":"задати питання","validation":"текст введено"}},
     {{"action":"keyboard_press","args":{{"key":"enter"}},"goal":"надіслати","validation":"відправлено"}},
     {{"action":"wait_for_response","args":{{"duration":300,"check_interval":25,"check_for_response":true,"use_uia":true}},"goal":"зачекати відповіді","validation":"очікування завершено"}}
   ]
   ПРИМІТКА: для постійного моніторингу відповідей використовуй start_windsurf_watch якщо доступна.

ВАЖЛИВО: Після кожного відправлення питання (keyboard_type + keyboard_press enter) ОБОВ'ЯЗКОВО додавай wait_for_response щоб зачекати відповіді (1-10 хв).
- duration: час очікування в секундах (рекомендовано 300 для 5 хв, 600 для 10 хв)
- check_interval: інтервал перевірки в секундах (рекомендовано 25 = перевірка кожні 25с)
- check_for_response: true (перевіряє наявність нової відповіді через UIA або OCR)
- check_for_confirmation: true (перевіряє наявність запиту на підтвердження через OCR)
- use_uia: true (використовує UI Automation для перевірки - швидше і надійніше за OCR, з fallback на OCR)
- Це універсальна функція для будь-якої програми/вікна, не тільки для Windsurf

Задача користувача: {task}

Відповідай тільки JSON, без жодного іншого тексту:"""
        return prompt

    @staticmethod
    def build_retry_plan_prompt(task: str, available_actions: str) -> str:
        """Побудувати повторний (retry) промпт після невдалого парсингу."""
        return f"""ТИ — PLANNER. Розбий задачу на кроки.

ПОПЕРЕДЖЕННЯ: Попередня відповідь була неправильною. Відповідай ТІЛЬКИ JSON.

ФУНКЦІЇ: {available_actions}

ФОРМАТ: [{{"action":"...","args":{{...}},"goal":"..."}}]

Задача: {task}

JSON:"""

    @staticmethod
    def build_repair_prompt(
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        artifacts_summary: str,
        available_actions: str,
    ) -> str:
        """Побудувати промпт для repair-кроку після невдалого виконання."""
        return f"""
Ти repair-planner. Поточна задача: {task}

Провалився крок:
{json.dumps(failed_step, ensure_ascii=False, indent=2)}

Результат/помилка:
{result}

ДОСТУПНІ АРТЕФАКТИ (використовуй placeholder-и типу {{{{last_file_path}}}}):
{artifacts_summary}

Доступні функції:
{available_actions}

Поверни ТІЛЬКИ JSON-об'єкт одного альтернативного кроку у форматі:
{{"action":"назва_функції","args":{{...}},"goal":"...","validation":"..."}}

Якщо безпечного repair-кроку немає, поверни:
{{"action":"abort","args":{{}},"goal":"stop","validation":"stop"}}
"""

    @staticmethod
    def build_replan_prompt(
        task: str,
        failed_step: Dict[str, Any],
        result: str,
        artifacts_summary: str,
        available_actions: str,
        completed_steps: int,
        repair_attempts: int,
        replan_attempts: int,
        remaining_steps: List[Dict[str, Any]],
    ) -> str:
        """Побудувати промпт для replan (перебудування решти плану)."""
        return f"""
Ти replanner локального асистента.

Початкова задача:
{task}

Невдалий крок:
{json.dumps(failed_step, ensure_ascii=False, indent=2)}

Результат невдачі:
{result}

ДОСТУПНІ АРТЕФАКТИ (використовуй placeholder-и типу {{{{last_file_path}}}}):
{artifacts_summary}

Кількість виконаних кроків: {completed_steps}
Кількість спроб repair: {repair_attempts}
Кількість replan: {replan_attempts}

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

    @staticmethod
    def build_context_section_for_plan(context: Optional[Dict[str, Any]]) -> str:
        """Побудувати секцію контексту з артефактів (для create_plan)."""
        if not context or not context.get("artifacts_summary"):
            return ""
        return f"""
ДОСТУПНІ АРТЕФАКТИ ВІД ПОПЕРЕДНІХ КРОКІВ:
{context['artifacts_summary']}

Використовуй ці placeholder-и для посилання на артефакти:
- {{previous_file_path}} або {{last_file_path}} — останній створений/змінений файл
- {{last_script_path}} — останній Python скрипт
- {{last_url}} — останній відкритий URL
- {{last_output}} — вивід останнього скрипта
- {{last_program}} — остання відкрита програма
"""

    @staticmethod
    def build_coding_section(is_coding: bool) -> str:
        """Побудувати секцію інструкцій для кодових задач."""
        if not is_coding:
            return ""
        return """
ЦЕ КОДОВА ЗАДАЧА. ДОТРИМУЙСЯ АЛГОРИТМУ (суворо по порядку):
1. **ОРІЄНТАЦІЯ** — викликати `get_repo_map()` — зрозуміти структуру проєкту
2. **ПОШУК** — визначити файли які стосуються задачі (за картою або `search_in_code`)
3. **АНАЛІЗ ЗАЛЕЖНОСТЕЙ** — для кожного файлу який планую змінити:
   викликати `get_file_dependents(filepath)`
4. **ЧИТАННЯ** — прочитати тільки потрібні файли через `read_code_file`
5. **ЗМІНА** — внести зміну (`edit_file` або `create_file`)
6. **ОНОВЛЕННЯ ІНДЕКСУ** — викликати `update_repo_map(filepath)` для зміненого файлу
7. **ПЕРЕВІРКА** — переконатись що залежні файли не зламані (`execute_python`)

⚠️ КРИТИЧНІ ЗАБОРОНИ:
1. НІКОЛИ не змінюй файл не перевіривши його залежності через `get_file_dependents`
2. НІКОЛИ не читай весь проєкт файл за файлом — використовуй `get_repo_map`
"""

    @staticmethod
    def build_forbidden_section() -> str:
        """Побудувати секцію заборонених патернів."""
        return """
ЗАБОРОНЕНІ ПАТЕРНИ:
- ЗАБОРОНЕНО використовувати `execute_python` з `time.sleep()` для очікування
- ЗАБОРОНЕНО використовувати `execute_python` з `import time` для затримок
- Для взаємодії з вікнами (Windsurf, браузер тощо) використовуй тільки keyboard_type, keyboard_press, mouse_click
- Не додавай зайві кроки очікування - виконуй тільки необхідні дії
"""