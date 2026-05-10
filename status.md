# Проєкт: Асистент МАРК
> Останнє оновлення: 10.05.2026

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash
# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

---

## 1. Мета проєкту

**МАРК** — локальний Windows-агент на Python, який:

- приймає задачу текстом або голосом;
- будує план і виконує його через інструменти;
- може працювати з файлами, кодом, браузером і GUI Windows;
- вміє делегувати частину задач іншим AI-провайдерам;
- прагне до довгих автономних сесій з контролем ризиків.

Коротко: ціль проєкту не "чат-асистент", а **goal-driven executor для Windows**.

---

## 2. Поточний стан

### Загальна оцінка

- **Ядро агента:** сильне MVP, придатне для локальної роботи й експериментів.
- **GUI automation:** хороша база, але ще не production-рівень.
- **Autonomous orchestration:** інфраструктура вже є, але не вся зшита в надійний E2E.
- **Універсальні домени:** частково закладені, але ще не доведені до "ТЗ -> готовий результат".

### Що вже реально є в коді

- GUI на PyQt6 у `core_gui_pyqt6/`, запуск через [run.py](D:/Python/agent/run.py) --qt.
- GUI на Tkinter застаріло і переміщено в [backup/tkinter_legacy/](D:/Python/agent/backup/tkinter_legacy/) (05.05.2026).
- Основний runtime у [main.py](D:/Python/agent/main.py).
- Planner / executor / memory / cache / safety / audit.
- `TaskRunner`, `PermissionGate`, `ExecutionReport`, `SessionBudget`, `Watcher`.
- LLM tool-calling та новий LLM-шар у `functions/llm/`.
  - `router.py` — RequestRouter для класифікації запитів
  - `provider_chain.py` — ProviderChain з fallback ланцюгом
- GUI automation: mouse/keyboard, windows, screenshot, OCR, UI detection, visual diff.
- Browser automation: Playwright CDP.
- AI actors / provider registry / repair loop / checkpoint infrastructure.
- Global voice input (Windows hook) — глобальне голосове введення.
- Self-learning — модуль самонавчання з аналізом помилок і skills базою.
- Plan executor — GUI-інтеграція для виконання планів.
- 64 тестових файли у [tests](D:/Python/agent/tests) + 10 діагностичних у [TEST_GUI](D:/Python/agent/TEST_GUI).
- CI та lint конфіг уже існують: [pyproject.toml](D:/Python/agent/pyproject.toml), [ci.yml](D:/Python/agent/.github/workflows/ci.yml).

### Що оновлено відносно старих версій статусу

- `requirements.txt` уже не "тільки audio": там є GUI/OCR/browser залежності.
- CI вже є; твердження "CI відсутній" більше неактуальне.
- Частина LLM-логіки вже винесена з умовного `logic_llm.py` у пакет [functions/llm](D:/Python/agent/functions/llm).
- GUI-інтеграція `TaskRunner` уже є як MVP.

---

## 3. Чесна оцінка готовності

### Сильні сторони

- Великий функціональний обсяг уже реалізований.
- Є реальна архітектурна база для автономного виконання, а не лише чат-відповідей.
- Є тестова база і CI, тобто проєкт вже не "без захисту".
- Є кілька важливих safety-механізмів: permission gate, audit, sandbox, undo/guardian.

### Що ще не дає вважати проєкт досягнутим

1. **Немає повністю стабільного trunk.**
   На 28.04.2026 весь `pytest` не проходить навіть collection:
   [tests/test_phase7_9.py](D:/Python/agent/tests/test_phase7_9.py) імпортує `parse_markdown_plan` з
   [functions/logic_task_runner.py](D:/Python/agent/functions/logic_task_runner.py), але цього API зараз немає.

2. **UIA-шар не завершено.**
   У [functions/tools_ui_accessibility.py](D:/Python/agent/functions/tools_ui_accessibility.py)
   частина LLM-facing функцій ще повертає заглушки `Not implemented yet`.

