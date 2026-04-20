# Проєкт: Асистент МАРК
> Останнє оновлення: 20.04.2026

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
- **бачить екран і взаємодіє з будь-якою програмою**

Основний стабільний сценарій: **текстова взаємодія через GUI**.
Стратегічний напрямок: **Універсальний Windows-агент з Computer Vision та GUI Automation**.

---

## 2. Поточний стан (20.04.2026)

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
- **Багатоетапний repair** — цикл до 3 спроб + 1 replan
- **Retry механізм планера** — 2 спроби з різними промптами
- **Утиліти** — `create_folder`, `search_in_text`, `count_words`
- **Тести** — pytest suite для `core_planner`, `core_memory`, `core_executor`
- **Документація** — README.md + CONTRIBUTING.md

### Не дороблено / В процесі

- Голосове введення — індикатор мікрофона в GUI (відкладено через STT)
- Planner не робить повне перепланування дерева
- **Phase 4-7 GUI Automation** — Computer Vision, Smart UI Navigation, Safety, Learning (детальний план нижче)

---

## 3. Залежності

| Пакет | Версія | Статус |
|-------|--------|--------|
| numpy | 1.26.4 | ✅ знижено (несумісність з torch 2.x) |
| torch | 2.x | ✅ |
| sounddevice | 0.5.5 | ✅ |
| noisereduce | 3.0.3 | ✅ |
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
### Етап B. Strong Agent Loop ✅
### Етап C. Tool Runtime ✅
### Етап D. Memory & Context ✅
### Етап E. Safety ✅
### Етап F. Code Agent Mode ✅

---

## 6. Готовність до продакшну

