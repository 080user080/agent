# Проєкт: Асистент МАРК

> Останнє оновлення: 07.06.2026 — синхронізовано з актуальним кодом (після Фаз 1-7).

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash
# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

---

## 1. Мета проєкту

**МАРК** — локальний Windows-агент на Python, який:

- приймає задачу текстом або голосом;
- будує план і виконує його через інструменти;
- може працювати з файлами, кодом, браузером і GUI Windows;
- вміє делегувати частину задач іншим AI-провайдерам;
- прагне до довгих автономних сесій з контролем ризиків.

Коротко: ціль проєкту не "чат-асистент", а **goal-driven executor для Windows**.

---

## 2. Поточний стан

### Загальна оцінка

- **Ядро агента:** сильне MVP, придатне для локальної роботи й експериментів.
- **GUI automation:** хороша база, але ще не production-рівень.
- **Autonomous orchestration:** інфраструктура вже є, але не вся зшита в надійний E2E.
- **Універсальні домени:** частково закладені, але ще не доведені до "ТЗ -> готовий результат".

### Що вже реально є в коді

- GUI на PyQt6 у `core_gui_pyqt6/`, запуск через [run.py](D:/Python/agent/run.py) --qt.
- GUI на Tkinter застаріло і переміщено в [backup/tkinter_legacy/](D:/Python/agent/backup/tkinter_legacy/).
- Основний runtime у [main.py](D:/Python/agent/main.py) (~874 рядки, рефакторено у Фазі 1, ще містить залишки God Object).
- AgentLoop у [agent_loop.py](D:/Python/agent/functions/planning/agent_loop.py) (~479 рядків, рефакторено у Фазі 7.2 — легкий state-machine).
- Фази AgentLoop винесено в [functions/agent/](D:/Python/agent/functions/agent/) (observe/plan/act/check).
- LLM-шар має повну реалізацію: router, provider_chain, providers (OpenAI/Anthropic/Google), streaming, tool-calling.
- Skills пакет [functions/skills/](D:/Python/agent/functions/skills/) з browser_skills (playwright → CDP → subprocess).
- GUI перероблено на вкладкову структуру в [core_gui_pyqt6/](D:/Python/agent/core_gui_pyqt6/) — 6 вкладок.
- Planner / executor / memory / cache / safety / audit.
- `TaskRunner`, `PermissionGate`, `ExecutionReport`, `SessionBudget`, `Watcher`.
- LLM tool-calling та новий LLM-шар у `functions/llm/` (router.py, provider_chain.py).
- GUI automation: mouse/keyboard, windows, screenshot, OCR, UI detection, visual diff.
- Browser automation: Playwright CDP.
- AI actors / provider registry / repair loop / checkpoint infrastructure.
- Global voice input (Windows hook) — глобальне голосове введення.
- Self-learning — модуль самонавчання з аналізом помилок і skills базою.
- Plan executor — GUI-інтеграція для виконання планів.
- 64 тестових файли у [tests](D:/Python/agent/tests) + 10 діагностичних у [TEST_GUI](D:/Python/agent/TEST_GUI).
- CI та lint конфіг уже існують: [pyproject.toml](D:/Python/agent/pyproject.toml), [ci.yml](D:/Python/agent/.github/workflows/ci.yml).
- [logic_core.py](D:/Python/agent/functions/logic_core.py) — FunctionRegistry, get_system_prompt.
- [logic_commands.py](D:/Python/agent/functions/logic_commands.py) — VoiceAssistant, логіка команд.
- [core_planner.py](D:/Python/agent/functions/core_planner.py), [core_planner_critic.py](D:/Python/agent/functions/core_planner_critic.py), [core_planner_runner.py](D:/Python/agent/functions/core_planner_runner.py).
- [logic_task_runner.py](D:/Python/agent/functions/logic_task_runner.py), [plan_executor.py](D:/Python/agent/functions/plan_executor.py).
- [logic_permission_gate.py](D:/Python/agent/functions/runtime/logic_permission_gate.py) — PermissionGate з 4-рівневою policy stack (397 рядків).
- [agent_loop.py](D:/Python/agent/functions/planning/agent_loop.py) — AgentLoop як легкий state-machine (~479 рядків, рефакторено). ActionDecider винесено в `functions/agent/plan.py`.

### Ключові проблеми (згідно з info.txt)