3. **Vision-LM MVP, але неповний.**
   У [functions/providers_vision.py](D:/Python/agent/functions/providers_vision.py) `analyze_image()` готовий для OpenAI/Claude/Gemini,
   але `detect_ui_elements()` і `suggest_actions()` — stubs (завжди повертають `[]`).
   LLM tools `vision_analyze_screenshot`, `vision_detect_ui`, `vision_suggest_actions` — не підключені (Not implemented yet).
   Потрібен: парсинг відповіді LLM + ініціалізація tools з `assistant` instance.

4. **Phase 13 ще не доведений до реального "ТЗ -> готовий артефакт".**
   У [functions/pipeline_code.py](d:\Python\agent/functions/pipeline_code.py) кодогенерація все ще
   створює scaffold/placeholder, а не повноцінний результат.
   - `_scaffold_content()` генерує порожні заглушки (docstring + TODO + `raise NotImplementedError`)
   - S9 (cross-AI actors) не підключено — немає інтеграції з `ai_actors.py` для реальної кодогенерації
   - `ai_actors.py` має інтерфейс для Codex/Windsurf/Cursor/ChatGPT/Claude/Gemini, але `_execute_windsurf()` і `_execute_cursor()` — заглушки
   - Деталі: див. TASKS.md ЕТАП 10

5. **ЕТАП 12 (Оркестрація ШІ) — частково реалізовано.**
   - ✅ `functions/llm/router.py` (122 рядків) — RequestRouter з keyword-based класифікацією
   - ✅ `functions/llm/provider_chain.py` (128 рядків) — ProviderChain з fallback ланцюгом
   - ✅ `tests/test_router.py` (12 тестів pass)
   - ❌ НЕ інтегровано в logic_commands.py і AgentLoop
   - ❌ НЕ налаштовано LLM_ENDPOINTS для GPT-OSS 20B, Gemini, DeepSeek
   - Деталі: див. TASKS.md ЕТАП 12

6. **AgentLoop JSON parsing issue (05.05.2026).**
   - LLM (qwen3-coder-30b-a3b-instruct) не генерує коректний JSON для tool-calling
   - ActionDecider отримує сміття замість JSON, що призводить до зациклення
   - Збільшено `max_steps` з 50 до 100 в `AgentLoopConfig` як тимчасове рішення
   - Потрібно: використати сильніший LLM або покращити парсинг JSON з fallback

7. **Windows-first проєкт покритий CI переважно на Linux.**
   Поточний [ci.yml](D:/Python/agent/.github/workflows/ci.yml) корисний для логіки, але не закриває
   реальні ризики `pywin32`, DPI, UIA, віконного менеджменту та GUI automation.

8. **Структура коду вже надто плоска й важка для підтримки.**
   У `functions/` 100+ файлів; найбільші модулі стали "центрами тяжіння":
   [main.py](D:/Python/agent/main.py),
   [logic_commands.py](D:/Python/agent/functions/logic_commands.py),
   [core_planner.py](D:/Python/agent/functions/core_planner.py),
   [logic_task_runner.py](D:/Python/agent/functions/logic_task_runner.py),
   [core_tool_runtime.py](D:/Python/agent/functions/core_tool_runtime.py).

9. **Контекст переповнюється при довгих діалогах.**
   Немає механізму стиснення історії — агент починає плутатися або ігнорувати старі інструкції.

10. **Skills DB лінійна.**
    self_learning зберігає навички як звичайний словник. Пошук за ключем, а не за змістом.
    Це не масштабується: після 30-40 навичок знайти потрібну стає неможливо.

11. **Критик = Виконавець.**
    AgentLoop використовує одну модель для планування та перевірки, що знижує якість самоаналізу.

---

## 4. Ключові вузькі місця

### P0. Стабільність і узгодженість контрактів

- Є розрив між тестами, статусом і фактичним API модулів.
- Документація вже кілька разів відставала від коду.
- Частина історичних описів посилається на старі імена модулів.

**Висновок:** головний ризик зараз не брак ідей, а drift між шарами системи.

### P1. Windows automation без достатнього hardening

- UIA частково недописаний.
- Немає Windows smoke CI.
- Реальна надійність на multi-monitor / DPI / accessibility ще не закрита системно.

### P1. E2E-сценарії ще слабші за обсяг інфраструктури