**~95% Core** — основні функції (планер, пам'ять, executor, кеш) працюють стабільно.
**~0% GUI Automation** — новий масштабний напрямок (Phase 1–7), перетворить агента на універсального автоматизатора Windows.

---

---

# 🚀 СТРАТЕГІЧНИЙ ПЛАН: GUI Automation & Computer Vision

> **Ціль:** Перетворити МАРК на універсального Windows-агента, який **бачить екран**, **розуміє** що на ньому, і **самостійно взаємодіє** з будь-якою програмою без спеціального API.

---

## 🗺️ Огляд фаз

| Фаза | Назва | Статус | Пріоритет | Термін |
|------|-------|--------|-----------|--------|
| 1 | Базова автоматизація GUI | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 2 | Скріншоти та аналіз екрану | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 3 | OCR — розпізнавання тексту | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 4 | Комп'ютерний зір (CV) | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 5 | Розумна навігація по UI | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 6 | Безпека та журнал дій | ✅ **Завершено** | ✅ Готово | 20.04.2026 |
| 7 | Навчання та адаптація | 🔴 Не розпочато | 🟡 Середній | 4–6 тижнів |

---

## 📦 Phase 1: Базова автоматизація GUI (Core Input Control)

**Статус:** ✅ Готово | **Пріоритет:** ✅ Завершено | **Термін:** 20.04.2026

**Мета:** Дати агенту «руки» — можливість керувати мишею та клавіатурою, взаємодіяти з вікнами Windows.

**Залежності:** `pyautogui`, `pywin32`, `psutil`

### 1.1 Модуль `tools_mouse_keyboard.py` — Керування мишею та клавіатурою

#### Миша
- [ ] `mouse_click(x, y, button='left', clicks=1, interval=0.1)` — клік в координати (одиночний / подвійний / правий)
- [ ] `mouse_move(x, y, duration=0.5)` — плавне переміщення курсора
- [ ] `mouse_scroll(amount, direction='down', x=None, y=None)` — прокрутка (вертикальна / горизонтальна)
- [ ] `mouse_drag(start_x, start_y, end_x, end_y, duration=0.5)` — перетягування (drag & drop)
- [ ] `get_mouse_position()` → `{"x": int, "y": int}` — поточні координати курсора
- [ ] `mouse_click_image(image_path, confidence=0.8)` — клік по зображенню (template matching)

#### Клавіатура
- [ ] `keyboard_press(key)` — одне натискання клавіші (Enter, Escape, Tab, F5, Delete, ...)
- [ ] `keyboard_type(text, interval=0.02)` — введення тексту (посимвольно, з урахуванням кодування)
- [ ] `keyboard_hotkey(*keys)` — комбінації клавіш (`Ctrl+C`, `Alt+F4`, `Win+D`, `Ctrl+Shift+T`)
- [ ] `keyboard_hold(key, duration=1.0)` — утримання клавіші (для drag, select-all, ...)
- [ ] `keyboard_send_special(key_name)` — спеціальні клавіші (`PrintScreen`, `NumLock`, `ScrollLock`)

#### Clipboard
- [ ] `clipboard_copy_text(text)` — записати текст у буфер обміну
- [ ] `clipboard_get_text()` → `str` — прочитати текст з буфера
- [ ] `clipboard_copy_image(image_path)` — скопіювати зображення

### 1.2 Модуль `tools_window_manager.py` — Керування вікнами Windows

#### Пошук та список вікон
- [ ] `list_windows(include_hidden=False)` → `[{hwnd, title, process_name, pid, rect}]`
- [ ] `find_window_by_title(pattern, exact=False)` → `hwnd | None`
- [ ] `find_window_by_process(process_name)` → `[hwnd]`
- [ ] `find_window_by_class(class_name)` → `[hwnd]`
- [ ] `get_active_window()` → `{hwnd, title, process_name, rect}`

#### Керування станом вікон
- [ ] `activate_window(hwnd)` — перевести вікно на передній план (SetForegroundWindow)
- [ ] `minimize_window(hwnd)` — згорнути вікно
- [ ] `maximize_window(hwnd)` — розгорнути на весь екран
- [ ] `restore_window(hwnd)` — відновити з мінімізованого стану
- [ ] `close_window(hwnd, force=False)` — закрити вікно (WM_CLOSE або TerminateProcess)
- [ ] `hide_window(hwnd)` / `show_window(hwnd)` — приховати / показати

#### Позиція та розмір
- [ ] `move_window(hwnd, x, y)` — перемістити вікно
- [ ] `resize_window(hwnd, width, height)` — змінити розмір
- [ ] `move_resize_window(hwnd, x, y, width, height)` — одночасно
- [ ] `get_window_rect(hwnd)` → `{"x": int, "y": int, "width": int, "height": int}`
- [ ] `center_window(hwnd)` — відцентрувати вікно на екрані

#### Допоміжні функції
- [ ] `is_window_visible(hwnd)` → `bool`
- [ ] `is_window_minimized(hwnd)` → `bool`
- [ ] `is_window_maximized(hwnd)` → `bool`
- [ ] `wait_for_window(title_pattern, timeout=10)` → `hwnd | None`
- [ ] `wait_window_close(hwnd, timeout=30)` → `bool`
- [ ] `bring_all_to_top(process_name)` — підняти всі вікна процесу

### 1.3 Реєстрація в TOOL_POLICIES

- [ ] Додати всі нові функції в `core_tool_runtime.py`
- [ ] Рівні ризику: `mouse_click` → `SAFE`, `keyboard_hotkey` → `SAFE`, `close_window` → `CONFIRM_REQUIRED`
- [ ] Аудит усіх GUI-дій у `logs/audit.jsonl`

### 1.4 Тести Phase 1

- [ ] `tests/test_tools_mouse_keyboard.py` — mock pyautogui, перевірка параметрів
- [ ] `tests/test_tools_window_manager.py` — mock win32gui, перевірка логіки пошуку
- [ ] Інтеграційний тест: відкрити notepad → ввести текст → зберегти → закрити

---

## 📸 Phase 2: Скріншоти та аналіз екрану (Screen Capture)

**Статус:** ✅ Готово | **Пріоритет:** ✅ Завершено | **Термін:** 20.04.2026

**Мета:** Дати агенту «очі» — можливість бачити екран і аналізувати його вміст.

**Залежності:** `Pillow`, `mss`, `pywin32`

### 2.1 Модуль `tools_screen_capture.py` — Захоплення екрану

#### Основні функції
- [ ] `take_screenshot(save_path=None)` → `PIL.Image` — повний скріншот (усі монітори)
- [ ] `capture_monitor(monitor_index=0, save_path=None)` → `PIL.Image` — скріншот конкретного монітора
- [ ] `capture_region(x, y, width, height, save_path=None)` → `PIL.Image` — захоплення прямокутної області
- [ ] `capture_window(hwnd, save_path=None)` → `PIL.Image` — скріншот конкретного вікна (навіть якщо перекрите)
- [ ] `capture_active_window(save_path=None)` → `PIL.Image` — скріншот активного вікна

#### Інформація про екран
- [ ] `get_screen_size()` → `{"width": int, "height": int}` — роздільна здатність
- [ ] `get_monitors_info()` → `[{index, x, y, width, height, primary}]` — всі монітори
- [ ] `get_pixel_color(x, y)` → `{"r": int, "g": int, "b": int, "hex": str}` — колір пікселя
- [ ] `get_region_color_histogram(x, y, w, h)` → розподіл кольорів в регіоні

#### Порівняння та пошук
- [ ] `find_image_on_screen(template_path, confidence=0.8)` → `{"x": int, "y": int, "confidence": float} | None`
- [ ] `find_all_images_on_screen(template_path, confidence=0.8)` → `[{x, y, confidence}]`
- [ ] `wait_for_image(template_path, timeout=10, interval=0.5)` → `{x, y} | None`
- [ ] `image_changed(region, threshold=0.05)` → `bool` — чи змінився регіон екрану
- [ ] `wait_for_visual_change(region, timeout=10)` → `bool` — очікувати будь-яку зміну
- [ ] `wait_for_visual_stable(region, stable_time=1.0, timeout=15)` → `bool` — очікувати стабільності

#### Аналіз кольорів та змін
- [ ] `pixel_matches_color(x, y, color, tolerance=10)` → `bool`
- [ ] `wait_for_color(x, y, color, timeout=10)` → `bool`
- [ ] `detect_loading_indicator(region=None)` → `bool` — спінер / progress bar
- [ ] `detect_modal_dialog()` → `bool` — чи є модальне вікно поверх основного

### 2.2 Кешування скріншотів

- [ ] `ScreenCache` клас — зберігає останні N скріншотів у пам'яті
- [ ] Автоматичний скріншот до/після кожної дії (зберігається у `logs/screenshots/`)
- [ ] Запис у `logs/gui_actions.jsonl` (JSONL-формат для зручного парсингу)
- [ ] Ліміт зберігання: налаштований у `config.py` (за замовчуванням 500 записів / 7 днів)

#### Перегляд та експорт
- [ ] `get_recent_actions(count=10)` → `[ActionRecord]`
- [ ] `export_session_log(format='json')` → `str` — повний лог сесії
- [ ] `generate_action_report()` → `str` — читабельний звіт для користувача
- [ ] `search_actions(filter_dict)` → `[ActionRecord]` — пошук за типом дії / часом / програмою

### 2.3 Тести Phase 2

- [ ] `tests/test_tools_screen_capture.py` — mock mss, перевірка PIL операцій
- [ ] Тест template matching з синтетичними зображеннями
- [ ] Тест `capture_window` для мінімізованого вікна

---

## Phase 3: OCR — Розпізнавання тексту на екрані

**Статус:** ✅ Готово | **Пріоритет:** ✅ Завершено | **Термін:** 20.04.2026

**Мета:** Агент читає текст з будь-якого місця екрану — кнопок, меню, повідомлень, таблиць.

**Залежності:** `pytesseract` (основний), `easyocr` (fallback)

### 3.1 Модуль `tools_ocr.py` — Розпізнавання тексту ✅

**Файл:** `functions/tools_ocr.py` (~520 рядків)

#### Базові функції
- ✅ `ocr_screen(save_screenshot=None)` → Розпізнати текст на всьому екрані
- ✅ `ocr_region(x, y, width, height)` → Розпізнати текст в області
- ✅ `ocr_window(hwnd)` → Розпізнати текст у вікні
- ✅ `ocr_image(image_path)` → Розпізнати текст на зображенні
- ✅ `ocr_to_string(region=None)` → Просто текст для LLM

#### Пошук та взаємодія
- ✅ `find_text_on_screen(text, case_sensitive=False)` → Знайти координати тексту
- ✅ `find_all_text_on_screen(text)` → Всі входження тексту
- ✅ `click_text(text, offset_x, offset_y)` → Знайти текст і клікнути
- ✅ `wait_for_text(text, timeout=10)` → Очікувати появи тексту

#### Реалізація
- ✅ **OCREngine** клас — підтримка PyTesseract та EasyOCR
- ✅ **ScreenOCR** клас — інтеграція з ScreenCapture
- ✅ **Fallback логіка** — якщо один движок не впевнений, пробує інший
- ✅ **Попередня обробка** — збільшення малих зображень, контраст, різкість
- ✅ **Визначення мов** — українська (ukr) + англійська (eng)

### 3.2 Реєстрація в TOOL_POLICIES ✅

Додано в `core_tool_runtime.py`:
- `ocr_screen` — SAFE, idempotent
- `ocr_region` — SAFE, idempotent  
- `ocr_window` — SAFE, idempotent
- `ocr_image` — SAFE, idempotent
- `find_text_on_screen` — SAFE, idempotent
- `click_text` — CONFIRM_REQUIRED (дія)
- `wait_for_text` — SAFE

### 3.3 Тести Phase 3 ✅

**Файл:** `tests/test_tools_ocr.py`
- ✅ Тести OCREngine (ініціалізація, розпізнавання)
- ✅ Тести ScreenOCR (пошук тексту, кліки)
- ✅ Тести попередньої обробки зображень
- ✅ Mock тести без зовнішніх залежностей

### Приклади використання

```python
# Розпізнати весь екран
result = ocr_screen()
print(result['text'])  # "Зберегти файл як..."

# Знайти кнопку і клікнути
result = click_text("Зберегти")
if result['success']:
    print(f"Клікнуто в ({result['clicked_at']['x']}, {result['clicked_at']['y']})")

# Очікувати текст на екрані
result = wait_for_text("Завантаження завершено", timeout=30)
```

### Встановлення залежностей

```bash
# Основний движок (рекомендовано)
pip install pytesseract
# Також потрібно встановити Tesseract-OCR:
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# У PATH додати: C:\Program Files\Tesseract-OCR

# Альтернатива (GPU-прискорена)
pip install easyocr
```

---

## Phase 4: Комп'ютерний зір (Computer Vision)

**Статус:** ✅ **Завершено** | **Пріоритет:** ✅ Готово | **Термін:** 20.04.2026

#### Template matching (без ML)
- `find_button_by_image(template_path, confidence=0.8)` → `{x, y, width, height, confidence}`
- `find_icon(icon_name_or_path, confidence=0.8)` → `{x, y, confidence}`
- `find_checkbox(region=None)` → `[{x, y, checked, center_x, center_y}]`
- `find_input_field(region=None)` → `[{x, y, width, height, center_x, center_y}]`
- `find_progress_bar(region=None)` → `{x, y, width, height, percent}`

#### Комбінований OCR + CV пошук
- `find_button_by_text(text, region=None, confidence=0.7)` → `{x, y, center_x, center_y, confidence}`
- `find_label(text, region=None)` → `{x, y, center_x, center_y}`
- `find_input_near_label(label_text, region=None)` → `{x, y, width, height, label}`

#### Аналіз стану елементів
- `is_button_enabled(x, y, width, height)` → `bool`
- `is_checkbox_checked(x, y)` → `bool`
- `get_button_state(x, y)` → `"normal" | "hovered" | "pressed" | "disabled"`

### 4.2 Модуль `tools_app_recognizer.py` — Розпізнавання програм 

- `detect_active_application()` → `{name, type, confidence, exe_name, pid, hwnd}`
- `detect_application_state()` → `{state: "idle"|"loading"|"error"|"dialog", details}`
- `is_application_ready(hwnd)` → `bool`
- `detect_file_dialog()` → `{type: "open"|"save", current_path, title, hwnd}`
- `detect_error_dialog()` → `{title, message, buttons, hwnd}`
- `detect_context_menu()` → `{items, count, hwnd}`

### 4.3 Модуль `tools_visual_diff.py` — Порівняння станів екрану 

- `capture_baseline(name)` — зберегти еталонний скріншот
- `delete_baseline(name)` — видалити еталон
- `list_baselines()` → `[{name, path, created, size_bytes}]`
- `compare_with_baseline(name)` → `{changed, diff_regions, diff_percent, changed_pixels}`
- `highlight_changes(before, after)` → `PIL.Image` з підсвіченими змінами
- `wait_for_visual_change(region, timeout=10)` → `{changed, diff_percent, wait_time}`
- `wait_for_visual_stable(region, stable_time=1.0, timeout=15)` → `{stable, wait_time}`

### 4.4 Тести Phase 4

- `tests/test_tools_ui_detector.py` — синтетичні зображення UI-елементів
- `tests/test_tools_app_recognizer.py` — mock скріншоти відомих програм
- [ ] `tests/test_tools_visual_diff.py` — синтетичні "до/після" зображення

---

## 🧠 Phase 5: Розумна навігація по UI (Smart UI Navigation)

**Статус:** ✅ **Завершено** | **Пріоритет:** ✅ Готово | **Термін:** 20.04.2026

**Мета:** Агент може виконувати складні UI-сценарії автономно: заповнити форму, пройти wizard, відповісти на діалог.

### 5.1 Модуль `logic_ui_navigator.py` — Інтелектуальна навігація ✅

**Файл:** `functions/logic_ui_navigator.py` (~650 рядків)

#### Базові UI-дії
- ✅ `click_element(description, element_type)` → `{success, coordinates, message}`
- ✅ `type_in_field(field_description, text, clear_first)` → `{success, field, text}`
- ✅ `select_option(dropdown_description, option_text)` → `{success, dropdown, option}`
- ✅ `check_checkbox(label, state)` → `{success, label, previous_state, new_state}`
- ✅ `select_radio(label)` → `{success, label}`
- ✅ `navigate_tabs(tab_name)` → `{success, tab}`

#### Форми
- ✅ `fill_form(field_dict)` → `{success, filled, failed, total}`
- ✅ `submit_form(submit_button_text)` → `{success, button}`
- ✅ `read_form_values(field_names)` → `{success, values, raw_text}`
- ✅ `validate_form_filled(required_fields)` → `{valid, missing, checked}`

#### Меню та контекстні меню
- ✅ `open_menu(menu_name)` → `{success, menu}`
- ✅ `click_menu_item(path_list)` → `{success, path, message}`
- ✅ `open_context_menu(x, y)` → `{success, coordinates}`
- ✅ `click_context_item(item_text)` → `{success, item}`
- ✅ `close_menu()` → `{success, message}`

#### Діалоги
- ✅ `handle_dialog(expected_text, action)` → `{success, action, button, message}`
- ✅ `dismiss_all_dialogs(timeout)` → `{closed, failed, message}`

### 5.2 Модуль `logic_scenario_runner.py` — Сценарії автоматизації ✅

**Файл:** `functions/logic_scenario_runner.py` (~700 рядків)

#### Визначення та виконання сценаріїв
- ✅ `ScenarioStep` — датаклас кроку: `{step_type, description, params, verify, on_fail}`
- ✅ `Scenario` — датаклас сценарію з серіалізацією JSON
- ✅ `run_scenario(scenario, variables)` → `ScenarioResult`
- ✅ `run_scenario_from_file(filename, variables)` → `ScenarioResult`
- ✅ `save_scenario(scenario, filename)` → `{success, path}`
- ✅ `load_scenario(filename)` → `{success, scenario}`
- ✅ `list_scenarios()` → `[{name, description, path, steps_count}]`
- ✅ `validate_scenario(scenario)` → `{valid, warnings, errors}`

#### Вбудовані типові сценарії
- ✅ `scenario_save_file()` — зберегти файл (Ctrl+S)
- ✅ `scenario_open_file(file_path)` — відкрити файл (Ctrl+O)
- ✅ `scenario_save_as(save_path)` — зберегти як (Ctrl+Shift+S)
- ✅ `scenario_find_in_program(search_text)` — пошук (Ctrl+F)
- ✅ `scenario_print()` — друк (Ctrl+P)
- ✅ `scenario_undo_redo(action, count)` — undo/redo
- ✅ `scenario_select_all_copy()` — виділити все та скопіювати

### 5.3 Модуль `logic_context_analyzer.py` — Аналіз контексту екрану ✅

**Файл:** `functions/logic_context_analyzer.py` (~600 рядків)
#### Аналіз стану екрану
- ✅ `analyze_current_context()` → `{application, state, elements, available_actions, warnings}`
- ✅ `suggest_next_action(goal)` → `{action, params, confidence, reasoning, alternatives}`
- ✅ `explain_screen(detail_level)` → `str` — текстовий опис для LLM
- ✅ `detect_user_goal_completion(goal_description)` → `{completed, confidence, evidence}`
- ✅ `detect_blocker()` → `{type, description, suggested_fix, severity}` або `None`
- ✅ `get_context_changes(steps_back)` → порівняння з попереднім станом

### 5.4 Тести Phase 5

- [ ] `tests/test_logic_ui_navigator.py` — mock Phase 1-4 модулі
- [ ] `tests/test_logic_scenario_runner.py` — mock сценарії
- [ ] E2E тест: відкрити Notepad → заповнити форму → зберегти → закрити

---

## Phase 6: Безпека, Аудит та Відкат дій

**Статус:**  **Завершено** | **Пріоритет:**  Готово | **Термін:** 20.04.2026

**Мета:** Гарантувати безпечну роботу агента з реальним UI — ніяких неочікуваних дій, журнал усього, можливість відкату.

### 6.1 Модуль `core_action_recorder.py` — Журнал GUI-дій 

**Файл:** `functions/core_action_recorder.py` (~500 рядків)

#### Запис дій
- `ActionRecord` датаклас зі скріншотами до/після
- `ActionRecorder` singleton з автозаписом
- Запис у `logs/gui_actions.jsonl`
- Ліміт: 500 записів / 7 днів
- Декоратор `@recordable(action_type)`

#### Перегляд та експорт
- `get_recent_actions(count)` / `search_actions(filter)`
- `export_session_log(format)` — JSON або text
- `generate_action_report()` — статистика по діях

### 6.2 Модуль `core_undo_manager.py` — Система відкату дій 

**Файл:** `functions/core_undo_manager.py` (~550 рядків)

#### Snapshots
- `StateSnapshot` — скріншот, кліпборд, активне вікно, позиція миші
- `save_snapshot(label)` / `restore_snapshot(id)`
- `list_snapshots()` / `SnapshotContext` менеджер

#### Undo логіка
- `undo_last(count)` — відкат N дій
- `undo_to_snapshot(id)` — відкат до snapshot
- Handlers: `mouse_click`, `keyboard_type`, `file_move`, `fill_form`
- `irreversible` прапорець для незворотних дій

### 6.3 Модуль `core_gui_guardian.py` — Захист від небезпечних дій 

**Файл:** `functions/core_gui_guardian.py` (~450 рядків)

#### Рівні ризику
- `GUIRiskLevel`: LOW / MEDIUM / HIGH / CRITICAL
- `assess_risk(action, params)` → оцінка ризику
- `is_action_allowed(action, params)` → перевірка

#### Sandbox
- `enable_sandbox_mode(region, apps)` — whitelist/blacklist
- `set_allowed_region(x, y, w, h)` — географічні обмеження
- `set_allowed_applications(apps)` — дозволені програми

#### Preview та Simulation
- `preview_action(action, params)` — текстовий опис
- `simulate_action(action, params)` — сухий прогін
- `get_safety_report()` — звіт про безпеку
- Декоратор `@guarded(action_name)`

### 6.4 Оновлення TOOL_POLICIES 

- Додано 20+ інструментів Phase 6
- Рівні ризику: SAFE для аналізу, CONFIRM_REQUIRED для відкату/змін

### 6.5 Тести Phase 6

- [ ] `tests/test_core_action_recorder.py`
- [ ] `tests/test_core_undo_manager.py` — тест undo для введення тексту, переміщення файлів
- [ ] `tests/test_core_gui_guardian.py` — тест блокування небезпечних дій

---

## 📚 Phase 7: Навчання, Адаптація та Профілі програм

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🟡 Середній | **Термін:** 4–6 тижнів

**Мета:** Агент вчиться зі свого досвіду — запам'ятовує успішні шляхи, будує профілі програм, автоматизує повторювані задачі.

### 7.1 Модуль `core_app_profiles.py` — Профілі програм

- [ ] `AppProfile` клас: `{app_name, exe_path, known_elements, common_shortcuts, workflows}`
- [ ] Вбудовані профілі для: Notepad, Paint, Explorer, Calculator, Chrome, Word, Excel
- [ ] `learn_from_interaction(app_name, action, result)` — доповнення профілю з досвіду
- [ ] `get_profile(app_name)` → `AppProfile`
- [ ] `save_profiles()` / `load_profiles()` — збереження в `app_profiles.json`
- [ ] `generate_profile_from_observation(hwnd)` — автоматично вивчити програму

### 7.2 Модуль `tools_macro_recorder.py` — Запис та відтворення макросів

#### Запис
- [ ] `start_recording(macro_name)` — почати запис дій користувача
- [ ] `stop_recording()` → `Macro` — зупинити та повернути записаний макрос
- [ ] `pause_recording()` / `resume_recording()` — пауза в записі
- [ ] `add_comment_to_recording(text)` — додати коментар до кроку

#### Макроси
- [ ] `Macro` клас: `{name, description, steps: [MacroStep], variables}`
- [ ] `MacroStep` клас: `{action, params, delay, verify, on_fail: "skip"|"abort"|"retry"}`
- [ ] `save_macro(macro, path)` — зберегти в JSON-файл
- [ ] `load_macro(path)` → `Macro`
- [ ] `list_macros()` → `[{name, description, path}]`

#### Відтворення
- [ ] `play_macro(macro_name_or_path, variables={})` → `{success, steps_completed, error}`
- [ ] `play_macro_step_by_step(macro)` — покроково з підтвердженням
- [ ] `validate_macro(macro)` → `{valid, warnings, errors}` — перевірка без виконання

### 7.3 Модуль `logic_task_learner.py` — Навчання на сценаріях

- [ ] `TaskPattern` — шаблон повторюваної задачі
- [ ] `detect_repeated_pattern(action_history)` → `TaskPattern | None` — розпізнати повтор
- [ ] `suggest_automation(pattern)` → `str` — запропонувати автоматизацію
- [ ] `create_macro_from_pattern(pattern)` → `Macro` — автоматично створити макрос
- [ ] `adaptive_click(description, fallback_list)` → `bool` — якщо перший варіант не спрацював, пробує наступні
- [ ] `remember_successful_path(goal, actions)` — запам'ятати успішний шлях
- [ ] `recall_path(goal)` → `[action] | None` — згадати перевірений шлях

### 7.4 Планувальник задач

- [ ] `schedule_task(task_description, time_or_trigger)` — запланувати задачу
- [ ] `list_scheduled_tasks()` → `[{id, description, schedule, status}]`
- [ ] `cancel_scheduled_task(task_id)` → `bool`
- [ ] Тригери: час (`"09:00"`), подія (`"on_file_change"`), інтервал (`"every 1h"`)

### 7.5 Тести Phase 7

- [ ] `tests/test_core_app_profiles.py`
- [ ] `tests/test_tools_macro_recorder.py` — mock запис та відтворення
- [ ] `tests/test_logic_task_learner.py` — синтетична history, перевірка pattern detection

---

## 🔌 Додаткові модулі (паралельно з основними фазами)

### Інтеграція з браузером (Chrome/Edge)
- [ ] `tools_browser.py` — Selenium-інтеграція
  - [ ] `open_url(url)`, `navigate_back()`, `navigate_forward()`, `refresh()`
  - [ ] `find_element_by_text(text)`, `find_element_by_selector(css)`
  - [ ] `browser_type(selector, text)`, `browser_click(selector)`
  - [ ] `browser_screenshot()`, `browser_get_page_text()`
  - [ ] `browser_execute_js(code)` → результат виконання JavaScript

### Інтеграція з Office (Word, Excel)
- [ ] `tools_word.py` — через COM (`win32com.client`)
  - [ ] Відкрити / зберегти / закрити документ
  - [ ] Знайти та замінити текст, форматування абзаців
  - [ ] Вставити зображення, таблицю, заголовок

- [ ] `tools_excel.py` — через COM
  - [ ] Читання / запис комірок, рядків, стовпців
  - [ ] Застосування формул, сортування, фільтри
  - [ ] Генерація графіків, збереження як PDF

### Голосові сповіщення та індикатори
- [ ] Overlay-індикатор на екрані (прозоре вікно): "⏳ Виконую: крок 3/5"
- [ ] Спливаючі toast-сповіщення (через `win10toast` або `plyer`)
- [ ] Звукові сигнали: успіх (✅), помилка (❌), підтвердження (❓)

---

## 📊 Метрики успіху

| Метрика | Ціль | Як виміряти |
|---------|------|-------------|
| Точність кліків | > 95% | Успішні кліки / Всього кліків |
| OCR точність | > 90% | Word accuracy на тестових скріншотах |
| Детекція UI-елементів | > 85% | Знайдені / Всі елементи на тестових сторінках |
| Completion rate сценаріїв | > 80% | Успішні / Всього запусків |
| False positive безпеки | < 5% | Хибні блокування / Всього дій |
| Час відповіді (клік → результат) | < 2с | Середнє по 100 операціям |
| Undo success rate | > 70% | Успішні відкати / Всього спроб |

---

## 🚨 Поточні проблеми та пріоритети (20.04.2026)

> **Критичні баги, що блокують роботу:**

### ✅ Пріоритет #1: LLM повертає пусту відповідь — **ВИРІШЕНО**
**Статус:** ✅ Проблему з LM Studio вирішено — моделі стабільно повертають відповіді

**Рішення:** Коректний формат запиту до /v1/chat/completions, правильна обробка system prompt

### 🔴 Пріоритет #2: Голосове введення до агента (STT інтеграція)
**Симптом:** STT працює окремо, але не передає текст в логіку агента  
**Поточний стан:** `voice_input` є як інструмент, але немає pipeline STT → executor  
**Дії:**
- [ ] Прийом голосових команд в GUI (мікрофон → STT → текст команди)
- [ ] Обробка голосу в реальному часі (streaming STT)
- [ ] Підтвердження розпізнаного тексту перед виконанням
- [ ] Wake word detection ("Окей Марк" або подібне)

### ✅ Пріоритет #3: Валідація GUI інструментів — **ЗАВЕРШЕНО**
**Статус:** ✅ Phase 1-3 протестовані та інтегровані

**Завершено:**
- ✅ `take_screenshot()` — робочий, збереження файлів
- ✅ `mouse_click()` — інтегровано в TOOL_POLICIES
- ✅ `list_windows()` — стабільно повертає список вікон
- ✅ Всі GUI інструменти зареєстровані в executor

---

---

## ⚠️ Ризики та їх мітігація

| Ризик | Ймовірність | Вплив | Мітігація |
|-------|-------------|-------|-----------|
| Антивірус блокує input automation | Середня | Високий | Code signing, whitelist, документація |
| Зміна UI після оновлення програм | Висока | Середній | Adaptive search, профілі з fallback |
| Помилки OCR на нестандартних шрифтах | Середня | Середній | Preprocessing, кілька движків, fallback |
| Випадкові дії в небезпечних місцях | Низька | Критичний | GUI Guardian, sandbox, undo, аудит |
| Зниження продуктивності (скріншоти) | Середня | Низький | mss (швидкий capture), кешування |
| Проблеми з multi-monitor | Середня | Середній | DPI awareness, координати з offset |
| Несумісність з Wine/VM | Висока | Низький | Документація, окремий compatibility layer |

---

## 🔗 Залежності для встановлення

```bash
# Phase 1 — Input & Windows
pip install pyautogui pywin32 psutil

# Phase 2 — Screen Capture
pip install mss Pillow opencv-python

# Phase 3 — OCR
pip install easyocr          # основний движок (GPU-прискорений)
pip install pytesseract      # fallback (потребує Tesseract у PATH)
# або
pip install paddlepaddle paddleocr  # альтернатива easyocr

# Phase 4 — Computer Vision (вже є через Phase 2)
# opencv-python вже встановлено

# Phase 7 — Automation
pip install selenium webdriver-manager  # для браузера
pip install pygetwindow                 # доп. менеджмент вікон

# Office Integration (опційно)
pip install pywin32  # вже є; використовуємо win32com.client
```

---

*Стратегічний план GUI Automation оновлено: 20.04.2026*
*Наступний крок: Phase 7 — Learning & Profiles (`core_app_profiles.py`, `tools_macro_recorder.py`, `logic_task_learner.py`))*