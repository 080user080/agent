# 📦 Модулі

> Оновлено: 21.05.2026 — актуалізовано шляхи модулів у відповідності з новою пакетною структурою.

## 📚 Зміст
- [Структура пакетів](#структура-пакетів)
- [functions/ — кореневі модулі](#functions---кореневі-модулі)
- [audio/ — Audio Modules](#audio---audio-modules)
- [llm/ — LLM Modules](#llm---llm-modules)
- [planning/ — Planning Modules](#planning---planning-modules)
- [runtime/ — Runtime Modules](#runtime---runtime-modules)
- [gui/ — GUI Modules](#gui---gui-modules)
- [tools/ — Tool Modules](#tools---tool-modules)
- [core_gui_pyqt6/ — PyQt6 GUI](#core_gui_pyqt6---pyqt6-gui)
- [Інші модулі functions/](#інші-модулі-functions)

---

## Структура пакетів

Замість плоскої структури `functions/`, модулі згруповані в підпакети:

```
functions/
├── __init__.py          # Експорт кореневих модулів
├── config.py            # Глобальна конфігурація
├── global_voice_input.py
├── logic_execution_report.py
├── audio/               # STT/TTS
├── llm/                 # LLM шар
├── planning/            # Планинг + AgentLoop
├── runtime/             # Runtime оркестрація
├── gui/                 # GUI логіка
└── tools/               # Desktop/browser інструменти
```

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

---

## llm/ — LLM Modules

Модулі для роботи з LLM. Розташування: `functions/llm/`.

### `__init__.py`
**Призначення**: Експорт LLM модулів, фабрика провайдерів.

### `helpers.py`
**Призначення**: Допоміжні функції для LLM (clean_llm_tokens, форматування).

### `logic_llm_tools.py`
**Призначення**: OpenAI-compatible tool-calling / JSON mode для LLM (~455 рядків).
**Методи**:
- `ask_llm_with_tools(prompt, tools) → ToolCallResult`: Запит з tool-calling
- `ask_llm_json(prompt, response_model) → dict`: JSON-режим
**Залежності**: `requests`, `openai`

### `providers_vision.py`
**Призначення**: Vision-LM — аналіз зображень через OpenAI/Claude/Gemini (~331 рядок).
**Методи**:
- `analyze_image(query) → VisionResponse`: Аналіз зображення
- `detect_ui_elements(image_path) → List[UIElement]`: 🟡 Stub
- `suggest_actions(image_path, goal) → List[SuggestedAction]`: 🟡 Stub
**Залежності**: `openai`, `anthropic`, `google-generativeai`

---

## planning/ — Planning Modules

Модулі планування та виконання задач. Розташування: `functions/planning/`.

### `agent_loop.py`
**Призначення**: AgentLoop — головний цикл observe → decide → act → check → repeat.
**Методи**:
- `run(goal) → RunResult`: Запуск циклу
- `_step()`: Один крок циклу
**Залежності**: `tools_*`, `logic_llm_tools`

### `core_planner.py`
**Призначення**: Планування задач через LLM з retry-механізмом.
**Методи**:
- `create_plan(task) → CompiledPlan`: Створення плану
- `refine_plan(plan, feedback) → CompiledPlan`: Уточнення плану
**Залежності**: `llm/`

### `core_task_intake.py`
**Призначення**: Прийом та валідація вхідних задач.

### `logic_context_analyzer.py`
**Призначення**: Аналіз контексту виконання (~854 рядки). Детекція блокаторів, підказки наступних дій.

### `logic_task_runner.py`
**Призначення**: TaskRunner з handler-реєстром (~836 рядків). 10 built-in handlers. Повна фаза виконання з PermissionGate, Expectations, SessionBudget.

### `pipeline_code.py`
**Призначення**: Code generation pipeline — автоматична генерація коду через AI actors.

---

## runtime/ — Runtime Modules

Модулі для оркестрації та виконання задач. Розташування: `functions/runtime/`.

### `__init__.py`
**Призначення**: Експорт runtime модулів.

### `conditions_windows.py`
**Призначення**: Умови виконання, специфічні для Windows.

### `core_initializer_checks.py`
**Призначення**: Перевірки ініціалізації перед стартом.

### `core_windsurf_watcher.py`
**Призначення**: Спостереження за Windsurf IDE (~411 рядків).
**Методи**:
- `watch_file(path)`: Початок спостереження файлу
- `get_open_files() → list[str]`: Отримання відкритих файлів
**Залежності**: `watchdog`, внутрішні модулі runtime/

### `logic_core.py`
**Призначення**: FunctionRegistry — реєстр функцій для динамічного виклику.
**Методи**:
- `register(name, func)`: Реєстрація функції
- `call(name, **kwargs)`: Виклик функції
**Залежності**: внутрішні модулі runtime/

### `logic_permission_gate.py`
**Призначення**: 4-рівнева policy stack для перевірки прав на дію (~387 рядків).
**Методи**:
- `ask(action, context) → Decision`: Запит на дозвіл
- `grant(user, action)`: Надання дозволу
**Залежності**: внутрішні модулі runtime/

### `logic_watcher.py`
**Призначення**: Watcher engine з потоками для моніторингу умов (~457 рядків).
**Методи**:
- `watch(condition, callback) → WatchHandle`: Початок спостереження
- `stop_watch(handle)`: Припинення спостереження
**Залежності**: внутрішні модулі runtime/

### Інші runtime модулі
- `core_app_profile.py` — Профілювання додатку
- `core_checkpoint.py` — Чекпоінти для відновлення
- `core_dispatcher.py` — Диспетчер команд
- `core_executor.py` — Виконавець планів
- `core_loop_detector.py` — LoopDetector (захист від зациклення)
- `core_macro.py` — Макроси
- `core_memory.py` — Пам'ять сесій
- `core_safety_sandbox.py` — Сендбокс для безпечного виконання
- `core_session_budget.py` — Бюджет сесії
- `core_tool_runtime.py` — Runtime для інструментів

---

## gui/ — GUI Modules

Модулі GUI-логіки. Розташування: `functions/gui/`.

### `core_gui_guardian.py`
**Призначення**: GUIGuardian — оцінка ризиків GUI-дій (~532 рядки).
**Методи**:
- `assess_risk(action, context) → RiskLevel`: Оцінка ризику
- `confirm_dangerous(action) → bool`: Підтвердження небезпечних дій
**Залежності**: внутрішні модулі

### `logic_commands.py`
**Призначення**: VoiceAssistant — обробка текстових команд, маршрутизація до планера/кешу/LLM.
**Методи**:
- `process_command(text) → str`: Обробка команди
- `set_tts_engine(engine)`: Встановлення TTS
**Залежності**: `logic_core.py`, `STT`, `TTS`

---

## tools/ — Tool Modules

Desktop/browser/media інструменти для GUI-автоматизації. Розташування: `functions/tools/`.

### `tools_mouse_keyboard.py`
**Призначення**: Mouse/keyboard automation через pyautogui (~436 рядків).
Інструменти: `mouse_click`, `mouse_move`, `mouse_scroll`, `mouse_drag`, `keyboard_type`, `keyboard_press`, `keyboard_hotkey`, `clipboard`.

### `tools_window_manager.py`
**Призначення**: Window manager через win32gui/pygetwindow (~605 рядків).
Інструменти: `list_windows`, `find_window_by_title`, `activate_window`, `move/resize/close`.

### `tools_screen_capture.py`
**Призначення**: Screen capture через mss + PIL + OpenCV (~608 рядків).
Інструменти: `take_screenshot`, `capture_region`, `find_image_on_screen`, `wait_for_image`.

### `tools_ocr.py`
**Призначення**: OCR — розпізнавання тексту (pytesseract + easyocr fallback) (~595 рядків).
Інструменти: `ocr_screen`, `find_text_on_screen`, `click_text`.

### `tools_ui_detector.py`
**Призначення**: UI detection — пошук кнопок, полів, чекбоксів через OpenCV + OCR (~653 рядки).
Інструменти: `find_button_by_text`, `find_input_field`, `find_checkbox`, `find_input_near_label`.

### `tools_app_recognizer.py`
**Призначення**: App recognizer — визначення активного додатку, діалогів (~573 рядки).
Інструменти: `detect_active_application`, `detect_file_dialog`, `detect_error_dialog`.

### `tools_visual_diff.py`
**Призначення**: Visual diff — порівняння скріншотів (baseline) (~504 рядки).
Інструменти: `capture_baseline`, `compare_with_baseline`, `highlight_changes`.

### `tools_ui_accessibility.py`
**Призначення**: Windows UIA API (uiautomation + pywinauto dual-backend) (~774 рядки).
Інструменти: 10+ LLM інструментів, інтеграція з AgentLoop.

### `tools_browser_cdp.py`
**Призначення**: Browser CDP automation через Playwright (~1071 рядок).
Інструменти: 12 інструментів для браузерної автоматизації.

### `tools_playwright.py`
**Призначення**: Playwright integration — додаткові утиліти.

### `aaa_file_operations.py`
**Призначення**: Legacy — файлові операції (create, edit, delete, rename).

### `aaa_open_interpreter.py`
**Призначення**: Open Interpreter fallback для self-healing виконання коду.
**Методи**:
- `is_available()`: Перевірка доступності
- `get_executor(url)`: Отримання singleton executor
- `oi_execute_with_healing(code, description)`: Виконання з автоматичним встановленням модулів

---

## core_gui_pyqt6/ — PyQt6 GUI

Модулі для PyQt6 GUI. Розташування: `core_gui_pyqt6/`.

### `__init__.py`
**Призначення**: Експорт GUI модулів.

### `main_window.py`
**Призначення**: MainWindowPyQt6 — головне вікно PyQt6.
**Компоненти**: чат, план, налаштування, кнопки, статус-бар.
**Особливості**:
- Динамічне збільшення поля вводу (`_update_input_height`) — 60–160px
- Збереження/відновлення геометрії вікна
- Потокобезпечна черга повідомлень через Qt signal

### `settings_tab_qt.py`
**Призначення**: SettingsTabQtMixin — міксин для налаштувань.
**Методи**:
- `_render_settings()`: Рендеринг налаштувань
- `_save_settings()`: Збереження налаштувань

### `chat_panel_qt.py`
**Призначення**: ChatPanelQtMixin — міксин для чату.
**Методи**:
- `add_message(sender, message)`: Додавання повідомлення
- `start_stream_message()` / `append_stream_chunk(chunk)` / `end_stream_message()`: Стрімінг

### `plan_panel_qt.py`
**Призначення**: PlanPanelQtMixin — міксин для плану.
**Методи**:
- `show_plan_panel(steps_info)`: Показати план
- `update_plan_step(data)`: Оновити крок
- `finish_plan_panel(stats)`: Завершити план

### `confirmation_qt.py`
**Призначення**: ConfirmationQtMixin — міксин для підтверджень.
**Методи**:
- `show_confirmation(question, callback)`: Показати діалог
- `hide_confirmation()`: Приховати діалог

### `llm_endpoints_editor_qt.py`
**Призначення**: LLMEndpointsEditor — редактор LLM ендпоінтів.
**Методи**:
- `get() → list[dict]`: Отримання ендпоінтів
- `set(endpoints)`: Встановлення ендпоінтів

---

## Інші модулі functions/

Модулі, що знаходяться безпосередньо в `functions/` (не в підпакетах):

- `__init__.py` — експорт
- `config.py` — глобальна конфігурація
- `global_voice_input.py` — глобальний голосовий ввід
- `logic_execution_report.py` — звіт виконання

---

## 📝 Примітка

Цей документ відображає актуальну структуру проєкту станом на 21.05.2026.
Деякі старі модулі (core_*, logic_*) були переміщені в підпакети `gui/`, `runtime/`, `planning/`, `tools/`, `llm/`.

Для автогенерації документації з docstring:
```bash
pdoc --html --output-dir docs functions
```
або
```bash
sphinx-apidoc -o docs/ functions/