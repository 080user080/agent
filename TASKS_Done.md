# Виконані задачі МАРК
> Останнє оновлення: 15.05.2026 (18:42)

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash
# Активація віртуального середовища
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

---

## НЕДАВНІ ВИПРАВЛЕННЯ (15.05.2026)

### A0. Усунуто конфлікт шляхів виконання (P0)

**Проблема:** В `main.py:process_text_command()` існували два конкуруючі шляхи виконання — Planner legacy (`VoiceAssistant.process_command`) і AgentLoop (`run_agent_loop`). Класифікація між ними через ключові слова була ненадійна. `run_agent_loop()` містив гілку `task_type == "CHAT"`, яка передоручала виконання назад у `process_command()` — це створювало зациклення.

**Виконано:**
- `process_text_command()` — замінено keyword-класифікацію на прямий виклик AgentLoop
- `run_agent_loop()` — видалено гілку `task_type == "CHAT"` і PlanExecutor fallback; тепер лише AgentLoop або fallback на `assistant.process_command()`
- `logic_commands.py:process_command()` — видалено `should_plan()` і AgentLoop-редирект; тепер тільки для STT-вводу

**Очікуваний pipeline:**
```
GUI команда → run_agent_loop() → AgentLoop → виконання
STT команда → process_command() → (якщо задача) → AgentLoop / (якщо чат) → LLM
```

**Файли:**
- `main.py` — `process_text_command()`, `run_agent_loop()`
- `functions/logic_commands.py` — `process_command()`

---

## НЕДАВНІ ВИПРАВЛЕННЯ (02.05.2026, 19:35)

### Виправлено Global Voice Input - tray icon
**Проблема:** Tray icon показується в system tray але не змінює колір при зміні статусу

**Виправлено:**
- Використано QApplication.postEvent() з кастомним _StatusUpdateEvent для потокобезпечного оновлення
- Додано customEvent() для обробки event-ів в основному потоці Qt
- Прибрано зайві логи

**Файли:**
- `functions/voice_tray_icon.py` - перероблено на postEvent/customEvent

### Виправлено Global Voice Input - вставка буфера обміну
**Проблема:** При натисканні Ctrl+F9 вставляється вміст буфера обміну Windows замість розпізнаного тексту

---

## ВИКОНАНІ ЗАВДАННЯ (перенесено 18.05.2026)

### ЕТАП А. Стабілізація та рефакторинг архітектури

#### А1. Полагодити pytest collection (P0) ✅

- [x] Повернути сумісність між тестами і `logic_task_runner`
- [x] Добитися щоб `pytest tests/` проходив хоча б collection без помилок
- [x] Зафіксувати публічні API для parser/runner/plan-об'єктів

#### А2. Реструктуризація папки functions/ ✅

Зараз у `functions/` 100+ файлів у плоскій структурі — це ускладнює навігацію. Згрупувати модулі по підпапках:

- [x] Створити `functions/llm/` — вже є, залишити без змін
- [x] Створити `functions/tools/` — перенести всі `tools_*.py` і `aaa_*.py`
- [x] Створити `functions/planning/` — перенести: `agent_loop.py`, `core_planner.py`, `core_plan_compiler.py`, `core_planner_critic.py`, `core_planner_runner.py`, `logic_task_runner.py`, `logic_expectations.py`, `task_spec.py`
- [x] Створити `functions/runtime/` — перенести: `core_tool_runtime.py`, `core_settings.py`, `core_memory.py`, `core_cache.py`, `core_session_budget.py`, `core_undo_manager.py`, `core_action_recorder.py`
- [x] Створити `functions/gui/` — перенести: `core_gui_guardian.py`, `tools_screen_capture.py`, `tools_ocr.py`, `tools_mouse_keyboard.py`, `tools_window_manager.py`, `tools_ui_detector.py`, `tools_ui_accessibility.py`, `tools_visual_diff.py`, `voice_tray_icon.py`
- [x] Виправити всі імпорти всередині переміщених файлів
- [x] Додати файли-заглушки для зворотної сумісності (49 файлів)
- [x] Переконатись що `pytest` проходить collection без помилок ✅ (1400 tests)

#### Розширення задачі А2.1: інтеграція core/ та utils/ ✅

- [x] Перенести `core/context_controller.py` до `functions/planning/`
- [x] Перенести `utils/screen_helper.py` до `functions/gui/`
- [x] Після перенесення виправити імпорти у всіх залежних модулях (tools_mouse_keyboard + тести)
- [x] Видалити порожні папки `core/` та `utils/`
- [x] Переконатись, що `pytest` проходить collection без помилок ✅ (1400 tests)