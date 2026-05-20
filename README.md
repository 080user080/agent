# 🤖 Агент-Помічник (Agent Assistant)

Україномовний AI-агент для автоматизації завдань з роботою з файлами, кодом, системою та інтернетом.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚠️ Критичні компоненти (НЕ ЗМІНЮВАТИ БЕЗ УЗГОДЖЕННЯ)

### Глобальне голосове введення (`functions/planning/global_voice_input.py`)
- **Критичні методи:** `_insert_segment`, `_send_input_unicode`
- **Опис:** Логіка вставки тексту оптимізована для Windows 10/11 з підтримкою кирилиці та емодзі
- **Ризики змін:** Дублювання тексту, відсутність вставки, спотворення символів

### Керування клавіатурою (`functions/tools/tools_mouse_keyboard.py`)
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

## 🧪 Тестування

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

# Запуск PyQt6 GUI тестів
python -m pytest tests/test_pyqt6_gui.py -v

# З покриттям
coverage run -m pytest tests/
coverage report
```

Для зручності використовуйте `Start_main_qt.bat` для запуску GUI версії через venv.

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
- **Open Interpreter fallback** — автоматичне встановлення відсутніх модулів через локальний LM Studio
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
- **Dynamic input height** — поле вводу автоматично збільшується (60–160px)
- **LLM endpoints editor** — налаштування кількох LLM провайдерів
- **Plan panel** — прогрес виконання плану з кнопками управління

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
│   ├── audio/                    # Аудіо-обробка (STT/TTS, фільтрація)
│   │   ├── core_stt_listener.py  # STT слухач для голосового вводу
│   │   ├── logic_audio.py        # Аудіо логіка обробки
│   │   ├── logic_audio_filtering.py # Фільтрація аудіо сигналів
│   │   ├── logic_continuous_listener.py # Неперервний слухач голосових команд
│   │   ├── logic_stt.py          # Speech-to-Text конвертація (Whisper, w2v-bert-uk)
│   │   └── logic_tts.py          # Text-to-Speech озвучування (edge-tts)
│   ├── llm/                      # LLM-шар
│   │   ├── router.py                 # RequestRouter для класифікації запитів
│   │   ├── provider_chain.py        # ProviderChain з fallback ланцюгом
│   │   ├── endpoint_client.py        # OpenAI-compatible endpoint client
│   │   ├── groq_client.py            # Groq API client
│   │   └── response_parser.py        # Парсер відповідей LLM
│   ├── planning/                 # Планинг-шар (task intake, context analysis)
│   │   ├── agent_loop.py              # AgentLoop (observe → plan → act → check)
│   │   ├── core_task_intake.py        # Прийом задач
│   │   ├── logic_context_analyzer.py  # Аналіз контексту
│   │   ├── pipeline_code.py           # Code generation pipeline
│   │   └── ... (інші planning модулі)
│   ├── runtime/                  # Runtime-оркестрація
│   │   ├── core_app_profile.py        # Профілювання додатку
│   │   ├── core_checkpoint.py         # Чекпоінти для відновлення
│   │   ├── core_dispatcher.py         # Диспетчер команд між GUI/planner/інструментами
│   │   ├── core_executor.py           # Виконавець планів (асинхронне виконання)
│   │   ├── core_loop_detector.py      # LoopDetector — захист від зациклення
│   │   ├── core_macro.py              # Макроси (збереження/виконання послідовних дій)
│   │   ├── core_memory.py             # Пам'ять сесій (історія, задачі, summaries)
│   │   ├── core_safety_sandbox.py     # Сендбокс для ізоляції небезпечних операцій
│   │   ├── core_session_budget.py     # Бюджет сесії (ліміти запитів, час)
│   │   ├── core_tool_runtime.py       # Runtime для реєстрації та виконання інструментів
│   │   ├── core_windsurf_watcher.py   # Спостереження за Windsurf IDE
│   │   └── ... (інші runtime модулі)
│   ├── tools/                    # Desktop/browser/media інструменти
│   │   ├── mouse_keyboard.py    # Mouse/keyboard automation
│   │   ├── window_manager.py    # Window manager
│   │   ├── screen_capture.py    # Screen capture
│   │   ├── ocr.py               # OCR (pytesseract/easyocr)
│   │   ├── ui_detector.py       # UI detection
│   │   ├── app_recognizer.py    # App recognizer
│   │   ├── visual_diff.py       # Visual diff
│   │   ├── ui_accessibility.py  # UI Automation (uiautomation/pywinauto)
│   │   └── browser_cdp.py       # Browser automation (Playwright CDP)
│   ├── core_*.py                  # Core модулі (~15)
│   │   ├── planner.py            # Планер з retry
│   │   ├── executor.py           # Виконавець планів
│   │   ├── cache.py              # Безпечний кеш (idempotent операції)
│   │   ├── settings.py           # Менеджер налаштувань
│   │   └── ... (інші core модулі)
│   ├── logic_*.py                 # Логіка (~15)
│   │   ├── commands.py          # Обробка команд
│   │   ├── llm_tools.py         # OpenAI-compatible tool-calling
│   │   ├── tts.py / stt.py      # TTS/STT конвертація
│   │   ├── context_analyzer.py  # Аналіз контексту
│   │   ├── ui_navigator.py      # UI навігація
│   │   ├── scenario_runner.py   # Scenario runner
│   │   ├── repair_loop.py       # Repair loop для відновлення
│   │   └── watcher.py           # Watcher для умов
│   ├── aaa_*.py                   # LLM-tool обгортки (~15)
│   ├── agent_loop.py              # AgentLoop (observe → plan → act → check)
│   ├── task_spec.py               # TaskSpecCompiler (структурована декомпозиція)
│   ├── ai_actors.py               # AI Actors (Codex/Windsurf/Cursor)
│   ├── global_voice_input.py      # Global voice input (Windows hook)
│   ├── self_learning.py           # Self-learning module
│   └── ... (інші модулі)
├── core_gui_pyqt6/             # GUI компоненти (PyQt6)
│   ├── main_window.py             # Головне вікно (PyQt6)
│   ├── settings_tab_qt.py         # Вкладка налаштувань (PyQt6)
│   ├── chat_panel_qt.py           # Панель чату (PyQt6)
│   ├── plan_panel_qt.py           # Панель плану (PyQt6)
│   ├── confirmation_qt.py         # Діалог підтверджень (PyQt6)
│   └── llm_endpoints_editor_qt.py # Редактор LLM ендпойнтів (PyQt6)
├── backup/                     # Застарілі компоненти
│   ├── tkinter_legacy/            # Tkinter GUI (застаріло)
│   └── gui_tabs/                  # Старі multi-tab вкладки (застаріло)
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
├── tests/                      # Тести (pytest, 64 файли)
├── TEST_GUI/                   # GUI діагностичні тести (10 файлів)
├── debug_logs/                 # Логи відладки
├── requirements.txt            # Рантайм-залежності
├── status.md                   # Статус розробки + дорожня карта
├── TASKS.md                    # Поточні задачі
├── TASKS_Done.md               # Виконані задачі
└── README.md                   # Цей файл
```

