# Поточні задачі МАРК

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash

# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```
**Відладка проводиться за допомогою Debug-Loop**
# Debug-Loop — Універсальний алгоритм відладки

## Опис

Debug-Loop — це універсальний метод відладки, який використовується в цьому проекті для систематичного пошуку та виправлення помилок.

docs/DEBUG_LOOP.md --- тут більш детально описано цей метод.

## Коли використовувати

Коли ви пишете в чаті слово **"дебаг"**, **"debug"**, або **"Debug-Loop"**, це означає що треба виконати саме цей метод.

**ПРИМІТКА:** Виконані завдання перенесено в [TASKS_Done.md](TASKS_Done.md).

---

## P0: СТАБІЛІЗАЦІЯ ТА РЕФАКТОРИНГ АРХІТЕКТУРИ + ІНДЕКСАЦІЯ КОДОВОГО АГЕНТА

**Мета:** Привести проєкт до стану, коли нові функції можна додавати без ризику зламати існуюче, та створити інфраструктуру для кодового агента.

**Порядок виконання:** А0 → А1 → А2 → А3 → Б1 → Б2 → Б3. Не починати Б до завершення А.

---

### ЕТАП А. Стабілізація та рефакторинг архітектури

**Мета:** Привести проєкт до стану, коли нові функції можна додавати без ризику зламати існуюче.

#### А0. Усунути конфлікт шляхів виконання (P0, передумова для А1-А3)

**Проблема:** В `main.py:process_text_command()` існують два конкуруючі шляхи виконання — Planner legacy (`VoiceAssistant.process_command`) і AgentLoop (`run_agent_loop`). Класифікація між ними через ключові слова ненадійна, команди можуть потрапляти в обидва шляхи. Крім того, `run_agent_loop()` містить гілку `task_type == "CHAT"`, яка передоручає виконання назад у `process_command()` — це створює "підводний камінь" і зациклення.

**Рішення:**
- [x] Зробити AgentLoop єдиним шляхом виконання команд з GUI
- [x] `VoiceAssistant.process_command` залишити тільки для голосового режиму (STT), прибрати з нього Planner legacy
- [x] Planner legacy використовується тільки всередині AgentLoop як інструмент планування (`_plan_from_planner`), а не як окремий шлях з GUI
- [x] **Прибрати Planner legacy з `process_command()`** (`should_plan` → `create_plan` → `execute_plan_async`). Замість нього — виклик AgentLoop для команд і ask_llm для розмов.
- [x] Прибрати гілку `task_type == "CHAT"` в `run_agent_loop()` — вона передоручає виконання в `process_command`, що створює дублювання
- [x] Спростити `process_text_command()`: замість класифікації через ключові слова — завжди пускати через AgentLoop. Якщо AgentLoop вирішить що це "чайт" — він сам запустить LLM.
- [x] `process_command()` після А0 виконує тільки: перевірка активаційного слова → визначення "команда vs розмова" → AgentLoop (для команд) / ask_llm (для розмов) → TTS → conversation_history
- [x] Видалити або закомітити методи Planner з `logic_commands.py`, які більше не потрібні на цьому шляху

**Очікуваний pipeline після А0:**
```
GUI команда → run_agent_loop() → AgentLoop (LLM decide / Planner / CompiledPlan) → виконання
STT команда → process_command() → (якщо задача) → AgentLoop / (якщо чат) → LLM
```

**Критерій готовності:** одна команда з GUI завжди йде через один шлях, без умовних розгалужень по ключових словах.

**Файли для змін:**
- `main.py` — `process_text_command()`, `run_agent_loop()`, `_classify_task()`
- `functions/logic_commands.py` — перевірити чи process_command використовується з GUI

#### А1. Полагодити pytest collection (P0) ✅

- [x] Повернути сумісність між тестами і `logic_task_runner`
- [x] Добитися щоб `pytest tests/` проходив хоча б collection без помилок
- [x] Зафіксувати публічні API для parser/runner/plan-об'єктів

#### А2. Реструктуризація папки functions/ ✅

Зараз у `functions/` 100+ файлів у плоскій структурі — це ускладнює навігацію. Згрупувати модулі по підпапках:

- [x] Створити `functions/llm/` — вже є, залишити без змін
- [x] Створити `functions/tools/` — перенести всі `tools_*.py` і `aaa_*.py`
- [x] Створити `functions/planning/` — перенести: `agent_loop.py`, `core_planner.py`, `core_plan_compiler.py`, `core_planner_critic.py`, `core_planner_runner.py`, `logic_task_runner.py`, `logic_expectations.py`, `task_spec.py`
- [x] Створити `functions/runtime/` — перенести: `core_tool_runtime.py`, `core_settings.py`, `core_memory.py`, `core_cache.py`, `core_session_budget.py`, `core_undo_manager.py`, `core_action_recorder.py`
- [x] Створити `functions/gui/` — перенести: `core_gui_guardian.py`, `tools_screen_capture.py`, `tools_ocr.py`, `tools_mouse_keyboard.py`, `tools_window_manager.py`, `tools_ui_detector.py`, `tools_ui_accessibility.py`, `tools_visual_diff.py`, `voice_tray_icon.py`
- [x] Виправити всі імпорти всередині переміщених файлів
- [x] Додати файли-заглушки для зворотної сумісності (49 файлів)
- [x] Переконатись що `pytest` проходить collection без помилок ✅ (1400 tests)

#### Розширення задачі А2.1: інтеграція core/ та utils/ ✅

- [x] Перенести `core/context_controller.py` до `functions/planning/`
- [x] Перенести `utils/screen_helper.py` до `functions/gui/`
- [x] Після перенесення виправити імпорти у всіх залежних модулях (tools_mouse_keyboard + тести)
- [x] Видалити порожні папки `core/` та `utils/`
- [x] Переконатись, що `pytest` проходить collection без помилок ✅ (1400 tests)

### P0: Стабілізація AgentLoop для коду (перед А3)

- [ ] 1. Налаштувати Groq API пріоритетним LLM:
  - URL: `https://api.groq.com/openai/v1`, модель: `llama3-70b-8192`
  - Перевірити ключ тестовим скриптом (curl/python)
  - Виправити помилки 401/404/400 в логах
туту низькі ліміти треба передивитися



- [ ] 2. Заборонити `execute_python` для створення/редагування файлів:
  - Оновити `SYSTEM_PROMPT` в `agent_loop.py` (жорстке правило)
  - Додати валідацію в `aaa_execute_python.py`: якщо code >5 рядків або містить `def/class` → error
