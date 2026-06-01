"""agent_coordinator.py — оркестрація та запуск AgentLoop.

Виносить збір залежностей AgentLoop з AssistantCore в окремий координатор,
щоб AssistantCore залишався чистим високорівневим фасадом.

Відповідальності:
1. Зібрати AgentLoopConfig + ActionDecider + StepRepairer
2. Створити інстанс AgentLoop
3. Запустити AgentLoop у фоновому потоці з обробкою помилок і тайм-аутом
4. Безпечний вихід при критичних помилках
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("agent_coordinator")


class AgentCoordinatorError(Exception):
    """Базова помилка координатора AgentLoop."""


class AgentLoopTimeoutError(AgentCoordinatorError):
    """Помилка тайм-ауту AgentLoop."""


class AgentCoordinator:
    """Оркестратор AgentLoop — збирає залежності та керує запуском циклу."""

    def __init__(
        self,
        assistant: Any,
        registry: Any,
        gui_queue: Any,
        gui_log_callback: Callable[[str, str], None],
    ):
        """
        Args:
            assistant: Інстанс VoiceAssistant
            registry: FunctionRegistry
            gui_queue: Черга для GUI повідомлень
            gui_log_callback: Callback для логування в GUI (sender, message)
        """
        self.assistant = assistant
        self.registry = registry
        self.gui_queue = gui_queue
        self._gui_log_callback = gui_log_callback

        # Ініціалізується в build()
        self.agent_loop: Any = None
        self.step_repairer: Any = None
        self.action_decider: Any = None

    # --- Публічний API ---

    def build(self) -> bool:
        """Зібрати AgentLoop з усіма залежностями.

        Returns:
            True якщо AgentLoop успішно створено, False при критичній помилці.
        """
        try:
            self._build_decider()
            self._build_repairer()
            self._build_agent_loop()
            self._attach_gui_callback()
            self._log_decider_and_repair_status()
            return True
        except Exception as e:
            logger.error("❌ Критична помилка збирання AgentLoop: %s", e)
            import traceback
            traceback.print_exc()
            self.agent_loop = None
            return False

    def run(self, task: str, timeout: float = 45.0) -> dict:
        """Запустити AgentLoop для задачі у фоновому потоці.

        Args:
            task: Текст задачі
            timeout: Максимальний час очікування виконання (сек)

        Returns:
            dict з результатом: {"ok": bool, "steps": int, "duration": float, "summary": str}
        """
        if not self.agent_loop:
            return {
                "ok": False,
                "steps": 0,
                "duration": 0.0,
                "summary": "AgentLoop не ініціалізовано",
            }

        if not task or not task.strip():
            return {
                "ok": False,
                "steps": 0,
                "duration": 0.0,
                "summary": "Порожня задача",
            }

        # --- Класифікація запиту через RequestRouter ---
        try:
            from functions.llm.router import RequestRouter
            router = RequestRouter()
            task_type = router.classify(task)
            logger.info("RequestRouter.classify('%s...') → %s", task[:60], task_type.value)
        except Exception as e:
            logger.warning("RequestRouter.classify() failed (non-critical): %s", e)
            task_type = None

        result: dict = {"ok": False, "steps": 0, "duration": 0.0, "summary": ""}
        start_time = time.time()

        def _run_agent() -> None:
            """Виконати AgentLoop з локальним перехопленням помилок."""
            nonlocal result
            try:
                result = self.agent_loop.run(task)
                if not isinstance(result, dict):
                    result = {"ok": True, "steps": 0, "duration": time.time() - start_time, "summary": str(result)}
            except Exception as e:
                logger.error("❌ Помилка AgentLoop: %s", e)
                import traceback
                traceback.print_exc()
                result = {
                    "ok": False,
                    "steps": 0,
                    "duration": time.time() - start_time,
                    "summary": f"Помилка: {e}",
                }

        thread = threading.Thread(target=_run_agent, daemon=False)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # Тайм-аут — безпечний вихід
            logger.warning("⚠️ AgentLoop перевищив ліміт часу (%sс), примусове завершення", timeout)
            self.request_stop()
            thread.join(timeout=2.0)
            result = {
                "ok": False,
                "steps": getattr(self.agent_loop, '_state', None).step if getattr(self.agent_loop, '_state', None) else 0,
                "duration": time.time() - start_time,
                "summary": f"⚠️ Перевищено ліміт часу ({timeout}с)",
            }

        # Додати duration якщо не встановлено
        if result.get("duration", 0.0) == 0.0:
            result["duration"] = time.time() - start_time

        return result

    def request_stop(self) -> None:
        """Запросити зупинку AgentLoop."""
        if self.agent_loop and hasattr(self.agent_loop, 'request_stop'):
            try:
                self.agent_loop.request_stop()
                logger.info("⏹️  AgentLoop: запит на зупинку надіслано")
            except Exception as e:
                logger.warning("⚠️  Помилка зупинки AgentLoop: %s", e)

    # --- Внутрішні методи збирання ---

    def _build_decider(self) -> None:
        """Створити ActionDecider з дефолтними налаштуваннями."""
        from functions.agent.plan import build_default_decider

        self.action_decider = build_default_decider(
            enable_vision=False,
            enable_uia=False,
            enable_browser=False,
            history_max=10,
        )

    def _build_repairer(self) -> None:
        """Створити StepRepairer (адаптивне відновлення при провалах)."""
        try:
            from functions.planning.logic_repair_loop import StepRepairer
            self.step_repairer = StepRepairer(assistant=self.assistant, max_repairs=3)
            logger.info("✅ StepRepairer створено")
        except Exception as e:
            self.step_repairer = None
            logger.warning("⚠️  StepRepairer недоступний: %s", e)

    def _build_agent_loop(self) -> None:
        """Створити інстанс AgentLoop з конфігурацією."""
        from functions.planning.agent_loop import AgentLoop, AgentLoopConfig

        self.agent_loop = AgentLoop(
            assistant=self.assistant,
            registry=self.registry,
            config=AgentLoopConfig(
                max_steps=50,
                max_duration_seconds=3600.0,
                enable_ocr=False,
                enable_vision=False,
                enable_llm_decider=True,
                enable_ui_elements=False,
                enable_repair=True,
                repair_after_failures=2,
                enable_checkpoint=False,
            ),
            decider=self.action_decider,
            repairer=self.step_repairer,
        )

    def _attach_gui_callback(self) -> None:
        """Прикріпити GUI callback до AgentLoop."""
        if self.agent_loop and self.gui_queue:
            self.agent_loop.gui_cb = lambda msg_type, data: (
                self.gui_queue.put((msg_type, data)) if self.gui_queue else None
            )

    def _log_decider_and_repair_status(self) -> None:
        """Вивести статус decider та repairer."""
        if not self.agent_loop:
            return

        decider_status = (
            "з LLM tool-calling"
            if (self.action_decider and self.action_decider.is_available)
            else "без LLM (fallback на CompiledPlan)"
        )
        repair_status = "+ repair" if self.step_repairer else ""
        status = f"✅ AgentLoop готовий ({decider_status}{repair_status})"
        logger.info(status)
        print(f"[AgentCoordinator] {status}")


# --- Функції для зворотної сумісності ---

def build_agent_coordinator(
    assistant: Any,
    registry: Any,
    gui_queue: Any,
    gui_log_callback: Callable[[str, str], None],
) -> Optional[AgentCoordinator]:
    """Зручна функція для створення AgentCoordinator.

    Args:
        assistant: VoiceAssistant інстанс
        registry: FunctionRegistry
        gui_queue: Черга GUI
        gui_log_callback: Callback логування

    Returns:
        AgentCoordinator або None при критичній помилці
    """
    try:
        coordinator = AgentCoordinator(
            assistant=assistant,
            registry=registry,
            gui_queue=gui_queue,
            gui_log_callback=gui_log_callback,
        )
        if coordinator.build():
            return coordinator
        return None
    except Exception as e:
        logger.error("❌ Помилка створення AgentCoordinator: %s", e)
        import traceback
        traceback.print_exc()
        return None


def run_agent_loop_safe(
    coordinator: Optional[AgentCoordinator],
    task: str,
    on_result: Optional[Callable[[dict], None]] = None,
    timeout: float = 45.0,
) -> dict:
    """Безпечний запуск AgentLoop через координатор.

    Args:
        coordinator: AgentCoordinator інстанс
        task: Текст задачі
        on_result: Callback з результатом (опційно)
        timeout: Тайм-аут виконання

    Returns:
        dict з результатом
    """
    if not coordinator or not coordinator.agent_loop:
        err_result = {
            "ok": False,
            "steps": 0,
            "duration": 0.0,
            "summary": "AgentCoordinator або AgentLoop недоступний",
        }
        if on_result:
            try:
                on_result(err_result)
            except Exception:
                pass
        return err_result

    result = coordinator.run(task, timeout=timeout)

    if on_result:
        try:
            on_result(result)
        except Exception:
            pass

    return result


__all__ = [
    "AgentCoordinator",
    "AgentCoordinatorError",
    "AgentLoopTimeoutError",
    "build_agent_coordinator",
    "run_agent_loop_safe",
]