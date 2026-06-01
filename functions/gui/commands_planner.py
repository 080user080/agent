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
    print(f"[classify_task] DEBUG: task='{task[:60]}' task_lower='{task_lower[:60]}'")

    # ═══ ПЕРША ПЕРЕВІРКА: Вітання / розмова — просто відповідь (не запускати AgentLoop) ═══
    greeting_keywords = [
        "привіт", "вітаю", "добрий день", "добрий вечір",
        "hello", "hi", "hey", "how are you",
        "good morning", "good evening",
    ]
    if any(k in task_lower for k in greeting_keywords):
        print(f"[classify_task] CHAT ← greeting: '{task_lower[:40]}'")
        return "CHAT"

    # Файлові операції — не потрібен екран
    file_keywords = [
        "створи файл", "запиши файл", "прочитай файл",
        "видали файл", "перейменуй", "create file", "write file", "read file",
    ]
    if any(k in task_lower for k in file_keywords):
        print(f"[classify_task] FILE_OP: '{task_lower[:40]}'")
        return "FILE_OP"

    # Питання — просто відповідь
    question_keywords = [
        "що таке", "поясни", "як працює",
        "what is", "explain", "how does",
    ]
    if any(k in task_lower for k in question_keywords):
        print(f"[classify_task] CHAT ← question: '{task_lower[:40]}'")
        return "CHAT"

    # GUI дії — потрібен екран
    gui_keywords = [
        "клікни", "відкрий програму", "натисни",
        "знайди на екрані", "click", "open app", "екран", "вікно", "кнопк",
    ]
    if any(k in task_lower for k in gui_keywords):
        print(f"[classify_task] GUI_ACTION: '{task_lower[:40]}'")
        return "GUI_ACTION"

    print(f"[classify_task] AGENT ← fallback: '{task_lower[:40]}'")
    return "AGENT"  # fallback — повний AgentLoop (включає виконання коду)


# ===========================================================================
# Перевірка неоднозначності команди
# ===========================================================================

# Дієслова без об'єкта — потребують уточнення
_AMBIGUOUS_VERBS = [
    "відкрий", "відкрити", "відкривай",
    "подивися", "подивись", "дивись", "глянь",
    "виконай", "виконати",
    "запусти", "запускай", "запустити",
    "покажи", "показати", "показуй",
    "перевір", "перевірити",
    "напиши", "написати", "пиши",
    "створи", "створити", "створюй",
    "знайди", "знайти", "шукай",
    "встав", "вставити",
    "скопіюй", "копіювати",
    "видали", "видалити",
]

# Команди з вказівним займенником без контексту
_AMBIGUOUS_DEMONSTRATIVE = [
    "зроби це", "зроби те",
    "виправ це", "виправ те",
    "зроби", "виправ", "поправ",
    "перероби", "перепиши",
]

# Команди про "проект/код" без уточнення
# Тільки точний збіг — без додаткових слів після "код"/"проект"
_AMBIGUOUS_PROJECT_PATTERNS = [
    r'^подиви(ся|сь)\s+код$',
    r'^покажи\s+проект$',
    r'^подиви(ся|сь)\s+проект$',
    r'^покажи\s+код$',
    r'^відкрий\s+проект$',
    r'^відкрий\s+код$',
    # Варіанти з "мій"
    r'^подиви(ся|сь)\s+мій\s+проект$',
    r'^покажи\s+мій\s+проект$',
    r'^покажи\s+мій\s+код$',
    r'^відкрий\s+мій\s+проект$',
    r'^відкрий\s+мій\s+код$',
    # Варіанти з комою після дієслова: "подивис, проект"
    r'^подиви(ся|сь)[\s,]+\s*проект$',
    r'^подиви(ся|сь)[\s,]+\s*код$',
    r'^покажи[\s,]+\s*проект$',
    r'^покажи[\s,]+\s*код$',
    r'^відкрий[\s,]+\s*проект$',
    r'^відкрий[\s,]+\s*код$',
]

# Патерни, які НЕ потребують уточнення (виконувати одразу)
_CLEAR_PATTERNS = [
    # Вітання
    r'^(привіт|вітаю|добрий\s+день|hello|hi|hey)\s*$',
    # Обчислення
    r'^(порахуй|скільки\s+буде|скільки)\b',
    r'^[0-9+\-*/()\s]+$',
    # Прямі питання
    r'^(як|що|чому|коли|де|хто|куди|звідки|навіщо|для\s+чого)\s',
    # Команди з повним об'єктом
    r'^відкрий\s+(файл|програму|додаток|сайт|посилання|документ)(\s|$)',
    r'^подиви(ся|сь)\s+(файл|код\s+у|папку|директорію|вміст)(\s|$)',
    r'^запусти\s+(програму|додаток|скрипт|файл)(\s|$)',
    r'^напиши\s+(код|файл|лист|текст|повідомлення)(\s|$)',
    r'^створи\s+(файл|папку|проект|скрипт|функцію|клас|документ)(\s|$)',
    r'^виконай\s+(команду|скрипт|код)(\s|$)',
]


