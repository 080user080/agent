"""Сумісний runtime для структурованих результатів інструментів."""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Рівні ризику
SAFE = "safe"                        # Можна виконувати без підтвердження
CONFIRM_REQUIRED = "confirm_required"  # Потрібне підтвердження користувача
BLOCKED = "blocked"                   # Заборонено для planner (але LLM може викликати)

# Категорії інструментів
CATEGORY_FILE = "file"
CATEGORY_CODE = "code"
CATEGORY_SYSTEM = "system"
CATEGORY_BROWSER = "browser"
CATEGORY_MEDIA = "media"
CATEGORY_META = "meta"
CATEGORY_GUI = "gui"  # GUI Automation Phase 1-7

TOOL_POLICIES: Dict[str, Dict[str, Any]] = {
    # --- Безпечні файлові операції (тільки Desktop) ---
    # idempotent=True — функції, які можна кешувати (чисті обчислення/читання)
    "create_file": {"risk": SAFE, "category": CATEGORY_FILE, "description": "Створення txt файлу на Desktop"},
    "edit_file": {"risk": SAFE, "category": CATEGORY_FILE, "description": "Редагування файлу з бекапом"},
    "create_folder": {"risk": SAFE, "category": CATEGORY_FILE, "description": "Створення папки"},
    "search_in_text": {"risk": SAFE, "category": CATEGORY_META, "description": "Пошук у тексті", "idempotent": True},
    "count_words": {"risk": SAFE, "category": CATEGORY_META, "description": "Підрахунок слів", "idempotent": True},

    # --- Python sandbox (безпечний) ---
    # execute_python ідемпотентний тільки без побічних ефектів
    "execute_python": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Виконання Python в пісочниці", "idempotent": True},
    "execute_python_code": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Alias для execute_python", "idempotent": True},
    "execute_python_file": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Виконання файлу з пісочниці"},
    "debug_python_code": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Автовиправлення Python коду"},
    "list_sandbox_scripts": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Список скриптів пісочниці", "idempotent": True},

    # --- Браузер і медіа ---
    "open_browser": {"risk": SAFE, "category": CATEGORY_BROWSER, "description": "Відкриття URL у браузері"},
    "voice_input": {"risk": SAFE, "category": CATEGORY_MEDIA, "description": "Голосовий ввід"},

    # --- Мета-дії ---
    "show_sandbox_status": {"risk": SAFE, "category": CATEGORY_META, "description": "Показати стан пісочниці", "idempotent": True},
    "confirm_action": {"risk": SAFE, "category": CATEGORY_META, "description": "Запит підтвердження"},

    # --- Code tools (читання безпечно) ---
    "read_code_file": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Читання файлу з кодом", "idempotent": True},
    "search_in_code": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Пошук у файлах", "idempotent": True},
    "list_directory": {"risk": SAFE, "category": CATEGORY_FILE, "description": "Вміст директорії", "idempotent": True},
    "git_status": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Git status", "idempotent": True},
    "git_diff": {"risk": SAFE, "category": CATEGORY_CODE, "description": "Git diff", "idempotent": True},

    # --- Системні дії (потрібне підтвердження) ---
    "open_program": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Відкрити програму"},
    "close_program": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Закрити програму"},
    "add_allowed_program": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Додати в whitelist"},
    "enable_auto_confirm": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Увімкнути автопідтвердження"},
    "disable_auto_confirm": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_SYSTEM, "description": "Вимкнути автопідтвердження"},
    "create_skill": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_META, "description": "Створення нової навички"},

    # --- Системні дії (безпечні) ---
    "clear_cache": {"risk": SAFE, "category": CATEGORY_SYSTEM, "description": "Очистити кеш асистента"},

    # --- GUI Automation Phase 1: Миша та клавіатура (безпечні) ---
    "mouse_click": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Клік мишою в координати"},
    "mouse_move": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Перемістити курсор"},
    "mouse_scroll": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Прокрутка мишою"},
    "mouse_drag": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Перетягування drag & drop"},
    "get_mouse_position": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Позиція курсора", "idempotent": True},
    "mouse_click_image": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Клік по зображенню на екрані"},
    "keyboard_press": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Натиснути клавішу"},
    "keyboard_type": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Ввести текст"},
    "keyboard_hotkey": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Комбінація клавіш"},
    "keyboard_hold": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Утримати клавішу"},
    "keyboard_send_special": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Спеціальна клавіша (PrintScreen...)"},
    "clipboard_copy_text": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Копіювати текст у буфер"},
    "clipboard_get_text": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Отримати текст з буфера", "idempotent": True},
    "clipboard_copy_image": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Копіювати зображення у буфер"},

    # --- GUI Automation Phase 1: Вікна Windows (читання безпечно, зміна — підтвердження) ---
    "list_windows": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Список вікон", "idempotent": True},
    "find_window_by_title": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти вікно за заголовком", "idempotent": True},
    "find_window_by_process": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти вікна процесу", "idempotent": True},
    "find_window_by_class": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти вікна за класом", "idempotent": True},
    "get_active_window": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Активне вікно", "idempotent": True},
    "get_window_rect": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Координати вікна", "idempotent": True},
    "is_window_visible": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Чи видиме вікно", "idempotent": True},
    "is_window_minimized": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Чи згорнуте вікно", "idempotent": True},
    "is_window_maximized": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Чи розгорнуте вікно", "idempotent": True},
    "wait_for_window": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Очікувати вікно"},
    "wait_window_close": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Очікувати закриття вікна"},

    # Зміна стану вікон — підтвердження (модифікують систему)
    "activate_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Активувати вікно"},
    "minimize_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Згорнути вікно"},
    "maximize_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Розгорнути вікно"},
    "restore_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відновити вікно"},
    "move_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Перемістити вікно"},
    "resize_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Змінити розмір вікна"},
    "move_resize_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Перемістити та змінити розмір"},
    "center_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відцентрувати вікно"},
    "bring_all_to_top": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Підняти всі вікна процесу"},

    # Небезпечні операції з вікнами
    "close_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Закрити вікно"},
    "hide_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Приховати вікно"},
    "show_window": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Показати вікно"},

    # --- GUI Automation Phase 2: Скріншоти та аналіз екрану (безпечні, ідемпотентні) ---
    "take_screenshot": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Зняти скріншот екрану", "idempotent": True},
    "capture_monitor": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Захопити монітор", "idempotent": True},
    "capture_region": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Захопити область екрану", "idempotent": True},
    "capture_window": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Захопити вікно", "idempotent": True},
    "capture_active_window": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Захопити активне вікно", "idempotent": True},
    "get_screen_size": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Розмір екрану", "idempotent": True},
    "get_monitors_info": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Інформація про монітори", "idempotent": True},
    "get_pixel_color": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Колір пікселя", "idempotent": True},
    "find_image_on_screen": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти зображення на екрані", "idempotent": True},
    "wait_for_image": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Очікувати зображення"},
    "pixel_matches_color": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Перевірити колір пікселя", "idempotent": True},
    "wait_for_color": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Очікувати колір"},
    "clear_screenshot_cache": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Очистити кеш скріншотів"},

    # --- GUI Automation Phase 3: OCR — Розпізнавання тексту (безпечні, ідемпотентні) ---
    "ocr_screen": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Розпізнати текст на екрані", "idempotent": True},
    "ocr_region": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Розпізнати текст в області", "idempotent": True},
    "ocr_window": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Розпізнати текст у вікні", "idempotent": True},
    "ocr_image": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Розпізнати текст на зображенні", "idempotent": True},
    "find_text_on_screen": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти текст на екрані", "idempotent": True},
    "find_all_text_on_screen": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти всі входження тексту", "idempotent": True},
    "click_text": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Знайти текст і клікнути по ньому"},
    "wait_for_text": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Очікувати появи тексту"},
    "ocr_to_string": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Розпізнати текст і повернути рядок", "idempotent": True},

    # --- GUI Automation Phase 4: Computer Vision — Детекція UI-елементів (idempotent) ---
    "find_button_by_image": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти кнопку за зображенням", "idempotent": True},
    "find_icon": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти іконку на екрані", "idempotent": True},
    "find_checkbox": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти чекбокси", "idempotent": True},
    "find_input_field": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти поля вводу", "idempotent": True},
    "find_progress_bar": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти прогрес-бар", "idempotent": True},
    "find_button_by_text": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти кнопку за текстом (OCR+CV)", "idempotent": True},
    "find_label": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти мітку за текстом", "idempotent": True},
    "find_input_near_label": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Знайти поле поруч з міткою", "idempotent": True},
    "is_button_enabled": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Чи кнопка активна", "idempotent": True},
    "is_checkbox_checked": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Чи чекбокс включений", "idempotent": True},
    "get_button_state": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Отримати стан кнопки", "idempotent": True},

    # --- GUI Automation Phase 4: Розпізнавання програм (idempotent) ---
    "detect_active_application": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Визначити активну програму", "idempotent": True},
    "detect_application_state": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Визначити стан програми", "idempotent": True},
    "is_application_ready": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Чи програма готова", "idempotent": True},
    "detect_file_dialog": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Визначити файловий діалог", "idempotent": True},
    "detect_error_dialog": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Визначити діалог помилки", "idempotent": True},
    "detect_context_menu": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Визначити контекстне меню", "idempotent": True},

    # --- GUI Automation Phase 4: Візуальний diff (idempotent) ---
    "capture_baseline": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Зберегти еталонний скріншот"},
    "delete_baseline": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Видалити еталон"},
    "list_baselines": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Список еталонів", "idempotent": True},
    "compare_with_baseline": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Порівняти з еталоном", "idempotent": True},
    "highlight_changes": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Підсвітити зміни", "idempotent": True},
    "wait_for_visual_change": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Очікувати зміну на екрані"},
    "wait_for_visual_stable": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Очікувати стабільності"},

    # --- GUI Automation Phase 5: Smart UI Navigation — Розумна навігація ---
    # Базові UI-дії (потребують підтвердження — це дії)
    "click_element": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Клік по елементу за описом"},
    "type_in_field": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Ввести текст у поле"},
    "select_option": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Вибрати пункт з dropdown"},
    "check_checkbox": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Встановити чекбокс"},
    "select_radio": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Вибрати radio button"},
    "navigate_tabs": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Перейти на вкладку"},
    # Форми (потребують підтвердження)
    "fill_form": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Заповнити форму"},
    "submit_form": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відправити форму"},
    "read_form_values": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Прочитати значення форми", "idempotent": True},
    "validate_form_filled": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Перевірити заповнення форми", "idempotent": True},
    # Меню (потребують підтвердження)
    "open_menu": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відкрити меню"},
    "click_menu_item": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Клік по пункту меню"},
    "open_context_menu": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відкрити контекстне меню"},
    "click_context_item": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Вибрати пункт контекстного меню"},
    "close_menu": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Закрити меню"},
    # Діалоги (потребують підтвердження)
    "handle_dialog": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відповісти на діалог"},
    "dismiss_all_dialogs": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Закрити всі діалоги"},
    # Сценарії (потребують підтвердження — виконують дії)
    "run_scenario": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Виконати сценарій"},
    "run_scenario_from_file": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Виконати сценарій з файлу"},
    "save_scenario": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Зберегти сценарій"},
    "load_scenario": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Завантажити сценарій", "idempotent": True},
    "list_scenarios": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Список сценаріїв", "idempotent": True},
    "delete_scenario": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Видалити сценарій"},
    "validate_scenario": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Перевірити сценарій", "idempotent": True},
    # Вбудовані сценарії (потребують підтвердження)
    "scenario_save_file": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Сценарій: зберегти файл"},
    "scenario_open_file": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Сценарій: відкрити файл"},
    "scenario_save_as": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Сценарій: зберегти як"},
    "scenario_find_in_program": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Сценарій: пошук"},
    "scenario_print": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Сценарій: друк"},
    "scenario_undo_redo": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Сценарій: undo/redo"},
    "scenario_select_all_copy": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Сценарій: виділити все та скопіювати"},

    # --- GUI Automation Phase 5: Context Analyzer — Аналіз контексту (idempotent) ---
    "analyze_current_context": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Проаналізувати поточний контекст UI", "idempotent": True},
    "suggest_next_action": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Запропонувати наступну дію", "idempotent": True},
    "explain_screen": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Отримати текстовий опис екрану", "idempotent": True},
    "detect_user_goal_completion": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Перевірити чи виконана ціль", "idempotent": True},
    "detect_blocker": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Виявити перешкоду", "idempotent": True},
    "get_context_changes": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Отримати зміни в контексті", "idempotent": True},

    # --- GUI Automation Phase 6: Safety, Audit & Undo — Безпека та відкат ---
    # Action Recorder (безпечні, idempotent для читання)
    "record_action": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Записати дію в журнал"},
    "get_recent_actions": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Останні дії з журналу", "idempotent": True},
    "export_session_log": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Експортувати лог сесії", "idempotent": True},
    "generate_action_report": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Звіт по діях", "idempotent": True},
    "search_actions": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Пошук в журналі", "idempotent": True},
    # Undo Manager (потребує підтвердження для відкату)
    "save_snapshot": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Зберегти стан системи"},
    "restore_snapshot": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відновити стан системи"},
    "list_snapshots": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Список snapshots", "idempotent": True},
    "undo_last": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відкатити останні дії"},
    "undo_to_snapshot": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Відкатити до snapshot"},
    "get_undo_stack": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Отримати undo stack", "idempotent": True},
    "clear_undo_stack": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Очистити undo stack"},
    # GUI Guardian (безпечні, idempotent для аналізу)
    "enable_sandbox_mode": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Увімкнути sandbox"},
    "disable_sandbox_mode": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Вимкнути sandbox"},
    "set_allowed_region": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Встановити дозволену зону"},
    "set_allowed_applications": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Whitelist програм"},
    "add_blocked_application": {"risk": CONFIRM_REQUIRED, "category": CATEGORY_GUI, "description": "Додати в blacklist"},
    "assess_risk": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Оцінити ризик дії", "idempotent": True},
    "is_action_allowed": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Перевірити чи дія дозволена", "idempotent": True},
    "preview_action": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Preview дії без виконання", "idempotent": True},
    "simulate_action": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Симулювати дію", "idempotent": True},
    "get_safety_report": {"risk": SAFE, "category": CATEGORY_GUI, "description": "Звіт безпеки", "idempotent": True},
}

