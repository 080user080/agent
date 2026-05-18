Оновлений план очищення з детальними критеріями приймання для кожного переміщеного файлу. Усі завдання мають формат `- [ ]`, придатний для відстеження агентом.

---

# Очищення кореня `functions/` — покрокові завдання

## Мета
Видалити з кореня `functions/` всі файли, що вже перенесені, перемістити решту модулів у підпапки, об’єднати дублікати та оновити імпорти. У корені залишаться лише `__init__.py`, `config.py`, `global_voice_input.py`.

---

## Етап 0: Підготовка
- [ ] 0.1 Переконатися, що ви в корені проєкту.
- [ ] 0.2 Запустити `pytest tests/` – зафіксувати, що всі тести проходять.
- [ ] 0.3 Створити резервну гілку: `git checkout -b backup/cleanup-$(date +%Y%m%d)`

---

## Етап 1: Видалення заглушок та застарілих копій
### 1.1 Видалення `aaa_*.py`
- [ ] 1.1.1 Видалити всі файли `aaa_*.py` з кореня `functions/`
  - `ls functions/aaa_*.py` не повинно нічого повертати.
  - `grep -r "from functions.aaa_" .` (з кореня проєкту) має повернути 0 рядків.
  - Якщо знайдено старі імпорти – спочатку виправити на `from functions.tools.aaa_...`.
- **Критерії приймання після видалення:**
  - [ ] `pytest tests/` – усі тести проходять.
  - [ ] `python run.py --qt` запускається без помилок імпорту (чекати 30 с, закрити, якщо GUI не падає).
  - [ ] Голосовий ввід (якщо реалізовано) та виконання базового коду працюють.
  - [ ] Жоден імпорт у проєкті не вказує на `functions.aaa_...`.

### 1.2 Видалення `tools_*.py`
- [ ] 1.2.1 Видалити всі файли `tools_*.py` з кореня
  - Перевірка `ls functions/tools_*.py` – порожньо.
  - `grep -r "from functions.tools_" .` – 0 входжень.
- **Критерії приймання після видалення:**
  - [ ] `pytest tests/` – усі тести проходять.
  - [ ] `python run.py --qt` – успішний старт.
  - [ ] Голосовий ввід та код працюють.
  - [ ] Немає імпортів до `functions.tools_...`.

### 1.3 Видалення інших файлів-заглушок
Видалити такі файли з кореня:
```
core_action_recorder.py
core_cache.py
core_gui_guardian.py
core_memory.py
core_plan_compiler.py
core_planner.py
core_planner_critic.py
core_planner_runner.py
core_session_budget.py
core_settings.py
core_tool_runtime.py
core_undo_manager.py
logic_expectations.py
logic_task_runner.py
task_spec.py
voice_tray_icon.py
```
- [ ] 1.3.1 Для кожного файлу: видалити, перевірити імпорти через `grep -r "from functions.<назва_модуля>" .`
- **Загальні критерії після видалення всіх 16 файлів:**
  - [ ] `pytest tests/` – всі тести зелені.
  - [ ] `python run.py --qt` – успішний запуск.
  - [ ] Голосовий ввід та код функціонують.
  - [ ] Жоден зі старих шляхів не використовується.

---

## Етап 2: Створення нових підпапок
- [ ] 2.1 Створити `functions/audio/__init__.py` (порожній файл).
- [ ] 2.2 Переконатися, що `llm/`, `planning/`, `runtime/`, `gui/` існують (якщо ні – створити).

---

## Етап 3: Переміщення файлів у підпапки
Кожне переміщення включає оновлення імпортів.  
**Методика:**
1. Перемістити файл.
2. Знайти всі `from functions.<старе_ім'я>` / `import functions.<старе_ім'я>` – замінити на новий шлях.
3. Запустити критерії приймання (вони наведені після кожного переміщення).

### Група 3.1 – Планування (`planning/`)
- [ ] 3.1.1 Перемістити `agent_loop.py` → `planning/agent_loop.py`
  - [ ] Оновити імпорти.
  - [ ] `pytest tests/` – успішно.
  - [ ] `python run.py --qt` – старт без помилок.
  - [ ] Голосовий ввід / код працюють.
  - [ ] Немає імпортів `from functions.agent_loop`.
- [ ] 3.1.2 Перемістити `ai_actors.py` → `planning/ai_actors.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії аналогічні)
- [ ] 3.1.3 Перемістити `core_task_intake.py` → `planning/core_task_intake.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.1.4 Перемістити `logic_agent_tools_schema.py` → `planning/logic_agent_tools_schema.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.1.5 Перемістити `logic_context_analyzer.py` → `planning/logic_context_analyzer.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.1.6 Перемістити `logic_orchestrator.py` → `planning/logic_orchestrator.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.1.7 Перемістити `logic_plan_critic.py` → `planning/logic_plan_critic.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.1.8 Перемістити `logic_repair_loop.py` → `planning/logic_repair_loop.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.1.9 Перемістити `pipeline_code.py` → `planning/pipeline_code.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.1.10 Перемістити `plan_executor.py` → `planning/plan_executor.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.1.11 Перемістити `logic_task_learner.py` → `planning/logic_task_learner.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)

