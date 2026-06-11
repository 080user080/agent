# Поточні задачі МАРК

## Загальні примітки

### ВАЖЛИВО: віртуальне середовище
Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash

# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

### Debug-Loop
**Відладка проводиться за допомогою Debug-Loop.**

Debug-Loop — це універсальний метод відладки, який використовується в цьому проекті для систематичного пошуку та виправлення помилок.

docs/DEBUG_LOOP.md --- тут більш детально описано цей метод.

**Коли використовувати:** Коли ви пишете в чаті слово **"дебаг"**, **"debug"**, або **"Debug-Loop"**, це означає що треба виконати саме цей метод.

### Правила ведення цього файлу
- Тут лише **актуальні задачі**, без довгих історичних фаз і PR-хронології.
- Виконані завдання (блоком, якщо є щось не виконане то залишається весь блок) перенесяться в [TASKS_Done.md]
- `status.md` відповідає на питання **"де ми зараз?"**
- `TASKS.md` відповідає на питання **"що робимо далі?"**
- `docs/ARCHITECTURE.md` відповідає на питання **"чому саме так і в якому технічному порядку?"**

### Пріоритети та статуси





- Пріоритети: `P0` > `P1` > `P2`
- Статуси: `Завершено` > `В процесі` > `Не розпочато`

---

# План рефакторингу для агента ✅ (Фази 1-3 завершено)

---

## Фаза 4 — Виправлення LLM-шару

### 4.1 Підключити router та provider_chain
- `RequestRouter.classify()` викликати на початку `AgentCoordinator.run()` ✅
- `ProviderChain.execute()` використовується замість прямого `call_endpoint()` у `functions/llm/helpers.py` (ask_llm спочатку пробує ProviderChain, потім fallback на call_endpoint) ✅
- [x] Відмітити виконання в TASK.md

### 4.2 Стабілізувати JSON parsing в ActionDecider
- В `functions/agent/plan.py` метод `decide()` — додано більш агресивне очищення відповіді перед парсингом (через `_fix_truncated_json()` + `_try_json_load()`) ✅
- Додано підтримку обрізаного JSON (дописати закриваючі дужки через `_fix_truncated_json()`) ✅
- Збільшено ліміт consecutive JSON failures до 5 перед `force done` ✅
- [x] Відмітити виконання в TASK.md

### 4.3 Виправити конфігурацію Vision-LM
- `VisionLMProvider.detect_ui_elements()` та `suggest_actions()` — задокументовано як заглушки з `TODO` + `NOTE` + `RETURN` коментарями ✅
- Додано метод `describe()` для сумісності з `observe()` (викликає `vision.describe()`) ✅
- `enable_vision=True` не ламає AgentLoop — всі помилки vision обгорнуті в try/except в `observe()` ✅
- [x] Відмітити виконання в TASK.md

---

## Фаза 5 — Підключення неінтегрованих модулів

### 5.1 Підключити WindsurfWatcher до GUI
- В `main_window.py` або `tab_settings.py` додати кнопку/перемикач "Start Windsurf Watch" ✅
  - Додано в `core_gui_pyqt6/tab_settings.py`: кнопка `_windsurf_watch_btn` з toggle start/stop
- `AssistantCore` має зберігати `WindsurfWatcherRunner` і передавати його стан у GUI через `gui_queue` ✅
  - Додано методи `start_windsurf_watch()` та `stop_windsurf_watch()` в `AssistantCore` (main.py)
  - Додано обробку повідомлень `windsurf_started`, `windsurf_stopped`, `windsurf_response`, `windsurf_error` в `main_window.py`
  - Додано `update_watcher_status_from_executor()` в `SettingsTab` для live-статусу
- [x] Відмітити виконання в TASK.md

### 5.2 Підключити StepRepairer надійно
- Перевірити що `RepairProposer` має доступ до робочого `ask_llm` при виклику з `AgentLoop._try_repair()` ✅
- Додати guard: якщо `assistant` або `ask_llm` недоступний — `StepRepairer.is_available()` повертає `False` ✅
  - Розширено `StepRepairer.is_available()` в `functions/planning/logic_repair_loop.py`: перевіряє наявність `ask_llm` або `get_llm` через `getattr()`
- [x] Відмітити виконання в TASK.md

---

## Фаза 6 — Виправлення pipeline_code (Phase 13) ✅

### 6.1 Реалізувати `_scaffold_content()`
- Замість `raise NotImplementedError` — генерувати базовий шаблон `.py` файлу з docstring та TODO-заглушками ✅
- Для тестових файлів — генерувати базовий `pytest` шаблон ✅
- [x] Відмітити виконання в TASK.md

### 6.2 Підключити `ai_actors` до CodePipeline
- `AIActor._execute_windsurf()` та `_execute_cursor()` — реалізувати через наявний `tools_browser_cdp.py` ✅
  - Виправлено відносні імпорти (`.tools_browser_cdp`) на абсолютні (`functions.tools.tools_browser_cdp`)
- `ActorRegistry.execute_with_fallback()` викликати з `CodePipeline.compile()` для заповнення scaffold ✅
  - Додано поле `use_ai_actors: bool = False` (вимкнено за замовчуванням)
  - Додано метод `_generate_with_ai()` для AI-генерації контенту через fallback
  - Налаштовано порядок провайдерів: CODEX → WINDSURF → CURSOR
- [x] Відмітити виконання в TASK.md

---

## Фаза 7 — Розбиття роздутих модулів

## Фаза 7 — Розбиття роздутих модулів (детальний план для агента кодування)

### Загальні вимоги до рефакторингу

1. **Зворотна сумісність** – публічні API класів (`AgentLoop`, `AssistantCore`, `FunctionRegistry`) не змінюються.
2. **Нові модулі** розміщувати згідно з існуючою структурою:
   - `functions/planning/` – для `AgentObserver`, `AgentPlanner`
   - `functions/runtime/` – для `LLMSubsystem` і системних промптів
3. **Тестування** – після кожного підпункту перевірити базові сценарії:
   - Чат: «привіт» → текстова відповідь
   - Команда: «відкрий блокнот» → відкриття програми
   - Команда: «створи файл test.py з кодом print(1+1)» → створення файлу
4. **Коміти** – кожен підпункт окремим комітом з описом «Phase 7.X: ...»
5. **Позначення в TASK.md** – після виконання кожного блоку додати `[x]` у відповідному рядку.

---

## 7.1 Розбити `AgentLoop`

### Поточний стан
Файл `functions/planning/agent_loop.py` містить клас `AgentLoop` (~200 рядків). Основний недолік – метод `plan()` містить складну логіку вибору джерела плану:
1. LLM `ActionDecider`
2. `Planner.create_plan()` (legacy, тільки перший крок)
3. Продовження плану через збережений `_plan_steps`
4. `CompiledPlan` від TaskSpec
5. Fallback `noop`/`done`

**Мета:** винести цю логіку в окремий клас `AgentPlanner`, а фазу спостереження – в `AgentObserver`.

### План реалізації

#### Крок 1. Створити `functions/planning/agent_observer.py`

```python
"""AgentObserver – фаза спостереження (обгортка над observe)."""

from functions.agent.observe import ObserveConfig, observe as _observe

class AgentObserver:
    def __init__(self, assistant, config: ObserveConfig = None):
        self.assistant = assistant
        self.config = config or ObserveConfig(
            enable_ocr=True,
            enable_vision=False,
            enable_ui_elements=True,
        )
    
    def observe(self, task: str):
        return _observe(config=self.config, assistant=self.assistant, task=task)
```

