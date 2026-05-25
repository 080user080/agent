# Поточні задачі МАРК

## Загальні примітки

### ВАЖЛИВО: віртуальне середовище
Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash

# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

### Debug-Loop
**Відладка проводиться за допомогою Debug-Loop.**

Debug-Loop — це універсальний метод відладки, який використовується в цьому проекті для систематичного пошуку та виправлення помилок.

docs/DEBUG_LOOP.md --- тут більш детально описано цей метод.

**Коли використовувати:** Коли ви пишете в чаті слово **"дебаг"**, **"debug"**, або **"Debug-Loop"**, це означає що треба виконати саме цей метод.

### Правила ведення цього файлу
- Тут лише **актуальні задачі**, без довгих історичних фаз і PR-хронології.
- Виконані завдання (блоком, якщо є щось не виконане то залишається весь блок) перенесяться в [TASKS_Done.md]
- `status.md` відповідає на питання **"де ми зараз?"**
- `TASKS.md` відповідає на питання **"що робимо далі?"**
- `docs/ARCHITECTURE.md` відповідає на питання **"чому саме так і в якому технічному порядку?"**

### Пріоритети та статуси
- Пріоритети: `P0` > `P1` > `P2`
- Статуси: `Завершено` > `В процесі` > `Не розпочато`

---
# Self-Coding Agent Pipeline

## Мета
Дати агенту здатність аналізувати власний код, планувати зміни та вносити їх безпечно.

---

## Фаза 1 — Само-читання та аналіз

- [ ] Відмітити виконання в TASK.md
### Крок 1.1 — Self-context builder
Створити `functions/planning/self_code_context.py`
Функція `build_self_context(task: str) -> dict`:
- читає `get_repo_map()`
- знаходить релевантні файли через `search_in_code()`
- читає їх через `read_code_file()`
- повертає контекст для LLM: які файли релевантні, їх поточний стан

- [ ] Відмітити виконання в TASK.md

### Крок 1.2 — Gap analyzer
Функція `analyze_gap(task: str, context: dict) -> dict`:
- через LLM визначає: що треба змінити/додати
- повертає список файлів для зміни + опис змін
- перевіряє чи зміна безпечна (не чіпає критичні модулі)

- [ ] Відмітити виконання в TASK.md

---

## Фаза 2 — Безпечне редагування

- [ ] Відмітити виконання в TASK.md

### Крок 2.1 — Snapshot before edit
У `core_undo_manager.py` вже є `save_snapshot()`.
Переконатись що перед кожною зміною коду робиться snapshot.
Розширити `edit_file()` — автоматичний snapshot якщо файл у папці `functions/`.

- [ ] Відмітити виконання в TASK.md

### Крок 2.2 — Code patch generator
Створити `functions/planning/self_code_patcher.py`
Функція `generate_patch(file_path: str, task: str, context: dict) -> str`:
- читає поточний вміст файлу
- через LLM генерує тільки змінену частину (не весь файл)
- валідує синтаксис через `ast.parse()` перед застосуванням

- [ ] Відмітити виконання в TASK.md

### Крок 2.3 — Syntax validator
Функція `validate_python_syntax(code: str) -> tuple[bool, str]`:
- `ast.parse()` — синтаксична перевірка
- перевірка імпортів на валідність
- повертає `(ok, error_message)`

- [ ] Відмітити виконання в TASK.md

---

## Фаза 3 — Верифікація після змін

- [ ] Відмітити виконання в TASK.md

### Крок 3.1 — Post-edit verification
Функція `verify_edit(file_path: str, task: str) -> dict`:
- повторно читає змінений файл
- через LLM перевіряє чи зміна відповідає задачі
- оновлює `repo_map` через `update_file_in_map()`
- повертає `{ok, summary, warnings}`

- [ ] Відмітити виконання в TASK.md

### Крок 3.2 — Rollback якщо верифікація провалилась
Якщо `verify_edit` повертає `ok=False`:
- автоматично викликати `restore_snapshot()`
- логувати в `self_learning` як невдалу спробу
- повернути детальний звіт чому не вийшло

- [ ] Відмітити виконання в TASK.md

---

## Фаза 4 — Pipeline інтеграція

- [ ] Відмітити виконання в TASK.md

### Крок 4.1 — Self-coding pipeline
Створити `functions/planning/pipeline_self_coding.py`
Клас `SelfCodingPipeline` — реалізує `Pipeline.compile()`:
- отримує `TaskSpec` з `domain=DOMAIN_CODE` де ціль — файл агента
- будує `Plan` з кроків: context → analyze → snapshot → patch → validate → verify

