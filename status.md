# Проєкт: Асистент МАРК
> Останнє оновлення: 20.04.2026 (розширення візії: універсальний task executor + оркестрація ШІ)

---

## 1. Загальний опис

**МАРК** — локальний **універсальний агент-виконавець** для Windows на Python.
Мета: не просто голосовий помічник, а **агент, здатний виконати будь-яку задачу**:
- отримує задачу українською мовою (голос/текст)
- будує план дій, виконує кроки через інструменти, перевіряє результат
- **бачить екран і взаємодіє з будь-якою програмою** (GUI-автоматизація)
- **виконує довгі автономні сесії** (3–6 годин — нагляд за іншими агентами, циклічні задачі)
- **оркеструє інші ШІ** (Windsurf, Cursor, Claude, GPT, локальні LLM) через API та/або браузер
- працює у **будь-яких доменах**: кодинг, фото/відео редагування, pipeline-и (ComfyUI, Blender), офіс, браузер

Стратегічний напрямок: **Універсальний Windows-агент**, що може керувати собою, іншими ШІ-агентами та будь-яким встановленим софтом.

---

## 1.1 🎯 Поведінкова філософія та пріоритети

Ці принципи визначають, **як** агент вирішує задачі та розставляє акценти під час розробки.

### Ієрархія пріоритетів поведінки (від найвищого до нижчого)

| # | Рівень | Опис | Приклад |
|---|--------|------|---------|
| **P0** | **Безпека й передбачуваність** | Не виконувати руйнівні дії без підтвердження (`execute_python`, `file_delete`, `system_command`). Rollback через `UndoManager`. | Перед `rm -rf`: snapshot + явне «ТАК». |
| **P1** | **Універсальність (task-agnostic)** | Агент НЕ обмежений кодингом. Має виконати будь-яку задачу, до якої має інструменти: фото, відео, ComfyUI, офіс, браузер, інсталятори. | «Наклади фільтр на фото» → Photoshop/GIMP/Pillow pipeline. |
| **P2** | **Оркестрація інших ШІ** | Коли задача складна — делегувати спеціалізованому агенту (Windsurf, Cursor, Claude, GPT, локальні моделі). Агент = диригент, не виконавець-самоучка. | «Дебаг цього репо» → відправити в Cursor/Claude Code, моніторити результат. |
| **P3** | **Довга автономія (3–6 год)** | Watcher-цикли: «коли інший агент дав відповідь → сформулюй наступний промпт → відправ». Самостійно переживає таймаути, reconnect-и, rate-limit-и. | Весь день переналагоджує репо через Windsurf без втручання. |
| **P4** | **Інженерна якість** | Debug, рефакторинг, створення PR. Може робити сам або делегувати (див. P2). | «Додай тести до модуля X» |
| **P5** | **Computer Vision + GUI** | Поточна сильна сторона (Phase 1–6). База для всього вищого. | OCR, template matching, scenario runner. |

### Інваріанти поведінки

1. **Завжди намагайся завершити задачу.** Якщо один інструмент зламався — спробуй альтернативу (pillow замість photoshop, HTTP API замість браузера). Ніколи не зупинятися на першій помилці.
2. **Оркеструй, не конкуруй.** Якщо інший ШІ робить щось краще — делегувати йому, не переписувати самому.
3. **Автономія = терпіння.** У watcher-режимі агент очікує хвилини/години між step-ами без зайвих дій. Немає «треба щось робити щосекунди».
4. **Бюджет дій обмежений.** Кожна автономна сесія має ліміт: `max_steps`, `max_tokens`, `max_duration_hours`, `max_api_cost`. Досяг — зупинка + summary.
5. **Прозорість.** Кожна автономна дія пишеться в `logs/audit.jsonl` з timestamp-ом. Користувач у будь-який момент бачить, що робиться.

### Що агент НЕ робить (anti-patterns)

- ❌ Не вигадує відповіді замість виклику інструмента («халюцинації»).
- ❌ Не виконує подовжені операції блокуюче в UI-потоці.
- ❌ Не проявляє ініціативу поза задачею («я помітив що можна ще..., робитиму»).
- ❌ Не відправляє дані користувача у зовнішні сервіси без дозволу.
- ❌ Не імітує відповіді інших ШІ (якщо Windsurf offline — так і повідомляє).

---

## 2. Поточний стан (21.04.2026)

### ✅ Реалізовано (ядро)

- GUI на Tkinter (модульна структура `core_gui/` — 9 файлів, `main_window.py` 584 рядки)
- Текстовий режим як основний робочий режим
- STT і TTS інтегровані (TTS вимкнено, STT — опційно)
- Реєстр функцій `aaa_*.py` (12 інструментів) + `tools_*.py` (7 GUI-модулів)
- Кеш (`core_cache.py`), dispatcher (`core_dispatcher.py`), стрімінг (`core_streaming.py`)
- LLM-виклики з JSON парсингом (`logic_llm.py`)
- Стрімінг відповіді LLM у GUI
- Довготривала пам'ять через `functions/core_memory.py`
- Planner інтегрований у `main.py` і `logic_commands.py`
- Асинхронне виконання плану через `TaskExecutor`
- **Структуровані результати інструментів** — `make_tool_result`
- **Артефакти кроків** — `step_artifacts`, `artifacts_summary`
- **Універсальні placeholder-и** — `{{last_file_path}}`, `{{last_output}}`
- **Адаптивна історія** — `_manage_conversation_history`
- **Розширена безпека** — 45 literal + 6 regex DANGEROUS_PATTERNS, 23 literal + 4 regex AMBIGUOUS_PATTERNS, `check_params_safety()`
- **Аудит** — `AuditLog`, журнал `logs/audit.jsonl`
- **Code tools** — `read_code_file`, `search_in_code`, `list_directory`, `git_status`, `git_diff`
- **Трирівнева пам'ять** — `SessionMemory` (RAM), `TaskMemory` (per-task), довготривала (JSON)
- **LLM-based summaries** — для задач та довгих діалогів
- **Coding Agent mode** — окремий prompt, автодетекція кодових задач (`aaa_architect.py`, `aaa_debug_code.py`)
- **GUI clipboard fix** — Ctrl+C/V/X на будь-якій розкладці
- **Панель плану** — прогрес-бар, статуси (pending/running/ok/error/blocked/skipped)
- **Підтвердження** — зворотний відлік 30с, кнопки ТАК/НІ/АВТОМАТИЧНО
- **SettingsManager** — persist у `user_settings.json`, schema для UI
- **Вкладка "Налаштування"** в GUI — Notebook, угрупування, валідація
- **Багатоетапний repair** — цикл до 3 спроб + 1 replan
- **Retry механізм планера** — 2 спроби з різними промптами
- **Утиліти** — `create_folder`, `search_in_text`, `count_words`
- **Safety sandbox** — `core_safety_sandbox.py` + `safety_config.json` (whitelist/blacklist)
- **Smart Patch GUI** — допоміжний GUI `smart_patch_gui.py` (642 рядки) для редагування коду
- **Phase 11 стек (новий, не підключений до GUI):** `TaskRunner` + `PermissionGate` + `ExecutionReport` + `SessionBudget` + `Watcher` + `ProviderRegistry` (LM Studio + fallback) + `PlanCritic` (meta-оцінка плану) + `Task.precheck` / `Task.expect` (Step-Check / Actor-Critic) + `ask_llm_with_tools` (OpenAI-compatible tool-calling) + `core_planner_critic` (bridge для legacy-плану у PlanCritic)
- **Тести** — pytest suite для `core_planner`, `core_memory`, `core_executor`, `tools_mouse_keyboard`, `tools_window_manager`, `tools_ocr` (6 файлів, ~1.6k рядків); **нові тести Phase 11+:** `test_logic_task_runner`, `test_logic_plan_critic`, `test_logic_expectations`, `test_logic_llm_tools`, `test_logic_watcher`, `test_core_session_budget`, `test_core_planner_critic` (+29) — разом **584 passed** на main
- **Документація** — README.md + CONTRIBUTING.md + tests.md

### ⚠️ Виявлено під час аудиту (20.04.2026)

1. **README.md розходиться з кодом:**
   - Посилається на структуру `gui/` — насправді `core_gui/`
   - Приклад запуску `python agent.py` — коректна команда `python run_assistant.py`
   - Перелік core-модулів у README неповний (відсутні `logic_scenario_runner`, `logic_ui_navigator`, `logic_context_analyzer`, `core_action_recorder`, `core_undo_manager`, `core_gui_guardian`, `tools_*`)
2. **`requirements.txt` застарілий:**
   - Містить лише audio-залежності (numpy, scipy, colorama, sounddevice, noisereduce, transformers, accelerate)
   - **Відсутні** фактично використовувані пакети: `pyautogui`, `pywin32`, `psutil`, `mss`, `Pillow`, `opencv-python`, `pytesseract` / `easyocr`, `requests`
3. **Чекбокси Phase 1–6 нижче все ще `[ ]`**, хоча самі фази позначені ✅ Завершено — модулі справді існують, але статус у тексті формально неузгоджений (актуалізовано в цьому оновленні).
4. **Неповне покриття тестами GUI Automation:**
   - ✅ Є: `test_tools_mouse_keyboard.py`, `test_tools_window_manager.py`, `test_tools_ocr.py`
   - ❌ Немає: `test_tools_screen_capture.py`, `test_tools_ui_detector.py`, `test_tools_app_recognizer.py`, `test_tools_visual_diff.py`, `test_logic_ui_navigator.py`, `test_logic_scenario_runner.py`, `test_logic_context_analyzer.py`, `test_core_action_recorder.py`, `test_core_undo_manager.py`, `test_core_gui_guardian.py`
5. **CI / lint-інфраструктура відсутні** — немає `.github/workflows/*`, `.pre-commit-config.yaml`, `pyproject.toml`, `ruff`/`flake8`/`black` конфігів.
6. **Застарілі / неактивні артефакти:**
   - `aaa_kill_process_by_name.py_off`, `aaa_open_program.py_old` — потрібно або повернути, або видалити
   - `cache_data.json`, `user_settings.json` лежать у `functions/` — краще винести в runtime-папку
7. **Архітектурна діаграма (секція 4)** не містить: `logic_core`, `logic_continuous_listener`, `logic_scenario_runner`, `logic_ui_navigator`, `logic_context_analyzer`, `core_streaming`, `core_dispatcher`, `core_action_recorder`, `core_undo_manager`, `core_gui_guardian`, `core_safety_sandbox`, `tools_*`, `aaa_architect`, `aaa_debug_code`, `aaa_voice_input` (виправлено нижче).

### Не дороблено / В процесі

- Голосове введення — індикатор мікрофона в GUI (відкладено через STT)
- Planner не робить повне перепланування дерева
- **Phase 7 GUI Automation** — Learning & Profiles (профілі програм, запис макросів, адаптивне навчання) — не розпочато
- **Покриття тестами Phase 2/4/5/6** — модулі є, автотестів немає (див. перелік вище)
- **Регулярний CI** (GitHub Actions, linters, coverage) — відсутній

---

## 3. Залежності

| Пакет | Версія | Статус |
|-------|--------|--------|
| numpy | 1.26.4 | ✅ знижено (несумісність з torch 2.x) |
| torch | 2.x | ✅ |
| sounddevice | 0.5.5 | ✅ |
| noisereduce | 3.0.3 | ✅ |
| scipy | 1.15.3 | ✅ |
| transformers | 5.0.0 | ✅ |
| colorama | 0.4.6 | ✅ |
| requests | 2.32.5 | ✅ |

**LM Studio:** `http://localhost:1234/v1/chat/completions`
**Поточна модель:** `deepseek-coder-v2-lite-instruct` / `openai/gpt-oss-20b`

**Запуск:** `python run_assistant.py`

---

## 4. Архітектура

