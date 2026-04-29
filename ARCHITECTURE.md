# Архітектура МАРК: поточний стан і напрямок
> Оновлено: 28.04.2026

---

## Документи проєкту

- [README.md](D:/Python/agent/README.md) — запуск і загальний огляд.
- [TASKS.md](D:/Python/agent/TASKS.md) — поточні задачі та їх статус.
- [status.md](D:/Python/agent/status.md) — короткий джерело правди про поточний стан.
- [tests.md](D:/Python/agent/tests.md) — тестові сценарії та чеклісти.

---

## 1. Навіщо цей документ

Це не roadmap усіх фаз і не changelog.
Це коротка технічна карта:

- як зараз реально влаштований проєкт;
- де архітектурний борг;
- у якому порядку варто його зменшувати.

---

## 2. Поточна структура

### Точки входу

- [run_assistant.py](D:/Python/agent/run_assistant.py) — GUI entrypoint.
- [main.py](D:/Python/agent/main.py) — основний runtime / AssistantCore.
- [smart_patch_gui.py](D:/Python/agent/smart_patch_gui.py) — окремий допоміжний GUI.

### Основні підсистеми

- `core_gui/` — Tkinter GUI.
- `functions/core_*` — planner, executor, memory, cache, settings, safety, checkpoint.
- `functions/logic_*` — orchestration, task running, scenarios, expectations, repair, watchers.
- `functions/tools_*` — desktop/browser/media tools.
- `functions/providers_*` + `functions/llm/` — LLM/provider layer.
- `functions/aaa_*` — legacy / wrapper-oriented tool layer.
- `tests/` — unit і integration-style тести.

### Спостереження

- Проєкт уже не малий: у `functions/` 96 файлів.
- З'явився новий LLM-пакет `functions/llm/`, але стара термінологія ще лишилася в документації й частині модулів.
- Новий orchestration-стек існує поруч із legacy-шарами.

---

## 3. Головні архітектурні проблеми

### 3.1. Плоска структура і перевантажені модулі

Найважчі файли зараз:

- [main.py](D:/Python/agent/main.py)
- [core_gui/main_window.py](D:/Python/agent/core_gui/main_window.py)
- [functions/logic_commands.py](D:/Python/agent/functions/logic_commands.py)
- [functions/core_planner.py](D:/Python/agent/functions/core_planner.py)
- [functions/logic_task_runner.py](D:/Python/agent/functions/logic_task_runner.py)
- [functions/core_tool_runtime.py](D:/Python/agent/functions/core_tool_runtime.py)

Проблема не лише в розмірі. Ці модулі одночасно:

- тримають state;
- знають про GUI;
- знають про tool runtime;
- знають про LLM / planning / execution transitions.

Це підвищує вартість будь-якої зміни.

### 3.2. Нестабільні контракти

Симптоми:

- тести імпортують API, яких уже немає;
- документація посилається на старі модулі;
- новий і legacy стек частково дублюють поняття.

Найперше тут треба стабілізувати:

- `Plan` / `Task` / parser / compiler контракти;
- публічні точки входу `TaskRunner`;
- публічний LLM helper layer.

### 3.3. Змішані шари відповідальності

Приклади:

- planner і execution concerns змішані в суміжних модулях;
- GUI-логіка та orchestration-рішення місцями близько пов'язані;
- browser/provider/tool abstraction не всюди розділені.

### 3.4. Legacy шар не ізольований

`aaa_*` ще корисний для сумісності, але він має бути чітко позначений як legacy-обгортки, а не рівноправний сучасний API.

### 3.5. Runtime-артефакти частково розкидані

Stateful дані мають жити або в `runtime/`, або в `logs/`.
Кодова директорія не повинна бути місцем для робочих JSON-станів.

---

## 4. Найважливіші технічні борги

### P0

- Полагодити `pytest` collection і вирівняти API `logic_task_runner`.
- Оновити документацію під реальний LLM-шар (`functions/llm/`).
- Позбутися суперечностей між статусом, README і кодом.

### P1

- Завершити `tools_ui_accessibility.py`.
- Додати Windows smoke CI.
- Зафіксувати один стабільний E2E vertical slice.

### P2

- Прибрати циклічні або напівциклічні залежності між GUI/screen/input шарами.
- Вирівняти структуру runtime state.
- Зменшити зв'язність між planner / runner / GUI.

---

## 5. Рекомендований порядок рефакторингу

### Крок 1. Стабілізувати контракти, не рухаючи папки

Спершу не треба робити великий rename/move.
Краще:

- ввести явні export points;
- повернути сумісність для тестів;
- зафіксувати один спосіб парсингу плану;
- визначити, що є public API, а що internal.

### Крок 2. Винести спільні абстракції

Має сенс додати невеликий спільний шар для:

- `Point`, `Rect`, `Region`;
- tool action/result structures;
- спільних error/result helpers.

Це дасть менше прямого імпорту між tool-модулями.

### Крок 3. Розрізати великі модулі по відповідальностях

Насамперед:

- `logic_commands.py`
- `core_planner.py`
- `main.py`

Не обов'язково все одразу. Головне — витягнути окремо:

- command handlers;
- planner prompt building / validation;
- app initialization / dependency wiring.

### Крок 4. Поступово групувати модулі по підсистемах

Після стабілізації API можна рухатися до структури на кшталт:

- `functions/llm/`
- `functions/tools/`
- `functions/planning/`
- `functions/gui_logic/`
- `functions/runtime/`
- `functions/legacy/`

Але це має бути наслідок попередніх кроків, а не стартова операція.

---

## 6. Чого не варто робити зараз

- Не робити "великий вибух" з масовим перенесенням файлів.
- Не додавати нові доменні пайплайни, поки code vertical slice не стабілізований.
- Не множити нові abstraction layers без конкретного виграшу в testability або підтримці.

---

## 7. Definition of better

Архітектура стане помітно кращою, коли:

- `pytest` стабільно проходить collection і базовий набір тестів;
- є Windows smoke CI;
- `status.md`, `README.md` і код не суперечать одне одному;
- UIA шар не містить critical TODO в основних user-facing entrypoints;
- є один стабільний E2E сценарій `task -> plan -> execute -> validate -> report`;
- legacy шар чітко відділений від нового orchestration-стеку.