- [ ] Відмітити виконання в TASK.md

### Крок 4.2 — Реєстрація в `make_default_registry()`
В `core_plan_compiler.py` додати `DOMAIN_SELF_CODE` домен
та зареєструвати `SelfCodingPipeline`.

- [ ] Відмітити виконання в TASK.md

---

## Фаза 5 — Захисні обмеження

- [ ] Відмітити виконання в TASK.md

### Крок 5.1 — Список заборонених для авто-редагування файлів
В `core_tool_runtime.py` або новому `self_code_safety.py`:
- `SELF_EDIT_BLACKLIST` — файли які агент НЕ може змінювати сам:
  - `core_safety_sandbox.py`
  - `logic_permission_gate.py`
  - `core_tool_runtime.py`
  - `main.py`
  - `run.py`

- [ ] Відмітити виконання в TASK.md

### Крок 5.2 — Обов'язкове підтвердження користувача
Будь-яка само-модифікація проходить через `confirm_action()`.
Без підтвердження — тільки читання та аналіз, без запису.

- [ ] Відмітити виконання в TASK.md

---

## Критичні ризики (врахувати в коді)

| Ризик | Мітигація |
|-------|-----------|
| Зламаний синтаксис | `ast.parse()` перед записом |
| Нескінченна рекурсія само-редагування | Blacklist критичних файлів |
| Непередбачені побічні ефекти | Snapshot + rollback |
| LLM галюцинує функції | Верифікація після зміни |
| Зміна змінює поведінку Guards | Ізоляція safety модулів |



# Завдання: Виправлення двох багів — list_directory та склеювання слів

## Мета
Виправити баги:
1. `list_directory()` не приймала параметр `path` → падала з `got an unexpected keyword argument 'path'`
2. Команди "подивися мій проект", "подивис, проект", "подивися папку" не розпізнавалися → LLM склеював слова

## Виконані кроки

### 1. list_directory — додано підтримку `path`
- [x] Відкрити `D:\Python\agent\functions\tools\aaa_file_operations.py`
- [x] Змінити сигнатуру: `def list_directory(directory: str = '.', path: str = None) -> dict`
- [x] Логіка: `directory = directory or path or '.'`
- [x] Відмітити виконання в TASK.md

### 2. Розширено _AMBIGUOUS_PROJECT_PATTERNS
- [x] Відкрити `D:\Python\agent\functions\gui\commands_planner.py`
- [x] Додано варіанти з "мій": `подивися мій проект`, `покажи мій проект`, `відкрий мій проект`
- [x] Додано варіанти з комою: `подивис, проект`, `покажи, код` тощо
- [x] Відмітити виконання в TASK.md

### 3. Виправлено _CLEAR_PATTERNS
- [x] Замінено `\s` на `(\s|$)` у всіх патернах з об'єктом
- [x] "подивися папку" тепер матчиться (раніше вимагало пробіл після "папку")
- [x] Відмітити виконання в TASK.md

### 4. Виправлено друкарську помилку
- [x] `\ss+` → `\s+` в одному з патернів

---

# Завдання: Виправлення рекурсивного завантаження модулів

## Мета
Виправити `load_all_modules()` в `functions/runtime/logic_core.py` — функції з підпапок (`functions/tools/`, `functions/skills/`) не завантажуються через не-рекурсивні glob-пошуки.

---

## Кроки

### 1. Відкрити файл для аналізу
- [x] Прочитати `D:\Python\agent\functions\runtime\logic_core.py` повністю
- [x] Відмітити виконання в TASK.md

### 2. Виправити glob для `core_*.py`
- [x] Знайти рядок з `functions_dir.glob("core_*.py")` (~54)
- [x] Замінити на `functions_dir.rglob("core_*.py")`
- [x] Відмітити виконання в TASK.md

### 3. Виправити glob для `aaa_*.py`
- [x] Знайти рядок з `functions_dir.glob("aaa_*.py")` (~82)
- [x] Замінити на `functions_dir.rglob("aaa_*.py")`
- [x] Відмітити виконання в TASK.md

### 4. Виправити glob для `tools_*.py`
- [x] Знайти рядок з `functions_dir.glob("tools_*.py")` (~107)
- [x] Замінити на `functions_dir.rglob("tools_*.py")`
- [x] Відмітити виконання в TASK.md

