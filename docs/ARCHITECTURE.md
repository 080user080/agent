# Архітектура МАРК: поточний стан і напрямок
> Оновлено: 21.05.2026

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

Це не roadmap усіх фаз і не changelog. Це коротка технічна карта: як зараз реально влаштований проєкт, де архітектурний борг, у якому порядку варто його зменшувати.

---

## 2. Поточна структура

### Точки входу

- [run.py](../run.py) — універсальний entrypoint (PyQt6).
- [run_assistant_qt.py](../run_assistant_qt.py) — GUI entrypoint (PyQt6).
- [main.py](../main.py) — основний runtime / AssistantCore.

### Основні підсистеми

- `core_gui_pyqt6/` — PyQt6 GUI (основний і єдиний GUI бекенд).
- `functions/__init__.py` — експорт кореневих модулів.
- `functions/config.py` — глобальна конфігурація.
- `functions/global_voice_input.py` — Global voice input (Windows hook).
- `functions/logic_execution_report.py` — Execution Report.
- `functions/audio/` — audio processing (STT/TTS, filtering, continuous listener). ✅
- `functions/llm/` — LLM/provider layer.
  - `__init__.py` — експорт LLM модулів
  - `helpers.py` — допоміжні функції
  - `logic_llm_tools.py` — OpenAI-compatible tool-calling
  - `providers_vision.py` — Vision-LM (OpenAI/Claude/Gemini)
- `functions/planning/` — planning layer (task intake, context analysis, pipeline compilation, agent loop).
- `functions/runtime/` — runtime orchestration (watcher, conditions, executor, FunctionRegistry). ✅
- `functions/gui/` — GUI-логіка:
  - `core_gui_guardian.py` — GUIGuardian risk assessment ✅
  - `logic_commands.py` — VoiceAssistant / обробка команд
- `functions/tools/` — desktop/browser/media tools:
  - `tools_mouse_keyboard.py` — mouse/keyboard automation ✅
  - `tools_window_manager.py` — window manager ✅
  - `tools_screen_capture.py` — screen capture ✅
  - `tools_ocr.py` — OCR ✅
  - `tools_ui_detector.py` — UI detection ✅
  - `tools_app_recognizer.py` — app recognizer ✅
  - `tools_visual_diff.py` — visual diff ✅
  - `tools_ui_accessibility.py` — Windows UIA API ✅
  - `tools_browser_cdp.py` — browser CDP automation ✅
  - `tools_playwright.py` — Playwright integration ✅
  - `aaa_file_operations.py` — legacy file operations wrapper
  - `aaa_open_interpreter.py` — Open Interpreter fallback
- `runtime/` — runtime data (cache, self-learning).
- `scenarios/` — JSON тестові сценарії.
- `scaner/` — файловий сканер.
- `tests/` — unit і integration-style тести (60+ файлів).
- `TEST_GUI/` — GUI діагностичні тести.

### Спостереження

- Проєкт уже не малий: у `functions/` 100+ файлів.
- LLM-пакет `functions/llm/` містить logic_llm_tools.py та providers_vision.py.
- `gui/` — новий пакет, виділений з кореня `functions/`.
- `tools/` — новий пакет, куди зібрано всі Phase 1-11 GUI-інструменти.
- `planning/` — містить AgentLoop, TaskRunner, ContextAnalyzer, PipelineCode.
- `runtime/` — містить FunctionRegistry, PermissionGate, Watcher, WindsurfWatcher.
- Стара термінологія ще лишилася в документації й частині модулів.

---

## 3. Головні архітектурні проблеми

### 3.1. Плоска структура і перевантажені модулі

Найважчі файли зараз: main.py, core_gui_pyqt6/main_window.py, logic_commands.py, core_planner.py, logic_task_runner.py, agent_loop.py. Проблема не лише в розмірі — ці модулі одночасно тримають state, знають про GUI, tool runtime, LLM/planning/execution transitions. Це підвищує вартість будь-якої зміни.

### 3.2. Нестабільні контракти

Симптоми: тести імпортують API, яких уже немає; документація посилається на старі модулі; новий і legacy стек частково дублюють поняття. Найперше треба стабілізувати: Plan/Task/parser/compiler контракти, публічні точки входу TaskRunner, публічний LLM helper layer.

### 3.3. Змішані шари відповідальності

planner і execution concerns змішані в суміжних модулях; GUI-логіка та orchestration-рішення місцями близько пов'язані; browser/provider/tool abstraction не всюди розділені.

### 3.4. Legacy шар не ізольований

`aaa_*` ще корисний для сумісності, але має бути чітко позначений як legacy-обгортки, а не рівноправний сучасний API.

### 3.5. Runtime-артефакти частково розкидані

Stateful дані мають жити або в `runtime/`, або в `logs/`. Кодова директорія не повинна бути місцем для робочих JSON-станів.

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
- **Vector Memory:** Поточна реалізація Skills DB не підтримує семантичний пошук. Потрібна інтеграція ChromaDB/FAISS.
- **Розділення ролей LLM:** AgentLoop не розрізняє модель для планування та модель для критики.

### P2

- Прибрати циклічні залежності між GUI/screen/input шарами.
- Вирівняти структуру runtime state.
- Зменшити зв'язність між planner / runner / GUI.

---

## 5. Рекомендований порядок рефакторингу

### Крок 1. Стабілізувати контракти, не рухаючи папки

Спершу не треба робити великий rename/move. Краще: ввести явні export points, повернути сумісність для тестів, зафіксувати один спосіб парсингу плану, визначити public API і internal.

### Крок 2. Винести спільні абстракції

Має сенс додати невеликий спільний шар для Point/Rect/Region, tool action/result structures, спільних error/result helpers. Це дасть менше прямого імпорту між tool-модулями.

### Крок 3. Розрізати великі модулі по відповідальностях

Насамперед: logic_commands.py, core_planner.py, main.py. Головне — витягнути окремо command handlers, planner prompt building/validation, app initialization/dependency wiring.

### Крок 4. Поступово групувати модулі по підсистемах

Після стабілізації API можна рухатися до структури: llm/, tools/, planning/, gui_logic/, runtime/, legacy/. Але це має бути наслідок попередніх кроків, а не стартова операція.

---

## 6. Чого не варто робити зараз

- Не робити "великий вибух" з масовим перенесенням файлів.
- Не додавати нові доменні пайплайни, поки code vertical slice не стабілізований.
- Не множити нові abstraction layers без конкретного виграшу в testability або підтримці.

---

## 7. Definition of better

Архітектура стане помітно кращою, коли: `pytest` стабільно проходить collection і базовий набір тестів; є Windows smoke CI; status.md, README.md і код не суперечать одне одному; UIA шар не містить critical TODO в основних user-facing entrypoints; є один стабільний E2E сценарій `task -> plan -> execute -> validate -> report`; legacy шар чітко відділений від нового orchestration-стеку.