```
run_assistant.py          ← точка входу (GUI + core)
main.py                   ← AssistantCore (ініціалізація, LLM, TTS, STT)
smart_patch_gui.py        ← окремий GUI для керованого редагування коду (патчі)
functions/
  # --- конфігурація / сховище ---
  config.py                    ← глобальні налаштування
  core_settings.py             ← SettingsManager (user_settings.json)
  safety_config.json           ← конфіг sandbox
  # --- планер / виконавець / runtime ---
  core_planner.py              ← Planner (Plan → Act → Verify → Repair)
  core_executor.py             ← TaskExecutor (async виконання плану)
  core_tool_runtime.py         ← TOOL_POLICIES, безпека, AuditLog
  core_dispatcher.py           ← маршрутизація викликів інструментів
  core_streaming.py            ← стрімінг відповідей LLM
  # --- пам'ять / кеш ---
  core_memory.py               ← MemoryManager (3 рівні)
  core_cache.py                ← кеш команд
  # --- безпека ---
  core_safety_sandbox.py       ← пісочниця виконання
  safety_sandbox.py            ← утиліти перевірок
  core_gui_guardian.py         ← Guardian для GUI-дій (risk levels, sandbox, preview)
  core_undo_manager.py         ← snapshots + undo для GUI-дій
  core_action_recorder.py      ← журнал GUI-дій (logs/gui_actions.jsonl)
  # --- LLM / логіка ---
  logic_core.py                ← спільна core-логіка
  logic_commands.py            ← VoiceAssistant (маршрутизація команд)
  logic_llm.py                 ← LLM виклики, JSON парсинг
  logic_tts.py                 ← TTS двигун
  logic_audio.py               ← аудіо фільтрація
  logic_audio_filtering.py     ← додаткові фільтри
  logic_stt.py                 ← STT (розпізнавання голосу)
  logic_continuous_listener.py ← постійне слухання мікрофона
  core_stt_listener.py         ← контролер STT-прослуховування
  # --- GUI Automation (Phase 1–6) ---
  tools_mouse_keyboard.py      ← миша + клавіатура + clipboard (Phase 1)
  tools_window_manager.py      ← керування вікнами Windows (Phase 1)
  tools_screen_capture.py      ← скріншоти, pixel, template matching (Phase 2)
  tools_ocr.py                 ← OCR (pytesseract + easyocr) (Phase 3)
  tools_ui_detector.py         ← UI елементи: кнопки, чекбокси, поля (Phase 4)
  tools_app_recognizer.py      ← розпізнавання активної програми/діалогу (Phase 4)
  tools_visual_diff.py         ← baselines + візуальне порівняння (Phase 4)
  logic_ui_navigator.py        ← інтелектуальна навігація UI (Phase 5)
  logic_scenario_runner.py     ← сценарії (save/open/find/print/...) (Phase 5)
  logic_context_analyzer.py    ← контекст екрану, suggest_next_action (Phase 5)
  # --- aaa_* інструменти агента ---
  aaa_architect.py             ← coding agent: архітектурні правки
  aaa_code_tools.py            ← читання/пошук/git
  aaa_confirmation.py          ← підтвердження дій
  aaa_create_file.py           ← створення файлу (Desktop)
  aaa_debug_code.py            ← автодебаг Python
  aaa_edit_file.py             ← редагування файлів (бекапи)
  aaa_execute_python.py        ← Python sandbox
  aaa_open_browser.py          ← відкриття URL
  aaa_programs.py              ← запуск/закриття програм
  aaa_system.py                ← системні команди
  aaa_utility_tools.py         ← дрібні утиліти
  aaa_voice_input.py           ← голосовий ввід
core_gui/
  __init__.py             ← shim (AssistantGUI, run_gui)
  main_window.py          ← AssistantGUI (головне вікно)
  chat_panel.py           ← ChatPanelMixin
  confirmation.py         ← ConfirmationMixin
  plan_panel.py           ← PlanPanelMixin
  settings_tab.py         ← SettingsTabMixin
  styles.py               ← ttk стилі
  constants.py            ← константи
  llm_endpoints_editor.py ← редактор LLM-ендпоїнтів
tests/
  test_core_planner.py           test_core_memory.py           test_core_executor.py
  test_tools_mouse_keyboard.py   test_tools_window_manager.py  test_tools_ocr.py
```

---

## 5. Завершені етапи розвитку

### Етап A. Minimum Viable Agent ✅
### Етап B. Strong Agent Loop ✅
### Етап C. Tool Runtime ✅
### Етап D. Memory & Context ✅
### Етап E. Safety ✅
### Етап F. Code Agent Mode ✅

---

## 6. Готовність до продакшну

