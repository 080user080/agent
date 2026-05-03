# GUI Автоматизація — Документація

## Дата: 2026-05-03
## Статус: ✅ Робоче рішення знайдено

---

## Проблема

При автоматизованому тестуванні GUI PyQt6 асистента МАРК виникали проблеми з вставкою тексту в поле вводу. Стандартні методи (`keyboard_type`, `pyautogui.write`) обрізали текст або не працювали з кирилицею.

### Симптоми:
- `keyboard_type(text="проаналізуй код d:\\Python\\agent")` → GUI отримував `:\` замість повного тексту
- `GlobalVoiceInput._insert_text()` (clipboard + Ctrl+V) → текст вставлявся, але не попадав в поле вводу PyQt6
- Проблема з фокусом: `focus_error: "(5, 'SetFocus', 'Access is denied.')"`

---

## Робоче Рішення

### GlobalVoiceInput._insert_text_with_script

**Файл:** `functions/global_voice_input.py:513-551`

**Принцип роботи:**
1. Копіює текст в буфер обміну (`clipboard_copy_text`)
2. Натискає `Shift+F10` — запускає зовнішній скрипт (AutoIt/AutoHotkey), який вставляє текст
3. Чекає 2 секунди
4. Очищає буфер обміну

**Переваги:**
- Обходить обмеження PyQt6 обробки подій клавіатури
- Працює з будь-яким вікном (включаючи Qt6110QWindowIcon)
- Підтримує кирилицю
- Не потребує фокусу на конкретному елементі

---

## Тестові Файли

### test_aaa_osnova2_vstavka_GVI.py
**Призначення:** Тест вставки тексту через GlobalVoiceInput._insert_text_with_script

**Робочий потік:**
```
1. Очистити логи
2. Запустити агента (subprocess.Popen)
3. Зачекати 6 секунд ініціалізації
4. Активувати вікно (activate_window_by_title)
5. Зачекати 1 секунду
6. Вставити текст (gvi._insert_text_with_script)
7. Зачекати 2 секунди
8. Натиснути Enter (keyboard_press)
9. Зачекати 45 секунд
10. Закрити агента
11. Прочитати логи
```

**Ключовий код:**
```python
from functions.global_voice_input import GlobalVoiceInput
from functions.tools_mouse_keyboard import keyboard_press

gvi = GlobalVoiceInput()
gvi._last_window_hwnd = result.get('hwnd')
gvi._last_window_title = result.get('title')

insert_result = gvi._insert_text_with_script("проаналізуй код d:/Python/agent")
keyboard_press(key="Enter")
```

### test_osnova2.py
**Призначення:** Тест виконання різних завдань через GUI

**Завдання для тестування:**
1. `"аналізуй екран"` — аналіз екрану (take_screenshot + ocr_screen)
2. `"проаналізуй код d:/Python/agent"` — аналіз коду
3. `"перелік файлів в d:/Python/agent"` — перелік файлів

---

## Вимоги

### Python Залежності
```bash
pip install pyperclip
pip install pynput  # опціонально, для hotkey
```

### Зовнішній Скрипт
Для роботи `_insert_text_with_script` потрібен зовнішній скрипт (AutoIt/AutoHotkey), який:
1. Чекає на натискання Shift+F10
2. Вставляє текст з буферу обміну в активне вікно

Скрипт має бути запущений окремо або як частина системи.

---

## Логування

**Розташування:** `d:\Python\agent\debug_logs\`

**Файли:**
- `main_window.log` — повідомлення з main_window.py
- `_on_message.log` — повідомлення з _on_message callback

**Формат:**
```
[YYYY-MM-DD HH:MM:SS] main_window add_message: sender=assistant, message=...
[YYYY-MM-DD HH:MM:SS] _on_message add_message: msg_type=add_message, sender=user, text=...
```

---

## Результати Тестування

### Завдання 1: "аналізуй екран"
```
✅ Користувач: "аналізуй екран"
✅ Асистент: "Аналіз екрану завершено: активне вікно 'МАРК — Асистент (PyQt6)' успішно ідентифіковано..."
✅ Agent loop завершено: 3 кроків за 6.3с
```

### Завдання 2: "проаналізуй код d:/Python/agent"
```
✅ Користувач: "проаналізуй код d:/Python/agent"
✅ Асистент: "Аналіз коду в d:/Python/agent завершено. Проєкт 'МАРК' спрямований на створення агента..."
✅ Agent loop завершено: 4 кроків за 4.9с
```

### Завдання 3: "перелік файлів в d:/Python/agent"
```
✅ Користувач: "перелік файлів в d:/Python/agent"
✅ Асистент: "Вміст d:/Python/agent: .git/, .github/, .gitignore, ..."
✅ list_directory виконано за 0.69с
```

---

## Помилки та Обхідні Шляхи

### Помилка: Текст обрізається при вставці
**Причина:** PyQt6 QTextInput обробляє події клавіатури по-іншому ніж Tkinter
**Рішення:** Використовувати `_insert_text_with_script` замість `keyboard_type`

### Помилка: Access is denied при SetFocus
**Причина:** Windows блокує встановлення фокусу на вікно з іншого процесу
**Рішення:** Не потрібен — `_insert_text_with_script` не залежить від фокусу

### Помилка: pynput не встановлено
**Причина:** Залежність не встановлена в середовищі
**Вплив:** Не критичний — hotkey не потрібен для тестів
**Рішення:** `pip install pynput` (опціонально)

---

## Використання

### Запуск тесту:
```bash
cd d:\Python\agent
python TEST_GUI\test_aaa_osnova2_vstavka_GVI.py
```

### Перевірка результатів:
```bash
cd d:\Python\agent\debug_logs
cat main_window.log
cat _on_message.log
```

---

## Архітектура

### Потік Даних
```
Тест → activate_window_by_title → GUI Window (hwnd)
     → GlobalVoiceInput._insert_text_with_script
       → clipboard_copy_text → Буфер обміну
       → pyautogui.hotkey('shift', 'f10') → Зовнішній скрипт
       → Зовнішній скрипт вставляє текст в GUI
     → keyboard_press('Enter') → GUI обробляє команду
     → AgentLoop → LLM → Tools → GUI Queue → Chat
```

### Компоненти
- `functions/global_voice_input.py` — GlobalVoiceInput клас
- `functions/tools_mouse_keyboard.py` — keyboard_press, keyboard_type
- `functions/aaa_voice_input.py` — activate_window_by_title
- `main.py` — AssistantCore, run_agent_loop
- `core_gui_pyqt6/main_window.py` — GUI чат

---

## Наступні Кроки

1. **Автоматичний запуск зовнішнього скрипта** — інтегрувати AutoIt/AHK скрипт в пайплайн
2. **Паралельне виконання** — запускати кілька завдань одночасно
3. **CI/CD інтеграція** — додати в GitHub Actions/GitLab CI
4. **Тести для інших модулів** — додати тести для Browser CDP, UIA, Vision-LM

---

## Автор

MAРК — Асистент для автоматизації роботи з ПК
Версія: PyQt6 MVP
Дата документації: 2026-05-03
