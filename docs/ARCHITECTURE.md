# Архітектура МАРК: поточний стан і напрямок
> Оновлено: 07.06.2026

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash
# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

---

## Документи проєкту

- [README.md](../README.md) — запуск і загальний огляд.
- [TASKS.md](../TASKS.md) — поточні задачі та їх статус.
- [TASKS_Done.md](../TASKS_Done.md) — виконані задачі (Фази 1-7, рефакторинг, GUI, skills).
- [status.md](../status.md) — короткий джерело правди про поточний стан.
- [MODULES.md](MODULES.md) — повний каталог модулів.
- [API.md](API.md) — публічний API для інтеграції.
- [SECURITY.md](SECURITY.md) — безпека та ризики.
- [tests.md](tests.md) — тестові сценарії.
- [DEBUG_LOOP.md](DEBUG_LOOP.md) — методологія Debug-Loop.
- [LLM_to_LM_Studio.md](LLM_to_LM_Studio.md) — налаштування LM Studio з JSON Schema.
- [PLAN_COMPUTER_USE.md](PLAN_COMPUTER_USE.md) — стратегічний план Computer Use (від 26.04.2026).

---

## 1. Навіщо цей документ

Це не roadmap усіх фаз і не changelog. Це коротка технічна карта: як зараз реально влаштований проєкт, де архітектурний борг, у якому порядку варто його зменшувати.

---

## 2. Поточна структура

### Точки входу

- [run.py](../run.py) — універсальний entrypoint (PyQt6).
- [run_assistant_qt.py](../run_assistant_qt.py) — GUI entrypoint (PyQt6).
- [main.py](../main.py) — основний runtime / AssistantCore (~874 рядки, рефакторено у Фазі 1).

### Основні підсистеми

Після Фаз 1-7 (див. `TASKS_Done.md`) модулі згруповані в підпакети:

#### `core_gui_pyqt6/` — PyQt6 GUI (вкладкова структура)
- `main_window.py` — `MainWindowPyQt6` з `QTabWidget` (Чат, План, Логи, Статистика, Інструменти, Налаштування).
- `tab_chat.py` / `tab_plan.py` / `tab_logs.py` / `tab_stats.py` / `tab_tools.py` / `tab_settings.py` — окремі вкладки.
- `base_tab.py` — `BaseTab(QWidget)`.
- `constants.py` — кольори, розміри, версія.
- `confirmation_qt.py`, `llm_endpoints_editor_qt.py` — утиліти.
- Legacy: `chat_panel_qt.py`, `plan_panel_qt.py`, `settings_tab_qt.py` (міксини, що не видалені для сумісності).

#### `functions/llm/` — LLM-шар (дворівнева архітектура)
- **J1 (низький рівень)**: `logic_ai_adapter.py` (`AIProvider` ABC), `logic_provider_registry.py` (`ProviderRegistry`).
- **J2-J4 (оркестрація)**: `router.py` (`RequestRouter` + `TaskType`), `provider_chain.py` (`ProviderChain` з fallback), `endpoint_client.py` (HTTP).
- **Провайдери**: `providers_openai_compatible.py`, `providers_anthropic.py`, `providers_google.py`, `providers_browser.py`, `providers_vision.py`.
- **Інфраструктура**: `logic_llm_tools.py` (tool-calling), `response_parser.py` (JSON, sanitize), `streaming_buffer.py` (live token counting), `groq_client.py` (SDK), `helpers.py` (`ask_llm`).
- ✅ Завершено Фазу 4.1: router + provider_chain підключені в `AgentCoordinator.run()` та `helpers.ask_llm`.

#### `functions/planning/` — Планування та AgentLoop
- `agent_loop.py` (~479 рядків) — **легкий state-machine диспетчер** фаз (після рефакторингу Фази 7.2 з 2008 рядків).
- `agent_coordinator.py` — координація запуску (викликає router + provider_chain).
- `core_planner.py` / `core_planner_critic.py` / `core_planner_runner.py` — Planner з retry, PlanCritic.
- `planner_prompt_builder.py` / `planner_validator.py` / `planner_repair.py` — винесено з core_planner (Фаза 7.4).
- `pipeline_code.py` / `core_plan_compiler.py` / `core_task_intake.py` / `task_spec.py` — Phase 13 (універсальний executor).
- `plan_executor.py` / `plan_models.py` — виконавець + моделі.
- `logic_task_runner.py` (~1013 рядків) — TaskRunner з handler-реєстром + PermissionGate + Expectations.
- `logic_expectations.py` — 17 evaluator-ів.
- `logic_repair_loop.py` — `StepRepairer` (LLM repair, Phase 12.2).
- `logic_context_analyzer.py` (~854 рядки) — аналіз контексту, детекція блокаторів.
- `logic_plan_critic.py` / `logic_execution_report.py` / `logic_task_learner.py` / `logic_orchestrator.py` — додаткові компоненти Phase 11+.
- `logic_agent_tools_schema.py` — OpenAI tools schema.
- `ai_actors.py` — обгортки для Codex/Windsurf/Cursor.

