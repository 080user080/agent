# Архітектура МАРК: поточний стан і напрямок
> Оновлено: 10.05.2026

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash
# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

---

## Документи проєкту

- [README.md](../README.md) — запуск і загальний огляд.
- [TASKS.md](../TASKS.md) — поточні задачі та їх статус.
- [status.md](../status.md) — короткий джерело правди про поточний стан.
- [tests.md](tests.md) — тестові сценарії та чеклісти.

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

- [run.py](../run.py) — універсальний entrypoint (PyQt6).
- [run_assistant_qt.py](../run_assistant_qt.py) — GUI entrypoint (PyQt6).
- [main.py](../main.py) — основний runtime / AssistantCore.

### Основні підсистеми

- `core_gui_pyqt6/` — PyQt6 GUI (основний і єдиний GUI бекенд).
- `backup/tkinter_legacy/` — Tkinter GUI (застаріло, переміщено в backup).
- `backup/gui_tabs/` — старі multi-tab вкладки (застаріло, переміщено в backup).
- `functions/core_*` — planner, executor, memory, cache, settings, safety, checkpoint.
- `functions/logic_*` — orchestration, task running, scenarios, expectations, repair, watchers.
- `functions/tools_*` — desktop/browser/media tools.
- `functions/providers_*` + `functions/llm/` — LLM/provider layer.
  - `functions/llm/router.py` — RequestRouter для класифікації запитів (CODE/DEBUG/GUI/WEB/GENERAL/QUICK)
  - `functions/llm/provider_chain.py` — ProviderChain з fallback ланцюгом і quota tracking
- `functions/aaa_*` — legacy / wrapper-oriented tool layer.
- `functions/agent_loop.py` — AgentLoop (observe → plan → act → check).
- `functions/core_loop_detector.py` — LoopDetector (захист від зациклення агента).
- `functions/task_spec.py` — TaskSpecCompiler (структурована декомпозиція).
- `functions/global_voice_input.py` — Global voice input (Windows hook).
- `functions/self_learning.py` — Self-learning module.
- `core/context_controller.py` — ContextController (єдине управління пам'яттю між AgentLoop та VoiceAssistant).
- `utils/screen_helper.py` — DPI корекція координат для Windows масштабування.
- `tests/` — unit і integration-style тести.

### Спостереження

- Проєкт уже не малий: у `functions/` 100+ файлів.
- З'явився новий LLM-пакет `functions/llm/` з router.py, provider_chain.py для оркестрації ШІ.
- Стара термінологія ще лишилася в документації й частині модулів.
- Новий orchestration-стек існує поруч із legacy-шарами.

---

## 3. Головні архітектурні проблеми

### 3.1. Плоска структура і перевантажені модулі

Найважчі файли зараз:

- [main.py](../main.py)
- [core_gui_pyqt6/main_window.py](../core_gui_pyqt6/main_window.py)
- [functions/logic_commands.py](../functions/logic_commands.py)
- [functions/core_planner.py](../functions/core_planner.py)
- [functions/logic_task_runner.py](../functions/logic_task_runner.py)
- [functions/core_tool_runtime.py](../functions/core_tool_runtime.py)
- [functions/agent_loop.py](../functions/agent_loop.py)

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
- **Context Summarizer:** ✅ **ВИРІШЕНО** — реалізовано `core/context_controller.py` з tiktoken. ContextController забезпечує єдине управління пам'яттю між AgentLoop та VoiceAssistant, автоматичне підсумовування старих дій через LLM, стиснення OCR тексту та токенометрію.

### P1

- Завершити `tools_ui_accessibility.py`.
- Додати Windows smoke CI.
- Зафіксувати один стабільний E2E vertical slice.
- **Vector Memory:** Поточна реалізація Skills DB не підтримує семантичний пошук. Потрібна інтеграція ChromaDB/FAISS для масштабування самонавчення.
- **Розділення ролей LLM:** AgentLoop не розрізняє модель для планування та модель для критики. Варто дозволити конфігурацію різних провайдерів для Executor та Critic.
- **Loop Detection:** ✅ **ВИРІШЕНО** — реалізовано LoopDetector у `functions/core_loop_detector.py` з інтеграцією в AgentLoop та stuck_warning для LLM.
- **DPI корекція:** ✅ **ВИРІШЕНО** — реалізовано `utils/screen_helper.py` з корекцією координат для Windows масштабування через ctypes.windll.shcore. Інтегровано в `tools_mouse_keyboard.py`.

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
