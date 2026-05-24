# Виконані задачі МАРК
> Останнє оновлення: 24.05.2026 (01:45)

**ВАЖЛИВО:** Всі тести та запуск програми повинні виконуватися тільки через віртуальне середовище (venv).

```bash
cd /d D:\Python\TEXT\LLM_model
call venv\Scripts\activate.bat
cd /d D:\Python\agent
```

---

## НЕДАВНІ ВИПРАВЛЕННЯ (15.05.2026)

### A0. Усунуто конфлікт шляхів виконання (P0)

---

## НЕДАВНІ ВИПРАВЛЕННЯ (02.05.2026, 19:35)

### Виправлено Global Voice Input - tray icon
### Виправлено Global Voice Input - вставка буфера обміну

---

## ВИКОНАНІ ЗАВДАННЯ (перенесено 24.05.2026)

### ЕТАП Б. Індексація проєкту для кодового агента

#### Б1. Repo Map — карта проєкту
- [x] Створити `functions/project_indexer.py`
- [x] Додати інструмент `get_repo_map()` в реєстр функцій
- [x] Додати інструмент `update_repo_map(filepath)`
- [x] Інтеграція в `get_coding_system_prompt()`

#### Б2. Dependency Graph — карта залежностей
- [x] Розширити `functions/project_indexer.py` — аналіз `import`
- [x] Додати інструмент `get_file_dependents(filepath)`
- [x] Оновити `build_coding_section()`

#### Б3. Навчити агента комбінувати інструменти
- [x] Оновити системний промпт coding-режиму
- [x] Додати явну заборону в промпт

---

## ВИКОНАНІ ЗАВДАННЯ (перенесено 18.05.2026)

### ЕТАП А. Стабілізація та рефакторинг архітектури

#### А1. Полагодити pytest collection (P0) ✅
#### А2. Реструктуризація папки functions/ ✅
#### Стабілізація AgentLoop для коду (перед А3) ✅
#### А3. Розрізати великі модулі ✅

**Частина 1: Розбиття `main.py`**
- Крок 1.1: `core_initializer_checks.py`
- Крок 1.2: `audio/initializer.py`
- Крок 1.3: `agent_coordinator.py`

**Частина 2: Розбиття `agent_loop.py`**
- Крок 2.1: `observe.py`
- Крок 2.2: `plan.py`
- Крок 2.3: `act.py`
- Крок 2.4: `check.py`
- Крок 2.5: Перезбирання `AgentLoop`

**Частина 3: Розбиття `logic_commands.py`**
- Крок 3.1: `commands_streaming.py`
- Крок 3.2: `commands_audio.py`
- Крок 3.3: `commands_planner.py`
- Крок 3.4: Рефакторинг `logic_commands.py`

**Частина 4: Розбиття `core_planner.py`**
- Крок 4.1: `planner_prompt_builder.py`
- Крок 4.2: `planner_validator.py`
- Крок 4.3: `planner_repair.py`
- Крок 4.4: Спрощення `core_planner.py`

---

## 📈 Загальні критерії готовності (Definition of Done)

- [x] **SRP:** Кожен файл має одну чітку відповідальність
- [x] **Zero ImportError:** Запуск без помилок
- [x] **Тести:** 1250 passed, 1 skipped
- [ ] **End-to-End:** ⏳ Не верифіковано