# Проєкт: Асистент МАРК
> Останнє оновлення: 20.04.2026

---

## 1. Загальний опис

**МАРК** — локальний голосовий і текстовий асистент для Windows на Python.
Мета: не просто голосовий помічник, а **агент**, який:
- отримує задачу українською мовою
- будує план дій
- виконує кроки через інструменти
- перевіряє результат
- пробує виправити невдалий крок
- зберігає контекст виконання

Основний стабільний сценарій: **текстова взаємодія через GUI**.

---

## 2. Поточний стан (19.04.2026)

### ✅ Реалізовано

- GUI на Tkinter (модульна структура `core_gui/` з 9 модулів)
- Текстовий режим як основний робочий режим
- STT і TTS інтегровані (TTS вимкнено, STT — опційно)
- Реєстр функцій `aaa_*.py`
- Кеш, dispatcher і LLM-виклики
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
- **Coding Agent mode** — окремий prompt, автодетекція кодових задач
- **GUI clipboard fix** — Ctrl+C/V/X на будь-якій розкладці
- **Панель плану** — прогрес-бар, статуси (pending/running/ok/error/blocked/skipped)
- **Підтвердження** — зворотний відлік 30с, кнопки ТАК/НІ/АВТОМАТИЧНО
- **SettingsManager** — persist у `user_settings.json`, schema для UI
- **Вкладка "Налаштування"** в GUI — Notebook, угрупування, валідація

### ⏳ Не дороблено

- ~~Repair-логіка лише 1 repair + 1 replan~~ — ✅ Виконано: цикл до 3 спроб
- ~~Планер: LLM не завжди повертає JSON~~ — ✅ Виконано: retry механізм + few-shot
- ~~Переробити кеш команд~~ — ✅ Виконано: тільки idempotent
- ~~Тести для core_planner~~ — ✅ Виконано: pytest suite
- ~~Тести для core_memory~~ — ✅ Виконано: pytest suite
- ~~Тести для core_executor~~ — ✅ Виконано: pytest suite
- ~~LLM-based summary~~ — ✅ Вже інтегровано в `_manage_conversation_history`
- ~~Документація~~ — ✅ Виконано: README.md + CONTRIBUTING.md
- Planner не робить повне перепланування дерева (потребує великої переробки)

---

## 3. Залежності

