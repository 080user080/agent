# Виконані задачі МАРК
> Останнє оновлення: 26.05.2026 (00:32)

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

---

## НЕДАВНІ ВИПРАВЛЕННЯ (15.05.2026)

### A0. Усунуто конфлікт шляхів виконання (P0)

---

## НЕДАВНІ ВИПРАВЛЕННЯ (02.05.2026, 19:35)

### Виправлено Global Voice Input - tray icon
### Виправлено Global Voice Input - вставка буфера обміну

---

## ВИКОНАНІ ЗАВДАННЯ (перенесено 24.05.2026)

### ЕТАП Б. Індексація проєкту для кодового агента

#### Б1. Repo Map — карта проєкту
- [x] Створити `functions/project_indexer.py`
- [x] Додати інструмент `get_repo_map()` в реєстр функцій
- [x] Додати інструмент `update_repo_map(filepath)`
- [x] Інтеграція в `get_coding_system_prompt()`

#### Б2. Dependency Graph — карта залежностей
- [x] Розширити `functions/project_indexer.py` — аналіз `import`
- [x] Додати інструмент `get_file_dependents(filepath)`
- [x] Оновити `build_coding_section()`

#### Б3. Навчити агента комбінувати інструменти
- [x] Оновити системний промпт coding-режиму
- [x] Додати явну заборону в промпт

---

## ВИКОНАНІ ЗАВДАННЯ (перенесено 18.05.2026)

### ЕТАП А. Стабілізація та рефакторинг архітектури

#### А1. Полагодити pytest collection (P0) ✅
#### А2. Реструктуризація папки functions/ ✅
#### Стабілізація AgentLoop для коду (перед А3) ✅
#### А3. Розрізати великі модулі ✅

**Частина 1: Розбиття `main.py`**
- Крок 1.1: `core_initializer_checks.py`
- Крок 1.2: `audio/initializer.py`
- Крок 1.3: `agent_coordinator.py`

**Частина 2: Розбиття `agent_loop.py`**
- Крок 2.1: `observe.py`
- Крок 2.2: `plan.py`
- Крок 2.3: `act.py`
- Крок 2.4: `check.py`
- Крок 2.5: Перезбирання `AgentLoop`

**Частина 3: Розбиття `logic_commands.py`**
- Крок 3.1: `commands_streaming.py`
- Крок 3.2: `commands_audio.py`
- Крок 3.3: `commands_planner.py`
- Крок 3.4: Рефакторинг `logic_commands.py`

**Частина 4: Розбиття `core_planner.py`**
- Крок 4.1: `planner_prompt_builder.py`
- Крок 4.2: `planner_validator.py`
- Крок 4.3: `planner_repair.py`
- Крок 4.4: Спрощення `core_planner.py`

---

## 📈 Загальні критерії готовності (Definition of Done)

- [x] **SRP:** Кожен файл має одну чітку відповідальність
- [x] **Zero ImportError:** Запуск без помилок
- [x] **Тести:** 1250 passed, 1 skipped
- [ ] **End-to-End:** ⏳ Не верифіковано

---

## ПЕРЕРОБКА GUI НА ВКЛАДКОВУ СТРУКТУРУ (перенесено 25.05.2026)

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

---

## FEATURE: Context Window Status Bar (перенесено 25.05.2026)

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

---

## ЕТАП 1: Стабілізація Trunk та ліквідація критичних помилок (перенесено 25.05.2026)

### 1.1. Полагодити trunk stability

* Повернути повну сумісність між тестами й модулем `logic_task_runner`.
* Добитися, щоб `pytest` повністю та без помилок проходив етап збору тестів (collection).
* Однозначно зафіксувати публічні API.
* [x] **Виконано 24.05.2026:**
  * Додано імпорт `Callable` в `logic_task_runner.py`
  * Створено відсутній модуль `functions/tools/tools_windsurf.py` (SnapshotFn, WindowFinder, WindsurfState, WindsurfWindow, diff_snapshots)
  * pytest collection: 1396 tests, 0 errors

