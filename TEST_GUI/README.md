# GUI Автоматизація — Документація

## Дата: 2026-05-08
## Статус: ✅ Актуальна версія

---

## Огляд

Папка `TEST_GUI` містить актуальні тести для перевірки функціональності вставки тексту, голосового введення та інтеграції GUI асистента МАРК.

**⚠️ Критичні компоненти:** Логіка вставки тексту в `global_voice_input.py` та `tools_mouse_keyboard.py` не повинна змінюватися без узгодження. Див. README.md в корені проекту.

---

## Актуальні Тести (10 файлів)

### 1. test_insert_notepad.py
**Призначення:** Тест вставки тексту в Windows Notepad через `insert_text_smart`

**Метод вставки:** SendInput Unicode (для Notepad Win11)

**Запуск:**
```bash
python TEST_GUI\test_insert_notepad.py
```

---

### 2. test_insert_text_smart.py
**Призначення:** Тест вставки тексту в PyQt6 QTextEdit через `insert_text_smart`

**Метод вставки:** Ctrl+V (Win32 API) для не-ASCII символів, SendInput Unicode для ASCII

**Запуск:**
```bash
python TEST_GUI\test_insert_text_smart.py
```

---

### 3. test_aaa_osnova2_vstavka_GVI.py
**Призначення:** Тест вставки тексту через GlobalVoiceInput для GUI автоматизації

**Метод вставки:** SendInput Unicode / WM_PASTE / Ctrl+V (адаптивний)

**Запуск:**
```bash
python TEST_GUI\test_aaa_osnova2_vstavka_GVI.py
```

---

### 4. test_mic_button_voice_input.py
**Призначення:** Тест voice_input через кнопку мікрофона в GUI

**Перевіряє:** Кнопка 🎤 → STT розпізнавання → вставка тексту

**Запуск:**
```bash
python TEST_GUI\test_mic_button_voice_input.py
```

---

### 5. test_stt_hotkey.py
**Призначення:** Тест STT та комбінації клавіш Ctrl+F9

**Перевіряє:** Hotkey → STT розпізнавання → вставка тексту

**Запуск:**
```bash
python TEST_GUI\test_stt_hotkey.py
```

---

### 6. test_global_voice.py
**Призначення:** Діагностичний скрипт для глобального голосового введення

**Перевіряє:** Налаштування GLOBAL_VOICE_ENABLED, GLOBAL_VOICE_HOTKEY

**Запуск:**
```bash
python TEST_GUI\test_global_voice.py
```

---

### 7. test_debug_loop_methodology.py
**Призначення:** Демонстрація Debug-Loop методології

**Тип:** Документаційний приклад логування

**Запуск:**
```bash
python TEST_GUI\test_debug_loop_methodology.py
```

---

### 8. test_tray_icon.py
**Призначення:** Тест VoiceTrayIcon

**Перевіряє:** Статуси tray icon (IDLE, RECORDING, PROCESSING, ERROR)

**Запуск:**
```bash
python TEST_GUI\test_tray_icon.py
```

---

### 9. test_agent_loop_chat.py
**Призначення:** Тест відображення повідомлень в GUI чаті при запуску AgentLoop

**Перевіряє:** AgentLoop → GUI Queue → Chat

**Запуск:**
```bash
python TEST_GUI\test_agent_loop_chat.py
```

---

### 10. test_osnova2.py
**Призначення:** Тест виконання різних завдань через GUI

**Завдання для тестування:**
1. `"аналізуй екран"` — аналіз екрану (take_screenshot + ocr_screen)
2. `"проаналізуй код d:/Python/agent"` — аналіз коду
3. `"перелік файлів в d:/Python/agent"` — перелік файлів

**Запуск:**
```bash
python TEST_GUI\test_osnova2.py
```

---

## Архітектура Вставки Тексту

### Методи вставки (адаптивні)

**1. SendInput Unicode (найкращий для сучасних UI)**
- Chrome/Mozilla
- PyQt6 з ASCII
- Notepad Win11

**2. Ctrl+V (Win32 API)**
- PyQt6 з не-ASCII (емодзі, кирилиця)
- Fallback для PyQt6 якщо SendInput не спрацював

**3. WM_PASTE (для старих Win32 додатків)**
- AkelPad, класичний Edit
- З попереднім копіюванням в буфер

**4. Ctrl+V (pyautogui)**
- Last fallback

---

## Критичні Компоненти

⚠️ **НЕ ЗМІНЮВАТИ БЕЗ УЗГОДЖЕННЯ:**

**global_voice_input.py:**
- `_insert_segment` - вставка сегментів тексту
- `_send_input_unicode` - SendInput Unicode вставка

**tools_mouse_keyboard.py:**
- `send_input_unicode` - SendInput Unicode вставка
- `insert_text_smart` - універсальна вставка тексту

---

## Вимоги

### Python Залежності
```bash
pip install pyperclip
pip install pynput  # опціонально, для hotkey
pip install PyQt6>=6.6.0
```

---

## Логування

**Розташування:** `d:\Python\agent\debug_logs\`

**Файли:**
- `main_window.log` — повідомлення з main_window.py
- `_on_message.log` — повідомлення з _on_message callback

---

## Результати Тестування

### PyQt6 (test_insert_text_smart.py)
```
✅ Текст з кирилицею та емодзі вставляється коректно
✅ Ctrl+V (Win32 API) працює для не-ASCII символів
✅ SendInput Unicode працює для ASCII символів
```

### Notepad Win11 (test_insert_notepad.py)
```
✅ SendInput Unicode працює коректно
✅ Текст вставляється без спотворень
```

---

## Помилки та Виправлення

### Помилка: Дублювання тексту в PyQt6
**Причина:** Подвійна вставка через SendInput + Ctrl+V
**Виправлено:** Ctrl+V тільки якщо SendInput не спрацював

### Помилка: Відсутність вставки в старі Win32 додатки
**Причина:** WM_PASTE викликався без копіювання в буфер
**Виправлено:** Додано копіювання в буфер перед WM_PASTE

### Помилка: Спотворення емодзі в PyQt6
**Причина:** SendInput Unicode спотворює емодзі в PyQt6
**Виправлено:** Для PyQt6 з не-ASCII одразу Ctrl+V

---

## Використання

### Запуск всіх тестів:
```bash
cd d:\Python\agent
python TEST_GUI\test_insert_notepad.py
python TEST_GUI\test_insert_text_smart.py
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

### Компоненти
- `functions/global_voice_input.py` — GlobalVoiceInput клас
- `functions/tools_mouse_keyboard.py` — insert_text_smart, send_input_unicode
- `core_gui_pyqt6/main_window.py` — GUI чат та кнопки
- `functions/core_stt_listener.py` — STT розпізнавання

---

## Автор

MAРК — Асистент для автоматизації роботи з ПК
Версія: PyQt6 MVP + виправлені методи вставки тексту
Дата документації: 2026-05-08
