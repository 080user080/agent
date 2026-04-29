# Поточні задачі МАРК
> Останнє оновлення: 30.04.2026

---

## РОБОЧІ МЕТОДИ АВТОМАТИЗАЦІЇ ДЛЯ PYQT6 GUI (підтверджено)

**Автоматизована вставка тексту в PyQt6 GUI:**
- `activate_window_by_title(title="МАРК — Асистент (PyQt6)")` з `functions.aaa_voice_input`
- `keyboard_type(text="привіт")` з `functions.tools_mouse_keyboard`
- `keyboard_press(key="Enter")` з `functions.tools_mouse_keyboard`

**Затримки:**
- 2 секунди до вставки тексту
- 20 секунд до перевірки відповіді

**Скрипт:** `test_duplication_direct.py` - автоматизований тест для перевірки дублювання повідомлень

**Фільтрація JSON:**
- Додана фільтрація JSON чанків в `append_stream_chunk` в `core_gui_pyqt6/main_window.py`
- JSON чанки не відображаються в чаті, але зберігаються в буфері для парсингу

**Виправлення дублювання в чаті GUI:**
- Прибрано виклик `stream_start` в `functions/logic_commands.py` - не додає порожній префікс "⚡ МАРК:"
- Прибрано виклик `assistant_stream_chunk` в `flush_buffer` - не додає текст через streaming
- Прибрано виклик `stream_end` - не завершує streaming
- Всі відповіді тепер додаватимуться через `log_to_gui` без дублювання префікса

---

## В процесі

### P0: Стабільність і узгодженість контрактів

- [ ] Полагодити trunk stability
  - Статус: В процесі
  - Пріоритет: P0
  - Деталі:
    - Повернути сумісність між тестами й `logic_task_runner`
    - Добитися, щоб `pytest` хоча б повністю проходив collection
    - Зафіксувати публічні API для parser/runner/plan-об'єктів

- [x] Визначити відповідність між проєктом та external AI-архітектурою
  - Статус: Завершено
  - Дата: 28.04.2026
  - Опис: Порівняно поточний стан з external AI-архітектурою (observe → decide → act → check → repeat)
  - Результат: Виявлено що основний цикл (AgentLoop) вже реалізовано (Phase 12.1), але потребує кращої інтеграції з GUI

- [ ] Синхронізувати документацію з реальним кодом
  - Статус: Не розпочато
  - Пріоритет: P0
  - Деталі:
    - Оновити `README.md` під актуальну структуру проєкту
    - Прибрати застарілі згадки про старий LLM-шар там, де вже використовується `functions/llm/`
    - Перевірити, щоб `README.md`, `status.md`, `TASKS.md` і код не суперечили одне одному

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

- [x] Створити AI actors для делегування
  - Статус: Завершено
  - Дата: 26.04.2026
  - Опис: AIActor база, ActorRegistry, автоматичний fallback між провайдерами (S5)

- [ ] Створити router для вибору агента
  - Статус: Не розпочато
  - Пріоритет: P1
  - Деталі:
    - Meta-agent вирішує хто виконує (local vs API)
    - Коли передати іншому провайдеру
    - Вирішує на основі типу задачі (gui/code/web/desktop)

### P1: Міграція GUI на PyQt6

