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

# Аналіз і план переробки GUI

## Що є зараз

З коду видно що поточний `MainWindowPyQt6` — монолітний клас (~600+ рядків) з міксинами:
- `ChatPanelQtMixin` — чат
- `PlanPanelQtMixin` — панель плану
- `SettingsTabQtMixin` — налаштування
- `ConfirmationQtMixin` — підтвердження

Все в одному вікні, без чіткої вкладкової структури для логів, статистики, інструментів.

## Що треба зробити

Переробити GUI зберігши весь існуючий функціонал але додавши нові вкладки і модульну структуру.

---

# Завдання для агента: Переробка GUI МАРК на модульну вкладкову структуру

## Цільова структура вкладок

1. **Чат** — існуючий чат (перенести з `ChatPanelQtMixin`)
2. **План** — існуюча панель плану (з `PlanPanelQtMixin`)
3. **Логи** — новий таб з таблицею логів з файлів `runtime/logs/`
4. **Статистика** — новий таб з метриками (токени, запити, час відповіді)
5. **Інструменти** — новий таб зі списком зареєстрованих інструментів з `FunctionRegistry`
6. **Налаштування** — існуючий таб (з `SettingsTabQtMixin`)

## Цільова файлова структура

```
core_gui_pyqt6/
├── __init__.py
├── main_window.py          # тільки оркестрація, мінімум коду
├── constants.py            # кольори, розміри, версія — НОВИЙ
├── base_tab.py             # BaseTab базовий клас — НОВИЙ
├── tab_chat.py             # ChatTab — перенести з chat_panel_qt.py
├── tab_plan.py             # PlanTab — перенести з plan_panel_qt.py
├── tab_logs.py             # LogsTab — НОВИЙ
├── tab_stats.py            # StatsTab — НОВИЙ
├── tab_tools.py            # ToolsTab — НОВИЙ
├── tab_settings.py         # SettingsTab — перенести з settings_tab_qt.py
├── confirmation_qt.py      # без змін
└── llm_endpoints_editor_qt.py  # без змін
```

---

## Кроки виконання

### Крок 1 — Створити `constants.py`

- [x] Створити `core_gui_pyqt6/constants.py` з константами:
  - `APP_VERSION = "1.0.0"`, `APP_NAME = "МАРК"`
  - Кольори ролей чату: `COLOR_USER`, `COLOR_ASSISTANT`, `COLOR_SYSTEM`
  - Кольори рівнів логів: `COLOR_DEBUG`, `COLOR_INFO`, `COLOR_WARNING`, `COLOR_ERROR`
  - Розміри: `INPUT_MIN_HEIGHT`, `INPUT_MAX_HEIGHT`
- [x] Відмітити виконання в TASK.md

### Крок 2 — Створити `base_tab.py`

- [x] Створити `core_gui_pyqt6/base_tab.py` з класом `BaseTab(QWidget)`:
  - Метод `setup_ui(self)` — абстрактний, реалізується в кожній вкладці
  - Метод `refresh(self)` — для оновлення даних вкладки при переключенні
  - Метод `get_title(self) -> str` — назва вкладки
- [x] Відмітити виконання в TASK.md

### Крок 3 — Створити `tab_chat.py`

- [x] Перенести логіку з `ChatPanelQtMixin` в клас `ChatTab(BaseTab)`
- [x] Зберегти всі публічні методи: `add_message()`, `start_stream_message()`, `append_stream_chunk()`, `end_stream_message()`, `focus_input()`
- [x] Сигнал `command_submitted = pyqtSignal(str)` для передачі команди з поля вводу
- [x] Кольори ролей брати з `constants.py`
- [x] Відмітити виконання в TASK.md

### Крок 4 — Створити `tab_plan.py`

- [x] Перенести логіку з `PlanPanelQtMixin` в клас `PlanTab(BaseTab)`
- [x] Зберегти всі публічні методи: `show_plan_panel()`, `update_plan_step()`, `finish_plan_panel()`
- [x] Відмітити виконання в TASK.md

### Крок 5 — Створити `tab_logs.py`