### Група 3.2 – Рантайм (`runtime/`)
- [ ] 3.2.1 Перемістити `conditions_web.py` → `runtime/conditions_web.py`
  - [ ] Оновити імпорти.
  - [ ] `pytest tests/` – успішно.
  - [ ] `python run.py --qt` – без помилок.
  - [ ] Голосовий ввід та код працюють.
  - [ ] Немає імпортів `from functions.conditions_web`.
- [ ] 3.2.2 Перемістити `conditions_windows.py` → `runtime/conditions_windows.py`
  - [ ] Оновити імпорти.
  - [ ] (критерії)
- [ ] 3.2.3 Перемістити `core_app_profile.py` → `runtime/core_app_profile.py`
  - [ ] (критерії)
- [ ] 3.2.4 Перемістити `core_checkpoint.py` → `runtime/core_checkpoint.py`
  - [ ] (критерії)
- [ ] 3.2.5 Перемістити `core_dispatcher.py` → `runtime/core_dispatcher.py`
  - [ ] (критерії)
- [ ] 3.2.6 Перемістити `core_executor.py` → `runtime/core_executor.py`
  - [ ] (критерії)
- [ ] 3.2.7 Перемістити `core_loop_detector.py` → `runtime/core_loop_detector.py`
  - [ ] (критерії)
- [ ] 3.2.8 Перемістити `core_macro.py` → `runtime/core_macro.py`
  - [ ] (критерії)
- [ ] 3.2.9 Перемістити `core_windsurf_watcher.py` → `runtime/core_windsurf_watcher.py`
  - [ ] (критерії)
- [ ] 3.2.10 Перемістити `logic_core.py` → `runtime/logic_core.py`
  - [ ] (критерії)
- [ ] 3.2.11 Перемістити `logic_permission_gate.py` → `runtime/logic_permission_gate.py`
  - [ ] (критерії)
- [ ] 3.2.12 Перемістити `logic_watcher.py` → `runtime/logic_watcher.py`
  - [ ] (критерії)
- [ ] 3.2.13 Перемістити `self_learning.py` → `runtime/self_learning.py`
  - [ ] (критерії)
- [ ] 3.2.14 Перемістити `windsurf_watcher_executor.py` → `runtime/windsurf_watcher_executor.py`
  - [ ] (критерії)
- [ ] 3.2.15 Перемістити `core_safety_sandbox.py` → `runtime/core_safety_sandbox.py` (тимчасово, об’єднання – в Етапі 4)
  - [ ] Оновити імпорти.
  - [ ] (критерії)

### Група 3.3 – GUI (`gui/`)
- [ ] 3.3.1 Перемістити `logic_commands.py` → `gui/logic_commands.py`
  - [ ] Оновити імпорти.
  - [ ] `pytest tests/` – успішно.
  - [ ] `python run.py --qt` – без помилок.
  - [ ] Голосовий ввід та код працюють.
  - [ ] Немає імпортів `from functions.logic_commands`.
- [ ] 3.3.2 Перемістити `logic_scenario_runner.py` → `gui/logic_scenario_runner.py`
  - [ ] (критерії)
- [ ] 3.3.3 Перемістити `logic_ui_navigator.py` → `gui/logic_ui_navigator.py`
  - [ ] (критерії)

### Група 3.4 – Аудіо (`audio/`)
- [ ] 3.4.1 Перемістити `core_stt_listener.py` → `audio/core_stt_listener.py`
  - [ ] Оновити імпорти.
  - [ ] `pytest tests/` – успішно.
  - [ ] `python run.py --qt` – без помилок.
  - [ ] Голосовий ввід та код працюють.
  - [ ] Немає імпортів `from functions.core_stt_listener`.
- [ ] 3.4.2 Перемістити `logic_audio.py` → `audio/logic_audio.py`
  - [ ] (критерії)
- [ ] 3.4.3 Перемістити `logic_audio_filtering.py` → `audio/logic_audio_filtering.py`
  - [ ] (критерії)
- [ ] 3.4.4 Перемістити `logic_continuous_listener.py` → `audio/logic_continuous_listener.py`
  - [ ] (критерії)
- [ ] 3.4.5 Перемістити `logic_stt.py` → `audio/logic_stt.py`
  - [ ] (критерії)
- [ ] 3.4.6 Перемістити `logic_tts.py` → `audio/logic_tts.py`
  - [ ] (критерії)

### Група 3.5 – LLM/провайдери (`llm/`)
- [ ] 3.5.1 Перемістити `logic_ai_adapter.py` → `llm/logic_ai_adapter.py`
  - [ ] Оновити імпорти.
  - [ ] `pytest tests/` – успішно.
  - [ ] `python run.py --qt` – без помилок.
  - [ ] Голосовий ввід та код працюють.
  - [ ] Немає імпортів `from functions.logic_ai_adapter`.
- [ ] 3.5.2 Перемістити `logic_llm_tools.py` → `llm/logic_llm_tools.py`
  - [ ] (критерії)