#### Крок 2. Створити `functions/planning/agent_planner.py`

```python
"""AgentPlanner – фаза планування (вибір стратегії)."""

from typing import Any, Dict, Optional

class AgentPlanner:
    def __init__(self, assistant, decider, compiled_plan=None):
        self.assistant = assistant
        self.decider = decider
        self.compiled_plan = compiled_plan
        self._plan_steps = None   # для продовження Planner
    
    def set_compiled_plan(self, cp):
        self.compiled_plan = cp
    
    def plan(self, task: str, obs: Any, state: Any) -> Dict[str, Any]:
        # 1. LLM ActionDecider
        if self.decider and self.decider.is_available:
            result = self._plan_from_decider(task, obs, state)
            if result:
                return result
        
        # 2. Planner (перший крок)
        if state.step == 0:
            plan = self._plan_from_planner(task)
            if plan:
                self._plan_steps = plan
                return self._step_from_plan(state.step)
        
        # 3. Продовження плану від Planner
        if self._plan_steps and state.step < len(self._plan_steps):
            return self._step_from_plan(state.step)
        
        # 4. CompiledPlan
        if self.compiled_plan and state.step < len(self.compiled_plan.steps):
            return self.compiled_plan.steps[state.step]
        
        return {"action": "noop", "args": {}, "done": True}
    
    def _plan_from_decider(self, task, obs, state):
        # копіюємо оригінальну логіку з AgentLoop.plan()
        ...
    
    def _plan_from_planner(self, task):
        planner = getattr(self.assistant, 'planner', None)
        if planner:
            try:
                return planner.create_plan(task)
            except Exception:
                return None
        return None
    
    def _step_from_plan(self, step_idx):
        step = self._plan_steps[step_idx]
        return {
            "action": step.get("action", "noop"),
            "args": step.get("args", {}),
            "done": step.get("done", False),
            "step_index": step_idx,
            "total_steps": len(self._plan_steps),
        }
```

#### Крок 3. Рефакторинг `AgentLoop`

Зміни в `functions/planning/agent_loop.py`:

```python
# Додати імпорти
from .agent_observer import AgentObserver
from .agent_planner import AgentPlanner

class AgentLoop:
    def __init__(self, ..., decider=None, compiled_plan=None):
        ...
        self._observer = AgentObserver(assistant, ObserveConfig(...))
        self._planner = AgentPlanner(assistant, decider, compiled_plan)
    
    def observe(self):
        return self._observer.observe(self._current_task)
    
    def plan(self, task, obs, state):
        return self._planner.plan(task, obs, state)
    
    def set_compiled_plan(self, cp):
        self._planner.set_compiled_plan(cp)
    
    # Всі інші методи (act, check, run) залишаються без змін
```

#### Крок 4. Оновлення `TASK.md`

Після завершення знайти рядок `### 7.1 Розбити AgentLoop` і замінити `[ ]` на `[x]`.

---

## 7.2 Розбити `AssistantCore` (`main.py`)

> **Примітка:** План базується на типовій структурі, яка видно з імпортів у `run_assistant_qt.py` та з використання `AudioInitializer`, `FunctionRegistry`, `AgentCoordinator`.

- [x] Перед створенням LLMSubsystem — перенести streaming wrapper 
      з process_text_command в окремий метод _stream_to_gui()
      щоб LLMSubsystem міг його використовувати ✅
- [x] Видалити _classify_task з AssistantCore — використовувати 
      commands_planner.classify_task (усунення дубліката) ✅
- [x] Перевірити де присвоюється self.gui в AssistantCore 
      (підозра: run_assistant_qt.py рядок ~AssistantAppQt) 
      і явно задокументувати цей зв'язок ✅

### Поточний стан (реконструкція)

`AssistantCore` (ймовірно) містить:
- Ініціалізацію аудіо (STT/TTS) – частково винесено в `AudioInitializer`, але не використовується
- Ініціалізацію LLM (endpoints, streaming)
- Ініціалізацію `FunctionRegistry`, `Planner`, `AgentCoordinator`
- Методи обробки команд: `process_text_command`, `run_agent_loop`, `stop_execution`
- Інтеграцію з `GlobalVoiceInput`

**Мета:** залишити в `AssistantCore` тільки координацію, а конкретні підсистеми винести.

### План реалізації

#### Крок 1. Підключити існуючий `AudioInitializer`

У `main.py` (або в `AssistantCore.initialize_without_listener`) замінити власний код ініціалізації аудіо на:

```python
from functions.audio.initializer import AudioInitializer

audio_init = AudioInitializer(gui_queue=self.gui_queue)
result = audio_init.init_all(with_listener=False)   # без безперервного слухача
self.stt_engine = result["stt_engine"]
self.tts_engine = result["tts_engine"]
self.audio_filter = result["audio_filter"]
```

#### Крок 2. Створити `LLMSubsystem` у `functions/runtime/llm_subsystem.py`

```python
"""LLMSubsystem – ініціалізація та управління LLM-ендпоінтами."""

from functions.llm.endpoint_client import get_primary_endpoint, get_secondary_endpoint
from functions.llm.streaming_buffer import StreamingBuffer

class LLMSubsystem:
    def __init__(self, gui_queue=None):
        self.gui_queue = gui_queue
        self.primary = None
        self.secondary = None
        self.streaming_buffer = StreamingBuffer()
    
    def init_endpoints(self):
        self.primary = get_primary_endpoint()
        self.secondary = get_secondary_endpoint()
        return self.primary is not None
    
    def ask_llm(self, messages, stream_callback=None):
        # логіка виклику LLM з fallback (копіюємо з існуючого методу)
        ...
```

#### Крок 3. Рефакторинг `AssistantCore`

Структура після змін:

```python
class AssistantCore:
    def __init__(self, gui_queue):
        self.gui_queue = gui_queue
        self.llm = None          # LLMSubsystem
        self.audio = None        # AudioInitializer
        self.registry = FunctionRegistry()
        self.planner = None
        self.agent_coordinator = None
    
    def initialize_without_listener(self):
        # 1. LLM
        self.llm = LLMSubsystem(self.gui_queue)
        if not self.llm.init_endpoints():
            log_console("⚠️ LLM endpoints not configured")
        
        # 2. Audio
        self.audio = AudioInitializer(self.gui_queue)
        audio_result = self.audio.init_all(with_listener=False)
        self.tts_engine = audio_result["tts_engine"]
        
        # 3. Registry, Planner, AgentCoordinator (без змін)
        ...
        return True
    
    def process_text_command(self, text):
        # використовує self.llm.ask_llm(...)
        ...
```

#### Крок 4. Оновлення `TASK.md`

Знайти рядок `### 7.2 Розбити AssistantCore (main.py)` і замінити `[ ]` на `[x]`.

---

## 7.3 Винести system prompt з `FunctionRegistry` ✅

### Поточний стан

У `functions/runtime/logic_core.py` метод `FunctionRegistry.get_system_prompt()` містить **хардкоджені** тексти:
- `_get_voice_system_prompt()` – для голосового режиму (~80 рядків)
- `get_coding_system_prompt()` – для режиму кодування (~120 рядків)