- [ ] Міграція GUI на PyQt6
  - Статус: В роботі (Phase A+B+D — MVP working, Phase C — pending)
  - Пріоритет: P1
  - Стратегія: **поступова, паралельна** (Tkinter і PyQt6 співіснують через feature-flag `GUI_BACKEND`)
  - PyQt6 6.11.0 встановлено, додано в `requirements.txt`
  - Поточний стан Tkinter GUI: 11 модулів у `core_gui/` (~120KB), включає chat, plan, confirmation, settings, windsurf, llm-editor, tray
  - Поточний стан PyQt6 GUI: повноцінне `MainWindowPyQt6` (~410 рядків) з API-сумісністю до Tkinter

  **Phase A — Підготовка та feature-flag (P1) — DONE:**
  - [x] Перевірити що PyQt6 встановлено (6.11.0)
  - [x] Додати `PyQt6>=6.6.0` в `requirements.txt`
  - [x] Додати setting `GUI_BACKEND` (`tkinter` | `pyqt6`, default: `tkinter`)
  - [x] Створити точку входу `run.py` з вибором бекенда (підтримка `--qt`/`--tk` CLI)
  - [x] Спільний контракт API GUI: `add_message`, `update_progress`, `queue_message`, `set_assistant`, `set_stt_controller`, `show_stop_button`/`hide_stop_button`, `start_stream_message`/`append_stream_chunk`/`end_stream_message`, `show_plan_panel`/`update_plan_step`/`finish_plan_panel`, `show_confirmation`, `run`

  **Phase B — Ядро PyQt6 (P1) — DONE:**
  - [x] `MainWindowPyQt6` з повним функціоналом:
    - Чат-історія (QTextEdit) з форматуванням повідомлень
    - Поле вводу (QTextEdit, multi-line, Enter=send, Shift+Enter=новий рядок)
    - Кнопки: 🎤 STT, 🤖 Agent, ➤ Send, ⬛ Stop
    - Status label + QProgressBar
    - Plan panel (QListWidget зі статусами ⏸/▶/✅/❌)
    - Splitter chat/plan
  - [x] Потокобезпечна черга через Qt signal `message_received` (замість `queue.Queue + after()`)
  - [x] QSS стилі (порт `core_gui/styles.py`)

  **Phase C — Модулі (P1) — DONE:**
  - [x] `settings_tab_qt.py` — SettingsTabQtMixin з динамічним рендерингом SETTINGS_SCHEMA (DONE)
  - [x] `llm_endpoints_editor_qt.py` — LLMEndpointsEditor для PyQt6 (DONE)
  - [x] `chat_panel_qt.py` — ChatPanelQtMixin (історія, ввід, clipboard, стрімінг, контекстні меню) (DONE)
  - [x] `plan_panel_qt.py` — PlanPanelQtMixin (кроки, прогрес, статуси) (DONE)
  - [x] `confirmation_qt.py` — ConfirmationQtMixin (кастомні діалоги підтвердження з таймаутом) (DONE)
  - [ ] `windsurf_panel_qt.py` (зараз відсутнє в Tkinter)
  - [ ] `tray_icon_qt.py` (QSystemTrayIcon, зараз відсутнє в Tkinter)

  **Phase D — Інтеграція (P1) — DONE:**
  - [x] `AssistantAppQt` у `run_assistant_qt.py` — паралельний до `AssistantApp`
  - [x] Реалізовано queue_dispatcher (фоновий потік: `gui_queue` → Qt-сигнал)
  - [x] Callbacks: `process_text`, `run_agent`, `run_plan`, `stop_plan`, `stop_execution`, mic
  - [x] Smoke test: 17 unit-тестів (`tests/test_pyqt6_gui.py`)
  - [x] Реальний запуск з ядром асистента (manual test з `python run.py --qt`)

  **Phase E — Deprecate Tkinter (P2):**
  - [ ] Після стабілізації PyQt6 — позначити Tkinter як deprecated
  - [ ] Перевести default `GUI_BACKEND` на `pyqt6`
  - [ ] Видалити `core_gui/` після перевірки feature parity

- [ ] Перетягнути LLM налаштування зі старого GUI в новий GUI
  - Статус: Не розпочато
  - Пріоритет: P1
  - Деталі:
    - Забезпечити **feature parity** між `core_gui/llm_endpoints_editor.py` і `core_gui_pyqt6/llm_endpoints_editor_qt.py`
    - Перевірити, що всі поля endpoint-ів доступні й однаково зберігаються/редагуються в новому GUI
    - Гарантувати, що існуючі LLM endpoint-и та пов'язані settings коректно підтягуються в PyQt6 без ручного перевнесення
    - Якщо потрібно — додати явну логіку copy/migrate existing settings при першому запуску нового GUI
    - Окремо перевірити: `name`, `enabled`, `role`, `type`, `url`, `model`, `api_key`, `temperature`, `max_tokens`, `timeout`, `script_command`, `script_output_file`, `rate_limit_*`

- [ ] Перевірити статус-бар і готовність LLM у новому GUI
  - Статус: Не розпочато
  - Пріоритет: P1
  - Деталі:
    - Узгодити поведінку статусу готовності між Tkinter і PyQt6
    - Перевірити, що в новому GUI коректно показуються назва LLM, час відповіді та стан готовності
    - Цільовий формат: `⚡ МАРК: ✅ Готовий до роботи! (0.7с)` або еквівалентний status-bar без втрати змісту

### P1: Глобальне голосове введення (global hook)

- [x] Створено модуль `functions/global_voice_input.py` — Global Voice Input (Windows hooks + STT)
  - HotkeyHook — Windows low-level keyboard hook для перехоплення гарячих клавіш
  - GlobalVoiceInput — клас для глобального голосового введення
  - Використовує існуючий STTListener для розпізнавання
  - Вставка тексту через clipboard (pyperclip) або SendInput fallback
  - Hotkey за замовчуванням: Ctrl+Shift+V
