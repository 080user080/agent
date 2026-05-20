"""AgentLoop — справжній цикл агента: observe → plan → act → check.

Це Phase 12.1 observe loop — заміна legacy linear execution на замкнутий цикл з feedback.

Архітектура:
- observe() → отримати поточний стан (скрін + OCR/UIA + UI elements + опц. Vision)
- plan() → вирішити що робити далі (LLM tool-calling → CompiledPlan → Planner)
- act() → виконати дію (миша/клавіатура/браузер)
- check() → перевірити чи спрацювало (скріншот + Expectations)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("agent_loop")

# Кешування імпортів для продуктивності
try:
    from functions.gui.tools_screen_capture import take_screenshot
    from functions.gui.tools_ocr import ocr_image
    from functions.gui.tools_ui_accessibility import get_uia_wrapper
    _SCREEN_CAPTURE_AVAILABLE = True
except ImportError:
    _SCREEN_CAPTURE_AVAILABLE = False


@dataclass
class Observation:
    """Результат observe() — поточний стан системи."""
    screenshot_path: str = ""
    ocr_text: str = ""
    screen_hash: str = ""
    timestamp: float = 0.0
    active_window_title: str = ""
    ui_elements: List[Dict[str, Any]] = field(default_factory=list)
    uia_tree: Optional[Dict[str, Any]] = None
    vision_description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


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


@dataclass
class AgentState:
    """Стат агента між ітераціями."""
    step: int = 0
    observations: List[Observation] = field(default_factory=list)
    last_action: Optional[str] = None
    last_result: Optional[str] = None
    actions_history: List[Dict[str, Any]] = field(default_factory=list)
    consecutive_failures: int = 0
    total_failures: int = 0
    done: bool = False
    success: bool = False
    done_summary: str = ""
    progress_summary: str = "Завдання розпочато."  # Підсумок виконання для ковзного вікна


@dataclass
class AgentLoopConfig:
    """Конфігурація AgentLoop."""
    max_steps: int = 200
    max_duration_seconds: float = 3600.0
    enable_ocr: bool = True
    enable_ui_a: bool = False
    enable_vision: bool = False
    enable_browser: bool = False
    enable_ui_elements: bool = True
    enable_llm_decider: bool = True
    enable_checkpoint: bool = True
    checkpoint_interval_steps: int = 5
    screen_diff_threshold: float = 0.01
    history_max_entries: int = 10
    max_observation_tokens: int =1500
    replan_after_failures: int = 3
    repair_after_failures: int = 2  # Викликати repairer при N consecutive failures
    enable_repair: bool = True
    skip_observe_for_simple: bool = False  # Пропускати скріншоти для простих задач
    summary_threshold: int = 7  # Кількість кроків після якої робити підсумовування
    keep_recent_actions: int = 3  # Скільки останніх дій залишати детальними
    expected_files: List[str] = field(default_factory=list)  # Список очікуваних файлів для перевірки завершеності (порожній за замовчуванням)


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

    def _format_observation(self, obs: Optional[Observation], max_chars: int = 1500) -> str:
        if not obs:
            return "(немає спостереження)"
        parts: List[str] = []
        if obs.active_window_title:
            parts.append(f"Активне вікно: {obs.active_window_title}")
        if obs.screenshot_path:
            parts.append(f"Скріншот: {obs.screenshot_path}")
        if obs.ocr_text:
            text = obs.ocr_text.strip()
            if len(text) > max_chars:
                text = text[:max_chars] + "…"
            parts.append(f"OCR-текст:\n{text}")
        if obs.ui_elements:
            elements = obs.ui_elements[:30]
            elem_lines = [
                f"- {e.get('type', '?')} \"{e.get('text', '')}\" @ {e.get('x', '?')},{e.get('y', '?')}"
                for e in elements
            ]
            parts.append("UI-елементи:\n" + "\n".join(elem_lines))
        if obs.uia_tree:
            try:
                tree_str = json.dumps(obs.uia_tree, ensure_ascii=False)[:1000]
                parts.append(f"UIA-дерево (скорочено): {tree_str}")
            except Exception:
                pass
        if obs.vision_description:
            parts.append(f"Vision-опис: {obs.vision_description}")
        return "\n\n".join(parts) if parts else "(порожнє спостереження)"

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
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
        observation: Optional[Observation],
        history: List[Dict[str, Any]],
        last_result: Optional[Dict[str, Any]] = None,
        extra_instructions: str = "",
        current_step: int = 0,
        progress_summary: str = "",
        context_controller: Optional[Any] = None,
        stuck_warning: str = "",
    ) -> List[Dict[str, str]]:
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
        observation: Optional[Observation],
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

        messages = self.build_messages(goal, observation, history, last_result, current_step=len(history), progress_summary=progress_summary, context_controller=context_controller, stuck_warning=stuck_warning, extra_instructions=extra_instructions)
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
            # Якщо помилка 400 про structured output — це конфлікт з tools
            # Повертаємо noop, LLM має генерувати JSON з content
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
        import re
        before_len = len(content)
        # DeepSeek:  
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = content.strip()
        after_len = len(content)
        if before_len != after_len:
            logger.info("ActionDecider: Removed think blocks (%d→%d chars): %s...", before_len, after_len, content[:200])

        # Видалити markdown code blocks якщо є
        if content.startswith("```"):
            # ```json ... ``` → взяти вміст
            lines = content.splitlines()
            # Пропустити перший рядок (```json або ```)
            json_lines = []
            for line in lines[1:]:
                if line.strip().startswith("```"):
                    break
                json_lines.append(line)
            content = "\n".join(json_lines).strip()
            logger.info("ActionDecider: Extracted from markdown: %s...", content[:200])

        # Спробувати знайти JSON через regex (пост-обробка)
        import re
        # Знаходимо JSON об'єкт, що починається з { і містить "action"
        # Простий підхід: знайти { і потім знайти відповідну }
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
                    # Знайшли повний JSON об'єкт
                    candidate = content[start_idx:i+1]
                    if '"action"' in candidate:
                        content = candidate
                        logger.info("ActionDecider: Extracted JSON via brace matching: %s...", content[:200])
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
                logger.warning("ActionDecider: JSON parse failed for: %s...", content[:100])
                raise ValueError(f"JSON parse failed for content: {content[:100]}")
            except ValueError as e:
                # Порожній план або невалідний action
                logger.warning("ActionDecider: Invalid plan: %s", e)
                raise
            except Exception as e:
                logger.warning("ActionDecider: Unexpected error parsing JSON: %s", e)
                raise ValueError(f"Unexpected error parsing JSON: {e}")

        # 3) Fallback → якщо не розпарсилось → take_screenshot
        logger.warning("ActionDecider: JSON parsing failed, fallback to take_screenshot")
        return AgentAction(
            name="take_screenshot",
            arguments={},
            reasoning="JSON parsing failed, taking screenshot as fallback",
        )

    def replan(
        self,
        goal: str,
        observation: Optional[Observation],
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
            goal, observation, history, last_result=None, extra_instructions=instructions, progress_summary=progress_summary, context_controller=context_controller
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


class AgentLoop:
    """Замкнутий цикл агента з observe → plan → act → check.

    Замінює legacy linear execution на справжній agent loop з feedback.
    """

    def __init__(
        self,
        assistant,
        registry=None,
        config: Optional[AgentLoopConfig] = None,
        ask_user_callback: Optional[Callable[[str, List[str]], str]] = None,
        decider: Optional[ActionDecider] = None,
        repairer: Optional[Any] = None,  # StepRepairer (опційно)
        context_controller: Optional[Any] = None,  # ContextController (опційно)
    ):
        self.assistant = assistant
        self.registry = registry
        self.config = config or AgentLoopConfig()
        self._state = AgentState()
        self._compiled_plan = None
        self.ask_user_callback = ask_user_callback
        self.decider = decider
        self.repairer = repairer  # StepRepairer для адаптивного відновлення
        self._prev_screen_hash = ""
        self._prev_screen_path = ""
        self._checkpoint_enabled = self.config.enable_checkpoint
        self._stop_flag = False
        self.gui_cb = None
        self.task_id = "default_task"
        
        # ContextController для єдиного управління пам'яттю
        self.context_controller = context_controller

        # LoopDetector — виявлення зациклення
        from functions.runtime.core_loop_detector import LoopDetector
        self.loop_detector = LoopDetector(max_repeats=3)

        # Блокування повторних ідентичних write_file
        self._blocked_write_fingerprints: set = set()
        self._execute_python_write_targets: set = set()

        # Пам'ять про відсутні файли (для A-B-A-B циклів)
        self.failed_reads: set = set()

        # Чи був викликаний list_directory хоч раз (для заборони другого)
        self._list_directory_used: bool = False
        # Останній результат list_directory (файли)
        self._last_list_dir_files: list = []
        # Чи був хоч один write_file після list_directory
        self._has_written_since_list_dir: bool = False

    # ─── GUI messaging ────────────────────────────────────────────────────────

    def _gui_msg(self, msg_type: str, data: Any = None) -> None:
        """Відправити повідомлення в GUI.
        
        Args:
            msg_type: Тип повідомлення
            data: Дані для передачі
        """
        if self.gui_cb:
            try:
                self.gui_cb(msg_type, data)
            except Exception as e:
                logger.debug("GUI callback error: %s", e)

    # ─── observe() ─────────────────────────────────────────────────────────────

    def _extract_python_write_targets(self, code: str) -> List[str]:
        """Best-effort detection of files written by generated Python code."""
        import os
        import re

        targets: List[str] = []
        patterns = [
            r"open\(\s*r?['\"]([^'\"]+)['\"]\s*,\s*['\"][^'\"]*w",
            r"with\s+open\(\s*r?['\"]([^'\"]+)['\"]\s*,\s*['\"][^'\"]*w",
            r"Path\(\s*r?['\"]([^'\"]+)['\"]\s*\)\.write_text\(",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, code, flags=re.IGNORECASE | re.DOTALL):
                path = match.group(1).strip()
                if path:
                    targets.append(os.path.normcase(os.path.abspath(path)))
        return sorted(set(targets))

    def _needs_screen_observation(self, task: str) -> bool:
        """Чи потрібен скріншот для цієї задачі?"""
        gui_indicators = [
            "екран", "вікно", "кнопк", "клік", "програм",
            "screen", "window", "button", "click", "app",
            "знайди на", "відкрий браузер", "натисни"
        ]
        return any(ind in task.lower() for ind in gui_indicators)

    def observe(self) -> Observation:
        """Отримати поточний стан системи (скрін + OCR + UIA + UI elements + Vision-LM)."""
        logger.info("AgentLoop.observe() called")
        obs = Observation(timestamp=time.time())

        # Якщо задача не потребує екрану — повернути мінімальне спостереження
        if self.config.skip_observe_for_simple:
            task = getattr(self, '_current_task', '')
            if not self._needs_screen_observation(task):
                print("[AgentLoop] ⏭️ Скріншот пропущено — задача не потребує екрану")
                obs.text = "[Screen observation skipped - not needed for this task]"
                return obs

        try:
            # 1. Скріншот (тільки якщо потрібен для vision/OCR)
            if (self.config.enable_vision or self.config.enable_ocr) and _SCREEN_CAPTURE_AVAILABLE:
                result = take_screenshot()
                if result.get("ok") and result.get("path"):
                    obs.screenshot_path = result["path"]
                    obs.screen_hash = self._hash_screenshot(obs.screenshot_path)

            # 2. Активне вікно (для контексту LLM)
            try:
                obs.active_window_title = self._get_active_window_title()
            except Exception as e:
                logger.debug("active window detection error: %s", e)

            # 3. OCR
            if self.config.enable_ocr and obs.screenshot_path and _SCREEN_CAPTURE_AVAILABLE:
                result_ocr = ocr_image({"image_path": obs.screenshot_path})
                if result_ocr.get("ok") and result_ocr.get("text"):
                    obs.ocr_text = result_ocr["text"]
                    obs.metadata["ocr_length"] = len(obs.ocr_text)

            # 4. UI елементи (кнопки + поля вводу)
            if self.config.enable_ui_elements and obs.screenshot_path:
                try:
                    obs.ui_elements = self._collect_ui_elements()
                except Exception as e:
                    logger.debug("ui_elements collection error: %s", e)

            # 5. UIA дерево
            if self.config.enable_ui_a and _SCREEN_CAPTURE_AVAILABLE:
                try:
                    uia = get_uia_wrapper()
                    if uia and uia.is_available():
                        focused = uia.get_focused_element()
                        if focused:
                            obs.metadata["uia_focused"] = self._safe_uia_dict(focused)
                        try:
                            tree = self._build_uia_tree(uia)
                            if tree:
                                obs.uia_tree = tree
                        except Exception as e:
                            logger.debug("uia tree error: %s", e)
                except Exception as e:
                    logger.debug("UIA error: %s", e)

            # 6. Vision-LM (якщо ввімкнено і доступно)
            if self.config.enable_vision and obs.screenshot_path:
                try:
                    from functions.llm.providers_vision import get_vision_provider
                    vision = get_vision_provider(self.assistant)
                    if vision and vision.is_available():
                        # Текстовий опис екрану
                        try:
                            desc = vision.describe(
                                obs.screenshot_path,
                                "Опиши що бачиш на екрані одним абзацом.",
                            )
                            if desc:
                                obs.vision_description = str(desc)[:1000]
                        except Exception as e:
                            logger.debug("vision describe error: %s", e)
                        # Елементи (опційно — резерв)
                        try:
                            elements = vision.detect_ui_elements(obs.screenshot_path)
                            if elements:
                                obs.metadata["vision_elements"] = elements
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug("Vision-LM error: %s", e)

        except Exception as e:
            logger.error("observe() error: %s", e)
            obs.metadata["error"] = str(e)

        logger.debug(
            "observe: screen_hash=%s, ocr_len=%d, ui_elements=%d, window=%s",
            obs.screen_hash[:8] if obs.screen_hash else "",
            len(obs.ocr_text),
            len(obs.ui_elements),
            obs.active_window_title[:40] if obs.active_window_title else "",
        )
        return obs

    def _get_active_window_title(self) -> str:
        """Повернути заголовок активного вікна (без винятків)."""
        try:
            import pygetwindow  # type: ignore
            w = pygetwindow.getActiveWindow()
            if w:
                return str(getattr(w, "title", "") or "")
        except Exception:
            pass
        try:
            import win32gui  # type: ignore
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return str(win32gui.GetWindowText(hwnd) or "")
        except Exception:
            pass
        return ""

    def _collect_ui_elements(self) -> List[Dict[str, Any]]:
        """Зібрати список видимих UI-елементів через ui_detector / app_recognizer."""
        elements: List[Dict[str, Any]] = []
        # Спроба через tools_ui_detector
        try:
            from functions.gui.tools_ui_detector import find_button_by_text, find_input_field
            buttons = find_button_by_text(text="*")
            if isinstance(buttons, dict) and buttons.get("ok"):
                for b in buttons.get("matches", []) or []:
                    elements.append({
                        "type": "button",
                        "text": b.get("text", ""),
                        "x": b.get("x"),
                        "y": b.get("y"),
                        "w": b.get("w"),
                        "h": b.get("h"),
                    })
            inputs = find_input_field()
            if isinstance(inputs, dict) and inputs.get("ok"):
                for i in inputs.get("matches", []) or []:
                    elements.append({
                        "type": "input",
                        "text": i.get("label", ""),
                        "x": i.get("x"),
                        "y": i.get("y"),
                        "w": i.get("w"),
                        "h": i.get("h"),
                    })
        except Exception as e:
            logger.debug("tools_ui_detector unavailable: %s", e)
        return elements

    def _safe_uia_dict(self, element) -> Dict[str, Any]:
        """Безпечне dict-представлення UIA-елемента."""
        try:
            return {
                "name": getattr(element, "name", ""),
                "control_type": getattr(element, "control_type", ""),
                "rect": getattr(element, "rect", None).__dict__
                    if getattr(element, "rect", None) and hasattr(getattr(element, "rect"), "__dict__")
                    else None,
                "is_enabled": getattr(element, "is_enabled", None),
                "is_visible": getattr(element, "is_visible", None),
            }
        except Exception:
            return {}

    def _build_uia_tree(self, uia) -> Optional[Dict[str, Any]]:
        """Зібрати скорочене UIA-дерево активного вікна для LLM."""
        try:
            if hasattr(uia, "get_ui_tree"):
                tree = uia.get_ui_tree()
                if isinstance(tree, dict):
                    return tree
            # Fallback — просто focused
            focused = uia.get_focused_element()
            if focused:
                return {"focused": self._safe_uia_dict(focused)}
        except Exception:
            return None
        return None

    def _hash_screenshot(self, path: str) -> str:
        """Порахувати MD5 хеш скріншоту для швидкого порівняння.
        
        Оптимізація: читаємо файл частинами для великих файлів.
        
        Args:
            path: Шлях до файлу скріншоту
            
        Returns:
            MD5 хеш файлу або порожній рядок при помилці
        """
        try:
            hash_md5 = hashlib.md5()
            with open(path, 'rb') as f:
                # Читаємо по 8KB для ефективності з великими файлами
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""

    # ─── check() ─────────────────────────────────────────────────────────────

    def check(
        self,
        action: str,
        obs: Observation,
        act_result: Optional[Dict[str, Any]] = None,
        expectations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Перевірити чи дія спрацювала.

        Перевірки (по черзі):
        1. Якщо act_result явно повернув ok=False — fail.
        2. Якщо передані expectations — перевірити через ExpectRegistry.
        3. Інакше — порівняти screen_hash зі попереднім.

        Дії, які не змінюють екран фізично (`take_screenshot`, `ocr_screen`,
        `describe_screen`, `wait_seconds`, `done`, `ask_user`), не вважаються
        провальними при незмінному екрані.
        """
        result: Dict[str, Any] = {
            "success": False,
            "screen_changed": False,
            "retry": False,
            "detail": "",
            "expectation_results": [],
        }

        non_visual_actions = {
            "take_screenshot", "ocr_screen", "find_text_on_screen",
            "find_button_by_text", "find_input_field", "describe_screen",
            "find_element_by_description", "is_screen_correct",
            "wait_seconds", "done", "ask_user", "noop",
            "uia_get_value", "uia_list_buttons", "uia_list_inputs",
            "browser_extract_text", "browser_screenshot",
        }

        # 1) act_result безпосередній провал
        if act_result is not None:
            ok_flag = act_result.get("ok") if isinstance(act_result, dict) else None
            if ok_flag is False:
                result["success"] = False
                result["retry"] = True
                result["detail"] = (
                    f"Дія повернула ok=False: {act_result.get('error', '')[:120]}"
                )
                self._prev_screen_hash = obs.screen_hash
                self._prev_screen_path = obs.screenshot_path
                return result

        # 2) Expectations через ExpectRegistry
        if expectations:
            expect_results = self._run_expectations(expectations, obs, act_result or {})
            result["expectation_results"] = expect_results
            failed = [r for r in expect_results if not r.get("ok", False)]
            if failed:
                result["success"] = False
                result["retry"] = True
                result["detail"] = (
                    "Не пройшли перевірки: "
                    + ", ".join(f"{r.get('kind')}({r.get('reason')})" for r in failed[:3])
                )
                self._prev_screen_hash = obs.screen_hash
                self._prev_screen_path = obs.screenshot_path
                return result

        # 3) Порівняння screen_hash (базовий fallback)
        if self._prev_screen_hash and obs.screen_hash:
            if self._prev_screen_hash != obs.screen_hash:
                result["screen_changed"] = True
                result["success"] = True
                result["detail"] = "Скріншот змінився"
            else:
                result["screen_changed"] = False
                # Не-візуальні дії не падають при незмінному екрані
                if action in non_visual_actions:
                    result["success"] = True
                    result["detail"] = "Дія не змінює екран — OK"
                else:
                    result["success"] = False
                    result["retry"] = True
                    result["detail"] = "Скріншот не змінився — можливо дія не спрацювала"
        else:
            result["success"] = True
            result["detail"] = "Перша ітерація / немає базового скріншоту"

        self._prev_screen_hash = obs.screen_hash
        self._prev_screen_path = obs.screenshot_path
        return result

    def _run_expectations(
        self,
        expectations: List[Dict[str, Any]],
        obs: Observation,
        act_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Виконати список ExpectSpec через ExpectRegistry.

        Кожен expectation — `{"kind": "...", "params": {...}}`.
        Повертає список dict-результатів `{kind, ok, reason}`.
        """
        out: List[Dict[str, Any]] = []
        try:
            from functions.planning.logic_expectations import (
                ExpectSpec, ExpectContext, ExpectRegistry,
            )
            # ExpectRegistry автоматично реєструє всі builtins у __init__
            if not hasattr(self, "_expect_registry"):
                self._expect_registry = ExpectRegistry()
            registry = self._expect_registry
            ctx = ExpectContext(
                task_id=self.task_id,
                handler_result=dict(act_result or {}),
                extras={"observation": {
                    "ocr_text": obs.ocr_text,
                    "active_window_title": obs.active_window_title,
                    "screenshot_path": obs.screenshot_path,
                }},
            )
            for e in expectations:
                if not isinstance(e, dict):
                    continue
                spec = ExpectSpec(
                    kind=str(e.get("kind", "")),
                    params=dict(e.get("params") or {}),
                )
                if not spec.kind:
                    continue
                try:
                    res = registry.evaluate(spec, ctx)
                    out.append({
                        "kind": res.kind,
                        "ok": res.ok,
                        "reason": res.reason,
                    })
                except Exception as exc:  # noqa: BLE001
                    out.append({
                        "kind": spec.kind,
                        "ok": False,
                        "reason": f"evaluator error: {exc}",
                    })
        except Exception as exc:  # noqa: BLE001
            logger.debug("ExpectRegistry unavailable: %s", exc)
        return out

    # ─── plan() ───────────────────────────────────────────────────────────────

    def set_compiled_plan(self, compiled_plan):
        """Встановити CompiledPlan від TaskSpec."""
        self._compiled_plan = compiled_plan

    def _save_checkpoint(self, state: AgentState) -> None:
        """Зберегти чекпоїнт."""
        if not self._checkpoint_enabled:
            return

        try:
            from functions.core_checkpoint import CheckpointData, get_checkpoint_manager

            manager = get_checkpoint_manager()
            checkpoint = CheckpointData(
                task_id=self.task_id,
                task_description=getattr(self, '_current_task', ''),
                current_step=state.step,
                total_steps=getattr(self, '_total_steps', 0),
                state={
                    "prev_screen_hash": self._prev_screen_hash,
                    "prev_screen_path": self._prev_screen_path,
                    "actions_history": state.actions_history,
                },
                metadata={"config": self.config.__dict__},
            )
            manager.save(checkpoint)
            logger.debug(f"Checkpoint saved at step {state.step}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def _load_checkpoint(self) -> Optional[AgentState]:
        """Завантажити чекпоїнт."""
        if not self._checkpoint_enabled:
            return None

        try:
            from functions.core_checkpoint import get_checkpoint_manager

            manager = get_checkpoint_manager()
            checkpoint = manager.load(self.task_id)

            if checkpoint:
                state = AgentState(step=checkpoint.current_step)
                state.actions_history = checkpoint.state.get("actions_history", [])
                self._prev_screen_hash = checkpoint.state.get("prev_screen_hash", "")
                self._prev_screen_path = checkpoint.state.get("prev_screen_path", "")
                logger.info(f"Checkpoint loaded: step {checkpoint.current_step}/{checkpoint.total_steps}")
                return state
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")

        return None

    def _get_step_from_plan(self, step: Dict[str, Any], state: AgentState, total_steps: int, from_compiled: bool) -> Dict[str, Any]:
        """Отримати план кроку з обробкою ask_user."""
        if step.get("ask_user"):
            return self._handle_ask_user_step(step, state, total_steps, from_compiled)
        return {
            "action": step.get("action", "noop"),
            "args": step.get("args", {}),
            "replan": False,
            "done": False,
            "step_index": state.step,
            "total_steps": total_steps,
            "from_compiled_plan": from_compiled,
        }

    def _plan_from_compiled(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Отримати наступний крок з CompiledPlan."""
        if not self._compiled_plan or not self._compiled_plan.steps:
            return None

        steps = self._compiled_plan.steps
        if state.step < len(steps):
            return self._get_step_from_plan(steps[state.step], state, len(steps), True)
        else:
            logger.warning(f"Step {state.step} out of range for compiled plan (len={len(steps)})")
            return {
                "action": "noop",
                "args": {},
                "replan": False,
                "done": True,
                "from_compiled_plan": True,
            }

    def _plan_from_planner(self, task: str, state: AgentState) -> Optional[Dict[str, Any]]:
        """Отримати наступний крок з Planner (тільки для першого кроку)."""
        if state.step != 0:
            return None
        
        planner = getattr(self.assistant, 'planner', None)
        if not planner:
            return None
        
        steps = planner.create_plan(task)
        if not steps or len(steps) == 0:
            logger.warning("Planner returned empty plan")
            return None
        
        first_step = steps[0]
        state.actions_history.append({"plan": steps})
        return self._get_step_from_plan(first_step, state, len(steps), False)

    def _plan_from_history(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Отримати наступний крок з історії планів."""
        if state.step == 0 or len(state.actions_history) == 0:
            return None

        if not isinstance(state.actions_history[0], dict):
            logger.warning("actions_history[0] is not a dict")
            return None

        last_plan = state.actions_history[0].get("plan", [])
        if not isinstance(last_plan, list) or len(last_plan) == 0:
            logger.warning("last_plan is not a list or is empty")
            return None

        if state.step < len(last_plan):
            return self._get_step_from_plan(last_plan[state.step], state, len(last_plan), False)

        return None

    def _plan_from_decider(
        self,
        task: str,
        obs: Observation,
        state: AgentState,
    ) -> Optional[Dict[str, Any]]:
        """Отримати наступний крок з LLM tool-calling decider."""
        if not self.config.enable_llm_decider or not self.decider or not self.decider.is_available:
            return None

        last_result = None
        if state.actions_history:
            last_entry = state.actions_history[-1]
            if isinstance(last_entry, dict) and "act_result" in last_entry:
                last_result = last_entry.get("act_result")

        # Replan після багатьох провалів
        if state.consecutive_failures >= self.config.replan_after_failures:
            try:
                action = self.decider.replan(
                    goal=task,
                    observation=obs,
                    history=state.actions_history,
                    consecutive_failures=state.consecutive_failures,
                    progress_summary=state.progress_summary,
                    context_controller=self.context_controller,
                )
                state.consecutive_failures = 0  # Reset, щоб дати новому плану шанс
            except Exception as e:
                logger.error("ActionDecider.replan() error: %s", e, exc_info=True)
                return {
                    "action": "done",
                    "args": {"summary": f"Помилка LLM при replan: {e}", "success": False},
                    "replan": False,
                    "done": True,
                    "success": False,
                    "from_decider": True,
                    "llm_error": str(e),
                }
        else:
            # stuck_warning від LoopDetector — змушує LLM змінити стратегію
            stuck_warning = ""
            if hasattr(self, 'loop_detector') and self.loop_detector.is_stuck:
                stuck_warning = self.loop_detector.get_stuck_warning_message()

            # Авто-інжекція контексту "відсутні файли" після list_directory
            # Якщо ми вже отримали список файлів через list_directory,
            # але ще не робили write_file — змушуємо LLM створювати файли
            extra_instructions = ""
            if self._list_directory_used and not self._has_written_since_list_dir:
                existing = self._last_list_dir_files
                # Визначаємо, які файли потрібно створити (загальні для PyQt6)
                required = self.config.expected_files
                missing = [f for f in required if f not in existing]
                if missing:
                    extra_instructions = (
                        "⚠️ АНАЛІЗ ПАПКИ ЗАВЕРШЕНО. "
                        f"Існують файли: {', '.join(existing[:20]) if existing else '(жодного)'}\n"
                        f"⚠️ ВІДСУТНІ ФАЙЛИ (треба створити): {', '.join(missing)}\n"
                        "⚠️ СУВОРА ЗАБОРОНА: Тобі ЗАБОРОНЕНО викликати list_directory знову! "
                        "Вміст папки не зміниться сам по собі.\n"
                        "⚠️ Наступна дія МАЄ БУТИ write_file для одного з відсутніх файлів.\n"
                        "⚠️ Після кожного write_file відмічай файл як 'DONE' і переходь до наступного."
                    )
                    logger.info("AgentLoop: авто-інжекція missing files: %s", missing)

            try:
                action = self.decider.decide(
                    goal=task,
                    observation=obs,
                    history=state.actions_history,
                    last_result=last_result,
                    progress_summary=state.progress_summary,
                    context_controller=self.context_controller,
                    stuck_warning=stuck_warning,
                    extra_instructions=extra_instructions,
                )
            except Exception as e:
                logger.error("ActionDecider.decide() error: %s", e, exc_info=True)
                return {
                    "action": "done",
                    "args": {"summary": f"Помилка LLM при decide: {e}", "success": False},
                    "replan": False,
                    "done": True,
                    "success": False,
                    "from_decider": True,
                    "llm_error": str(e),
                }

        if action.name == "noop":
            # Fallback на take_screenshot тільки якщо LLM явно повернув JSON з action="noop"
            # Якщо це помилка або недоступність — дозволяємо fallback на наступні пріоритети
            if "error" in action.reasoning or "unavailable" in action.reasoning:
                return None  # Дозволити fallback на CompiledPlan/Planner/plan_from_history
            # LLM явно повернув noop → force take_screenshot
            logger.warning("ActionDecider returned noop (from LLM), forcing take_screenshot")
            return {
                "action": "take_screenshot",
                "args": {},
                "replan": False,
                "done": False,
                "reasoning": "Forced take_screenshot instead of noop",
                "from_decider": True,
            }

        logger.info("ActionDecider: Parsed action=%s, args=%s", action.name, action.arguments)

        # Спеціальні дії
        if action.name == "done":
            return {
                "action": "done",
                "args": dict(action.arguments),
                "replan": False,
                "done": True,
                "summary": action.arguments.get("summary", ""),
                "success": bool(action.arguments.get("success", True)),
                "reasoning": action.reasoning,
                "from_decider": True,
            }

        if action.name == "ask_user":
            question = action.arguments.get("question", "Питання?")
            options = action.arguments.get("options", []) or []
            answer = ""
            if self.ask_user_callback:
                try:
                    answer = self.ask_user_callback(question, options)
                except Exception as e:
                    logger.error("ask_user callback error: %s", e)
            args = {"user_answer": answer, **action.arguments}
            return {
                "action": "noop",
                "args": args,
                "replan": False,
                "done": False,
                "user_answer": answer,
                "reasoning": action.reasoning,
                "from_decider": True,
            }

        # Звичайна дія — резолвимо alias до реального імені у registry
        real_name = self.decider.resolve_alias(action.name)
        return {
            "action": real_name,
            "args": dict(action.arguments),
            "replan": False,
            "done": False,
            "reasoning": action.reasoning,
            "tool_call_id": action.tool_call_id,
            "from_decider": True,
        }

    def plan(self, task: str, obs: Observation, state: AgentState) -> Dict[str, Any]:
        """Вирішити що робити далі.

        Пріоритет:
        1. LLM ActionDecider (tool-calling)
        2. CompiledPlan (від TaskSpec)
        3. Planner (legacy, тільки для першого кроку)
        4. Історія планів
        5. noop / done

        Повертає: {"action": "...", "args": {...}, "replan": bool, "done": bool}
        """
        # Пріоритет 1: LLM ActionDecider
        result = self._plan_from_decider(task, obs, state)
        if result:
            return result

        # Пріоритет 2: CompiledPlan від TaskSpec
        result = self._plan_from_compiled(state)
        if result:
            return result

        # Пріоритет 3: Planner (для першого кроку)
        result = self._plan_from_planner(task, state)
        if result:
            return result

        # Пріоритет 4: Історія планів
        result = self._plan_from_history(state)
        if result:
            return result

        # Fallback — noop / done
        return {
            "action": "noop",
            "args": {},
            "replan": False,
            "done": True,
        }

    def _handle_ask_user_step(self, step: Dict[str, Any], state: AgentState, total_steps: int, from_compiled: bool) -> Dict[str, Any]:
        """Обробити крок що вимагає запиту користувача."""
        question = step.get("ask_user", {}).get("question", "Питання?")
        options = step.get("ask_user", {}).get("options", [])

        if self.ask_user_callback:
            try:
                answer = self.ask_user_callback(question, options)
                # Зберігаємо відповідь в args
                args = step.get("args", {})
                args["user_answer"] = answer
                return {
                    "action": step.get("action", "noop"),
                    "args": args,
                    "replan": False,
                    "done": False,
                    "step_index": state.step,
                    "total_steps": total_steps,
                    "from_compiled_plan": from_compiled,
                    "user_answer": answer,
                }
            except Exception as e:
                logger.error("ask_user callback error: %s", e)
                # Fallback — пропускаємо крок
                return {
                    "action": "noop",
                    "args": {},
                    "replan": False,
                    "done": False,
                    "step_index": state.step,
                    "total_steps": total_steps,
                    "from_compiled_plan": from_compiled,
                    "error": str(e),
                }
        else:
            # Fallback — пропускаємо крок
            logger.warning("ask_user_callback not set, skipping ask_user step")
            return {
                "action": step.get("action", "noop"),
                "args": step.get("args", {}),
                "replan": False,
                "done": False,
                "step_index": state.step,
                "total_steps": total_steps,
                "from_compiled_plan": from_compiled,
                "error": "ask_user_callback not set",
            }

    # ─── act() ────────────────────────────────────────────────────────────────

    def act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Виконати дію через registry."""
        action = plan.get("action", "noop")
        args = plan.get("args", {})

        try:
            if action == "noop":
                return {"ok": True, "result": "noop"}

            # Виконати через registry (auto_create=False — AgentLoop не створює нові функції)
            result = self.registry.execute_function(action, args, auto_create=False)
            if isinstance(result, dict):
                return result
            return {"ok": True, "result": str(result)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── run() ────────────────────────────────────────────────────────────────

    def _should_stop(self, state: AgentState, start_time: float) -> bool:
        """Перевірити чи треба зупинити виконання."""
        if self._stop_flag:
            logger.info("Stop requested by user")
            return True
        if state.done:
            return True
        if state.step >= self.config.max_steps:
            return True
        if time.time() - start_time > self.config.max_duration_seconds:
            logger.warning("Max duration exceeded")
            return True
        return False

    def request_stop(self):
        """Запит на зупинку AgentLoop (з GUI кнопки 'Стоп')."""
        self._stop_flag = True

    def _execute_single_step(self, task: str, state: AgentState, start_time: float) -> bool:
        """Виконати одну ітерацію циклу. Повертає True якщо треба продовжувати."""
        logger.info("AgentLoop._execute_single_step() step=%d", state.step)
        print(f"[AgentLoop] ▶ Крок {state.step + 1}/{self.config.max_steps}: починаю виконання...")
        # 1. Observe
        obs = self.observe()
        state.observations.append(obs)
        # Тримаємо тільки останні 5 observations щоб не роздувати пам'ять
        if len(state.observations) > 5:
            state.observations = state.observations[-5:]

        # 2. Plan
        try:
            plan = self.plan(task, obs, state)
        except Exception as e:
            logger.error(f"Error in plan(): {e}", exc_info=True)
            state.done = True
            state.success = False
            state.done_summary = f"Помилка планування: {e}"
            return False

        if plan.get("done"):
            summary = plan.get("summary") or plan.get("args", {}).get("summary", "")
            success = plan.get("success", True)
            state.done = True
            state.success = bool(success)
            state.done_summary = str(summary or "")
            if summary:
                self._gui_msg('add_message', ('assistant', f'✅ {summary}' if success else f'❌ {summary}'))
            logger.info("Plan says done (success=%s): %s", success, summary[:100] if summary else "")
            return False

        action = plan.get("action", "noop")
        args = plan.get("args", {})
        expectations = plan.get("expectations") or plan.get("expect")
        reasoning = plan.get("reasoning", "")

        # ─── Loop detection ─────────────────────────────────────────────
        if action != "noop" and action != "done" and action != "ask_user":
            if self.loop_detector.is_looping(action, args):
                logger.warning("LoopDetector: виявлено зациклення дії '%s'", action)
                self._gui_msg('add_message', ('assistant',
                    f'⚠️ Зациклення: дія \'{action}\' повторюється. Пробую інший підхід...'))
                # is_stuck вже встановлено в LoopDetector
                # На наступній ітерації decider отримає stuck_warning
            elif self.loop_detector.is_stuck:
                # Якщо раніше був stuck але ця дія інша — не скидаємо,
                # скинеться після успішної дії (on_action_success)
                pass

        print(f"[AgentLoop]   🎯 Action: {action}")
        if args:
            print(f"[AgentLoop]   📋 Args: {args}")
        if reasoning:
            print(f"[AgentLoop]   💭 Reasoning: {reasoning[:100]}...")

        status_msg = f'▶ Крок {state.step + 1}/{self.config.max_steps}: {action}'
        if reasoning:
            lines = str(reasoning).strip().splitlines()
            short = lines[0][:80] if lines else ""
            if short:
                status_msg += f' — {short}'
        self._gui_msg('update_status', status_msg)

        # ─── Блокування повторного читання неіснуючих файлів ────────
        if action == "read_code_file":
            filepath = args.get('filepath', '')
            if filepath in self.failed_reads:
                # Цей файл вже був не знайдено — блокуємо повторне читання
                logger.warning("Блоковано повторне читання неіснуючого файлу: %s", filepath)
                print(f"[AgentLoop]   ⛔ Блоковано повторне читання неіснуючого файлу: {filepath}")
                self._gui_msg('add_message', ('assistant',
                    f'⛔ ПОМИЛКА КРИТИЧНА: Файл {filepath} вже був не знайдено. ВІН НЕ З\'ЯВИТЬСЯ САМ. Тобі ЗАБОРОНЕНО читати його знову. Негайно використай write_file, щоб СТВОРИТИ його.'))
                state.consecutive_failures += 1
                state.step += 1
                time.sleep(0.3)
                return True  # Продовжуємо цикл, LLM отримає stuck_warning

        # ─── Блокування list_directory після першого разу (СУВОРА ЗАБОРОНА) ─────
        if action == "list_directory":
            if self._list_directory_used and not self._has_written_since_list_dir:
                # list_directory вже викликаний, а write_file ще не було — БЛОКУЄМО
                logger.warning("СУВОРО Блоковано повторний list_directory (ще не було write_file)")
                print(f"[AgentLoop]   ⛔ СУВОРО Блоковано повторний list_directory (ще не було write_file)")
                self._gui_msg('add_message', ('assistant',
                    '⛔ КРИТИЧНА ПОМИЛКА: Ти ВЖЕ викликав list_directory. Вміст папки НЕ ЗМІНИТЬСЯ, поки ти не створиш файл. Твоя наступна дія МАЄ БУТИ write_file. ЗАБОРОНЕНО викликати list_directory знову без write_file!'))
                state.consecutive_failures += 1
                state.step += 1
                time.sleep(0.3)
                return True  # Продовжуємо цикл, LLM отримає stuck_warning

            # Рахуємо, скільки разів він викликав list_directory за останні 4 кроків
            recent_actions = [a.get('action') for a in state.actions_history[-4:]]
            if recent_actions.count('list_directory') >= 2:
                logger.warning("Блоковано повторний list_directory (A-B-A-B цикл)")
                print(f"[AgentLoop]   ⛔ Блоковано повторний list_directory")
                self._gui_msg('add_message', ('assistant',
                    '⛔ ПОМИЛКА: Ти вже двічі перевіряв папку за останні кроки. Досить спостерігати! Почни створювати відсутні файли (write_file).'))
                state.consecutive_failures += 1
                state.step += 1
                time.sleep(0.3)
                return True  # Продовжуємо цикл, LLM отримає stuck_warning
        # ─── Блокування повторних write_file (ідемпотентна операція) ────
        if action == "write_file":
            # Створюємо fingerprint для порівняння
            import json as _json
            try:
                fp = f"write_file:{args.get('filepath', '')}:{_json.dumps(args.get('content', ''), sort_keys=True)}"
            except Exception:
                fp = f"write_file:{args.get('filepath', '')}:{str(args.get('content', ''))}"
            
            if fp in self._blocked_write_fingerprints:
                # Цей write_file вже був виконаний — це ідемпотентна операція
                # Повертаємо ok=True, щоб LLM отримала підтвердження "вже записано"
                # і не намагалась писати той самий файл знову
                logger.info("Ідемпотентний write_file пропущено: %s", args.get('filepath', ''))
                print(f"[AgentLoop]   ⏭️ Ідемпотентний write_file пропущено: {args.get('filepath', '')}")
                self._gui_msg('add_message', ('assistant',
                    f'⏭️ Файл {args.get("filepath", "")} вже існує, пропущено'))
                # Повертаємо ok=True + спеціальний результат — LLM отримує
                # сигнал "все ок, файл вже записаний, іди далі"
                act_result = {"ok": True, "result": "already written, skipped"}
                # Скидаємо consecutive_failures (це не помилка)
                state.consecutive_failures = 0
                # Не блокуємо в LoopDetector — скидаємо is_stuck
                self.loop_detector.on_action_success()
                # Додаємо в історію дій для LLM контексту
                action_data = {
                    "step": state.step,
                    "action": action,
                    "args": args,
                    "act_result": act_result,
                    "check_result": {"success": True, "detail": "already written, skipped"},
                    "from_decider": plan.get("from_decider", False),
                    "reasoning": reasoning,
                }
                state.actions_history.append(action_data)
                state.step += 1
                time.sleep(0.3)
                return True  # Продовжуємо цикл — LLM отримає ok=True в історії

        if action == "execute_python":
            code = str(args.get("code", "") or "")
            write_targets = self._extract_python_write_targets(code)
            repeated_targets = [t for t in write_targets if t in self._execute_python_write_targets]
            if repeated_targets:
                target_list = ", ".join(repeated_targets)
                logger.info("Repeated execute_python file write skipped: %s", target_list)
                print(f"[AgentLoop]   ⏭️ Repeated execute_python file write skipped: {target_list}")
                self._gui_msg('add_message', ('assistant',
                    f'⏭️ Повторний execute_python для запису того самого файлу пропущено: {target_list}. Використай write_file або done.'))
                act_result = {"ok": True, "result": f"repeated execute_python file write skipped: {target_list}"}
                action_data = {
                    "step": state.step,
                    "action": action,
                    "args": args,
                    "act_result": act_result,
                    "check_result": {"success": True, "detail": "repeated execute_python file write skipped"},
                    "from_decider": plan.get("from_decider", False),
                    "reasoning": reasoning,
                }
                state.actions_history.append(action_data)
                state.consecutive_failures = 0
                state.step += 1
                time.sleep(0.3)
                return True
            self._execute_python_write_targets.update(write_targets)

        # 3. Act
        act_result = self.act(plan)
        
        # ─── Зберігаємо результат list_directory для контексту ─────────
        if action == "list_directory" and act_result.get("ok"):
            self._list_directory_used = True
            # Зберегти список файлів з результату
            result = act_result.get('result', '')
            if isinstance(result, str):
                self._last_list_dir_files = [f.strip() for f in result.split('\n') if f.strip() and not f.startswith('[')]
            elif isinstance(result, list):
                self._last_list_dir_files = [str(f) for f in result]
            else:
                self._last_list_dir_files = []
            logger.info("AgentLoop: list_directory збережено (%d файлів)", len(self._last_list_dir_files))

        # ─── Автоматичний прогрес після write_file ──────────────────────
        if action in ("write_file", "edit_file") and act_result.get("ok"):
            # Позначаємо що був хоч один write_file після list_directory
            if action == "write_file":
                self._has_written_since_list_dir = True
                # Додаємо до blocked, щоб блокувати повторні записи того самого файлу
                try:
                    fp = f"write_file:{args.get('filepath', '')}:{_json.dumps(args.get('content', ''), sort_keys=True)}"
                except Exception:
                    fp = f"write_file:{args.get('filepath', '')}:{str(args.get('content', ''))}"
                self._blocked_write_fingerprints.add(fp)
            
            # Додаємо прогрес
            filepath = args.get('filepath', '') or args.get('filename', '')
            filename = filepath.split('/')[-1].split('\\')[-1] if filepath else 'unknown'
            progress_line = f"✅ Створено: {filename}"
            if progress_line not in state.progress_summary:
                state.progress_summary += f"\n{progress_line}"
                logger.info("AgentLoop: додано прогрес: %s", progress_line)
            
            # ─── Punkt 3: Автоматична синтаксична перевірка .py файлів ──
            if filepath.endswith('.py'):
                # Отримуємо вміст: для write_file — "content", для edit_file — "new_content"
                content = (args.get('content') or args.get('new_content') or '')
                try:
                    compile(content, filepath, 'exec')
                    act_result["auto_test_passed"] = True
                    act_result["auto_test_error"] = ""
                    logger.info("AgentLoop: auto_test_passed=True for %s", filename)
                    print(f"[AgentLoop]   ✅ Синтаксис OK: {filename}")
                except SyntaxError as e:
                    act_result["auto_test_passed"] = False
                    act_result["auto_test_error"] = str(e)
                    logger.warning("AgentLoop: auto_test_passed=False for %s: %s", filename, e)
                    print(f"[AgentLoop]   ❌ Синтаксична помилка: {filename}: {e}")
        state.last_action = action

        print(f"[AgentLoop]   ✅ Result: {act_result.get('ok', False)}")
        if act_result.get('result'):
            print(f"[AgentLoop]   📄 Output: {str(act_result.get('result', ''))[:1000]}...")
        if act_result.get('error'):
            print(f"[AgentLoop]   ❌ Error: {act_result.get('error')}")

        # ─── Punkt 4: Repair-loop для коду (LLM виправляє синтаксичні помилки) ──
        if act_result.get("auto_test_passed") is False and act_result.get("auto_test_error"):
            # Не блокуємо весь план — даємо шанс виправити
            _code_repair_tries = getattr(self, '_code_repair_counter', 0)
            if _code_repair_tries < 2:
                self._code_repair_counter = _code_repair_tries + 1
                filepath = args.get('filepath', '') or args.get('filename', '')
                content = args.get('content') or args.get('new_content') or ''
                error_text = act_result.get("auto_test_error", "")
                
                print(f"[AgentLoop]   🔧 Repair-loop: спроба {self._code_repair_counter}/2 для {filename}")
                logger.info("Code repair attempt %d/2 for %s: %s", self._code_repair_counter, filename, error_text)
                
                # Формуємо repair_prompt для LLM
                repair_prompt = (
                    f"⚠️ Синтаксична помилка у файлі '{filepath}'.\n\n"
                    f"ПОМИЛКА:\n{error_text}\n\n"
                    f"НЕВДАЛИЙ КОД:\n```python\n{content}\n```\n\n"
                    f"ЗАВДАННЯ: '{self._current_task}'\n\n"
                    "Поверни JSON з дією edit_file та виправленим вмістом файлу. "
                    "Не змінюй логіку, тільки виправ синтаксичні помилки.\n\n"
                    'Формат: {"action": "edit_file", "args": {"filepath": "...", "new_content": "..."}, "reasoning": "..."}\n'
                    "Відповідай ТІЛЬКИ JSON."
                )
                
                try:
                    if hasattr(self, 'decider') and self.decider is not None and self.decider.is_available:
                        messages = [
                            {"role": "system", "content": "Ти — repair-агент, який виправляє синтаксичні помилки Python. Повертай ТІЛЬКИ JSON."},
                            {"role": "user", "content": repair_prompt},
                        ]
                        response = self.decider._ask_llm_with_tools(
                            messages=messages,
                            tools=[],
                            tool_choice=None,
                        )
                        content_response = str(getattr(response, "content", "") or "").strip()
                        
                        # Парсимо JSON з відповіді
                        import re as _re
                        json_match = _re.search(r'\{.*"action".*"args".*\}', content_response, _re.DOTALL)
                        if json_match:
                            repair_json = json.loads(json_match.group(0))
                            if repair_json.get("action") == "edit_file":
                                repair_args = repair_json.get("args", {})
                                repair_filepath = repair_args.get("filepath", filepath)
                                repair_content = repair_args.get("new_content", "")
                                
                                if repair_content:
                                    # Виконуємо edit_file через registry
                                    fix_result = self.act({
                                        "action": "edit_file",
                                        "args": {"filepath": repair_filepath, "new_content": repair_content},
                                    })
                                    
                                    if fix_result.get("ok"):
                                        # Повторна перевірка
                                        try:
                                            compile(repair_content, repair_filepath, 'exec')
                                            act_result["auto_test_passed"] = True
                                            act_result["auto_test_error"] = ""
                                            print(f"[AgentLoop]   ✅ Repair-loop: виправлено! Синтаксис OK для {filename}")
                                            logger.info("Code repair SUCCESS for %s", filename)
                                            # Скидаємо consecutive_failures — все ок
                                            state.consecutive_failures = 0
                                        except SyntaxError as e2:
                                            print(f"[AgentLoop]   ❌ Repair-loop: друга спроба теж з помилкою: {e2}")
                                            logger.warning("Code repair FAILED after fix for %s: %s", filename, e2)
                                            act_result["auto_test_error"] = str(e2)
                                    else:
                                        print(f"[AgentLoop]   ❌ Repair-loop: edit_file не вдався: {fix_result.get('error', '')}")
                                else:
                                    print(f"[AgentLoop]   ❌ Repair-loop: LLM повернула порожній код")
                        else:
                            print(f"[AgentLoop]   ❌ Repair-loop: LLM не повернула JSON або JSON невалідний")
                    else:
                        print(f"[AgentLoop]   ⏭️ Repair-loop: LLM decider недоступний, пропускаємо")
                except Exception as repair_e:
                    print(f"[AgentLoop]   ❌ Repair-loop: помилка: {repair_e}")
                    logger.warning("Code repair exception: %s", repair_e)
            else:
                print(f"[AgentLoop]   ⏭️ Repair-loop: досягнуто ліміту спроб (2/2), позначаємо як помилку")
                logger.warning("Code repair max attempts reached for %s", args.get('filepath', '') or args.get('filename', ''))

        # ─── Запам'ятовуємо відсутні файли ───────────────────────────
        if action == "read_code_file" and not act_result.get("ok"):
            result_str = str(act_result.get('error', '') + str(act_result.get('result', '')))
            if "Файл не знайдено" in result_str or "не існує" in result_str or "No such file" in result_str:
                filepath = args.get('filepath', '')
                self.failed_reads.add(filepath)
                logger.info("Запам'ятовано відсутній файл: %s", filepath)

        # 4. Check (з act_result + expectations)
        check_result = self.check(action, obs, act_result=act_result, expectations=expectations)
        state.last_result = check_result.get("detail", "")

        print(f"[AgentLoop]   🔍 Check: {check_result.get('success', False)}")
        if check_result.get('detail'):
            print(f"[AgentLoop]   📝 Detail: {check_result.get('detail')[:100]}...")

        # Відправити крок в GUI план
        self._gui_msg('step_update', {
            "step": state.step,
            "action": action,
            "success": check_result.get('success', False),
            "reasoning": reasoning[:100] if reasoning else "",
            "result": str(act_result.get('result', ''))[:100] if act_result.get('result') else ""
        })

        # Лог в історію
        action_data = {
            "step": state.step,
            "action": action,
            "args": args,
            "act_result": act_result,
            "check_result": check_result,
            "from_decider": plan.get("from_decider", False),
            "reasoning": reasoning,
        }
        state.actions_history.append(action_data)
        
        # Використовуємо ContextController якщо є, інакше fallback на стару логіку
        if self.context_controller:
            # Додаємо подію в контролер — він сам вирішить коли підсумовувати
            event_type = "action_success" if check_result.get("success") else "action_failed"
            self.context_controller.add_event(event_type, action_data)
            # Оновлюємо progress_summary з контролера для сумісності
            state.progress_summary = self.context_controller.global_summary
        else:
            # Fallback на стару логіку з progress_summary
            threshold = self.config.summary_threshold + self.config.keep_recent_actions
            if len(state.actions_history) > threshold:
                from functions.context_manager import summarize_progress, format_actions_for_summary
                
                # Беремо старі дії для підсумовування
                to_summarize = state.actions_history[:-self.config.keep_recent_actions]
                # Залишаємо останні дії детальними
                state.actions_history = state.actions_history[-self.config.keep_recent_actions:]
                
                # Якщо є decider з LLM — підсумовуємо через LLM
                if self.decider and self.decider.is_available:
                    def ask_llm_wrapper(prompt: str, system_prompt: Optional[str] = None) -> str:
                        """Wrapper для виклику LLM через decider."""
                        messages = [{"role": "system", "content": system_prompt or ""}]
                        messages.append({"role": "user", "content": prompt})
                        response = self.decider._ask_llm_with_tools(
                            messages=messages,
                            tools=[],
                            tool_choice=None
                        )
                        return str(getattr(response, "content", "") or "")
                    
                    state.progress_summary = summarize_progress(
                        to_summarize,
                        state.progress_summary,
                        ask_llm_wrapper
                    )
                    logger.info("AgentLoop: Progress summary updated: %s...", state.progress_summary[:100])
                else:
                    # Fallback без LLM — просте об'єднання
                    state.progress_summary += "\n" + format_actions_for_summary(to_summarize)
                    state.progress_summary = state.progress_summary[:1000]

        # Зберегти чекпоїнт (через інтервал)
        if self._checkpoint_enabled and state.step % self.config.checkpoint_interval_steps == 0:
            self._save_checkpoint(state)

        # Облік провалів
        if check_result.get("success"):
            state.consecutive_failures = 0
            self.loop_detector.on_action_success()
        else:
            state.consecutive_failures += 1
            state.total_failures += 1
            if check_result.get("retry"):
                logger.warning(
                    "Action %s failed (consecutive=%d): %s",
                    action, state.consecutive_failures, check_result.get("detail", ""),
                )

            # Repair Loop: спробувати адаптивне відновлення
            if (
                self.config.enable_repair
                and self.repairer is not None
                and state.consecutive_failures >= self.config.repair_after_failures
                and getattr(self.repairer, "is_available", False)
            ):
                self._try_repair(action, args, reasoning, act_result, obs, state, expectations)

        state.step += 1
        time.sleep(0.3)
        return True

    def _try_repair(
        self,
        action: str,
        args: Dict[str, Any],
        reasoning: str,
        act_result: Dict[str, Any],
        obs: Observation,
        state: AgentState,
        expectations: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Викликати StepRepairer для адаптивного відновлення.

        Модифікує state на основі рішення:
        - RETRY: додає модифіковану дію в actions_history із прапором "repair_retry"
                 (наступна ітерація plan() використає її через decider context)
        - SKIP: ресетить consecutive_failures (продовжуємо)
        - REPLAN: ресетить consecutive_failures (decider зробить replan на наступному кроці)
        - STOP: ставить state.done=True із summary
        """
        try:
            decision = self.repairer.repair(
                failed_action={"action": action, "args": args, "reasoning": reasoning},
                act_result=act_result,
                observation=obs,
                history=state.actions_history,
                expectations=expectations,
            )
        except Exception as e:
            logger.warning("Repair call failed: %s", e)
            return

        if decision is None:
            return

        from functions.planning.logic_repair_loop import RepairAction
        logger.info("Repair decision: %s — %s", decision.action.value, decision.reason)
        self._gui_msg('update_status', f'🔧 Repair: {decision.action.value} — {decision.reason[:60]}')

        if decision.action == RepairAction.RETRY and decision.modified_action:
            # Додаємо «підказку» для наступного planning кроку
            modified = decision.modified_action
            state.actions_history.append({
                "step": state.step,
                "action": "_repair_hint",
                "args": modified,
                "act_result": {"ok": True, "result": "repair retry"},
                "check_result": {"success": True, "detail": decision.reason},
                "from_repairer": True,
            })
            state.consecutive_failures = 0
        elif decision.action == RepairAction.SKIP:
            state.consecutive_failures = 0
        elif decision.action == RepairAction.REPLAN:
            # Виставляємо лічильник на поріг replan, щоб decider зробив replan на наступній ітерації
            state.consecutive_failures = self.config.replan_after_failures
        elif decision.action == RepairAction.STOP:
            # Спробуємо Open Interpreter fallback перед зупинкою
            self._try_open_interpreter_fallback(self._current_task or "unknown task", state)
            if not state.success:
                state.done = True
                state.success = False
                state.done_summary = f"Зупинено repair-стратегом: {decision.reason}"

    def _cleanup_checkpoint(self) -> None:
        """Видалити чекпоїнт після завершення."""
        if not self._checkpoint_enabled:
            return
        
        try:
            from functions.core_checkpoint import get_checkpoint_manager
            manager = get_checkpoint_manager()
            manager.delete(self.task_id)
            logger.info("Checkpoint deleted after completion")
        except Exception as e:
            logger.warning(f"Failed to delete checkpoint: {e}")

    def _send_completion_summary(self, state: AgentState, duration: float) -> None:
        """Відправити summary про завершення в GUI з перевіркою чек-лісту."""
        self._gui_msg('execution_finished', None)

        # Перевірка файлів тільки якщо expected_files задано (не порожній список)
        required_files = self.config.expected_files
        is_incomplete = False
        missing_files = []

        if required_files:
            import os
            target_dir = "."

            # Пробуємо отримати правильну директорію з context_controller
            if self.context_controller and hasattr(self.context_controller, 'target_dir'):
                target_dir = self.context_controller.target_dir
            elif hasattr(self.assistant, 'target_dir'):
                target_dir = self.assistant.target_dir
            else:
                # Пробуємо витягти з останнього list_directory з історії
                for h in reversed(state.actions_history):
                    if h.get('action') == 'list_directory':
                        dir_arg = h.get('args', {}).get('directory', '')
                        if dir_arg and os.path.isdir(dir_arg):
                            target_dir = dir_arg
                            break

            # Перевіряємо наявність файлів згідно з конфігурацією
            try:
                actual_files = os.listdir(target_dir) if os.path.isdir(target_dir) else []
            except Exception:
                actual_files = []

            missing_files = [f for f in required_files if f not in actual_files]
            is_incomplete = len(missing_files) > 0

        summary = f"📊 Agent loop завершено: {state.step} кроків за {duration:.1f}с"
        if state.success and not is_incomplete:
            summary += " ✅ Успішно"
        elif is_incomplete:
            summary += f" ⚠️ Незавершено (відсутні: {', '.join(missing_files)})"
            state.success = False  # Оновлюємо стан якщо незавершено
        else:
            summary += " ⚠️ Не завершено"
        self._gui_msg('add_message', ('assistant', summary))
        self._gui_msg('update_status', '✅ Готовий до роботи')

    def _try_open_interpreter_fallback(self, task: str, state: AgentState) -> None:
        """Спробувати вирішити задачу через Open Interpreter як останній рятівник.

        Викликається коли AgentLoop не зміг виконати задачу.
        Передає повний контекст: завдання, створені файли, цільову папку.
        """
        from functions.tools.aaa_open_interpreter import is_available, oi_execute_with_healing

        if not is_available():
            logger.info("Open Interpreter недоступний, пропускаємо fallback")
            return

        # Формуємо контекст з історії виконання (actions_history, не observations)
        history_summary = "\n".join([
            f"- Крок {i+1}: {h.get('action', '?')} → {h.get('check_result', {}).get('success', '?')}"
            for i, h in enumerate(state.actions_history)
        ])

        # Формуємо список вже створених файлів з історії
        created_files = []
        for h in state.actions_history:
            if h.get('action') == 'write_file':
                filepath = h.get('args', {}).get('filepath', '')
                if filepath and filepath not in created_files:
                    created_files.append(filepath)

        files_summary = "\n".join([f"- {f}" for f in created_files]) if created_files else "(немає створених файлів)"

        # Отримуємо цільову директорію з context_controller або використовуємо поточну
        target_dir = "."
        if self.context_controller and hasattr(self.context_controller, 'target_dir'):
            target_dir = self.context_controller.target_dir
        elif hasattr(self.assistant, 'target_dir'):
            target_dir = self.assistant.target_dir

        # Отримуємо advice від LoopDetector якщо є
        loop_advice = ""
        if hasattr(self, 'loop_detector') and self.loop_detector.is_stuck:
            last_event = self.loop_detector.loop_events[-1] if self.loop_detector.loop_events else None
            if last_event:
                action_dict = {"action": last_event.action, "args": {}}
                loop_advice = self.loop_detector.get_loop_advice(action_dict)

        # Отримуємо список файлів в цільовій директорії для визначення відсутніх
        import os
        try:
            actual_files = os.listdir(target_dir) if os.path.isdir(target_dir) else []
        except Exception:
            actual_files = []

        # Визначаємо відсутні файли згідно з конфігурацією
        required_files = self.config.expected_files
        missing_files = [f for f in required_files if f not in actual_files]

        # Формуємо ПОВНИЙ промпт для Open Interpreter (замість просто коментарів)
        # Це дає Open Interpreter розуміння що проект НЕ завершено і треба допрацювати
        fallback_prompt = f"""
Мій попередній агент (Марк) зациклився.

ОРИГІНАЛЬНЕ ЗАВДАННЯ: "{task}"

ПОТОЧНИЙ СТАН:
- Всього кроків виконано: {state.step}
- Промахів поспіль: {state.consecutive_failures}
- Історія виконання:
{history_summary}

ВЖЕ СТВОРЕНО ФАЙЛІВ:
{files_summary}

ФАКТИЧНІ ФАЙЛИ В ПАПЦІ "{target_dir}":
{chr(10).join([f"- {f}" for f in actual_files]) if actual_files else "(папка порожня)"}

ВІДСУТНІ ФАЙЛИ (ТРЕБА СТВОРИТИ):
{chr(10).join([f"- {f}" for f in missing_files]) if missing_files else "(всі файли є)"}

ПРИЧИНА ЗУПИНКИ:
{loop_advice if loop_advice else "Я не зміг виконати завдання через зациклення або помилки."}

ТВОЯ МЕТА:
1. Створити відсутні файли: {', '.join(missing_files) if missing_files else '(ніяких)'}
2. Використовувати BaseTab та constants.py (якщо вони є) для створення вкладок.
3. Завершити проект, щоб він став робочим.
4. НЕ роби list_directory більше одного разу. Одразу пиши код.
5. Ти маєш повний доступ до файлової системи та інтернету.
Використовуй os, pathlib, subprocess для виконання задачі.
"""

        logger.info("Спробуємо Open Interpreter fallback для задачі: %s", task[:50])
        self._gui_msg('add_message', ('assistant', '🔄 Спроба вирішення через Open Interpreter...'))

        try:
            result = oi_execute_with_healing(
                code=fallback_prompt,
                task_description=task,
                auto_run=True
            )

            if getattr(result, 'success', False):
                logger.info("Open Interpreter fallback успішний")
                output = getattr(result, 'output', '')
                self._gui_msg('add_message', ('assistant', f'✅ Open Interpreter вирішив: {str(output)[:200]}'))
                state.success = True
                state.done_summary = f'Вирішено через Open Interpreter: {str(output)[:200]}'
            else:
                error = getattr(result, 'error', 'невідома помилка')
                logger.warning("Open Interpreter fallback не вдався: %s", error)
                self._gui_msg('add_message', ('assistant', f'❌ Open Interpreter не зміг вирішити: {str(error)[:200]}'))
        except Exception as e:
            logger.error("Помилка виклику Open Interpreter fallback: %s", e)
            self._gui_msg('add_message', ('assistant', f'❌ Помилка Open Interpreter: {str(e)[:200]}'))

    def run(self, task: str) -> Dict[str, Any]:
        """Основний цикл агента: observe → plan → act → check.

        Args:
            task: Опис задачі

        Returns:
            dict з результатами виконання
        """
        logger.info("AgentLoop.run() called with task: %s", task[:50])
        self._current_task = task
        self._stop_flag = False
        # Скидаємо LoopDetector для нової сесії
        self.loop_detector.full_reset()
        # Скидаємо бюджет repair-спроб для нової сесії
        if self.repairer is not None and hasattr(self.repairer, "reset"):
            try:
                self.repairer.reset()
            except Exception:
                pass
        state = self._load_checkpoint() or AgentState()
        start_time = time.time()

        # Скидаємо стан list_directory для нової сесії
        self._list_directory_used = False
        self._last_list_dir_files = []
        self._has_written_since_list_dir = False

        self._gui_msg('update_status', '🔄 Agent loop: observe → plan → act → check')
        self._gui_msg('execution_started', None)

        try:
            while not self._should_stop(state, start_time):
                logger.info("AgentLoop: step=%d, max_steps=%d", state.step, self.config.max_steps)

                # Перевіряємо на штрафний ліміт (друге зациклення) - негайний fallback
                if self.loop_detector.should_force_fallback():
                    logger.warning("Штрафний ліміт зациклень (%d циклів), примусовий Open Interpreter fallback",
                                   self.loop_detector.loop_count)
                    self._try_open_interpreter_fallback(task, state)
                    if state.success or state.done:
                        break

                # Перевіряємо на глибоке зациклення (багато циклів)
                # LoopDetector вже виявляє поодинокі цикли в _execute_single_step
                # Тут — захист від повторюваних циклів (агент зациклився >3 разів)
                if self.loop_detector.total_loops_detected >= 3:
                    logger.warning("Глибоке зациклення (%d циклів), спробуємо Open Interpreter fallback",
                                   self.loop_detector.total_loops_detected)
                    self._try_open_interpreter_fallback(task, state)
                    if state.success or state.done:
                        break

                if not self._execute_single_step(task, state, start_time):
                    break
        finally:
            duration = time.time() - start_time
            self._cleanup_checkpoint()

            # Open Interpreter fallback як останній рятівник
            if not state.success and not state.done:
                self._try_open_interpreter_fallback(task, state)

            self._send_completion_summary(state, duration)

        return {
            "ok": state.success,
            "steps": state.step,
            "duration": duration,
            "summary": state.done_summary,
            "state": state,
        }


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
    "AgentLoop",
    "AgentLoopConfig",
    "AgentState",
    "Observation",
    "build_default_decider",
]