- [x] Створити `LogsTab(BaseTab)` з `QTableWidget` колонками: Час, Рівень, Модуль, Повідомлення
- [x] Фільтр по рівню (`QComboBox`: ALL / DEBUG / INFO / WARNING / ERROR)
- [x] Поле пошуку `QLineEdit` для фільтрації по тексту
- [x] Кнопка "Очистити" і кнопка "Оновити" (читати з `runtime/logs/`)
- [x] Метод `add_log_entry(level, module, message)` для додавання рядків програмно
- [x] Кольори рядків залежно від рівня — з `constants.py`
- [x] Відмітити виконання в TASK.md

### Крок 6 — Створити `tab_stats.py`

- [x] Створити `StatsTab(BaseTab)` з метриками:
  - Загальна кількість запитів до LLM
  - Загальна кількість токенів (prompt + completion)
  - Середній час відповіді LLM
  - Кількість виконаних планів / кроків агента
- [x] `QProgressBar` для показу використання контексту (якщо доступно)
- [x] Кнопка "Оновити" яка читає дані з `SessionBudget` або логів
- [x] Метод `update_stats(stats: dict)` для оновлення з ядра
- [x] Відмітити виконання в TASK.md

### Крок 7 — Створити `tab_tools.py`

- [x] Створити `ToolsTab(BaseTab)` з `QTableWidget` колонками: Назва, Опис, Ризик, Статус
- [x] Завантажувати список інструментів з `FunctionRegistry` при відкритті вкладки
- [x] Кнопка "Оновити список"
- [x] Кнопка "Виконати" для вибраного інструменту (відкриває діалог з параметрами)
- [x] Колонка Ризик показує `get_tool_risk(action)` з `core_tool_runtime`
- [x] Відмітити виконання в TASK.md

### Крок 8 — Перенести `tab_settings.py`

- [x] Перенести логіку з `SettingsTabQtMixin` в клас `SettingsTab(BaseTab)`
- [x] Зберегти весь існуючий функціонал (lazy build, фільтр, збереження)
- [x] Налаштування зберігати через `QSettings` де можливо
- [x] Відмітити виконання в TASK.md

### Крок 9 — Переписати `main_window.py`

- [x] `MainWindowPyQt6` більше не наслідує міксини — тільки `QMainWindow`
- [x] Створює `QTabWidget` і додає всі 6 вкладок
- [x] Статус-бар внизу з версією програми з `constants.APP_VERSION`
- [x] Делегує виклики відповідним вкладкам: `add_message()` → `chat_tab.add_message()`
- [x] Зберігає зворотну сумісність публічного API для `run_assistant_qt.py`
- [x] Потокобезпечна черга повідомлень через Qt signal залишається
- [x] Відмітити виконання в TASK.md

### Крок 10 — Перевірка

- [x] Запустити `python run.py --qt` через venv
- [x] Перевірити що всі 6 вкладок відкриваються
- [x] Надіслати тестову команду — перевірити чат і логи
- [x] Перевірити вкладку Інструменти — список завантажується
- [x] Перевірити вкладку Налаштування — зберігання працює
- [x] Запустити `python -m pytest tests/test_pyqt6_gui.py -v` — **23 passed**
- [x] Відмітити виконання в TASK.md


Агент правильно проаналізував код і план виглядає добре. Ось уточнення:

---

## Уточнення до плану переробки GUI

### 1. Порядок виконання — суворо послідовний

Кроки 1→2→3→4→5→6→7→8→9→10 виконувати **по одному**. Не починати наступний крок поки попередній не перевірений і запускається без помилок.

### 2. Зворотна сумісність — критично

`run_assistant_qt.py` не чіпати. Публічний API `MainWindowPyQt6` зберегти повністю — всі методи що викликаються з `run_assistant_qt.py`:
- `add_message()`, `start_stream_message()`, `append_stream_chunk()`, `end_stream_message()`
- `update_progress()`, `show_stop_button()`, `hide_stop_button()`
- `show_plan_panel()`, `update_plan_step()`, `finish_plan_panel()`
- `show_confirmation()`, `queue_message()`, `set_assistant()`, `set_stt_controller()`, `run()`

Всі вони залишаються в `MainWindowPyQt6` але **делегують** до відповідних вкладок.

### 3. Міксини після перенесення

