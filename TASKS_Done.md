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