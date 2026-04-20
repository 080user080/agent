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

### ⏳ Не дороблено / В процесі

- Голосовий ввід — індикатор мікрофона в GUI (відкладено через STT)
- Planner не робить повне перепланування дерева
- GUI Automation — не розпочато (Phase 1–7, детальний план нижче)

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
| 1 | Базова автоматизація GUI | 🔴 Не розпочато | 🔥 Критичний | 2–3 тижні |
| 2 | Скріншоти та аналіз екрану | 🔴 Не розпочато | 🔥 Критичний | 2–3 тижні |
| 3 | OCR — розпізнавання тексту | 🔴 Не розпочато | 🔥 Критичний | 2–3 тижні |
| 4 | Комп'ютерний зір (CV) | 🔴 Не розпочато | 🔴 Високий | 3–4 тижні |
| 5 | Розумна навігація по UI | 🔴 Не розпочато | 🔴 Високий | 3–4 тижні |
| 6 | Безпека та журнал дій | 🔴 Не розпочато | 🔴 Високий | 2–3 тижні |
| 7 | Навчання та адаптація | 🔴 Не розпочато | 🟡 Середній | 4–6 тижнів |

---

## 📦 Phase 1: Базова автоматизація GUI (Core Input Control)

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🔥 Критичний | **Термін:** 2–3 тижні

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

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🔥 Критичний | **Термін:** 2–3 тижні

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
- [ ] `wait_for_change(region, timeout=10)` → `bool` — очікати зміни в регіоні

#### Аналіз кольорів та змін
- [ ] `pixel_matches_color(x, y, color, tolerance=10)` → `bool`
- [ ] `wait_for_color(x, y, color, timeout=10)` → `bool`
- [ ] `detect_loading_indicator(region=None)` → `bool` — спінер / progress bar
- [ ] `detect_modal_dialog()` → `bool` — чи є модальне вікно поверх основного

### 2.2 Кешування скріншотів

- [ ] `ScreenCache` клас — зберігає останні N скріншотів у пам'яті
- [ ] Автоматичне збереження "before/after" для критичних дій
- [ ] Очищення кешу через `clear_cache` / `aaa_system.py`

### 2.3 Тести Phase 2

- [ ] `tests/test_tools_screen_capture.py` — mock mss, перевірка PIL операцій
- [ ] Тест template matching з синтетичними зображеннями
- [ ] Тест `capture_window` для мінімізованого вікна

---

## 🔤 Phase 3: OCR — Розпізнавання тексту на екрані

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🔥 Критичний | **Термін:** 2–3 тижні

**Мета:** Агент читає текст з будь-якого місця екрану — кнопок, меню, повідомлень, таблиць.

**Залежності:** `easyocr` або `paddleocr` (основний), `pytesseract` (fallback)

### 3.1 Модуль `tools_ocr.py` — Розпізнавання тексту

#### Базові функції
- [ ] `ocr_screen(languages=['uk', 'en'])` → `[{text, confidence, bbox}]` — весь екран
- [ ] `ocr_region(x, y, width, height, languages=['uk', 'en'])` → `[{text, confidence, bbox}]`
- [ ] `ocr_window(hwnd, languages=['uk', 'en'])` → `[{text, confidence, bbox}]` — вікно цілком
- [ ] `ocr_image(image_path, languages=['uk', 'en'])` → `[{text, confidence, bbox}]`
- [ ] `ocr_to_string(region=None)` → `str` — весь текст як рядок (для простих запитів)

#### Пошук тексту на екрані
- [ ] `find_text_on_screen(text, case_sensitive=False, confidence=0.7)` → `{x, y, width, height} | None`
- [ ] `find_all_text_on_screen(text)` → `[{x, y, width, height, matched_text}]`
- [ ] `find_text_in_region(text, x, y, width, height)` → `{x, y} | None`
- [ ] `click_text(text, offset_x=0, offset_y=0)` → `bool` — знайти текст і клікнути по ньому
- [ ] `wait_for_text(text, region=None, timeout=10)` → `bool`