- [x] Додано налаштування GLOBAL_VOICE_HOTKEY та GLOBAL_VOICE_ENABLED в SETTINGS_SCHEMA
- [x] Інтегровано GlobalVoiceInput в main.py (автоматичний запуск при GLOBAL_VOICE_ENABLED=True)
- [x] Створено unit-тести в `tests/test_global_voice_input.py`
- [x] Тестування на реальній Windows системі з включеним GLOBAL_VOICE_ENABLED

### P1: Самонавчання

- [x] Створено модуль `functions/self_learning.py` — SelfLearning (логування, аналіз помилок, skills база)
  - log_execution() — логування виконання задач (task, result, success, error, steps)
  - analyze_errors() — аналіз останніх помилок
  - generate_rules_from_errors() — генерування правил з помилок (heuristic + LLM)
  - add_skill() / get_skill() — skills база для накопичення досвіду
  - get_stats() — статистика виконань
- [x] Інтегровано SelfLearning в AssistantCore (main.py)
  - Ініціалізація в initialize()
  - Логування виконання в run_agent_loop()
- [ ] Тестування та покращення правил на основі реальних помилок

---

## Перевірка правильності (P1, high priority) — DONE ✅

### CHECK: P1 Глобальне голосове введення — PASSED

- [x] `functions/global_voice_input.py` — HotkeyHook парсить `ctrl+shift+v` правильно ({0x11, 0x10, 0x56})
  - HotkeyHook: `set_callback`, `start`, `stop`, `_keyboard_proc`, `_message_loop`
  - GlobalVoiceInput: `start`, `stop`, `_on_hotkey_pressed`, `_on_text_recognized`, `_insert_text`, `_simulate_paste`
- [x] SETTINGS_SCHEMA містить `GLOBAL_VOICE_HOTKEY` (str, "ctrl+shift+v") та `GLOBAL_VOICE_ENABLED` (bool, False)
- [x] `main.py` імпортує `GlobalVoiceInput`, ініціалізує `self.global_voice_input` при `GLOBAL_VOICE_ENABLED=True`

### CHECK: P1 Самонавчання — PASSED

- [x] `functions/self_learning.py` — всі методи присутні: `log_execution`, `analyze_errors`, `generate_rules_from_errors`, `add_skill`, `get_skill`, `get_stats`
- [x] `AssistantCore` (main.py): імпорт `get_self_learning`, ініціалізація в `initialize()`, виклик `log_execution` в `run_agent_loop` (try/except/finally)
- [x] JSONL логи пишуться в `D:\Python\agent\runtime\self_learning\execution_logs.jsonl` (виправлено `data_dir` шлях: `parent.parent` замість `parent.parent.parent`)

---

## Модульна перевірка PyQt6 (P1, high priority) — DONE ✅

### MODULAR CHECK: main_window.py — PASSED (10/10)

- [x] Імпорт та клас MainWindowPyQt6
- [x] Міксини успадковані: SettingsTabQtMixin, ChatPanelQtMixin, PlanPanelQtMixin, ConfirmationQtMixin
- [x] Qt-сигнал message_received присутній
- [x] __init__ параметри: assistant_callback
- [x] API методи: add_message, send_text_command, show_plan_panel, update_plan_step, finish_plan_panel, show_confirmation, set_assistant, set_stt_controller, run
- [x] _on_tab_change присутній
- [x] _apply_styles присутній
- [x] _scroll_chat_to_end присутній
- [x] eventFilter присутній
- [x] _on_message присутній

### MODULAR CHECK: chat_panel_qt.py — PASSED (8/8)

- [x] Імпорт та клас ChatPanelQtMixin
- [x] API методи: add_message, start_stream_message, append_stream_chunk, end_stream_message
- [x] Методи чату: focus_input, _setup_clipboard_and_menus, _show_input_context_menu, _show_chat_context_menu
- [x] Методи clipboard: _clipboard_copy, _clipboard_cut, _clipboard_paste, _clipboard_select_all
- [x] Методи стрімінгу: start_stream_message, append_stream_chunk, end_stream_message
- [x] add_message використовує chat_history
- [x] ANSI токен очищення присутнє (re.sub)
- [x] Контекстні меню реалізовані (QMenu)

### MODULAR CHECK: plan_panel_qt.py — PASSED (6/6)

- [x] Імпорт та клас PlanPanelQtMixin
- [x] API методи: show_plan_panel, update_plan_step, finish_plan_panel, on_plan_execution_started, on_plan_execution_finished
- [x] Методи кнопок: _on_run_plan, _on_stop_plan
- [x] Іконки статусів: pending, running, ok, error, blocked, needs_confirmation, skipped
- [x] show_plan_panel використовує plan_list
- [x] finish_plan_panel має приховування

