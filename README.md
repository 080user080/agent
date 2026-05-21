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
- **Code generation pipeline** — автоматична генерація коду через AI actors

### 💻 Робота з кодом
- Читання, створення, редагування файлів
- Пошук у коді (`search_in_code`)
- Виконання Python (`execute_python`)
- **Open Interpreter fallback** — автоматичне встановлення відсутніх модулів через локальний LM Studio
- Git інтеграція (status, diff, commit)

### 🤖 Оркестрація ШІ
- **RequestRouter** — класифікація запитів за типом (CODE/DEBUG/GUI/WEB/GENERAL/QUICK)
- **ProviderChain** — fallback ланцюг з кількома моделями
- **Multi-LLM support** — GPT-OSS 20B, Gemini, DeepSeek, Groq
- **Quota tracking** — управління лімітами запитів
- **Vision-LM** — аналіз зображень через OpenAI/Claude/Gemini

### 🛡️ Безпека
- **Підтвердження дій** — зворотний відлік 30с для небезпечних операцій
- **Кеш тільки idempotent** — не кешуємо створення/видалення файлів
- **Tool policies** — маркування ризиків для кожної функції
- **Safety sandbox** — ізольоване виконання Python коду
- **GUIGuardian** — перевірка ризиків GUI-дій

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

### 🖥️ GUI
- **PyQt6 GUI** — сучасний багатовкладковий інтерфейс (run.py --qt)
- **Thread-safe messages** — потікобезпечна черга повідомлень
- **Settings editor** — динамічний рендеринг налаштувань
- **Dynamic input height** — поле вводу автоматично збільшується (60–160px)
- **LLM endpoints editor** — налаштування кількох LLM провайдерів
- **Plan panel** — прогрес виконання плану з кнопками управління

### 🎯 Самонавчання
- **Self-learning module** — аналіз помилок і генерація правил
- **Skills база** — накопичення успішних паттернів
- **Execution logs** — JSONL логи виконань задач

### 🖥️ Desktop Automation (Phase 1-11)
- **Mouse/keyboard** — керування мишею та клавіатурою через pyautogui
- **Window manager** — керування вікнами (win32gui/pygetwindow)
- **Screen capture** — скріншоти з mss + PIL + OpenCV
- **OCR** — розпізнавання тексту (pytesseract/easyocr)
- **UI detection** — пошук кнопок, полів, чекбоксів через OpenCV + OCR
- **App recognition** — визначення активного додатку та діалогів
- **Visual diff** — порівняння скріншотів (baseline)
- **UI Accessibility** — Windows UIA API (uiautomation + pywinauto)
- **Browser CDP** — браузерна автоматизація (Playwright)
- **Scenario Runner** — виконання сценаріїв тестування GUI
- **TaskRunner** — повна фаза виконання з PermissionGate, Expectations, SessionBudget, PlanCritic
- **Watcher** — моніторинг умов виконання

---

## 📁 Структура проєкту