# Патерни небезпечних дій у планах (literal substring match, lowercased)
DANGEROUS_PATTERNS: List[str] = [
    # Деструктивне видалення
    "rm -rf",
    "rm -fr",
    "format c:",
    "del /f /s /q",
    "del /q /s",
    "rmdir /s",
    "rd /s /q",
    "vssadmin delete shadows",
    "wbadmin delete",
    "diskpart",
    # Потужний PowerShell (execution-bypass + remote)
    "powershell -enc",
    "powershell -encodedcommand",
    "powershell -nop",
    "invoke-expression",
    "iex (",
    "downloadstring",
    "downloadfile",
    "invoke-webrequest http",
    # Системне керування
    "shutdown /",
    "shutdown -",
    "reg delete",
    "reg add hklm\\software\\microsoft\\windows\\currentversion\\run",
    "schtasks /create",
    "taskkill /f",
    "net user",
    "net localgroup administrators",
    "bcdedit",
    # Віддалене виконання / reverse shell
    "curl http",
    "wget http",
    "nc -e",
    "ncat -e",
    "bash -i",
    "/dev/tcp/",
    "mshta http",
    "bitsadmin /transfer",
    # Credential theft / сканери
    "mimikatz",
    "sekurlsa",
    "procdump lsass",
    "sam.hive",
    "ntds.dit",
    # Обфускація
    " base64 -d",
    "frombase64string",
    "[convert]::frombase64",
    # Ransomware-подібні операції
    "cipher /w",
    "encrypt /",
]