- [ ] 3. Автоматична перевірка коду після `write_file`/`edit_file`:
  - У `agent_loop._execute_single_step` після запису `.py` файлу викликати `execute_python`
  - Результат (`auto_test_passed`) додати в `observation`
- [ ] 4. Посилити repair loop для коду:
  - При `auto_test_passed=False` сформувати repair_prompt з помилкою
  - Викликати LLM для отримання `edit_file` і повторити перевірку

### P1: А3. Розрізати великі модулі (після стабілізації)

- [ ] `agent_loop.py` → `observe.py`, `plan.py`, `act.py`, `check.py`
- [ ] `main.py` → винести STT/TTS/LM Studio ініціалізацію
- [ ] `logic_commands.py` → розділити за типами команд
- [ ] `core_planner.py` → розділити prompt/валідацію/repair

### P1: ЕТАП 2. GUI Tester (самотестування)

- [ ] Створити `functions/logic_gui_tester.py`
- [ ] Додати вкладку "Тестування" в `core_gui_pyqt6/`
- [ ] Написати сценарії для Notepad та власного GUI

### P1: ЕТАП 10. Phase 13 – реальна кодогенерація (після всього)

- [ ] Реалізувати `_execute_windsurf` та `_execute_cursor` через CDP
- [ ] Замінити `_scaffold_content()` на виклик `AIActor.execute()`
- [ ] Інтегрувати `ai_actors.py` з `pipeline_code.py`

#### А3. Розрізати великі модулі

Пріоритетні файли для розбиття:

- [ ] `main.py` (AssistantCore) — винести ініціалізацію STT, TTS, LM Studio-перевірку, AgentLoop в окремі модулі
- [ ] `agent_loop.py` — розділити на `observe.py`, `plan.py`, `act.py`, `check.py` всередині підпапки `functions/agent/`
- [ ] `logic_commands.py` — винести planner-гілку, streaming-гілку і TTS-гілку окремо
- [ ] `core_planner.py` — розділити prompt-будування, валідацію плану і repair-логіку

**Критерій готовності:** жоден файл не перевищує 400 рядків.

---

### ЕТАП Б. Інтеграція індексації проєкту для кодового агента

**Контекст:** Кодовий агент ("агент кодування") має бачити весь проєкт і грамотно вносити точкові зміни, не чіпаючи решту коду. Для цього потрібна двошарова індексація: карта проєкту (швидка) + семантичний пошук (точний).

#### Б1. Repo Map — карта проєкту (перший крок)

- [ ] Створити `functions/project_indexer.py`
  - Сканує кореневу папку проєкту
  - Парсить всі `.py` файли через `ast` (без зовнішніх залежностей)
  - Витягує класи, функції, методи з сигнатурами (без тіла)
  - Результат зберігається у `runtime/repo_map.json`
- [ ] Автоматичне оновлення карти після кожної зміни файлу кодовим агентом
- [ ] Інтеграція в `get_coding_system_prompt()` — під час старту coding-сесії карта підвантажується і додається в системний промпт агента

#### Б2. Семантичний пошук по коду (другий крок, після Б1)

- [ ] Реалізувати `functions/vector_memory.py` на базі ChromaDB
  - Кожна функція/клас індексується як окремий чанк з ембеддингом
- [ ] Додати інструмент `search_code(query)` в реєстр функцій
  - Повертає 3-5 найбільш релевантних фрагментів коду за смисловим запитом
- [ ] Це вирішує ситуацію коли задача сформульована людською мовою: агент знаходить потрібний код не по імені функції, а по суті того що вона робить

#### Б3. Навчити coding-агента комбінувати інструменти

- [ ] В системному промпті coding-режиму прописати чіткий алгоритм роботи з кодом:
  - Спочатку переглянути Repo Map або зробити `search_code`
  - Визначити файли-кандидати
  - Прочитати їх повністю через `read_code_file`
  - Внести зміну
  - Оновити індекс
- [ ] Без цього кроку індексація буде зроблена але агент її не використовуватиме

---



## В процесі



### Проблема: Global Voice Input - tray icon не оновлюється

**Статус:** Виправлено (02.05.2026, 19:33)
Потрібно доробити, щоб ця іконка завжди була в треї. і відповідно показувало статус самого асистента. Мається на увазі саме статус по мікрофону. і розпізнавання тексту.



**Симптоми:**
**
- Tray icon показується в system tray але не змінює колір при зміні статусу

- Логи показують що set_status викликається але іконка залишається незмінною



**Причина:**

- QTimer.singleShot не працює надійно з інших потоків

- QApplication вже існує від PyQt6 GUI, створення окремого event loop призводило до конфлікту



**Рішення:**

- Використано QApplication.postEvent() з кастомним _StatusUpdateEvent

- Додано customEvent() для обробки event-ів в основному потоці Qt

- Прибрано зайві логи


**
**Файли:**

- `functions/voice_tray_icon.py` - перероблено на postEvent/customEvent



---



### Проблема: Global Voice Input - tray icon не показує змін стану

**Статус:** Відстеження (03.05.2026)

**Симптоми:**
- Tray icon відображається в system tray
- При зміні стану (RECORDING, PROCESSING, IDLE) іконка НЕ змінюється візуально
- Логи показують що `_do_set_status` викликається коректно:
  - Іконка створюється: `icon.isNull()=False`
  - Іконка встановлюється: `Іконка встановлена`
  - Tooltip встановлюється: `🔴 Запис...`

**Причина:**
- Windows кешує іконки system tray і не оновлює їх автоматично
- `QSystemTrayIcon.setIcon()` не завжди оновлює візуальне відображення в Windows

**Спроби вирішення:**
1. **postEvent з кастомним _StatusUpdateEvent** - не працювало з існуючим QApplication від GUI
2. **pyqtSignal _update_requested.emit()** - сигнал не оброблявся через відсутність підключення до Qt event loop
3. **QTimer.singleShot** - не працювало через те ж саме
4. **QApplication.postEvent** - не оброблявся customEvent
5. **Прямий виклик _do_set_status для існуючого QApplication** - працює, логи показують що іконка встановлюється
6. **hide()/show() для примусового оновлення** - додано для примусового оновлення system tray

**Поточний стан:**
- `_do_set_status` викликається коректно при натисканні Ctrl+F9
- Іконка створюється і встановлюється (підтверджено логами)
- Візуально іконка НЕ змінюється в system tray (можливо проблема Windows кешування)

