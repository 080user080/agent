# functions/gui/commands_planner.py
"""Запуск довготривалих задач ШІ-планера та оркестрація AgentLoop.

Відокремлює важкі callback-функції запуску ШІ-планера, декомпозиції завдань
та ініціалізації фонових потоків для обчислень ШІ від коду вікна та інших команд.

Правила:
1. Усі функції — чисті та standalone, приймають залежності через параметри.
2. Інтерфейси взаємодії з TaskSpecCompiler та передача об'єктів задач
   залишаються незмінними для зворотної сумісності.
3. Фонові потоки захищені від помилок браку пам'яті або блокувань ресурсів.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Callable, Optional

from colorama import Fore

logger = logging.getLogger("commands_planner")


# ===========================================================================
# Класифікація завдань (без LLM)
# ===========================================================================

def classify_task(task: str) -> str:
    """Швидка класифікація завдання без LLM.

    Args:
        task: Текст завдання.

    Returns:
        FILE_OP — файлові операції (не потрібен екран)
        CODE_OP — виконання коду (не потрібен екран)
        CHAT — питання (просто відповідь)
        GUI_ACTION — GUI дії (потрібен екран)
        AGENT — fallback — повний AgentLoop
    """
    if not task:
        return "CHAT"

    task_lower = task.lower()

    # Файлові операції — не потрібен екран
    file_keywords = [
        "створи файл", "запиши файл", "прочитай файл",
        "видали файл", "перейменуй", "create file", "write file", "read file",
    ]
    if any(k in task_lower for k in file_keywords):
        return "FILE_OP"

    # Питання — просто відповідь
    question_keywords = [
        "що таке", "поясни", "як працює",
        "what is", "explain", "how does",
    ]
    if any(k in task_lower for k in question_keywords):
        return "CHAT"

    # GUI дії — потрібен екран
    gui_keywords = [
        "клікни", "відкрий програму", "натисни",
        "знайди на екрані", "click", "open app", "екран", "вікно", "кнопк",
    ]
    if any(k in task_lower for k in gui_keywords):
        return "GUI_ACTION"

    return "AGENT"  # fallback — повний AgentLoop (включає виконання коду)


# ===========================================================================
# Витягування Python коду
# ===========================================================================

def extract_python_code(task: str) -> str:
    """Витягти Python код з тексту завдання.

    Підтримує:
    - ```python``` блоки
    - Рядки що починаються з import, def, class, print

    Args:
        task: Текст завдання.

    Returns:
        str: Знайдений Python код або порожній рядок.
    """
    if not task:
        return ""

    # Спроба 1: витягти з ```python``` блоку
    code_block_match = re.search(r'```python\s*\n(.*?)\n```', task, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Спроба 2: витягти з ``` блоку без мови
    code_block_match = re.search(r'```\s*\n(.*?)\n```', task, re.DOTALL)
    if code_block_match:
        code = code_block_match.group(1).strip()
        # Перевірити чи це Python код
        if any(kw in code for kw in ['import ', 'def ', 'class ', 'print(']):
            return code

    # Спроба 3: знайти рядки що виглядають як Python код
    lines = task.split('\n')
    code_lines = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        # Початок коду
        if any(stripped.startswith(kw) for kw in ['import ', 'from ', 'def ', 'class ', 'print(']):
            in_code = True
            code_lines.append(line)
        elif in_code:
            # Продовження коду (відступи або порожній рядок між блоками)
            if line.startswith(' ') or line.startswith('\t') or stripped == '':
                code_lines.append(line)
            else:
                # Кінець коду
                break

    if code_lines:
        return '\n'.join(code_lines).strip()

    return ""


# ===========================================================================
# Пряме виконання (без AgentLoop)
# ===========================================================================

def execute_direct(
    task: str,
    action: str,
    registry: Any,
    gui_queue: Any,
) -> None:
    """Пряме виконання функції без AgentLoop (для простих операцій).

    Args:
        task: Текст завдання.
        action: Тип дії (write_file, execute_python).
        registry: FunctionRegistry.
        gui_queue: Черга для GUI повідомлень.
    """
    print(f"[DEBUG] Direct execution: {action} for task: {task[:50] if task else ''}...")

    if gui_queue:
        gui_queue.put(('update_status', f'📝 Пряме виконання: {action}'))

    try:
        if not registry:
            if gui_queue:
                gui_queue.put(('add_message', ('assistant', '❌ Registry не доступний')))
            return

        msg = ""

        if action == "write_file":
            # Парсинг параметрів з завдання
            filepath_match = re.search(
                r'["\']?([^"\']+\.(txt|py|md|json))["\']?', task, re.IGNORECASE
            )
            content_match = re.search(
                r'["\']?([^"\']+)["\']?\s*з текстом\s*["\']?([^"\']+)["\']?',
                task, re.IGNORECASE,
            )

            filepath = filepath_match.group(1) if filepath_match else "output.txt"
            content = content_match.group(2) if content_match else ""

            result = registry.execute_function(
                "write_file", {"filepath": filepath, "content": content}, auto_create=False,
            )
            msg = (
                f'✅ Файл створено: {filepath}'
                if result.get('ok')
                else f'❌ Помилка: {result.get("error")}'
            )

        elif action == "execute_python":
            # Витягти Python код з тексту завдання
            code = extract_python_code(task)
            if not code:
                msg = "❌ Не вдалося витягти Python код з завдання"
            else:
                result = registry.execute_function(
                    "execute_python", {"code": code}, auto_create=False,
                )
                # execute_python повертає dict з полями ok, message, data
                if isinstance(result, dict):
                    msg = (
                        result.get('message', 'Виконано')
                        if result.get('ok')
                        else f'❌ Помилка: {result.get("error")}'
                    )
                else:
                    # Якщо повернулось щось інше (наприклад str)
                    msg = str(result)

        else:
            msg = f'❌ Невідома дія: {action}'

        if gui_queue:
            gui_queue.put(('add_message', ('assistant', msg)))
            gui_queue.put(('update_status', '✅ Готовий до роботи'))

    except Exception as e:
        print(f"[ERROR] Direct execution failed: {e}")
        import traceback
        traceback.print_exc()
        if gui_queue:
            gui_queue.put(('add_message', ('assistant', f'❌ Помилка виконання: {e}')))


# ===========================================================================
# Запуск AgentLoop
# ===========================================================================

def run_agent_loop(
    task: str,
    *,
    gui_queue: Any,
    agent_coordinator: Any = None,
    agent_loop: Any = None,
    assistant: Any = None,
    on_result: Optional[Callable[[dict], None]] = None,
    timeout: float = 45.0,
) -> None:
    """Запустити AgentLoop для задачі через AgentCoordinator.

    Args:
        task: Текст задачі.
        gui_queue: Черга для GUI повідомлень.
        agent_coordinator: AgentCoordinator інстанс (пріоритетний шлях).
        agent_loop: AgentLoop інстанс (fallback, якщо координатор не задано).
        assistant: VoiceAssistant інстанс (legacy fallback).
        on_result: Опційний callback із результатом виконання.
        timeout: Тайм-аут очікування (сек).
    """
    print(f"[DEBUG] run_agent_loop called with task: {task[:50] if task else ''}...")
    if not task:
        if gui_queue:
            gui_queue.put(('add_message', ('assistant', '❌ Немає задачі для виконання.')))
        return

    # Повідомлення користувача вже логовано в process_text_command — не дублюємо
    if gui_queue:
        gui_queue.put(('update_status', '🤖 AgentLoop: observe → plan → act → check'))

    # AgentCoordinator — основний шлях
    print(f"[DEBUG] agent_coordinator exists: {agent_coordinator is not None}")
    if agent_coordinator and agent_coordinator.agent_loop:
        print(f"[DEBUG] AgentCoordinator calling run() with task: {task[:50] if task else ''}...")

        def _default_on_result(result: dict) -> None:
            """Дефолтний callback після завершення AgentLoop."""
            if not gui_queue:
                return
            ok = result.get("ok")
            msg = (
                f'📊 Agent loop: {result.get("steps", 0)} кроків за {result.get("duration", 0):.1f}с ✅'
                if ok else f'❌ Помилка: {result.get("summary", "")}'
            )
            gui_queue.put(('add_message', ('assistant', msg)))

        _on_result = on_result or _default_on_result

        from functions.planning.agent_coordinator import run_agent_loop_safe

        thread = threading.Thread(
            target=lambda: _run_agent_loop_safe_wrapper(
                coordinator=agent_coordinator,
                task=task,
                on_result=_on_result,
                timeout=timeout,
            ),
            daemon=False,
        )
        thread.start()
        thread.join(timeout=timeout + 5)
        return

    # Fallback на пряме використання agent_loop (якщо координатор не створено)
    if agent_loop:
        print(f"[DEBUG] Fallback: calling agent_loop.run() directly")

        def _run_agent():
            try:
                result = agent_loop.run(task)
                if gui_queue:
                    ok = result.get("ok")
                    msg = (
                        f'📊 Agent loop: {result.get("steps", 0)} кроків за {result.get("duration", 0):.1f}с ✅'
                        if ok else f'❌ Помилка: {result.get("summary", "")}'
                    )
                    gui_queue.put(('add_message', ('assistant', msg)))
            except Exception as e:
                import traceback
                traceback.print_exc()
                if gui_queue:
                    gui_queue.put(('add_message', ('assistant', f'❌ Помилка AgentLoop: {e}')))

        thread = threading.Thread(target=_run_agent, daemon=False)
        thread.start()
        thread.join(timeout=timeout)
        return

    # Останній fallback — на assistant.process_command
    if assistant:
        print(f"[DEBUG] AgentLoop not available, falling back to assistant.process_command")
        try:
            assistant.process_command(task, from_gui=True)
        except Exception as e:
            if gui_queue:
                gui_queue.put(('add_message', ('assistant', f'❌ Помилка: {e}')))
    else:
        if gui_queue:
            gui_queue.put(('add_message', ('assistant', '❌ AgentLoop та Assistant недоступні')))


def _run_agent_loop_safe_wrapper(
    coordinator: Any,
    task: str,
    on_result: Callable[[dict], None],
    timeout: float,
) -> None:
    """Безпечний запуск run_agent_loop_safe з локальним перехопленням помилок.

    Args:
        coordinator: AgentCoordinator інстанс.
        task: Текст задачі.
        on_result: Callback з результатом.
        timeout: Тайм-аут виконання.
    """
    try:
        from functions.planning.agent_coordinator import run_agent_loop_safe
        run_agent_loop_safe(
            coordinator=coordinator,
            task=task,
            on_result=on_result,
            timeout=timeout,
        )
    except MemoryError:
        logger.error("❌ MemoryError при запуску AgentLoop — недостатньо пам'яті")
        if on_result:
            try:
                on_result({
                    "ok": False,
                    "steps": 0,
                    "duration": 0.0,
                    "summary": "❌ Недостатньо пам'яті для запуску AgentLoop",
                })
            except Exception:
                pass
    except Exception as e:
        logger.error("❌ Помилка запуску AgentLoop: %s", e)
        import traceback
        traceback.print_exc()
        if on_result:
            try:
                on_result({
                    "ok": False,
                    "steps": 0,
                    "duration": 0.0,
                    "summary": f"Помилка: {e}",
                })
            except Exception:
                pass


# ===========================================================================
# Виконання плану, що очікує
# ===========================================================================

def run_pending_plan(
    *,
    gui_queue: Any,
    assistant: Any = None,
    agent_coordinator: Any = None,
    agent_loop: Any = None,
) -> None:
    """Виконати план, що очікує (викликається з GUI кнопки 'Виконати план').

    Args:
        gui_queue: Черга для GUI повідомлень.
        assistant: VoiceAssistant інстанс (для отримання останньої команди).
        agent_coordinator: AgentCoordinator інстанс.
        agent_loop: AgentLoop інстанс (fallback).
    """
    # Отримати останню команду користувача
    task = _get_last_user_command(assistant) or ""

    if not task:
        if gui_queue:
            gui_queue.put(('add_message', ('assistant', '❌ Немає задачі для виконання.')))
        return

    # Запускаємо через AgentLoop
    run_agent_loop(
        task,
        gui_queue=gui_queue,
        agent_coordinator=agent_coordinator,
        agent_loop=agent_loop,
        assistant=assistant,
    )


def _get_last_user_command(assistant: Any) -> str:
    """Отримати останню команду користувача з історії асистента.

    Args:
        assistant: VoiceAssistant інстанс.

    Returns:
        str: Остання команда користувача або порожній рядок.
    """
    if assistant and hasattr(assistant, 'conversation_history'):
        for msg in reversed(assistant.conversation_history):
            if msg.get('role') == 'user':
                return msg.get('content', '')
    return ""


# ===========================================================================
# Зупинка виконання плану
# ===========================================================================

def stop_plan_execution(
    *,
    agent_loop: Any = None,
    agent_coordinator: Any = None,
    plan_executor: Any = None,
    assistant: Any = None,
    gui_queue: Any = None,
) -> None:
    """Зупинити виконання плану (з GUI кнопки 'Стоп план').

    Args:
        agent_loop: AgentLoop інстанс.
        agent_coordinator: AgentCoordinator інстанс.
        plan_executor: PlanExecutor інстанс (legacy).
        assistant: VoiceAssistant інстанс (для зупинки executor).
        gui_queue: Черга для GUI повідомлень (опційно).
    """
    if agent_loop and hasattr(agent_loop, 'request_stop'):
        try:
            agent_loop.request_stop()
            logger.info("⏹️  AgentLoop: запит на зупинку надіслано")
        except Exception as e:
            logger.warning("⚠️  Помилка зупинки AgentLoop: %s", e)

    if agent_coordinator and hasattr(agent_coordinator, 'request_stop'):
        try:
            agent_coordinator.request_stop()
            logger.info("⏹️  AgentCoordinator: запит на зупинку надіслано")
        except Exception as e:
            logger.warning("⚠️  Помилка зупинки AgentCoordinator: %s", e)

    if plan_executor and hasattr(plan_executor, 'request_stop'):
        try:
            plan_executor.request_stop()
            logger.info("⏹️  PlanExecutor: запит на зупинку надіслано")
        except Exception as e:
            logger.warning("⚠️  Помилка зупинки PlanExecutor: %s", e)

    # Також зупинити основний executor
    if assistant and hasattr(assistant, 'executor'):
        try:
            assistant.executor.stop()
            logger.info("⏹️  Assistant executor: зупинено")
        except Exception as e:
            logger.warning("⚠️  Помилка зупинки executor: %s", e)

    if gui_queue:
        gui_queue.put(('execution_finished', None))
        gui_queue.put(('add_message', ('assistant', '⏹️ Виконання зупинено користувачем.')))


# ===========================================================================
# Запуск AgentLoop для voice_input (з логуванням)
# ===========================================================================

def run_agent_loop_for_voice(
    command_text: str,
    *,
    agent_coordinator: Any = None,
    agent_loop: Any = None,
    gui_queue: Any = None,
    gui_log_callback: Callable[[str, str], None] = None,
    assistant: Any = None,
) -> None:
    """Запустити AgentLoop для voice_input команди зі статусним повідомленням.

    Args:
        command_text: Текст voice_input команди.
        agent_coordinator: AgentCoordinator інстанс.
        agent_loop: AgentLoop інстанс.
        gui_queue: Черга для GUI повідомлень.
        gui_log_callback: Callback для логування в GUI (sender, message).
        assistant: VoiceAssistant інстанс (fallback).
    """
    print(f"{Fore.CYAN}🎤 [DEBUG] Виклик run_agent_loop для voice_input")
    run_agent_loop(
        command_text,
        gui_queue=gui_queue,
        agent_coordinator=agent_coordinator,
        agent_loop=agent_loop,
        assistant=assistant,
    )
    if gui_log_callback:
        gui_log_callback("update_status", '✅ Готовий до роботи')


# ===========================================================================
# Експорт
# ===========================================================================

__all__ = [
    "classify_task",
    "execute_direct",
    "extract_python_code",
    "run_agent_loop",
    "run_agent_loop_for_voice",
    "run_pending_plan",
    "stop_plan_execution",
]