Старі файли `chat_panel_qt.py`, `plan_panel_qt.py`, `settings_tab_qt.py` — **не видаляти одразу**. Спочатку переконатись що новий код працює, тоді видалити. Щоб не ламати імпорти в тестах — перевірити `tests/test_pyqt6_gui.py` що він не імпортує міксини напряму.

### 4. Закоментований план-код

В `main_window.py` рядки 195-221 — розкоментувати і перенести в `tab_plan.py`. Це пріоритет, бо панель плану зараз фактично не відображається.

### 5. Логи — читати реальні файли

`tab_logs.py` має читати з `runtime/logs/` якщо там є `.log` або `.jsonl` файли. Якщо файл не знайдено — показати порожню таблицю без помилки. Метод `add_log_entry()` також підписати на Python `logging` через `QueueHandler` щоб логи з ядра потрапляли в таблицю в реальному часі.

### 6. Статистика — реальні дані

`tab_stats.py` читає з `SessionBudget.snapshot()` якщо доступний, або з `runtime/logs/` як fallback. Не хардкодити нулі — показувати реальний стан або прочерк якщо дані недоступні.

### 7. Вкладка Інструменти — тільки читання

`tab_tools.py` — кнопку "Виконати" зробити але при натисканні показувати `QMessageBox` з повідомленням `"Введіть команду в чаті"`. Повне виконання інструментів через GUI — окреме завдання на майбутнє.

### 8. Тести

Перед початком запустити `pytest tests/test_pyqt6_gui.py -v` щоб знати базовий стан. Після кожного кроку — знову запускати тести. Якщо тест впав через рефакторинг — виправити одразу, не накопичувати.

### 9. `confirmation_qt.py` — мінімальна зміна

Залишити `ConfirmationDialog` як є. `ConfirmationQtMixin` — залишити теж (або перенести логіку в `main_window.py` напряму). Не витрачати час на рефакторинг цього файлу — він маленький і не заважає.

### 10. Після завершення

Оновити `core_gui_pyqt6/__init__.py` щоб експортував `MainWindowPyQt6` з нового `main_window.py`. Перевірити `python run.py --qt` — програма запускається, всі 6 вкладок видно, чат працює.


## FEATURE: Context Window Status Bar

### Задача 1: Підключити UsageInfo до SessionBudget
- [x] Заповнювати `UsageInfo.prompt_tokens` + `completion_tokens` з реального API response в `providers_openai_compatible.py` — ✅ було готово (див. `_parse_success()`, рядки 268-273)
- [x] Заповнювати `UsageInfo` в `providers_anthropic.py` — ✅ було готово (рядки 101-114)
- [x] Заповнювати `UsageInfo` в `providers_google.py` — ✅ було готово (рядки 98-111)
- [x] Передавати `usage` в `SessionBudget.record_tokens()` після кожного `chat()` виклику — ✅ додано `budget=` параметр в `ProviderRegistry.chat()` (центральний хаб усіх LLM-викликів). При `budget` не `None` і `resp.ok` — записуються `total_tokens` та `cost_usd`
- [x] Перевірити: `SessionBudget.usage.tokens > 0` після будь-якого LLM виклику — ✅ написано 7 інтеграційних тестів (`tests/test_providers_budget_integration.py`), всі проходять
- [x] Відмітити виконання в TASK.md

---

### Задача 2: Знати ліміт контексту активної моделі
- [x] Скласти словник відомих моделей → `max_context_tokens` в `endpoint_client.py`
- [x] Реалізувати `get_model_context_limit(model_name) -> int`
- [x] Для локальних моделей читати ліміт з `/v1/models` або з `config` — `fetch_local_model_context_limit()`
- [x] Зберігати `active_model` + його ліміт в `SettingsManager`
- [x] Перевірити: функція повертає коректне значення для відомих моделей — 51 тест, всі пройдено

---

### Задача 3: ContextController → пробрасувати токени назовні
- [x] Додати property `context_tokens_used -> int` в `context_controller.py`
- [x] `AgentLoop` читає `context_tokens_used` після кожного кроку
- [x] `AgentLoop` надсилає `gui_msg` типу `"context_update": {"used": N, "limit": M, "model": "..."}`
- [x] Перевірити: повідомлення `context_update` приходить в GUI після кожного кроку — ✅ додано обробник `context_update` в `MainWindowPyQt6._on_message()`, дані передаються в `StatsTab.update_stats()`
- [x] Відмітити виконання в TASK.md