**Файли:**
- `functions/voice_tray_icon.py` - змінено `set_status()` на прямий виклик для існуючого QApplication, додано hide()/show()
- `tests/test_voice_tray_icon.py` - створено повний набір тестів (13 passed, 1 skipped)
- `TEST_GUI/test_tray_icon_with_logs.py` - тест з логуванням (працює)
- `TEST_GUI/test_tray_icon_hotkey.py` - тест через Ctrl+F9 hotkey (працює, логи підтверджують виклик _do_set_status)

**Можливі рішення:**
- Використати інший спосіб відображення статусу (наприклад, зміна tooltip замість кольору іконки)
- Використати іншу бібліотеку для tray icon (наприклад, pystray)
- Додати механізм примусового оновлення Windows system tray через Win32 API



---



### Проблема: Global Voice Input - не запам'ятовує розмір і позицію вікна

**Статус:** Відстеження (02.05.2026, 19:33)



**Симптоми:**

- Після повернення фокусу вікно може бути зміщене або змінене за розміром

- Не зберігається початковий стан вікна перед голосовим введенням



**Причина:**

- Запам'ятовується тільки HWND вікна, не розмір і позиція

- Немає механізму відновлення початкового стану



**Дії:**

- Додати запам'ятовування розміру (width, height) і позиції (x, y) вікна

- Додати відновлення розміру і позиції після вставки тексту



**Файли:**

- `functions/global_voice_input.py` - GlobalVoiceInput._start_recording, _on_text_recognized



---



### Архітектура: Global Voice Input — вставка через зовнішній макрос

**Статус:** Реалізовано (03.05.2026)

**Архітектура:**
- `global_voice_input.py` — тільки запис голосу + тригер Shift+F10
- **Зовнішній макрос** (Robotask / AutoHotkey) — ловить Shift+F10 і виконує Ctrl+V

**Алгоритм:**
1. Ctrl+F9 — запускає запис, очищає буфер обміну
2. Після розпізнавання — копіює текст у буфер, натискає **Shift+F10**
3. Зовнішній макрос ловить Shift+F10 і виконує Ctrl+V у цільове вікно
4. Чекає 2 сек, потім очищає буфер обміну

**Важливо:**
- ⚠️ **НЕ РЕДАГУЙТЕ** логіку вставки в `global_voice_input.py` без узгодження
- Для зміни поведінки вставки — редагуйте **ЗОВНІШНІЙ макрос**

**Файли:**
- `functions/global_voice_input.py` — запис голосу + тригер Shift+F10
- Ваш зовнішній макрос (Robotask/AutoHotkey) — ловить Shift+F10 і виконує Ctrl+V



---



> **Перенесено в А0** — конфлікт шляхів виконання тепер вирішується архітектурно, а не точковими правками.

---



## P0: COMPUTER USE АГЕНТ — МАРК як людина за комп'ютером



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



---



#### ЕТАП 2: GUI ТЕСТУВАЛЬНИК (ВИСОКА ЦІННІСТЬ для self-validation)



**Ціль:** МАРК може тестувати власні зміни в GUI як QA-інженер: відкрити програму, перевірити функції, зробити висновки.



**Робоча основа:**

- ✅ `test_duplication_direct.py` (~134 рядків) — працюючий скрипт для автоматизованого GUI тестування

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



---



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

    - Якщо LLM просить — викликати `vision_provider.find_element(...)` для пошуку елемента за описом



- [ ] Додати vision-tools в schema (`logic_agent_tools_schema.py`)

  - Пріоритет: P1

  - Tools: `describe_screen`, `find_element_by_description`, `is_screen_correct`



- [ ] Тести (`tests/test_providers_vision.py`, ~150 рядків)

  - Пріоритет: P1

  - Моки HTTP-викликів OpenAI/Anthropic/Ollama



**Оцінка:** ~200 нових рядків + ~50 змін + ~150 тестів. Складність: середня. Залежність: API key або Ollama.



---



#### ЕТАП 7: CHECKPOINT/RESUME — НАДІЙНІСТЬ ДОВГИХ СЕСІЙ



**Ціль:** При краші 6-годинної сесії — продовжити з останньої точки.



- [ ] Перевірити `core_checkpoint.py` та інтеграцію з `AgentLoop`

  - Пріоритет: P2

  - Деталі:

    - `CheckpointManager.save/load/delete` вже існує

    - В `AgentLoop._save_checkpoint` — додати збереження observations[-3:] (останні 3 спостереження для контексту)

    - В `_load_checkpoint` — відновити `_compiled_plan` якщо був

    - CLI `python run.py --resume <task_id>` для запуску з checkpoint



- [ ] Тести (`tests/test_core_checkpoint.py` якщо ще немає)

  - Пріоритет: P2



**Оцінка:** ~50-100 нових рядків + ~30 змін. Складність: низька.



---



#### ЕТАП 8: SELF-TESTING ЦИКЛ — МАРК тестує себе



**Ціль:** Об'єднати всі етапи у workflow: МАРК робить зміну в коді → запускає GUITester → отримує звіт → робить висновок.



- [ ] Створити `functions/self_test_workflow.py` (~300 рядків)

  - Пріоритет: P1

  - Деталі:

    - Метод `test_my_changes(changes_description)` — головний workflow

    - Крок 1: Прочитати changes (через `git_diff` або переданий опис)

    - Крок 2: Визначити які сценарії запускати (по changed files)

    - Крок 3: Запустити `GUITester.test_scenario()` для кожного

    - Крок 4: Згенерувати агрегований звіт

    - Крок 5: Якщо є помилки — викликати LLM для діагностики ("що пішло не так і як виправити")

    - Крок 6: Повернути вердикт: "✅ Все ок" / "❌ Треба доробити: ..."



- [ ] Інтеграція в GUI як кнопка "🧪 Протестувати зміни"

  - Пріоритет: P1

  - Файл: `core_gui_pyqt6/main_window.py`



- [ ] Документувати workflow в `docs/tests.md`

  - Пріоритет: P1



**Оцінка:** ~300 нових рядків + ~50 змін.



---



#### ЕТАП 9: ТЕСТИ + CI

---

#### ЕТАП 10: PHASE 13 — КОДОГЕНЕРАЦІЯ (S9 CROSS-AI ACTORS)

**Ціль:** Реальне "ТЗ → готовий артефакт" через cross-AI actors (Codex/ChatGPT/Windsurf)

**Поточний стан:**

- ✅ `pipeline_code.py` (330 рядків) — scaffold система для `DOMAIN_CODE`
  - `CodePipeline.compile(spec)` — генерує Plan з кроками: mkdir, write_file, pytest, ruff
  - `_scaffold_content()` — створює **placeholder** (docstring + TODO + `raise NotImplementedError`)
  - `required_tools()` — повертає список потрібних інструментів

