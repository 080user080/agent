# 🤖 Агент-Помічник (Agent Assistant)

Україномовний AI-агент для автоматизації завдань з роботою з файлами, кодом, системою та інтернетом.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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
python run_assistant.py

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

## ✨ Можливості

### 🧠 Інтелектуальне планування
- **Planner** — розбиває складні задачі на кроки
- **Auto-repair** — до 3 спроб виправлення помилок
- **JSON output** — структуровані плани з retry-механізмом

### 💻 Робота з кодом
- Читання, створення, редагування файлів
- Пошук у коді (`search_in_code`)
- Виконання Python (`execute_python`)
- Git інтеграція (status, diff, commit)

### 🛡️ Безпека
- **Підтвердження дій** — зворотний відлік 30с для небезпечних операцій
- **Кеш тільки idempotent** — не кешуємо створення/видалення файлів
- **Tool policies** — маркування ризиків для кожної функції

### 🎙️ Голосовий ввід
- **STT (Speech-to-Text)** — голосові команди
- **TTS (Text-to-Speech)** — озвучування відповідей
- Індикатор мікрофона в GUI

### 📊 Панель плану
- Прогрес-бар виконання
- Статуси кроків: pending → running → ok/error/blocked/skipped
- Деталі кожного кроку

### ⚙️ Налаштування
- GUI редактор налаштувань (вкладка "Налаштування")
- Пошук по налаштуваннях
- Спойлери для груп
- Збереження в `user_settings.json`

---

## 📁 Структура проєкту

```
agent/
├── run_assistant.py            # Точка входу з GUI (основний запуск)
├── main.py                     # Консольна точка входу (AssistantCore)
├── smart_patch_gui.py          # Допоміжний GUI для редагування коду патчами
├── functions/                  # Основна логіка (~40 модулів)
│   ├── core_*.py                  # Core модулі (~11)
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
│   │   ├── core_action_recorder.py    # Аудит GUI-дій (Phase 2/6)
│   │   ├── core_undo_manager.py       # Undo для GUI-дій (Phase 6)
│   │   └── core_gui_guardian.py       # Захист GUI-дій (Phase 6)
│   ├── logic_*.py                 # Логіка (~10)
│   │   ├── logic_core.py              # FunctionRegistry
│   │   ├── logic_commands.py          # Обробка команд
│   │   ├── logic_llm.py               # LLM взаємодія
│   │   ├── logic_tts.py / logic_stt.py / logic_audio.py / logic_audio_filtering.py
│   │   ├── logic_continuous_listener.py
│   │   ├── logic_context_analyzer.py  # Phase 5
│   │   ├── logic_ui_navigator.py      # Phase 5
│   │   └── logic_scenario_runner.py   # Phase 5
│   ├── tools_*.py                 # GUI-інструменти (~7)
│   │   ├── tools_mouse_keyboard.py    # Phase 1
│   │   ├── tools_window_manager.py    # Phase 1
│   │   ├── tools_screen_capture.py    # Phase 2
│   │   ├── tools_ocr.py               # Phase 3 (pytesseract/easyocr)
│   │   ├── tools_ui_detector.py       # Phase 4
│   │   ├── tools_app_recognizer.py    # Phase 4
│   │   └── tools_visual_diff.py       # Phase 4
│   └── aaa_*.py                   # LLM-tool обгортки (~12)
│       ├── aaa_architect.py / aaa_code_tools.py / aaa_debug_code.py
│       ├── aaa_create_file.py / aaa_edit_file.py / aaa_execute_python.py
│       ├── aaa_open_browser.py / aaa_programs.py / aaa_system.py
│       └── aaa_voice_input.py / aaa_utility_tools.py / aaa_confirmation.py
├── core_gui/                   # GUI компоненти (Tkinter)
│   ├── main_window.py             # Головне вікно
│   ├── chat_panel.py              # Панель чату
│   ├── plan_panel.py              # Панель плану
│   ├── settings_tab.py            # Вкладка налаштувань
│   ├── confirmation.py            # Діалог підтверджень
│   ├── llm_endpoints_editor.py    # Редактор LLM ендпойнтів
│   ├── styles.py / constants.py
├── tests/                      # Тести (pytest)
│   ├── test_core_planner.py
│   ├── test_core_memory.py
│   ├── test_core_executor.py
│   ├── test_tools_mouse_keyboard.py
│   ├── test_tools_window_manager.py
│   └── test_tools_ocr.py
├── requirements.txt            # Рантайм-залежності
├── pytest.ini                  # Конфіг тестів
├── status.md                   # Статус розробки + дорожня карта
├── CONTRIBUTING.md             # Гайд для контриб'юторів
├── tests.md                    # Специфікації тестів
└── README.md                   # Цей файл
```

---

## 🧪 Тести

```bash
# Запуск всіх тестів
python -m pytest tests/ -v

# Запуск конкретного файлу
python -m pytest tests/test_core_planner.py -v

# З покриттям
coverage run -m pytest tests/
coverage report
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