- Фундамент є, але мало доведених сценаріїв "від задачі до перевіреного результату".
- Найбільший розрив видно у universal task execution і code/photo/presentation pipelines.

### P2. Архітектурна маса

- `functions/` перевантажений.
- Є змішані стилі назв: `core_*`, `logic_*`, `tools_*`, `providers_*`, `aaa_*`.
- Є сліди legacy-підходів поруч із новим стеком.

---

## 5. Пріоритети на найближчі спринти

### Найвищий пріоритет (оновлено на основі external AI-архітектури)

1. **Полагодити trunk stability**
   - повернути сумісність між тестами й `logic_task_runner`;
   - добитися, щоб `pytest` хоча б повністю проходив collection;
   - зафіксувати публічні API для parser/runner/plan-об'єктів.

2. **Виправити AgentLoop JSON parsing**
   - LLM (qwen3) не генерує коректний JSON для tool-calling → зациклення
   - Рішення: сильніший LLM або покращений парсинг з fallback

3. **Створити Skills (абстракції над базовими діями)**
   - Замість "клікни сюди" - "open_browser(), search_google(), fill_form()"
   - Менше помилок, швидше, стабільніше
   - База накопичуваних навичок

### Середній пріоритет

4. **Доробити accessibility-шар**
   - завершити `uia_list_elements`, `uia_find_button`, `uia_click_element`, `uia_set_text`;
   - покрити це smoke-тестами на Windows.

5. **Додати Windows CI / smoke suite**
   - окремий workflow або nightly job;
   - мінімум для `tools_window_manager`, `tools_screen_capture`, `tools_mouse_keyboard`, `tools_ui_accessibility`.

6. **Створити router для вибору агента**
   - Meta-agent вирішує хто виконує (local vs API);
   - Коли передати іншому провайдеру;
   - Вирішує на основі типу задачі (gui/code/web/desktop).

7. **Рефакторинг великих модулів**
   - main.py (52KB) → розділити на модулі
   - agent_loop.py (62KB) → розділити observe/plan/act/check
   - logic_commands.py (45KB) → розділити по типах команд

### Завершені пріоритети

- ✅ **Інтеграція AgentLoop з GUI** — кнопка 🤖, run_agent_loop
- ✅ **Tool-calling для LLM** — logic_agent_tools_schema, tool-calling інтеграція
- ✅ **Міграція GUI на PyQt6** — core_gui_pyqt6/ основний бекенд, Tkinter в backup/
- ✅ **Глобальне голосове введення** — global_voice_input.py, Ctrl+Shift+V hook
- ✅ **Самонавчання** — self_learning.py, JSONL логи, skills база
- ✅ **Синхронізація документації** — README/status/TASKS оновлено (10.05.2026)

---

## 6. Що вважаю реально завершеним

### Можна вважати завершеним як фундамент

- базові planner / executor / memory / cache механізми;
- audit / permission / sandbox foundation;
- базові GUI tools;
- browser CDP MVP;
- repair loop foundation;
- checkpoint / watcher foundation;
- базову GUI-інтеграцію нового планового стеку.

### Не можна вважати завершеним попри наявність коду

- UI accessibility як production-ready шар;
- Phase 13 як universal executor;
- Windows automation hardening;
- cross-AI orchestration як надійну повсякденну функцію;
- документацію як повністю синхронізовану з кодом.

---

## 7. Документи проєкту

- [README.md](README.md) — запуск і загальний огляд.
- [TASKS.md](TASKS.md) — поточні задачі та їх статус.
- [docs/tests.md](docs/tests.md) — тестові сценарії та чеклісти.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архітектурний стан, борг і план рефакторингу.

`status.md` відтепер є **коротким джерелом правди про поточний стан**.
Детальні історичні фази, розлогі brainstorm-нотатки та довгі списки технічного боргу
сюди більше не дублюються.

---

## 8. Підсумок

Проєкт уже має сильний фундамент і незвично широкий обсяг реалізованого функціоналу.
Головний наступний крок — не "ще більше фіч", а **стабілізація, завершення accessibility,
Windows hardening і доведення 1-2 наскрізних сценаріїв до надійного стану**.