- **main.py (~874 рядки):** Рефакторено у Фазі 1, ще містить залишки God Object. `AssistantCore` має `initialize_without_listener()` і `check_lm_studio()`.
- **agent_loop.py (~479 рядків):** Рефакторено у Фазі 7.2 (з 2008 рядків). Логіка винесена в `functions/agent/{observe,plan,act,check}.py`. `ActionDecider` тепер у `functions/agent/plan.py`.
- **core_planner.py (~537 рядків):** Ще важкий, але `planner_prompt_builder`/`planner_validator`/`planner_repair` винесено у Фазі 7.4.
- **logic_task_runner.py (~1013 рядків):** 10 built-in handlers + PermissionGate + Expectations. Потребує подальшого розбиття.
- **logic_commands.py:** `VoiceAssistant` — ще багато логіки, хоча `commands_planner`/`commands_streaming`/`commands_audio` винесено у Фазі 7.3.
- **logic_core.py:** `FunctionRegistry` робить занадто багато; `get_system_prompt()` ще містить хардкоджений текст (потребує Фазу 7.3 — винести в JSON).
- **logic_permission_gate.py:** 397 рядків, 4-рівнева policy stack, дублювання з `logic_expectations.py`.
- **Системне дублювання:** ✅ усунуто `core_settings.py` (2 рази → 1), ✅ `_sandbox.py` обʼєднано в `core_safety_sandbox.py`. Залишилось: `logic_stt.py` / `core_stt_listener.py` (ОК — різні ролі), `logic_task_learner.py` / `self_learning.py` (потребує аналізу), `logic_execution_report.py` / `logic_report_generator.py` (різні ролі).
- **Архітектурна маса:** ✅ functions/ структуровано в підпакети: `audio/llm/planning/agent/runtime/gui/tools/skills/`. Залишилось: 100+ файлів, змішані стилі назв.
- **AAA_* група:** 15 файлів на ~15 функцій — ще є, але не критично (працюють як legacy-обгортки).

---

## 3. Чесна оцінка готовності

### Сильні сторони

- Великий функціональний обсяг уже реалізований.
- Є реальна архітектурна база для автономного виконання, а не лише чат-відповідей.
- Є тестова база і CI, тобто проєкт вже не "без захисту".
- Є кілька важливих safety-механізмів: permission gate, audit, sandbox, undo/guardian.

### Що ще не дає вважати проєкт досягнутим

1. **Немає повністю стабільного trunk.**
   [tests/test_phase7_9.py](D:/Python/agent/tests/test_phase7_9.py) імпортує `parse_markdown_plan` з
   [functions/logic_task_runner.py](D:/Python/agent/functions/logic_task_runner.py), але цього API зараз немає.

2. **UIA-шар не завершено.**
   У [functions/tools_ui_accessibility.py](D:/Python/agent/functions/tools_ui_accessibility.py)
   частина LLM-facing функцій ще повертає заглушки `Not implemented yet`.

3. **Vision-LM MVP, але неповний.**
   У [functions/providers_vision.py](D:/Python/agent/functions/providers_vision.py) `analyze_image()` готовий для OpenAI/Claude/Gemini,
   але `detect_ui_elements()` і `suggest_actions()` — stubs.

4. **Phase 13 (Code pipeline) — не доведений до реального "ТЗ -> готовий артефакт".**
   - `_scaffold_content()` генерує порожні заглушки.
   - S9 (cross-AI actors) не підключено.
   - Деталі: див. TASKS.md ЕТАП 10.

5. **AgentLoop JSON parsing issue.**
   - LLM не генерує коректний JSON для tool-calling → зациклення.
   - Рішення: сильніший LLM або покращений парсинг JSON з fallback.

6. **Структура коду вже надто плоска й важка для підтримки.**
   У `functions/` 100+ файлів; найбільші модулі стали "центрами тяжіння":
   [main.py](D:/Python/agent/main.py),
   [logic_commands.py](D:/Python/agent/functions/logic_commands.py),
   [core_planner.py](D:/Python/agent/functions/core_planner.py),
   [logic_task_runner.py](D:/Python/agent/functions/logic_task_runner.py),
   [agent_loop.py](D:/Python/agent/functions/agent_loop.py).

7. **Контекст переповнюється при довгих діалогах.**
   Немає механізму стиснення історії.

8. **Skills DB лінійна.**
   self_learning зберігає навички як звичайний словник.

9. **Критик = Виконавець.**
   AgentLoop використовує одну модель для планування та перевірки.

---

## 4. Ключові вузькі місця

### P0. Стабільність і узгодженість контрактів

- Є розрив між тестами, статусом і фактичним API модулів.
- Документація вже кілька разів відставала від коду.
- Частина історичних описів посилається на старі імена модулів.

