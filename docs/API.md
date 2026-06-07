# 🔌 API

> Оновлено: 07.06.2026 — синхронізовано з актуальним кодом (після Фаз 1-7).

## Огляд

Цей документ описує публічний API для інтеграції з агентом МАРК.

Див. також:
- [MODULES.md](MODULES.md) — повний каталог модулів.
- [ARCHITECTURE.md](ARCHITECTURE.md) — архітектурна карта.
- [SECURITY.md](SECURITY.md) — безпека та ризики.

---

## FunctionRegistry API

### Реєстрація функції

```python
from functions.runtime.logic_core import FunctionRegistry

def my_function(param: str) -> str:
    """Опис функції."""
    return f"Result: {param}"

FunctionRegistry.register("my_function", my_function)
```

### Виклик функції

```python
result = FunctionRegistry.call("my_function", param="test")
```

### Оцінка ризику

```python
from functions.runtime.logic_core import FunctionRegistry
risk = FunctionRegistry.get_tool_risk("execute_python")
```

### Автозавантаження модулів

`FunctionRegistry.load_all_modules()` завантажує всі модулі з `functions/{core,aaa,tools,skills}/` через `rglob`. Підтримуються як файли в корені, так і в підпапках.

---

## GUI Callback API

### Відправка команди в ядро

```python
# PyQt6
gui_callback('process_text', 'Створи файл test.py')
gui_callback('run_agent', 'Відкрий notepad і напиши привіт')
```

### Доступні callback-и

| Callback | Параметри | Опис |
|----------|-----------|------|
| `process_text` | `text: str` | Обробка текстової команди (з `classify_task` → CHAT/AGENT) |
| `run_agent` | `task: str` | Запуск AgentLoop (кнопка 🤖) |
| `run_plan` | - | Виконання плану |
| `stop_plan` | - | Зупинення плану |
| `stop_execution` | - | Зупинення виконання |
| `pause_listening` | - | Призупинити слухання |
| `resume_listening` | - | Відновити слухання |
| `start_windsurf_watch` | - | Запустити Windsurf Watch |
| `stop_windsurf_watch` | - | Зупинити Windsurf Watch |

---

## LLM API (дворівнева архітектура)

LLM-шар має **дворівневу архітектуру**:

- **J1 (низький рівень)**: абстракція `AIProvider` + реєстр `ProviderRegistry`.
- **J2-J4 (оркестрація)**: `RequestRouter` → `ProviderChain` з fallback.

### Рівень 1: `ask_llm` — простий запит

```python
from functions.llm.helpers import ask_llm
response = ask_llm("Привіт, як справи?", system_prompt="Ти асистент МАРК")
```

### Рівень 2: `RequestRouter` — класифікація задачі

```python
from functions.llm.router import RequestRouter, TaskType

router = RequestRouter()
decision = router.classify("Створи файл hello.py")
# decision.task_type == TaskType.CODE
# decision.primary_provider_id == "openai_compatible"
# decision.fallback_chain == ["anthropic", "google"]
```

Типи задач: `CODE`, `DEBUG`, `GUI`, `WEB`, `GENERAL`, `QUICK`.

### Рівень 3: `ProviderChain` — виконання з fallback

```python
from functions.llm.provider_chain import ProviderChain
from functions.llm.logic_ai_adapter import ChatRequest

chain = ProviderChain(providers={
    "openai_compatible": openai_provider,
    "anthropic": anthropic_provider,
})
response = chain.execute(request=chat_request, decision=decision, timeout=180.0)
```

### Прямий виклик через `AIProvider`

```python
from functions.llm.providers_openai_compatible import OpenAICompatibleProvider
from functions.llm.providers_anthropic import AnthropicProvider
from functions.llm.providers_google import GoogleProvider

provider = OpenAICompatibleProvider(
    endpoint="http://localhost:1234/v1",
    model="qwen3-30b",
)
if provider.available():
    response = provider.chat(request)
```

### Tool-calling

```python
from functions.llm.logic_llm_tools import ask_llm_with_tools

tools = [
    {"name": "create_file", "description": "Створити файл"},
    {"name": "execute_python", "description": "Виконати код"}
]

response = ask_llm_with_tools("Створи файл hello.py", tools)
```

### Streaming + token counting

```python
from functions.llm.streaming_buffer import StreamingBuffer

buffer = StreamingBuffer(
    on_status=lambda msg: print(f"Status: {msg}"),
    on_context_update=lambda used, limit, model: print(f"{used}/{limit} ({model})"),
    context_limit=128000,
    model="claude-sonnet-4-6",
)

# Під час стрімінгу:
for chunk in stream:
    buffer.add_chunk(chunk)

# Після стрімінгу:
buffer.finish(real_usage)  # замінює оцінку реальним usage
```

### Vision-LM

```python
from functions.llm.providers_vision import (
    VisionLMProvider, VisionQuery, get_vision_provider
)

provider = get_vision_provider()
if provider.is_available():
    query = VisionQuery(
        image_path="screenshot.png",
        question="Що бачиш на екрані?"
    )
    response = provider.analyze_image(query)
    print(response.text)
```