#### Структурований OCR
- [ ] `ocr_table(region)` → `[[str]]` — розпізнати таблицю як 2D масив
- [ ] `ocr_form_fields(region)` → `[{label, value, type}]` — поля форми (лейбл + значення)
- [ ] `ocr_menu(hwnd)` → `[str]` — пункти меню
- [ ] `read_status_bar(hwnd)` → `str` — текст статус-бару програми
- [ ] `read_title_bar(hwnd)` → `str` — заголовок вікна

#### Якість та постобробка
- [ ] `preprocess_for_ocr(image)` → `PIL.Image` — покращення зображення (контраст, різкість, масштаб)
- [ ] `correct_ocr_errors(text)` → `str` — базова корекція типових OCR-помилок (0/O, 1/l, ...)
- [ ] `get_ocr_engine_info()` → `{engine, languages, version}` — інформація про поточний двигун

### 3.2 Модуль `logic_text_reader.py` — Контекстне читання тексту

- [ ] `read_screen_context()` → `str` — загальний опис того, що на екрані (для LLM)
- [ ] `read_error_messages()` → `[str]` — всі повідомлення про помилки на екрані
- [ ] `read_notifications()` → `[str]` — спливаючі сповіщення
- [ ] `read_dialog_content(hwnd=None)` → `{title, message, buttons}` — вміст діалогового вікна
- [ ] `read_selected_text()` → `str` — виділений текст (через Ctrl+C)
- [ ] `describe_screen()` → `str` — LLM-опис екрану на основі OCR

### 3.3 Тести Phase 3

- [ ] `tests/test_tools_ocr.py` — синтетичні зображення з текстом, перевірка точності
- [ ] `tests/test_logic_text_reader.py` — mock OCR, перевірка парсингу діалогів
- [ ] Benchmark: точність OCR на різних шрифтах і фонах

---

## 👁️ Phase 4: Комп'ютерний зір (Computer Vision)

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🔴 Високий | **Термін:** 3–4 тижні

**Мета:** Агент не просто читає текст, але й **розуміє** інтерфейс — знаходить кнопки, поля, іконки, визначає стан елементів.

**Залежності:** `opencv-python`, `Pillow`, опційно `ultralytics` (YOLO) або `detectron2`

### 4.1 Модуль `tools_ui_detector.py` — Детекція UI-елементів

#### Template matching (без ML)
- [ ] `find_button_by_image(template_path, confidence=0.8)` → `{x, y, width, height} | None`
- [ ] `find_icon(icon_name_or_path, confidence=0.8)` → `{x, y} | None`
- [ ] `find_checkbox(region=None)` → `[{x, y, checked: bool}]`
- [ ] `find_radio_button(region=None)` → `[{x, y, selected: bool}]`
- [ ] `find_input_field(region=None)` → `[{x, y, width, height}]`
- [ ] `find_progress_bar(region=None)` → `{x, y, width, height, percent: float} | None`
- [ ] `find_scrollbar(region=None)` → `{x, y, orientation, position: float} | None`

#### Комбінований OCR + CV пошук
- [ ] `find_button_by_text(text, region=None, confidence=0.7)` → `{x, y, center_x, center_y} | None`
- [ ] `find_label(text, region=None)` → `{x, y} | None`
- [ ] `find_input_near_label(label_text, region=None)` → `{x, y, width, height} | None`
- [ ] `find_menu_item(menu_path_list)` → `{x, y} | None` — напр. `["Файл", "Відкрити"]`
- [ ] `find_tab(tab_name, region=None)` → `{x, y} | None`
- [ ] `find_dropdown(label_text=None, region=None)` → `{x, y, width, height} | None`

