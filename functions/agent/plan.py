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
    ):
        self._ask_llm_with_tools = ask_llm_with_tools_fn
        self._tools = list(tools_schema or [])
        self._aliases = dict(tool_aliases or {})
        self._system_prompt = system_prompt or self.SYSTEM_PROMPT
        self._history_max = max(1, int(history_max))

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
        """Один крок рішення через LLM (JSON parsing fallback)."""
        if not self.is_available:
            return AgentAction(name="noop", reasoning="LLM decider unavailable")

        messages = self.build_messages(
            goal, observation, history, last_result,
            current_step=len(history),
            progress_summary=progress_summary,
            context_controller=context_controller,
            stuck_warning=stuck_warning,
            extra_instructions=extra_instructions,
        )
        try:
            # Спочатку спробуємо без tools (JSON parsing fallback)
            # LM Studio може не підтримувати function-calling або конфліктувати з ним
            response = self._ask_llm_with_tools(
                messages=messages,
                tools=[],  # Порожній список — без function-calling
                tool_choice=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ActionDecider LLM call failed: %s", exc)
            return AgentAction(name="noop", reasoning=f"LLM error: {exc}")

        if getattr(response, "error", None):
            error_msg = str(response.error)
            logger.warning("ActionDecider LLM error: %s", error_msg)
            return AgentAction(name="noop", reasoning=f"LLM error: {error_msg}")

        # 1) Спробувати tool_calls (OpenAI-compatible)
        tool_calls = getattr(response, "tool_calls", None) or []
        if tool_calls:
            tc = tool_calls[0]
            return AgentAction(
                name=str(tc.name),
                arguments=dict(tc.arguments or {}),
                reasoning=str(getattr(response, "content", "") or ""),
                tool_call_id=str(getattr(tc, "id", "") or "") or None,
            )

        # 2) Fallback — парсити JSON з content
        content = str(getattr(response, "content", "") or "").strip()
        logger.info("ActionDecider: LLM content (full)=%s", content)

        # Видалити thinking блоки (для Qwen3 та інших thinking моделей)
        before_len = len(content)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = content.strip()
        after_len = len(content)
        if before_len != after_len:
            logger.info(
                "ActionDecider: Removed think blocks (%d→%d chars): %s...",
                before_len, after_len, content[:200],
            )

        # Видалити markdown code blocks якщо є
        if content.startswith("```"):
            lines = content.splitlines()
            json_lines = []
            for line in lines[1:]:
                if line.strip().startswith("```"):
                    break
                json_lines.append(line)
            content = "\n".join(json_lines).strip()
            logger.info("ActionDecider: Extracted from markdown: %s...", content[:200])

        # Спробувати знайти JSON через regex (пост-обробка)
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
                        content = candidate
                        logger.info(
                            "ActionDecider: Extracted JSON via brace matching: %s...",
                            content[:200],
                        )
                        break

        # Спробувати парсити як JSON
        if content.startswith("{"):
            try:
                parsed = json.loads(content)
                action_name = parsed.get("action", "noop")
                args = parsed.get("args", {})
                if not isinstance(args, dict):
                    args = {}
                reasoning = parsed.get("reasoning", "")

                # Перевірка на порожній або невалідний план
                if not action_name or action_name == "noop":
                    logger.warning("ActionDecider: Empty or noop action in parsed JSON")
                    raise ValueError(f"LLM returned empty/noop action: {action_name}")

                logger.info("ActionDecider: Parsed JSON action=%s", action_name)
                return AgentAction(
                    name=str(action_name),
                    arguments=args,
                    reasoning=str(reasoning) + "\n[JSON parsed]",
                )
            except json.JSONDecodeError:
                logger.warning(
                    "ActionDecider: JSON parse failed for: %s...", content[:100]
                )
                raise ValueError(f"JSON parse failed for content: {content[:100]}")
            except ValueError as e:
                logger.warning("ActionDecider: Invalid plan: %s", e)
                raise
            except Exception as e:
                logger.warning(
                    "ActionDecider: Unexpected error parsing JSON: %s", e
                )
                raise ValueError(f"Unexpected error parsing JSON: {e}")

        # 3) Fallback → якщо не розпарсилось → take_screenshot
        logger.warning(
            "ActionDecider: JSON parsing failed, fallback to take_screenshot"
        )
        return AgentAction(
            name="take_screenshot",
            arguments={},
            reasoning="JSON parsing failed, taking screenshot as fallback",
        )

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