```
agent/
├── run.py                          # Універсальна точка входу (PyQt6)
├── run_assistant_qt.py             # Точка входу з GUI (PyQt6)
├── main.py                         # Консольна точка входу (AssistantCore)
├── pyproject.toml                  # Налаштування проєкту + CI
├── requirements.txt                # Рантайм-залежності
├── requirements-dev.txt            # Dev-залежності
│
├── functions/                      # Основна логіка
│   ├── __init__.py
│   ├── config.py                   # Глобальна конфігурація
│   ├── global_voice_input.py       # Глобальний голосовий ввід (Windows hook)
│   ├── logic_execution_report.py   # Звіт виконання
│   │
│   ├── audio/                      # Аудіо-обробка (STT/TTS)
│   │   ├── core_stt_listener.py    # STT слухач
│   │   ├── logic_audio.py          # Аудіо логіка
│   │   ├── logic_audio_filtering.py# Фільтрація аудіо
│   │   ├── logic_continuous_listener.py# Неперервний слухач
│   │   ├── logic_stt.py            # Speech-to-Text (Whisper, w2v-bert-uk)
│   │   └── logic_tts.py            # Text-to-Speech (edge-tts)
│   │
│   ├── llm/                        # LLM-шар
│   │   ├── __init__.py             # Експорт LLM модулів
│   │   ├── helpers.py              # Допоміжні функції для LLM
│   │   ├── logic_llm_tools.py      # OpenAI-compatible tool-calling
│   │   ├── providers_vision.py     # Vision-LM (OpenAI/Claude/Gemini)
│   │   └── ... (інші LLM модулі)
│   │
│   ├── planning/                   # Планинг-шар
│   │   ├── agent_loop.py               # AgentLoop (observe → plan → act → check)
│   │   ├── core_planner.py             # Планер з retry
│   │   ├── core_task_intake.py          # Прийом задач
│   │   ├── logic_context_analyzer.py    # Аналіз контексту
│   │   ├── logic_task_runner.py         # TaskRunner з handler-реєстром
│   │   ├── pipeline_code.py            # Code generation pipeline
│   │   └── ... (інші planning модулі)
│   │
│   ├── runtime/                    # Runtime-оркестрація
│   │   ├── __init__.py             # Експорт runtime модулів
│   │   ├── conditions_windows.py   # Умови виконання для Windows
│   │   ├── core_initializer_checks.py # Перевірки ініціалізації
│   │   ├── core_windsurf_watcher.py   # Windsurf Watcher
│   │   ├── logic_core.py             # FunctionRegistry
│   │   ├── logic_permission_gate.py   # 4-рівнева policy stack
│   │   ├── logic_watcher.py           # Watcher engine
│   │   └── ... (інші runtime модулі)
│   │
│   ├── gui/                        # GUI-логіка
│   │   ├── core_gui_guardian.py    # GUIGuardian Risk Assessment
│   │   └── logic_commands.py       # VoiceAssistant — обробка команд
│   │
│   ├── tools/                      # Desktop/browser/media інструменти
│   │   ├── aaa_file_operations.py     # Файлові операції
│   │   ├── aaa_open_interpreter.py    # Open Interpreter fallback
│   │   ├── tools_app_recognizer.py    # App recognizer
│   │   ├── tools_browser_cdp.py       # Browser CDP automation
│   │   ├── tools_mouse_keyboard.py    # Mouse/keyboard automation
│   │   ├── tools_ocr.py               # OCR (pytesseract/easyocr)
│   │   ├── tools_playwright.py        # Playwright integration
│   │   ├── tools_screen_capture.py    # Screen capture
│   │   ├── tools_ui_accessibility.py  # Windows UIA API
│   │   ├── tools_ui_detector.py       # UI detection (OpenCV+OCR)
│   │   ├── tools_visual_diff.py       # Visual diff
│   │   └── tools_window_manager.py    # Window manager
│   │
│   └── ... (інші core/logic модулі)
│
├── core_gui_pyqt6/                 # GUI компоненти (PyQt6)
│   ├── __init__.py
│   ├── main_window.py              # Головне вікно
│   ├── settings_tab_qt.py          # Вкладка налаштувань
│   ├── chat_panel_qt.py            # Панель чату
│   ├── plan_panel_qt.py            # Панель плану
│   ├── confirmation_qt.py          # Діалог підтверджень
│   └── llm_endpoints_editor_qt.py  # Редактор LLM ендпойнтів
│
├── docs/                           # Документація
│   ├── API.md                      # API для інтеграції
│   ├── ARCHITECTURE.md             # Архітектура проєкту
│   ├── DEBUG_LOOP.md               # Універсальний алгоритм відладки
│   ├── LLM_to_LM_Studio.md         # Налаштування LM Studio
│   ├── MODULES.md                  # Опис модулів
│   ├── PLAN_COMPUTER_USE.md        # План Computer Use агента
│   ├── SECURITY.md                 # Безпека та ризики
│   └── tests.md                    # Тестові сценарії
│
├── tests/                          # Тести (pytest, 60+ файлів)
├── TEST_GUI/                       # GUI діагностичні тести (10 файлів)
├── scenarios/                      # JSON сценарії тестування
├── runtime/                        # Рантайм-дані
├── debug_logs/                     # Логи відладки
├── scaner/                         # Сканер файлів
│
├── status.md                       # Статус розробки + дорожня карта
├── TASKS.md                        # Поточні задачі
├── TASKS_Done.md                   # Виконані задачі
└── TASKS1.md                       # Додаткові задачі
```

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

### AgentLoop (новий orchestration стек)

```
AgentLoop.run(goal):
    while not done:
        1. OBSERVE → ScreenObserver (screenshot + OCR + UIA)
        2. DECIDE  → ActionDecider (LLM tool-calling або JSON Schema)
        3. ACT     → TaskRunner (PermissionGate → handler → Expectation)
        4. CHECK   → PlanCritic meta-оцінка
```

### Core модулі

| Модуль | Призначення | Розташування |
|--------|-------------|---------------|
| `core_planner` | Генерація планів з retry-механізмом | `functions/planning/` |
| `core_executor` | Асинхронне виконання кроків плану | `functions/runtime/` |
| `core_memory` | Пам'ять сесій | `functions/runtime/` |
| `core_cache` | Безпечне кешування idempotent операцій | `functions/` |
| `core_settings` | Управління налаштуваннями | `functions/` |
| `core_tool_runtime` | Реєстр та виконання інструментів + аудит | `functions/runtime/` |
| `core_dispatcher` | Диспетчер команд між GUI / planner / інструментами | `functions/runtime/` |
| `core_streaming` | Стрімінг відповідей LLM до GUI | `functions/` |
| `core_stt_listener` | Прийом голосового вводу | `functions/audio/` |
| `core_safety_sandbox` | Сендбокс для `execute_python` та файлових дій | `functions/runtime/` |
| `core_action_recorder` | Запис GUI-дій + скріншотів | `functions/` |
| `core_undo_manager` | Undo для GUI-дій | `functions/` |
| `core_gui_guardian` | Перевірка ризиків та підтвердження небезпечних GUI-дій | `functions/gui/` |
| `core_windsurf_watcher` | Спостереження за Windsurf IDE | `functions/runtime/` |
| `core_loop_detector` | Захист від зациклення агента | `functions/runtime/` |

### Open Interpreter інтеграція

**`functions/tools/aaa_open_interpreter.py`** — модуль для self-healing виконання коду

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

---

## 🔧 Налаштування

### Конфігураційні файли

- `user_settings.json` — користувацькі налаштування
- `runtime/cache_data.json` — кеш (автоматично)
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
- [docs/MODULES.md](docs/MODULES.md) — опис модулів
- [docs/API.md](docs/API.md) — API для інтеграції
- [docs/DEBUG_LOOP.md](docs/DEBUG_LOOP.md) — універсальний алгоритм відладки
- [docs/LLM_to_LM_Studio.md](docs/LLM_to_LM_Studio.md) — налаштування LM Studio
- [docs/tests.md](docs/tests.md) — тестові сценарії та чеклісти
- [docs/PLAN_COMPUTER_USE.md](docs/PLAN_COMPUTER_USE.md) — план Computer Use агента
- [docs/SECURITY.md](docs/SECURITY.md) — безпека та ризики

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