**Проблема:** зміна промпту вимагає редагування коду.  
**Мета:** винести в окремі JSON-файли в папку `d:\Python\agent\runtime\prompts\`, з можливістю перезавантаження.

### План реалізації

#### Крок 1. Створити директорію та JSON-файли

```
d:\Python\agent\runtime\prompts\
├── voice_prompt.json
├── coding_prompt.json
└── (можливо інші)
```

**Приклад `voice_prompt.json`:**

```json
{
  "template": "ТИ: {ASSISTANT_NAME}, асистент-кодер. Мова: українська.\nРЕЖИМ: {ACTIVE_MODE} ({max_words} слів, {max_sentences} реч).\n\nПРАВИЛА ВІДПОВІДІ (ти сам вирішуєш — відповісти текстом чи виконати дію):\n1. Привітання, соціальні фрази, питання → {\"response\":\"текст відповіді\"}\n2. Прості дії → {\"action\":\"назва_функції\",\"параметр\":\"значення\"}\n3. СКЛАДНІ задачі → {\"action\":\"run_agent_loop\",\"task\":\"опис задачі\"}\n\nДОСТУПНІ ФУНКЦІЇ:\n{FUNCTIONS_LIST}\n\nЗАВЖДИ ПОВЕРТАЙ JSON З action!"
}
```

**Приклад `coding_prompt.json`:**

```json
{
  "template": "ТИ: Агент-розробник {ASSISTANT_NAME} для роботи з кодом.\n\nАЛГОРИТМ РОБОТИ З КОДОВОЮ БАЗОЮ (виконувати суворо по порядку):\n1. **ОРІЄНТАЦІЯ** — викликати `get_repo_map()`\n2. **ПОШУК** — визначити файли які стосуються задачі\n3. **АНАЛІЗ ЗАЛЕЖНОСТЕЙ** — викликати `get_file_dependents(filepath)`\n4. **ЧИТАННЯ** — прочитати тільки потрібні файли через `read_code_file`\n5. **ЗМІНА** — внести зміну (`edit_file` або `create_file`)\n6. **ОНОВЛЕННЯ ІНДЕКСУ** — викликати `update_repo_map(filepath)`\n7. **ПЕРЕВІРКА** — `execute_python`\n\n⚠️ КРИТИЧНІ ЗАБОРОНИ:\n1. НІКОЛИ не змінюй файл не перевіривши його залежності\n2. НІКОЛИ не читай весь проєкт файл за файлом — використовуй `get_repo_map`\n3. ЗАБОРОНЕНО використовувати `execute_python` з `time.sleep`\n\nДОСТУПНІ ФУНКЦІЇ (перші 15):\n{FUNCTIONS_LIST}\n\nФОРМАТ ВІДПОВІДІ (два варіанти):\nA) Є конкретна технічна задача → {\"action\":\"назва\",\"параметр\":\"значення\"}\nB) Питання, привітання, незрозуміла команда → {\"response\":\"текст\"}"
}
```

#### Крок 2. Створити модуль завантаження промптів

Файл `functions/runtime/prompt_loader.py`:

```python
import json
import os
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "runtime" / "prompts"

def load_prompt_template(name: str) -> str:
    """Завантажити шаблон з JSON-файлу."""
    path = PROMPTS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("template", "")
```

#### Крок 3. Змінити `FunctionRegistry.get_system_prompt()`

У `functions/runtime/logic_core.py`:

```python
from .prompt_loader import load_prompt_template

class FunctionRegistry:
    # ... інші методи ...
    
    def get_system_prompt(self, mode: str = None):
        from functions.config import ASSISTANT_NAME, ACTIVE_MODE, ASSISTANT_MODES
        
        active_mode = mode or ACTIVE_MODE
        mode_info = ASSISTANT_MODES.get(active_mode, {})
        
        # Завантажити шаблон
        if active_mode == "coding":
            template = load_prompt_template("coding_prompt")
        else:
            template = load_prompt_template("voice_prompt")
        
        # Підставити значення
        functions_list = self._format_functions_list()
        prompt = template.format(
            ASSISTANT_NAME=ASSISTANT_NAME,
            ACTIVE_MODE=active_mode,
            max_words=mode_info.get("max_words", 10),
            max_sentences=mode_info.get("max_sentences", 2),
            FUNCTIONS_LIST=functions_list,
        )
        
        # Додати Repo Map для coding режиму
        if active_mode == "coding":
            repo_map = self._get_repo_map()
            if repo_map:
                prompt += f"\n\n📋 REPO MAP:\n{repo_map}\n"
        
        return prompt
    
    def _format_functions_list(self, max_funcs: int = 15) -> str:
        """Сформувати список функцій для вставки в промпт."""
        if not self.functions:
            return "⚠️ Функції недоступні."
        lines = []
        for name, info in sorted(self.functions.items())[:max_funcs]:
            lines.append(f"• {name}: {info['description'][:50]}...")
        if len(self.functions) > max_funcs:
            lines.append(f"... та ще {len(self.functions) - max_funcs} функцій")
        return "\n".join(lines)
    
    def _get_repo_map(self) -> str:
        try:
            from functions.project_indexer import get_repo_map
            return get_repo_map()
        except Exception:
            return ""
```

#### Крок 4. Додати можливість перезавантаження (опціонально)

Метод для оновлення промптів без перезапуску:

```python
def reload_prompts(self):
    """Перезавантажити JSON-файли промптів."""
    import importlib
    import functions.runtime.prompt_loader as pl
    importlib.reload(pl)
    # очистити кеш, якщо є
    self._prompt_cache = None
```

#### Крок 5. Оновлення `TASK.md`

Знайти рядок `### 7.3 Винести system prompt з FunctionRegistry` і замінити `[ ]` на `[x]`.

---

## Підсумкові дії після всіх трьох пунктів

1. Запустити `run_assistant_qt.py` і виконати smoke-тест:
   - Відкрити GUI, написати «привіт» → текстова відповідь
   - Написати «відкрий блокнот» → відкривається Notepad
   - Написати «створи файл test.py з кодом print(1+1)» → файл створюється
   - Якщо STT увімкнено – перевірити голосове введення
2. Переконатись, що всі три пункти в `TASK.md` позначені як `[x]`.
3. Зробити фінальний коміт з повідомленням: `Phase 7: Refactor AgentLoop, AssistantCore, extract system prompts`.

---
---

## Фаза 8 — Конфігурація

### 8.1 Типізувати config.py ✅
- Додати анотації типів до всіх констант ✅ (AudioConfig, TTSConfig, LLMEndpoint dataclasses)
- Константи що стосуються одної підсистеми — згрупувати в датакласи або `TypedDict` ✅
- [x] Відмітити виконання в TASK.md

### 8.2 Усунути прямі імпорти config (частково)
- Знайти всі `from functions.config import X` поза `core_settings.py` ✅ (знайдено 15 файлів)
- Додано deprecated note в config.py docstring ✅
- Повна міграція на get_setting() — поетапна (застосовується при наступних правках файлів)
- [ ] Відмітити виконання в TASK.md (повна міграція — відкласти)

---

## Фаза 9 — Тестування

### 9.1 Відновити pytest collection
- Запустити `pytest --collect-only` і виправити всі помилки збору
- [ ] Відмітити виконання в TASK.md