### 5. Додати блок завантаження `functions/skills/`
- [x] Після блоку `tools_*.py` додано новий блок, який:
  - Шукає `skills_dir = functions_dir / "skills"`
  - Перевіряє що директорія існує
  - Завантажує всі `*.py` крім `__init__.py` через `importlib`
  - Виводить лог аналогічно до інших блоків (`✅ skills/<назва> (N функцій)`)
- [x] Відмітити виконання в TASK.md

### 6. Перевірка дублікатів після rglob
- [x] Додано `_loaded_modules` — множина для відстеження завантажених імен
- [x] Кожен блок (core/aaa/tools) перевіряє `if module_name in _loaded_modules` перед завантаженням
- [x] Відмітити виконання в TASK.md

### 7. Запустити та перевірити
- [x] Запустити `run.py`
- [x] Переконатись у консолі що тепер виводиться завантаження функцій з `functions/tools/` (aaa_*, tools_*) та `functions/skills/`

---

## Очікуваний результат у консолі після виправлення

```
📦 Завантаження core модулів...
✅ core_settings (N функцій)
✅ core_memory (N функцій)
...

📦 Завантаження функцій...
✅ aaa_file_operations (N функцій)
✅ aaa_create_file (N функцій)
...

📦 Завантаження GUI Automation tools...
✅ tools_screen_capture (N функцій)
✅ tools_mouse_keyboard (N функцій)
✅ tools_project_indexer (4 функцій)
...

📦 Завантаження skills...
✅ skills/browser_skills (N функцій)
...
```



### Етап 2: Середній пріоритет — Доробка Accessibility-шару та Windows-інфраструктури

2.1. **Доробити accessibility-шар для Windows**

* Замінити заглушки "Not implemented yet" у файлі `functions/tools_ui_accessibility.py`.


* Повністю реалізувати функції `uia_list_elements`, `uia_find_button`, `uia_click_element`, `uia_set_text`.


* Провести повне smoke-тестування інтерфейсу в середовищі Windows.


* [ ] Відмітити виконання в TASK.md

2.2. **Додати Windows CI / smoke suite**

* Створити та інтегрувати спеціалізований smoke-набір тестів для автоматичної перевірки GUI та взаємодії з ОС Windows.


* [ ] Відмітити виконання в TASK.md

2.3. **Створити router для вибору агента**

* Реалізувати логіку Meta-agent, який аналізує складність задачі та визначає оптимального виконавця (локальний інструмент чи зовнішній AI-провайдер через API).


* [ ] Відмітити виконання в TASK.md

---

### Етап 3: Архітектурний рефакторинг великих модулів (God Objects)

3.1. **Рефакторинг `main.py`**

* Розділити перевантажений файл `main.py` (1242 рядки), який зараз несе забагато відповідальностей (state, app initialization, runtime wiring), на окремі ізольовані модулі.


* [ ] Відмітити виконання в TASK.md

3.2. **Рефакторинг `agent_loop.py`**

* Розрізати файл `agent_loop.py` (2008 рядків) на менші логічні компоненти з чітко визначеною зоною відповідальності.


* [ ] Відмітити виконання в TASK.md

3.3. **Рефакторинг `logic_permission_gate.py` та `logic_core.py`**

* Оптимізувати 4-рівневу policy stack у `logic_permission_gate.py` (~397 рядків) та усунути дублювання з `logic_expectations.py`.


* Зменшити зв'язність у `logic_core.py`: розвантажити `FunctionRegistry` та винести ~200 рядків хардкодженого тексту з методу `get_system_prompt()`.


* [ ] Відмітити виконання в TASK.md

3.4. **Рефакторинг `logic_commands.py` та `global_voice_input.py`**

* Винести надмірну бізнес-логіку з компонента `VoiceAssistant` у файлі `logic_commands.py`.


* Очистити й виділити в окрему логіку механізми вставки тексту в методах `_insert_segment` та `_send_input_unicode` у `global_voice_input.py`.


* [ ] Відмітити виконання в TASK.md

3.5. **Оптимізація планувальника та усунення накладання пайплайнів**

* Виправити перетин обов'язків між модулями `core_planner.py / core_planner_critic.py / core_planner_runner.py` та файлом `logic_task_runner.py`.


* Оптимізувати Phase 13 (компоненти `core_task_intake.py / task_spec.py / pipeline_code.py / core_plan_compiler.py`): зараз 4 файли обслуговують один пайплайн, хоча `ActionDecider` вже має вбудоване online-планування.


* [ ] Відмітити виконання в TASK.md

---