---


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
    core_executor    logic_llm_tools.ask_llm_with_tools()
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

### Open Interpreter інтеграція

**`functions/tools_open_interpreter.py`** — модуль для self-healing виконання коду

- **`is_available()`** — перевіряє чи Open Interpreter доступний і увімкнений (`OI_ENABLED` setting)
- **`get_executor(lm_studio_url)`** — повертає singleton Open Interpreter executor з налаштуванням LM Studio
- **`oi_execute_with_healing(code, task_description)`** — виконує код з автоматичним встановленням відсутніх модулів через Open Interpreter

**Як працює:**
1. При виконанні `execute_python` і виникненні `ModuleNotFoundError`
2. Автоматично викликається Open Interpreter через локальний LM Studio
3. LLM аналізує помилку і генерує команду для встановлення відсутнього модуля
4. Повторно виконує код з успішним результатом

**Налаштування:**
- `OI_ENABLED` (bool, default `False`) — увімкнення Open Interpreter fallback
- `LM_STUDIO_URL` (string, default `"http://localhost:1234/v1/chat/completions"`) — URL локального LM Studio сервера

### Logic та Tools (скорочено)

- **`logic_*`** — `logic_core` (FunctionRegistry), `logic_commands`, `logic_llm_tools`, `logic_tts`/`logic_stt`/`logic_audio*`, `logic_continuous_listener`, а також модулі Phase 5–11: `logic_context_analyzer`, `logic_ui_navigator`, `logic_scenario_runner`, `logic_task_runner`, `logic_repair_loop`, `logic_watcher`, `logic_permission_gate`, `logic_plan_critic`, `logic_execution_report`.
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

*Останнє оновлення: травень 2026*
