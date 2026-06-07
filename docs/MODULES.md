# 📦 Модулі

> Оновлено: 07.06.2026 — синхронізовано з актуальним кодом (після Фаз 1-7 рефакторингу).

## 📚 Зміст
- [Структура пакетів](#структура-пакетів)
- [functions/ — кореневі модулі](#functions---кореневі-модулі)
- [audio/ — Audio Modules](#audio---audio-modules)
- [llm/ — LLM Modules](#llm---llm-modules)
- [planning/ — Planning Modules](#planning---planning-modules)
- [agent/ — AgentLoop Phases](#agent---agentloop-phases)
- [runtime/ — Runtime Modules](#runtime---runtime-modules)
- [gui/ — GUI Modules](#gui---gui-modules)
- [tools/ — Tool Modules](#tools---tool-modules)
- [skills/ — Skills Modules](#skills---skills-modules)
- [core_gui_pyqt6/ — PyQt6 GUI](#core_gui_pyqt6---pyqt6-gui)
- [Інші модулі functions/](#інші-модулі-functions)

---

## Структура пакетів

Після Фаз 1-7 рефакторингу (див. `TASKS_Done.md`) модулі згруповані в підпакети за відповідальністю:

```
functions/
├── __init__.py          # Експорт кореневих модулів
├── config.py            # Глобальна конфігурація
├── global_voice_input.py
├── logic_execution_report.py
├── project_indexer.py   # Repo map + dependency graph
├── tools_project_indexer.py
├── audio/               # STT/TTS, фільтри, continuous listener
├── llm/                 # LLM-шар: providers, router, streaming
├── planning/            # Planer, executor, AgentLoop coordination
├── agent/               # Фази AgentLoop (observe/plan/act/check)
├── runtime/             # Runtime оркестрація, реєстри, safety
├── gui/                 # GUI-логіка
├── tools/               # Desktop/browser/media tools
└── skills/              # Високорівневі навички (browser_skills)
```

> **Історична довідка:** до Фази 7 всі модулі лежали у `functions/` (плоска структура, 100+ файлів). Було проведено розбиття `agent_loop.py` (2008 → 479 рядків, легкий state-machine) та винесення `main.py` (1242 → 874 рядки) у підпакети.

---

## functions/ — кореневі модулі

### `config.py`
**Призначення**: Глобальна конфігурація проєкту (налаштування, API keys, шляхи).
**Методи**:
- `get_setting(key, default)` / `set_setting(key, value)` — читання/запис налаштувань
**Залежності**: `json`, `os`

### `global_voice_input.py`
**Призначення**: Глобальний голосовий ввід через Windows hook (Ctrl+Shift+V).
**Методи**:
- `start()` / `stop()` — запуск/зупинка глобального слухача
- `_insert_segment(text)` / `_send_input_unicode(text)` — критичні методи вставки тексту
**Залежності**: `keyboard` (глобальний hook), `pyperclip`

### `logic_execution_report.py`
**Призначення**: Звіт виконання задач (StepReport + ExecutionReport dataclasses).
**Методи**:
- `StepReport.to_dict()` — серіалізація кроку
- `ExecutionReport` — збір статистики виконання
**Залежності**: `dataclasses`, `datetime`

### `project_indexer.py` (Repo Map + Dependency Graph)
**Призначення**: Індекс проєкту — карта файлів, залежностей, пошук. Використовується coding-агентом.
**Методи**:
- `get_repo_map() -> str` — компактна карта проєкту
- `get_file_dependents(filepath) -> list[str]` — хто залежить від файлу
- `update_repo_map(filepath)` — оновити після зміни
- `search_in_code(query)` — пошук по коду
**Залежності**: `pathlib`, `ast`

### `tools_project_indexer.py`
**Призначення**: Tool-обгортки навколо `project_indexer.py` для виклику через FunctionRegistry.
**Методи** (реєструються автоматично): `get_repo_map()`, `get_file_dependents()`, `update_repo_map()`, `search_in_code()`

---

## audio/ — Audio Modules

Модулі для обробки аудіо (STT/TTS, фільтрація). Розташування: `functions/audio/`.

### `core_stt_listener.py`
**Призначення**: STT слухач для прийому голосового вводу.
**Залежності**: `config`, `logic_stt`

### `logic_audio.py`
**Призначення**: Аудіо логіка обробки.

### `logic_audio_filtering.py`
**Призначення**: Фільтрація аудіо сигналів.

### `logic_continuous_listener.py`
**Призначення**: Неперервний слухач для голосових команд.

### `logic_stt.py`
**Призначення**: Speech-to-Text конвертація (Whisper, w2v-bert-uk).

### `logic_tts.py`
**Призначення**: Text-to-Speech озвучування (edge-tts).

### `initializer.py` (НОВИЙ)
**Призначення**: `AudioInitializer` — єдина точка ініціалізації STT/TTS/фільтрів (винесено з `main.py` у Фазі 1).
**Методи**:
- `init_all(with_listener: bool)` — ініціалізувати всю аудіо-підсистему
**Залежності**: `logic_stt`, `logic_tts`, `logic_audio_filtering`

---

## llm/ — LLM Modules

LLM-шар має дворівневу архітектуру:

1. **Низький рівень** (J1): `logic_ai_adapter.py` + `logic_provider_registry.py` + конкретні провайдери.
2. **Оркестрація** (J2-J4): `router.py` + `provider_chain.py` + `endpoint_client.py`.

Розташування: `functions/llm/`.

### `__init__.py`
**Призначення**: Експорт LLM модулів. Забезпечує зворотну сумісність через `ask_llm` з `helpers.py`.
```python
from functions.llm.helpers import ask_llm
from functions.llm.response_parser import process_llm_response
from functions.llm.endpoint_client import get_primary_endpoint, call_endpoint
from functions.llm.streaming_buffer import StreamingBuffer
```

### `helpers.py` (~90 рядків)
**Призначення**: Допоміжні функції для LLM (clean_llm_tokens, форматування, ask_llm).
**Методи**:
- `ask_llm(prompt, system_prompt="", stream_callback=None) -> str` — основна точка входу для LLM
- `clean_llm_tokens(text)` — очищення сирих LLM токенів

### `logic_ai_adapter.py` (~359 рядків)
**Призначення**: `AIProvider` — абстракція виклику зовнішніх ШІ (API + браузер). Скелет + `EchoProvider`/`ScriptedProvider` для тестів.
**Data-класи**: `ChatMessage`, `ChatRequest`, `ChatResponse`, `ProviderCapabilities`, `UsageInfo`.
**Базовий клас**: `AIProvider` (ABC з методами `available()`, `chat()`, `name`).

### `logic_provider_registry.py` (~254 рядки)
**Призначення**: `ProviderRegistry` — реєстр ШІ-провайдерів + вибір за capability/вартістю.
**Методи**:
- `register()` / `unregister()` / `get()` / `list()`
- `select(criteria)` — пошук найкращого за вимогами
- `select_many(criteria)` — fallback-ланцюжок
- `chat(request, criteria)` — hi-level shortcut з автоматичним fallback

### `router.py` (~135 рядків)
**Призначення**: `RequestRouter` — класифікація запитів за типом задачі (Рівень 1 оркестрації).
**Класи**: `TaskType` (enum: CODE, DEBUG, GUI, WEB, GENERAL, QUICK), `RoutingDecision`.
**Методи**:
- `RequestRouter.classify(text) -> RoutingDecision` — keyword-based класифікація (швидко, без LLM)

### `provider_chain.py` (~162 рядки)
**Призначення**: `ProviderChain` — послідовний fallback ланцюг провайдерів (Рівень 2).
**Методи**:
- `ProviderChain.execute(request, decision, timeout=180.0)` — послідовно primary → fallback з health-check
- Quota tracking (consecutive errors limiter)

### `endpoint_client.py` (~500 рядків)
**Призначення**: HTTP-клієнт для endpointів LLM (LM Studio, OpenAI, Groq).
**Методи**:
- `get_primary_endpoint()` / `get_secondary_endpoint()` — вибір endpoint
- `call_endpoint(endpoint, messages, stream=False)` — виклик
- `get_model_context_limit(model_name) -> int` — ліміт контексту моделі

### `logic_llm_tools.py` (~455 рядків)
**Призначення**: OpenAI-compatible tool-calling / JSON mode для LLM.
**Методи**:
- `ask_llm_with_tools(prompt, tools) -> ToolCallResult` — запит з tool-calling
- `ask_llm_json(prompt, response_model) -> dict` — JSON-режим
**Залежності**: `requests`, `openai`

### `response_parser.py` (~638 рядків)
**Призначення**: Парсер відповідей LLM (JSON, tool calls, очищення артефактів).
**Методи**:
- `process_llm_response(text) -> dict` — головна точка входу
- `sanitize_json_string(text)` — екранування control chars у JSON strings
**Кешовані regex**: `_JSON_CODE_BLOCK_PATTERN`, `_QUOTE_PATTERN`, тощо.

### `streaming_buffer.py` (~147 рядків)
**Призначення**: `StreamingBuffer` — підрахунок токенів у реальному часі під час стрімінгу.
**Атрибути**: `total_chars`, `estimated_tokens` (= chars // 4).
**Методи**:
- `add_chunk(chunk) -> int` — додати чанк, оновити оцінку, викликати callback
- `finish(real_usage)` — замінити оцінку реальним `usage` після стрімінгу
- `update_context_limits(context_limit, model)` — оновити при старті стрімінгу
**Callbacks**: `on_status`, `on_context_update(used, limit, model)`.

### `groq_client.py` (~148 рядків)
**Призначення**: SDK-клієнт для Groq (швидкий inference).
**Методи**: `stream_groq_sdk(...)` з `usage_callback` для real-time usage.

### `providers_openai_compatible.py` (~391 рядок)
**Призначення**: `OpenAICompatibleProvider` — OpenAI-сумісні endpointи (LM Studio, vLLM, Groq через OpenAI API).
**Реалізує**: `AIProvider`.

### `providers_anthropic.py` (~115 рядків)
**Призначення**: `AnthropicProvider` — Claude API.
**Реалізує**: `AIProvider`. Заповнює `UsageInfo`.

### `providers_google.py` (~112 рядків)
**Призначення**: `GoogleProvider` — Gemini API.
**Реалізує**: `AIProvider`. Заповнює `UsageInfo`.

### `providers_browser.py` (~127 рядків)
**Призначення**: `BrowserProvider` — fallback через браузерну автоматизацію (для сайтів без API).
**Реалізує**: `AIProvider`.

### `providers_vision.py` (~354 рядки)
**Призначення**: Vision-LM — аналіз зображень через OpenAI/Claude/Gemini.
**Методи**:
- `analyze_image(query) -> VisionResponse` — аналіз зображення
- `detect_ui_elements(image_path) -> List[UIElement]` — 🟡 Stub
- `suggest_actions(image_path, goal) -> List[SuggestedAction]` — 🟡 Stub
- `get_vision_provider(assistant)` — singleton instance
**Залежності**: `openai`, `anthropic`, `google-generativeai`

---

## planning/ — Planning Modules

Модулі планування та виконання задач. Розташування: `functions/planning/`.

### `agent_loop.py` (~479 рядків, **оновлено у Фазі 7.2**)
**Призначення**: `AgentLoop` — легкий state-machine диспетчер фаз **observe → plan → act → check** (замість старого God Object 2008 рядків).
**Делегує логіку** в `functions/agent/{observe,plan,act,check}.py`.
**Класи**:
- `AgentLoop` — головний клас із `run(task) -> dict`
- `AgentLoopConfig` — параметри (max_steps=200, max_duration_seconds=3600, enable_* прапорці)
- `AgentState` — стан агента між ітераціями
**Публічні методи**: `run()`, `request_stop()`, `set_compiled_plan(cp)`.

### `agent_coordinator.py` (НОВИЙ, Фаза 1.3)
**Призначення**: `AgentCoordinator` — координація запуску AgentLoop, маршрутизація задач.
**Методи**:
- `run(task) -> RunResult` — запуск з обробкою провайдерів
- `request_stop()` — зовнішня зупинка

### `core_planner.py` (~537 рядків)
**Призначення**: `Planner` — планування задач через LLM з retry-механізмом.
**Методи**:
- `create_plan(task) -> list[dict]` — створення плану (legacy, тільки перший крок використовується в `AgentLoop.plan()`)
- `refine_plan(plan, feedback) -> CompiledPlan` — уточнення плану
**Залежності**: `llm/`, `planner_prompt_builder`, `planner_validator`

### `core_planner_critic.py`
**Призначення**: `PlanCritic` — LLM-оцінка готовності плану перед виконанням.

### `core_planner_runner.py`
**Призначення**: Міст legacy → TaskRunner (для поступової міграції).

### `core_task_intake.py`
**Призначення**: Прийом та валідація вхідних задач → `TaskSpec`.

### `task_spec.py`
**Призначення**: `TaskSpec` — типізоване представлення задачі (Phase 13).

### `pipeline_code.py`
**Призначення**: Code generation pipeline — автоматична генерація коду через AI actors (Phase 13).
**Метод**: `compile(spec) -> CompiledPlan` з опційним `use_ai_actors=True`.

### `core_plan_compiler.py`
**Призначення**: `CompiledPlan`, реєстрація `Pipeline`-ів за доменами (`DOMAIN_*`).

### `plan_models.py`
**Призначення**: Pydantic/dataclass моделі для `Plan`, `Task`, `Step`.

### `plan_executor.py`
**Призначення**: `PlanExecutor` — виконавець планів через TaskRunner.

### `planner_prompt_builder.py` (НОВИЙ, Фаза 7.4)
**Призначення**: Побудова промптів для Planner (винесено з `core_planner.py`).

### `planner_validator.py` (НОВИЙ, Фаза 7.4)
**Призначення**: Валідація результатів `create_plan()` (JSON schema, типи).

### `planner_repair.py` (НОВИЙ, Фаза 7.4)
**Призначення**: Механізм repair для Planner (3 спроби).

### `logic_agent_tools_schema.py`
**Призначення**: OpenAI tools schema для LLM tool-calling (AGENT/VISION/UIA/BROWSER tools).

### `logic_context_analyzer.py` (~854 рядки)
**Призначення**: `ContextAnalyzer` — аналіз контексту виконання. Детекція блокаторів, підказки наступних дій.

### `logic_task_runner.py` (~1013 рядків)
**Призначення**: `TaskRunner` з handler-реєстром. 10 built-in handlers. Повна фаза виконання з PermissionGate, Expectations, SessionBudget.
**Методи**:
- `run(plan) -> ExecutionReport` — головний цикл
- `register_handler(kind, fn)` — реєстрація handler-а

### `logic_expectations.py`
**Призначення**: `ExpectRegistry` — 17 evaluator-ів для перевірки результатів кроків (TextVisible, FileExists, NoErrorDialog, тощо).

### `logic_repair_loop.py`
**Призначення**: `StepRepairer` — LLM-based repair після невдалого кроку (Phase 12.2).

### `logic_plan_critic.py`
**Призначення**: `PlanCritic` — LLM meta-оцінка плану (legacy-ім'я, див. також `core_planner_critic.py`).

### `logic_execution_report.py`
**Призначення**: `StepReport` + `ExecutionReport` dataclasses (Phase 11).

### `logic_task_learner.py`
**Призначення**: `TaskLearner` — самонавчання з аналізом помилок.

### `logic_orchestrator.py` (НОВИЙ)
**Призначення**: `Orchestrator` — верхньорівнева оркестрація (Phase 12.4).

### `ai_actors.py`
**Призначення**: `AIActor` — обгортки для зовнішніх AI (Codex, Windsurf, Cursor) у `pipeline_code.py`.

---

## agent/ — AgentLoop Phases

Винесено з `agent_loop.py` у Фазі 7.2. Кожен модуль — одна фаза циклу агента.

Розташування: `functions/agent/`.

### `observe.py` (~410 рядків)
**Призначення**: Фаза спостереження — збір "картини світу" з екрану.
**Класи**: `Observation` (dataclass), `ObserveConfig` (dataclass).
**Методи**:
- `observe(config, assistant, task) -> Observation` — головна точка входу
- Збирає: screenshot, OCR, UI elements, UIA tree, vision description, active window, app_state.

### `plan.py` (~723 рядки)
**Призначення**: Фаза планування — `ActionDecider` через LLM tool-calling.
**Класи**: `ActionDecider`.
**Методи**:
- `decide(goal, observation, history, ...) -> AgentAction` — основний виклик
- `replan(...)` — переосмислення після серії невдач
- `resolve_alias(name)` — маппінг `ask_user` → реальна назва
- `_parse_json_from_content()` — парсинг JSON з відповіді LLM (з fallback)
- `_try_with_tools()` — fallback на tool-calling
- `_json_failure_fallback()` — фінальний fallback на `done`/`take_screenshot`

### `act.py` (~477 рядків)
**Призначення**: Фаза виконання — `ActionGuard` для безпекового прошарку.
**Класи**: `ActionGuard`, `ActionGuardConfig`.
**Методи**:
- `run_guards(action, args, actions_history, gui_cb)` — перевірка дозволів
- `update_after_action(action, args, result)` — оновити стан guard-а

### `check.py` (~350 рядків)
**Призначення**: Фаза перевірки результату.
**Класи**: `CheckState`, `CheckResult`.
**Методи**:
- `check(action, obs, state, act_result, expectations) -> CheckResult` — головна точка входу
- `save_checkpoint()` / `load_checkpoint()` / `cleanup_checkpoint()` — управління чекпоїнтами

---

## runtime/ — Runtime Modules

Модулі для оркестрації та виконання задач. Розташування: `functions/runtime/`.

### `__init__.py`
**Призначення**: Експорт runtime модулів.

### `conditions_windows.py`
**Призначення**: Умови виконання, специфічні для Windows.

### `conditions_web.py`
**Призначення**: Умови для веб-середовища (мультиплатформний fallback).

### `core_initializer_checks.py` (НОВИЙ, Фаза 1.1)
**Призначення**: Перевірки ініціалізації (LM Studio доступність, файли, шляхи) — винесено з `main.py`.

### `core_windsurf_watcher.py` (~411 рядків)
**Призначення**: `WindsurfWatcher` — спостереження за Windsurf IDE.
**Класи**: `WindsurfWatcherConfig` (dataclass), `WindsurfWatcherRunner`.
**Методи**:
- `start_windsurf_watch()` / `stop_windsurf_watch()` — керування
- `get_open_files() -> list[str]` — отримання відкритих файлів
- GUI інтегровано в `tab_settings.py` (кнопка toggle) та `AssistantCore`.

### `logic_core.py` (~511 рядків)
**Призначення**: `FunctionRegistry` — реєстр функцій для динамічного виклику через LLM.
**Методи**:
- `register(name, func, description, risk_level)` — реєстрація функції
- `call(name, **kwargs) -> dict` — виклик функції
- `get_tool_risk(action) -> RiskLevel` — оцінка ризику
- `load_all_modules()` — автозавантаження модулів з `functions/{core,aaa,tools,skills}/` (з `rglob`)
- `get_system_prompt()` — генерація system prompt для coding/voice режимів
- `get_voice_system_prompt()` / `get_coding_system_prompt()` — окремі промпти

### `logic_permission_gate.py` (~397 рядків)
**Призначення**: 4-рівнева policy stack для перевірки прав на дію.
**Методи**:
- `ask(action, context) -> Decision` — запит на дозвіл
- `grant(user, action)` — надання дозволу

### `logic_watcher.py` (~457 рядків)
**Призначення**: `Watcher` engine з потоками для моніторингу умов.
**Методи**:
- `watch(condition, callback) -> WatchHandle` — початок спостереження
- `stop_watch(handle)` — припинення

### `core_settings.py` (НОВИЙ)
**Призначення**: Єдине джерело налаштувань (раніше дублювався у двох місцях).

### `core_app_profile.py` (~280 рядків)
**Призначення**: `AppProfile` — профілювання додатку (learn_from_interaction — 🟡 заглушка).

### `core_checkpoint.py`
**Призначення**: Чекпоінти для відновлення сесій (Phase 12.4).

### `core_dispatcher.py`
**Призначення**: Диспетчер команд.

### `core_executor.py`
**Призначення**: Виконавець планів.

### `core_loop_detector.py`
**Призначення**: `LoopDetector` — захист від зациклення агента.

### `core_macro.py` (~293 рядки)
**Призначення**: `MacroRecorder` + `MacroPlayer` (поки не підключені до GUI).

### `core_memory.py`
**Призначення**: Пам'ять сесій.

### `core_safety_sandbox.py`
**Призначення**: Сендбокс для безпечного виконання коду (AST-валідація, обмеження).

### `core_session_budget.py` (~215 рядків)
**Призначення**: `SessionBudget` — ліміти на час/кроки/токени.

### `core_tool_runtime.py`
**Призначення**: Runtime для інструментів (TOOL_POLICIES).

### `core_undo_manager.py` (~641 рядок)
**Призначення**: Snapshots + undo для файлових операцій.

### `core_action_recorder.py` (~521 рядок)
**Призначення**: `ActionRecorder` — скріншоти до/після дії.

### `core_cache.py`
**Призначення**: Кеш тільки для idempotent операцій.

### `self_learning.py`
**Призначення**: Модуль самонавчання — JSONL логи + skills база.

### `sync_settings_copy.py`
**Призначина**: Синхронізація копій налаштувань.

### `windsurf_watcher_executor.py`
**Призначення**: Виконавець watcher-а для Windsurf.

---

## gui/ — GUI Modules

GUI-логіка (викликається з PyQt6 main_window.py). Розташування: `functions/gui/`.

### `core_gui_guardian.py` (~532 рядки)
**Призначення**: `GUIGuardian` — оцінка ризиків GUI-дій.
**Методи**:
- `assess_risk(action, context) -> RiskLevel`
- `confirm_dangerous(action) -> bool` — з 30-секундним зворотним відліком

### `logic_commands.py` (розбито на Фазі 7.3)
**Призначення**: `VoiceAssistant` — обробка текстових команд.
**Методи**:
- `process_command(text) -> str`
- `classify_task(text) -> TaskType` — CHAT / AGENT / GUI_ACTION
- `needs_clarification(text) -> bool`

### `commands_planner.py` (НОВИЙ, Фаза 7.3)
**Призначення**: Маршрутизація команд (CHAT / AGENT / GUI_ACTION).

### `commands_streaming.py` (НОВИЙ, Фаза 7.3)
**Призначення**: Логіка стрімінгу.

### `commands_audio.py` (НОВИЙ, Фаза 7.3)
**Призначення**: Аудіо-команди.

### `voice_tray_icon.py`
**Призначення**: Іконка в треї для voice input.

---

## tools/ — Tool Modules

Desktop/browser/media інструменти для GUI-автоматизації. Розташування: `functions/tools/`.

### `tools_mouse_keyboard.py` (~436 рядків)
**Призначення**: Mouse/keyboard automation через pyautogui.
**Інструменти**: `mouse_click`, `mouse_move`, `mouse_scroll`, `mouse_drag`, `keyboard_type`, `keyboard_press`, `keyboard_hotkey`, `clipboard`.

### `tools_window_manager.py` (~605 рядків)
**Призначення**: Window manager через win32gui/pygetwindow.
**Інструменти**: `list_windows`, `find_window_by_title`, `activate_window`, `move/resize/close`.

### `tools_screen_capture.py` (~608 рядків)
**Призначення**: Screen capture через mss + PIL + OpenCV.
**Інструменти**: `take_screenshot`, `capture_region`, `find_image_on_screen`, `wait_for_image`.

### `tools_ocr.py` (~595 рядків)
**Призначення**: OCR — розпізнавання тексту (pytesseract + easyocr fallback).
**Інструменти**: `ocr_screen`, `find_text_on_screen`, `click_text`.

### `tools_ui_detector.py` (~653 рядки)
**Призначення**: UI detection — пошук кнопок, полів, чекбоксів через OpenCV + OCR.
**Інструменти**: `find_button_by_text`, `find_input_field`, `find_checkbox`, `find_input_near_label`.

### `tools_app_recognizer.py` (~573 рядки)
**Призначення**: App recognizer — визначення активного додатку, діалогів.
**Інструменти**: `detect_active_application`, `detect_file_dialog`, `detect_error_dialog`.

### `tools_visual_diff.py` (~504 рядки)
**Призначення**: Visual diff — порівняння скріншотів (baseline).
**Інструменти**: `capture_baseline`, `compare_with_baseline`, `highlight_changes`.

### `tools_ui_accessibility.py` (~774 рядки)
**Призначення**: Windows UIA API (uiautomation + pywinauto dual-backend).
**Інструменти**: 10+ LLM інструментів (`uia_list_elements`, `uia_find_button`, `uia_click_element`, `uia_set_text`, тощо), інтеграція з `AgentLoop.observe()` для UIA-дерева.

### `tools_browser_cdp.py` (~1071 рядок)
**Призначення**: Browser CDP automation через Playwright.
**Інструменти**: 12 інструментів для браузерної автоматизації.

### `tools_playwright.py`
**Призначення**: Playwright integration — додаткові утиліти.

### `tools_windsurf.py` (НОВИЙ, Фаза 1.1)
**Призначення**: `SnapshotFn`, `WindowFinder`, `WindsurfState`, `WindsurfWindow`, `diff_snapshots` — створено для фікса `pytest` collection.

### `aaa_file_operations.py`
**Призначення**: Legacy — файлові операції (create, edit, delete, rename). `list_directory(directory, path=None)` приймає обидва параметри.

### `aaa_execute_python.py`
**Призначення**: Виконання Python коду в сендбоксі (auto-wrap виразів у `print()`).

### `aaa_open_interpreter.py`
**Призначення**: Open Interpreter fallback для self-healing виконання коду.
**Методи**:
- `is_available()` — перевірка доступності
- `get_executor(url)` — singleton executor
- `oi_execute_with_healing(code, description)` — виконання з автовстановленням модулів

---

## skills/ — Skills Modules

**НОВИЙ пакет** (Фаза 1.3). Високорівневі навички над базовими інструментами.

Розташування: `functions/skills/`.

### `base.py` (~97 рядків)
**Призначення**: Базові абстракції.
**Класи**: `BaseSkill`, `SkillResult`, `SkillError`.

### `registry.py` (~87 рядків)
**Призначення**: `SkillRegistry` — реєстрація/пошук/список skills.
**Методи**:
- `register(skill)` — реєстрація
- `find(name) -> BaseSkill` — пошук
- `list() -> list[BaseSkill]`

### `browser_skills.py` (~398 рядків)
**Призначення**: Конкретні навички для браузера.
**Класи**: `OpenBrowser`, `SearchGoogle`, `FillForm` — з fallback ланцюжком: `playwright` → `CDP` → `subprocess`.

---

## core_gui_pyqt6/ — PyQt6 GUI

**ПЕРЕРОБЛЕНО на вкладкову структуру** (див. `TASKS_Done.md` "ПЕРЕРОБКА GUI НА ВКЛАДКОВУ СТРУКТУРУ"). Замість міксинів — окремі класи вкладок.

Розташування: `core_gui_pyqt6/`.

### `__init__.py`
**Призначення**: Експорт `MainWindowPyQt6` з `main_window.py`.

### `constants.py`
**Призначення**: Константи (версія, кольори ролей чату, кольори рівнів логів, розміри).

### `base_tab.py`
**Призначення**: `BaseTab(QWidget)` — базовий клас для всіх вкладок з абстрактними `setup_ui()` / `refresh()` / `get_title()`.

### `main_window.py`
**Призначення**: `MainWindowPyQt6` — головне вікно з `QTabWidget`. Делегує виклики до вкладок.
**Особливості**:
- Динамічне збільшення поля вводу (`_update_input_height`) — 60–160px
- Збереження/відновлення геометрії вікна
- Потокобезпечна черга повідомлень через Qt signal
- Статус-бар контексту (`QProgressBar` ~6px) з кольорами 0-60%/60-80%/80-95%/95+%
- Зворотна сумісність: всі старі методи (`add_message()`, `start_stream_message()`, тощо) делеговані

### `tab_chat.py`
**Призначення**: `ChatTab(BaseTab)` — вкладка чату. Сигнал `command_submitted = pyqtSignal(str)`.

### `tab_plan.py`
**Призначення**: `PlanTab(BaseTab)` — вкладка плану. Методи: `show_plan_panel()`, `update_plan_step()`, `finish_plan_panel()`.

### `tab_logs.py`
**Призначення**: `LogsTab(BaseTab)` — вкладка логів з `QTableWidget` (Час, Рівень, Модуль, Повідомлення), фільтром по рівню + пошуком. Читає з `runtime/logs/`. Rolling window: макс. 50 рядків.

### `tab_stats.py`
**Призначення**: `StatsTab(BaseTab)` — вкладка статистики (запити, токени, середній час) + `QProgressBar` для контексту. Метод `update_stats(stats: dict)`.

### `tab_tools.py`
**Призначення**: `ToolsTab(BaseTab)` — список інструментів з `FunctionRegistry` (Назва, Опис, Ризик, Статус). Кнопка "Виконати" — тільки `QMessageBox` ("Введіть команду в чаті").

### `tab_settings.py`
**Призначення**: `SettingsTab(BaseTab)` — налаштування з `QSplitter` (ліва панель категорій + права з контентом). Lazy build, `QSettings` для збереження.

### `confirmation_qt.py`
**Призначення**: `ConfirmationDialog` + `ConfirmationQtMixin` — діалог підтвердження небезпечних дій.

### `llm_endpoints_editor_qt.py`
**Призначення**: `LLMEndpointsEditor` — редактор LLM ендпоінтів.
**Методи**:
- `get() -> list[dict]` — отримання ендпоінтів
- `set(endpoints)` — встановлення

### `chat_panel_qt.py`, `plan_panel_qt.py`, `settings_tab_qt.py` (legacy міксини)
**Призначення**: Застарілі міксини, що використовувалися до переробки GUI. Логіка перенесена в окремі класи вкладок (`tab_*.py`). Видаляти не можна без перевірки тестів.

---

## Інші модулі functions/

Модулі, що знаходяться безпосередньо в `functions/` (не в підпакетах):

- `__init__.py` — експорт
- `config.py` — глобальна конфігурація
- `global_voice_input.py` — глобальний голосовий ввід
- `logic_execution_report.py` — звіт виконання
- `project_indexer.py` — repo map + dependency graph (ЕТАП Б)
- `tools_project_indexer.py` — tool-обгортки для project_indexer

---

## 📝 Примітка

Цей документ відображає актуальну структуру проєкту станом на **07.06.2026**.

**Ключові зміни від попередньої версії (21.05.2026):**

1. **AgentLoop** (`functions/planning/agent_loop.py`) — рефакторинг у Фазі 7.2: 2008 → 479 рядків. Логіка винесена в `functions/agent/{observe,plan,act,check}.py`.
2. **LLM-шар** (`functions/llm/`) — додано 10+ нових модулів: `router.py`, `provider_chain.py`, `endpoint_client.py`, `response_parser.py`, `streaming_buffer.py`, `logic_ai_adapter.py`, `logic_provider_registry.py`, `groq_client.py`, `providers_anthropic.py`, `providers_google.py`, `providers_browser.py`, `providers_openai_compatible.py`.
3. **GUI** (`core_gui_pyqt6/`) — переробка на вкладкову структуру у Фазі "ПЕРЕРОБКА GUI". 6 вкладок: Чат, План, Логи, Статистика, Інструменти, Налаштування.
4. **Skills** (`functions/skills/`) — новий пакет з високорівневими навичками (browser_skills, registry).
5. **Planning** (`functions/planning/`) — додано `agent_coordinator.py`, `plan_executor.py`, `plan_models.py`, `planner_prompt_builder.py`, `planner_validator.py`, `planner_repair.py`, `logic_orchestrator.py`, `logic_task_learner.py`.
6. **Audio** (`functions/audio/`) — додано `initializer.py` (`AudioInitializer`).
7. **Runtime** (`functions/runtime/`) — додано `core_settings.py`, `core_initializer_checks.py`, `conditions_web.py`, `sync_settings_copy.py`, `windsurf_watcher_executor.py`.
8. **Tools** (`functions/tools/`) — додано `tools_windsurf.py` (створено для фікса pytest collection).

Для автогенерації документації з docstring:
```bash
pdoc --html --output-dir docs functions
```
або
```bash
sphinx-apidoc -o docs/ functions/
```