- [ ] 3.5.3 Перемістити `logic_provider_registry.py` → `llm/logic_provider_registry.py`
  - [ ] (критерії)
- [ ] 3.5.4 Перемістити `providers_anthropic.py` → `llm/providers_anthropic.py`
  - [ ] (критерії)
- [ ] 3.5.5 Перемістити `providers_browser.py` → `llm/providers_browser.py`
  - [ ] (критерії)
- [ ] 3.5.6 Перемістити `providers_google.py` → `llm/providers_google.py`
  - [ ] (критерії)
- [ ] 3.5.7 Перемістити `providers_openai_compatible.py` → `llm/providers_openai_compatible.py`
  - [ ] (критерії)
- [ ] 3.5.8 Перемістити `providers_vision.py` → `llm/providers_vision.py`
  - [ ] (критерії)

---

## Етап 4: Об’єднання дублікатів
### 4.1 `safety_sandbox.py` та `core_safety_sandbox.py`
- [ ] 4.1.1 Проаналізувати `functions/safety_sandbox.py`. Якщо він є лише реекспортом або застарілою обгорткою – просто видалити його.
  - [ ] Оновити всі імпорти, що використовували `safety_sandbox`, на `runtime.core_safety_sandbox`.
  - [ ] `grep -r "from functions.safety_sandbox" .` має бути порожньо.
- [ ] 4.1.2 Якщо в `safety_sandbox.py` є унікальний код, якого немає в `runtime/core_safety_sandbox.py` – перенести його туди.
- [ ] 4.1.3 Видалити `functions/safety_sandbox.py`.
- [ ] 4.1.4 **Критерії:**
  - [ ] `pytest tests/` – успішно.
  - [ ] `python run.py --qt` – старт без помилок.
  - [ ] Голосовий ввід та код працюють.
  - [ ] Відсутні імпорти старого шляху.

### 4.2 `logic_execution_report.py` та `logic_report_generator.py`
- [ ] 4.2.1 Перемістити обидва файли в `planning/` (якщо ще не там).
- [ ] 4.2.2 Об’єднати код у `planning/logic_execution_report.py` (залишити лише один файл).
- [ ] 4.2.3 Оновити всі імпорти, що використовували `logic_report_generator`, на `planning.logic_execution_report`.
- [ ] 4.2.4 Видалити `logic_report_generator.py`.
- [ ] 4.2.5 **Критерії:**
  - [ ] `pytest tests/` – успішно.
  - [ ] `python run.py --qt` – без помилок.
  - [ ] Голосовий ввід та код працюють.
  - [ ] Немає імпортів старого модуля.

### 4.3 `context_manager.py` та `planning/context_controller.py`
- [ ] 4.3.1 Перемістити `context_manager.py` в `planning/`.
- [ ] 4.3.2 Перенести весь унікальний вміст з `context_manager.py` у `context_controller.py`.
- [ ] 4.3.3 Оновити всі імпорти, що посилалися на `context_manager`, на `planning.context_controller`.
- [ ] 4.3.4 Видалити `planning/context_manager.py` (або файл із кореня, якщо не переміщували).
- [ ] 4.3.5 **Критерії:**
  - [ ] `pytest tests/` – успішно.
  - [ ] `python run.py --qt` – без помилок.
  - [ ] Голосовий ввід та код працюють.
  - [ ] Немає імпортів `context_manager`.

---

## Етап 5: Фінальна зачистка кореня
- [ ] 5.1 Переконатися, що в корені `functions/` залишилися лише:
  ```
  __init__.py
  config.py
  global_voice_input.py
  ```
- [ ] 5.2 Глобальний пошук застарілих імпортів:
  ```bash
  grep -r "from functions\.\(aaa_\|tools_\|core_action\|core_cache\|core_memory\|core_gui\|core_plan\|core_session\|core_settings\|core_tool_runtime\|core_undo\|logic_expectations\|logic_task_runner\|task_spec\|voice_tray_icon\|safety_sandbox\|core_safety_sandbox\|context_manager\|logic_report_generator\)" .
  ```
  Має бути 0 результатів (або лише коментарі).
- [ ] 5.3 Запустити повний набір тестів: `pytest tests/` – усі повинні пройти.
- [ ] 5.4 Запустити `python run.py --qt`, зачекати 30 секунд, переконатися у відсутності помилок імпорту та падінь.
- [ ] 5.5 Перевірити голосовий ввід (якщо підтримується) і виконання простого коду.

---

## Етап 6: Оновлення документації
- [ ] 6.1 У файлах `README.md`, `docs/ARCHITECTURE.md`, `docs/MODULES.md` знайти та замінити старі шляхи на нові (наприклад, `functions.agent_loop` → `functions.planning.agent_loop`).
- [ ] 6.2 Додати опис нових папок `audio/`, `llm/`, якщо в документації описана структура проєкту.

---

**Кінцевий стан:** корінь `functions/` містить лише 3 файли, тести проходять, GUI запускається, імпорти актуальні.