**Висновок:** головний ризик зараз не брак ідей, а drift між шарами системи.

### P1. Windows automation без достатнього hardening

- UIA частково недописаний.
- Немає Windows smoke CI.
- Реальна надійність на multi-monitor / DPI / accessibility ще не закрита системно.

### P1. E2E-сценарії ще слабші за обсяг інфраструктури

- Фундамент є, але мало доведених сценаріїв "від задачі до перевіреного результату".

### P2. Архітектурна маса

- `functions/` перевантажений.
- Є змішані стилі назв: `core_*`, `logic_*`, `tools_*`, `providers_*`, `aaa_*`.
- Є сліди legacy-підходів поруч із новим стеком.

---

## 5. Пріоритети на найближчі спринти

### Найвищий пріоритет

1. **Полагодити trunk stability**
   - повернути сумісність між тестами й `logic_task_runner`;
   - добитися, щоб `pytest` хоча б повністю проходив collection;
   - зафіксувати публічні API.

2. **Виправити AgentLoop JSON parsing**
   - LLM не генерує коректний JSON → зациклення
   - Рішення: сильніший LLM або покращений парсинг з fallback

3. **Створити Skills (абстракції над базовими діями)**
   - open_browser(), search_google(), fill_form()
   - База накопичуваних навичок

### Середній пріоритет

4. **Доробити accessibility-шар**
   - завершити `uia_list_elements`, `uia_find_button`, `uia_click_element`, `uia_set_text`.
   - Smoke-тести на Windows.

5. **Додати Windows CI / smoke suite**

6. **Створити router для вибору агента**
   - Meta-agent вирішує хто виконує (local vs API).

7. **Рефакторинг великих модулів** (частково виконано)
   - ✅ main.py (1242 → 874 рядки) — частково розділено (Фази 1.1-1.3)
   - ✅ agent_loop.py (2008 → 479 рядків) — розділено на functions/agent/ (Фаза 7.2)
   - ✅ logic_commands.py → commands_planner/streaming/audio (Фаза 7.3)
   - ⏳ logic_permission_gate.py (397 рядків) → перевірити дублювання з logic_expectations.py
   - ⏳ logic_task_runner.py (~1013 рядків) — потребує розбиття
   - ⏳ core_planner.py (~537 рядків) — ще важкий
   - ⏳ logic_commands.py — ще має залишки логіки

### Завершені пріоритети

- ✅ **Інтеграція AgentLoop з GUI** — кнопка 🤖, run_agent_loop
- ✅ **Tool-calling для LLM** — logic_agent_tools_schema, tool-calling інтеграція
- ✅ **Міграція GUI на PyQt6** — core_gui_pyqt6/ основний бекенд, Tkinter в backup/
- ✅ **Глобальне голосове введення** — global_voice_input.py, Ctrl+Shift+V hook
- ✅ **Самонавчання** — self_learning.py, JSONL логи, skills база.
- ✅ **LoopDetector** — core_loop_detector.py, захист від зациклення агента.
- ✅ **Синхронізація документації** — README/status/TASKS оновлено.

---

## 6. Що вважаю реально завершеним

### Можна вважати завершеним як фундамент

- базові planner / executor / memory / cache механізми;
- audit / permission / sandbox foundation;
- базові GUI tools;
- browser CDP MVP;
- repair loop foundation;
- checkpoint / watcher foundation;
- базову GUI-інтеграцію нового планового стеку.

### Не можна вважати завершеним попри наявність коду

- UI accessibility як production-ready шар;
- Phase 13 як universal executor;
- Windows automation hardening;
- cross-AI orchestration як надійну повсякденну функцію;
- документацію як повністю синхронізовану з кодом.

---

## 7. Документи проєкту

- [README.md](README.md) — запуск і загальний огляд.
- [TASKS.md](TASKS.md) — поточні задачі та їх статус.
- [docs/tests.md](docs/tests.md) — тестові сценарії та чеклісти.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архітектурний стан, борг і план рефакторингу.
- [info.txt](info.txt) — детальні описи .py файлів проєкту (оновлено 24.05.2026).

`status.md` відтепер є **коротким джерелом правди про поточний стан**.

---

## 8. Підсумок

Проєкт уже має сильний фундамент і незвично широкий обсяг реалізованого функціоналу.
Головний наступний крок — не "ще більше фіч", а **стабілізація, завершення accessibility,
Windows hardening і доведення 1-2 наскрізних сценаріїв до надійного стану**.