# Regex-патерни для складніших небезпечних дій
DANGEROUS_REGEXES: List[str] = [
    r"\brm\s+-[rf]+\s+/\S*",                    # rm -rf / (у т.ч. -fr, -Rf)
    r"\bdd\s+if=.+of=/dev/",                    # dd if=... of=/dev/sda
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}",        # fork bomb
    r"chmod\s+-?R?\s*777\s+/",                  # chmod 777 /
    r"\bkill\s+-9\s+1\b",                       # kill -9 1 (init)
    r"format\s+[a-z]:\s*/",                     # format X: /
]

# Патерни двозначних дій (потрібна додаткова обережність)
AMBIGUOUS_PATTERNS: List[str] = [
    # Системні шляхи Windows
    "system32",
    "syswow64",
    "windows\\",
    "windows/",
    "program files",
    "programdata",
    "appdata",
    "startup",
    # Критичні файли
    "hosts",
    "bootmgr",
    "boot.ini",
    # Приховані конфіги зі credentials
    ".ssh/id_",
    ".git-credentials",
    ".aws/credentials",
    ".npmrc",
    ".env",
    "wp-config.php",
    "secrets.",
    # Security-sensitive
    "lsass",
    "sam ",
    # Широкі sudo/admin
    "sudo rm",
    "sudo chmod",
    "runas ",
]

