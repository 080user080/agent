# 🤖 Агент-Помічник (Agent Assistant)

Україномовний AI-агент для автоматизації завдань з роботою з файлами, кодом, системою та інтернетом.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚠️ Критичні компоненти (НЕ ЗМІНЮВАТИ БЕЗ УЗГОДЖЕННЯ)

### Глобальне голосове введення (`functions/global_voice_input.py`)
- **Критичні методи:** `_insert_segment`, `_send_input_unicode`
- **Опис:** Логіка вставки тексту оптимізована для Windows 10/11 з підтримкою кирилиці та емодзі
- **Ризики змін:** Дублювання тексту, відсутність вставки, спотворення символів

### Керування клавіатурою (`functions/tools_mouse_keyboard.py`)
- **Критичні методи:** `send_input_unicode`, `insert_text_smart`
- **Опис:** Універсальна вставка тексту з адаптивною логікою для різних типів вікон
- **Ризики змін:** Дублювання тексту, відсутність вставки, спотворення символів

**Примітка:** Ці методи використовують SendInput Unicode, WM_PASTE та Ctrl+V з оптимізаціями для Chrome, PyQt6, Notepad та інших додатків. Будь-які зміни можуть порушити роботу глобального голосового введення.

---

## 🚀 Швидкий старт

### Вимоги
- Python 3.10 або новіше
- Windows 10/11
- [LM Studio](https://lmstudio.ai/) (локальні LLM) або OpenAI API key

### Встановлення

```bash
# Клонування репозиторію
git clone https://github.com/080user080/agent.git
cd agent

# Встановлення залежностей
pip install -r requirements.txt

# PyTorch встановити окремо (під вашу версію CUDA або CPU-only)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Запуск (GUI — основний спосіб)
python run.py --qt  # PyQt6 (рекомендовано)

# Або консольний режим (без GUI)
python main.py
```

### Перше налаштування

1. Запустіть агента — відкриється GUI
2. Перейдіть у вкладку **"Налаштування"**
3. Налаштуйте LLM ендпоінти (LM Studio або OpenAI)
4. Перевірте з'єднання з кнопкою **"Test"**
5. Готово! Можете починати спілкування

---

## 🧪 Діагностичні тести

У проекті є два постійних тести для діагностики (НЕ ВИДАЛЯТИ!):

### `test_llm_endpoint.py`
Тест для перевірки доступності та роботи LLM endpoints.
```bash
python test_llm_endpoint.py
```
Перевіряє:
- Завантаження конфігурації LLM endpoints
- З'єднання з primary endpoint
- Коректність відповіді на тестовий запит

### `test_duplication_direct.py`
Тест для перевірки GUI автоматизації та LLM response.
```bash
python test_duplication_direct.py
```
Перевіряє:
- Запуск агента в GUI режимі
- Активацію вікна агента
- Вставку тексту через keyboard automation
- LLM response на команду (наприклад "відкрий браузер")
- Виконання дій через tools

**Важливо:** Ці тести використовуються для діагностики проблем і не повинні видалятися.

---

## ✨ Можливості

### 🧠 Інтелектуальне планування
- **Planner** — розбиває складні задачі на кроки
- **Auto-repair** — до 3 спроб виправлення помилок
- **JSON output** — структуровані плани з retry-механізмом
- **AgentLoop** — observe → plan → act → check цикл для автономного виконання

### 💻 Робота з кодом
- Читання, створення, редагування файлів
- Пошук у коді (`search_in_code`)
- Виконання Python (`execute_python`)
- Git інтеграція (status, diff, commit)
- **Code generation pipeline** — автоматична генерація коду через AI actors

### 🤖 Оркестрація ШІ
- **RequestRouter** — класифікація запитів за типом (CODE/DEBUG/GUI/WEB/GENERAL/QUICK)
- **ProviderChain** — fallback ланцюг з кількома моделями
- **Multi-LLM support** — GPT-OSS 20B, Gemini, DeepSeek, Groq
- **Quota tracking** — управління лімітами запитів

### 🛡️ Безпека
- **Підтвердження дій** — зворотний відлік 30с для небезпечних операцій
- **Кеш тільки idempotent** — не кешуємо створення/видалення файлів
- **Tool policies** — маркування ризиків для кожної функції
- **Safety sandbox** — ізольоване виконання Python коду

### 🎙️ Голосовий ввід
- **STT (Speech-to-Text)** — голосові команди (Whisper, w2v-bert-uk)
- **TTS (Text-to-Speech)** — озвучування відповідей (edge-tts)
- **Global voice input** — глобальний hook на Windows (Ctrl+Shift+V)
- Індикатор мікрофона в GUI

### 📊 Панель плану
- Прогрес-бар виконання
- Статуси кроків: pending → running → ok/error/blocked/skipped
- Деталі кожного кроку
- Кнопки "Виконати" і "Стоп" для запуску планів

### 🎯 Самонавчання
- **Self-learning module** — аналіз помилок і генерація правил
- **Skills база** — накопичення успішних паттернів
- **Execution logs** — JSONL логи виконань задач

### 🖥️ GUI
- **PyQt6 GUI** — сучасний багатовкладковий інтерфейс (run.py --qt)
- **Thread-safe messages** — потікобезпечна черга повідомлень
- **Settings editor** — динамічний рендеринг налаштувань
- **Multi-tab interface** — Чат, Налаштування, Логи, Статистика, Про програму, Інструменти

### ⚙️ Налаштування
- GUI редактор налаштувань (вкладка "Налаштування")
- Пошук по налаштуваннях
- Спойлери для груп
- Збереження в `user_settings.json`
- **LLM endpoints editor** — налаштування кількох LLM провайдерів

---

## 📁 Структура проєкту

```
agent/
├── run.py                      # Універсальна точка входу (PyQt6)
├── run_assistant_qt.py         # Точка входу з GUI (PyQt6)
├── main.py                     # Консольна точка входу (AssistantCore)
├── functions/                  # Основна логіка (~100 модулів)
│   ├── llm/                      # LLM-шар
│   │   ├── router.py                 # RequestRouter для класифікації запитів
│   │   ├── provider_chain.py        # ProviderChain з fallback ланцюгом
│   │   ├── endpoint_client.py        # OpenAI-compatible endpoint client
│   │   ├── groq_client.py            # Groq API client
│   │   └── response_parser.py        # Парсер відповідей LLM
│   ├── core_*.py                  # Core модулі (~20)
│   │   ├── core_planner.py            # Планер з retry
│   │   ├── core_executor.py           # Виконавець планів
│   │   ├── core_memory.py             # Пам'ять сесій
│   │   ├── core_cache.py              # Безпечний кеш
│   │   ├── core_tool_runtime.py       # Реєстр інструментів
│   │   ├── core_settings.py           # Менеджер налаштувань
│   │   ├── core_dispatcher.py         # Диспетчер команд
│   │   ├── core_streaming.py          # Стрімінг відповідей LLM
│   │   ├── core_stt_listener.py       # STT-лістнер
│   │   ├── core_safety_sandbox.py     # Сендбокс безпеки
│   │   ├── core_action_recorder.py    # Аудит GUI-дій
│   │   ├── core_undo_manager.py       # Undo для GUI-дій
│   │   ├── core_gui_guardian.py       # Захист GUI-дій
│   │   ├── core_checkpoint.py         # Checkpoint/Resume
│   │   └── core_session_budget.py     # Budget для сесій
│   ├── logic_*.py                 # Логіка (~20)
│   │   ├── logic_core.py              # FunctionRegistry
│   │   ├── logic_commands.py          # Обробка команд
│   │   ├── logic_llm.py               # LLM взаємодія
│   │   ├── logic_tts.py / logic_stt.py / logic_audio.py / logic_audio_filtering.py
│   │   ├── logic_continuous_listener.py
│   │   ├── logic_context_analyzer.py  # Аналіз контексту
│   │   ├── logic_ui_navigator.py      # UI навігація
│   │   ├── logic_scenario_runner.py   # Scenario runner
│   │   ├── logic_agent_tools_schema.py # Tool-calling schema
│   │   ├── logic_ai_adapter.py        # AI Provider adapter
│   │   ├── logic_provider_registry.py # Provider registry
│   │   ├── logic_task_runner.py       # Task runner
│   │   ├── logic_repair_loop.py       # Repair loop
│   │   └── logic_watcher.py           # Watcher для умов
│   ├── tools_*.py                 # GUI-інструменти (~10)
│   │   ├── tools_mouse_keyboard.py    # Mouse/keyboard automation
│   │   ├── tools_window_manager.py    # Window manager
│   │   ├── tools_screen_capture.py    # Screen capture
│   │   ├── tools_ocr.py               # OCR (pytesseract/easyocr)
│   │   ├── tools_ui_detector.py       # UI detection
│   │   ├── tools_app_recognizer.py    # App recognizer
│   │   ├── tools_visual_diff.py       # Visual diff
│   │   ├── tools_ui_accessibility.py  # UI Automation (uiautomation/pywinauto)
│   │   └── tools_browser_cdp.py       # Browser automation (Playwright CDP)
│   ├── agent_loop.py              # AgentLoop (observe → plan → act → check)
│   ├── task_spec.py               # TaskSpecCompiler (структурована декомпозиція)
│   ├── ai_actors.py               # AI Actors (Codex/Windsurf/Cursor)
│   ├── global_voice_input.py      # Global voice input (Windows hook)
│   ├── self_learning.py           # Self-learning module
│   ├── plan_executor.py           # Plan executor bridge
│   ├── windsurf_watcher_executor.py # Windsurf Watch GUI
│   ├── pipeline_code.py           # Code generation pipeline
│   ├── aaa_*.py                   # LLM-tool обгортки (~15)
│       ├── aaa_architect.py / aaa_code_tools.py / aaa_debug_code.py
│       ├── aaa_create_file.py / aaa_edit_file.py / aaa_execute_python.py
│       ├── aaa_open_browser.py / aaa_programs.py / aaa_system.py
│       └── aaa_voice_input.py / aaa_utility_tools.py / aaa_confirmation.py
├── core_gui_pyqt6/             # GUI компоненти (PyQt6)
│   ├── main_window.py             # Головне вікно (PyQt6)
│   ├── settings_tab_qt.py         # Вкладка налаштувань (PyQt6)
│   ├── chat_panel_qt.py           # Панель чату (PyQt6)
│   ├── plan_panel_qt.py           # Панель плану (PyQt6)
│   ├── confirmation_qt.py         # Діалог підтверджень (PyQt6)
│   └── llm_endpoints_editor_qt.py # Редактор LLM ендпойнтів (PyQt6)
├── gui_tabs/                   # GUI вкладки (PyQt6 multi-tab)
│   ├── main_window.py             # MultiTabGUI (6 вкладок)
│   ├── base_tab.py               # BaseTab
│   ├── chat_tab.py               # ChatTab
│   ├── settings_tab.py           # SettingsTab
│   ├── logs_tab.py               # LogsTab
│   ├── statistics_tab.py         # StatisticsTab
│   ├── about_tab.py              # AboutTab
│   ├── tools_tab.py              # ToolsTab
│   └── constants.py              # Константи для GUI
├── docs/                       # Документація
│   ├── ARCHITECTURE.md           # Архітектура проєкту
│   ├── MODULES.md                # Опис модулів
│   ├── API.md                    # API для інтеграції
│   ├── CONTRIBUTING.md           # Гайд для контриб'юторів
│   ├── tests.md                  # Тестові сценарії
│   ├── PLAN_COMPUTER_USE.md      # План використання комп'ютера
│   ├── CHANGELOG.md              # Історія змін
│   ├── SECURITY.md               # Безпека та ризики
│   ├── FAQ.md                    # Часті питання
│   └── LLM_to_LM_Studio.md       # LLM інтеграція
├── tests/                      # Тести (pytest)
│   ├── test_core_planner.py
│   ├── test_core_memory.py
│   ├── test_core_executor.py
│   ├── test_agent_loop.py
│   ├── test_action_decider.py
│   ├── test_plan_executor.py
│   ├── test_task_spec.py
│   ├── test_tools_mouse_keyboard.py
│   ├── test_tools_window_manager.py
│   ├── test_tools_ocr.py
│   └── test_pyqt6_gui.py
├── TEST_GUI/                   # Тест GUI
│   └── test_multi_tab_gui.py
├── requirements.txt            # Рантайм-залежності
├── pytest.ini                  # Конфіг тестів
├── status.md                   # Статус розробки + дорожня карта
├── TASKS.md                    # Поточні задачі
├── TASKS_Done.md               # Виконані задачі
└── README.md                   # Цей файл
```

---

## 🧪 Тести

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash
# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent

# Запуск всіх тестів
python -m pytest tests/ -v

# Запуск конкретного файлу
python -m pytest tests/test_core_planner.py -v

# З покриттям
coverage run -m pytest tests/
coverage report
```

Для зручності використовуйте `Start_main_qt.bat` для запуску GUI версії через venv.

---

## 🛠️ Архітектура

### Потік обробки команди

```
Користувач → GUI → logic_commands.process_command()
                    ↓
            ┌───────┴───────┐
            ↓               ↓
    Planner (якщо      Кеш (якщо
    потрібен план)     увімкнено)
            ↓               ↓
    core_executor    logic_llm.ask_llm()
    (виконання)              ↓
            ↓          Streaming/Regular
            └───────┬───────┘
                    ↓
              Відповідь GUI
```

### Core модулі

| Модуль | Призначення |
|--------|-------------|
| `core_planner` | Генерація планів з retry-механізмом |
| `core_executor` | Асинхронне виконання кроків плану |
| `core_memory` | Зберігання історії, задач, summaries |
| `core_cache` | Безпечне кешування idempotent операцій |
| `core_settings` | Управління налаштуваннями |
| `core_tool_runtime` | Реєстр та виконання інструментів + аудит |
| `core_dispatcher` | Диспетчер команд між GUI / planner / інструментами |
| `core_streaming` | Стрімінг відповідей LLM до GUI |
| `core_stt_listener` | Прийом голосового вводу |
| `core_safety_sandbox` | Сендбокс для `execute_python` та файлових дій |
| `core_action_recorder` | Запис GUI-дій + скріншотів в `logs/gui_actions.jsonl` |
| `core_undo_manager` | Undo для GUI-дій (введення тексту, переміщення файлів) |
| `core_gui_guardian` | Перевірка ризиків та підтвердження небезпечних GUI-дій |

### Logic та Tools (скорочено)

- **`logic_*`** — `logic_core` (FunctionRegistry), `logic_commands`, `logic_llm`, `logic_tts`/`logic_stt`/`logic_audio*`, `logic_continuous_listener`, а також модулі Phase 5: `logic_context_analyzer`, `logic_ui_navigator`, `logic_scenario_runner`.
- **`tools_*`** — GUI-інструменти Phase 1–4: `tools_mouse_keyboard`, `tools_window_manager`, `tools_screen_capture`, `tools_ocr`, `tools_ui_detector`, `tools_app_recognizer`, `tools_visual_diff`.
- **`aaa_*`** — LLM-обгортки (tool wrappers), які викликаються з планів: `aaa_create_file`, `aaa_edit_file`, `aaa_execute_python`, `aaa_open_browser`, `aaa_programs`, `aaa_system`, тощо.

---

## 🔧 Налаштування

### Конфігураційні файли

- `user_settings.json` — користувацькі налаштування
- `cache_data.json` — кеш (автоматично)
- `session_memory.json` — пам'ять сесій (автоматично)

### Ключові налаштування

| Параметр | Опис | За замовчуванням |
|----------|------|------------------|
| `LLM_ENDPOINTS` | Список LLM ендпоінтів | `[{"name": "Local LM Studio", "url": "http://localhost:1234/v1/chat/completions", "model": "local"}]` |
| `LLM_TIMEOUT` | Таймаут запиту (сек) | 120 |
| `LLM_TEMPERATURE` | Температура генерації | 0.1 |
| `STREAMING_ENABLED` | Стрімінг відповідей | true |
| `TTS_ENABLED` | Озвучування відповідей | false |
| `STT_ENABLED` | Голосовий ввід | false |
| `CACHE_ENABLED` | Кешування команд | false |
| `CONFIRM_DANGEROUS` | Підтвердження небезпечних дій | true |

---

## 📖 Приклади використання

### Прості команди
```
Користувач: Привіт!
Агент: Привіт! Чим можу допомогти?
```

### Задачі з плануванням
```
Користувач: Створи файл hello.py з функцією greeting
Агент: [створює план з 3 кроків]
1. Створити файл hello.py ✓
2. Написати функцію greeting ✓
3. Перевірити код ✓
```

### Робота з кодом
```
Користувач: Знайди всі функції в файлі utils.py
Агент: Знайдено 5 функцій: helper1(), helper2(), ...
```

### Обчислення
```
Користувач: Скільки буде 123 * 456?
Агент: Результат: 56088
```

---

## 📚 Документація

### Основні файли
- [status.md](status.md) — поточний стан проєкту та пріоритети
- [TASKS.md](TASKS.md) — поточні задачі та їх статус
- [TASKS_Done.md](TASKS_Done.md) — виконані задачі

### Технічна документація (docs/)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архітектура проєкту
- [docs/MODULES.md](docs/MODULES.md) — опис модулів (aaa_*, core_*, logic_*)
- [docs/API.md](docs/API.md) — API для інтеграції
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — як внести внесок в проєкт
- [docs/tests.md](docs/tests.md) — тестові сценарії та чеклісти
- [docs/PLAN_COMPUTER_USE.md](docs/PLAN_COMPUTER_USE.md) — план використання комп'ютера

### Додаткова документація
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — історія змін
- [docs/SECURITY.md](docs/SECURITY.md) — безпека та ризики
- [docs/FAQ.md](docs/FAQ.md) — часті питання

---

## 🤝 Внесок в проєкт

1. Форкніть репозиторій
2. Створіть feature branch (`git checkout -b feature/amazing-feature`)
3. Зробіть commit зі змінами (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Відкрийте Pull Request

---

## 📝 Ліцензія

Розповсюджується під ліцензією MIT. Дивіться [LICENSE](LICENSE) для деталей.

---

## 🙏 Подяки

- [LM Studio](https://lmstudio.ai/) — локальні LLM
- [OpenAI](https://openai.com/) — API для GPT моделей
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) — STT
- [edge-tts](https://github.com/rany2/edge-tts) — TTS

---

*Останнє оновлення: квітень 2026*