### MODULAR CHECK: settings_tab_qt.py — PASSED (8/8)

- [x] Імпорт та клас SettingsTabQtMixin
- [x] API методи: _on_tab_changed, _build_settings_tab, _toggle_group, _save_all_settings, _reset_all_settings, _reload_settings_tab
- [x] Методи створення віджетів: _create_settings_widget, _apply_settings_filter
- [x] Методи дій: _clear_command_cache, _restart_agent
- [x] _build_settings_tab використовує SETTINGS_SCHEMA
- [x] _create_settings_widget використовує schema
- [x] _toggle_group має логіку акордеонів
- [x] update_watcher_status присутній

### MODULAR CHECK: confirmation_qt.py — PASSED (6/6)

- [x] Імпорт: ConfirmationQtMixin та ConfirmationDialog
- [x] API методи: show_confirmation, hide_confirmation
- [x] ConfirmationDialog методи: __init__, _update_countdown, _on_yes, _on_no, _on_auto
- [x] Таймер присутній в _update_countdown
- [x] show_confirmation використовує callback
- [x] Кнопки ТАК/НІ присутні

### MODULAR CHECK: llm_endpoints_editor_qt.py — PASSED (6/6)

- [x] Імпорт та клас LLMEndpointsEditor
- [x] API методи: get, set
- [x] Методи діалогу: __init__, _init_ui, _refresh_list, _add_item, _edit_item, _remove_item
- [x] QListWidget використовується
- [x] Кнопки присутні (add, edit, remove)
- [x] Базовий клас: QFrame

### INTEGRATION CHECK: run_assistant_qt.py — PASSED (7/7)

- [x] Імпорт та клас AssistantAppQt
- [x] API методи: __init__, gui_callback, start
- [x] AssistantAppQt використовує MainWindowPyQt6
- [x] gui_callback використовує self.core
- [x] queue_dispatcher присутній і використовує gui_queue
- [x] gui_queue присутній
- [x] self.gui використовується в start()

### END-TO-END CHECK: синтаксис та інтеграція — PASSED (6/6)

- [x] Всі PyQt6 файли мають коректний синтаксис (7 файлів)
- [x] AssistantCore імпортується з main.py
- [x] GUI_BACKEND присутній в SETTINGS_SCHEMA
- [x] run.py має коректний синтаксис
- [x] AssistantCore має необхідні методи для інтеграції (initialize, run_agent_loop)
- [x] PyQt6 unit-тести пройдені (14/14)

**Всього перевірено:** 8 модулів, 57 перевірок, все PASSED ✅

---

## Заплановано

### P2: GUI поліпшення

- [ ] Додати динамічне збільшення вікна вводу в новому GUI (PyQt6)
  - Статус: Не розпочато
  - Пріоритет: P2
  - Деталі:
    - Поле вводу в PyQt6 має автоматично збільшувати висоту при наборі тексту
    - Мінімальна висота: 2-3 рядки
    - Максимальна висота: 6-8 рядків
    - Реалізувати через QTextEdit з динамічним resize

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

## Завершено

### GUI інтеграція

- [x] Додати назву LLM та час виконання в статус GUI
  - Дата: 28.04.2026
  - Опис: Статус-бар показує назву LLM, час виконання та час завершення відповіді

### LLM конфігурація

- [x] Виправити помилку `llm_time` referenced before assignment
  - Дата: 28.04.2026
  - Опис: Розрахунок `llm_time` перенесено перед використанням в GUI update

- [x] Додати `name` в `_normalize_endpoint`
  - Дата: 28.04.2026
  - Опис: Endpoint зберігає назву LLM для відображення в GUI

### Кодування

- [x] Виправити кодування виводу Python-скрипта на Windows
  - Дата: 28.04.2026
  - Опис: Додано UTF-8 encoding для stdout/stderr у Python sandbox/скриптах

---

## Правила ведення цього файлу

- Тут лише **актуальні задачі**, без довгих історичних фаз і PR-хронології.
- `status.md` відповідає на питання **"де ми зараз?"**
- `TASKS.md` відповідає на питання **"що робимо далі?"**
- `ARCHITECTURE.md` відповідає на питання **"чому саме так і в якому технічному порядку?"**

---

## Примітки

- Пріоритети: `P0` > `P1` > `P2`
- Статуси: `Завершено` > `В процесі` > `Не розпочато`