# Regex для двозначних шляхів (захоплює шляхи з різними роздільниками)
AMBIGUOUS_REGEXES: List[str] = [
    r"c:[\\/]windows[\\/]",
    r"c:[\\/]program\s*files",
    r"/etc/(passwd|shadow|sudoers)",
    r"~/\.\w+rc",                               # ~/.bashrc, ~/.zshrc тощо
]


class AuditLog:
    """Журнал аудиту виконаних дій."""

    def __init__(self, log_dir: Optional[Path] = None, max_entries: int = 1000):
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True, parents=True)
        self.log_file = log_dir / "audit.jsonl"
        self.max_entries = max_entries
        self._entries: List[Dict[str, Any]] = []

    def log(self, action: str, params: Dict[str, Any], result: Dict[str, Any], risk: str) -> None:
        """Записати дію в аудит."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "risk": risk,
            "ok": result.get("ok"),
            "error": result.get("error"),
            "params_summary": self._summarize_params(params),
        }
        self._entries.append(entry)

        # Записуємо у файл
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Не ламаємо виконання через проблеми з логом

        # Обмежуємо кількість в пам'яті
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

    def _summarize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Скоротити великі параметри (напр. code) для логу."""
        summary = {}
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 200:
                summary[key] = value[:200] + f"... [{len(value)} chars]"
            else:
                summary[key] = value
        return summary

    def get_recent(self, count: int = 10) -> List[Dict[str, Any]]:
        """Отримати останні записи з аудиту."""
        return self._entries[-count:]