### 9.2 Додати smoke-тести для критичних шляхів
- Тест: `AgentCoordinator.run()` з моком `ActionDecider` та `FunctionRegistry`
- Тест: `TaskRunner.run()` з простим планом з 2 кроків
- Тест: `PermissionGate.check()` для дозволених і заборонених дій
- [ ] Відмітити виконання в TASK.md

### 9.3 Mock Windows-залежностей
- Всі `win32gui`, `win32con`, `uiautomation` — обернути в `try/except ImportError` якщо ще не зроблено
- Додати `conftest.py` що підставляє заглушки для Windows API в CI
- [ ] Відмітити виконання в TASK.md


Ось детальний список завдань для кодуючого агента (**Cline** або будь-якого іншого AI-розробника), оформлений точно за вашим зразком. Кожен блок містить конкретні технічні кроки для усунення виявлених архітектурних проблем проекту **Mark**.

---

### 1.1 Оптимізація потокової безпеки між Ядром та PyQt6 GUI

* Замінити прямі виклики методів або синхронне читання віджетів з фонового потоку `run_core_in_thread` на використання нативних сигналів `pyqtSignal`
* Перевести `queue_dispatcher` на роботу через QThread або зв'язати його з Qt Event Loop, щоб уникнути блокування інтерфейсу під час інтенсивного логування
* Перевірити всі методи оновлення стану UI у `core_gui_pyqt6/main_window.py` та переконатися, що вони викликаються виключно через механізм сигналів/слотів
* [ ] Відмітити виконання в TASK.md

### 1.2 Запобігання нескінченним циклам у відновленні планів

* Додати параметр жорсткого ліміту спроб (`max_repair_attempts = 3`) у класи `logic_repair_loop.py` та `planner_repair.py`
* Реалізувати механізм переривання циклу (Break), якщо локальна модель (Qwen/DeepSeek) видає некоректний або пошкоджений JSON кілька разів поспіль
* Додати генерацію фінального звіту про критичну помилку користувачу в чат у разі перевищення ліміту спроб самовідновлення, замість падіння в стазис
* [ ] Відмітити виконання в TASK.md

### 1.3 Підвищення стабільності аналізу інтерфейсу Windows

* Змінити пріоритет взаємодії в ОС: перенести основну логіку з аналізу скріншотів (`tools_ui_detector.py`) на нативне дерево елементів через `tools_ui_accessibility.py`
* Додати коефіцієнт динамічної денормалізації координат у `tools_window_manager.py`, що автоматично враховує поточне масштабування екрана Windows (DPI Scaling: 100%, 125%, 150%)
* Налаштувати резервний сценарій (fallback): якщо OpenCV контури у `cv2.boundingRect` повертають нульові координати, система автоматично перемикається на пошук через текстові дескриптори або гарячі клавіші
* [ ] Відмітити виконання в TASK.md

### 1.4 Управління тривалими таймаутами без блокування інтерфейсу

* Перенести мережеві запити до ендпоінтів LLM у `llm_endpoints_editor_qt.py` та адаптерах у неблокуючий режим (асинхронно через `asyncio` або фонові потоки Qt)
* Реалізувати динамічний таймаут (наприклад, збільшення ліміту до 120-180 секунд автоматично, якщо агент виконує завдання кодування великих файлів через `pipeline_code.py`)
* Додати візуальний індикатор завантаження (Spinner/Progress Bar) або потоковий лог «Агент думає...» у вікно чату, щоб інтерфейс не виглядав завислим під час тривалих операцій
* [ ] Відмітити виконання в TASK.md

### 1.5 Ізоляція середовища виконання коду (Sandbox)