---

### Задача 4: GUI — окремий статус-бар контексту
- [x] Додати `QProgressBar` тонка лінія `~6px` під чат-панеллю або над полем вводу в `main_window.py`
- [x] Реалізувати логіку кольору: `0-60%` зелений, `60-80%` жовтий, `80-95%` помаранчевий, `95%+` червоний
- [x] Додати tooltip: `"12 450 / 200 000 tokens (claude-sonnet-4-6)"`
- [x] Підключити оновлення через `_on_message()` при отриманні `"context_update"`
- [x] Скидати бар до `0` при старті нової задачі
- [x] Перевірити: бар видно, заповнюється, міняє колір
- [x] Відмітити виконання в TASK.md

---

### Задача 5: Стрімінг — підрахунок токенів у реальному часі
- [x] Створити `functions/llm/streaming_buffer.py` з класом `StreamingBuffer`
- [x] Додати грубу оцінку токенів `chars // 4` в `StreamingBuffer.add_chunk()` для live-оновлення бару
- [x] Додати `StreamingBuffer.finish(real_usage)` — заміна оцінки на реальне `usage` після стрімінгу
- [x] Підключити `StreamingBuffer` в `MainWindowPyQt6.__init__()` з callbacks `_on_streaming_status` та `_on_streaming_context_update`
- [x] Інтегрувати `StreamingBuffer` в `append_stream_chunk()` — кожен чанк оновлює прогрес-бар контексту
- [x] При `stream_start` автоматично встановлювати ліміти контексту з `get_model_context_limit()`
- [x] Підключити `usage_callback` в `stream_groq_sdk()` в `groq_client.py` для отримання реального usage після стріму
- [x] Експортувати `StreamingBuffer` з `functions/llm/__init__.py`
- [x] Перевірити: бар поступово заповнюється під час стрімінгу
- [x] Відмітити виконання в TASK.md

Ось точний і детальний план для агента кодування, сформований на основі аналізу наданого контексту архітектури та виявлених проблем проєкту.

---

### Етап 1: Найвищий пріоритет — Стабілізація Trunk та ліквідація критичних помилок

1.1. **Полагодити trunk stability**

* Повернути повну сумісність між тестами й модулем `logic_task_runner`.
* Добитися, щоб `pytest` повністю та без помилок проходив етап збору тестів (collection).
* Однозначно зафіксувати публічні API.
* [x] **Виконано 24.05.2026:**
  * Додано імпорт `Callable` в `logic_task_runner.py`
  * Створено відсутній модуль `functions/tools/tools_windsurf.py` (SnapshotFn, WindowFinder, WindsurfState, WindsurfWindow, diff_snapshots)
  * pytest collection: 1396 tests, 0 errors

1.2. **Виправити AgentLoop JSON parsing**

* Усунути зациклення, які виникають через те, що LLM генерує некоректний JSON.
* Впровадити покращений механізм парсингу з обов'язковим fallback-режимом (або перемиканням на сильнішу модель).
* [x] **Виконано 24.05.2026:**
  * `decide()` більше не викидає `ValueError` назовні — завжди повертає `AgentAction`
  * Додано `_consecutive_json_failures` трекінг — після N=5 невдач force `done`
  * Додано подвійний fallback: JSON parsing → function-calling (tool_choice="auto") → take_screenshot/done
  * Рефакторинг: `_parse_json_from_content`, `_try_with_tools`, `_json_failure_fallback` окремі методи
  * Збережено очищення `<think>` блоків, markdown code blocks, brace matching

1.3. **Створити Skills (абстракції над базовими діями)**

