"""AgentLoop — справжній цикл агента: observe → plan → act → check.

Це Phase 12.1 observe loop — заміна legacy linear execution на замкнутий цикл з feedback.

Архітектура:
- observe() → отримати поточний стан (скрін + OCR/UIA)
- plan() → вирішити що робити далі (LLM з можливістю перепланування)
- act() → виконати дію (миша/клавіатура/браузер)
- check() → перевірити чи спрацювало (скріншот порівняння)
"""
from __future__ import annotations

import hashlib
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
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """Стат агента між ітераціями."""
    step: int = 0
    observations: List[Observation] = field(default_factory=list)
    last_action: Optional[str] = None
    last_result: Optional[str] = None
    actions_history: List[Dict[str, Any]] = field(default_factory=list)
    done: bool = False
    success: bool = False


@dataclass
class AgentLoopConfig:
    """Конфігурація AgentLoop."""
    max_steps: int = 50
    max_duration_seconds: float = 3600.0
    enable_ocr: bool = True
    enable_ui_a: bool = False
    enable_vision: bool = False
    enable_checkpoint: bool = True
    checkpoint_interval_steps: int = 5
    screen_diff_threshold: float = 0.01


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
    ):
        self.assistant = assistant
        self.registry = registry
        self.config = config or AgentLoopConfig()
        self._state = AgentState()
        self._compiled_plan = None
        self.ask_user_callback = ask_user_callback
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
        """Отримати поточний стан системи (скрін + OCR + UIA + Vision-LM)."""
        obs = Observation(timestamp=time.time())

        try:
            # Скріншот
            if _SCREEN_CAPTURE_AVAILABLE:
                result = take_screenshot()
                if result.get("ok") and result.get("path"):
                    obs.screenshot_path = result["path"]
                    # Хеш для порівняння
                    obs.screen_hash = self._hash_screenshot(obs.screenshot_path)

            # OCR (якщо увімкнено)
            if self.config.enable_ocr and obs.screenshot_path and _SCREEN_CAPTURE_AVAILABLE:
                result_ocr = ocr_image({"image_path": obs.screenshot_path})
                if result_ocr.get("ok") and result_ocr.get("text"):
                    obs.ocr_text = result_ocr["text"]
                    obs.metadata["ocr_length"] = len(obs.ocr_text)

            # UIA (якщо увімкнено)
            if self.config.enable_ui_a and _SCREEN_CAPTURE_AVAILABLE:
                uia = get_uia_wrapper()
                if uia.is_available():
                    focused = uia.get_focused_element()
                    if focused:
                        obs.metadata["uia_focused"] = focused.__dict__

            # Vision-LM (якщо увімкнено і скріншот готовий)
            if self.config.enable_vision and obs.screenshot_path:
                try:
                    from .providers_vision import get_vision_provider
                    vision = get_vision_provider(self.assistant)
                    if vision.is_available():
                        # Базовий аналіз UI
                        elements = vision.detect_ui_elements(obs.screenshot_path)
                        if elements:
                            obs.metadata["vision_elements"] = elements
                except Exception as e:
                    logger.debug("Vision-LM error: %s", e)

        except Exception as e:
            logger.error("observe() error: %s", e)
            obs.metadata["error"] = str(e)

        logger.debug("observe: screen_hash=%s, ocr_len=%d", obs.screen_hash[:8], len(obs.ocr_text))
        return obs

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

    def check(self, action: str, obs: Observation) -> Dict[str, Any]:
        """Перевірити чи дія спрацювала (порівняння скріншотів).

        Базова імплементація: якщо скрін змінився — дія спрацювала.
        """
        result = {
            "success": False,
            "screen_changed": False,
            "retry": False,
            "detail": "",
        }

        # Порівняти з попереднім скріншотом
        if self._prev_screen_hash and self._prev_screen_hash != obs.screen_hash:
            result["screen_changed"] = True
            result["success"] = True
            result["detail"] = "Скріншот змінився"
        elif self._prev_screen_hash == obs.screen_hash:
            result["screen_changed"] = False
            result["success"] = False
            result["retry"] = True
            result["detail"] = "Скріншот не змінився — можливо дія не спрацювала"
        else:
            # Перша ітерація — вважаємо OK
            result["success"] = True
            result["detail"] = "Перша ітерація"

        # Зберігаємо поточний як попередній
        self._prev_screen_hash = obs.screen_hash
        self._prev_screen_path = obs.screenshot_path

        return result

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
            return None
        
        first_step = steps[0]
        state.actions_history.append({"plan": steps})
        return self._get_step_from_plan(first_step, state, len(steps), False)

    def _plan_from_history(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Отримати наступний крок з історії планів."""
        if state.step == 0 or len(state.actions_history) == 0:
            return None
        
        last_plan = state.actions_history[0].get("plan", [])
        if state.step < len(last_plan):
            return self._get_step_from_plan(last_plan[state.step], state, len(last_plan), False)
        
        return None

    def plan(self, task: str, obs: Observation, state: AgentState) -> Dict[str, Any]:
        """Вирішити що робити далі (LLM з можливістю перепланування).

        Повертає: {"action": "...", "args": {...}, "replan": bool, "done": bool}
        """
        # Пріоритет 1: CompiledPlan від TaskSpec
        result = self._plan_from_compiled(state)
        if result:
            return result

        # Пріоритет 2: Planner (для першого кроку)
        result = self._plan_from_planner(task, state)
        if result:
            return result

        # Пріоритет 3: Історія планів
        result = self._plan_from_history(state)
        if result:
            return result

        # Fallback — noop
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
        # 1. Observe
        obs = self.observe()
        state.observations.append(obs)

        # 2. Plan
        plan = self.plan(task, obs, state)
        if plan.get("done"):
            logger.info("Plan says done")
            state.done = True
            state.success = True
            return False

        action = plan.get("action", "noop")
        args = plan.get("args", {})

        self._gui_msg('update_status', f'▶ Крок {state.step + 1}/{self.config.max_steps}: {action}')

        # 3. Act
        act_result = self.act(plan)
        state.last_action = action

        # 4. Check
        check_result = self.check(action, obs)
        state.last_result = check_result.get("detail", "")

        # Лог в історію
        state.actions_history.append({
            "step": state.step,
            "action": action,
            "args": args,
            "act_result": act_result,
            "check_result": check_result,
        })

        # Зберегти чекпоїнт (через інтервал)
        if self._checkpoint_enabled and state.step % self.config.checkpoint_interval_steps == 0:
            self._save_checkpoint(state)

        # Перевірка успіху
        if not check_result.get("success") and check_result.get("retry"):
            logger.warning("Action failed, retrying...")

        state.step += 1
        time.sleep(0.3)
        return True

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
        self._current_task = task
        self._stop_flag = False
        state = self._load_checkpoint() or AgentState()
        start_time = time.time()

        self._gui_msg('update_status', '🔄 Agent loop: observe → plan → act → check')
        self._gui_msg('execution_started', None)

        try:
            while not self._should_stop(state, start_time):
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
            "state": state,
        }