| Пакет | Версія | Статус |
|-------|--------|--------|
| numpy | 1.26.4 | ✅ знижено (несумісність з torch 2.x) |
| torch | 2.x | ✅ |
| sounddevice | 0.5.5 | ✅ встановлено |
| noisereduce | 3.0.3 | ✅ встановлено |
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
functions/
  config.py               ← глобальні налаштування
  core_settings.py        ← SettingsManager (user_settings.json)
  core_planner.py         ← Planner (Plan → Act → Verify → Repair)
  core_executor.py        ← TaskExecutor (async виконання плану)
  core_tool_runtime.py    ← TOOL_POLICIES, безпека, AuditLog
  core_memory.py          ← MemoryManager (3 рівні)
  core_cache.py           ← кеш команд
  logic_commands.py       ← VoiceAssistant (маршрутизація команд)
  logic_llm.py            ← LLM виклики, JSON парсинг
  logic_tts.py            ← TTS двигун
  logic_audio.py          ← аудіо фільтрація
  aaa_*.py                ← інструменти агента
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
```

---

## 5. Завершені етапи розвитку

### Етап A. Minimum Viable Agent ✅
- [x] Planner
- [x] Підключено до реального виконання
- [x] Базова пам'ять
- [x] Валідація кроків
- [x] Один repair-крок після помилки

### Етап B. Strong Agent Loop ✅
- [x] Базове перепланування після невдалого repair
- [x] Структурований формат результату для всіх інструментів
- [x] Артефакти кроків (`step_artifacts`, `artifacts_summary`)
- [x] Placeholders між кроками (`_resolve_placeholders`)

### Етап C. Tool Runtime ✅
- [x] Runtime із єдиним форматом результату
- [x] Уніфікація `create_file`, `edit_file`, `execute_python`
- [x] Статуси `success / error / needs_confirmation / retryable`
- [x] Категорії SAFE / CONFIRM_REQUIRED / BLOCKED

### Етап D. Memory & Context ✅
- [x] `SessionMemory`, `TaskMemory`
- [x] Збереження проміжних результатів кроків
- [x] Адаптивна `_manage_conversation_history`
- [x] LLM-based summaries (`summarize_conversation`, `_summarize_task`)

### Етап E. Safety ✅
- [x] Централізована runtime policy
- [x] `confirm_action` у ризиковані дії
- [x] `DANGEROUS_PATTERNS` + `DANGEROUS_REGEXES` (45 literal + 6 regex)
- [x] `AMBIGUOUS_PATTERNS` + `AMBIGUOUS_REGEXES` (23 literal + 4 regex)
- [x] `check_params_safety(action, params)` — перевірка параметрів
- [x] `AuditLog` → `logs/audit.jsonl`

### Етап F. Code Agent Mode ✅
- [x] `read_code_file`, `search_in_code`, `list_directory`
- [x] `git_status`, `git_diff`
- [x] Coding-цикл (`_is_coding_task`, coding prompt)
- [x] `get_coding_system_prompt`, `AGENT_MODE`

---

## 6. Подальший план розвитку

### Короткострокові (наступна сесія)

**Перевірка планера — поточна робота** — ✅ Виконано (20.04.2026)
- Проблема: LLM повертає чат-відповідь замість JSON плану
- Рішення:
  - Покращений промпт з few-shot прикладом (`core_planner.py`)
  - **Retry механізм**: 2 спроби з різними промптами
  - Дебаг-лог: `🔍 [DEBUG] planner exists: X, should_plan: Y`
  - Fallback: виконання напряму без планування

**Виправити парсинг простих виразів** — ✅ Виконано (20.04.2026)
- Проблема: `2+2` → `❌ Невідомий формат команди: {'result': 4}`
- Рішення: `logic_llm.py` обробляє `result` без `action`
- Парсер тепер розпізнає прості вирази

**Додати відсутні функції** — ✅ Виконано (20.04.2026)
- `create_folder` — створення папки на Desktop
- `search_in_text` — пошук підрядка/regex у тексті
- `count_words` — підрахунок слів, символів, рядків
- Файл: `functions/aaa_utility_tools.py`

**Виправити парсинг множинних дій** — ✅ Виконано (20.04.2026)
- Проблема: `Створи 3 файли` → `❌ Невідомий формат команди: {'actions': [...]}`
- Рішення: `logic_llm.py` обробляє `actions` список
- Кожна дія виконується послідовно

**Багатоетапний repair** — ✅ Виконано (20.04.2026)
- Зараз лише 1 repair + 1 replan
- Рішення: `while` цикл до 3 repair-спроб (`MAX_REPAIR_ATTEMPTS = 3`)
- Антициклічна перевірка: пропускаємо ідентичні кроки
- Евристика: спочатку repair (до 3 разів), потім replan (1 раз)
- Файл: `functions/logic_commands.py`

**Індикатор завершення відповіді в GUI** — ✅ Виконано (19.04.2026)
- Статус-рядок оновлюється: "✅ Відповідь готова | час"

**Streaming виведення відповіді** — ✅ Виконано (20.04.2026)
- Буферизація по 180 символів (~2-3 речення)
- Flush при кінці речення (`. `, `! `, `? `, `\n`)
- Статус-бар показує прогрес: "💭 Генерую... (N токенів)"

**Спойлери в налаштуваннях GUI** — ✅ Виконано (19.04.2026)
- Заголовки груп клікабельні: ▼ відкрито · ▶ згорнуто
- `_toggle_group()` + `_group_headers` в `settings_tab.py`

**Пошук налаштувань** — ✅ Виконано (19.04.2026)
- 🔍 Entry-поле зверху вкладки
- Фільтрує за key / label / desc; приховує групи без збігів
- `_apply_settings_filter()` з `trace_add('write', ...)`

**Позиція і розмір вікна GUI** — ✅ Виконано (19.04.2026)
- Ключ `WINDOW_GEOMETRY` в `SETTINGS_SCHEMA` (hidden, user_only)
- Збереження при закритті (`WM_DELETE_WINDOW` → `_on_close`)
- Відновлення при старті в `AssistantGUI.__init__`

**Голосовий ввід — індикатор мікрофона** — ⏳ Відкладено
- Залежить від стабілізації STT модуля
- Базова логіка готова (тогл в налаштуваннях)

**Виправити статус 'Режим вводу тексту'** — ✅ Виконано (19.04.2026)
- Було: "⌨️ Режим вводу тексту - аудіо призупинено"
- Стало: "⌨️ Ввід тексту | 🎤 вимк."

**STT toggle в налаштуваннях** — ✅ Виконано (20.04.2026)
- `STT_ENABLED` — перемикач у групі "Розпізнавання мови"
- Вимкнено за замовчуванням (`false` в `user_settings.json`)
- Код перевіряє налаштування перед завантаженням STT моделей

### Середньострокові

**Тести для core модулів** — середній пріоритет
- unit тести для `core_planner`, `core_memory`, `core_tool_runtime`
- інтеграційні тести для agent loop

**Інтеграція pytest як code-tool** — середній пріоритет
- Інструмент для запуску pytest
- Інтеграція в coding-цикл

### Довгострокові (опціонально)

**Міграція на PyQt6**
- Структура `core_gui/` готова
- Замінити Tkinter на PyQt6 в кожному модулі

**Semantic search у коді**
- Embeddings через sentence-transformers

**STT + голосовий ввід в GUI**
- Доробити STT для повноцінної голосової взаємодії
- Індикатор мікрофона в GUI: 🎤 зелена = слухає, 🎤 сіра = вимкнено
- Клік по іконці — тогл on/off голосового вводу
- Пов'язано з короткостроковим пунктом "Голосовий ввід — індикатор мікрофона"

**Переробити кеш команд** — ✅ Виконано (20.04.2026)
- Проблема: кеш зберігав `action_info` і автоматично виконував дії (небезпечно)
- Рішення:
  - Додано `idempotent=True` в `TOOL_POLICIES` для безпечних функцій
  - Кеш тепер тільки для читання/обчислень (execute_python, count_words, search_in_text, read_code_file, git_status)
  - Видалено `_extract_action_info()`, `execute_cached_action()` депрекейтед
  - Метод `set()` перевіряє ідемпотентність перед збереженням

**Метрики виконання**
- success rate, avg steps, тривалість

---

## 7. Готовність до продакшну

**~95% Core** — основні функції (планер, пам'ять, executor, кеш) працюють стабільно.
**~0% GUI Automation** — новий масштабний напрямок (Phase 1-6), перетворить агента на універсального автоматизатора Windows.

**Наступний фокус:** Phase 1 GUI Automation (миша, клавіатура, вікна, скріншоти)

---

---

## 8. 🚀 Future Roadmap: GUI Automation & Computer Vision

Стратегічний план перетворення агента на універсального автоматизатора Windows-інтерфейсу.

---

### 🎯 Фаза 1: Базова автоматизація GUI (Core GUI Automation)
**Статус:** 🔴 Не розпочато | **Термін:** 2-3 тижні | **Пріоритет:** Високий

#### 1.1 Керування мишею та клавіатурою
- [ ] **Модуль `tools_input.py`** — інтеграція `pyautogui`
  - `mouse_click(x, y, button='left', clicks=1)` — клік в координати
  - `mouse_move(x, y, duration=0.5)` — плавне переміщення
  - `mouse_scroll(amount, direction='vertical')` — скрол
  - `mouse_drag(start_x, start_y, end_x, end_y)` — перетягування
  - `keyboard_press(key)` — натискання клавіші
  - `keyboard_type(text, interval=0.01)` — введення тексту
  - `keyboard_hotkey(*keys)` — комбінації (Ctrl+C, Alt+Tab)
  - `get_mouse_position()` — отримати поточні координати

#### 1.2 Скріншоти та аналіз екрану
- [ ] **Модуль `tools_screen.py`** — базові операції з екраном
  - `take_screenshot()` — зняття скріншота всього екрану
  - `capture_region(x, y, width, height)` — скріншот області
  - `get_screen_size()` — роздільна здатність екрану
  - `pixel_color(x, y)` — колір пікселя в точці
  - `wait_for_color(x, y, color, timeout=10)` — очікування зміни кольору

#### 1.3 Керування вікнами Windows
- [ ] **Модуль `tools_window.py`** — робота з вікнами
  - `list_windows()` — список відкритих вікон (hwnd, title, process)
  - `find_window(title_pattern)` — пошук вікна за назвою
  - `activate_window(hwnd)` — активація вікна (фокус)
  - `minimize_window(hwnd)` / `maximize_window(hwnd)` / `restore_window(hwnd)`
  - `move_window(hwnd, x, y, width, height)` — переміщення та зміна розміру
  - `close_window(hwnd)` — закриття вікна
  - `get_window_rect(hwnd)` — координати та розмір вікна
  - `is_window_visible(hwnd)` — перевірка видимості

---

### 🔮 Фаза 2: Комп'ютерний зір (Computer Vision)
**Статус:** 🔴 Не розпочато | **Термін:** 3-4 тижні | **Пріоритет:** Високий

#### 2.1 OCR — розпізнавання тексту на екрані
- [ ] **Модуль `tools_ocr.py`** — інтеграція `easyocr` або `tesseract`
  - `ocr_screen()` — розпізнати весь текст на екрані
  - `ocr_region(x, y, width, height)` — розпізнати текст в області
  - `find_text_on_screen(text)` — знайти координати тексту
  - `ocr_window(hwnd)` — OCR активного вікна
  - **Підтримка мов:** українська, англійська, російська

#### 2.2 Детекція UI елементів
- [ ] **Модуль `tools_ui_detect.py`** — пошук елементів інтерфейсу
  - `find_button(text_pattern)` — знайти кнопку за текстом
  - `find_input_field(label)` — знайти поле вводу за міткою
  - `find_menu_item(menu_path)` — навігація по меню ("File/Open")
  - `find_checkbox(label)` / `find_radio(label)` — елементи керування
  - `find_icon(icon_name)` — пошук іконки (template matching)
  - `list_ui_elements()` — всі елементи поточного вікна

#### 2.3 Візуальний аналіз контексту
- [ ] **Модуль `tools_vision.py`** — розуміння того, що на екрані
  - `analyze_screen()` — загальний опис екрану (що відкрито)
  - `detect_open_application()` — розпізнавання активної програми
  - `is_dialog_present()` — чи є діалогове вікно
  - `is_loading()` — детекція індикаторів завантаження
  - `detect_error_message()` — пошук вікон помилок
  - `read_notification()` — читання спливаючих сповіщень

---

### 🧠 Фаза 3: Розумна автоматизація (Smart Automation)
**Статус:** 🔴 Не розпочато | **Термін:** 4-6 тижнів | **Пріоритет:** Середній

#### 3.1 Навігація по UI
- [ ] **Модуль `logic_ui_nav.py`** — інтелектуальна навігація
  - `click_element(element_description)` — клік за описом ("кнопка OK")
  - `fill_form(fields_dict)` — заповнення форми за даними
  - `navigate_menu(path_list)` — навігація: `["File", "Preferences", "General"]`
  - `select_from_dropdown(label, option_text)` — вибір з випадаючого списку
  - `scroll_to_element(element)` — скрол до елементу
  - `wait_and_click(element, timeout=10)` — очікування та клік

#### 3.2 Розпізнавання сценаріїв
- [ ] **Модуль `core_scenario.py`** — шаблони типових дій
  - Збереження файлу (Ctrl+S, введення шляху, Enter)
  - Відкриття файлу (Ctrl+O, навігація, вибір)
  - Пошук в програмі (Ctrl+F, введення тексту)
  - Закриття з підтвердженням (перевірка діалогу "Save changes?")
  - Логін (введення credentials, натискання Login)

#### 3.3 Контекстна допомога
- [ ] **Сценарії допомоги**
  - "В мене не працює кнопка X" → аналіз, чи вона активна, чи є альтернатива
  - "Зроби скріншот і поясни, що тут не так" → OCR + LLM аналіз
  - "Покажи, як зробити Y в програмі Z" → демонстрація кроків

---

### 🛡️ Фаза 4: Безпека та надійність
**Статус:** 🔴 Не розпочато | **Термін:** 2 тижні | **Пріоритет:** Високий

#### 4.1 Журнал дій (Action Logging)
- [ ] **Модуль `core_action_log.py`** — реєстрація всіх дій GUI
  - Запис кожної дії: координати, елемент, час
  - Скріншот до/після критичних дій
  - Експорт логу в JSON/текст
  - Повний аудит-лог для аналізу

#### 4.2 Система Undo/Redo
- [ ] **Модуль `core_undo.py`** — відкат дій
  - `save_state()` — збереження стану перед операцією
  - `undo_last_action()` — відкат останньої дії (якщо можливо)
  - `undo_n_actions(n)` — відкат N дій
  - **Обмеження:** не всі дії можна відкотити (наприклад, відправка email)

#### 4.3 Режим підтвердження критичних дій
- [ ] **Модуль `core_gui_guardian.py`** — захист від помилок
  - **Рівні ризику:**
    - `low` — без підтвердження (клік по відомій кнопці)
    - `medium` — підтвердження через GUI (зворотний відлік 5с)
    - `high` — явне підтвердження користувача (ТАК/НІ)
    - `critical` — блокування + пояснення чому це небезпечно
  - **Критичні операції:**
    - Видалення файлів/папок
    - Зміна системних налаштувань
    - Відправка даних в інтернет
    - Закриття важливих програм без збереження
    - Дії з правами адміністратора

#### 4.4 Sandbox режим
- [ ] **Модуль `core_sandbox.py`** — тестування дій
  - `preview_actions(action_list)` — показати, що буде зроблено
  - `simulate_actions(action_list)` — "сухий" прогін без реального виконання
  - `limited_scope(rect)` — обмеження дій областю екрану
  - `disable_critical_tools()` — відключення небезпечних інструментів

---

### 📚 Фаза 5: Навчання та адаптація
**Статус:** 🔴 Не розпочато | **Термін:** 3-4 тижні | **Пріоритет:** Середній

#### 5.1 Запис макросів
- [ ] **Модуль `tools_macro.py`** — запис дій користувача
  - `start_recording()` — почати запис
  - `stop_recording()` — зупинити та зберегти
  - `play_macro(macro_name)` — відтворити записану послідовність
  - `save_macro(name, description)` — збереження в бібліотеку
  - **Редактор макросів:** перегляд, редагування кроків

#### 5.2 Автоматизація типових задач
- [ ] **Бібліотека готових сценаріїв**
  - Щоденне резервне копіювання (запуск програми → Export → вибір папки)
  - Форматування документів (Word: вибір стилю, вирівнювання)
  - Очищення папки Downloads (сортування за типами файлів)
  - Налаштування нової програми (прохід початкового setup)
  - Заплановані задачі (черга на певний час)

#### 5.3 Адаптивне навчання
- [ ] **Система покращення**
  - Запам'ятовування успішних шляхів навігації в програмах
  - Корекція координат (якщо елемент змістився)
  - Навчання на помилках ("попередній спосіб не спрацював, пробую альтернативу")
  - Профілі програм (окремі налаштування для Photoshop, Excel, і т.д.)

---

### 🔌 Фаза 6: Розширена інтеграція
**Статус:** 🔴 Не розпочато | **Термін:** 3-4 тижні | **Пріоритет:** Низький

#### 6.1 API популярних програм
- [ ] **Модулі інтеграції**
  - `integration_excel.py` — робота з Excel через COM
  - `integration_photoshop.py` — Photoshop scripting (JavaScript/VBScript)
  - `integration_browser.py` — автоматизація Chrome/Edge через Selenium
  - `integration_outlook.py` — відправка листів, робота з календарем
  - `integration_teams.py` — повідомлення в Teams/Slack

#### 6.2 Голосове керування v2.0
- [ ] **Покращення STT/TTS**
  - Неперервне слухання (wake word: "Марко")
  - Розпізнавання команд в шумі
  - Голосові підтвердження ("Ви сказали: [дія]. Підтверджуєте?")
  - Відповіді голосом про статус виконання

#### 6.3 Зворотний зв'язок та моніторинг
- [ ] **Система сповіщень**
  - Візуальні індикатори прогресу (overlay на екрані)
  - Спливаючі повідомлення про завершення
  - Звукові сигнали для важливих подій
  - Webhook сповіщення (на телефон/месенджер)

---

### 📊 Метрики успіху GUI Automation

| Метрика | Цільове значення | Як виміряти |
|---------|------------------|-------------|
| **Accuracy кліків** | > 95% | Успішні кліки / Загальні кліки |
| **OCR precision** | > 90% | Правильно розпізнані слова / Всі слова |
| **UI detection** | > 85% | Знайдені елементи / Всі елементи |
| **Task completion** | > 80% | Успішні сценарії / Всі спроби |
| **False positive rate** | < 5% | Хибні спрацьовування безпеки / Всі дії |
| **User satisfaction** | > 4.0/5 | Опитування користувачів |

---

### 🗓️ Пріоритетність виконання

**Phase 1 (Core GUI)** → Високий пріоритет — базова функціональність
**Phase 4 (Safety)** → Високий пріоритет — обов'язково перед використанням
**Phase 2 (CV)** → Високий пріоритет — ключова відмінність
**Phase 3 (Smart)** → Середній — залежить від Phase 1-2
**Phase 5 (Learning)** → Середній — покращення UX
**Phase 6 (Integration)** → Низький — nice-to-have

---

### ⚠️ Технічні обмеження та ризики

| Ризик | Ймовірність | Вплив | Мітігація |
|-------|-------------|-------|-----------|
| Антивіруси блокують input automation | Середня | Високий | Підпис драйвера, додавання в whitelist |
| Зміна UI програм (оновлення) | Висока | Середній | Адаптивний пошук, не hardcoded координати |
| Нестабільність Computer Vision | Середня | Середній | Fallback на OCR, кешування шаблонів |
| Безпека (випадкові дії) | Низька | Критичний | Multi-layer safety, undo система |
| Продуктивність (сповільнення) | Низька | Середній | Оптимізація, async обробка |

---

### 🔗 Корисні ресурси

- **pyautogui** — https://pyautogui.readthedocs.io/
- **pywinauto** — https://pywinauto.readthedocs.io/ (native Windows UI)
- **easyocr** — https://github.com/JaidedAI/EasyOCR
- **OpenCV** — комп'ютерний зір
- **Tesseract OCR** — розпізнавання тексту
- **Selenium** — автоматизація браузерів

---

*План GUI Automation додано 20.04.2026. Об'єднано з основним планом розвитку.*