#### Аналіз стану елементів
- [ ] `is_button_enabled(x, y, width, height)` → `bool` — чи активна кнопка (за кольором)
- [ ] `is_checkbox_checked(x, y)` → `bool`
- [ ] `is_input_focused(x, y)` → `bool`
- [ ] `get_button_state(x, y)` → `"normal" | "hovered" | "pressed" | "disabled"`
- [ ] `detect_cursor_type()` → `"arrow" | "hand" | "text" | "wait" | "resize" | ...`

### 4.2 Модуль `tools_app_recognizer.py` — Розпізнавання програм

- [ ] `detect_active_application()` → `{name, type, confidence}` — яка програма відкрита
- [ ] `detect_application_state()` → `{state: "idle"|"loading"|"error"|"dialog", details}`
- [ ] `is_application_ready(hwnd)` → `bool` — чи закінчила програма завантаження
- [ ] `detect_file_dialog()` → `{type: "open"|"save", current_path, title} | None`
- [ ] `detect_error_dialog()` → `{title, message, buttons} | None`
- [ ] `detect_context_menu()` → `{items: [str], positions: [{x, y}]} | None`
- [ ] `get_application_profile(app_name)` → `{known_elements, common_workflows}` — профіль програми

### 4.3 Модуль `tools_visual_diff.py` — Порівняння станів екрану

- [ ] `capture_baseline(name)` — зберегти еталонний скріншот
- [ ] `compare_with_baseline(name)` → `{changed: bool, diff_regions: [{x, y, w, h}], diff_percent: float}`
- [ ] `highlight_changes(before, after)` → `PIL.Image` — зображення з підсвіченими змінами
- [ ] `wait_for_visual_change(region, timeout=10)` → `bool` — очікувати будь-яку зміну
- [ ] `wait_for_visual_stable(region, stable_time=1.0, timeout=15)` → `bool` — очікувати стабільності

### 4.4 Тести Phase 4

- [ ] `tests/test_tools_ui_detector.py` — синтетичні зображення UI-елементів
- [ ] `tests/test_tools_app_recognizer.py` — mock скріншоти відомих програм
- [ ] `tests/test_tools_visual_diff.py` — синтетичні "до/після" зображення

---

## 🧠 Phase 5: Розумна навігація по UI (Smart UI Navigation)

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🔴 Високий | **Термін:** 3–4 тижні

**Мета:** Агент може виконувати складні UI-сценарії автономно: заповнити форму, пройти wizard, відповісти на діалог.

### 5.1 Модуль `logic_ui_navigator.py` — Інтелектуальна навігація

#### Базові UI-дії
- [ ] `click_element(description)` → `bool` — клік за описом ("кнопка OK", "поле пошуку")
- [ ] `type_in_field(field_description, text)` → `bool` — ввести текст у поле
- [ ] `select_option(dropdown_description, option_text)` → `bool` — вибрати пункт з dropdown
- [ ] `check_checkbox(label, state=True)` → `bool` — встановити чекбокс
- [ ] `select_radio(label)` → `bool` — вибрати radio button
- [ ] `navigate_tabs(tab_name)` → `bool` — перейти на вкладку

#### Форми та wizard
- [ ] `fill_form(field_dict)` — заповнити форму: `{"Ім'я": "Іван", "Email": "ivan@test.com"}`
- [ ] `submit_form(submit_button_text="OK")` → `bool`
- [ ] `navigate_wizard(steps_dict)` — пройти багатосторінковий wizard
- [ ] `read_form_values()` → `{field_name: value}` — прочитати поточні значення форми
- [ ] `validate_form_filled(required_fields)` → `{valid: bool, missing: [str]}`

#### Меню та контекстні меню
- [ ] `open_menu(menu_name)` → `bool` — відкрити пункт меню (File, Edit, ...)
- [ ] `click_menu_item(path_list)` → `bool` — клік по пункту: `["Файл", "Зберегти як..."]`
- [ ] `open_context_menu(x, y)` → `bool` — відкрити контекстне меню
- [ ] `click_context_item(item_text)` → `bool` — вибрати пункт контекстного меню
- [ ] `close_menu()` → `bool` — закрити відкрите меню (Escape)

