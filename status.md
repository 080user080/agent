# Проєкт: Асистент МАРК
> Останнє оновлення: 19.04.2026

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

- Repair-логіка лише 1 repair + 1 replan (не багатоетапна)
- Planner не робить повне перепланування дерева
- LLM-based summary для довгих сесій не інтегровано в `_manage_conversation_history`
- Тести для core модулів відсутні

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

**Багатоетапний repair** — середній пріоритет
- Зараз лише 1 repair + 1 replan
- Реалізувати цикл repair до 3 спроб
- Покращити евристику: коли repair, коли повний replan

**Індикатор завершення відповіді в GUI** — ✅ Виконано (19.04.2026)
- Зелена галочка `✅` після кожної відповіді асистента
- Статус-рядок оновлюється: "✅ Відповідь готова | час"

**Спойлери в налаштуваннях GUI** — низький пріоритет
- Згортання/розгортання груп налаштувань
- ~20-30 рядків у `settings_tab.py`

**Пошук налаштувань** — низький пріоритет
- Entry-поле зверху вкладки налаштувань
- Фільтрація рядків по ключу/label

**Позиція і розмір вікна GUI** — низький пріоритет
- Зберігати `root.geometry()` в `user_settings.json`
- 5-10 рядків у `main_window.py`

**Голосовий ввід — індикатор мікрофона** — середній пріоритет
- Іконка мікрофона в GUI (біля поля вводу або в статус-барі)
- 🎤 Зелена — голосовий ввід активний (слухає)
- 🎤 Сіра — голосовий ввід вимкнено / призупинено
- Клік по іконці — тогл on/off голосового вводу
- ~30-50 рядків у `chat_panel.py` або новий `voice_indicator.py`

**Виправити статус 'Режим вводу тексту - аудіо призупинено'** — низький пріоритет
- Зараз: "⌨️  Режим вводу тексту - аудіо призупинено" (довге, зайве)
- Має бути: "⌨️  Ввід тексту" або "🎤 Слухання призупинено"
- При blur: відновлення статусу готовності
- 2-3 рядки в `core_gui/chat_panel.py` метод `on_input_focus()`

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

**STT (голосовий ввід)**
- Доробити для повноцінної голосової взаємодії

**Метрики виконання**
- success rate, avg steps, тривалість

---

## 7. Готовність до продакшну

**~75%** — базові функції працюють, розширена безпека додана, GUI модульний.
Залишається: тести, багатоетапний repair, PyQt6 міграція.

---

*Файл оновлено 19.04.2026. Об'єднано з ANALYSIS_TODO.md і PROJECT_STATUS.txt.*