* Реалізувати базові високорівневі функції: `open_browser()`, `search_google()`, `fill_form()`.
* Створити архітектуру для накопичуваної бази навичок агента.
* [x] **Виконано 24.05.2026:**
  * `functions/skills/` пакет з модульною архітектурою:
    * `base.py` — `BaseSkill`, `SkillResult`, `SkillError`
    * `registry.py` — `SkillRegistry` з реєстрацією/пошуком/списком skills
    * `browser_skills.py` — `OpenBrowser`, `SearchGoogle`, `FillForm` (з fallback ланцюжком: playwright → CDP → subprocess)
  * Кожен skill має: name, description, асинхронний `execute()`, логування

---

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

3.1. **Рефакторинг `main.py**`

* Розділити перевантажений файл `main.py` (1242 рядки), який зараз несе забагато відповідальностей (state, app initialization, runtime wiring), на окремі ізольовані модулі.


* [ ] Відмітити виконання в TASK.md

3.2. **Рефакторинг `agent_loop.py**`

* Розрізати файл `agent_loop.py` (2008 рядків) на менші логічні компоненти з чітко визначеною зоною відповідальності.


* [ ] Відмітити виконання в TASK.md

3.3. **Рефакторинг `logic_permission_gate.py` та `logic_core.py**`

* Оптимізувати 4-рівневу policy stack у `logic_permission_gate.py` (~397 рядків) та усунути дублювання з `logic_expectations.py`.


* Зменшити зв'язність у `logic_core.py`: розвантажити `FunctionRegistry` та винести ~200 рядків хардкодженого тексту з методу `get_system_prompt()`.


* [ ] Відмітити виконання в TASK.md

3.4. **Рефакторинг `logic_commands.py` та `global_voice_input.py**`

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

### FEATURE: Уточнення неоднозначних команд

**Ціль:** Якщо команда неоднозначна (наприклад: "відкрий", "подивися код", "зроби це") — запитати уточнення до відправки в LLM.

- [x] Проаналізувати `process_command()` — pre-check відсутній, всі команди йдуть до LLM
- [x] Визначити критерії неоднозначності: дієслово без об'єкта, вказівні займенники, "код/проект" без вказівки
- [x] Реалізувати `needs_clarification()` в `commands_planner.py`
- [x] Підключити перевірку в `process_command()` перед LLM-маршрутом
- [x] Реалізувати `_pending_clarification` — збереження контексту + об'єднання з уточненням
- [x] Створити тести (7 тестів, всі пройдено)
- [x] Виправити зациклення: `_skip_clarification` флаг після об'єднання
- [x] Виправити патерни `_AMBIGUOUS_PROJECT_PATTERNS` — додано `$` для точного збігу
- [x] Прибрати дублювання user-повідомлень та мітку "неоднозначна команда"
- [x] Додати тести на виправлене зациклення (5 тестів)

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

### ПЕРЕРОБКА ВКЛАДКИ ЛОГИ (tab_logs.py) — 24.05.2026

- [x] `_load_from_files()` обмежено до 50 останніх записів (читання з кінця файлу через `_read_tail()`)
- [x] `refresh()` прибрано автозавантаження — таблиця порожня з підказкою
- [x] Кнопка "Оновити" підключена до `_load_from_files()` з лімітом 50 записів
- [x] `_poll_log_queue()` додано rolling window: макс. 50 рядків, найстаріші видаляються
- [x] Додано `_placeholder_label` з текстом "Натисніть 'Оновити' щоб завантажити останні 50 записів"
- [x] Вкладка відкривається миттєво без зависання

### ПЕРЕРОБКА ВКЛАДКИ НАЛАШТУВАННЯ (tab_settings.py) — 24.05.2026

- [x] Layout перероблено на `QSplitter` з лівою панеллю (QListWidget, ~160px) + права панель (QScrollArea)
- [x] Категорії визначено з реального `SETTINGS_SCHEMA`: Асистент, Безпека, Продуктивність, LLM, LLM Моделі, Розпізнавання мови, Vision-LM, Аудіо, Озвучення, GUI, Global Voice Input, Аудіо-фільтри
- [x] Іконки категорій (опційно) в `CATEGORY_ICONS`
- [x] Рядок пошуку `QLineEdit` зверху над лівою панеллю — фільтрує по всіх категоріях, показує результати в правій панелі
- [x] При кліку на категорію — права панель будує контент (lazy build, кешування в `_category_widgets`)
- [x] За замовчуванням при відкритті — перша категорія вибрана