- ✅ `ai_actors.py` (420 рядків) — інтерфейс для зовнішніх провайдерів
  - `AIActor.execute()` — базовий метод
  - Підтримувані провайдери: Codex, Windsurf, Cursor, ChatGPT, Claude, Gemini

- 🟡 `_execute_codex()` — використовує primary endpoint як Codex API (але це не справжній Codex)

- ❌ `_execute_windsurf()`, `_execute_cursor()` — не реалізовано (тільки заглушки)

- ❌ **S9 не підключено** — немає інтеграції `pipeline_code.py` з `ai_actors.py` для реальної кодогенерації

**Проблема:**
- `_scaffold_content()` генерує порожні заглушки, а не реальний код
- В коментарях написано: `"TODO: implement. Real code-generation is wired in S9 via cross-AI actors (Codex/ChatGPT/Windsurf)"`
- Реальне "ТЗ → готовий артефакт" не працює

**Що треба доробити:**

- [ ] Реалізувати `_execute_windsurf()` — інтеграція з Windsurf (можливо через CLI або API)
- [ ] Реалізувати `_execute_cursor()` — інтеграція з Cursor (можливо через CLI або API)
- [ ] Замінити `_scaffold_content()` на реальну кодогенерацію через `AIActor.execute()`
- [ ] Додати параметр `CodePipeline.use_ai_actors` для перемикання між scaffold і реальною кодогенерацією
- [ ] Інтегрувати `ai_actors.py` в `pipeline_code.py` для виклику S9
- [ ] Тести для `ai_actors.py` (моки для зовнішніх API)
- [ ] Тести для `pipeline_code.py` з AI actors (інтеграційні)

**Оцінка:** ~300-400 рядків нового коду + ~200 рядків тестів. Складність: середня (залежить від доступності Windsurf/Cursor API).

---

#### ЕТАП 12: ОРКЕСТРАЦІЯ ШІ (ROUTER + PROVIDER CHAIN)

**Ціль:** Повна оркестрація ШІ з класифікацією запитів, fallback ланцюгом і quota tracking.

**Архітектура (3 рівні):**
- **Рівень 1 — Router:** Класифікація запитів за типом (CODE/DEBUG/GUI/WEB/GENERAL/QUICK), вибір провайдера
  - Послідовний fallback ланцюг
  - Quota tracking (consecutive errors limiter)
  - Health-check для LM Studio
  - Structured logging через `mark.orchestration` logger

- ✅ `tests/test_router.py` (12 тестів pass) — тести класифікації і маршрутизації

- ❌ НЕ інтегровано в logic_commands.py (process_command)
- ❌ НЕ налаштовано LLM_ENDPOINTS для GPT-OSS 20B, Gemini, DeepSeek
- ❌ НЕ реалізовано context_budget обрізання conversation history
- ❌ НЕ написано тести для provider_chain

**Ролі моделей:**
- **Orchestrator (GPT-OSS 20B, LM Studio):** Primary для загальних запитів, планування, об'єднання результатів
- **Code Generator (Gemini 3.1 Flash Lite):** Secondary для кодогенерації (швидка API)
- **Debugger (DeepSeek):** Fallback для відладки/аналізу помилок

**Що треба доробити:**

- [ ] Інтегрувати Router + ProviderChain в logic_commands.py (process_command) замість прямого ask_llm
- [ ] Налаштувати LLM_ENDPOINTS в config.py: orchestrator (GPT-OSS 20B), code_generator (Gemini), debugger (DeepSeek)
- [ ] Реалізувати context_budget обрізання conversation history при зміні провайдера
- [ ] Додати health-check для LM Studio перед запитами (ConnectionRefused обробка)
- [ ] Тести для provider_chain (fallback, quota, health-check)
- [ ] Інтегрувати в AgentLoop (ActionDecider використовує Router)
- [ ] GUI для оркестрації: відображення активної моделі, моніторинг квот

**Обладнання:**
- Відеокарта: RTX 5060 Ti (12GB VRAM)
- LM Studio: `http://localhost:1234/v1/chat/completions`
- Підтримує: CUDA, float16, квантування

**Оцінка:** ~200-300 рядків інтеграції + ~100 рядків тестів. Складність: середня (залежить від налаштування LM Studio).

---

### ЕТАП 13: МАРШРУТИЗАЦІЯ КРОКІВ ЗА СКЛАДНІСТЮ (БРАУЗЕРНІ AI)

**Мета:** Розширити `AgentLoop` можливістю делегувати виконання «кодогенеруючих» кроків різним зовнішнім AI залежно від оціненої складності. Прості кроки виконує локальний LLM (через існуючий `ActionDecider`), середні – DeepSeek або Grok через браузер (CDP), складні – ChatGPT/Claude через браузер. Результат зберігається у файл і проходить автоматичну перевірку (`execute_python`).

**Пріоритет:** P1 (підвищує якість складних завдань без втрати швидкості на простих)

**Залежності:**
- ✅ `tools_browser_cdp.py` (CDP – Chrome DevTools Protocol)
- ✅ `aaa_execute_python.py` (перевірка згенерованого коду)
- ✅ `agent_loop.py` (основний цикл, метод `act`)
- 🟡 `logic_llm_tools.ask_llm_with_tools` (локальний LLM для простих кроків)

---

#### Завдання 13.1. Класифікатор складності кроку

- [ ] Створити `functions/step_difficulty.py`
- [ ] Реалізувати функцію `classify_step(step: dict) -> 'simple'|'medium'|'hard'`
- [ ] Критерії:
  - `simple`: дії типу `read_code_file`, `list_directory`, `search_in_code`; або генерація коду довжиною до 20 рядків без `class`/складних алгоритмів.
  - `medium`: `write_file` з кодом 20–100 рядків, наявність функцій, помірна логіка.
  - `hard`: генерація багатофайлових проєктів, використання `asyncio`, класів, зовнішніх API; ключові слова «складний», «архітектура», «оптимізуй».
- [ ] Покрити тестами (`tests/test_step_difficulty.py`)

#### Завдання 13.2. Браузерні виконавці для зовнішніх AI

- [ ] Створити `functions/browser_ai_executors.py`
- [ ] Реалізувати функції:
  - `execute_with_deepseek(task: str) -> dict` – відкриває chat.deepseek.com, вводить `task`, чекає відповідь, повертає текст.
  - `execute_with_grok(task: str) -> dict`
  - `execute_with_chatgpt(task: str) -> dict`