# Глобальний аудит
_audit = AuditLog()


def get_audit_log() -> AuditLog:
    """Отримати глобальний аудит."""
    return _audit


def check_dangerous_content(content: str) -> Optional[str]:
    """Перевірити текст на небезпечні патерни. Повертає знайдений патерн або None.

    Перевіряє (1) літеральні substring та (2) регулярні вирази.
    """
    if not content:
        return None
    content_lower = content.lower()
    # Літеральні substring
    for pattern in DANGEROUS_PATTERNS:
        if pattern in content_lower:
            return pattern
    # Regex
    for rx in DANGEROUS_REGEXES:
        m = re.search(rx, content_lower, flags=re.IGNORECASE)
        if m:
            return m.group(0)
    return None


def check_ambiguous_content(content: str) -> Optional[str]:
    """Перевірити текст на двозначні патерни (літеральні + regex)."""
    if not content:
        return None
    content_lower = content.lower()
    for pattern in AMBIGUOUS_PATTERNS:
        if pattern in content_lower:
            return pattern
    for rx in AMBIGUOUS_REGEXES:
        m = re.search(rx, content_lower, flags=re.IGNORECASE)
        if m:
            return m.group(0)
    return None


def check_dangerous_content_full(content: str) -> Optional[Tuple[str, str]]:
    """Як check_dangerous_content, але повертає (pattern, kind) де kind='literal'|'regex'."""
    if not content:
        return None
    content_lower = content.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in content_lower:
            return (pattern, "literal")
    for rx in DANGEROUS_REGEXES:
        m = re.search(rx, content_lower, flags=re.IGNORECASE)
        if m:
            return (m.group(0), "regex")
    return None