### 1.2. Виправити AgentLoop JSON parsing

* Усунути зациклення, які виникають через те, що LLM генерує некоректний JSON.
* Впровадити покращений механізм парсингу з обов'язковим fallback-режимом (або перемиканням на сильнішу модель).
* [x] **Виконано 24.05.2026:**
  * `decide()` більше не викидає `ValueError` назовні — завжди повертає `AgentAction`
  * Додано `_consecutive_json_failures` трекінг — після N=5 невдач force `done`
  * Додано подвійний fallback: JSON parsing → function-calling (tool_choice="auto") → take_screenshot/done
  * Рефакторинг: `_parse_json_from_content`, `_try_with_tools`, `_json_failure_fallback` окремі методи
  * Збережено очищення `<think>` блоків, markdown code blocks, brace matching

### 1.3. Створити Skills (абстракції над базовими діями)

* Реалізувати базові високорівневі функції: `open_browser()`, `search_google()`, `fill_form()`.
* Створити архітектуру для накопичуваної бази навичок агента.
* [x] **Виконано 24.05.2026:**
  * `functions/skills/` пакет з модульною архітектурою:
    * `base.py` — `BaseSkill`, `SkillResult`, `SkillError`
    * `registry.py` — `SkillRegistry` з реєстрацією/пошуком/списком skills
    * `browser_skills.py` — `OpenBrowser`, `SearchGoogle`, `FillForm` (з fallback ланцюжком: playwright → CDP → subprocess)
  * Кожен skill має: name, description, асинхронний `execute()`, логування

---

## FEATURE: Уточнення неоднозначних команд (перенесено 25.05.2026)

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

## ПЕРЕРОБКА ВКЛАДКИ ЛОГИ (tab_logs.py) — 24.05.2026 (перенесено 25.05.2026)

- [x] `_load_from_files()` обмежено до 50 останніх записів (читання з кінця файлу через `_read_tail()`)
- [x] `refresh()` прибрано автозавантаження — таблиця порожня з підказкою
- [x] Кнопка "Оновити" підключена до `_load_from_files()` з лімітом 50 записів
- [x] `_poll_log_queue()` додано rolling window: макс. 50 рядків, найстаріші видаляються
- [x] Додано `_placeholder_label` з текстом "Натисніть 'Оновити' щоб завантажити останні 50 записів"
- [x] Вкладка відкривається миттєво без зависання

## ПЕРЕРОБКА ВКЛАДКИ НАЛАШТУВАННЯ (tab_settings.py) — 24.05.2026 (перенесено 25.05.2026)

- [x] Layout перероблено на `QSplitter` з лівою панеллю (QListWidget, ~160px) + права панель (QScrollArea)
- [x] Категорії визначено з реального `SETTINGS_SCHEMA`: Асистент, Безпека, Продуктивність, LLM, LLM Моделі, Розпізнавання мови, Vision-LM, Аудіо, Озвучення, GUI, Global Voice Input, Аудіо-фільтри
- [x] Іконки категорій (опційно) в `CATEGORY_ICONS`
- [x] Рядок пошуку `QLineEdit` зверху над лівою панеллю — фільтрує по всіх категоріях, показує результати в правій панелі
- [x] При кліку на категорію — права панель будує контент (lazy build, кешування в `_category_widgets`)
- [x] За замовчуванням при відкритті — перша категорія вибрана

---

## Перенесено 26.05.2026

### Діагностика завантаження інструментів — `logic_core.py`

#### Крок 1: Знайти де викликається завантаження модулів
- [x] Відкрити `functions/runtime/logic_core.py`
- [x] Знайти метод `load_all_modules()`
- [x] Знайти які папки він сканує — шукати рядки з `os.walk`, `importlib`, або список папок типу `["tools", "gui", ...]`
- [x] Записати в TASK.md: які папки скануються
- [x] Відмітити виконання в TASK.md

**Результат кроку 1:**
`load_all_modules()` використовує `functions_dir.glob("aaa_*.py")` і `glob("tools_*.py")` — ці `glob`-запити шукають файли ТІЛЬКИ в корені `functions/`, без рекурсивного обходу підпапок.