#### Діалоги
- [ ] `handle_dialog(expected_text=None, action="ok")` → `bool` — відповісти на діалог
- [ ] `dismiss_all_dialogs(timeout=5)` — закрити всі модальні вікна
- [ ] `wait_and_handle_dialog(expected_text, action, timeout=10)` → `bool`
- [ ] `read_and_handle_dialog()` → `{text, action_taken}` — прочитати і автоматично відповісти

### 5.2 Модуль `logic_scenario_runner.py` — Сценарії автоматизації

#### Визначення та виконання сценаріїв
- [ ] `ScenarioStep` — клас кроку: `{action, params, verify, on_fail}`
- [ ] `Scenario` — клас сценарію: список кроків із умовами
- [ ] `run_scenario(scenario)` → `{success, steps_completed, error}`
- [ ] `run_scenario_from_file(path)` — завантажити і виконати JSON-сценарій

#### Вбудовані типові сценарії
- [ ] `scenario_save_file(program_hwnd)` — зберегти файл (Ctrl+S, обробка діалогу)
- [ ] `scenario_open_file(program_hwnd, file_path)` — відкрити файл (Ctrl+O, навігація)
- [ ] `scenario_save_as(program_hwnd, save_path)` — зберегти як (Ctrl+Shift+S)
- [ ] `scenario_find_in_program(program_hwnd, search_text)` — пошук в програмі (Ctrl+F)
- [ ] `scenario_print(program_hwnd)` — друк (Ctrl+P, OK)
- [ ] `scenario_undo_redo(program_hwnd, action='undo', count=1)` — undo/redo
- [ ] `scenario_select_all_copy(program_hwnd)` → `str` — виділити все і скопіювати
- [ ] `scenario_login(url, username, password)` — авторизація на веб-сторінці

### 5.3 Модуль `logic_context_analyzer.py` — Аналіз контексту екрану

- [ ] `analyze_current_context()` → `{app, state, available_actions, warnings}`
- [ ] `suggest_next_action(goal)` → `{action, params, confidence}` — що зробити далі
- [ ] `explain_screen()` → `str` — LLM-опис: "Відкрита програма X, в ній діалог Y з кнопками A і B"
- [ ] `detect_user_goal_completion(goal_description)` → `bool` — чи виконана ціль
- [ ] `detect_blocker()` → `{type, description, suggested_fix} | None` — що заважає виконанню

### 5.4 Тести Phase 5

- [ ] `tests/test_logic_ui_navigator.py` — mock Phase 1-4 модулі
- [ ] `tests/test_logic_scenario_runner.py` — mock сценарії
- [ ] E2E тест: відкрити Notepad → заповнити форму → зберегти → закрити

---

## 🛡️ Phase 6: Безпека, Аудит та Відкат дій

**Статус:** 🔴 Не розпочато | **Пріоритет:** 🔴 Високий | **Термін:** 2–3 тижні

**Мета:** Гарантувати безпечну роботу агента з реальним UI — ніяких неочікуваних дій, журнал усього, можливість відкату.

### 6.1 Модуль `core_action_recorder.py` — Журнал GUI-дій

#### Запис дій
- [ ] `ActionRecord` датаклас: `{timestamp, action_type, params, screenshot_before, screenshot_after, result}`
- [ ] `ActionRecorder` клас — singleton, автозапис усіх GUI-дій
- [ ] Автоматичний скріншот до/після кожної дії (зберігається у `logs/screenshots/`)
- [ ] Запис у `logs/gui_actions.jsonl` (JSONL-формат для зручного парсингу)
- [ ] Ліміт зберігання: налаштований у `config.py` (за замовчуванням 500 записів / 7 днів)

#### Перегляд та експорт
- [ ] `get_recent_actions(count=10)` → `[ActionRecord]`
- [ ] `export_session_log(format='json')` → `str` — повний лог сесії
- [ ] `generate_action_report()` → `str` — читабельний звіт для користувача
- [ ] `search_actions(filter_dict)` → `[ActionRecord]` — пошук за типом дії / часом / програмою