- [ ] Використовувати `tools_browser_cdp` для:
  - `cdp_ensure_chrome` (запуск Chrome з портом 9222)
  - `cdp_open_tab`, `cdp_type_text`, `cdp_click_text` (або `cdp_click`), `cdp_wait_for_text`, `cdp_get_response`
- [ ] Додати конфігурацію селекторів у `runtime/browser_selectors.json` (URL, textarea, кнопка submit, контейнер відповіді)
- [ ] Додати таймаути (120 секунд) та повторні спроби (2–3)
- [ ] Тести: `tests/test_browser_ai_executors.py` (з моками CDP або реальні smoke)

#### Завдання 13.3. Інтеграція в AgentLoop (метод `act`)

- [ ] У `functions/agent_loop.py` імпортувати `classify_step`, `execute_with_deepseek`, `execute_with_grok`, `execute_with_chatgpt`
- [ ] Модифікувати метод `act`:
  - Якщо `action` НЕ є кодогенеруючим (`write_file`, `edit_file`, `execute_python`, `create_file`) → виконати локально через `registry.execute_function` (без змін).
  - Якщо кодогенеруючий крок:
    - `difficulty = classify_step(step)`
    - `simple` → використати локальний LLM (через `ask_llm_with_tools` або `self.decider`), зберегти у файл (якщо `write_file`).
    - `medium` → спробувати `execute_with_deepseek`, при невдачі – `execute_with_grok`. Результат зберегти, викликати `execute_python` для перевірки.
    - `hard` → виконати через `execute_with_chatgpt`, також з перевіркою.
- [ ] Результат `act` має містити поля `success`, `result` (текст коду або повідомлення), `engine` (local/deepseek/grok/chatgpt), `verified` (True/False після `execute_python`).

#### Завдання 13.4. Обробка невдалої перевірки коду (repair)

- [ ] У `AgentLoop._execute_single_step` після виклику `act` перевірити `result.get("verified")`.
- [ ] Якщо `verified == False` і є `result["error"]` (помилка виконання), викликати існуючий `StepRepairer` з контекстом.
- [ ] Розширити `StepRepairer` (`logic_repair_loop.py`) можливістю повторно відправити завдання з текстом помилки в той самий браузерний AI (наприклад, «Твій код не працює: ... Виправ»).
- [ ] Максимум 2 спроби repair на крок.

#### Завдання 13.5. Налаштування та документація

- [ ] Додати в `SETTINGS_SCHEMA` (`core_settings.py`):
  - `ROUTE_BY_DIFFICULTY_ENABLED` (bool, default False) – глобальний вимикач.
  - `BROWSER_AI_TIMEOUT` (int, default 120)
  - `BROWSER_AI_RETRIES` (int, default 2)
  - `LOCAL_LLM_FOR_SIMPLE` (bool, default True)
- [ ] Оновити `docs/ARCHITECTURE.md` – додати розділ «Маршрутизація кроків за складністю».
- [ ] Оновити `README.md` – згадати можливість делегування ChatGPT/DeepSeek через браузер.

#### Завдання 13.6. Тестування інтеграції

- [ ] Написати інтеграційний тест `tests/test_agent_loop_routing.py`:
  - Завдання з простим кодом → переконатися, що виконався локальний LLM.
  - Завдання із середнім кодом → викликався DeepSeek (або Grok), результат збережено, перевірка пройшла.
  - Завдання зі складним кодом → викликався ChatGPT, збережено, перевірено.
- [ ] Smoke-тест на реальному Chrome (опціонально, вручну).

---
**Результат після виконання етапу:**
AgentLoop вміє самостійно вирішувати, кому доручити генерацію коду – локальній моделі, DeepSeek, Grok чи ChatGPT. Код автоматично зберігається у файли і перевіряється на працездатність. При помилках – запускається виправлення через той самий зовнішній AI. Усі дії відбуваються без участі користувача, в межах одного циклу `observe → plan → act → check`.

---

#### ЕТАП 11: ТЕСТИ + CI



- [ ] Додати відсутні unit-тести (Phase 2-4 інструменти)

  - Пріоритет: P1

  - Файли:

    - `tests/test_tools_screen_capture.py` (~200 рядків)

    - `tests/test_tools_ui_detector.py` (~200 рядків)

    - `tests/test_tools_app_recognizer.py` (~200 рядків)

    - `tests/test_agent_loop_full.py` (~300 рядків) — повний цикл з моками



- [ ] Налаштувати GitHub Actions CI

  - Пріоритет: P2

  - Файл: `.github/workflows/ci.yml`

  - Кроки: ruff check, pytest, coverage report

  - Окремий Windows job для UIA-тестів



- [ ] Pre-commit config

  - Пріоритет: P2

  - Файл: `.pre-commit-config.yaml`

  - Hooks: ruff (--fix), pytest pre-push



**Оцінка:** ~900 нових рядків тестів + конфіги.



---



#### ПРІОРИТЕТИ ТА ЗАЛЕЖНОСТІ



```

ЕТАП 1 (Agent Loop + LLM tool-calling) ← КРИТИЧНИЙ, основа всього [DONE]

  ├→ ЕТАП 3 (UIA посилення) — підсилює observe/act [DONE]

  ├→ ЕТАП 4 (Vision-LLM) — підсилює decide [MVP — analyze_image для OpenAI/Claude/Gemini готовий, detect_ui_elements/suggest_actions — stubs]

  ├→ ЕТАП 5 (Browser) — нові capabilities [DONE]

  ├→ ЕТАП 6 (Repair Loop) — стійкість [DONE]

  ├→ ЕТАП 7 (Checkpoint) — надійність [PENDING]

  └→ ЕТАП 2 (GUI Tester) — використовує AgentLoop [PENDING]

       └→ ЕТАП 8 (Self-Testing) — використовує GUITester [PENDING]

ЕТАП 10 (Phase 13 — Кодогенерація) ← незалежний, використовує ai_actors [PENDING]

ЕТАП 12 (Оркестрація ШІ) ← Router + Provider Chain, інтегрується в AgentLoop [PENDING]

ЕТАП 13 (Маршрутизація кроків за складністю) ← браузерні AI (DeepSeek/Grok/ChatGPT), залежить від Browser CDP + AgentLoop [PENDING]

ЕТАП 11 (Тести + CI) ← паралельно з усім [PENDING]

```



#### СУМАРНА ОЦІНКА (ЗАЛИШИЛОСЯ)



| Етап | Нових рядків | Змін | Нових файлів | Час |

|------|-------------|------|--------------|-----|

| 2. GUI Tester | ~700 | ~50 | 2-3 | 2 дні |

| 4. Vision-LLM | ~200 | ~50 | 0 | 1 день |