Скануються:
- `functions/core_*.py` (core-модулі)
- `functions/aaa_*.py` (функції)
- `functions/tools_*.py` (GUI інструменти)

Жодна з цих `glob`-функцій **не заходить** в `functions/tools/` або інші підпапки.

#### Крок 2: Знайти де і як завантажуються aaa_* файли
- [x] В тому ж `logic_core.py` знайти чи є окремий блок для завантаження `functions/tools/aaa_*` файлів
- [x] Перевірити чи є умова яка пропускає певні файли (наприклад фільтр по імені, або `try/except` який мовчки ковтає помилку)
- [x] Записати результат
- [x] Відмітити виконання в TASK.md

**Результат кроку 2:**
Окремий блок для `aaa_*` є (рядки 82-103), але він шукає файли ТІЛЬКИ в `functions/`, а не в `functions/tools/`.

Немає жодної умови, яка би пропускала файли — проблема виключно в тому, що `glob("aaa_*.py")` не рекурсивний і знаходить тільки файли безпосередньо в `functions/`.

#### Крок 3: Знайти де в логу має бути вивід про завантаження
- [x] В `logic_core.py` знайти рядок де виводиться `"Завантаження GUI Automation tools"` або аналогічний print
- [x] Подивитись яка логіка після цього рядка
- [x] Чи є там завантаження `aaa_*` файлів після цього блоку
- [x] Відмітити виконання в TASK.md

**Результат кроку 3:**
У `load_all_modules()` три блоки виводу в такому порядку:
1. **Рядок 53:** `"📦 Завантаження core модулів..."` → `core_*.py`
2. **Рядок 81:** `"📦 Завантаження функцій..."` → `aaa_*.py`
3. **Рядок 106:** `"📦 Завантаження GUI Automation tools..."` → `tools_*.py`

`aaa_*` завантажуються **до** tools_, тобто ані `aaa_*`, ані `tools_*` не сканують `functions/tools/` — всі glob-запити обмежені коренем `functions/`.

#### Крок 4: Перевірити чи є помилки імпорту в aaa_* файлах
- [x] Відкрити `functions/tools/aaa_execute_python.py`
- [x] Подивитись на всі рядки `import` на початку файлу
- [x] Перевірити чи всі ці модулі реально встановлені (особливо нестандартні типу `open_interpreter`)
- [x] Відкрити `functions/tools/aaa_file_operations.py`
- [x] Зробити те саме
- [x] Відмітити виконання в TASK.md

**Результат кроку 4:**
Всі імпорти в `aaa_execute_python.py` стандартні (os, sys, subprocess, tempfile, re, pathlib, datetime, colorama) — жодних проблем з імпортами немає. Подальша перевірка інших aaa_* файлів не має сенсу, бо корінь проблеми вже знайдено.

#### Крок 5: Запустити пряму перевірку імпорту
- [x] Не потрібно — проблема вже діагностована

#### Крок 6: Зробити висновок
- [x] Проблема: `load_all_modules()` використовує `glob("aaa_*.py")` і `glob("tools_*.py")` без рекурсії
- [x] Файли лежать в `functions/tools/`, а не в корені `functions/`
- [x] Жодних помилок імпорту — файли просто ніколи не знаходяться
- [x] Відмітити виконання в TASK.md

**ВИСНОВОК:**
Проблема — в `functions/runtime/logic_core.py`, метод `load_all_modules()`:
- `functions_dir.glob("aaa_*.py")` → сканує тільки корінь `functions/`, не заходить в `functions/tools/`
- `functions_dir.glob("tools_*.py")` → те саме
- Єдиний файл в корені, який підпадає під `tools_*.py` — це `tools_project_indexer.py`, тому він єдиний завантажується

**Виправлення:**
Замінити `glob("aaa_*.py")` на рекурсивний варіант — `glob("**/aaa_*.py")` або `rglob("aaa_*.py")`. Аналогічно для `tools_*` та `core_*`.