---

## 9. Детальні проблеми по файлах (з info.txt)

### Критичні файли (після рефакторингу)

- **main.py:** ~874 рядки (було 1242). `AssistantCore` — ще за багато, але частково винесено у Фазі 1.
- **agent_loop.py:** ~479 рядків (було 2008). `ActionDecider` винесено в `functions/agent/plan.py`. `AgentLoop` — легкий state-machine.
- **logic_task_runner.py:** ~1013 рядків. 10 handlers + PermissionGate + Expectations. Потребує розбиття.
- **logic_permission_gate.py:** 397 рядків. 4-рівнева policy stack. Дублює logic_expectations.py.

### Серйозні проблеми

- **logic_core.py:** FunctionRegistry робить занадто багато. `get_system_prompt()` ~200 рядків хардкодженого тексту (потребує Фазу 7.3).
- **logic_commands.py:** VoiceAssistant — ще багато логіки, хоча commands_planner/streaming/audio винесено у Фазі 7.3.
- **global_voice_input.py:** Логіка вставки тексту в `_insert_segment` та `_send_input_unicode`.
- **core_planner.py (~537 рядків):** Ще важкий, але planner_prompt_builder/validator/repair винесено у Фазі 7.4.
- **core_task_intake.py / task_spec.py / pipeline_code.py / core_plan_compiler.py:** Phase 13 — 4 файли на один пайплайн, але ActionDecider вже має online planning.

### Дублювання (після рефакторингу)

- ✅ `core_settings.py` — усунено (залишено тільки `functions/runtime/core_settings.py`).
- ✅ `safety_sandbox.py / core_safety_sandbox.py` — обʼєднано в `functions/runtime/core_safety_sandbox.py`.
- **logic_stt.py / core_stt_listener.py** — різні ролі (STT-функція vs STT-слухач), не дублікати.
- **logic_task_learner.py / self_learning.py** — потребують аналізу (можливо, обʼєднати).
- **logic_execution_report.py / logic_report_generator.py** — різні ролі (dataclass vs generator), не дублікати.

### Архітектурні пропозиції (з info.txt) — статус

1. ✅ **main.py** — частково розділено: `core_initializer_checks.py` (Фаза 1.1), `audio/initializer.py` (Фаза 1.2), `agent_coordinator.py` (Фаза 1.3). Залишилось: винести `lm_manager.py`, `audio_manager.py`, `stt_manager.py`, `tts_manager.py`.
2. ✅ **agent_loop.py** — розділено на `functions/agent/{observe,plan,act,check}.py` (Фаза 7.2).
3. ⏳ **logic_core.py** — не розділено. Потребує: `module_loader.py`, `function_registry.py`, `system_prompt_builder.py` (Фаза 7.3).
4. ⏳ **AAA_* група** — ще не згруповано в `tools/code_tools/`, `tools/voice_audio/`, `tools/system/`.
5. ✅ **Дубльовані файли** — частково усунено (core_settings, safety_sandbox).

### Виконані Фази рефакторингу (24.05.2026 — 07.06.2026)

| Фаза | Зміни |
|------|------|
| **Фаза 1.1** | `main.py` → `core_initializer_checks.py` |
| **Фаза 1.2** | `main.py` → `audio/initializer.py` |
| **Фаза 1.3** | `main.py` → `agent_coordinator.py`; створено `functions/skills/` пакет |
| **Фаза 1 (trunk)** | pytest collection виправлено (1396 tests, 0 errors); створено `tools_windsurf.py` |
| **Фаза 4** | LLM-шар: router + provider_chain підключено в `AgentCoordinator` та `helpers.ask_llm` |
| **Фаза 5** | WindsurfWatcher інтегровано в GUI; StepRepairer.is_available() розширено |
| **Фаза 6** | `_scaffold_content()` реалізує базові шаблони; AI actors підключено в pipeline_code |
| **Фаза 7.2** | `agent_loop.py` 2008 → 479 рядків |
| **Фаза 7.3** | `logic_commands.py` → `commands_planner.py` + `commands_streaming.py` + `commands_audio.py` |
| **Фаза 7.4** | `core_planner.py` → `planner_prompt_builder.py` + `planner_validator.py` + `planner_repair.py` |
| **GUI переробка** | `core_gui_pyqt6/` має 6 вкладок замість міксинів |
| **Phase 12.4** | `StreamingBuffer` + status-bar контексту в `MainWindowPyQt6` |
| **ЕТАП Б** | Repo Map + Dependency Graph (project_indexer.py) |