#### `functions/agent/` — Фази AgentLoop (винесено у Фазі 7.2)
- `observe.py` (~410 рядків) — спостереження: screenshot, OCR, UIA tree, vision, active window.
- `plan.py` (~723 рядки) — `ActionDecider` з tool-calling, JSON parsing з fallback, replan.
- `act.py` (~477 рядків) — `ActionGuard` (безпековий прошарок).
- `check.py` (~350 рядків) — перевірка результату + checkpoint.

#### `functions/runtime/` — Runtime оркестрація
- `logic_core.py` (~511 рядків) — `FunctionRegistry` (реєстр функцій), `load_all_modules()` (з `rglob` по підпапках), `get_system_prompt()`.
- `logic_permission_gate.py` (~397 рядків) — 4-рівнева policy stack.
- `logic_watcher.py` (~457 рядків) — Watcher з потоками.
- `core_session_budget.py` (~215 рядків) — `SessionBudget` (ліміти часу/кроків/токенів, інтегрується з `UsageInfo`).
- `core_undo_manager.py` (~641 рядок) — snapshots + undo.
- `core_action_recorder.py` (~521 рядок) — ActionRecorder зі скріншотами до/після.
- `core_gui_guardian.py` (~532 рядки) — GUIGuardian (risk assessment).
- `core_safety_sandbox.py` — сендбокс для execute_python (AST-валідація).
- `core_loop_detector.py` — LoopDetector (захист від зациклення).
- `core_macro.py` (~293 рядки) — MacroRecorder + MacroPlayer (поки не в GUI).
- `core_windsurf_watcher.py` (~411 рядків) — WindsurfWatcher (GUI-інтегровано).
- `core_cache.py` — кеш тільки для idempotent операцій.
- `core_settings.py` — єдине джерело налаштувань (раніше дублювався).
- `core_app_profile.py` (~280 рядків) — AppProfile.
- `core_checkpoint.py` / `core_dispatcher.py` / `core_executor.py` / `core_memory.py` / `core_tool_runtime.py` — runtime-утиліти.
- `conditions_windows.py` / `conditions_web.py` — умови для платформ.
- `self_learning.py` — JSONL логи + skills база.
- `sync_settings_copy.py` / `windsurf_watcher_executor.py` — утиліти.
- `core_initializer_checks.py` — перевірки ініціалізації (винесено з main.py, Фаза 1.1).

#### `functions/audio/` — Audio
- `logic_stt.py` — Whisper, w2v-bert-uk.
- `logic_tts.py` — edge-tts.
- `logic_audio.py` / `logic_audio_filtering.py` — обробка.
- `logic_continuous_listener.py` — неперервний слухач.
- `core_stt_listener.py` — STT слухач.
- `initializer.py` — `AudioInitializer` (винесено з main.py, Фаза 1.2).

#### `functions/gui/` — GUI-логіка
- `logic_commands.py` — `VoiceAssistant` (обробка команд + `classify_task`).
- `commands_planner.py` — маршрутизація CHAT/AGENT/GUI_ACTION (винесено, Фаза 7.3).
- `commands_streaming.py` / `commands_audio.py` — стрімінг + аудіо-команди (винесено, Фаза 7.3).
- `core_gui_guardian.py` — risk assessment.
- `voice_tray_icon.py` — іконка в треї.

#### `functions/tools/` — Desktop/browser/media tools
- `tools_mouse_keyboard.py` (~436), `tools_window_manager.py` (~605), `tools_screen_capture.py` (~608), `tools_ocr.py` (~595), `tools_ui_detector.py` (~653), `tools_app_recognizer.py` (~573), `tools_visual_diff.py` (~504) — Phase 1-4.
- `tools_ui_accessibility.py` (~774) — UIA Windows API (uiautomation + pywinauto dual-backend, 10+ LLM tools, інтегровано з AgentLoop.observe()).
- `tools_browser_cdp.py` (~1071) — Playwright/CDP (12 browser tools).
- `tools_playwright.py` — додаткові утиліти.
- `tools_windsurf.py` — `SnapshotFn`, `WindowFinder`, `WindsurfState` (створено для фікса pytest, Фаза 1.1).
- `aaa_file_operations.py` — legacy файлові операції (з підтримкою `path` і `directory`).
- `aaa_execute_python.py` — execute_python з auto-wrap у print().
- `aaa_open_interpreter.py` — Open Interpreter fallback.

