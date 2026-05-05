# 📦 Модулі

## 📚 Зміст
- [aaa_* — AI Action Modules](#aaa---ai-action-modules)
- [core_* — Core Modules](#core---core-modules)
- [logic_* — Logic Modules](#logic---logic-modules)
- [llm/ — LLM Modules](#llm---llm-modules)
- [gui_tabs/ — GUI Tabs](#gui_tabs---gui-tabs)
- [core_gui_pyqt6/ — PyQt6 GUI](#core_gui_pyqt6---pyqt6-gui)

---

## aaa_* — AI Action Modules

Модулі, що викликаються AI через FunctionRegistry або tool-calling.

### `aaa_create_file.py`
**Призначення**: Створення файлу через AI.
**Виклик**: Через `FunctionRegistry` або tool-calling.
**Параметри**:
- `file_path` (str): Шлях до файлу
- `content` (str): Вміст файлу
- `encoding` (str, optional): Кодування (default: `utf-8`)
**Приклад**:
```python
{
  "tool": "aaa_create_file",
  "args": {
    "file_path": "test.py",
    "content": "print('Hello')"
  }
}
```
**Залежності**: `core_tool_runtime.py`, `core_safety_sandbox.py`

### `aaa_edit_file.py`
**Призначення**: Редагування існуючого файлу.
**Параметри**:
- `file_path` (str): Шлях до файлу
- `edits` (list): Список змін (old_string, new_string)
**Залежності**: `core_tool_runtime.py`

### `aaa_execute_python.py`
**Призначення**: Виконання Python коду в сендбоксі.
**Параметри**:
- `code` (str): Python код для виконання
- `timeout` (int, optional): Таймаут (default: 30)
**Залежності**: `core_safety_sandbox.py`

### `aaa_open_browser.py`
**Призначення**: Відкриття браузера з URL.
**Параметри**:
- `url` (str): URL для відкриття
**Залежності**: `webbrowser`

### `aaa_system.py`
**Призначення**: Системні команди (shutdown, reboot, etc.).
**Параметри**:
- `command` (str): Системна команда
**Залежності**: `os`, `subprocess`

### Інші aaa_* модулі
- `aaa_architect.py` — Архітектурні рішення
- `aaa_code_tools.py` — Інструменти для роботи з кодом
- `aaa_confirmation.py` — Підтвердження дій
- `aaa_debug_code.py` — Налагодження коду
- `aaa_help.py` — Допомога
- `aaa_programs.py` — Робота з програмами
- `aaa_utility_tools.py` — Утилітарні інструменти
- `aaa_voice_input.py` — Голосовий ввід

---

## core_* — Core Modules

Основні модулі, що забезпечують функціональність ядра.

### `core_planner.py`
**Призначення**: Планування задач через LLM.
**Методи**:
- `create_plan(task: str) -> CompiledPlan`: Створення плану
- `refine_plan(plan: CompiledPlan, feedback: str) -> CompiledPlan`: Уточнення плану
**Залежності**: `llm/`, `logic_core.py`

### `core_executor.py`
**Призначення**: Виконання планів.
**Методи**:
- `execute_plan(plan: CompiledPlan) -> ExecutionResult`: Виконання плану
- `stop()`: Зупинення виконання
**Залежності**: `FunctionRegistry`, `aaa_*`

### `core_safety_sandbox.py`
**Призначення**: Ізольоване виконання коду.
**Методи**:
- `execute_code(code: str, timeout: int) -> ExecutionResult`: Виконання коду
**Залежності**: `subprocess`, `tempfile`

### `core_cache.py`
**Призначення**: Кешування результатів (тільки idempotent операції).
**Методи**:
- `get(key: str) -> Any`: Отримання з кешу
- `set(key: str, value: Any)`: None: Запис в кеш
**Залежності**: `json`, `hashlib`

### `core_settings.py`
**Призначення**: Налаштування проєкту.
**Методи**:
- `get_setting(key: str, default: Any) -> Any`: Отримання налаштування
- `set_setting(key: str, value: Any) -> None`: Збереження налаштування
**Залежності**: `json`, `SETTINGS_SCHEMA`

**GUI налаштування**:
- `GUI_BACKEND` — GUI бекенд (pyqt6)
- `GLOBAL_VOICE_HOTKEY` — Гаряча клавіша для глобального голосового введення (наприклад: ctrl+f9)
- `GLOBAL_VOICE_ENABLED` — Увімкнути глобальне голосове введення

**Геометрія вікна** (планується):
- `GUI_WINDOW_X` — Позиція X при старті
- `GUI_WINDOW_Y` — Позиція Y при старті
- `GUI_WINDOW_WIDTH` — Ширина при старті
- `GUI_WINDOW_HEIGHT` — Висота при старті
- `GUI_WINDOW_MAXIMIZED` — Чи відкривати в повноекранному режимі
- `GUI_SAVE_GEOMETRY` — Чи зберігати геометрію при закритті

### Інші core_* модулі
- `core_action_recorder.py` — Запис дій в лог
- `core_app_profile.py` — Профілювання додатку
- `core_checkpoint.py` — Чекпоінти для відновлення
- `core_dispatcher.py` — Диспетчер задач
- `core_gui_guardian.py` — Захист GUI
- `core_macro.py` — Макроси
- `core_memory.py` — Пам'ять агента
- `core_plan_compiler.py` — Компіляція планів
- `core_planner_critic.py` — Критика планів
- `core_planner_runner.py` — Запуск планів
- `core_session_budget.py` — Бюджет сесії
- `core_streaming.py` — Стрімінг відповідей
- `core_stt_listener.py` — STT слухач
- `core_task_intake.py` — Прийом задач
- `core_tool_runtime.py` — Runtime для інструментів
- `core_undo_manager.py` — Скасування дій
- `core_windsurf_watcher.py` — Спостереження за Windsurf

---

## logic_* — Logic Modules

Логічні модулі для бізнес-логіки.

### `logic_core.py`
**Призначення**: FunctionRegistry — реєстр функцій.
**Методи**:
- `register(name: str, func: Callable) -> None`: Реєстрація функції
- `call(name: str, **kwargs) -> Any`: Виклик функції
- `get_function(name: str) -> Callable`: Отримання функції
**Залежності**: `aaa_*`, `core_*`

### `logic_commands.py`
**Призначення**: VoiceAssistant — голосовий асистент.
**Методи**:
- `process_command(text: str) -> str`: Обробка команди
- `set_tts_engine(engine) -> None`: Встановлення TTS
**Залежності**: `logic_core.py`, `STT`, `TTS`

### `logic_llm.py`
**Призначення**: LLM інтеграція.
**Методи**:
- `ask_llm(prompt: str) -> str`: Запит до LLM
- `ask_llm_with_tools(prompt: str, tools: list) -> dict`: Запит з tool-calling
**Залежності**: `llm/`

### Інші logic_* модулі
- `logic_agent_tools_schema.py` — Схема інструментів для AgentLoop
- `logic_audio_filtering.py` — Фільтрація аудіо
- `logic_repair_loop.py` — Repair loop для відновлення
- `logic_tts.py` — TTS двигун

---

## llm/ — LLM Modules

Модулі для роботи з LLM.

### `llm/endpoint_client.py`
**Призначення**: Клієнт для LLM ендпоінтів.
**Методи**:
- `chat(messages: list) -> dict`: Чат з LLM
- `stream_chat(messages: list) -> Iterator`: Стрімінг чат
**Залежності**: `requests`, `openai`

### `llm/groq_client.py`
**Призначення**: Groq API клієнт.
**Методи**:
- `chat(messages: list) -> dict`: Чат з Groq
**Залежності**: `groq`

### `llm/provider_chain.py`
**Призначення**: Ланцюг провайдерів LLM.
**Методи**:
- `get_provider() -> BaseProvider`: Отримання провайдера
**Залежності**: `endpoint_client.py`, `groq_client.py`

### `llm/router.py`
**Призначення**: Роутинг запитів до різних LLM.
**Методи**:
- `route(request: dict) -> dict`: Роутинг запиту
**Залежності**: `provider_chain.py`

---

## gui_tabs/ — GUI Tabs

Модулі для PyQt6 GUI вкладок.

### `gui_tabs/main_window.py`
**Призначення**: MultiTabGUI — головне вікно з вкладками.
**Класи**:
- `MultiTabGUI(QMainWindow)`: Головне вікно
**Вкладки**: ChatTab, SettingsTab, LogsTab, StatisticsTab, AboutTab, ToolsTab

### `gui_tabs/base_tab.py`
**Призначення**: BaseTab — базовий клас для вкладок.
**Методи**:
- `create_group(title: str) -> QGroupBox`: Створення групи
- `_build_content(layout: QVBoxLayout)`: Побудова контенту

### `gui_tabs/chat_tab.py`
**Призначення**: ChatTab — вкладка чату.
**Методи**:
- `add_message(role: str, text: str)`: Додавання повідомлення
- `send_message()`: Відправка повідомлення

### `gui_tabs/settings_tab.py`
**Призначення**: SettingsTab — вкладка налаштувань.
**Методи**:
- `save_settings()`: Збереження налаштувань
- `reset_settings()`: Скидання налаштувань

### `gui_tabs/logs_tab.py`
**Призначення**: LogsTab — вкладка логів.
**Методи**:
- `add_log(level: str, module: str, message: str)`: Додавання логу
- `clear_logs()`: Очищення логів

### `gui_tabs/statistics_tab.py`
**Призначення**: StatisticsTab — вкладка статистики.
**Методи**:
- `refresh_statistics()`: Оновлення статистики

### `gui_tabs/about_tab.py`
**Призначення**: AboutTab — вкладка про програму.
**Контент**: Назва, версія, опис, функції, технології

### `gui_tabs/tools_tab.py`
**Призначення**: ToolsTab — вкладка інструментів.
**Методи**:
- `execute_tool()`: Виконання інструменту

### `gui_tabs/constants.py`
**Призначення**: Константи для GUI.
**Константи**:
- `ROLE_COLORS`: Кольори для ролей в чаті
- `LOG_LEVEL_COLORS`: Кольори для рівнів логів
- `QUICK_COMMANDS`: Швидкі команди
- `TAB_NAMES`: Назви вкладок
- `SettingsDefaults`: Дефолтні налаштування

---

## core_gui_pyqt6/ — PyQt6 GUI

Модулі для PyQt6 GUI.

### `core_gui_pyqt6/main_window.py`
**Призначення**: MainWindowPyQt6 — головне вікно PyQt6.
**Класи**:
- `MainWindowPyQt6(QMainWindow)`: Головне вікно
**Компоненти**: чат, план, налаштування, кнопки, статус-бар

### `core_gui_pyqt6/settings_tab_qt.py`
**Призначення**: SettingsTabQtMixin — міксин для налаштувань.
**Методи**:
- `_render_settings()`: Рендеринг налаштувань
- `_save_settings()`: Збереження налаштувань

### `core_gui_pyqt6/chat_panel_qt.py`
**Призначення**: ChatPanelQtMixin — міксин для чату.
**Методи**:
- `add_message(sender: str, message: str)`: Додавання повідомлення
- `start_stream_message()`: Початок стрімінгу
- `append_stream_chunk(chunk: str)`: Додавання чанку
- `end_stream_message()`: Кінець стрімінгу

### `core_gui_pyqt6/plan_panel_qt.py`
**Призначення**: PlanPanelQtMixin — міксин для плану.
**Методи**:
- `show_plan_panel(steps_info: list)`: Показати план
- `update_plan_step(data: dict)`: Оновити крок
- `finish_plan_panel(stats: dict)`: Завершити план

### `core_gui_pyqt6/confirmation_qt.py`
**Призначення**: ConfirmationQtMixin — міксин для підтверджень.
**Методи**:
- `show_confirmation(question: str, callback: Callable)`: Показати діалог
- `hide_confirmation()`: Приховати діалог

### `core_gui_pyqt6/llm_endpoints_editor_qt.py`
**Призначення**: LLMEndpointsEditor — редактор LLM ендпоінтів.
**Методи**:
- `get() -> list[dict]`: Отримання ендпоінтів
- `set(endpoints: list[dict])`: Встановлення ендпоінтів

---

## 📝 Примітка

Цей документ є базовим шаблоном. Повний опис всіх модулів буде доповнюватися поступово.

Для автогенерації документації з docstring використовуйте:
```bash
pdoc --html --output-dir docs functions
```
або
```bash
sphinx-apidoc -o docs/ functions/
```