**~95% Core** — основні функції (планер, пам'ять, executor, кеш) працюють стабільно.
**~70% GUI Automation** — реалізовано 6 з 7 фаз (Phase 1–6), код є в `functions/tools_*.py` та `functions/logic_*_navigator/runner/analyzer.py`; залишається Phase 7 (Learning & Profiles) + повне покриття автотестами Phase 2/4/5/6.

---

---

# 🚀 СТРАТЕГІЧНИЙ ПЛАН: GUI Automation & Computer Vision

> **Ціль:** Перетворити МАРК на універсального Windows-агента, який **бачить екран**, **розуміє** що на ньому, і **самостійно взаємодіє** з будь-якою програмою без спеціального API.

---

## 🗺️ Огляд фаз

| Фаза | Назва | Статус | Пріоритет | Термін |
|------|-------|--------|-----------|--------|
| 1 | Базова автоматизація GUI | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 2 | Скріншоти та аналіз екрану | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 3 | OCR — розпізнавання тексту | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 4 | Комп'ютерний зір (CV) | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 5 | Розумна навігація по UI | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 6 | Безпека та журнал дій | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 7 | Навчання, адаптація, профілі, макроси | 🟡 Фундамент у роботі | 🟡 Середній | 4–6 тижнів |
| 8 | **Автономія (Watcher, довгі сесії)** | 🟢 Скелет готовий (I1+I2+I3) | 🔴 Високий | 4–6 тижнів |
| 9 | **Оркестрація інших ШІ** (API + браузер) | 🟢 Скелет готовий (J1+J2+J3) | 🔴 Високий | 6–8 тижнів |
| 10 | Універсальні домени (фото/відео/ComfyUI/офіс/браузер) | 🔴 Не розпочато | 🟡 Середній | постійно |
| 11 | **Autonomous Task Orchestrator** (TaskRunner + PermissionGate + ExecutionReport) | ✅ **Скелет готовий** (PR #13) | 🔴 **Критичний** | 20.04.2026 |
| 11.5 | **Plan-critic LLM** (самокритика плану перед виконанням) | ✅ Злито (PR #18) | 🔴 Високий | 20.04.2026 |
| 11.5a | **Bridge PlanCritic ↔ legacy Planner** (`core_planner_critic`) | ✅ Злито (PR #21) | 🔴 Високий | 21.04.2026 |
| 11.6 | **Bridge Planner → TaskRunner** (`core_planner_runner`: legacy-tools як `kind`-и + `run_legacy_plan_via_runner`) | 🟢 У PR | 🔴 Високий | 21.04.2026 |
| 12.1 | **Step-Check / Actor-Critic MVP** (`Task.precheck` / `Task.expect`) | ✅ Злито (PR #18) | 🔴 Високий | 20.04.2026 |
| F1 | **LM Studio tool-calling + JSON mode** (`logic_llm_tools.ask_llm_with_tools`) | ✅ Злито (PR #19) | 🔴 Високий | 20.04.2026 |
| 12.2 | **LLM repair loop на `expect_failed`** (повний Actor-Critic цикл) | 🔴 Не розпочато | 🟡 Середній | наступний спринт |
| 12.3 | **GUI-інтеграція TaskRunner** (кнопка «Виконати план», live-progress, kill-switch) | 🔴 Не розпочато | 🔴 Високий (блокер для 3–6 год автономії) | наступний спринт |
| 12.4 | **Checkpoint + resume** (persist `StepReport[]` + `context`, відновлення після крашу) | 🔴 Не розпочато | 🟡 Середній (потрібно для 3–6 год автономії) | +1 спринт |

---

## 🧍 Пробіли до «як людина»

> **Мета цього розділу:** чесно зафіксувати, що саме бракує MARK, щоб діяти з ПК **як людина** — тобто бачити екран, розуміти UI, взаємодіяти з будь-якою програмою надійно і довго. Це **не окремі фази**, а **перехресні треки**, які покривають зазори між існуючими фазами.

### 🔴 Блокери (без них «як людина» неможливо)

| ID | Трек | Проблема | Пропозиція |
|----|------|----------|------------|
| **V1** | **Accessibility API (UIA)** | Агент «бачить» лише через OCR + template matching — це крихко до DPI, локалізації, тем оформлення. Людина «бачить» структуру UI (кнопка, поле вводу) через accessibility-дерево. | Інтегрувати `uiautomation` (Windows `UIAutomationCore`) або `pywinauto` як новий `tools_ui_accessibility.py`. Повертати список елементів (role, name, bounds, enabled) поточного вікна. Це фундамент для решти. |
| **V2** | **Vision-LM** | Без vision-моделі агент не може «подивитись на скрін і зрозуміти що тут треба натиснути». `tools_ocr` / `tools_ui_detector` дають сирі дані — не розуміння. | Додати `providers_vision.py` (pluggable: GPT-4V / Claude Vision / LLaVA локально). Новий tool `describe_screen(image)` → текст-опис або `plan_next_action(screenshot, goal)`. Не обовʼязково GPT-4V — локальна LLaVA через Ollama достатня для MVP. |
| **V3** | **Real browser automation** | `aaa_open_browser.py` = `webbrowser.open(url)` і більше нічого. Не може клікати, вводити текст, витягти дані зі сторінки. Без цього задачі типу «зайди на Gemini, спитай щось» — неможливі. | Підключити **Playwright** через CDP на існуючому Chrome-профілі юзера (залогінений). Новий `tools_browser.py`: `open_url`, `click_by_role`, `fill`, `screenshot`, `extract_text`, `wait_for`. Див. трек **E2** / **J3**. |
| **V4** | **GUI-інтеграція нового стеку** | Phase 11 стек (`TaskRunner`, `PlanCritic`, `Task.expect`, `SessionBudget`, `PermissionGate`) повністю відʼєднаний від `run_assistant.py`. Коли юзер натискає «Виконати» — йде по legacy-потоку **без** цих покращень. | Phase 12.3 (див. вище) — кнопка «Виконати план» у `core_gui/` + live `StepReport` + kill-switch. |

### 🟡 Важливе (робить агента значно надійнішим)

| ID | Трек | Проблема | Пропозиція |
|----|------|----------|------------|
| **V5** | **DPI & multi-monitor координати** | `pyautogui.click(x, y)` використовує абсолютні екранні координати. При зміні DPI, позиції вікна, переносі на другий монітор — кліки промахуються. | Координати **відносно вікна** (`RECT` з `pywin32`), нормалізовані за DPI (`GetDpiForWindow`). Новий helper `click_in_window(hwnd, rel_x, rel_y)` у `tools_mouse_keyboard.py`. |
| **V6** | **Людяний input** | Лінійний рух миші + фіксовані затримки легко детектяться анти-ботами, і виглядають нереалістично в рекордингах. | `human_move(x, y)` з Bezier-кривою + варіабельна швидкість. `human_type(text)` з варіацією pause distribution (30–120ms). Опційно: не вмикати за замовчанням — тільки для «realistic mode». |
| **V7** | **Repair loop на `expect_failed`** | Якщо очікуваний стан не досягнуто (`Task.expect` fail), агент зупиняється або retry-ить той самий крок. Людина ж адаптує подальші дії. | Phase 12.2 (див. вище) — LLM бачить `metadata.expect_results` + решту плану і переписує наступні кроки. |
| **V8** | **Windsurf / Cursor делегування** | Для важких задач (написати компонент, відрефакторити модуль) логічно делегувати спеціалізованим агентам. Зараз нема. | Трек **J4** — `delegate_to_windsurf(task)` / `delegate_to_cursor(task)` через Playwright CDP (заздалегідь залогінений профіль). |

### 🟢 Дрібне (якість життя)

| ID | Трек | Проблема |
|----|------|----------|
| **V9** | **Checkpoint + resume** | При крашу 3-годинної сесії все втрачено. Phase 12.4 (див. вище). |
| **V10** | **Drag-n-drop файлів у програму** | Базова підтримка є, не тестовано на всіх типах (Explorer → app, app → app). |
| **V11** | **Global hotkeys / tray icon** | Нема способу «розбудити» агента глобальним hotkey без перемикання вікна. |
| **V12** | **Мікрофон/камера/аудіо-вихід як інпути для vision-LM** | STT опційно. Вебкамера не підʼєднана. Голосове керування «по ходу роботи» — нема. |

### Пріоритет реалізації (рекомендація)

1. **V4 (GUI-інтеграція)** — найдешевший шлях отримати реальну користь від Phase 11 стеку.
2. **V3 (Playwright)** — розблоковує весь клас «веб-задач», які зараз просто неможливі.
3. **V1 (UIA)** — робить GUI-кліки стійкими до DPI/локалізації/тем.
4. **V2 (Vision-LM)** — робить агента здатним «зрозуміти незнайомий UI».
5. **V7 (repair loop)** — замикає Actor-Critic.
6. Решта — коли буде час.

> **Оцінка чесного stage:** без V1–V4 агент — це **набір ізольованих інструментів з планером**, а не «користувач ПК». З V1–V4 — вже реальний GUI-агент рівня ранніх версій OpenAI Operator / Claude Computer Use.

---

## 📦 Phase 1: Базова автоматизація GUI (Core Input Control)

**Статус:** ✅ Готово | **Пріоритет:** ✅ Завершено | **Термін:** 20.04.2026

**Мета:** Дати агенту «руки» — можливість керувати мишею та клавіатурою, взаємодіяти з вікнами Windows.

**Залежності:** `pyautogui`, `pywin32`, `psutil`

### 1.1 Модуль `tools_mouse_keyboard.py` — Керування мишею та клавіатурою

#### Миша
- [x] `mouse_click(x, y, button='left', clicks=1, interval=0.1)`
- [x] `mouse_move(x, y, duration=0.5)`
- [x] `mouse_scroll(amount, direction='down', x=None, y=None)`
- [x] `mouse_drag(start_x, start_y, end_x, end_y, duration=0.5)`
- [x] `get_mouse_position()` → `{"x": int, "y": int}`
- [x] `mouse_click_image(image_path, confidence=0.8)` — template matching

#### Клавіатура
- [x] `keyboard_press(key)`
- [x] `keyboard_type(text, interval=0.02)`
- [x] `keyboard_hotkey(*keys)`
- [x] `keyboard_hold(key, duration=1.0)`
- [x] `keyboard_send_special(key_name)`

#### Clipboard
- [x] `clipboard_copy_text(text)`
- [x] `clipboard_get_text()` → `str`
- [x] `clipboard_copy_image(image_path)`

### 1.2 Модуль `tools_window_manager.py` — Керування вікнами Windows

#### Пошук та список вікон
- [x] `list_windows(include_hidden=False)`
- [x] `find_window_by_title(pattern, exact=False)`
- [x] `find_window_by_process(process_name)`
- [x] `find_window_by_class(class_name)`
- [x] `get_active_window()`

#### Керування станом вікон
- [x] `activate_window(hwnd)` (SetForegroundWindow)
- [x] `minimize_window(hwnd)` / `maximize_window(hwnd)` / `restore_window(hwnd)`
- [x] `close_window(hwnd, force=False)`
- [x] `hide_window(hwnd)` / `show_window(hwnd)`

#### Позиція та розмір
- [x] `move_window(hwnd, x, y)` / `resize_window(hwnd, w, h)` / `move_resize_window(...)`
- [x] `get_window_rect(hwnd)`
- [x] `center_window(hwnd)`

#### Допоміжні функції
- [x] `is_window_visible` / `is_window_minimized` / `is_window_maximized`
- [x] `wait_for_window(title_pattern, timeout=10)`
- [x] `wait_window_close(hwnd, timeout=30)`
- [x] `bring_all_to_top(process_name)`

### 1.3 Реєстрація в TOOL_POLICIES

- [x] Всі функції зареєстровані в `core_tool_runtime.py` (категорія `CATEGORY_GUI`)
- [x] Рівні ризику встановлені (`SAFE`/`CONFIRM_REQUIRED`)
- [x] Аудит GUI-дій у `logs/audit.jsonl` (через `AuditLog`)

### 1.4 Тести Phase 1

- [x] `tests/test_tools_mouse_keyboard.py` (253 рядки, mock pyautogui)
- [x] `tests/test_tools_window_manager.py` (460 рядків, mock win32gui)
- [ ] Інтеграційний тест: відкрити notepad → ввести текст → зберегти → закрити (потребує Windows VM для CI)

---

## 📸 Phase 2: Скріншоти та аналіз екрану (Screen Capture)

**Статус:** ✅ Готово | **Пріоритет:** ✅ Завершено | **Термін:** 20.04.2026

**Мета:** Дати агенту «очі» — можливість бачити екран і аналізувати його вміст.

**Залежності:** `Pillow`, `mss`, `pywin32`

### 2.1 Модуль `tools_screen_capture.py` — Захоплення екрану

#### Основні функції (`functions/tools_screen_capture.py`, 608 рядків)
- [x] `take_screenshot(save_path=None)` — повний скріншот (усі монітори)
- [x] `capture_monitor(monitor_index=0, save_path=None)`
- [x] `capture_region(x, y, width, height, save_path=None)`
- [x] `capture_window(hwnd, save_path=None)` (PrintWindow)
- [x] `capture_active_window(save_path=None)`

#### Інформація про екран
- [x] `get_screen_size()`
- [x] `get_monitors_info()`
- [x] `get_pixel_color(x, y)`
- [x] `get_region_color_histogram(x, y, w, h)`

#### Порівняння та пошук
- [x] `find_image_on_screen(template_path, confidence=0.8)`
- [x] `find_all_images_on_screen(template_path, confidence=0.8)`
- [x] `wait_for_image(template_path, timeout=10, interval=0.5)`
- [x] `image_changed(region, threshold=0.05)`
- [x] `wait_for_visual_change(region, timeout=10)` / `wait_for_visual_stable(...)`

#### Аналіз кольорів та змін
- [x] `pixel_matches_color(x, y, color, tolerance=10)`
- [x] `wait_for_color(x, y, color, timeout=10)`
- [x] `detect_loading_indicator(region=None)`
- [x] `detect_modal_dialog()`

### 2.2 Кешування скріншотів та аудит дій (`functions/core_action_recorder.py`, 521 рядок)

- [x] `ActionRecorder` singleton з автозаписом
- [x] Автоматичний скріншот до/після кожної дії через декоратор `@recordable`
- [x] Запис у `logs/gui_actions.jsonl`
- [x] Ліміт: 500 записів / 7 днів

#### Перегляд та експорт
- [x] `get_recent_actions(count)`
- [x] `export_session_log(format)` — JSON або text
- [x] `generate_action_report()` — статистика по діях
- [x] `search_actions(filter)`

### 2.3 Тести Phase 2

- [ ] `tests/test_tools_screen_capture.py` — mock mss, PIL операції (**ТРЕБА**)
- [ ] Тест template matching з синтетичними зображеннями (**ТРЕБА**)
- [ ] `tests/test_core_action_recorder.py` (**ТРЕБА**)

---

## Phase 3: OCR — Розпізнавання тексту на екрані

**Статус:** ✅ Готово | **Пріоритет:** ✅ Завершено | **Термін:** 20.04.2026

**Мета:** Агент читає текст з будь-якого місця екрану — кнопок, меню, повідомлень, таблиць.

**Залежності:** `pytesseract` (основний), `easyocr` (fallback)

### 3.1 Модуль `tools_ocr.py` — Розпізнавання тексту ✅

**Файл:** `functions/tools_ocr.py` (~520 рядків)

#### Базові функції
- ✅ `ocr_screen(save_screenshot=None)` → Розпізнати текст на всьому екрані
- ✅ `ocr_region(x, y, width, height)` → Розпізнати текст в області
- ✅ `ocr_window(hwnd)` → Розпізнати текст у вікні
- ✅ `ocr_image(image_path)` → Розпізнати текст на зображенні
- ✅ `ocr_to_string(region=None)` → Просто текст для LLM

#### Пошук та взаємодія
- ✅ `find_text_on_screen(text, case_sensitive=False)` → Знайти координати тексту
- ✅ `find_all_text_on_screen(text)` → Всі входження тексту
- ✅ `click_text(text, offset_x, offset_y)` → Знайти текст і клікнути
- ✅ `wait_for_text(text, timeout=10)` → Очікувати появи тексту

#### Реалізація
- ✅ **OCREngine** клас — підтримка PyTesseract та EasyOCR
- ✅ **ScreenOCR** клас — інтеграція з ScreenCapture
- ✅ **Fallback логіка** — якщо один движок не впевнений, пробує інший
- ✅ **Попередня обробка** — збільшення малих зображень, контраст, різкість
- ✅ **Визначення мов** — українська (ukr) + англійська (eng)

### 3.2 Реєстрація в TOOL_POLICIES ✅

Додано в `core_tool_runtime.py`:
- `ocr_screen` — SAFE, idempotent
- `ocr_region` — SAFE, idempotent  
- `ocr_window` — SAFE, idempotent
- `ocr_image` — SAFE, idempotent
- `find_text_on_screen` — SAFE, idempotent
- `click_text` — CONFIRM_REQUIRED (дія)
- `wait_for_text` — SAFE

### 3.3 Тести Phase 3 ✅

**Файл:** `tests/test_tools_ocr.py`
- ✅ Тести OCREngine (ініціалізація, розпізнавання)
- ✅ Тести ScreenOCR (пошук тексту, кліки)
- ✅ Тести попередньої обробки зображень
- ✅ Mock тести без зовнішніх залежностей

### Приклади використання

```python
# Розпізнати весь екран
result = ocr_screen()
print(result['text'])  # "Зберегти файл як..."

# Знайти кнопку і клікнути
result = click_text("Зберегти")
if result['success']:
    print(f"Клікнуто в ({result['clicked_at']['x']}, {result['clicked_at']['y']})")

# Очікувати текст на екрані
result = wait_for_text("Завантаження завершено", timeout=30)
```

### Встановлення залежностей

```bash
# Основний движок (рекомендовано)
pip install pytesseract
# Також потрібно встановити Tesseract-OCR:
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# У PATH додати: C:\Program Files\Tesseract-OCR

# Альтернатива (GPU-прискорена)
pip install easyocr
```

---

## Phase 4: Комп'ютерний зір (Computer Vision)

**Статус:** ✅ **Завершено** | **Пріоритет:** ✅ Готово | **Термін:** 20.04.2026

#### Template matching (без ML)
- `find_button_by_image(template_path, confidence=0.8)` → `{x, y, width, height, confidence}`
- `find_icon(icon_name_or_path, confidence=0.8)` → `{x, y, confidence}`
- `find_checkbox(region=None)` → `[{x, y, checked, center_x, center_y}]`
- `find_input_field(region=None)` → `[{x, y, width, height, center_x, center_y}]`
- `find_progress_bar(region=None)` → `{x, y, width, height, percent}`

#### Комбінований OCR + CV пошук
- `find_button_by_text(text, region=None, confidence=0.7)` → `{x, y, center_x, center_y, confidence}`
- `find_label(text, region=None)` → `{x, y, center_x, center_y}`
- `find_input_near_label(label_text, region=None)` → `{x, y, width, height, label}`

#### Аналіз стану елементів
- `is_button_enabled(x, y, width, height)` → `bool`
- `is_checkbox_checked(x, y)` → `bool`
- `get_button_state(x, y)` → `"normal" | "hovered" | "pressed" | "disabled"`

### 4.2 Модуль `tools_app_recognizer.py` — Розпізнавання програм 

- `detect_active_application()` → `{name, type, confidence, exe_name, pid, hwnd}`
- `detect_application_state()` → `{state: "idle"|"loading"|"error"|"dialog", details}`
- `is_application_ready(hwnd)` → `bool`
- `detect_file_dialog()` → `{type: "open"|"save", current_path, title, hwnd}`
- `detect_error_dialog()` → `{title, message, buttons, hwnd}`
- `detect_context_menu()` → `{items, count, hwnd}`

### 4.3 Модуль `tools_visual_diff.py` — Порівняння станів екрану 

- `capture_baseline(name)` — зберегти еталонний скріншот
- `delete_baseline(name)` — видалити еталон
- `list_baselines()` → `[{name, path, created, size_bytes}]`
- `compare_with_baseline(name)` → `{changed, diff_regions, diff_percent, changed_pixels}`
- `highlight_changes(before, after)` → `PIL.Image` з підсвіченими змінами
- `wait_for_visual_change(region, timeout=10)` → `{changed, diff_percent, wait_time}`
- `wait_for_visual_stable(region, stable_time=1.0, timeout=15)` → `{stable, wait_time}`

### 4.4 Тести Phase 4

- [ ] `tests/test_tools_ui_detector.py` — синтетичні зображення UI-елементів (**ТРЕБА**)
- [ ] `tests/test_tools_app_recognizer.py` — mock скріншоти відомих програм (**ТРЕБА**)
- [ ] `tests/test_tools_visual_diff.py` — синтетичні "до/після" зображення (**ТРЕБА**)

---

## 🧠 Phase 5: Розумна навігація по UI (Smart UI Navigation)

**Статус:** ✅ **Завершено** | **Пріоритет:** ✅ Готово | **Термін:** 20.04.2026

**Мета:** Агент може виконувати складні UI-сценарії автономно: заповнити форму, пройти wizard, відповісти на діалог.

### 5.1 Модуль `logic_ui_navigator.py` — Інтелектуальна навігація ✅

**Файл:** `functions/logic_ui_navigator.py` (~650 рядків)

#### Базові UI-дії
- ✅ `click_element(description, element_type)` → `{success, coordinates, message}`
- ✅ `type_in_field(field_description, text, clear_first)` → `{success, field, text}`
- ✅ `select_option(dropdown_description, option_text)` → `{success, dropdown, option}`
- ✅ `check_checkbox(label, state)` → `{success, label, previous_state, new_state}`
- ✅ `select_radio(label)` → `{success, label}`
- ✅ `navigate_tabs(tab_name)` → `{success, tab}`

#### Форми
- ✅ `fill_form(field_dict)` → `{success, filled, failed, total}`
- ✅ `submit_form(submit_button_text)` → `{success, button}`
- ✅ `read_form_values(field_names)` → `{success, values, raw_text}`
- ✅ `validate_form_filled(required_fields)` → `{valid, missing, checked}`

#### Меню та контекстні меню
- ✅ `open_menu(menu_name)` → `{success, menu}`
- ✅ `click_menu_item(path_list)` → `{success, path, message}`
- ✅ `open_context_menu(x, y)` → `{success, coordinates}`
- ✅ `click_context_item(item_text)` → `{success, item}`
- ✅ `close_menu()` → `{success, message}`

#### Діалоги
- ✅ `handle_dialog(expected_text, action)` → `{success, action, button, message}`
- ✅ `dismiss_all_dialogs(timeout)` → `{closed, failed, message}`

### 5.2 Модуль `logic_scenario_runner.py` — Сценарії автоматизації ✅

**Файл:** `functions/logic_scenario_runner.py` (~700 рядків)

#### Визначення та виконання сценаріїв
- ✅ `ScenarioStep` — датаклас кроку: `{step_type, description, params, verify, on_fail}`
- ✅ `Scenario` — датаклас сценарію з серіалізацією JSON
- ✅ `run_scenario(scenario, variables)` → `ScenarioResult`
- ✅ `run_scenario_from_file(filename, variables)` → `ScenarioResult`
- ✅ `save_scenario(scenario, filename)` → `{success, path}`
- ✅ `load_scenario(filename)` → `{success, scenario}`
- ✅ `list_scenarios()` → `[{name, description, path, steps_count}]`
- ✅ `validate_scenario(scenario)` → `{valid, warnings, errors}`

#### Вбудовані типові сценарії
- ✅ `scenario_save_file()` — зберегти файл (Ctrl+S)
- ✅ `scenario_open_file(file_path)` — відкрити файл (Ctrl+O)
- ✅ `scenario_save_as(save_path)` — зберегти як (Ctrl+Shift+S)
- ✅ `scenario_find_in_program(search_text)` — пошук (Ctrl+F)
- ✅ `scenario_print()` — друк (Ctrl+P)
- ✅ `scenario_undo_redo(action, count)` — undo/redo
- ✅ `scenario_select_all_copy()` — виділити все та скопіювати

### 5.3 Модуль `logic_context_analyzer.py` — Аналіз контексту екрану ✅

**Файл:** `functions/logic_context_analyzer.py` (~600 рядків)
#### Аналіз стану екрану
- ✅ `analyze_current_context()` → `{application, state, elements, available_actions, warnings}`
- ✅ `suggest_next_action(goal)` → `{action, params, confidence, reasoning, alternatives}`
- ✅ `explain_screen(detail_level)` → `str` — текстовий опис для LLM
- ✅ `detect_user_goal_completion(goal_description)` → `{completed, confidence, evidence}`
- ✅ `detect_blocker()` → `{type, description, suggested_fix, severity}` або `None`
- ✅ `get_context_changes(steps_back)` → порівняння з попереднім станом

### 5.4 Тести Phase 5

- [ ] `tests/test_logic_ui_navigator.py` — mock Phase 1-4 модулі (**ТРЕБА**)
- [ ] `tests/test_logic_scenario_runner.py` — mock сценарії (**ТРЕБА**)
- [ ] `tests/test_logic_context_analyzer.py` — mock поєднання OCR + UI detector (**ТРЕБА**)
- [ ] E2E тест: відкрити Notepad → заповнити форму → зберегти → закрити (потребує Windows VM)

---

## Phase 6: Безпека, Аудит та Відкат дій

**Статус:**  **Завершено** | **Пріоритет:**  Готово | **Термін:** 20.04.2026

**Мета:** Гарантувати безпечну роботу агента з реальним UI — ніяких неочікуваних дій, журнал усього, можливість відкату.

### 6.1 Модуль `core_action_recorder.py` — Журнал GUI-дій 

**Файл:** `functions/core_action_recorder.py` (~500 рядків)

#### Запис дій
- `ActionRecord` датаклас зі скріншотами до/після
- `ActionRecorder` singleton з автозаписом
- Запис у `logs/gui_actions.jsonl`
- Ліміт: 500 записів / 7 днів
- Декоратор `@recordable(action_type)`

#### Перегляд та експорт
- `get_recent_actions(count)` / `search_actions(filter)`
- `export_session_log(format)` — JSON або text
- `generate_action_report()` — статистика по діях

### 6.2 Модуль `core_undo_manager.py` — Система відкату дій 

**Файл:** `functions/core_undo_manager.py` (~550 рядків)

#### Snapshots
- `StateSnapshot` — скріншот, кліпборд, активне вікно, позиція миші
- `save_snapshot(label)` / `restore_snapshot(id)`
- `list_snapshots()` / `SnapshotContext` менеджер

#### Undo логіка
- `undo_last(count)` — відкат N дій
- `undo_to_snapshot(id)` — відкат до snapshot
- Handlers: `mouse_click`, `keyboard_type`, `file_move`, `fill_form`
- `irreversible` прапорець для незворотних дій

### 6.3 Модуль `core_gui_guardian.py` — Захист від небезпечних дій 

**Файл:** `functions/core_gui_guardian.py` (~450 рядків)

#### Рівні ризику
- `GUIRiskLevel`: LOW / MEDIUM / HIGH / CRITICAL
- `assess_risk(action, params)` → оцінка ризику
- `is_action_allowed(action, params)` → перевірка

#### Sandbox
- `enable_sandbox_mode(region, apps)` — whitelist/blacklist
- `set_allowed_region(x, y, w, h)` — географічні обмеження
- `set_allowed_applications(apps)` — дозволені програми

#### Preview та Simulation
- `preview_action(action, params)` — текстовий опис
- `simulate_action(action, params)` — сухий прогін
- `get_safety_report()` — звіт про безпеку
- Декоратор `@guarded(action_name)`

### 6.4 Оновлення TOOL_POLICIES 

- Додано 20+ інструментів Phase 6
- Рівні ризику: SAFE для аналізу, CONFIRM_REQUIRED для відкату/змін

### 6.5 Тести Phase 6

- [ ] `tests/test_core_action_recorder.py` (**ТРЕБА** — дублюється у 2.3)
- [ ] `tests/test_core_undo_manager.py` — undo для введення тексту, переміщення файлів (**ТРЕБА**)
- [ ] `tests/test_core_gui_guardian.py` — блокування небезпечних дій (**ТРЕБА**)

---

## 📚 Phase 7: Навчання, Адаптація, Профілі програм, Макроси

**Статус:** 🟡 Фундамент у роботі | **Пріоритет:** 🟡 Середній | **Термін:** 4–6 тижнів

**Мета:** Агент вчиться зі свого досвіду — запам'ятовує успішні шляхи, будує профілі програм, автоматизує повторювані задачі через макроси. Це база для Phase 8 (автономія) та Phase 9 (оркестрація).

### 7.1 Модуль `core_app_profile.py` — Профілі програм

- [ ] `AppProfile` клас: `{app_name, exe_path, known_elements, common_shortcuts, workflows}`
- [ ] Вбудовані профілі для: Notepad, Paint, Explorer, Calculator, Chrome, Word, Excel
- [ ] `learn_from_interaction(app_name, action, result)` — доповнення профілю з досвіду
- [ ] `get_profile(app_name)` → `AppProfile`
- [ ] `save_profiles()` / `load_profiles()` — збереження в `app_profiles.json`
- [ ] `generate_profile_from_observation(hwnd)` — автоматично вивчити програму

### 7.2 Модуль `tools_macro_recorder.py` — Запис та відтворення макросів

#### Запис
- [ ] `start_recording(macro_name)` — почати запис дій користувача
- [ ] `stop_recording()` → `Macro` — зупинити та повернути записаний макрос
- [ ] `pause_recording()` / `resume_recording()` — пауза в записі
- [ ] `add_comment_to_recording(text)` — додати коментар до кроку

#### Макроси
- [ ] `Macro` клас: `{name, description, steps: [MacroStep], variables}`
- [ ] `MacroStep` клас: `{action, params, delay, verify, on_fail: "skip"|"abort"|"retry"}`
- [ ] `save_macro(macro, path)` — зберегти в JSON-файл
- [ ] `load_macro(path)` → `Macro`
- [ ] `list_macros()` → `[{name, description, path}]`

#### Відтворення
- [ ] `play_macro(macro_name_or_path, variables={})` → `{success, steps_completed, error}`
- [ ] `play_macro_step_by_step(macro)` — покроково з підтвердженням
- [ ] `validate_macro(macro)` → `{valid, warnings, errors}` — перевірка без виконання

### 7.3 Модуль `logic_task_learner.py` — Навчання на сценаріях

- [ ] `TaskPattern` — шаблон повторюваної задачі
- [ ] `detect_repeated_pattern(action_history)` → `TaskPattern | None` — розпізнати повтор
- [ ] `suggest_automation(pattern)` → `str` — запропонувати автоматизацію
- [ ] `create_macro_from_pattern(pattern)` → `Macro` — автоматично створити макрос
- [ ] `adaptive_click(description, fallback_list)` → `bool` — якщо перший варіант не спрацював, пробує наступні
- [ ] `remember_successful_path(goal, actions)` — запам'ятати успішний шлях
- [ ] `recall_path(goal)` → `[action] | None` — згадати перевірений шлях

### 7.4 Планувальник задач

- [ ] `schedule_task(task_description, time_or_trigger)` — запланувати задачу
- [ ] `list_scheduled_tasks()` → `[{id, description, schedule, status}]`
- [ ] `cancel_scheduled_task(task_id)` → `bool`
- [ ] Тригери: час (`"09:00"`), подія (`"on_file_change"`), інтервал (`"every 1h"`)

### 7.5 Тести Phase 7

- [ ] `tests/test_core_app_profile.py`
- [ ] `tests/test_core_macro.py` — mock запис та відтворення
- [ ] `tests/test_logic_task_learner.py` — синтетична history, перевірка pattern detection

---

## 🤖 Phase 8: Автономія — довгі watcher-сесії (3–6 годин)

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🔴 Високий | **Термін:** 4–6 тижнів

**Мета:** Агент може **самостійно працювати годинами**, чекаючи подій і продовжуючи ланцюжок дій без втручання користувача. Це критично для делегування іншим ШІ (див. Phase 9) та будь-яких довгих pipeline-ів.

**Приклад use-case:** «Протягом 6 годин давай Windsurf по черзі такі задачі: 1) додати тести, 2) виправити lint, 3) зробити PR. Після кожної — перевірити CI, відправити наступну.»

### 8.1 Модуль `logic_watcher.py` — Watcher engine

- [ ] `Watcher` клас: `{condition_fn, action_fn, poll_interval, max_duration, max_iterations}`
- [ ] `start_watcher(watcher)` → неблокуючий запуск у окремому треді/процесі
- [ ] `stop_watcher(watcher_id)` — коректна зупинка
- [ ] `list_active_watchers()` → `[{id, task, running_for, last_action}]`
- [ ] Вбудовані conditions:
  - [ ] `condition_file_changed(path)`
  - [ ] `condition_process_finished(pid)`
  - [ ] `condition_window_title_contains(pattern)`
  - [ ] `condition_chat_idle(chat_provider, idle_seconds)` — інший ШІ закінчив відповідь
  - [ ] `condition_url_response_contains(url, pattern)` — CI/GitHub перевірка

### 8.2 Бюджет та безпека автономних сесій

- [ ] `SessionBudget` dataclass: `{max_steps, max_tokens, max_duration_hours, max_api_cost_usd}`
- [ ] Жорсткі ліміти на кількість дій, tokens, час — зупинка + summary.
- [ ] `core_gui_guardian` обов'язково бере дозвіл на руйнівні дії, навіть в автономі.
- [ ] Emergency kill-switch: гаряча клавіша або файл-маркер `/tmp/marc-stop`.

### 8.3 Персистентність довгих сесій

- [ ] Стан watcher-а зберігається у `logs/watchers/{id}.jsonl` (append-only).
- [ ] Можна reconnect-итися після краху / перезавантаження.
- [ ] `resume_watcher(id)` — продовжити з останньої точки.

### 8.4 Тести Phase 8

- [ ] `tests/test_logic_watcher.py` — синтетичні condition/action, перевірка циклу + таймаутів.
- [ ] `tests/test_session_budget.py` — зупинка при досягненні лімітів.

---

## 🎭 Phase 9: Оркестрація інших ШІ (AI Conductor)

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🔴 Високий | **Термін:** 6–8 тижнів

**Мета:** Агент виступає **диригентом**: делегує задачі спеціалізованим ШІ (Windsurf, Cursor, Claude Code, GPT-коду, локальні моделі), моніторить їх, формулює наступні промпти. Разом із Phase 8 дає: «відправив та забув на 6 годин — отримав готовий PR».

### 9.1 Модуль `logic_ai_adapter.py` — Уніфіковані адаптери

- [ ] Абстрактний клас `AIProvider`: `{send(prompt, context) → response, stream(prompt), health_check() → bool}`
- [ ] HTTP-адаптери:
  - [ ] `OpenAIAdapter` (OpenAI, OpenRouter, LM Studio, Ollama)
  - [ ] `AnthropicAdapter` (Claude)
  - [ ] `GoogleAdapter` (Gemini)
- [ ] Browser-адаптери (через Playwright, див. трек E2):
  - [ ] `WindsurfBrowserAdapter` — локальний Windsurf IDE через accessibility API / браузер
  - [ ] `CursorBrowserAdapter`
  - [ ] `ChatGPTWebAdapter`
  - [ ] `ClaudeWebAdapter`
- [ ] `ProviderRegistry` — вибір провайдера за capability (coding/vision/long-context).

### 9.2 Модуль `logic_orchestrator.py` — Декомпозиція та делегування

- [ ] `decompose_task(goal)` → `[SubTask]` (де кожна підзадача має `preferred_provider`)
- [ ] `delegate(subtask, provider)` → `Response` (через adapter)
- [ ] `aggregate(responses)` → фінальний результат
- [ ] Fallback: якщо основний провайдер fail — повторити через резервний.
- [ ] Паралельне делегування (N провайдерів одночасно, беремо найкращу відповідь).

### 9.3 Моніторинг зовнішніх ШІ (через Phase 8 Watcher)

- [ ] `watch_chat_for_completion(provider, chat_id)` — чекає «готово» і повертає текст.
- [ ] `continue_conversation(provider, chat_id, next_prompt)` — продовжує у тому ж чаті.
- [ ] Детекція різних станів: `busy`, `idle`, `error`, `rate_limited`, `auth_expired`.

### 9.4 Безпека оркестрації

- [ ] API-ключі тільки з `.env` / keyring, НІКОЛИ в коді.
- [ ] Per-provider rate-limits.
- [ ] Redaction PII у промптах, що йдуть у хмару.
- [ ] Audit log: хто кого про що питав.

### 9.5 Тести Phase 9

- [ ] `tests/test_logic_ai_adapter.py` — моки HTTP/browser.
- [ ] `tests/test_logic_orchestrator.py` — декомпозиція + делегування.
- [ ] `tests/test_ai_provider_registry.py` — вибір провайдера за capability.

---

## 🌈 Phase 10: Універсальні домени (task-agnostic)

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🟡 Середній | **Термін:** постійно (drip-in)

**Мета:** Реалізація принципу **«агент має виконати будь-яку задачу»** через додавання доменних інструментів. Нарощується інкрементально.

### 10.1 Домен: Фото / відео редагування

- [ ] `tools_image_pillow.py` — базові фільтри, crop, resize, формати (без GUI).
- [ ] `tools_image_photoshop.py` — через COM/Photoshop Scripting (якщо встановлено).
- [ ] `tools_image_gimp.py` — через Script-Fu / batch mode.
- [ ] `tools_video_ffmpeg.py` — обгортка над ffmpeg (cut, concat, rescale, extract frames).

### 10.2 Домен: AI-генерація (Stable Diffusion / ComfyUI)

- [ ] `tools_comfyui.py` — HTTP API до локального ComfyUI (`/prompt`, `/view`).
- [ ] `tools_a1111.py` — AUTOMATIC1111 API.
- [ ] `tools_ollama.py` — локальні LLM + vision моделі.
- [ ] Автоматичне встановлення: агент вміє запустити інсталятор ComfyUI та завантажити моделі (за дозволом).

### 10.3 Домен: Офіс / документи

- [ ] `tools_word.py` (вже намічено в додатках) — через `win32com.client`.
- [ ] `tools_excel.py` — читання/запис комірок, формули, pivot.
- [ ] `tools_pdf.py` — merge, split, OCR (pdfplumber + pytesseract).

### 10.4 Домен: Браузерна автоматизація

- [ ] `tools_browser.py` — Playwright (див. трек E2). Спільна база для Phase 9 browser-адаптерів.
- [ ] Сценарії: Gmail, Google Docs, Notion, Jira.

### 10.5 Домен: Системне адміністрування

- [ ] `tools_installer.py` — winget/choco/apt запуск з підтвердженням.
- [ ] `tools_service_manager.py` — Windows services, systemd (за наявності WSL).
- [ ] `tools_network.py` — ping/curl/DNS checks.

### 10.6 Тести Phase 10

- [ ] По-доменні, drip-in: додаємо разом із кожним новим інструментом.

---

## 🚀 Phase 11: Autonomous Task Orchestrator (верхній рівень автономії)

**Статус:** ✅ **Скелет готовий** (PR #13) | **Пріоритет:** 🔴 Критичний | **Термін:** 20.04.2026

**Мета:** Дати **єдиний верхній рівень**, який дозволяє сказати агенту «виконай усі задачі з цього файлу й дай звіт» — і він реально їх виконує, використовуючи всі примітиви з Phase 1–10. Це те, що перетворює набір модулів на `autopilot`.

**Ключовий сценарій (приклад користувача):**
> «Виконай усі задачі по файлу status.md. На питання про запуск команд давай дозвіл, якщо це стосується поточного проекту й не шкодить ПК. По закінченні задай в Windsurf рефакторинг пройти 3 рази. По пунктах створиш звіт по кожному виконанню тезисно із часом виконання.»

Phase 11 = `TaskRunner` + `PermissionGate` + `ExecutionReport` + формат плану + інтеграція з усім, що вже побудовано.

### 11.1 `functions/logic_task_runner.py` — TaskRunner

- [ ] **Типи:** `Task` (dataclass з `id`, `name`, `kind`, `params`, `on_error`, `depends_on`), `Plan` (упорядкований список `Task`-ів + метадані), `StepResult`.
- [ ] **`TaskRunner.run(plan, budget=None, gate=None, report=None)`** — послідовне виконання; на `on_error=stop/skip/retry`, на watcher-like умовах — чекання; автоматичне оновлення `SessionBudget`/`ExecutionReport`.
- [ ] **Kind-и (handler-реєстр):**
  - `run_command` — subprocess з PermissionGate.
  - `edit_file` / `write_file` / `read_file` — файлові операції.
  - `call_provider` — `ProviderRegistry.chat()` з промптом.
  - `delegate_to_windsurf` / `delegate_to_cursor` — через J4 (browser-адаптер).
  - `watch_until` — крутить `Watcher` з конкретним condition'ом, блокується до спрацьовування або budget-ліміту.
  - `sub_plan` — рекурсивний `TaskRunner` (ієрархія підзадач).
  - `sleep` / `noop` / `log` — службові.
- [ ] **Формат плану (JSON за замовчуванням):**
  ```json
  {
    "name": "refactor-and-delegate",
    "tasks": [
      {"id": "t1", "kind": "run_command", "params": {"cmd": "pytest -q"}},
      {"id": "t2", "kind": "call_provider", "params": {"prompt": "Підсумуй результат t1", "registry": "default"}, "depends_on": ["t1"]},
      {"id": "t3", "kind": "delegate_to_windsurf", "params": {"prompt": "Refactor as discussed", "times": 3}},
      {"id": "t4", "kind": "noop", "params": {"note": "done"}}
    ]
  }
  ```
- [ ] **markdown-план** (через окремий `logic_plan_parser.py`): секції `### N. Назва` → `run_command`-crud із блоків ` ```bash … ``` `.
- [ ] **Дефолти:** `on_error="stop"`; `project_root` = cwd; звіт у `logs/reports/run_{timestamp}.md`.

### 11.2 `functions/logic_permission_gate.py` — PermissionGate

- [ ] **`PermissionRequest(action, resource, reason, metadata)`** + `Decision(allow, persist, note)`.
- [ ] **Policy stack (виконується в порядку):**
  1. **Always-deny** (regex / patterns): `rm -rf /`, `sudo *`, `:(){:|:&};:`, запис у `/etc`, `/System`, `C:\Windows\System32\...`, мережеве з'єднання з привілейованих портів.
  2. **Always-allow whitelist:** git status/diff/log/branch, `ls`, `cat`, `python -m pytest`, `ruff check`, і будь-що повністю в `project_root`.
  3. **Per-session-allow cache:** користувач уже дозволив цю дію в цій сесії → повторно не питати.
  4. **Ask-user** через callback `ask_fn(request) -> Decision`. У тестах — мок. У прод — GUI-попап (core_gui-тред).
- [ ] **Persistent allow-list** (опційно): JSON-файл `~/.marc/permissions.json` з записами, які юзер погодив «назавжди для цього типу дії».
- [ ] **`check(action, resource)`** повертає `Decision` без викликів зовнішніх систем (чистий helper).

### 11.3 `functions/logic_execution_report.py` — ExecutionReport

- [ ] **`StepReport`** (`task_id, task_name, status, started_at, finished_at, duration_s, summary, stdout_tail, error, cost_usd, tokens`).
- [ ] **`ExecutionReport`:** `record(step)`, `add_event(msg)`, `to_markdown()`, `to_json()`, `to_text()` (компактний формат тезами з таймінгами), `save(path)`.
- [ ] **Формат markdown за замовчуванням:**
  ```markdown
  # Звіт виконання: refactor-and-delegate
  Початок: 2026-04-20 21:00:00 | Кінець: 2026-04-20 23:15:42 | Тривалість: 2h 15m 42s

  ## 1. Запуск тестів (run_command) ✅
  - Час: 21:00:00 → 21:03:20 (3m 20s)
  - `pytest -q`: 270 passed
  - ---
  ## 2. Підсумок від LM Studio (call_provider) ✅
  - Час: 21:03:22 → 21:03:45 (23s)
  - Tokens: 1450 prompt / 320 completion | Cost: $0.00
  - Summary: «Усі тести пройшли, лишились 2 DeprecationWarning в tests/test_core_memory.py»
  - ---
  ## 3. Windsurf — рефакторинг × 3 (delegate_to_windsurf) ⚠️
  - Спроба 1: 21:04 → 21:42 (38m) — виконано
  - Спроба 2: 21:45 → 22:18 (33m) — виконано
  - Спроба 3: 22:20 → 23:15 (55m) — **timeout** (budget exhausted)
  ```
- [ ] Автоматичне додавання `SessionBudget.snapshot()` та `ProviderRegistry.describe_all()` у `footer`.

### 11.4 Інтеграція з існуючими примітивами

- [ ] `Task.kind="watch_until"` викликає `Watcher` (Phase 8 / I1).
- [ ] `Task.kind="call_provider"` викликає `ProviderRegistry.chat()` (Phase 9 / J2).
- [ ] Усі task-и інкрементують лічильники `SessionBudget` (Phase 8 / I2) — kill-switch на 3–6 год працює *весь plan*, не окремі кроки.
- [ ] `PermissionGate` — прошарок ПЕРЕД subprocess / writefile / HTTP, незалежно від того, хто його викликав.
- [ ] GUI (Phase 7+): вкладка «План» для перегляду прогресу `ExecutionReport` у реальному часі — буде в окремому PR після MVP.

### 11.5 Тести Phase 11

- [ ] `tests/test_logic_task_runner.py` — виконання простих плану (10+ тестів).
- [ ] `tests/test_logic_permission_gate.py` — allow/deny/ask-cache (15+ тестів, всі з mock `ask_fn`).
- [ ] `tests/test_logic_execution_report.py` — запис / markdown-форматування / save (10+ тестів).

### 11.6 Поведінкові гарантії

| Гарантія | Механізм |
|---|---|
| Небезпечна команда → ВІДМОВА | `PermissionGate.always_deny` патерни |
| Локальна безпечна команда → без питань | `PermissionGate.always_allow` + `project_root` |
| Невідома команда → питаєм юзера | `ask_fn(request)` callback |
| План падає на одному кроці → не губимо звіт | `ExecutionReport` автосейв після кожного step-а |
| Budget вичерпано → негайна зупинка | `SessionBudget.should_stop()` перед кожним task-ом |
| Результат делегації (Windsurf × 3) → структурований лог | `StepReport` містить метадані кожної спроби |

---

## 🧠 Phase 11.5: Plan-critic LLM (самокритика плану перед виконанням)

**Статус:** ✅ **Злито** (PR #18) | **Пріоритет:** 🔴 Високий | **Термін:** 20.04.2026

**Мета:** Додати **meta-рівень оцінки плану в цілому**, а не лише per-call
через `TOOL_POLICIES` / `PermissionGate`. Це той «другий LLM-голос», який
дивиться на весь план і каже:

- `approve` — план виглядає безпечним і розумним,
- `concerns` — є ризики (список з `severity: info/warn/block`), але план можна виконати з обережністю,
- `redo` — план треба переписати; повертається `suggested_changes` для репланера.

Підвищує успішність планів на ~20–30% (за вимірюваннями Plan-Critic агентів у GUI-Thinker / UFO).

### 11.5.1 `functions/logic_plan_critic.py` — PlanCritic

- [x] **`PlanCritic(provider_registry)`** — тонкий wrapper над `ProviderRegistry.chat()`
  з dedicated `critic_system_prompt` і JSON-parser відповіді.
- [x] **`review(plan) -> CritiqueResult(verdict, concerns[], usage, raw_text)`**,
  де `verdict ∈ {"approve", "concerns", "redo"}`.
- [x] **Stability guard:** якщо `verdict=approve`, але серед `concerns` є
  `severity=block` — автоматично перетворюється на `redo` (не довіряємо LLM,
  який сам себе суперечить).
- [x] **Парсер стійкий до fenced ```json, prose-вкраплень, invalid JSON**
  (fallback → `verdict=concerns` з оригінальним текстом у `concerns[0]`).

### 11.5.2 `review_and_run_plan(plan, runner, critic, replan_fn=None)` — full-cycle helper

- [x] Крок 1: `critic.review(plan)`.
- [x] Крок 2: якщо `verdict="redo"` і є `replan_fn` → викликати `replan_fn(plan, concerns)` →
  отримати новий `plan` → **повторити review** (один раз, без infinite loop).
- [x] Крок 3: після фінального `approve` / `concerns` → `runner.run(plan)`.
- [x] Крок 4: у звіт додається блок `plan_critic` з verdict-ом і concerns-ами.

### 11.5.3 Інтеграція

- [x] Підключається **опційно** (`TaskRunner.run(plan, critic=None)`) —
  не ламає існуючий потік, коли critic не переданий.
- [ ] Інтеграція в `core_planner` — щоб кожен згенерований planner-ом план
  автоматично проходив через PlanCritic перед `core_executor`. **Заплановано в окремому PR.**

### 11.5.4 Тести

- [x] `tests/test_logic_plan_critic.py` — 38 тестів: парсер, stability guard, happy path,
  network error, malformed JSON, `review_and_run_plan` з/без `replan_fn`, autoescalate block-severity.

---

## 🎯 Phase 12.1: Step-Check / Actor-Critic MVP (`Task.precheck` / `Task.expect`)

**Статус:** ✅ **Злито** (PR #18) | **Пріоритет:** 🔴 Високий | **Термін:** 20.04.2026

**Мета:** Зробити кожен крок `Task`-а **перевіряємим**: до запуску (`precheck`)
та після (`expect`). Це переносить MARK з моделі «виконав — повірили» у
модель **Actor-Critic** (запозичена з GUI-Thinker / UFO):

- **Step-Check (before):** «якщо стан світу не той, який потрібен — не запускаємо handler взагалі, це заощаджує час і ресурси». `precheck_failed`.
- **Actor-Critic (after):** «handler може кричати *я успішний!*, але якщо очікуваний стан не досягнуто — це провал». `expect_failed`.

Обидва поля — **опційні** (backward-compatible: без них Task поводиться як раніше).

### 12.1.1 `functions/logic_expectations.py` — Evaluator-registry

- [x] **10 вбудованих evaluator-ів:**
  `file_exists`, `file_missing`, `stdout_contains`, `stderr_contains`,
  `return_code`, `window_title_contains`, `process_running`,
  `process_not_running`, `no_error_in_report`, `ok_count_at_least`.
- [x] **Розширюваний registry:** `runner.expect_registry.register(kind, fn)`.
- [x] **Evaluator-результат:** `ExpectResult(kind, ok, details, elapsed_s)`.

### 12.1.2 Розширення `Task` (у `logic_task_runner.py`)

- [x] **`Task.precheck`** (`Expectation | list[Expectation] | None`) — обчислюється **до** handler-а.
- [x] **`Task.expect`** (`Expectation | list[Expectation] | None`) — обчислюється **після** handler-а.
- [x] **Нові статуси в `ExecutionReport`:**
  `STATUS_PRECHECK_FAILED`, `STATUS_EXPECT_FAILED`.
- [x] **`metadata.expect_results`:** повний лог перевірок у `StepReport`
  (для майбутнього repair loop у 12.2).

### 12.1.3 Поведінка з `on_error="retry"`

- [x] Невдала перевірка **автоматично тригерить retry** (handler запускається знову).
  Тест `test_expect_with_retry_succeeds_second_attempt`: файл зʼявляється лише
  на 2-й спробі → task завершується `ok` на 2-му циклі.

### 12.1.4 Тести

- [x] `tests/test_logic_expectations.py` — 27 тестів evaluator-ів (per-kind + registry).
- [x] `tests/test_logic_task_runner_expect.py` — 12 тестів інтеграції
  (precheck blocking, expect failure, retry-loop, multi-expectation AND-логіка).

---

## 🔧 Phase 12.2: LLM repair loop на `expect_failed` (повний Actor-Critic цикл)

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🟡 Середній | **Термін:** наступний спринт

**Мета:** Коли `expect` не пройшов — замість механічного retry, запустити
**LLM-repair**: планер дивиться на `metadata.expect_results` (який саме очікуваний
стан не досягнуто), на `stdout_tail`, на попередні кроки — і **переписує наступні
кроки плану**, щоб досягти мети.

### План

- [ ] **`TaskRunner.on_expect_failed_hook`** — callback, який отримує `(plan, failed_step, expect_results)` і повертає `Plan` (новий план починаючи з поточного step-а).
- [ ] **`logic_step_repair.py`** — дефолтна реалізація hook-а: формує промпт із попереднього плану + помилки + результатів перевірок → `ProviderRegistry.chat()` → `safe_json_loads` → новий `Plan`.
- [ ] **Budget guard:** `SessionBudget.repair_attempts_left` — щоб уникнути нескінченного циклу «план → провал → LLM-repair → новий план → провал → ...».
- [ ] **Тести:** `test_step_repair.py` — happy path, network error, malformed plan, budget exhausted.

Залежить від Phase 12.1 (метадані `expect_results` у `StepReport`).

---

## 🚀 Phase 13: Universal Task Executor (UTE) — «ТЗ → агент виконав»

**Статус:** 🔴 Не розпочато (цей документ — план) | **Пріоритет:** 🔴 Найвищий після Phase 12.3/12.4 | **Термін:** S6–S12 (~3 місяці)

**Мета:** Перехід від «чат-агента з інструментами» до **goal-driven executor-а**: користувач дає вільне ТЗ — агент сам декомпозує, обирає інструменти/ШІ/додатки, виконує, валідує результат, звітує.

**Чому це окрема Phase, а не продовження Phase 11:** Phase 11 дав **інфраструктуру виконання** (TaskRunner, PlanCritic, expect, budget). Phase 13 додає **шар зверху** — intake вільного ТЗ, маршрутизацію між доменами, квотинг, batch-примітиви, вузькі актори для зовнішніх ШІ, domain-validators, dashboard. Це 7–9 модулів, які окремо один від одного не дають цінності, але разом перетворюють агент з «набору тулів» на «виконавця завдань».

### Цільові use-cases (що має запрацювати)

1. **Кодинг:** «Напиши CRUD для таблиці User у моєму Django-проекті. Codex поки є ліміт, далі Windsurf. Всі команди дозволяй.»
2. **Batch-фото:** «Прогнати всі фото з `D:/photos/in/` через workflow `upscale_2x.json`, скинути в `D:/photos/out/`.»
3. **Презентація:** «Зробити 10-слайдову презентацію про Phase 13 за нашим `status.md`, зберегти у `.pptx`.»
4. **Мікс:** «Рефакторинг модуля X: Codex draft → Windsurf review → pytest. Якщо щось провалиться — ChatGPT-web за advice.»
5. **Research + doc:** «Знайти 5 статей про RAG за 2025, зробити summary-markdown з цитатами.»

### Потік виконання

```
User ТЗ (free-form text)
    │
    ▼
[13.1 Task Intake]         LLM парсить → TaskSpec + clarification Qs
    │
    ▼
[13.2 Resource Router]     TaskSpec → Pipeline (code / photo / doc / web / mixed)
    │
    ▼
[13.3 Quota Tracker]       Перевіряє залишок квот AI (Codex/GPT/Claude/…)
    │
    ▼
[13.4 Pipeline.compile()]  → Plan (список Task, враховує quota fallback)
    │                          ↑ (PlanCritic ревізує — PR #21)
    ▼
[13.5 TaskRunner.run()]    Виконання + нові handler-и (codex_call,
    │                      windsurf_actor, comfyui_workflow, batch_task, …)
    │
    ▼
[13.6 Cross-AI Actors]     Делегування у Codex/Cursor/ChatGPT-web/Claude-web
    │
    ▼
[13.7 Output Validators]   Per-domain: validate_code / validate_photo / …
    │                          ↑ (викликається з Task.expect — PR #18)
    ▼
[13.8 Task Dashboard GUI]  Live progress, milestone bar, kill-switch
    │
    ▼
[13.9 Checkpoint / Resume] logs/tasks/{id}/checkpoint.json
    │
    ▼
[13.10 Post-execution Report]  Markdown summary: goal, time, cost, outputs
```

### 13.1 Task Intake — «ТЗ → TaskSpec»

**Модуль:** `functions/core_task_intake.py`

**Задача:** розпарсити вільний текст ТЗ у структурований `TaskSpec`, запитати уточнення якщо неоднозначно.

**TaskSpec:**
```python
@dataclass
class TaskSpec:
    goal: str                          # «написати CRUD»
    deliverables: list[str]            # ["models.py", "views.py", "tests"]
    constraints: list[str]             # ["Django ORM", "pytest", "без зміни DB schema"]
    domain: str                        # code | photo_batch | presentation | web | mixed
    domain_sub: str                    # django | react | …
    preferred_ai_order: list[str]      # ["codex", "windsurf", "gpt-4o-mini"]
    permission_mode: str               # confirm_each | auto_read | auto_all
    budget: BudgetHints                # max_hours, max_cost_usd, max_ai_calls
    input_files: list[Path]            # з аттачментів / згадок «D:/photos/in/»
    output_dir: Path | None
    raw_tz: str                        # збережене ТЗ як є
```

**Алгоритм:**
1. LLM (з `ProviderRegistry`) отримує промпт: `ТЗ + enum доступних доменів + JSON-схема TaskSpec`.
2. Повертає JSON → `safe_json_loads` → `TaskSpec`.
3. Якщо якесь `required` поле `None` або `"unclear"` — задає юзеру clarification Qs (через callback `ask_user(question, options)`).
4. Записує `logs/tasks/{id}/spec.json`.

**API:**
```python
def create_task_spec_from_tz(
    tz_text: str,
    *,
    registry: ProviderRegistry,
    ask_user: Callable[[str, list[str]], str] | None = None,
) -> TaskSpec
```

**Тести:** happy path, неоднозначне ТЗ → 2 clarification Qs, порожнє ТЗ → ValueError, LLM-fallback на 2-й провайдер.

### 13.2 Resource Router — «TaskSpec → Pipeline»

**Модуль:** `functions/core_resource_router.py` + директорія `pipelines/`

**Задача:** за `TaskSpec.domain` вибрати рецепт.

**Реєстр:**
```python
PIPELINE_REGISTRY = {
    "code":          pipelines.code_pipeline,
    "photo_batch":   pipelines.photo_batch_pipeline,
    "presentation":  pipelines.presentation_pipeline,
    "web_research":  pipelines.web_research_pipeline,
    "mixed":         pipelines.mixed_pipeline,
}
```

**Pipeline protocol:**
```python
class Pipeline(Protocol):
    name: str
    def compile(self, spec: TaskSpec, quota: QuotaTracker) -> Plan: ...
    def required_tools(self, spec: TaskSpec) -> list[str]: ...  # для preflight check
```

**MVP:** реалізуємо лише **`code_pipeline`** + шаблон `mixed_pipeline`. Решта — stub (raise NotImplementedError з повідомленням «цей домен у roadmap, див. S11»).

### 13.3 Quota Tracker

**Модуль:** `functions/core_quota_tracker.py`

**Персистентність:** `~/.mark/quotas.json`
```json
{
  "codex":        {"daily_limit": 500, "used_today": 120, "reset_at_utc": "2026-04-22T00:00Z"},
  "openai_gpt4o": {"rpm_limit":  60,  "used_last_minute": 3},
  "anthropic":    {"monthly_tokens": 1_000_000, "used_this_month": 340_000},
  "windsurf_ui":  {"sessions_today": 12}
}
```

**API:**
- `can_call(provider, cost_hint) -> (ok, reason)`
- `record_call(provider, tokens, cost)`
- `reset_if_window_passed()`  ← викликається lazy при кожному check-у
- `next_available_provider(preferred_list) -> provider_id | None`

**Інтегрується з** `ProviderRegistry.chat()` — перед викликом перевіряє quota, при вичерпанні робить fallback на наступний provider з `spec.preferred_ai_order`.

### 13.4 Batch primitive

**Новий Task kind:** `batch_task`

```python
Task(
    kind="batch_task",
    params={
        "items": list_of_inputs,           # або lazy callable
        "per_item_task": Task(kind="comfyui_workflow", params={...}),  # template
        "max_parallel": 2,
        "on_item_error": "retry:2 | skip | abort",
        "progress_every": 5,
    },
    expect=ExpectSpec(min_success_ratio=0.95),
)
```

**Виконавець** (в TaskRunner) ітерує items, підставляє кожен у template, викликає `_handle_task` рекурсивно, агрегує StepReport-и у `BatchReport`, пише прогрес у логи + callback (для GUI progress bar).

### 13.5 Нові task kinds і handler-и

| Kind | Handler | Для чого |
|---|---|---|
| `codex_call` | `tools_codex_actor.py` | API виклик Codex / OpenAI code-моделі |
| `windsurf_actor` | `tools_windsurf_actor.py` | Написати у Windsurf + прочитати відповідь (extension PR #23 watcher) |
| `cursor_actor` | `tools_cursor_actor.py` | Cursor через Playwright CDP |
| `chatgpt_browser` | `tools_chatgpt_browser.py` | chat.openai.com через Playwright |
| `claude_browser` | `tools_claude_browser.py` | claude.ai через Playwright |
| `comfyui_workflow` | `tools_comfyui.py` | POST до `http://localhost:8188` з workflow JSON |
| `pillow_edit` | `tools_pillow.py` | Batch-резайз/фільтри через Pillow (для простих photo задач без ComfyUI) |
| `ppt_action` | `tools_powerpoint.py` | `pywin32` до PowerPoint / python-pptx |
| `batch_task` | вбудовано у TaskRunner | цикл + агрегація |

### 13.6 Cross-AI Delegation («AppAgents»)

Різниця з Phase 12.5 (Windsurf Watcher): **watcher = passive (читає),  actor = active (пише)**.

Actor-API:
```python
class AIActor(Protocol):
    def send_prompt(self, prompt: str, *, timeout: float) -> str: ...
    def health_check(self) -> bool: ...
    def quota_cost(self, prompt: str) -> dict: ...
```

Реалізації:
- `CodexActor` — HTTPS API, найдешевше, лімітоване
- `WindsurfActor` — OCR-read + click+type у UI; повільне, але без лімітів
- `ChatGPTBrowserActor` — Playwright CDP до `chat.openai.com` з залогіненим профілем
- `ClaudeBrowserActor` — так само до `claude.ai`
- `CursorActor` — Playwright до локального Cursor

**Ризик:** залогінені сесії — великий attack surface. Credentials не зберігаємо у репо; Playwright використовує окремий Chrome-профіль у `~/.mark/browser_profile/`.

### 13.7 Output Validators

**Модуль:** `functions/validators/`

- `validate_code(path, *, tests_run=True, lint=True) -> ValidationReport`
- `validate_photo(path, *, min_size_kb=100, expected_dims=None, no_black_frames=True)`
- `validate_presentation(path, *, min_slides=5, has_titles=True)`
- `validate_markdown(path, *, min_words=200, has_headings=True)`

Викликаються з `Task.expect.custom_validator="validators.validate_code"`.

### 13.8 Task Dashboard GUI

Нова вкладка **«Task»** у `run_assistant.py` (міксин `task_tab.py`).

Елементи:
- Textarea «Опис задачі (ТЗ)»
- Attachments (input files)
- Кнопки: **Run** / **Pause** / **Stop (hard)**
- Milestone progress bar (заповнюється з `BatchReport.progress`)
- Live `StepReport` stream (scrollable)
- Permission checkbox: «Дозволити всі команди без підтвердження» (warning-іконка)

Залежить від **V4 / Phase 12.3** (GUI-інтеграція TaskRunner — базова кнопка «Виконати план»).

### 13.9 Checkpoint / Resume

Формат checkpoint-а:
```
logs/tasks/{task_id}/
├── spec.json               # TaskSpec
├── plan.json               # compiled Plan
├── step_reports.jsonl      # append-only кожен StepReport
├── batch_progress.jsonl    # для batch_task item-рівень
└── checkpoint.json         # current_step_index + context + quota state
```

`resume_task(task_id)`:
1. Читає `plan.json` + `checkpoint.json`
2. Перестворює TaskRunner з `context` з checkpoint
3. Пропускає виконані step-и (по `step_reports.jsonl`)
4. Продовжує з `checkpoint.json.next_step_index`

### 13.10 Post-execution Report

`functions/core_task_report.py` → `generate_markdown_report(task_id) -> str`

Структура:
```markdown
# Task Report: <goal>
**Task ID:** abc123
**Duration:** 43 min
**Status:** ✅ Completed / ⚠️ Partial / ❌ Failed

## Milestones
1. ✅ Codex CRUD skeleton (3 min, $0.12, 3 AI calls)
2. ✅ Django migrations (45s)
3. ✅ Windsurf refactor (15 min, 1 delegation)
4. ✅ pytest — 7/7 passed (2 min)

## Outputs
- `apps/users/models.py` (+45 LoC)
- `apps/users/views.py` (+78 LoC)
- ...

## Issues
- Codex quota 500→397 (still OK)
- pytest WARNING: deprecated `django.conf.urls.url`

## Next Steps Suggested
- [ ] Оновити URL routing до path()
- [ ] Додати permissions class

## Audit trail
→ `logs/tasks/abc123/step_reports.jsonl`
```

---

### Приклади повних flow

#### Приклад 1 — «Django CRUD» (код + Codex + Windsurf)

**ТЗ:** _«Напиши CRUD для таблиці User у моєму Django-проекті. Codex поки є ліміт, далі Windsurf. Всі команди дозволяй.»_

1. **13.1 Intake** → `TaskSpec(domain="code", domain_sub="django", preferred_ai_order=["codex","windsurf_actor","gpt4o"], permission_mode="auto_all", budget=BudgetHints(max_hours=3))`
2. **13.2 Router** → `code_pipeline`
3. **13.3 Quota** → Codex: 380/500 today → OK для 5 викликів
4. **13.4 compile()** → Plan:
   ```
   T1 codex_call     prompt="generate Django CRUD for table User"  → files[]
   T2 shell          "./manage.py makemigrations && migrate"       expect: rc==0
   T3 windsurf_actor prompt="refactor views to ListAPIView"
                     (PR #23 Watcher читає відповідь)
   T4 shell          "pytest apps/users/"                           expect: ok_count>=5
   T5 [on_expect_failed hook] → Phase 12.2 repair loop
   ```
5. **13.5 Runner**: виконує; PlanCritic каже approve; SessionBudget дивиться 3h
6. **13.7 Validators**: `validate_code(apps/users/models.py, lint=True, tests=True)`
7. **13.10 Report:**
   ```
   ✅ Django User CRUD | 43 min | Codex calls: 3 ($0.12) | Windsurf: 1
   Files: apps/users/{models,views,serializers,tests}.py
   Tests: 7 passed | Lint: clean | Next: оновити до path()
   ```

#### Приклад 2 — «100 фото у ComfyUI»

**ТЗ:** _«Прогнати всі фото з `D:/photos/in/` через workflow `upscale_2x.json`, скинути в `D:/photos/out/`.»_

1. **13.1 Intake** → `TaskSpec(domain="photo_batch", input_dir="D:/photos/in", output_dir="D:/photos/out", extra={"workflow":"upscale_2x.json"}, budget=BudgetHints(max_hours=8))`
2. **13.2 Router** → `photo_batch_pipeline`
3. **13.4 compile()**:
   ```
   T1 shell        glob "D:/photos/in/*.{jpg,png}" → items (100 files)
   T2 batch_task   per_item=comfyui_workflow(workflow="upscale_2x.json", input=$item)
                   max_parallel=2, on_item_error="retry:2 | skip"
                   expect: min_success_ratio=0.95
   T3 shell        du -sh D:/photos/out/
   ```
4. **13.5 Runner**: progress bar 0/100 → 100/100; 2 items skip (CUDA OOM)
5. **13.7 Validators**: `validate_photo` на кожен out → 98 ok, 2 skipped
6. **13.10 Report:** _«98/100 ok, 2 skipped (CUDA OOM), total 2h 15min, disk used 1.2 GB»_

#### Приклад 3 — «Рефакторинг × 3 у Windsurf» (з Key Scenario у status.md)

**ТЗ:** _«По закінченні задач, задай у Windsurf рефакторинг пройти 3 рази. По пунктах зроби звіт по кожному виконанню тезисно із часом виконання.»_

1. **13.1 Intake** → `TaskSpec(domain="mixed", deliverables=["windsurf_refactor×3", "per-run report"])`
2. **13.2 Router** → `mixed_pipeline`
3. **13.4 compile()**:
   ```
   T1 batch_task {
     items: ["refactor_1", "refactor_2", "refactor_3"],
     per_item: windsurf_actor(prompt="пройди рефакторинг №$i")
               + windsurf_watch (PR #23) поки чат idle 3s
               + record duration
   }
   T2 markdown_report → logs/tasks/{id}/refactor_report.md
   ```
4. **13.10 Report:** _«Рефакторинг 1: 8 min 12s | 2: 6 min 40s | 3: 5 min 55s»_

---

### Послідовність реалізації (S6 → S12)

| Спринт | Задачі | Що дає в руки юзеру |
|---|---|---|
| **S6** | 13.1 Intake + 13.4 skeleton Plan compile | Перший working `ТЗ → Plan` (ще без custom handler-ів) — вже можна демонструвати |
| **S7** | 13.2 Router + `code_pipeline` MVP | Кодингова задача E2E — використовує існуючі tool-и (shell, file-edit, pytest) |
| **S8** | 13.4 `batch_task` + `photo_batch_pipeline` + `comfyui_workflow` handler | «100 фото» реально запрацює |
| **S9** | 13.3 Quota Tracker + 13.6 CodexActor + ChatGPTBrowserActor | Мікс AI з автоматичним fallback |
| **S10** | 13.7 validators + 13.10 report generator | Якісні звіти після кожного run-у |
| **S11** | `presentation_pipeline` + `ppt_action` + `web_research_pipeline` | Нові домени |
| **S12** | 13.8 Dashboard GUI + 13.9 checkpoint/resume (залежить від V4/12.3) | Повний юзер-флоу «натиснув Run і пішов спати» |

### Критерії готовності Phase 13

- [ ] 5 use-case-ів (code / photo / presentation / mixed / research) запускаються з єдиного UI-поля ТЗ
- [ ] >= 90% задач завершуються без втручання юзера (при `permission_mode="auto_all"`)
- [ ] Середній час на декомпозицію ТЗ → Plan: <30s
- [ ] Quota fallback працює без людського втручання
- [ ] Resume після краш-а продовжує з точно того самого місця
- [ ] Markdown-звіт автогенерується для кожної сесії

### Залежності на інші фази

| Залежність | Чому |
|---|---|
| Phase 11 (TaskRunner, PlanCritic, expect, budget) | ✅ вже є — фундамент |
| Phase 12.2 (repair loop) | бажано для робастного E2E |
| Phase 12.3 (GUI-інтеграція TaskRunner) | блокер для **13.8 Dashboard** |
| Phase 12.4 (checkpoint/resume інфра) | бекенд для **13.9** |
| Phase 12.5 Windsurf Watcher (PR #23) | базис для `windsurf_actor` (13.6) |
| V1 UIA (accessibility) | для стійкого `ppt_action` / ComfyUI UI-кліків |
| V2 Vision-LM | для «зрозуміти незнайомий UI» у нових доменах |
| V3 Playwright | блокер для ChatGPT/Claude browser actors (13.6) |

---

## 🔌 Додаткові модулі (паралельно з основними фазами)

### Інтеграція з браузером (Chrome/Edge)
- [ ] `tools_browser.py` — Selenium-інтеграція
  - [ ] `open_url(url)`, `navigate_back()`, `navigate_forward()`, `refresh()`
  - [ ] `find_element_by_text(text)`, `find_element_by_selector(css)`
  - [ ] `browser_type(selector, text)`, `browser_click(selector)`
  - [ ] `browser_screenshot()`, `browser_get_page_text()`
  - [ ] `browser_execute_js(code)` → результат виконання JavaScript

### Інтеграція з Office (Word, Excel)
- [ ] `tools_word.py` — через COM (`win32com.client`)
  - [ ] Відкрити / зберегти / закрити документ
  - [ ] Знайти та замінити текст, форматування абзаців
  - [ ] Вставити зображення, таблицю, заголовок

- [ ] `tools_excel.py` — через COM
  - [ ] Читання / запис комірок, рядків, стовпців
  - [ ] Застосування формул, сортування, фільтри
  - [ ] Генерація графіків, збереження як PDF

### Голосові сповіщення та індикатори
- [ ] Overlay-індикатор на екрані (прозоре вікно): "⏳ Виконую: крок 3/5"
- [ ] Спливаючі toast-сповіщення (через `win10toast` або `plyer`)
- [ ] Звукові сигнали: успіх (✅), помилка (❌), підтвердження (❓)

---

## 📊 Метрики успіху

| Метрика | Ціль | Як виміряти |
|---------|------|-------------|
| Точність кліків | > 95% | Успішні кліки / Всього кліків |
| OCR точність | > 90% | Word accuracy на тестових скріншотах |
| Детекція UI-елементів | > 85% | Знайдені / Всі елементи на тестових сторінках |
| Completion rate сценаріїв | > 80% | Успішні / Всього запусків |
| False positive безпеки | < 5% | Хибні блокування / Всього дій |
| Час відповіді (клік → результат) | < 2с | Середнє по 100 операціям |
| Undo success rate | > 70% | Успішні відкати / Всього спроб |

---

## Поточні проблеми та пріоритети (20.04.2026)

> **Критичні баги, що блокують роботу:**

### ✅ Пріоритет #1: LLM повертає пусту відповідь — **ВИРІШЕНО**
**Статус:** ✅ Проблему з LM Studio вирішено — моделі стабільно повертають відповіді

**Рішення:** Коректний формат запиту до /v1/chat/completions, правильна обробка system prompt

### ✅ Пріоритет #2: Переповнення контексту LLM (4576 > 4096 токенів) — **ВИРІШЕНО**
**Статус:** ✅ Виправлено скороченням промптів та історії

**Зміни:**
- Voice system prompt: 40 → 20 функцій (тільки пріоритетні)
- Планер: мінімальний промпт без voice system_prompt та історії
- Історія діалогу: max_messages 12→6, max_tokens 2500→1200
- Планер функції: 100+ → 35 з обрізаними описами

**Файли:** `logic_core.py`, `logic_commands.py`, `core_planner.py`

### ✅ Пріоритет #3: STT не ініціалізовано в GUI — **ВИРІШЕНО**
**Статус:** ✅ STT контролер тепер передається в GUI режим

**Зміни:**
- Додано створення STT контролера в `initialize_without_listener()`
- Передача через `_pending_stt_controller` в `run_assistant.py`
- `core_stt_listener` тепер перевіряє актуальне налаштування через `get_setting()`

**Файли:** `main.py`, `run_assistant.py`, `core_stt_listener.py`, `config.py`

### ✅ Пріоритет #4: Помилки Tkinter в plan_panel.py — **ВИРІШЕНО**
**Статус:** ✅ Виправлено для ttk.Label та знищених widget-ів

**Зміни:**
- `foreground` замість `fg` для ttk.Label
- Перевірка `winfo_exists()` перед доступом до widget-ів
- Fallback для обох методів (`update_plan_step`, `_get_label_status`)

**Файл:** `core_gui/plan_panel.py`

### ✅ Пріоритет #5: Анімація індикатора "Думаю..." — **ЗАВЕРШЕНО**
**Статус:** ✅ Додано анімовані крапки в статус-бар

**Зміни:**
- Методи `_start_thinking_animation()`, `_animate_thinking_dots()`
- Анімація: "🤔 Думаю" → "🤔 Думаю." → "🤔 Думаю.." → "🤔 Думаю..." (кожні 500мс)
- Автоматичний запуск при статусі "Думаю"

**Файли:** `core_gui/main_window.py`, `logic_commands.py`

### ✅ Пріоритет #6: Обробка пустої відповіді в стрімінгу — **ЗАВЕРШЕНО**
**Статус:** ✅ Показуємо повідомлення про помилку якщо контекст перевантажено

**Зміни:**
- Перевірка чи був контент в стрімі
- Заміна пустого "⚡ Марк:" на: "⚡ Марк: ⚠️ Порожня відповідь (можливо, перевантажено контекст LLM)"

**Файл:** `core_gui/chat_panel.py`

### ✅ Пріоритет #7: Валідація GUI інструментів — **ЗАВЕРШЕНО**
**Статус:** ✅ Phase 1-3 протестовані та інтегровані

**Завершено:**
- ✅ `take_screenshot()` — робочий, збереження файлів
- ✅ `mouse_click()` — інтегровано в TOOL_POLICIES
- ✅ `list_windows()` — стабільно повертає список вікон
- ✅ Всі GUI інструменти зареєстровані в executor

---

## Залежності для встановлення
## ⚠️ Ризики та їх мітігація

| Ризик | Ймовірність | Вплив | Мітігація |
|-------|-------------|-------|-----------|
| Антивірус блокує input automation | Середня | Високий | Code signing, whitelist, документація |
| Зміна UI після оновлення програм | Висока | Середній | Adaptive search, профілі з fallback |
| Помилки OCR на нестандартних шрифтах | Середня | Середній | Preprocessing, кілька движків, fallback |
| Випадкові дії в небезпечних місцях | Низька | Критичний | GUI Guardian, sandbox, undo, аудит |
| Зниження продуктивності (скріншоти) | Середня | Низький | mss (швидкий capture), кешування |
| Проблеми з multi-monitor | Середня | Середній | DPI awareness, координати з offset |
| Несумісність з Wine/VM | Висока | Низький | Документація, окремий compatibility layer |

---

## 🔗 Залежності для встановлення

```bash
# Phase 1 — Input & Windows
pip install pyautogui pywin32 psutil

# Phase 2 — Screen Capture
pip install mss Pillow opencv-python

# Phase 3 — OCR
pip install easyocr          # основний движок (GPU-прискорений)
pip install pytesseract      # fallback (потребує Tesseract у PATH)
# або
pip install paddlepaddle paddleocr  # альтернатива easyocr

# Phase 4 — Computer Vision (вже є через Phase 2)
# opencv-python вже встановлено

# Phase 7 — Automation
pip install selenium webdriver-manager  # для браузера
pip install pygetwindow                 # доп. менеджмент вікон

# Office Integration (опційно)
pip install pywin32  # вже є; використовуємо win32com.client
```

---

*Стратегічний план GUI Automation оновлено: 20.04.2026*
*Наступний крок: Phase 7 — Learning & Profiles (`core_app_profiles.py`, `tools_macro_recorder.py`, `logic_task_learner.py`))*

---

## 🧭 Пропозиції шляхів розвитку (квітень 2026)

Нижче — пріоритезований список ініціатив за результатами аудиту коду (20.04.2026).
Кожен пункт має: **P1** (критично / без цього не можна), **P2** (важливо), **P3** (бажано).

### 🔧 Трек A. Інженерна гігієна та якість

- **A1 [P1] Привести `requirements.txt` у відповідність з реальними імпортами.**
  Додати: `pyautogui`, `pywin32`, `psutil`, `mss`, `Pillow`, `opencv-python`, `pytesseract`, `easyocr` (опційно), `requests`.
  Розділити на `requirements.txt` (runtime) + `requirements-dev.txt` (`pytest`, `pytest-cov`, `ruff`, `black`, `mypy`).

- **A2 [P1] Синхронізувати README.md з реальною структурою.**
  - `gui/` → `core_gui/`
  - `python agent.py` → `python run_assistant.py`
  - Додати в перелік core-модулів `logic_scenario_runner`, `logic_ui_navigator`, `logic_context_analyzer`, `core_action_recorder`, `core_undo_manager`, `core_gui_guardian`, `tools_*`, `smart_patch_gui.py`.

- **A3 [P1] Додати CI (GitHub Actions).**
  Workflow: `lint` (`ruff check` + `black --check`), `tests` (`pytest tests/ --cov=functions`) на Windows-runner (для Phase 1/3) + Linux-runner (для core-логіки з моками).
  Додати `coverage` badge у README.

- **A4 [P2] Pre-commit hooks.**
  `.pre-commit-config.yaml` з `ruff`, `black`, `trailing-whitespace`, `end-of-file-fixer`, `check-merge-conflict`, `check-yaml/json`.

- **A5 [P2] `pyproject.toml` з налаштуваннями `ruff`/`black`/`pytest`.**
  Замінити/доповнити `pytest.ini` → `[tool.pytest.ini_options]` у `pyproject.toml`.

- **A6 [P2] Type hints + `mypy --strict` для `core_*` модулів.**
  Планер, executor, memory, tool_runtime — мають стабільні сигнатури; підвищить надійність рефакторів.

- **A7 [P3] Logging.** Перейти з `print(Fore.CYAN + "[DEBUG]...")` на `logging` з ротацією файлів (`logs/marc.log`).

### 🧪 Трек B. Покриття тестами (Phase 2/4/5/6)

- **B1 [P1] Обов'язкові unit-тести (всі з mock, без Windows залежностей):**
  - `test_tools_screen_capture.py` — mock `mss`, `PIL.ImageGrab`, перевірка збереження/координат
  - `test_tools_ui_detector.py` — синтетичні PIL-зображення (кнопка, checkbox)
  - `test_tools_app_recognizer.py` — mock `psutil.Process`, `win32gui.GetWindowText`
  - `test_tools_visual_diff.py` — синтетичні "до/після" PIL-зображення
  - `test_logic_ui_navigator.py` — mock Phase 1–4
  - `test_logic_scenario_runner.py` — JSON-сценарії + mock executor
  - `test_logic_context_analyzer.py` — mock OCR + UI detector
  - `test_core_action_recorder.py` — mock filesystem, перевірка JSONL
  - `test_core_undo_manager.py` — snapshots + undo по history
  - `test_core_gui_guardian.py` — ризик-рівні, sandbox region, preview_action

- **B2 [P2] Integration tests на Windows VM (GitHub Actions `windows-latest`):**
  - Сценарій Notepad (open → type → save → close)
  - Сценарій File Explorer (знайти файл, скопіювати шлях)
  - Маркери `@pytest.mark.windows` + `@pytest.mark.gui_integration`.

- **B3 [P3] Regression snapshots** — зберігати "золоті" baselines скріншотів UI-елементів у `tests/fixtures/baselines/` для `visual_diff`.

### 🧹 Трек C. Очищення кодової бази

- **C1 [P1] Видалити / повернути файли з суфіксами `_off` / `_old`:**
  - `functions/aaa_kill_process_by_name.py_off`
  - `functions/aaa_open_program.py_old`
  Рішення: або інтегрувати, або винести в `legacy/`.

- **C2 [P2] Винести runtime-state з `functions/`:**
  - `cache_data.json`, `user_settings.json`, `safety_config.json` → `./runtime/` або `~/.marc/`
  - Не включати в package-path.

- **C3 [P2] Обмежити розмір файлів.** Модулі `logic_ui_navigator.py` (860), `logic_context_analyzer.py` (854), `logic_scenario_runner.py` (807), `core_planner.py` (754), `main.py` (742) — рефакторити на підмодулі (напр. `planner/{prompt,retry,parser}.py`).

- **C4 [P3] Єдина конвенція іменування.** Перемішане `aaa_*` (агентські інструменти) / `tools_*` (GUI) / `logic_*` / `core_*` — виписати правила в CONTRIBUTING.md та привести до єдиного стилю.

### 🚀 Трек D. Phase 7 — Learning & Adaptation

- **D1 [P1] Фундамент Phase 7 (`core_app_profile` + `core_macro`):**
  `AppProfile` dataclass + JSON-persistence; `MacroRecorder` з інтеграцією `core_action_recorder`. Мінімальний MVP — без fancy ML.

- **D2 [P2] Вбудовані профілі:**
  Notepad, Explorer, Chrome, Paint із `common_shortcuts` та `known_elements`. Дозволяє агенту одразу впевнено працювати з цими програмами.

- **D3 [P3] `logic_task_learner.py`:**
  Простий `detect_repeated_pattern` (N-gram по історії дій). Складніші ML-фічі — пізніше.

- **D4 [P3] Планувальник задач (scheduling).**
  Тригери по часу/подіях файловій системі (`watchdog`). Частково пересікається з Phase 8 Watcher.

### 🤖 Трек I. Phase 8 — Автономія (Watcher + довгі сесії)

- **I1 [P1] `logic_watcher.py` engine:**
  `Watcher` клас із `condition_fn` / `action_fn` / `poll_interval`, запуск у окремому треді, персистенція стану в `logs/watchers/`.

- **I2 [P1] Бюджетні ліміти + kill-switch:**
  `SessionBudget`, `/tmp/marc-stop`-маркер, hotkey. Без цього небезпечно запускати на 6 годин.

- **I3 [P2] Вбудовані conditions:**
  `file_changed`, `process_finished`, `window_title_contains`, `chat_idle`, `url_response_contains`.

- **I4 [P3] Resume & reconnect:**
  `resume_watcher(id)` — продовжити з останньої точки після перезавантаження.

### 🎭 Трек J. Phase 9 — Оркестрація ШІ

- **J1 [P1] Абстракція `AIProvider` + HTTP-адаптери:**
  `OpenAIAdapter`, `AnthropicAdapter`, `GoogleAdapter` — повторне використання логіки `logic_llm.py`.

- **J2 [P1] `ProviderRegistry` + capability-based вибір:**
  Реєстр з описом можливостей (coding / vision / long-context) та автоматичним вибором.

- **J3 [P2] Browser-адаптери (Playwright):**
  `WindsurfBrowserAdapter`, `CursorBrowserAdapter`, `ChatGPTWebAdapter`, `ClaudeWebAdapter`.

- **J4 [P2] `logic_orchestrator.py`:**
  Декомпозиція задачі → делегування → агрегація. Fallback і паралельне делегування.

- **J5 [P3] Redaction PII + audit log:**
  Маска конфіденційних даних у промптах, що виходять у хмару.

### 🌈 Трек K. Phase 10 — Універсальні домени

- **K1 [P2] Фото/відео:** `tools_image_pillow`, `tools_video_ffmpeg`.
- **K2 [P2] ComfyUI / SD:** HTTP API до локального ComfyUI.
- **K3 [P3] Офіс:** `tools_word`, `tools_excel`, `tools_pdf`.
- **K4 [P3] Інсталятори:** winget/choco/apt із підтвердженням.

### 🌐 Трек E. Розширення можливостей

- **E1 [P2] Мультиплатформність (Linux/macOS).**
  Абстрагувати `tools_window_manager` (зараз win32-only) — `xdotool`/`wmctrl` на Linux, AppleScript/Accessibility на macOS. Дозволить розробникам на не-Windows тестувати core.

- **E2 [P2] Інтеграція з браузером.**
  `tools_browser.py` через **Playwright** (кращий за Selenium у 2026): `open_url`, `find_by_role`, `screenshot`, `execute_js`. Покриває 50%+ щоденних задач без клікання по пікселях.

- **E3 [P3] Office Integration (Word/Excel).**
  Через `win32com.client`. Потрібно тільки якщо є реальний сценарій — інакше перегрів scope.

- **E4 [P3] Tray-іконка + глобальні гарячі клавіші.**
  `pystray` + `keyboard` для швидкого виклику агента без відкриття GUI.

### 🧠 Трек F. LLM та планер

- **F1 [P1] Структуровані виклики інструментів (function/tool calling).**
  Замість самописного JSON-парсингу перейти на OpenAI-compatible `tools` параметр (LM Studio ≥ 0.3.x підтримує). Підвищить надійність планів на ~10–20%.
  ✅ **Злито в PR #19:** `functions/logic_llm_tools.py` — адитивний шар
  поверх legacy `logic_llm` з `ask_llm_with_tools`, `ChatToolsResponse`, `ToolCall`,
  `build_tool_spec`, `functions_to_tools`, `parse_tool_calls_from_body`,
  `execute_tool_calls`, `tool_results_to_messages`. 54 тести, 100% backward-compatible.
  Лишається окремим PR-ом: інтегрувати `ask_llm_with_tools` у `core_planner`,
  щоб замінити `extract_json_from_text` на структуровані `tool_calls`.

- **F2 [P2] Tree-of-thoughts / повний replan.**
  В статусі вже зазначено: «Planner не робить повне перепланування дерева». Додати `replan_from_step(N)` у `core_planner`.

- **F3 [P2] Оцінка якості плану (self-critique).**
  Перед виконанням LLM оцінює план (0–10) і за < 7 — переформовує.
  ✅ **Злито:** див. Phase 11.5 (`logic_plan_critic.py`, PR #18) —
  verdict `approve` / `concerns` / `redo` + stability guard + `review_and_run_plan` helper.
  Лишається інтегрувати в `core_planner` як обовʼязковий крок між `plan()` і `execute()`.

- **F4 [P3] Локальна fine-tuned модель для планів.**
  Коли зберемо `~500 успішних (задача, план)` пар — спробувати LoRA на базі `deepseek-coder` або `Qwen2.5-Coder-7B` для швидшого плануючого двигуна.

### 🛡️ Трек G. Безпека та надійність

- **G1 [P1] Обмежити `execute_python` через `RestrictedPython` або окремий процес.**
  Зараз sandbox — умовний; для real-world використання потрібна ізоляція (subprocess з обмеженням ресурсів, firejail/WSL на Linux, Win32 Job Objects на Windows).

- **G2 [P2] Rate limiting для LLM-викликів.**
  Запобігти нескінченним repair-циклам (вже є 3+1, але додати глобальний timeout на задачу).

- **G3 [P2] Телеметрія (opt-in).**
  Локальна DB `~/.marc/telemetry.sqlite` з подіями `task_started/completed/failed` + тривалістю — для аналітики, не надсилаючи нічого назовні.

- **G4 [P3] Код-підпис `.exe` збірки (PyInstaller).**
  Якщо планується розповсюдження бінарника — для антивірусів.

### 📦 Трек H. Дистрибуція

- **H1 [P2] PyInstaller збірка `.exe` + інсталятор (Inno Setup).**
  Мета: одноклікова інсталяція на Windows для non-tech користувачів.

- **H2 [P3] Оновлення через GitHub Releases.**
  Авто-перевірка нових релізів, `update.bat` для заміни виконуваного файлу.

---

## 🗓 Рекомендована послідовність (оновлено під нову візію — 6 спринтів × 2 тижні)

| Спринт | Пріоритети | Результат |
|--------|-----------|-----------|
| **S1 (✅ done)** | A1, A2, A3, C1, B1 | Робочий CI, чистий requirements, актуальний README, 147 тестів, 0 skipped |
| **S2 (in progress)** | D1 (Phase 7 фундамент), A4, A5 | `core_app_profile` + `core_macro` MVP, pre-commit, pyproject.toml повністю |
| **S3 (✅ done)** | I1+I2+I3 ✅ (Phase 8 Watcher + бюджети + conditions), F1 ✅ (tool calling, PR #19 злито), C3 | Довгі автономні сесії можливі + міцніший планер |
| **S4** | J1+J2+J3 ✅ (Phase 9 адаптери + registry + OpenAI-compatible), Phase 11 ✅ (PR #13), G1, B2 | Оркестрація через HTTP API + Autonomous Task Orchestrator + безпечний sandbox + Windows CI |
| **S4.5 (✅ done)** | **Phase 11.5 (Plan-critic)** + **Phase 12.1 (Step-Check / Actor-Critic)** — PR #18 злито | Якість прийняття рішень: +20-30% успішність планів; `precheck`/`expect` на кожному кроці |
| **S5** | J4 (browser-адаптери для Windsurf/Cursor), E2 (Playwright), **Phase 12.2** (LLM repair loop на `expect_failed`) | Windsurf/Cursor через браузер, паралельне делегування, повний Actor-Critic цикл |
| **S6** | K1–K4 (Phase 10 домени, drip-in), H1 | Фото/ComfyUI/офіс-інструменти, PyInstaller-інсталятор |

---

*Пропозиції розвитку підготовлені Devin (сесія [43aa3b10](https://app.devin.ai/sessions/43aa3b103a6642db94c3afb6707a35be)) на основі аудиту репозиторію станом на 20.04.2026.*