#### `functions/skills/` — Високорівневі навички (НОВИЙ пакет, Фаза 1.3)
- `base.py` (~97) — `BaseSkill`, `SkillResult`, `SkillError`.
- `registry.py` (~87) — `SkillRegistry`.
- `browser_skills.py` (~398) — `OpenBrowser`, `SearchGoogle`, `FillForm` з fallback (playwright → CDP → subprocess).

#### Кореневі модулі `functions/`
- `config.py` — глобальна конфігурація.
- `global_voice_input.py` — Windows hook (Ctrl+Shift+V).
- `logic_execution_report.py` — StepReport + ExecutionReport.
- `project_indexer.py` — Repo Map + Dependency Graph (ЕТАП Б).
- `tools_project_indexer.py` — tool-обгортки для project_indexer.

#### Інше
- `runtime/` — runtime data (cache, self-learning, settings, profiles, snapshots, macros, checkpoints, memory).
- `scenarios/` — JSON тестові сценарії.
- `scaner/` — файловий сканер.
- `tests/` — unit і integration-style тести (60+ файлів).
- `TEST_GUI/` — GUI діагностичні тести.

### Спостереження

- Після Фаз 1-7 проєкт структуровано: є чіткі підпакети `audio/llm/planning/agent/runtime/gui/tools/skills/`.
- `agent_loop.py` тепер 479 рядків (з 2008) — рефакторено у стан легкого state-machine.
- `main.py` — 874 рядки (з 1242), частково рефакторено (Фаза 1.1, 1.2, 1.3).
- Створено новий пакет `functions/agent/` з фазами AgentLoop.
- LLM-шар має повну реалізацію: router, provider_chain, providers, streaming, tool-calling.
- Skills DB наразі лінійна (потребує vector memory, Phase 10 P1).

---

## 3. Головні архітектурні проблеми

### 3.1. Залишкові перевантажені модулі

Найважчі файли зараз:
- `main.py` (~874 рядки) — ще має залишки God Object, потребують подальшого розбиття
- `core_planner.py` (~537 рядків) — ще важкий, хоча prompt_builder/validator/repair винесено
- `logic_task_runner.py` (~1013 рядків) — 10 handlers + PermissionGate + Expectations
- `logic_commands.py` — ще містить багато логіки, хоча commands_planner/streaming/audio винесено

### 3.2. Нестабільні контракти

Симптоми: тести імпортують API, яких уже немає (див. `TASKS.md` "Пріоритет 1"). Головне — підтримувати зворотну сумісність `AgentLoop`, `AssistantCore`, `FunctionRegistry`.

### 3.3. Змішані шари відповідальності

Planner і execution concerns залишаються переплетеними. PlanRunner як міст — тимчасове рішення.

### 3.4. Legacy шар не ізольований

`aaa_*` ще корисний для сумісності, але має бути чітко позначений як legacy-обгортки. `chat_panel_qt.py` / `plan_panel_qt.py` / `settings_tab_qt.py` — старі міксини, що залишилися для зворотної сумісності.

### 3.5. Runtime-артефакти частково розкидані

Stateful дані мають жити або в `runtime/`, або в `logs/`. Кодова директорія не повинна бути місцем для робочих JSON-станів.

### 3.6. AgentLoop все ще частково legacy

- AgentLoop тепер легкий state-machine (479 рядків), але логіка ще перетинається з `core_planner.py` та `core_planner_runner.py`.
- `AgentLoop.plan()` має 5 fallback-ів: decider → planner → plan_steps history → compiled_plan → noop.

---

## 4. Найважливіші технічні борги

### P0 (блокери для trunk)

- **ActionDecider fallback**: 5 FAILED тестів — `decide()` повертає `take_screenshot` замість `noop` після JSON failures.
- **AgentLoop removed methods**: 6 FAILED — `_execute_single_step`, `_handle_ask_user_step` (потрібно повернути або оновити тести).
- **get_endpoint_by_role**: 1 FAILED — відсутній експорт.
- **WindsurfWatcherConfig.max_tokens**: 7 FAILED — відсутній атрибут.
- **PermissionGate test failures**: 3 FAILED — шлях поза project root.
- **UndoManager**: 10 FAILED — стек/snapshot логіка розходиться з тестами.
- **UIAWrapper return normalization**: 6 FAILED — None замість error dict.
- **UIElement constructor**: 2 FAILED — `bounding_rectangle` → `bounding_rect`.

### P1 (стабільність / quality)

- **Здійснити Фазу 7.3 (Функція 7.3)**: винести system prompt з `FunctionRegistry` в JSON-файли.
- **Завершити `tools_ui_accessibility.py`**: деякі LLM-facing функції ще повертають `Not implemented yet`.
- **Додати Windows smoke CI**.
- **Vector Memory**: поточна реалізація Skills DB не підтримує семантичний пошук. Потрібна інтеграція ChromaDB/FAISS.
- **Розділення ролей LLM**: AgentLoop не розрізняє модель для планування та модель для критики.
- **GUI потокобезпечність**: `queue_dispatcher` ще потребує міграції на QThread для уникнення блокувань UI.
- **Sandbox ізоляція**: `core_safety_sandbox.py` потребує AST-валідації `aaa_execute_python` та обмеження робочої директорії.
- **ContextController**: замість жорсткого видалення повідомлень — sliding window з токен-каунтом.

