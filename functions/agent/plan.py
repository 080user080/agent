"""plan — LLM-driven phase для генерації плану дій (ActionDecider).

Цей модуль ізолює формування системних промптів та взаємодію з LLM-моделлю
для визначення наступного кроку агента.

Архітектура:
- `AgentAction` — структурована дія (name + arguments + reasoning).
- `ActionDecider` — LLM-клас, який на основі observation повертає `AgentAction`.
- `build_default_decider` — фабрика для збірки дефолтного `ActionDecider`.

Виділено з `functions/planning/agent_loop.py` в рамках рефакторингу А3 (Крок 2.2).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("agent.plan")


# --------------------------------------------------------------------------- #
# Структури даних                                                             #
# --------------------------------------------------------------------------- #


@dataclass
class AgentAction:
    """Структурована дія, яку повертає ActionDecider.

    Аналог OpenAI tool_call: name + arguments. Спеціальні значення
    `name`: ``done`` (завершити цикл), ``ask_user`` (запитати користувача).
    """
    name: str = "noop"
    arguments: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    tool_call_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Observation typing                                                           #
# --------------------------------------------------------------------------- #

# Для type hints використовуємо Dict, щоб уникнути циклічного імпорту
ObservationDict = Dict[str, Any]


# --------------------------------------------------------------------------- #
# ActionDecider                                                               #
# --------------------------------------------------------------------------- #


class ActionDecider:
    """LLM-driven decider: на основі observation повертає наступну `AgentAction`.

    Використовує OpenAI-compatible tool-calling через `logic_llm_tools.ask_llm_with_tools`.
    Якщо LLM повертає `tool_calls` — беремо перший і конвертуємо в `AgentAction`.
    Якщо ні (немає tools_calls, лише content) — інтерпретуємо як `done`.

    Якщо LLM-шар недоступний (немає endpoint, немає logic_llm_tools, тощо) —
    `decide()` повертає `AgentAction(name="noop")`, що змусить AgentLoop впасти
    на наступний пріоритет (CompiledPlan / Planner).
    """

    SYSTEM_PROMPT = (
        "Ти — агент, який аналізує екран, код і виконує задачі на комп'ютері. "
        "Тобі дано задачу і поточний стан (скріншот, файли, історія дій). "
        "Твоя робота — повернути ОДИН наступний крок як JSON об'єкт. "
        "\n"
        "ВАЖЛИВО: You MUST respond with ONLY valid JSON. No markdown, no explanations outside JSON.\n"
        "Format:\n"
        "{\n"
        '  "action": "<tool_name>",\n'
        '  "args": {...},\n'
        '  "reasoning": "explanation"\n'
        "}\n"
        "\n"
        "Available actions:\n"
        "- take_screenshot: args={} — Capture current screen. Use when task is about SCREEN, desktop, windows.\n"
        "- ocr_screen: args={\"lang\": \"ukr+eng\"} — Read visible text from screen. Use after take_screenshot for screen analysis.\n"
        "- find_text_on_screen: args={\"text\": \"search_text\"} — Find coordinates of text on screen.\n"
        "- list_directory: args={\"directory\": \"path\"} — List files in directory (limited output).\n"
        "- read_code_file: args={\"filepath\": \"path\"} — Read file from disk.\n"
        "- write_file: args={\"filepath\": \"path\", \"content\": \"text\"} — Create or overwrite a text file.\n"
        "- execute_python: args={\"code\": \"python_code\"} — Execute Python code in a safe sandbox. Use for simple tasks and file search with glob/os.walk.\n"
        "- oi_execute_with_healing: args={\"code\": \"python_code\"} — Execute code with self-healing via Open Interpreter. Use for complex tasks requiring auto-install of missing modules or error recovery.\n"
        "- done: args={\"summary\": \"short_result\"} — Complete the task.\n"
        "- ask_user: args={\"question\": \"question\"} — Ask user for information.\n"
        "\n"
        "CRITICAL RULES:\n"
        "1. If you don't know what to do — use \"take_screenshot\"\n"
        "2. Never return empty or noop unless absolutely necessary\n"
        "3. If task is about \"screen analysis\" — first take_screenshot, then ocr_screen, then done with summary\n"
        "4. Do not use list_directory for screen analysis — it analyzes files, not screen!\n"
        "5. For file search with many files, use execute_python with glob or os.walk instead of list_directory.\n"
        "6. For simple code execution, use execute_python. For complex tasks with potential missing modules, use oi_execute_with_healing.\n"
        "7. Execute at most 3-5 actions for analysis tasks\n"
        "8. After 2-3 steps, you must call done with summary\n"
        "9. When task is complete — action=\"done\", args={\"summary\": \"short result\"}\n"
        "10. If you need information from user — action=\"ask_user\"\n"
        "11. If task is about executing code — use \"execute_python\" (simple) or \"oi_execute_with_healing\" (complex)\n"
        "12. If task is about creating files — use \"write_file\"\n"
        "12a. Do NOT create or rewrite project files through execute_python with open(..., 'w') or Path.write_text(...). Use write_file for file content, then execute_python only to verify.\n"
        "13. If task is ambiguous or unclear — ask_user for clarification BEFORE taking action\n"
        "14. DO NOT invent new tools — use only the ones listed above\n"
        "15. **TASK CHECKLIST**: After each action, mentally track what's done vs what's left. Example: \"1. constants.py [DONE], 2. base_tab.py [DONE], 3. chat_tab.py [NEXT]\".\n"
        "16. **NO REPEATED LIST_DIRECTORY**: NEVER call list_directory twice in a row unless you changed the folder contents. If file is missing — CREATE IT, don't check again!\n"
        "17. **NO REPEATED WRITE_FILE**: After write_file returns ok=True, NEVER write to the same filepath again unless you need to change the content. Move to the NEXT file immediately.\n"
        "18. **INTERNAL CHECKLIST**: Keep a mental checklist. After each write_file ok=True — mark that file as DONE and never touch it again. Move to next file.\n"
        "19. **ЗАБОРОНА execute_python ДЛЯ ФАЙЛІВ**: Ніколи не використовуй execute_python для створення або редагування файлів. Для цього є write_file та edit_file. execute_python дозволений ТІЛЬКИ для перевірки коротких виразів (≤5 рядків, без def/class) або запуску вже існуючих скриптів через execute_python_file. Код довший за 5 рядків або з def/class буде відхилено валідатором.\n"
        "20. **АВТОПЕРЕВІРКА**: Після write_file/edit_file для .py файлу система автоматично перевіряє синтаксис. Якщо є помилка — буде запущено repair-loop для виправлення.\n"
        "\n"
        "ПРАВИЛО ВИКОНАВЦЯ (пріоритет дії над перевіркою):\n"
        "A. Якщо завдання передбачає створення N файлів — не намагайся перевірити їх наявність після кожного кроку.\n"
        "B. Створив файл → Записав у внутрішній чек-лист → Перейшов до наступного.\n"
        "C. Викликай list_directory ТІЛЬКИ ОДИН РАЗ на самому початку і ОДИН РАЗ в самому кінці для фінальної перевірки.\n"
        "D. Якщо ти бачиш у actions_history, що ти вже робив list_directory — тобі ЗАБОРОНЕНО робити його знову, поки ти не створиш новий файл.\n"
        "\n"
        "ПРАВИЛО СУВОРОЇ ПОСЛІДОВНОСТІ:\n"
        "1. Після створення файлу (write_file), відмічай його у своєму внутрішньому списку як \"DONE\".\n"
        "2. ЗАБОРОНЕНО викликати одну й ту саму READ-дію (list_directory, read_file) двічі поспіль без проміжної WRITE-дії.\n"
        "3. Якщо ти бачиш у списку файлів 4 файли з 10 потрібних — не чекай, поки вони з'являться самі. Створи відсутні файли.\n"
        "4. Якщо ти вже бачив вивід list_directory, ти МАЄШ ПОВЕРНУТИ помилку самому собі, якщо намагаєшся викликати його знову без створення файлу.\n"
        "5. ПРАВИЛО СТВОРЕННЯ: Якщо дія read_code_file повертає 'Файл не знайдено', це означає, що твоя наступна дія має бути виключно write_file для цього файлу. ЗАБОРОНЕНО робити list_directory або знову read_code_file після помилки відсутності файлу.\n"
        "\n"
        "RESPOND WITH ONLY JSON. NO MARKDOWN. NO EXPLANATIONS OUTSIDE JSON."
    )

    def __init__(
        self,
        ask_llm_with_tools_fn: Optional[Callable[..., Any]] = None,
        tools_schema: Optional[List[Dict[str, Any]]] = None,
        tool_aliases: Optional[Dict[str, str]] = None,
        system_prompt: Optional[str] = None,
        history_max: int = 10,
        max_json_failures: int = 5,
    ):
        self._ask_llm_with_tools = ask_llm_with_tools_fn
        self._tools = list(tools_schema or [])
        self._aliases = dict(tool_aliases or {})
        self._system_prompt = system_prompt or self.SYSTEM_PROMPT
        self._history_max = max(1, int(history_max))
        self._max_json_failures = max(1, int(max_json_failures))
        self._consecutive_json_failures: int = 0

    @property
    def is_available(self) -> bool:
        """Чи доступний LLM-шар для прийняття рішень."""
        avail = self._ask_llm_with_tools is not None
        return avail

    def resolve_alias(self, tool_name: str) -> str:
        """Перетворити alias імені інструменту на реальне ім'я в FunctionRegistry."""
        return self._aliases.get(tool_name, tool_name)

    def _format_observation(self, obs: Any, max_chars: int = 1500) -> str:
        """Форматувати observation для LLM-промпту.

        Приймає об'єкт Observation з observe.py або dict-подібний об'єкт.
        """
        if not obs:
            return "(немає спостереження)"
        parts: List[str] = []
        # Отримуємо атрибути через getattr для сумісності з dataclass та dict
        active_window_title = (
            getattr(obs, 'active_window_title', None)
            or (obs.get('active_window_title') if isinstance(obs, dict) else None)
        )
        screenshot_path = (
            getattr(obs, 'screenshot_path', None)
            or (obs.get('screenshot_path') if isinstance(obs, dict) else None)
        )
        ocr_text = (
            getattr(obs, 'ocr_text', None)
            or (obs.get('ocr_text') if isinstance(obs, dict) else None)
        )
        ui_elements = (
            getattr(obs, 'ui_elements', None)
            or (obs.get('ui_elements') if isinstance(obs, dict) else None)
        )
        uia_tree = (
            getattr(obs, 'uia_tree', None)
            or (obs.get('uia_tree') if isinstance(obs, dict) else None)
        )
        vision_description = (
            getattr(obs, 'vision_description', None)
            or (obs.get('vision_description') if isinstance(obs, dict) else None)
        )

        if active_window_title:
            parts.append(f"Активне вікно: {active_window_title}")
        if screenshot_path:
            parts.append(f"Скріншот: {screenshot_path}")
        if ocr_text:
            text = ocr_text.strip()
            if len(text) > max_chars:
                text = text[:max_chars] + "…"
            parts.append(f"OCR-текст:\n{text}")
        if ui_elements:
            elements = ui_elements[:30]
            elem_lines = [
                f"- {e.get('type', '?')} \"{e.get('text', '')}\" @ {e.get('x', '?')},{e.get('y', '?')}"
                for e in elements
            ]
            parts.append("UI-елементи:\n" + "\n".join(elem_lines))
        if uia_tree:
            try:
                tree_str = json.dumps(uia_tree, ensure_ascii=False)[:1000]
                parts.append(f"UIA-дерево (скорочено): {tree_str}")
            except Exception:
                pass
        if vision_description:
            parts.append(f"Vision-опис: {vision_description}")
        return "\n\n".join(parts) if parts else "(порожнє спостереження)"

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """Форматувати історію дій для LLM-промпту."""
        if not history:
            return "(історія порожня — це перший крок)"
        recent = history[-self._history_max:]
        lines = []
        for h in recent:
            action = h.get("action", "?")
            args = h.get("args", {})
            ok = h.get("act_result", {}).get("ok", "?")
            check = h.get("check_result", {}).get("detail", "")
            try:
                args_str = json.dumps(args, ensure_ascii=False)[:1000]
            except Exception:
                args_str = str(args)[:1000]
            lines.append(f"- {action}({args_str}) → ok={ok} {check}")
        return "\n".join(lines)

    def build_messages(
        self,
        goal: str,
        observation: Any,
        history: List[Dict[str, Any]],
        last_result: Optional[Dict[str, Any]] = None,
        extra_instructions: str = "",
        current_step: int = 0,
        progress_summary: str = "",
        context_controller: Optional[Any] = None,
        stuck_warning: str = "",
    ) -> List[Dict[str, str]]:
        """Побудувати список повідомлень для LLM."""
        user_parts = [
            f"ЗАДАЧА: {goal}",
            f"ПОТОЧНИЙ КРОК: {current_step} (максимум 3-5 кроків для аналізу коду)",
            "",
            "ПОТОЧНЕ СПОСТЕРЕЖЕННЯ ЕКРАНУ:",
            self._format_observation(observation),
            "",
            "ОСТАННІ ДІЇ:",
            self._format_history(history),
        ]

        # Пріоритет: context_controller > progress_summary
        context_block = ""
        if context_controller:
            context_block = context_controller.get_full_context()
        elif progress_summary:
            context_block = f"ПРОГРЕС ВИКОНАННЯ:\n{progress_summary}"

        if context_block:
            user_parts = [
                f"ЗАДАЧА: {goal}",
                f"ПОТОЧНИЙ КРОК: {current_step} (максимум 3-5 кроків для аналізу коду)",
                "",
                context_block,
                "",
                "ПОТОЧНЕ СПОСТЕРЕЖЕННЯ ЕКРАНУ:",
                self._format_observation(observation),
                "",
                "ОСТАННІ ДІЇ:",
                self._format_history(history),
            ]

        if last_result is not None:
            try:
                last_str = json.dumps(last_result, ensure_ascii=False)[:400]
            except Exception:
                last_str = str(last_result)[:400]
            user_parts += ["", f"РЕЗУЛЬТАТ ОСТАННЬОЇ ДІЇ: {last_str}"]
        if extra_instructions:
            user_parts += ["", extra_instructions]
        if stuck_warning:
            user_parts += ["", stuck_warning]
        user_parts += [
            "",
            "Виклич ОДИН інструмент для наступного кроку. Якщо задача виконана — виклич `done`.",
        ]
        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

    def decide(
        self,
        goal: str,
        observation: Any,
        history: List[Dict[str, Any]],
        last_result: Optional[Dict[str, Any]] = None,
        progress_summary: str = "",
        context_controller: Optional[Any] = None,
        stuck_warning: str = "",
        extra_instructions: str = "",
    ) -> AgentAction:
        """Один крок рішення через LLM (JSON parsing fallback).

        Покращений механізм:
        1. Спочатку пробує JSON-parsing (без function-calling) — для моделей
           без підтримки tool_calls (LM Studio, локальні).
        2. Якщо JSON не парситься — пробує з function-calling (tool_choice="auto").
        3. Якщо і це невдало — fallback на take_screenshot (або done якщо
           перевищено ліміт спроб).
        4. Трекінг consecutive JSON failures — після N невдач force `done`.
        5. Жодних Exception назовні — завжди повертає AgentAction.
        """
        if not self.is_available:
            return AgentAction(name="noop", reasoning="LLM decider unavailable")

        # Force done якщо забагато послідовних JSON помилок
        if self._consecutive_json_failures >= self._max_json_failures:
            logger.warning(
                "ActionDecider: Too many consecutive JSON failures (%d≥%d), force done",
                self._consecutive_json_failures, self._max_json_failures,
            )
            self._consecutive_json_failures = 0
            return AgentAction(
                name="done",
                arguments={"summary": "Force done: too many JSON parsing failures", "success": False},
                reasoning="Force done after max consecutive JSON failures",
            )

        messages = self.build_messages(
            goal, observation, history, last_result,
            current_step=len(history),
            progress_summary=progress_summary,
            context_controller=context_controller,
            stuck_warning=stuck_warning,
            extra_instructions=extra_instructions,
        )

        # --- Спроба 1: Без tool_calls (JSON parsing) ---
        try:
            response = self._ask_llm_with_tools(
                messages=messages,
                tools=[],
                tool_choice=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ActionDecider: LLM call (JSON mode) failed: %s", exc)
            # Пробуємо function-calling як fallback
            return self._try_with_tools(messages)

        if getattr(response, "error", None):
            logger.warning("ActionDecider: LLM error (JSON mode): %s", response.error)
            return self._try_with_tools(messages)

        # Перевіряємо tool_calls у відповіді
        tool_calls = getattr(response, "tool_calls", None) or []
        if tool_calls:
            return self._parse_tool_calls(response, tool_calls)

        # Парсимо JSON з content
        action = self._parse_json_from_content(response)
        if action is not None:
            # Успіх — скидаємо лічильник помилок
            self._consecutive_json_failures = 0
            return action

        # JSON не розпарсився. Окремий випадок: порожній контент → done,
        # це означає що LLM нічого не повернула і нема чого парсити.
        raw_content = str(getattr(response, "content", "") or "").strip()
        if not raw_content:
            logger.warning("ActionDecider: empty response, fallback to done")
            return AgentAction(
                name="done",
                arguments={"summary": "Empty response from LLM", "success": False},
                reasoning="Empty response — terminating to avoid loop",
            )

        # JSON не розпарсився (невалідний/обрізаний) — інкрементуємо лічильник
        # і передаємо вміст у _try_with_tools для подальшої обробки
        self._consecutive_json_failures += 1
        logger.warning(
            "ActionDecider: JSON parsing attempt %d/%d failed",
            self._consecutive_json_failures, self._max_json_failures,
        )

        # --- Спроба 2: З tool_calls (function-calling режим) ---
        return self._try_with_tools(messages, last_content=raw_content)

    def _parse_tool_calls(
        self, response: Any, tool_calls: List[Any],
    ) -> AgentAction:
        """Розпарсити tool_calls у AgentAction."""
        tc = tool_calls[0]
        return AgentAction(
            name=str(tc.name),
            arguments=dict(tc.arguments or {}),
            reasoning=str(getattr(response, "content", "") or ""),
            tool_call_id=str(getattr(tc, "id", "") or "") or None,
        )

    def _try_with_tools(
        self,
        messages: List[Dict[str, str]],
        last_content: str = "",
    ) -> AgentAction:
        """Fallback: спроба LLM виклику з function-calling (tool_choice='auto')."""
        try:
            response = self._ask_llm_with_tools(
                messages=messages,
                tools=self._tools,
                tool_choice="auto",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ActionDecider: LLM call (tool mode) failed: %s", exc)
            self._consecutive_json_failures += 1
            return self._json_failure_fallback(last_content=last_content)

        if getattr(response, "error", None):
            logger.warning(
                "ActionDecider: LLM error (tool mode): %s", response.error,
            )
            self._consecutive_json_failures += 1
            return self._json_failure_fallback(last_content=last_content)

        tool_calls = getattr(response, "tool_calls", None) or []
        if tool_calls:
            self._consecutive_json_failures = 0
            return self._parse_tool_calls(response, tool_calls)

        # Tool-режим теж не повернув tool_calls — спробуємо JSON з content
        action = self._parse_json_from_content(response)
        if action is not None:
            self._consecutive_json_failures = 0
            return action

        self._consecutive_json_failures += 1
        tool_content = str(getattr(response, "content", "") or "").strip()
        return self._json_failure_fallback(last_content=tool_content or last_content)

    def _json_failure_fallback(self, last_content: str = "") -> AgentAction:
        """Повернути fallback дію при невдалому парсингу JSON.

        Стратегія:
        - Якщо контент починається з `{` (схожий на JSON, але невалідний)
          — примусовий `done` (аби уникнути нескінченного циклу take_screenshot).
        - Інакше (довільний текст, не схожий на JSON) — `take_screenshot`
          для оновлення спостереження (legacy поведінка).
        - Якщо перевищено ліміт `_consecutive_json_failures` — `done`.
        """
        if self._consecutive_json_failures >= self._max_json_failures:
            logger.warning(
                "ActionDecider: Max JSON failures (%d) reached, force done",
                self._consecutive_json_failures,
            )
            self._consecutive_json_failures = 0
            return AgentAction(
                name="done",
                arguments={
                    "summary": "Force done after max JSON parsing failures",
                    "success": False,
                },
                reasoning="Force done after max consecutive JSON failures",
            )

        # Якщо контент починається з { — це явно невалідний JSON → done
        if last_content and last_content.lstrip().startswith("{"):
            logger.warning(
                "ActionDecider: Content looks like JSON but failed to parse, force done",
            )
            self._consecutive_json_failures += 1
            return AgentAction(
                name="done",
                arguments={
                    "summary": "Invalid JSON from LLM",
                    "success": False,
                },
                reasoning="Invalid JSON content — terminating to avoid loop",
            )

        # Довільний текст (не схожий на JSON) — take_screenshot
        logger.warning(
            "ActionDecider: Non-JSON content, fallback to take_screenshot",
        )
        return AgentAction(
            name="take_screenshot",
            arguments={},
            reasoning="Non-JSON content, taking screenshot as fallback",
        )

    def _fix_truncated_json(self, content: str) -> str:
        """Дописати закриваючі дужки для обрізаного JSON.

        Викликається після _extract_json_braces, якщо json.loads не вдався.
        Пробує дописати `}` та `"]` для завершення незавершених конструкцій.
        """
        # Якщо вміст вже порожній або не починається з { — не чіпаємо
        if not content or not content.startswith("{"):
            return content

        # Спроба дописати обрізані лапки для останнього значення
        # Рахуємо баланс фігурних дужок
        brace_depth = 0
        in_string = False
        escaped = False
        last_char = ""
        for ch in content:
            if escaped:
                escaped = False
                continue
            if ch == '\\' and in_string:
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
            if not in_string:
                if ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth -= 1
            last_char = ch

        # Якщо всередині незакритого рядка — закриваємо лапки
        fixed = content
        if in_string:
            # Додаємо закриваючі лапки
            fixed += '"'
            in_string = False

        # Додаємо закриваючі фігурні дужки
        if brace_depth > 0:
            fixed += "}" * brace_depth

        if fixed != content:
            logger.info(
                "ActionDecider: Fixed truncated JSON (%d → %d chars): %s...",
                len(content), len(fixed), fixed[-100:],
            )

        return fixed

    def _parse_json_from_content(
        self, response: Any,
    ) -> Optional[AgentAction]:
        """Спробувати розпарсити JSON з content відповіді.

        Повертає AgentAction або None, якщо парсинг не вдався.
        """
        content = str(getattr(response, "content", "") or "").strip()
        if not content:
            return None

        # Видалити thinking блоки (для Qwen3 та інших thinking моделей)
        content = self._clean_think_blocks(content)

        # Видалити markdown code blocks
        content = self._extract_from_markdown(content)

        # Виділити JSON через brace matching
        content = self._extract_json_braces(content)

        if not content.startswith("{"):
            return None

        # Спроба 1: прямий парсинг
        parsed = self._try_json_load(content)
        if parsed is not None:
            return self._build_action_from_parsed(parsed)

        # Спроба 2: обрізаний JSON — дописати закриваючі дужки
        logger.info("ActionDecider: Trying truncated JSON fix for: %s...", content[:150])
        fixed = self._fix_truncated_json(content)
        if fixed != content:
            parsed = self._try_json_load(fixed)
            if parsed is not None:
                logger.info("ActionDecider: Truncated JSON fixed successfully")
                return self._build_action_from_parsed(parsed)

        return None

    def _try_json_load(self, content: str) -> Optional[dict]:
        """Спробувати json.loads з обробкою помилок."""
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.debug("ActionDecider: JSON parse error: %s", exc)
            return None

    def _build_action_from_parsed(self, parsed: dict) -> Optional[AgentAction]:
        """Побудувати AgentAction з розпарсеного dict."""
        action_name = parsed.get("action", "noop")
        args = parsed.get("args", {})
        if not isinstance(args, dict):
            args = {}
        reasoning = parsed.get("reasoning", "")

        if not action_name or action_name == "noop":
            logger.warning(
                "ActionDecider: Empty/noop action in parsed JSON: %s",
                action_name,
            )
            return None

        return AgentAction(
            name=str(action_name),
            arguments=args,
            reasoning=str(reasoning) + "\n[JSON parsed]",
        )

    def _clean_think_blocks(self, content: str) -> str:
        """Видалити <think>...</think> блоки."""
        cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        cleaned = cleaned.strip()
        if len(cleaned) != len(content):
            logger.info(
                "ActionDecider: Removed think blocks (%d→%d chars): %s...",
                len(content), len(cleaned), cleaned[:200],
            )
        return cleaned

    def _extract_from_markdown(self, content: str) -> str:
        """Виділити JSON з markdown code blocks."""
        if not content.startswith("```"):
            return content
        lines = content.splitlines()
        json_lines = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            json_lines.append(line)
        result = "\n".join(json_lines).strip()
        if result:
            logger.info("ActionDecider: Extracted from markdown: %s...", result[:200])
        return result

    def _extract_json_braces(self, content: str) -> str:
        """Виділити JSON об'єкт через балансування дужок."""
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(content):
            if char == '{' and start_idx == -1:
                start_idx = i
                brace_count = 1
            elif char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    candidate = content[start_idx:i + 1]
                    if '"action"' in candidate:
                        logger.info(
                            "ActionDecider: Extracted JSON via brace matching: %s...",
                            candidate[:200],
                        )
                        return candidate
        return content

    def replan(
        self,
        goal: str,
        observation: Any,
        history: List[Dict[str, Any]],
        consecutive_failures: int,
        progress_summary: str = "",
        context_controller: Optional[Any] = None,
    ) -> AgentAction:
        """Переосмислити підхід після кількох невдач підряд."""
        instructions = (
            f"УВАГА: Останні {consecutive_failures} спроби не спрацювали. "
            "Подумай ШИРШЕ — можливо потрібен інший шлях. "
            "Спочатку зроби `take_screenshot` або `describe_screen`, "
            "якщо ще не зрозумів стан екрану."
        )
        if not self.is_available:
            return AgentAction(name="noop", reasoning="LLM decider unavailable")
        messages = self.build_messages(
            goal, observation, history, last_result=None,
            extra_instructions=instructions,
            progress_summary=progress_summary,
            context_controller=context_controller,
        )
        try:
            response = self._ask_llm_with_tools(
                messages=messages,
                tools=self._tools,
                tool_choice="auto",
            )
        except Exception as exc:  # noqa: BLE001
            return AgentAction(name="noop", reasoning=f"replan LLM error: {exc}")

        tool_calls = getattr(response, "tool_calls", None) or []
        if tool_calls:
            tc = tool_calls[0]
            return AgentAction(
                name=str(tc.name),
                arguments=dict(tc.arguments or {}),
                reasoning="(replan) " + str(getattr(response, "content", "") or ""),
                tool_call_id=str(getattr(tc, "id", "") or "") or None,
            )
        return AgentAction(
            name="done",
            arguments={
                "summary": str(getattr(response, "content", "") or "")
                or "Не вдалося знайти спосіб виконати задачу.",
                "success": False,
            },
        )


# --------------------------------------------------------------------------- #
# Factory helpers                                                             #
# --------------------------------------------------------------------------- #


def build_default_decider(
    *,
    enable_vision: bool = False,
    enable_uia: bool = False,
    enable_browser: bool = False,
    history_max: int = 10,
) -> Optional[ActionDecider]:
    """Зібрати ActionDecider із дефолтним LLM-шаром і tool-схемою.

    Повертає None якщо `logic_llm_tools` або `logic_agent_tools_schema` не
    імпортуються (середовище без LLM endpoint, тести без мережі тощо).
    """
    try:
        from functions.llm.logic_llm_tools import ask_llm_with_tools
        from functions.planning.logic_agent_tools_schema import (
            get_tools_for_capabilities,
            TOOL_NAME_ALIASES,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("ActionDecider unavailable: %s", exc)
        return None

    tools = get_tools_for_capabilities(
        enable_vision=enable_vision,
        enable_uia=enable_uia,
        enable_browser=enable_browser,
    )
    return ActionDecider(
        ask_llm_with_tools_fn=ask_llm_with_tools,
        tools_schema=tools,
        tool_aliases=dict(TOOL_NAME_ALIASES),
        history_max=history_max,
    )


__all__ = [
    "ActionDecider",
    "AgentAction",
    "ObservationDict",
    "build_default_decider",
]