* Додати у `core_safety_sandbox.py` базову валідацію генерованого Python-коду перед запуском через абстрактне синтаксичне дерево (`ast.parse`) на наявність небезпечних системних викликів (наприклад, `shutil.rmtree` кореневих директорій, `os.system` небезпечних утиліт)
* Обмежити область видимості для `aaa_execute_python.py`, змусивши його виконувати скрипти виключно в ізольованій тимчасовій папці проекту (наприклад, `D:\Python\agent\sandbox_run\`), заборонивши вихід за її межі
* Додати обов'язковий крок верифікації (Confirmation Prompt) у GUI через `confirmation_qt.py` для будь-яких операцій, що класифікуються як потенційно деструктивні
* [ ] Відмітити виконання в TASK.md

### 1.6 Розумне бюджетування контексту в ContextController

* Переписати логіку очищення контексту в `ContextController`: замість жорсткого видалення повідомлень до ліміту у 2 репліки, впровадити підрахунок токенів
* Реалізувати механізм ковзного вікна (Rolling Window), що зберігає системні інструкції (System Prompt) та цілі (Goals), але стискає або підсумовує (Summarize) лише проміжні технічні логи виконання
* Додати у `pipeline_code.py` пофайлове зчитування (Chunking) замість завантаження всього вмісту великих PyQt6 файлів у контекст за один раз
* [ ] Відмітити виконання в TASK.md


# Self-Coding Agent Pipeline

## Мета
Дати агенту здатність аналізувати власний код, планувати зміни та вносити їх безпечно.

---

## Фаза 1 — Само-читання та аналіз

### Крок 1.1 — Self-context builder ✅
Створити `functions/planning/self_code_context.py`
Функція `build_self_context(task: str) -> dict`:
- використовує існуючі `get_repo_map()`, `search_in_code()`, `read_code_file()` з `aaa_code_tools.py` ✅
- повертає контекст для LLM: які файли релевантні, їх поточний стан ✅

- [x] Відмітити виконання в TASK.md ✅

### Крок 1.2 — Gap analyzer ✅
Функція `analyze_gap(task: str, context: dict) -> dict` в тому ж файлі:
- через LLM визначає що треба змінити/додати ✅
- повертає список файлів для зміни + опис змін ✅
- перевіряє чи файл не в `SELF_EDIT_BLACKLIST` (з Кроку 5.1) — реалізується коли буде створено self_code_safety.py в Фазі 5.1

- [x] Відмітити виконання в TASK.md ✅

---

## Фаза 2 — Безпечне редагування

### Крок 2.1 — Snapshot перед редагуванням
`SelfCodingPipeline` викликає існуючий `UndoManager.save_snapshot()` перед кожним патчем.
`edit_file()` не чіпаємо — у нього вже є власний datetime-бекап.

⚠️ **ВІДКЛАДЕНО до Фази 4** — `SelfCodingPipeline` не існує ще (pipeline_self_coding.py не створено).
Реалізується разом з Кроком 4.1. `UndoManager.save_snapshot()` вже готовий до використання.

- [ ] Відмітити виконання в TASK.md (разом з Фазою 4, Крок 4.1)

### Крок 2.2 — Code patch generator ✅
Створити `functions/planning/self_code_patcher.py` ✅
Функція `generate_patch(file_path: str, task: str, context: dict) -> str`:
- читає поточний вміст файлу через `read_code_file()` ✅
- через LLM генерує тільки змінену частину (не весь файл) ✅
- перед поверненням валідує через існуючий `PythonSandbox.validate_code()` з `aaa_execute_python.py` ✅
- якщо синтаксис невалідний — повертає помилку, не записує файл ✅

- [x] Відмітити виконання в TASK.md ✅

---

## Фаза 3 — Верифікація після змін

### Крок 3.1 — Post-edit verification ✅
Функція `verify_edit(file_path: str, task: str) -> dict` в `self_code_patcher.py` ✅:
- повторно читає змінений файл через `read_code_file()` ✅
- через LLM перевіряє чи зміна відповідає задачі ✅
- оновлює repo map через існуючий `update_file_in_map()` ✅
- повертає `{ok, summary, warnings}` ✅

- [x] Відмітити виконання в TASK.md ✅

### Крок 3.2 — Автоматичний rollback ✅
Якщо `verify_edit` повертає `ok=False`:
- викликати існуючий `UndoManager.restore_snapshot()` ✅
- залогувати через існуючий `SelfLearning.log_execution()` як невдалу спробу ✅
- повернути детальний звіт ✅

Додатково: `verify_and_maybe_rollback()` — обгортка для зручного виклику з pipeline.

- [x] Відмітити виконання в TASK.md ✅

---

## Фаза 4 — Pipeline інтеграція

### Крок 4.1 — Self-coding pipeline
Створити `functions/planning/pipeline_self_coding.py`
Клас `SelfCodingPipeline` — реалізує `Pipeline.compile()` як в існуючому `pipeline_code.py`:
- отримує `TaskSpec`
- будує `Plan` з кроків у послідовності:
  `build_self_context` → `analyze_gap` → `confirm_action` → `save_snapshot` → `generate_patch` → `verify_edit` → (rollback якщо треба)

- [x] Відмітити виконання в TASK.md

### Крок 4.2 — Реєстрація в `make_default_registry()`
В `core_plan_compiler.py` додати `DOMAIN_SELF_CODE` та зареєструвати `SelfCodingPipeline`.

- [x] Відмітити виконання в TASK.md

---

## Фаза 5 — Захисні обмеження

### Крок 5.1 — Blacklist файлів
Створити `functions/planning/self_code_safety.py`
`SELF_EDIT_BLACKLIST` — файли які агент не може змінювати:
- `core_safety_sandbox.py`
- `logic_permission_gate.py`
- `core_tool_runtime.py`
- `main.py`
- `run.py`
- `self_code_safety.py` (сам себе)

Функція `is_edit_allowed(file_path: str) -> tuple[bool, str]`

- [ ] Відмітити виконання в TASK.md

### Крок 5.2 — Підтвердження користувача
`SelfCodingPipeline` викликає існуючий `confirm_action()` з `aaa_confirmation.py` перед кожним записом патча.
Без підтвердження — тільки читання та аналіз, жодного запису.

- [ ] Відмітити виконання в TASK.md

---

## Залежності між кроками

```
5.1 → 1.2 (blacklist потрібен в analyze_gap)
1.1 → 1.2 → 4.1
2.1 → 2.2 → 3.1 → 3.2
4.1 → 4.2
```

Рекомендований порядок виконання: **5.1 → 1.1 → 1.2 → 2.2 → 3.1 → 3.2 → 2.1 → 4.1 → 4.2 → 5.2**

---

## Критичні ризики

| Ризик | Мітигація |
|-------|-----------|
| Зламаний синтаксис | `PythonSandbox.validate_code()` перед записом |
| Нескінченна рекурсія само-редагування | `SELF_EDIT_BLACKLIST` |
| Непередбачені побічні ефекти | `UndoManager` snapshot + rollback |
| LLM галюцинує функції | `verify_edit()` після зміни |
| Зміна ламає safety модулі | Blacklist ізолює критичні файли |



# Завдання: Виправлення двох багів — list_directory та склеювання слів

## Мета
Виправити баги:
1. `list_directory()` не приймала параметр `path` → падала з `got an unexpected keyword argument 'path'`
2. Команди "подивися мій проект", "подивис, проект", "подивися папку" не розпізнавалися → LLM склеював слова

## Виконані кроки

### 1. list_directory — додано підтримку `path`
- [x] Відкрити `D:\Python\agent\functions\tools\aaa_file_operations.py`
- [x] Змінити сигнатуру: `def list_directory(directory: str = '.', path: str = None) -> dict`
- [x] Логіка: `directory = directory or path or '.'`
- [x] Відмітити виконання в TASK.md

### 2. Розширено _AMBIGUOUS_PROJECT_PATTERNS
- [x] Відкрити `D:\Python\agent\functions\gui\commands_planner.py`
- [x] Додано варіанти з "мій": `подивися мій проект`, `покажи мій проект`, `відкрий мій проект`
- [x] Додано варіанти з комою: `подивис, проект`, `покажи, код` тощо
- [x] Відмітити виконання в TASK.md

### 3. Виправлено _CLEAR_PATTERNS
- [x] Замінено `\s` на `(\s|$)` у всіх патернах з об'єктом
- [x] "подивися папку" тепер матчиться (раніше вимагало пробіл після "папку")
- [x] Відмітити виконання в TASK.md

### 4. Виправлено друкарську помилку
- [x] `\ss+` → `\s+` в одному з патернів

---

# Завдання: Виправлення рекурсивного завантаження модулів

## Мета
Виправити `load_all_modules()` в `functions/runtime/logic_core.py` — функції з підпапок (`functions/tools/`, `functions/skills/`) не завантажуються через не-рекурсивні glob-пошуки.

---

## Кроки

### 1. Відкрити файл для аналізу
- [x] Прочитати `D:\Python\agent\functions\runtime\logic_core.py` повністю
- [x] Відмітити виконання в TASK.md

### 2. Виправити glob для `core_*.py`
- [x] Знайти рядок з `functions_dir.glob("core_*.py")` (~54)
- [x] Замінити на `functions_dir.rglob("core_*.py")`
- [x] Відмітити виконання в TASK.md

### 3. Виправити glob для `aaa_*.py`
- [x] Знайти рядок з `functions_dir.glob("aaa_*.py")` (~82)
- [x] Замінити на `functions_dir.rglob("aaa_*.py")`
- [x] Відмітити виконання в TASK.md

### 4. Виправити glob для `tools_*.py`
- [x] Знайти рядок з `functions_dir.glob("tools_*.py")` (~107)
- [x] Замінити на `functions_dir.rglob("tools_*.py")`
- [x] Відмітити виконання в TASK.md

### 5. Додати блок завантаження `functions/skills/`
- [x] Після блоку `tools_*.py` додано новий блок, який:
  - Шукає `skills_dir = functions_dir / "skills"`
  - Перевіряє що директорія існує
  - Завантажує всі `*.py` крім `__init__.py` через `importlib`
  - Виводить лог аналогічно до інших блоків (`✅ skills/<назва> (N функцій)`)
- [x] Відмітити виконання в TASK.md

### 6. Перевірка дублікатів після rglob
- [x] Додано `_loaded_modules` — множина для відстеження завантажених імен
- [x] Кожен блок (core/aaa/tools) перевіряє `if module_name in _loaded_modules` перед завантаженням
- [x] Відмітити виконання в TASK.md

### 7. Запустити та перевірити
- [x] Запустити `run.py`
- [x] Переконатись у консолі що тепер виводиться завантаження функцій з `functions/tools/` (aaa_*, tools_*) та `functions/skills/`

---

## Очікуваний результат у консолі після виправлення

```
📦 Завантаження core модулів...
✅ core_settings (N функцій)
✅ core_memory (N функцій)
...

📦 Завантаження функцій...
✅ aaa_file_operations (N функцій)
✅ aaa_create_file (N функцій)
...

📦 Завантаження GUI Automation tools...
✅ tools_screen_capture (N функцій)
✅ tools_mouse_keyboard (N функцій)
✅ tools_project_indexer (4 функцій)
...

📦 Завантаження skills...
✅ skills/browser_skills (N функцій)
...
```

# Фікс: Режими Voice / Coding не розрізняються

## Мета
Слово "привіт" (і будь-яка розмовна фраза) не повинне запускати AgentLoop.
Voice-режим = планування/розмова. Coding-режим = виконання/дія.

## Кроки

### 1. Діагностика — знайти точку входу
- [x] Відкрити `run_assistant_qt.py`, метод `_handle_process_text()`
- [x] Знайти де саме викликається `run_agent_loop` або `AgentCoordinator.run()`
- [x] Перевірити чи є перевірка `classify_task()` перед запуском агента
- [x] **Висновок:** `_handle_process_text` уже має правильну гілку `if task_type == "CHAT"` (рядок 77). Код коректний.
- [x] Відмітити виконання в TASK.md

### 2. Діагностика — перевірити classify_task
- [x] Відкрити `functions/gui/commands_planner.py`
- [x] Перевірити що повертає `classify_task("привіт")` — `CHAT` ✅
- [x] Перевірити що повертає `classify_task("напиши функцію сортування")` — `AGENT` ✅
- [x] **Висновок:** `classify_task()` має greeting_keywords і правильно класифікує. `run_agent_loop()` у тому ж файлі НЕ викликає `classify_task` повторно — все всередині себе коректно.
- [x] Відмітити виконання в TASK.md

### 3. Діагностика — перевірити весь ланцюжок CHAT vs AGENT
- [x] Знайти всі місця де викликається `run_agent_loop` або `AgentCoordinator.run()`
- [x] **Ланцюжок з PyQt6 GUI:**
  - `ChatTab._send_text_command()` → emit `command_submitted`
  - `MainWindowPyQt6._on_command_submitted(command)` → `assistant_callback("process_text", command)`
  - `AssistantAppQt.gui_callback("process_text")` → `_handle_process_text(text)`
  - `_handle_process_text` → `classify_task()` → `CHAT` → `process_text_command()` (LLM без AgentLoop) ✅
  - `_handle_process_text` → `classify_task()` → не-CHAT → `run_agent_loop()` (AgentLoop) ✅
- [x] **Обхідні шляхи:** `gui_callback("run_agent")` (кнопка 🤖) — свідомо запускає AgentLoop без classify_task — очікувана поведінка
- [x] **Проблема:** `importlib.reload(gui.commands_planner)` у `_handle_process_text` — крихкий механізм з можливими проблемами кешування. **Виправлено** — замінено на прямий `import`.
- [x] Відмітити виконання в TASK.md

### 4. Виправити точку входу
- [x] `_handle_process_text` вже має правильну логіку: CHAT → `process_text_command()`, інакше → `AgentCoordinator`
- [x] **Виправлено:** прибрано `importlib.reload` — замінено на прямий `from functions.gui.commands_planner import classify_task`
- [x] Відмітити виконання в TASK.md

### 5. Перевірити needs_clarification
- [x] У `commands_planner.py` є `needs_clarification()` — вже викликає `classify_task()` і пропускає CHAT (не питає уточнення для вітань) — ✅
- [x] Для неоднозначних запитів агент має питати уточнення — вже працює через `_AMBIGUOUS_VERBS` — ✅
- [x] Відмітити виконання в TASK.md

### 6. Тест та перезапуск
- [x] `classify_task("привіт")` → `CHAT` ✅ (перевірено через python -c)
- [x] `classify_task("напиши функцію сортування")` → `AGENT` ✅ (перевірено)
- [x] `classify_task("відкрий notepad")` → `GUI_ACTION` ✅
- [x] **Виправлено:** прибрано `importlib.reload` з `run_assistant_qt.py`
- [ ] Запустити асистента та протестувати в реальному GUI
- [x] Відмітити виконання в TASK.md
кнопку 🤖



### Етап 2: Середній пріоритет — Доробка Accessibility-шару та Windows-інфраструктури

2.1. **Доробити accessibility-шар для Windows**

* Замінити заглушки "Not implemented yet" у файлі `functions/tools_ui_accessibility.py`.


* Повністю реалізувати функції `uia_list_elements`, `uia_find_button`, `uia_click_element`, `uia_set_text`.


* Провести повне smoke-тестування інтерфейсу в середовищі Windows.


* [ ] Відмітити виконання в TASK.md

2.2. **Додати Windows CI / smoke suite**

* Створити та інтегрувати спеціалізований smoke-набір тестів для автоматичної перевірки GUI та взаємодії з ОС Windows.


* [ ] Відмітити виконання в TASK.md

2.3. **Створити router для вибору агента**

* Реалізувати логіку Meta-agent, який аналізує складність задачі та визначає оптимального виконавця (локальний інструмент чи зовнішній AI-провайдер через API).


* [ ] Відмітити виконання в TASK.md

---

### Етап 3: Архітектурний рефакторинг великих модулів (God Objects)

3.1. **Рефакторинг `main.py`**

* Розділити перевантажений файл `main.py` (1242 рядки), який зараз несе забагато відповідальностей (state, app initialization, runtime wiring), на окремі ізольовані модулі.


* [ ] Відмітити виконання в TASK.md

3.2. **Рефакторинг `agent_loop.py`**

* Розрізати файл `agent_loop.py` (2008 рядків) на менші логічні компоненти з чітко визначеною зоною відповідальності.


* [ ] Відмітити виконання в TASK.md

3.3. **Рефакторинг `logic_permission_gate.py` та `logic_core.py`**

* Оптимізувати 4-рівневу policy stack у `logic_permission_gate.py` (~397 рядків) та усунути дублювання з `logic_expectations.py`.


* Зменшити зв'язність у `logic_core.py`: розвантажити `FunctionRegistry` та винести ~200 рядків хардкодженого тексту з методу `get_system_prompt()`.


* [ ] Відмітити виконання в TASK.md

3.4. **Рефакторинг `logic_commands.py` та `global_voice_input.py`**

* Винести надмірну бізнес-логіку з компонента `VoiceAssistant` у файлі `logic_commands.py`.


* Очистити й виділити в окрему логіку механізми вставки тексту в методах `_insert_segment` та `_send_input_unicode` у `global_voice_input.py`.


* [ ] Відмітити виконання в TASK.md

3.5. **Оптимізація планувальника та усунення накладання пайплайнів**

* Виправити перетин обов'язків між модулями `core_planner.py / core_planner_critic.py / core_planner_runner.py` та файлом `logic_task_runner.py`.


* Оптимізувати Phase 13 (компоненти `core_task_intake.py / task_spec.py / pipeline_code.py / core_plan_compiler.py`): зараз 4 файли обслуговують один пайплайн, хоча `ActionDecider` вже має вбудоване online-планування.


* [ ] Відмітити виконання в TASK.md

---

### Етап 4: Ліквідація дублювання коду та файлів

4.1. **Усунення дублювання конфігурацій та середовищ**

* Видалити дублікат `core_settings.py` (файл присутній одночасно у `functions/` та `core/`).


* Проаналізувати та об'єднати ідентичний код у файлах `safety_sandbox.py` та `core_safety_sandbox.py`.


* [ ] Відмітити виконання в TASK.md

4.2. **Усунення дублювання STT та підсистем навчання/звітності**

* Об'єднати або чітко розмежувати однакові STT-компоненти у файлах `logic_stt.py` та `core_stt_listener.py`.


* Позбутися дублювання в логіці самонавчання агента між `logic_task_learner.py` та `self_learning.py`.


* Синхронізувати та об'єднати генератори звітів у `logic_execution_report.py` та `logic_report_generator.py`.


* [ ] Відмітити виконання в TASK.md

---

### ЕТАП Б. Індексація проєкту для кодового агента

**Контекст:** Кодовий агент має бачити структуру проєкту і грамотно вносити точкові зміни, не чіпаючи решту коду.

**Виконані підетапи (перенесено в TASKS_Done.md):** Б1 (Repo Map), Б2 (Dependency Graph), Б3 (Навчання комбінувати інструменти) — ✅

#### Б4. Семантичний пошук (відкласти до реальної потреби)

**Реалізувати ТІЛЬКИ якщо виникне конкретна проблема:** агент не може знайти функцію бо не знає її назви але може описати що вона робить.

- [ ] Реалізувати `functions/vector_memory.py` на базі ChromaDB
  - Кожна функція/клас індексується як окремий чанк
- [ ] Додати інструмент `search_code(query)` — повертає 3-5 релевантних фрагментів за смисловим запитом

**Поки що:** для більшості задач достатньо `search_in_code` (grep) + Repo Map.

---

### COMPUTER USE АГЕНТ — МАРК як людина за комп'ютером

> Базовий план: див. `docs/PLAN_COMPUTER_USE.md` (1138 рядків, аудит коду 26.04.2026)

> Мета: Перетворити МАРК з "набору інструментів з планером" на агента, який користується ПК як людина і може тестувати GUI як QA-інженер.

**Поточний стан (станом на 30.04.2026):**

- ✅ AgentLoop повний (`functions/agent_loop.py`, ~1190 рядків) — observe→plan→act→check + LLM tool-calling
- ✅ ActionDecider з LLM tool-calling (через `logic_llm_tools.ask_llm_with_tools`)
- ✅ Tools schema (`functions/logic_agent_tools_schema.py`) — AGENT/VISION/UIA/BROWSER tools
- ✅ `Observation` посилене: screenshot, OCR, UI elements, UIA tree, vision description, active window
- ✅ `check()` посилене: act_result + ExpectRegistry (17 evaluator-ів) + screen hash fallback
- ✅ AgentLoop інтегрований з GUI (кнопка "🤖 Агент" → run_agent_loop)
- ✅ Базові інструменти (mouse_keyboard, screen_capture, ocr, ui_detector, window_manager, app_recognizer, visual_diff)
- ✅ Phase 11+ стек (TaskRunner, PermissionGate, Expectations, ExecutionReport, SessionBudget, PlanCritic)
- ✅ UIA dual-backend (`tools_ui_accessibility.py`) — uiautomation (основний) + pywinauto fallback, 10+ LLM інструментів (uia_list_elements, uia_click_element, uia_set_text тощо), інтеграція з AgentLoop.observe() для UIA-дерева
- ✅ Vision providers (`providers_vision.py`) — analyze_image для OpenAI/Claude/Gemini, detect_ui_elements/suggest_actions — MVP stubs
- ✅ Browser CDP + Playwright (`tools_browser_cdp.py`, `tools_playwright.py`)
- ✅ Repair loop базовий (`logic_repair_loop.py`)
- ✅ Checkpoint manager (`core_checkpoint.py`)
- ✅ LLM tool-calling низькорівневий (`logic_llm_tools.py`)
- 🟡 **Gap**: GUITester для тестування GUI як QA-інженер — відсутній (ЕТАП 2)
- 🟡 **Gap**: Vision-LM, Browser capabilities в decider — вимкнені за замовчуванням (треба ввімкнути в config). UIA вже інтегровано.

#### ЕТАП 2: GUI ТЕСТУВАЛЬНИК (ВИСОКА ЦІННІСТЬ для self-validation)

**Ціль:** МАРК може тестувати власні зміни в GUI як QA-інженер: відкрити програму, перевірити функції, зробити висновки.

**Робоча основа:**
- [ ] `test_duplication_direct.py` (~134 рядків) — працюючий скрипт для автоматизованого GUI тестування
- Використовує: `activate_window_by_title`, `keyboard_type`, `keyboard_press`
- Запускає GUI через subprocess, вставляє текст, чекає відповіді, читає логи
- Це базовий шаблон для розширення до повноцінного GUITester

- [ ] Створити `functions/logic_gui_tester.py` (~500 рядків) на основі `test_duplication_direct.py`
  - Пріоритет: P1
  - Деталі:
    - `class GUITester` що використовує `AgentLoop` під капотом
    - Метод `test_scenario(scenario: TestScenario) → TestReport`
    - Метод `test_function(app_name, function_name) → TestCaseResult` — швидкий тест однієї функції
    - Метод `test_changes(app_name, changes_description) → TestReport` — тестування ПІСЛЯ змін у коді
    - Інтеграція з `core_action_recorder.ActionRecorder` (скріншоти до/після вже є)
    - Інтеграція з `tools_visual_diff` (порівняння baseline/current)
    - dataclasses: `TestCase`, `TestScenario`, `TestCaseResult`, `TestReport`, `Expectation`
    - Built-in expectations: `TextVisible`, `TextNotVisible`, `WindowTitle`, `ElementExists`, `NoErrorDialog`, `VisualMatch`, `FileExists`

- [ ] Створити `functions/logic_gui_test_report.py` (~200 рядків)
  - Пріоритет: P1
  - Деталі:
    - `class TestReportGenerator` — markdown-звіт з вердиктом
    - Колонки: Тест, Статус (✅/❌), Час, Деталі
    - Розділ "❌ Невдалі тести" з очікуваним vs отриманим, скріншотами
    - Висновок: "Все ок" або "Не пройшло X з Y, рекомендація: доробити"
    - Збереження звіту в `runtime/test_reports/{date}_{scenario}.md`

- [ ] Створити каталог сценаріїв `scenarios/`
  - Пріоритет: P1
  - Деталі:
    - `scenarios/test_notepad_basic.json` — базові функції Notepad
    - `scenarios/test_marka_gui.json` — самотестування PyQt6 GUI МАРКА (відкрити, ввести команду, перевірити відповідь, відсутність дублювання)
    - `scenarios/test_browser_basic.json` — базова веб-автоматизація
    - JSON-формат: `name`, `app_name`, `setup_steps`, `test_cases[]{name, goal, expectations[]}`, `teardown_steps`

- [ ] Інтегрувати GUITester в GUI як вкладка "Тестування"
  - Пріоритет: P2
  - Файли: `core_gui_pyqt6/main_window.py`, новий `core_gui_pyqt6/test_panel_qt.py`
  - Деталі:
    - QListWidget зі списком сценаріїв
    - Кнопки: "Запустити", "Запустити всі", "Переглянути звіт"
    - Прогрес-бар виконання
    - Перегляд скріншотів до/після для кожного тесту

- [ ] Тести для `logic_gui_tester.py` (`tests/test_logic_gui_tester.py`, ~200 рядків)
  - Пріоритет: P1

**Оцінка:** ~700 нових рядків + ~50 змін + ~200 тестів. Складність: середня (використовує AgentLoop).

#### ЕТАП 4: VISION-LLM ІНТЕГРАЦІЯ (РОЗУМІННЯ ЕКРАНУ)

**Ціль:** Агент дивиться на скріншот через GPT-4V/Claude Vision/LLaVA і розуміє що бачить.

- [ ] Перевірити та доробити `providers_vision.py`
  - Пріоритет: P1
  - Деталі:
    - Перевірити що реалізовано: `OpenAIVisionProvider`, `AnthropicVisionProvider`, `OllamaVisionProvider`
    - Додати методи: `describe(image_path, prompt) → str`, `plan_action(image_path, goal) → Dict`, `find_element(image_path, description) → Dict[bbox]`
    - `get_vision_provider(assistant)` factory — з конфігу `VISION_PROVIDER` в SETTINGS_SCHEMA
    - Кешування: не аналізувати той самий скріншот повторно (хеш скрину → опис)

- [ ] Інтегрувати у `ActionDecider.decide()` (~50 рядків)
  - Пріоритет: P1
  - Деталі:
    - Якщо `enable_vision=True` і провайдер доступний — додавати vision_description в промпт

---

## 🔴 Пріоритет 1: Стабільність основних модулів (критичні для роботи)

- [x] **`get_endpoint_by_role` — відсутній експорт** (1 FAILED: `test_execute_not_implemented`)
  - Файли: `functions/config.py`, `functions/planning/ai_actors.py`
  - Фікс: додати функцію назад у config або оновити ai_actors.py

- [x] **`WindsurfWatcherConfig.max_tokens` — відсутній атрибут** (7 FAILED)
  - Файл: `functions/runtime/core_windsurf_watcher.py`
  - Фікс: додати поле `max_tokens` до dataclass `WindsurfWatcherConfig`

- [x] **ActionDecider fallback логіка** (5 FAILED: `test_decide_handles_llm_error`, `test_decide_handles_llm_exception`, `test_decider_noop_falls_through`, `test_empty_response`, `test_invalid_json`)
  - Файл: `functions/agent/plan.py` (рядки ~440-460)
  - Фікс: після вичерпання спроб JSON парсингу повертати `noop` замість `take_screenshot`

- [x] **AgentLoop — видалені методи** (6 FAILED: `test_consecutive_failures_increment`, `test_handle_ask_user_step_*`, `test_plan_with_ask_user_compiled_plan`)
  - Файл: `functions/planning/agent_loop.py` (рядки 300-450)
  - Фікс: повернути методи `_execute_single_step` та `_handle_ask_user_step` або оновити тести

- [x] **Імпорт `functions.logic_plan_critic`** (2 FAILED: `test_calls_create_plan_with_concerns_block`, `test_serialized_plan_contains_goal_and_validation_in_legacy_meta`)
  - Файл: `tests/test_core_planner_critic.py`
  - Фікс: виправити імпорт на `functions.planning.logic_plan_critic`

## 🟠 Пріоритет 2: UndoManager (10 FAILED)

- [ ] **Повний рефакторинг UndoManager**
  - Файл: `functions/runtime/core_undo_manager.py`
  - Проблеми:
    - стек 4 замість 3 (`test_add_multiple_to_undo_stack`)
    - `undo_last` повертає 0 замість 1
    - `undo_all` повертає 1 замість 2
    - `save_snapshot` повертає False
    - `list_snapshots` повертає 3 замість 2
    - `restore_snapshot` повертає False
    - `undo_to_snapshot` повертає False
  - Фікс: переписати логіку стеків/снапшотів або синхронізувати тести

## 🟡 Пріоритет 3: API-сумісність

- [ ] **ScreenCapture — змінені імена методів** (5 FAILED)
  - Файл: `functions/tools/tools_screen_capture.py`
  - Фікс: додати методи-обгортки `capture_screen` → `capture_region`, `save_screenshot` → `take_screenshot`

- [ ] **UIElement — конструктор** (2 FAILED: `test_ui_element_creation`, `test_ui_element_defaults`)
  - Файл: `functions/tools/tools_ui_accessibility.py`
  - Фікс: `bounding_rectangle` → `bounding_rect`, `control_type` мати дефолт None

- [ ] **UIAWrapper — нормалізація return** (6 FAILED)
  - Файл: `functions/tools/tools_ui_accessibility.py`
  - Фікс: методи мають повертати `{"error": "...", "success": False}` замість None

- [ ] **LLMTools UIA — сигнатури функцій** (8 FAILED)
  - Файли: `functions/tools/tools_ui_accessibility.py`, `tests/test_tools_ui_accessibility.py`
  - Фікс: синхронізувати сигнатури `uia_list_elements`, `uia_set_text`, `uia_wait_for_element`, `uia_list_buttons`, `uia_list_inputs`, `uia_get_focused_element`

## 🔵 Пріоритет 4: Інфраструктура тестів

- [ ] **PermissionGate — шлях поза project root** (3 FAILED)
  - Файли: `functions/runtime/logic_permission_gate.py`, `tests/test_logic_permission_gate.py`
  - Фікс: налаштувати CWD тестів або виправити логіку визначення project root

- [x] **`test_second_response_extracts_tail`** — зайвий пробіл
  - Файл: `tests/test_core_windsurf_watcher.py`
  - Фікс: strip() при порівнянні

- [ ] **`test_missing_kind_raises`** — ValueError не кидається
  - Файл: `tests/test_logic_task_runner.py`
  - Фікс: виправити парсинг `Plan.from_dict()` або тест

- [ ] **`test_plan_from_dict_parses_expect_and_precheck`** — dict замість об'єкта
  - Файл: `tests/test_logic_task_runner_expect.py`
  - Фікс: нормалізувати precheck

- [ ] **TestCodePipelineEndToEnd** — scaffold denied (permission gate)
  - Файл: `tests/test_pipeline_code.py`
  - Фікс: те саме, що permission gate

- [ ] **TestUIDetector** — find_input_field/find_checkbox
  - Файл: `tests/test_tools_ui_detector.py`
  - Фікс: виправити обробку помилок

- [ ] **TestVoiceTrayIcon** — `_get_tooltip` відсутній, `_should_run`
  - Файл: `tests/test_voice_tray_icon.py`, `functions/gui/voice_tray_icon.py`
  - Фікс: додати `_get_tooltip` метод, нормалізувати `_should_run`

## ⚪ Пріоритет 5: Linux-специфічні (очікувані на CI, маркувати skip)

- [ ] **DPI scaling / ScreenHelper** (8 FAILED)
  - Файл: `tests/test_screen_helper.py`, `tests/test_dpi_multimonitor.py`
  - Фікс: `ctypes.windll` не існує на Linux → `@pytest.mark.skipif(sys.platform != "win32")`

- [ ] **MouseKeyboardController** (17 ERROR + 6 FAILED)
  - Файл: `tests/test_tools_mouse_keyboard.py`, `tests/test_drag_drop.py`
  - Фікс: `@pytest.mark.skipif(sys.platform != "win32")`

- [ ] **GlobalVoiceInput** (12 FAILED)
  - Файл: `tests/test_global_voice_input.py`
  - Фікс: `@pytest.mark.skipif(...)` або оновити імпорти