### 6.2 Модуль `core_undo_manager.py` — Система відкату дій

#### Стани та snapshots
- [ ] `StateSnapshot` — snapshot стану: `{timestamp, screenshot, clipboard, active_window}`
- [ ] `save_snapshot(label)` — зберегти поточний стан перед небезпечною операцією
- [ ] `restore_snapshot(snapshot_id)` → `bool` — спробувати відновити стан
- [ ] `list_snapshots()` → `[{id, label, timestamp}]`

#### Undo логіка
- [ ] `UndoAction` — клас, що описує зворотну дію: `{action_type, undo_steps}`
- [ ] `register_undoable(action, undo_fn)` — зареєструвати відкат для дії
- [ ] `undo_last(count=1)` → `{success, actions_undone, errors}`
- [ ] `undo_to_snapshot(snapshot_id)` → `bool`
- [ ] Підтримка undo для: введення тексту (Delete), переміщення файлів (move назад), закриття вікон (reopen)
- [ ] Обмеження: дії без undo (відправка email, видалення без кошика) позначаються як `irreversible=True`

### 6.3 Модуль `core_gui_guardian.py` — Захист від небезпечних дій

#### Рівні ризику GUI-дій
- [ ] `GUI_RISK_LOW` — без підтвердження (клік по відомих кнопках, введення тексту)
- [ ] `GUI_RISK_MEDIUM` — підтвердження у статус-барі + 5-секундний відлік
- [ ] `GUI_RISK_HIGH` — явне підтвердження через GUI (кнопки ТАК/НІ)
- [ ] `GUI_RISK_CRITICAL` — заблоковано + пояснення причини

#### Небезпечні GUI-дії (критичний ризик)
- [ ] Клік по "Видалити" / "Delete" / "Remove" без підтвердження
- [ ] Клік по "Format" / "Erase" / "Wipe"
- [ ] Закриття вікна зі незбереженими змінами
- [ ] Відправка даних (кнопки "Send", "Submit", "Publish")
- [ ] Дії в системних вікнах (UAC, диспетчер задач, реєстр)
- [ ] Зміна системних налаштувань (Control Panel, мережеві налаштування)

#### Sandbox режим
- [ ] `enable_sandbox_mode()` — тільки безпечні дії, блокування ризикових
- [ ] `set_allowed_region(x, y, width, height)` — обмежити дії до регіону екрану
- [ ] `set_allowed_applications([hwnd])` — дозволити дії тільки у вказаних вікнах
- [ ] `preview_action(action, params)` → `str` — опис що буде зроблено (без виконання)
- [ ] `simulate_action(action, params)` → `str` — "сухий" прогін (логування без дії)

### 6.4 Оновлення TOOL_POLICIES

- [ ] Додати `GUI_RISK_*` константи поруч із `SAFE / CONFIRM_REQUIRED / BLOCKED`
- [ ] Розширити `core_tool_runtime.py` перевіркою GUI ризиків
- [ ] Додати GUI-дії до `DANGEROUS_PATTERNS` та `AMBIGUOUS_PATTERNS`
- [ ] Інтегрувати `ActionRecorder` у `execute_function` автоматично

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

## 🗓️ Пріоритет виконання

```
Phase 1 (Input Control)  ──┐
Phase 2 (Screen Capture) ──┤── Паралельно → основа для всього
Phase 3 (OCR)            ──┘

Phase 4 (CV)             ──┐
Phase 6 (Safety)         ──┤── Паралельно → після Phase 1-3
                           ┘

Phase 5 (Smart Nav)      ──── Після Phase 1-4

Phase 7 (Learning)       ──── Після Phase 1-6

Browser / Office         ──── Паралельно з будь-якою фазою
```

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
*Наступний крок: розпочати Phase 1 — `tools_mouse_keyboard.py` та `tools_window_manager.py`*