| 7. Checkpoint | ~50 | ~30 | 0 | 0.3 дня |

| 8. Self-Testing | ~300 | ~50 | 1 | 1 день |

| 9. Тести + CI | ~900 | конфіги | 4+ | 2 дні |

| **РАЗОМ** | **~2150** | **~180** | **7+** | **~6-7 днів** |



---



### P0: Стабільність і узгодженість контрактів



- [ ] Додати GUI налаштування для таймауту LLM

  - Статус: Не розпочато

  - Пріоритет: P0

  - Деталі:

    - Поточний таймаут: 60 секунд (замалий для кодингу)

    - Додати налаштування `LLM_TIMEOUT` в SETTINGS_SCHEMA (default 180)

    - Інтегрувати в GUI (SettingsTab)

    - Застосувати в `logic_llm.ask_llm` та `logic_llm_tools.ask_llm_with_tools`

    - Файли: `functions/core_settings.py`, `core_gui_pyqt6/settings_tab_qt.py`, `functions/logic_llm.py`



- [ ] Обробка помилок LLM в AgentLoop

  - Статус: Не розпочато

  - Пріоритет: P0

  - Деталі:

    - При таймауті/помилці мережі AgentLoop повертає "Успішно" замість "Error"

    - Додати try/except в `_execute_single_step` для ActionDecider.decide()

    - При помилці LLM встановлювати `state.status = "Error"` та зупиняти цикл

    - Логування помилок LLM для діагностики

    - Файли: `functions/agent_loop.py`



- [ ] Синхронізувати документацію з реальним кодом

  - Статус: Не розпочато

  - Пріоритет: P0

  - Деталі:

    - Оновити `README.md` під актуальну структуру проєкту

    - Прибрати застарілі згадки про старий LLM-шар там, де вже використовується `functions/llm/`

    - Перевірити, щоб `README.md`, `status.md`, `TASKS.md` і код не суперечили одне одному



### P0: ОПТИМІЗАЦІЯ КОДУ


- [ ] Перевірити та оптимізувати `functions/agent_memory.json` (3.8MB)

  - Статус: Не розпочато

  - Пріоритет: P0

  - Деталі:

    - Перевірити актуальність даних в файлі

    - Можливо потребує очищення від застарілих записів

    - Розглянути архівування старих даних

    - Можливо реалізувати ротацію логів пам'яті



### P0: Інтеграція AgentLoop з GUI (критично для external AI-архітектури)


- [ ] Покращити GUI → AgentLoop інтеграцію

  - Статус: Не розпочато

  - Пріоритет: P0

  - Деталі:

    - AgentLoop вже реалізовано (observe → plan → act → check) в Phase 12.1

    - Потрібно зробити його основним шляхом виконання задач з GUI

    - Замінити legacy flow (GUI → logic_commands → planner → executor)

    - Додати чіткий UI для запуску AgentLoop (кнопка "Запустити агента")



- [ ] Додати tool-calling для LLM

  - Статус: Не розпочато

  - Пріоритет: P0

  - Деталі:

    - LLM зараз повертає JSON з action/code

    - Потрібно перейти на structured tool-calling (OpenAI-compatible)

    - Це дасть кращий control над actions



- [ ] Створити Skills (абстракції над базовими діями)

  - Статус: Не розпочато

  - Пріоритет: P0

  - Деталі:

    - Замість "клікни сюди" - "open_browser(), search_google(), fill_form()"

    - Менше помилок, швидше, стабільніше

    - База накопичуваних навичок



### P0: Context Summarizer (стиснення контексту)

- [ ] Створити `functions/context_summarizer.py`
  - Пріоритет: P0
  - Деталі:
    - Відстежувати кількість токенів у сесії (через token_counter)
    - При досягненні 80% ліміту контексту викликати LLM для стиснення старих повідомлень
    - Зберігати ключові факти, цілі, рішення; видаляти несуттєві репліки

- [ ] Інтегрувати в `logic_commands.py` перед кожним викликом LLM
- [ ] Додати налаштування `CONTEXT_SUMMARIZE_THRESHOLD` (за замовчуванням 0.8)
- [ ] Тест: `tests/test_context_summarizer.py`

**Оцінка:** ~150 рядків коду + тести

### P1: Vector Long-Term Memory (заміна Skills DB на ChromaDB)

- [ ] Встановити `chromadb`
- [ ] Створити `functions/vector_memory.py` (адаптер над self_learning)
  - Методи: `store_skill(description, code)`, `find_similar_skills(query, top_k=3)`
- [ ] Замінити поточний лінійний пошук у `self_learning.get_skill()` на векторний
- [ ] Міграція старих навичок у колекцію ChromaDB
- [ ] Тест: `tests/test_vector_memory.py`

**Оцінка:** ~200 рядків коду + міграція

### P1: Multi-LLM Debate (різні моделі для Виконавця/Критика)

- [ ] Додати в `SETTINGS_SCHEMA` параметри `CRITIC_MODEL` та `EXECUTOR_MODEL`
- [ ] У `AgentLoop._plan()` викликати Executor (основна модель), у `_check()` — Critic (глибший аналіз, може бути DeepSeek)
- [ ] Забезпечити можливість вказати різні endpoints/моделі для цих ролей
- [ ] Тест: `tests/test_multi_llm_debate.py`

**Оцінка:** ~100 рядків змін + конфіг

### P1: Інтеграція Open Interpreter (self-healing executor)

**Статус:** Виконано (10.05.2026) - потребує реального тестування з LM Studio

- [x] Встановити `open-interpreter`
- [x] Створити `functions/tools_open_interpreter.py`
  - `oi_execute_with_healing(code, task_description, auto_run=True)`
  - Налаштувати на локальний LM Studio, щоб не використовувати OpenAI API
- [x] Додати `OI_ENABLED` (bool, default=False) у `SETTINGS_SCHEMA`
- [x] Інтегрувати fallback в `execute_python` при `ModuleNotFoundError` (aaa_execute_python.py)
- [x] Тест: `tests/test_tools_open_interpreter.py` (9/9 pass)
- [ ] Виконано (10.05.2026) - потребує реального тестування
**Оцінка:** ~120 рядків + інтеграція

**Використання:**
1. Увімкнути `OI_ENABLED=True` в налаштуваннях GUI
2. Запустити LM Studio на `http://localhost:1234`
3. Коли execute_python зустрічає `ModuleNotFoundError`, OI автоматично встановить модуль

### P1: Windows automation



- [ ] Доробити accessibility-шар

  - Статус: Не розпочато

  - Пріоритет: P1

  - Деталі:

    - Завершити `uia_list_elements`, `uia_find_button`, `uia_click_element`, `uia_set_text`

    - Покрити це smoke-тестами на Windows



