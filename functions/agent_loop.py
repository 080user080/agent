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
    from .tools_screen_capture import take_screenshot
    from .tools_ocr import ocr_image
    from .tools_ui_accessibility import get_uia_wrapper
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


@dataclass
class AgentLoopConfig:
    """Конфігурація AgentLoop."""
    max_steps: int = 50
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
    replan_after_failures: int = 3
    repair_after_failures: int = 2  # Викликати repairer при N consecutive failures
    enable_repair: bool = True


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
        "Ти — агент, який аналізує код і виконує задачі на комп'ютері. "
        "Тобі дано задачу і поточний стан (скріншот, файли, історія дій). "
        "Твоя робота — повернути ОДИН наступний крок як JSON об'єкт. "
        "Формат: {\"action\": \"ім'я_інструменту\", \"args\": {...}, \"reasoning\": \"пояснення\"}. "
        "ВАЖЛИВО: args ОБОВ'ЯЗКОВО має бути словником з параметрами інструменту. "
        "Доступні інструменти з параметрами: "
        "- list_directory: args={\"directory\": \"шлях_до_директорії\"} "
        "- read_code_file: args={\"filepath\": \"шлях_до_файлу\"} "
        "- done: args={\"summary\": \"короткий результат\"} "
        "- ask_user: args={\"question\": \"питання\"} "
        "ВАЖЛИВО: Виконуй не більше 3-5 дій для задачі аналізу коду. "
        "Після 2-3 кроків обов'язково викликай done з summary. "
        "Коли задача виконана — action=\"done\", args={\"summary\": \"короткий результат\"}. "
        "Якщо потрібна інформація від користувача — action=\"ask_user\". "
        "ВІДПОВІДАЙ ТІЛЬКИ JSON, без markdown, без пояснень поза JSON."
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

    def _format_observation(self, obs: Optional[Observation]) -> str:
        if not obs:
            return "(немає спостереження)"
        parts: List[str] = []
        if obs.active_window_title:
            parts.append(f"Активне вікно: {obs.active_window_title}")
        if obs.screenshot_path:
            parts.append(f"Скріншот: {obs.screenshot_path}")
        if obs.ocr_text:
            text = obs.ocr_text.strip()
            if len(text) > 1500:
                text = text[:1500] + "…"
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
                args_str = json.dumps(args, ensure_ascii=False)[:200]
            except Exception:
                args_str = str(args)[:200]
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
        if last_result is not None:
            try:
                last_str = json.dumps(last_result, ensure_ascii=False)[:400]
            except Exception:
                last_str = str(last_result)[:400]
            user_parts += ["", f"РЕЗУЛЬТАТ ОСТАННЬОЇ ДІЇ: {last_str}"]
        if extra_instructions:
            user_parts += ["", extra_instructions]
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
    ) -> AgentAction:
        """Один крок рішення через LLM (JSON parsing fallback)."""
        if not self.is_available:
            return AgentAction(name="noop", reasoning="LLM decider unavailable")

        messages = self.build_messages(goal, observation, history, last_result, current_step=len(history))
        try:
            # Не передаємо tools — покладаємось на JSON parsing fallback
            # (qwen3/deepseek не підтримують function-calling)
            response = self._ask_llm_with_tools(
                messages=messages,
                tools=[],  # Порожній список — без function-calling
                tool_choice=None,  # Без tool_choice
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ActionDecider LLM call failed: %s", exc)
            return AgentAction(name="noop", reasoning=f"LLM error: {exc}")

        if getattr(response, "error", None):
            logger.warning("ActionDecider LLM error: %s", response.error)
            return AgentAction(name="noop", reasoning=f"LLM error: {response.error}")

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
        logger.info("ActionDecider: LLM content=%s...", content[:200])

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

        # Спробувати парсити як JSON
        if content.startswith("{"):
            try:
                parsed = json.loads(content)
                action_name = parsed.get("action", "noop")
                args = parsed.get("args", {})
                if not isinstance(args, dict):
                    args = {}
                reasoning = parsed.get("reasoning", "")
                logger.info("ActionDecider: Parsed JSON action=%s", action_name)
                return AgentAction(
                    name=str(action_name),
                    arguments=args,
                    reasoning=str(reasoning) + "\n[JSON parsed]",
                )
            except json.JSONDecodeError:
                logger.warning("ActionDecider: JSON parse failed for: %s...", content[:100])

        # 3) Якщо не вдалося — інтерпретувати як done
        return AgentAction(
            name="done",
            arguments={"summary": content or "Задачу завершено без додаткових дій."},
            reasoning=content,
        )

    def replan(
        self,
        goal: str,
        observation: Optional[Observation],
        history: List[Dict[str, Any]],
        consecutive_failures: int,
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
            goal, observation, history, last_result=None, extra_instructions=instructions
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

    def observe(self) -> Observation:
        """Отримати поточний стан системи (скрін + OCR + UIA + UI elements + Vision-LM)."""
        logger.info("AgentLoop.observe() called")
        obs = Observation(timestamp=time.time())

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
                    from .providers_vision import get_vision_provider
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
            from .tools_ui_detector import find_button_by_text, find_input_field
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
            from .logic_expectations import (
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
            from .core_checkpoint import CheckpointData, get_checkpoint_manager

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
            from .core_checkpoint import get_checkpoint_manager

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
            action = self.decider.replan(
                goal=task,
                observation=obs,
                history=state.actions_history,
                consecutive_failures=state.consecutive_failures,
            )
            state.consecutive_failures = 0  # Reset, щоб дати новому плану шанс
        else:
            action = self.decider.decide(
                goal=task,
                observation=obs,
                history=state.actions_history,
                last_result=last_result,
            )

        if action.name == "noop":
            return None  # Дозволити fallback на CompiledPlan/Planner

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

            # Виконати через registry
            result = self.registry.execute_function(action, args)
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

        status_msg = f'▶ Крок {state.step + 1}/{self.config.max_steps}: {action}'
        if reasoning:
            lines = str(reasoning).strip().splitlines()
            short = lines[0][:80] if lines else ""
            if short:
                status_msg += f' — {short}'
        self._gui_msg('update_status', status_msg)

        # 3. Act
        act_result = self.act(plan)
        state.last_action = action

        # 4. Check (з act_result + expectations)
        check_result = self.check(action, obs, act_result=act_result, expectations=expectations)
        state.last_result = check_result.get("detail", "")

        # Лог в історію
        state.actions_history.append({
            "step": state.step,
            "action": action,
            "args": args,
            "act_result": act_result,
            "check_result": check_result,
            "from_decider": plan.get("from_decider", False),
            "reasoning": reasoning,
        })
        # Тримаємо обмежений розмір історії
        if len(state.actions_history) > 100:
            state.actions_history = state.actions_history[-100:]

        # Зберегти чекпоїнт (через інтервал)
        if self._checkpoint_enabled and state.step % self.config.checkpoint_interval_steps == 0:
            self._save_checkpoint(state)

        # Облік провалів
        if check_result.get("success"):
            state.consecutive_failures = 0
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

        from .logic_repair_loop import RepairAction
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
            state.done = True
            state.success = False
            state.done_summary = f"Зупинено repair-стратегом: {decision.reason}"

    def _cleanup_checkpoint(self) -> None:
        """Видалити чекпоїнт після завершення."""
        if not self._checkpoint_enabled:
            return
        
        try:
            from .core_checkpoint import get_checkpoint_manager
            manager = get_checkpoint_manager()
            manager.delete(self.task_id)
            logger.info("Checkpoint deleted after completion")
        except Exception as e:
            logger.warning(f"Failed to delete checkpoint: {e}")

    def _send_completion_summary(self, state: AgentState, duration: float) -> None:
        """Відправити summary про завершення в GUI."""
        self._gui_msg('execution_finished', None)

        summary = f"📊 Agent loop завершено: {state.step} кроків за {duration:.1f}с"
        if state.success:
            summary += " ✅ Успішно"
        else:
            summary += " ⚠️ Не завершено"
        self._gui_msg('add_message', ('assistant', summary))
        self._gui_msg('update_status', '✅ Готовий до роботи')

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
        # Скидаємо бюджет repair-спроб для нової сесії
        if self.repairer is not None and hasattr(self.repairer, "reset"):
            try:
                self.repairer.reset()
            except Exception:
                pass
        state = self._load_checkpoint() or AgentState()
        start_time = time.time()

        self._gui_msg('update_status', '🔄 Agent loop: observe → plan → act → check')
        self._gui_msg('execution_started', None)

        try:
            while not self._should_stop(state, start_time):
                logger.info("AgentLoop: step=%d, max_steps=%d", state.step, self.config.max_steps)
                if not self._execute_single_step(task, state, start_time):
                    break
        finally:
            duration = time.time() - start_time
            self._cleanup_checkpoint()
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
        from .logic_llm_tools import ask_llm_with_tools
        from .logic_agent_tools_schema import (
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