def needs_clarification(task: str) -> tuple[bool, str]:
    """Перевірити, чи команда неоднозначна і потребує уточнення.

    Args:
        task: Текст команди користувача.

    Returns:
        (True, "питання для уточнення") — якщо команда неоднозначна
        (False, "") — якщо команда зрозуміла, виконувати одразу
    """
    if not task:
        return False, ""

    task_stripped = task.strip()
    task_lower = task_stripped.lower()

    # ── 1. CHAT — ніколи не питаємо ────────────────────
    if classify_task(task_lower) == "CHAT":
        return False, ""

    # ── 2. Чіткі патерни — виконуємо одразу ────────────
    for pattern in _CLEAR_PATTERNS:
        if re.search(pattern, task_lower):
            return False, ""

    # ── 3. Дієслово без об'єкта ─────────────────────────
    # Команда складається ТІЛЬКИ з дієслова (без об'єкта дії)
    for verb in _AMBIGUOUS_VERBS:
        # Точний збіг: "відкрий" (все слово)
        if task_lower == verb:
            return _make_clarification(verb)
        # "відкрий." або "відкрий!" або "відкрий?"
        if task_lower.rstrip('.!?') == verb:
            return _make_clarification(verb)
        # "відкрий будь ласка" / "відкрий, будь ласка"
        if re.match(rf'^{re.escape(verb)}[\s,]+(будь\s+ласка|пожалуйста|please|плиз)\s*$', task_lower):
            return _make_clarification(verb)

    # ── 4. Вказівні займенники без контексту ───────────
    for phrase in _AMBIGUOUS_DEMONSTRATIVE:
        if task_lower == phrase:
            return (True, "Що саме? Опишіть детальніше, що потрібно зробити.")

    # ── 5. "подивися код" / "покажи проект" без об'єкта ─
    for pattern in _AMBIGUOUS_PROJECT_PATTERNS:
        if re.search(pattern, task_lower):
            return (True, "Який саме файл або папку переглянути? Наприклад: functions/planning/agent_loop.py або весь список файлів?")

    return False, ""


def _make_clarification(verb: str) -> tuple[bool, str]:
    """Сформувати питання для уточнення залежно від дієслова."""
    verb_questions = {
        "відкрий": "Що саме відкрити? (файл, програму, посилання)",
        "відкрити": "Що саме відкрити? (файл, програму, посилання)",
        "відкривай": "Що саме відкрити? (файл, програму, посилання)",
        "подивися": "Який саме файл або папку переглянути?",
        "подивись": "Який саме файл або папку переглянути?",
        "дивись": "Який саме файл або папку переглянути?",
        "глянь": "Який саме файл або папку переглянути?",
        "виконай": "Що саме виконати? (команду, скрипт, код)",
        "виконати": "Що саме виконати? (команду, скрипт, код)",
        "запусти": "Яку програму або скрипт запустити?",
        "запускай": "Яку програму або скрипт запустити?",
        "запустити": "Яку програму або скрипт запустити?",
        "покажи": "Що саме показати? (код, файл, папку, інформацію)",
        "показати": "Що саме показати? (код, файл, папку, інформацію)",
        "показуй": "Що саме показати? (код, файл, папку, інформацію)",
        "перевір": "Що саме перевірити?",
        "перевірити": "Що саме перевірити?",
        "напиши": "Що саме написати? (код, файл, лист, текст)",
        "написати": "Що саме написати? (код, файл, лист, текст)",
        "пиши": "Що саме написати? (код, файл, лист, текст)",
        "створи": "Що саме створити? (файл, папку, функцію, клас)",
        "створити": "Що саме створити? (файл, папку, функцію, клас)",
        "створюй": "Що саме створити? (файл, папку, функцію, клас)",
        "знайди": "Що саме знайти? (файл, текст, інформацію)",
        "знайти": "Що саме знайти? (файл, текст, інформацію)",
        "шукай": "Що саме знайти? (файл, текст, інформацію)",
        "встав": "Що і куди вставити?",
        "вставити": "Що і куди вставити?",
        "скопіюй": "Що саме скопіювати?",
        "копіювати": "Що саме скопіювати?",
        "видали": "Що саме видалити?",
        "видалити": "Що саме видалити?",
    }
    question = verb_questions.get(verb, f"Яку дію виконати з '{verb}'? Додайте об'єкт дії.")
    return (True, question)


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
    "needs_clarification",
    "run_agent_loop",
    "run_agent_loop_for_voice",
    "run_pending_plan",
    "stop_plan_execution",
]