⚠️ `detect_ui_elements()` та `suggest_actions()` поки що stubs (див. `TASKS.md`).

---

## AgentLoop API

### Ініціалізація та запуск

```python
from functions.planning.agent_loop import AgentLoop, AgentLoopConfig
from functions.agent.plan import ActionDecider

config = AgentLoopConfig(
    max_steps=200,
    max_duration_seconds=3600.0,
    enable_ocr=True,
    enable_ui_a=False,           # Windows UIA (вимкнено за замовчуванням)
    enable_vision=False,         # Vision-LM (вимкнено за замовчуванням)
    enable_ui_elements=True,
    enable_llm_decider=True,
    enable_checkpoint=True,
    checkpoint_interval_steps=5,
    replan_after_failures=3,
    repair_after_failures=2,
    enable_repair=True,
    screen_diff_threshold=0.01,
)

decider = ActionDecider(assistant=assistant, tools=tools_schema)
loop = AgentLoop(
    assistant=assistant,
    registry=function_registry,
    config=config,
    decider=decider,
    repairer=step_repairer,
    context_controller=context_controller,
)

result = loop.run("Знайди файл README.md і прочитай його")
# result == {"ok": bool, "steps": int, "duration": float, "summary": str, "state": AgentState}
```

### Зупинка

```python
loop.request_stop()  # викликати з іншого потоку
```

### CompiledPlan

```python
from functions.planning.task_spec import TaskSpec

# Створити TaskSpec → CompiledPlan → передати в AgentLoop
loop.set_compiled_plan(compiled_plan)
```

### Пріоритет стратегій в `plan()`

`AgentLoop.plan()` має 5 fallback-ів:

1. **LLM ActionDecider** — якщо `enable_llm_decider=True` і decider доступний.
2. **Planner (legacy)** — тільки на першому кроці (`state.step == 0`).
3. **Plan history** — продовження з `state._plan_steps`.
4. **CompiledPlan** — від `TaskSpec`.
5. **Fallback** — `{"action": "noop", "done": True}`.

---

## TaskRunner API

```python
from functions.planning.logic_task_runner import TaskRunner
from functions.runtime.logic_permission_gate import PermissionGate
from functions.runtime.core_session_budget import SessionBudget, SessionLimits

runner = TaskRunner(
    gate=PermissionGate(),
    budget=SessionBudget(limits=SessionLimits()),
    registry=function_registry,
)

# Додати handler
runner.register_handler("run_command", my_handler)

# Запустити план
report = runner.run(plan)
# report — ExecutionReport з StepReport-ами
```

---

## PermissionGate API

```python
from functions.runtime.logic_permission_gate import PermissionGate

gate = PermissionGate()
decision = gate.ask(
    action="execute_python",
    context={"code": "print('hello')"}
)
# decision можна прийняти або відхилити
# 4-рівнева policy stack: GLOBAL → USER → SESSION → ACTION
```

---

## Watcher API

```python
from functions.runtime.logic_watcher import Watcher

watcher = Watcher()
handle = watcher.watch(
    condition=lambda: check_window_exists("Notepad"),
    callback=lambda: print("Notepad opened!")
)
# Зупинити:
watcher.stop_watch(handle)
```

---

## LoopDetector API

### Ініціалізація

```python
from functions.runtime.core_loop_detector import LoopDetector

ld = LoopDetector(max_repeats=3)
```

### Перевірка на зациклення

```python
is_loop = ld.is_looping("click", {"x": 100, "y": 200})
if ld.is_stuck:
    print("Агент зациклився")
```

### Обробка успішних дій

```python
ld.on_action_success()  # скидає is_stuck
```

### Попередження для LLM

```python
warning = ld.get_stuck_warning_message()
# "КРИТИЧНЕ ЗАУВАЖЕННЯ: Ти щойно намагався..."
```

### Статистика

```python
stats = ld.get_stats()
# {'is_stuck': False, 'total_loops_detected': 2, ...}
```

### Скидання

```python
ld.reset()           # очистити історію (після виявлення)
ld.full_reset()      # повне скидання для нової сесії
```

---

## SessionBudget API

```python
from functions.runtime.core_session_budget import SessionBudget, SessionLimits

budget = SessionBudget(limits=SessionLimits(
    max_duration_seconds=3600,
    max_steps=200,
    max_tokens=100000,
))

# Після кожного LLM-виклику:
budget.record_tokens(prompt_tokens=500, completion_tokens=200)

# Перевірка:
if budget.check() == False:
    print("Бюджет вичерпано")
```

`SessionBudget` інтегрується з `ProviderRegistry.chat(budget=...)` для автоматичного запису usage.

---

## Project Indexer API

```python
from functions.project_indexer import (
    get_repo_map, get_file_dependents, update_repo_map, search_in_code
)

# Repo Map — компактна карта проєкту
map_text = get_repo_map()

# Dependency graph — хто залежить від файлу
dependents = get_file_dependents("functions/planning/agent_loop.py")

# Оновити після зміни
update_repo_map("functions/planning/agent_loop.py")

# Пошук по коду
matches = search_in_code("AgentLoopConfig")
```