- [ ] Додати Windows CI / smoke suite

  - Статус: Не розпочато

  - Пріоритет: P1

  - Деталі:

    - Додати окремий workflow або nightly job

    - Мінімум для `tools_window_manager`, `tools_screen_capture`, `tools_mouse_keyboard`, `tools_ui_accessibility`



### P1: Оркестрація (кілька агентів)



- [ ] Створити router для вибору агента

  - Статус: Не розпочато

  - Пріоритет: P1

  - Деталі:

    - Meta-agent вирішує хто виконує (local vs API)

    - Коли передати іншому провайдеру

    - Вирішує на основі типу задачі (gui/code/web/desktop)



### P1: GUI ПОКРАЩЕННЯ ТА НАЛАШТУВАННЯ

#### Chunked streaming для LLM відповідей (40-80 токенів)

- [ ] Реалізувати chunked streaming в GUI для LLM відповідей

  - Пріоритет: P1

  - Файли: `core_streaming.py`, `core_gui/chat_panel.py`, `core_gui_pyqt6/chat_panel_qt.py`

  - Деталі:

    - Вивід від LLM має бути по 40-80 токенів (chunked streaming)

    - Замість повного виводу всієї відповіді — виводити частинами по 40-80 токенів

    - Це дає кращий UX: користувач бачить прогрес генерації в реальному часі

    - Реалізувати в `core_streaming.py` — додати параметр `chunk_size` (за замовчуванням 60 токенів)

    - GUI має обробляти chunks і додавати їх до чату поступово

    - Логування: `[Streaming] Chunk {i}: {tokens} tokens`

  - Тести:

    - Перевірити що chunks виводяться по 40-80 токенів

    - Перевірити що GUI оновлюється поступово

    - Перевірити що повна відповідь збирається коректно

#### Обов'язкове тестування та логування GUI-функцій



- [ ] Створити стандарт для GUI-функцій: тест + логування

  - Пріоритет: P0

  - Деталі:

    - Будь-яка нова функція, пов'язана з чатом, введенням тексту або іншими GUI-елементами, має бути протестована автоматичним тестом для GUI

    - Функція має створюватися із логуванням з самого початку

    - Тест має включати сценарій для запуску і перевірки даної функції

    - Додати в `docs/tests.md` інструкцію: "Стандарт розробки GUI-функцій"

    - Додати чек-лист в `docs/CONTRIBUTING.md` (якщо є) або створити



#### Авто озвучення відповіді (TTS) - чекбокс на головному екрані



- [ ] Додати чекбокс "🔊 Озвучувати відповіді" на головному екрані чату

  - Пріоритет: P1

  - Файли: `core_gui_pyqt6/main_window.py`, `core_gui_pyqt6/chat_panel_qt.py`

  - Деталі:

    - Чекбокс в control_frame поруч з кнопками STT/Agent/Send

    - Встановлений: TTS вмикається навіть якщо в загальних налаштуваннях вимкнено

    - Знятий: TTS вимикається навіть якщо в загальних налаштуваннях ввімкнено

    - Зберігається в runtime налаштуваннях (не персистентно, для відладки)

    - Логування: `[GUI] TTS override: enabled/disabled`

    - Інтеграція з `logic_tts.py` — перевіряти чекбокс перед викликом TTS



- [ ] Автоматичний тест для TTS чекбокса

  - Пріоритет: P1

  - Файл: `tests/test_tts_checkbox.py`

  - Деталі:

    - Запуск GUI, натискання чекбокса, перевірка що TTS оверрайд працює

    - Перевірка логування



**Оцінка:** ~80 нових рядків + ~50 змін. Складність: низька.



#### Керування вводом (STT) - чекбокс на головному екрані



- [ ] Додати чекбокс "🎙 Голосовий ввід" на головному екрані чату

  - Пріоритет: P1

  - Файли: `core_gui_pyqt6/main_window.py`, `core_gui_pyqt6/chat_panel_qt.py`

  - Деталі:

    - Чекбокс в control_frame поруч з кнопкою STT

    - Встановлений: STT вмикається навіть якщо в загальних налаштуваннях вимкнено

    - Знятий: STT вимикається навіть якщо в загальних налаштуваннях ввімкнено

    - Зберігається в runtime налаштуваннях (не персистентно, для відладки)

    - Логування: `[GUI] STT override: enabled/disabled`

    - Інтеграція з `core_stt_listener.py` — перевіряти чекбокс перед запуском STT



- [ ] Автоматичний тест для STT чекбокса

  - Пріоритет: P1

  - Файл: `tests/test_stt_checkbox.py`

  - Деталі:

    - Запуск GUI, натискання чекбокса, перевірка що STT оверрайд працює

    - Перевірка логування



**Оцінка:** ~80 нових рядків + ~50 змін. Складність: низька.



#### Керування геометрією вікна в налаштуваннях



- [ ] Додати налаштування геометрії вікна (позиція + розміри)

  - Пріоритет: P1

  - Файли: `core_gui_pyqt6/settings_tab_qt.py`, `core_gui_pyqt6/main_window.py`, `SETTINGS_SCHEMA`

  - Деталі:

    - Додати новий акордеон "Вікно" в налаштуваннях GUI

    - Поля:

      - `GUI_WINDOW_X` (int, default: None) — позиція X при старті

      - `GUI_WINDOW_Y` (int, default: None) — позиція Y при старті

      - `GUI_WINDOW_WIDTH` (int, default: 1200) — ширина при старті

      - `GUI_WINDOW_HEIGHT` (int, default: 800) — висота при старті

      - `GUI_WINDOW_MAXIMIZED` (bool, default: False) — чи відкривати в повноекранному режимі

      - `GUI_SAVE_GEOMETRY` (bool, default: True) — чи зберігати геометрію при закритті

    - При закритті вікна: зберігати поточну геометрію в налаштуваннях (якщо `GUI_SAVE_GEOMETRY=True`)

    - При відкритті вікна: відновлювати геометрію з налаштувань

    - Логування: `[GUI] Window geometry restored: x={x}, y={y}, w={w}, h={h}`



- [ ] Автоматичний тест для геометрії вікна

  - Пріоритет: P1

  - Файл: `tests/test_window_geometry.py`

  - Деталі:

    - Встановити налаштування геометрії, відкрити GUI, перевірити позицію/розміри

    - Закрити GUI, перевірити що геометрія збереглась

    - Перевірка логування



**Оцінка:** ~150 нових рядків + ~100 змін. Складність: середня.



