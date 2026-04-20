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
git clone <repo-url>
cd agent

# Встановлення залежностей
pip install -r requirements.txt

# Запуск
python agent.py
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
├── agent.py                 # Точка входу
├── functions/               # Основна логіка
│   ├── core_*.py           # Core модулі
│   │   ├── core_planner.py      # Планер з retry
│   │   ├── core_executor.py     # Виконавець планів
│   │   ├── core_memory.py       # Пам'ять сесій
│   │   ├── core_cache.py        # Безпечний кеш
│   │   ├── core_tool_runtime.py # Реєстр інструментів
│   │   └── core_settings.py     # Менеджер налаштувань
│   ├── logic_*.py          # Логіка
│   │   ├── logic_commands.py    # Обробка команд
│   │   ├── logic_llm.py         # LLM взаємодія
│   │   └── logic_parser.py      # Парсинг відповідей
│   └── tools_*.py          # Інструменти
├── gui/                     # GUI компоненти
│   ├── main_gui.py         # Головне вікно
│   └── settings/           # Налаштування
├── tests/                   # Тести
│   ├── test_core_planner.py
│   ├── test_core_memory.py
│   └── test_core_executor.py
├── requirements.txt         # Залежності
├── status.md               # Статус розробки
└── README.md               # Цей файл
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
| `core_tool_runtime` | Реєстр та виконання інструментів |

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