---

## Global Voice Input API

```python
from functions.global_voice_input import GlobalVoiceInput

def on_voice_text(text: str):
    print(f"Розпізнано: {text}")

def on_status(status: str):
    print(f"Статус: {status}")

gvi = GlobalVoiceInput(
    hotkey="ctrl+shift+v",
    callback=on_voice_text,
    status_callback=on_status
)
gvi.start()
# ...
gvi.stop()
```

---

## Skills API (НОВИЙ, Фаза 1.3)

```python
from functions.skills.registry import SkillRegistry
from functions.skills.browser_skills import OpenBrowser, SearchGoogle, FillForm

registry = SkillRegistry()
registry.register(OpenBrowser())
registry.register(SearchGoogle())
registry.register(FillForm())

# Виконати
skill = registry.find("open_browser")
result = await skill.execute(url="https://google.com")
# result — SkillResult з success, data, error
```

Browser skills мають fallback ланцюжок: `playwright` → `CDP` → `subprocess`.

---

## AssistantCore API (main.py)

### Ініціалізація

```python
from main import AssistantCore
import queue

gui_queue = queue.Queue()
core = AssistantCore(gui_queue=gui_queue)
core.initialize_without_listener()
```

### Обробка команди

```python
core.process_text_command("Створи файл test.py")
```

### Запуск AgentLoop

```python
core.run_agent_loop("Створи проєкт з 3 файлами")
```

### Windsurf Watcher

```python
core.start_windsurf_watch()
# ...
core.stop_windsurf_watch()
```

---

## GUI Queue API

### Повідомлення в GUI

```python
gui_queue.put(('add_message', ('assistant', 'Привіт!')))
gui_queue.put(('update_status', 'Готовий'))
gui_queue.put(('update_progress', 50))
```

### Типи повідомлень

| Тип | Параметри | Опис |
|-----|-----------|------|
| `add_message` | `(sender, message)` | Додати повідомлення в чат |
| `update_status` | `status: str` | Оновити статус |
| `update_progress` | `value: int` | Оновити прогрес |
| `stream_start` | - | Початок стрімінгу |
| `stream_chunk` | `chunk: str` | Чанк стрімінгу |
| `stream_end` | - | Кінець стрімінгу |
| `show_confirmation` | `question: str` | Показати підтвердження |
| `execution_started` | - | Виконання запущено |
| `execution_finished` | - | Виконання завершено |
| `plan_started` | `plan: dict` | План запущено |
| `step_update` | `step: dict` | Крок оновлено |
| `plan_finished` | `stats: dict` | План завершено |
| `context_update` | `{used, limit, model}` | Оновлення usage контексту |
| `windsurf_started` | - | Windsurf Watch запущено |
| `windsurf_stopped` | - | Windsurf Watch зупинено |
| `windsurf_response` | `response: dict` | Відповідь від Windsurf |
| `windsurf_error` | `error: str` | Помилка Windsurf |

---

## StreamingBuffer API

```python
from functions.llm.streaming_buffer import StreamingBuffer

buffer = StreamingBuffer(
    on_status=lambda msg: gui_queue.put(('update_status', msg)),
    on_context_update=lambda used, limit, model:
        gui_queue.put(('context_update', {'used': used, 'limit': limit, 'model': model})),
    context_limit=128000,
    model="claude-sonnet-4-6",
)

# Під час стрімінгу:
for chunk in stream:
    estimated = buffer.add_chunk(chunk)  # -> int (estimated tokens)

# Після стрімінгу:
buffer.finish(real_usage_dict)  # замінює оцінку реальним usage
```

Використовується для live-оновлення статус-бару контексту в `MainWindowPyQt6` (QProgressBar з кольорами 0-60%/60-80%/80-95%/95+%).

---

## Agent Coordinator API

```python
from functions.planning.agent_coordinator import AgentCoordinator

coordinator = AgentCoordinator(
    agent_loop=loop,
    router=router,
    provider_chain=chain,
    registry=function_registry,
)

result = coordinator.run(task)  # маршрутизує через router + provider_chain
coordinator.request_stop()  # зовнішня зупинка
```

---

## WindsurfWatcher API

```python
from functions.runtime.core_windsurf_watcher import (
    WindsurfWatcherConfig, WindsurfWatcherRunner
)

config = WindsurfWatcherConfig(
    max_tokens=4096,
    temperature=0.2,
    watch_interval=1.0,
)
runner = WindsurfWatcherRunner(config=config, gui_queue=gui_queue)
runner.start()
# ...
files = runner.get_open_files()
runner.stop()
```

GUI інтегровано в `tab_settings.py` (кнопка toggle start/stop).

---

## Примітка

API знаходиться в активній розробці. Деталі можуть змінюватися. Див. [TASKS.md](../TASKS.md) "Пріоритет 1" для поточних неузгодженостей API з тестами.