#### Реорганізація вікна налаштувань



- [ ] Проаналізувати і покращити структуру вікна налаштувань

  - Пріоритет: P2

  - Файли: `core_gui_pyqt6/settings_tab_qt.py`

  - Деталі:

    - Проаналізувати поточні акордеони та поля

    - Групувати пов'язані налаштування логічніше

    - Додати пошук по налаштуваннях (QLineEdit з фільтрацією)

    - Додати кнопку "Скинути до дефолтів" для кожного акордеона

    - Додати tooltips з описом кожного налаштування

    - Розглянути використання QFormLayout замість QVBoxLayout для кращого вирівнювання



- [ ] Документація нової структури

  - Пріоритет: P2

  - Файл: `TASKS.md` або окремий `docs/SETTINGS_GUIDE.md`

  - Деталі:

    - Опис всіх акордеонів та полів

    - Пояснення що робить кожне налаштування

    - Рекомендовані значення для різних сценаріїв



**Оцінка:** ~200-300 нових рядків + ~150 змін. Складність: середня.



#### Відображення вкладки "План" - показувати/приховувати



- [ ] Додати налаштування показу вкладки "План"

  - Пріоритет: P1

  - Файли: `core_gui_pyqt6/main_window.py`, `core_gui_pyqt6/plan_panel_qt.py`, `SETTINGS_SCHEMA`

  - Деталі:

    - Додати налаштування `GUI_SHOW_PLAN_TAB` (bool, default: True) в SETTINGS_SCHEMA

    - Якщо `False`: вкладка "План" приховується (QTabWidget.removeTab або setVisible(False))

    - Якщо `True`: вкладка "План" показується

    - Додати чекбокс "Показувати вкладку План" в налаштуваннях GUI (акордеон "Вікно")

    - Логування: `[GUI] Plan tab visibility: shown/hidden`



- [ ] Автоматичний тест для вкладки План

  - Пріоритет: P1

  - Файл: `tests/test_plan_tab_visibility.py`

  - Деталі:

    - Встановити `GUI_SHOW_PLAN_TAB=False`, відкрити GUI, перевірити що вкладка прихована

    - Змінити на True, перевірити що вкладка з'явилась

    - Перевірка логування



**Оцінка:** ~60 нових рядків + ~40 змін. Складність: низька.



#### Доцільність блоку "План" (низький пріоритет)



- [ ] Оцінити доцільність вкладки "План" після підключення нового планера

  - Пріоритет: P3

  - Деталі:

    - Після повного підключення і відтестованого нового планера (AgentLoop)

    - Проаналізувати чи потрібна вкладка "План" в GUI

    - Якщо AgentLoop показує прогрес в чаті — можливо вкладка не потрібна

    - Якщо планер генерує складні багатокрокові плани — вкладка може бути корисною

    - Зробити висновок і оновити TASKS.md



**Оцінка:** Аналіз, без коду.



---



### P1: Міграція GUI на PyQt6 — DONE ✅



**Виконані етапи перенесено в TASKS_Done.md**



---



## Заплановано



### P2: GUI поліпшення



- [x] Додати динамічне збільшення вікна вводу в новому GUI (PyQt6)

  - Статус: Завершено (08.05.2026)

  - Пріоритет: P2

  - Деталі:

    - Поле вводу в PyQt6 має автоматично збільшувати висоту при наборі тексту

    - Мінімальна висота: 2-3 рядки (60px)

    - Максимальна висота: 6-8 рядків (160px)

    - Реалізовано через QTextEdit з динамічним resize

  - Файли:

    - `core_gui_pyqt6/main_window.py` - додано `_update_input_height()` метод

    - `tests/test_pyqt6_gui.py` - додано `TestDynamicInputHeight` клас з 5 тестами



- [ ] Додати відсутній стиль `StopMic.TButton`

  - Статус: Не розпочато

  - Пріоритет: P2

  - Деталі:

    - Стиль `StopMic.TButton` використовується для `stop_mic_button` у `core_gui/main_window.py`, але не визначений у `core_gui/styles.py`

    - Призводить до використання дефолтного стилю замість червоного "stop"

    - Додати в `styles.py` після `MicRecording.TButton`



- [ ] Прибрати дублювання повідомлень і сирий JSON у чаті

  - Статус: Не розпочато

  - Пріоритет: P2

  - Деталі:

    - Зараз некоректний сценарій:

      - `👑 ВИ: привіт`

      - `👑 ВИ: привіт`

      - `⚡ МАРК: {"response": "..."}`

      - `⚡ МАРК: ...`

    - Потрібний сценарій:

      - `👑 ВИ: привіт`

      - `⚡ МАРК: Вітаю. Я готовий до роботи. Яку задачу потрібно виконати?`

    - Прибрати дубль user-message в GUI pipeline

    - Не показувати сирий JSON, якщо з нього вже витягнуто `response`

    - Перевірити обидва GUI-шляхи: Tkinter і PyQt6



### P2: Архітектурна маса



- [ ] Вирівняти runtime-дані

  - Статус: Не розпочато

  - Пріоритет: P2

  - Деталі:

    - Усі stateful JSON/логи/кеші тримати в `runtime/` або `logs/`

    - Не зберігати робочі артефакти в `functions/`



- [ ] Зменшити зв'язність між tool / GUI / planning шарами

  - Статус: Не розпочато

  - Пріоритет: P2

  - Деталі:

    - Розрізати циклічні або напівциклічні залежності між screen/input/accessibility шарами

    - Винести спільні абстракції для координат / прямокутників / результатів дій

    - Підготувати ґрунт для подальшого рефакторингу без "великого вибуху"



- [ ] Поступовий рефакторинг структури

  - Статус: Не розпочато

  - Пріоритет: P2

  - Деталі:

    - Не починати з масового перенесення файлів

    - Спершу стабілізувати API й вирізати великі вузли відповідальності

    - Лише потім групувати модулі по підсистемах



---



## Правила ведення цього файлу



- Тут лише **актуальні задачі**, без довгих історичних фаз і PR-хронології.

- Виконані завдання перенесено в [TASKS_Done.md](TASKS_Done.md).

- `status.md` відповідає на питання **"де ми зараз?"**

- `TASKS.md` відповідає на питання **"що робимо далі?"**

- `docs/ARCHITECTURE.md` відповідає на питання **"чому саме так і в якому технічному порядку?"**Іконка мертва і не показує жодного статусу.





---



## Примітки



- Пріоритети: `P0` > `P1` > `P2`

- Статуси: `Завершено` > `В процесі` > `Не розпочато`