### Етап 4: Ліквідація дублювання коду та файлів

4.1. **Усунення дублювання конфігурацій та середовищ**

* Видалити дублікат `core_settings.py` (файл присутній одночасно у `functions/` та `core/`).


* Проаналізувати та об'єднати ідентичний код у файлах `safety_sandbox.py` та `core_safety_sandbox.py`.


* [ ] Відмітити виконання в TASK.md

4.2. **Усунення дублювання STT та підсистем навчання/звітності**

* Об'єднати або чітко розмежувати однакові STT-компоненти у файлах `logic_stt.py` та `core_stt_listener.py`.


* Позбутися дублювання в логіці самонавчання агента між `logic_task_learner.py` та `self_learning.py`.


* Синхронізувати та об'єднати генератори звітів у `logic_execution_report.py` та `logic_report_generator.py`.


* [ ] Відмітити виконання в TASK.md

---

### ЕТАП Б. Індексація проєкту для кодового агента

**Контекст:** Кодовий агент має бачити структуру проєкту і грамотно вносити точкові зміни, не чіпаючи решту коду.

**Виконані підетапи (перенесено в TASKS_Done.md):** Б1 (Repo Map), Б2 (Dependency Graph), Б3 (Навчання комбінувати інструменти) — ✅

#### Б4. Семантичний пошук (відкласти до реальної потреби)

**Реалізувати ТІЛЬКИ якщо виникне конкретна проблема:** агент не може знайти функцію бо не знає її назви але може описати що вона робить.

- [ ] Реалізувати `functions/vector_memory.py` на базі ChromaDB
  - Кожна функція/клас індексується як окремий чанк
- [ ] Додати інструмент `search_code(query)` — повертає 3-5 релевантних фрагментів за смисловим запитом

**Поки що:** для більшості задач достатньо `search_in_code` (grep) + Repo Map.

---

### COMPUTER USE АГЕНТ — МАРК як людина за комп'ютером

> Базовий план: див. `docs/PLAN_COMPUTER_USE.md` (1138 рядків, аудит коду 26.04.2026)

> Мета: Перетворити МАРК з "набору інструментів з планером" на агента, який користується ПК як людина і може тестувати GUI як QA-інженер.

**Поточний стан (станом на 30.04.2026):**

- ✅ AgentLoop повний (`functions/agent_loop.py`, ~1190 рядків) — observe→plan→act→check + LLM tool-calling
- ✅ ActionDecider з LLM tool-calling (через `logic_llm_tools.ask_llm_with_tools`)
- ✅ Tools schema (`functions/logic_agent_tools_schema.py`) — AGENT/VISION/UIA/BROWSER tools
- ✅ `Observation` посилене: screenshot, OCR, UI elements, UIA tree, vision description, active window
- ✅ `check()` посилене: act_result + ExpectRegistry (17 evaluator-ів) + screen hash fallback
- ✅ AgentLoop інтегрований з GUI (кнопка "🤖 Агент" → run_agent_loop)
- ✅ Базові інструменти (mouse_keyboard, screen_capture, ocr, ui_detector, window_manager, app_recognizer, visual_diff)
- ✅ Phase 11+ стек (TaskRunner, PermissionGate, Expectations, ExecutionReport, SessionBudget, PlanCritic)
- ✅ UIA dual-backend (`tools_ui_accessibility.py`) — uiautomation (основний) + pywinauto fallback, 10+ LLM інструментів (uia_list_elements, uia_click_element, uia_set_text тощо), інтеграція з AgentLoop.observe() для UIA-дерева
- ✅ Vision providers (`providers_vision.py`) — analyze_image для OpenAI/Claude/Gemini, detect_ui_elements/suggest_actions — MVP stubs
- ✅ Browser CDP + Playwright (`tools_browser_cdp.py`, `tools_playwright.py`)
- ✅ Repair loop базовий (`logic_repair_loop.py`)
- ✅ Checkpoint manager (`core_checkpoint.py`)
- ✅ LLM tool-calling низькорівневий (`logic_llm_tools.py`)
- 🟡 **Gap**: GUITester для тестування GUI як QA-інженер — відсутній (ЕТАП 2)
- 🟡 **Gap**: Vision-LM, Browser capabilities в decider — вимкнені за замовчуванням (треба ввімкнути в config). UIA вже інтегровано.

#### ЕТАП 2: GUI ТЕСТУВАЛЬНИК (ВИСОКА ЦІННІСТЬ для self-validation)