### P2 (архітектурний борг)

- Прибрати циклічні залежності між GUI/screen/input шарами.
- Вирівняти структуру runtime state.
- Зменшити зв'язність між planner / runner / GUI.
- Здійснити Фазу 8 (конфігурація): type annotations на `config.py`, усунути прямі імпорти.
- MacroRecorder/MacroPlayer підключити до GUI.

---

## 5. Рекомендований порядок рефакторингу

### Крок 1. Закрити P0 (узгодженість контрактів)

Повернути відсутні API:
- `get_endpoint_by_role` в `functions/config.py`.
- `WindsurfWatcherConfig.max_tokens`.
- `AgentLoop._execute_single_step` / `_handle_ask_user_step`.
- Виправити `ActionDecider.decide()` — `noop` замість `take_screenshot` після JSON failures.
- Синхронізувати `UndoManager` з тестами.
- `UIAWrapper` — нормалізувати return values.
- `UIElement.bounding_rect` замість `bounding_rectangle`.

### Крок 2. Здійснити Фазу 7.3 (винести system prompt)

`FunctionRegistry.get_system_prompt()` → `runtime/prompts/{voice,coding}_prompt.json` через `prompt_loader.py`.

### Крок 3. Закрити P1 (quality)

- Доробити `tools_ui_accessibility.py` (Not implemented yet → реальна логіка).
- Додати Windows smoke CI.
- Vector memory (ChromaDB).
- Розділити ролі LLM (plan vs critic).

### Крок 4. Архітектурна гігієна

- Усунути циклічні залежності.
- Вирівняти runtime state.
- Зменшити зв'язність planner/runner/GUI.
- Здійснити Фазу 8 конфігурації.

### Крок 5. Поступово групувати модулі по підсистемах

Після стабілізації API можна рухатися до більш чіткої структури. Але це має бути наслідок попередніх кроків, а не стартова операція.

---

## 6. Чого не варто робити зараз

- Не робити "великий вибух" з масовим перенесенням файлів.
- Не додавати нові доменні пайплайни, поки code vertical slice не стабілізований.
- Не множити нові abstraction layers без конкретного виграшу в testability або підтримці.
- Не видаляти legacy `aaa_*` модулі та `*_panel_qt.py` міксини без ретельної перевірки тестів.

---

## 7. Definition of better

Архітектура стане помітно кращою, коли:
- ✅ `pytest` collection проходить стабільно (після Фази 1.1 — 1396 tests, 0 errors).
- ⏳ Базовий набір тестів повністю зелений (P0 з `TASKS.md` закриті).
- ⏳ Є Windows smoke CI.
- ⏳ status.md, README.md, MODULES.md, ARCHITECTURE.md і код не суперечать одне одному.
- ⏳ UIA шар не містить critical TODO в основних user-facing entrypoints.
- ⏳ Є один стабільний E2E сценарій `task → plan → execute → validate → report`.
- ⏳ Legacy шар чітко відділений від нового orchestration-стеку.

---

## 8. Ключові зміни від попередньої версії (21.05.2026 → 07.06.2026)

1. **Фаза 1.1-1.3** — розбиття `main.py` (1242 → 874 рядки): `core_initializer_checks.py`, `audio/initializer.py`, `agent_coordinator.py`.
2. **Фаза 7.2** — розбиття `agent_loop.py` (2008 → 479 рядків): логіка в `functions/agent/{observe,plan,act,check}.py`.
3. **Фаза 7.3** — розбиття `logic_commands.py`: `commands_planner.py`, `commands_streaming.py`, `commands_audio.py`.
4. **Фаза 7.4** — розбиття `core_planner.py`: `planner_prompt_builder.py`, `planner_validator.py`, `planner_repair.py`.
5. **Фаза 4** — LLM-шар: `router.py`, `provider_chain.py`, `endpoint_client.py` — все підключено в `AgentCoordinator.run()` та `helpers.ask_llm`.
6. **GUI переробка** — `core_gui_pyqt6/` має вкладкову структуру: 6 вкладок замість міксинів.
7. **Skills** — створено `functions/skills/` пакет (browser_skills з fallback ланцюжком).
8. **Phase 12.4 Context Window** — `StreamingBuffer` + status-bar контексту в `MainWindowPyQt6`.
9. **Phase 13** — `_scaffold_content()` реалізує базові шаблони; `pipeline_code.py` має `use_ai_actors` (вимкнено за замовчуванням).