# Ключі параметрів інструментів, що містять команду/код/шлях — їх треба перевіряти
_SENSITIVE_PARAM_KEYS = {
    "code", "script", "command", "cmd", "powershell",
    "filepath", "file_path", "path", "filename", "target", "dest", "destination",
    "url", "pattern", "query",
}


def check_params_safety(action: str, params: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Перевірити параметри виклику інструменту на небезпечні/двозначні патерни.

    Повертає dict з полями {kind, pattern, param} або None якщо все чисто.
    kind='dangerous' або 'ambiguous'.
    """
    if not isinstance(params, dict):
        return None
    for key, value in params.items():
        if key.lower() not in _SENSITIVE_PARAM_KEYS:
            continue
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        danger = check_dangerous_content(text)
        if danger:
            return {"kind": "dangerous", "pattern": danger, "param": key}
        ambig = check_ambiguous_content(text)
        if ambig:
            return {"kind": "ambiguous", "pattern": ambig, "param": key}
    return None


def make_tool_result(
    ok: bool,
    message: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    needs_confirmation: bool = False,
    retryable: bool = False,
) -> Dict[str, Any]:
    """Побудувати єдиний формат результату інструмента."""
    return {
        "ok": ok,
        "message": message,
        "data": data or {},
        "error": error,
        "needs_confirmation": needs_confirmation,
        "retryable": retryable,
    }


def normalize_tool_result(raw_result: Any) -> Dict[str, Any]:
    """Звести довільний результат до єдиного формату."""
    if isinstance(raw_result, dict) and "ok" in raw_result and "message" in raw_result:
        return {
            "ok": bool(raw_result.get("ok")),
            "message": str(raw_result.get("message", "")),
            "data": raw_result.get("data", {}) or {},
            "error": raw_result.get("error"),
            "needs_confirmation": bool(raw_result.get("needs_confirmation", False)),
            "retryable": bool(raw_result.get("retryable", False)),
        }

    if isinstance(raw_result, dict):
        status = str(raw_result.get("status", "")).lower()
        ok = status in {"confirmed", "ok", "success"}
        needs_confirmation = status == "timeout"
        message = raw_result.get("message")
        if not message:
            if status:
                message = f"Статус: {status}"
            else:
                message = str(raw_result)
        return make_tool_result(
            ok=ok,
            message=message,
            data=raw_result,
            error=None if ok else message,
            needs_confirmation=needs_confirmation,
            retryable=not ok,
        )

    text = str(raw_result)
    ok = not text.startswith("❌") and "помилка" not in text.lower()
    return make_tool_result(
        ok=ok,
        message=text,
        data={},
        error=None if ok else text,
        retryable=not ok,
    )


def get_tool_policy(action: str) -> Dict[str, Any]:
    """Отримати політику інструмента."""
    return TOOL_POLICIES.get(action, {"risk": BLOCKED})


def get_tool_risk(action: str) -> str:
    """Отримати risk-level для інструмента."""
    return get_tool_policy(action).get("risk", BLOCKED)