**Ціль:** МАРК може тестувати власні зміни в GUI як QA-інженер: відкрити програму, перевірити функції, зробити висновки.

**Робоча основа:**
- [ ] `test_duplication_direct.py` (~134 рядків) — працюючий скрипт для автоматизованого GUI тестування
- Використовує: `activate_window_by_title`, `keyboard_type`, `keyboard_press`
- Запускає GUI через subprocess, вставляє текст, чекає відповіді, читає логи
- Це базовий шаблон для розширення до повноцінного GUITester

- [ ] Створити `functions/logic_gui_tester.py` (~500 рядків) на основі `test_duplication_direct.py`
  - Пріоритет: P1
  - Деталі:
    - `class GUITester` що використовує `AgentLoop` під капотом
    - Метод `test_scenario(scenario: TestScenario) → TestReport`
    - Метод `test_function(app_name, function_name) → TestCaseResult` — швидкий тест однієї функції
    - Метод `test_changes(app_name, changes_description) → TestReport` — тестування ПІСЛЯ змін у коді
    - Інтеграція з `core_action_recorder.ActionRecorder` (скріншоти до/після вже є)
    - Інтеграція з `tools_visual_diff` (порівняння baseline/current)
    - dataclasses: `TestCase`, `TestScenario`, `TestCaseResult`, `TestReport`, `Expectation`
    - Built-in expectations: `TextVisible`, `TextNotVisible`, `WindowTitle`, `ElementExists`, `NoErrorDialog`, `VisualMatch`, `FileExists`

- [ ] Створити `functions/logic_gui_test_report.py` (~200 рядків)
  - Пріоритет: P1
  - Деталі:
    - `class TestReportGenerator` — markdown-звіт з вердиктом
    - Колонки: Тест, Статус (✅/❌), Час, Деталі
    - Розділ "❌ Невдалі тести" з очікуваним vs отриманим, скріншотами
    - Висновок: "Все ок" або "Не пройшло X з Y, рекомендація: доробити"
    - Збереження звіту в `runtime/test_reports/{date}_{scenario}.md`

- [ ] Створити каталог сценаріїв `scenarios/`
  - Пріоритет: P1
  - Деталі:
    - `scenarios/test_notepad_basic.json` — базові функції Notepad
    - `scenarios/test_marka_gui.json` — самотестування PyQt6 GUI МАРКА (відкрити, ввести команду, перевірити відповідь, відсутність дублювання)
    - `scenarios/test_browser_basic.json` — базова веб-автоматизація
    - JSON-формат: `name`, `app_name`, `setup_steps`, `test_cases[]{name, goal, expectations[]}`, `teardown_steps`

- [ ] Інтегрувати GUITester в GUI як вкладка "Тестування"
  - Пріоритет: P2
  - Файли: `core_gui_pyqt6/main_window.py`, новий `core_gui_pyqt6/test_panel_qt.py`
  - Деталі:
    - QListWidget зі списком сценаріїв
    - Кнопки: "Запустити", "Запустити всі", "Переглянути звіт"
    - Прогрес-бар виконання
    - Перегляд скріншотів до/після для кожного тесту

- [ ] Тести для `logic_gui_tester.py` (`tests/test_logic_gui_tester.py`, ~200 рядків)
  - Пріоритет: P1

**Оцінка:** ~700 нових рядків + ~50 змін + ~200 тестів. Складність: середня (використовує AgentLoop).

#### ЕТАП 4: VISION-LLM ІНТЕГРАЦІЯ (РОЗУМІННЯ ЕКРАНУ)

**Ціль:** Агент дивиться на скріншот через GPT-4V/Claude Vision/LLaVA і розуміє що бачить.

- [ ] Перевірити та доробити `providers_vision.py`
  - Пріоритет: P1
  - Деталі:
    - Перевірити що реалізовано: `OpenAIVisionProvider`, `AnthropicVisionProvider`, `OllamaVisionProvider`
    - Додати методи: `describe(image_path, prompt) → str`, `plan_action(image_path, goal) → Dict`, `find_element(image_path, description) → Dict[bbox]`
    - `get_vision_provider(assistant)` factory — з конфігу `VISION_PROVIDER` в SETTINGS_SCHEMA
    - Кешування: не аналізувати той самий скріншот повторно (хеш скрину → опис)

- [ ] Інтегрувати у `ActionDecider.decide()` (~50 рядків)
  - Пріоритет: P1
  - Деталі:
    - Якщо `enable_vision=True` і провайдер доступний — додавати vision_description в промпт