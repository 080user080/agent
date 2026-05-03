#!/usr/bin/env python3
"""
Автоматизований тест для перевірки вставки тексту через GlobalVoiceInput._insert_text.

ПОСТІЙНИЙ ТЕСТ - НЕ ВИДАЛЯТИ!
Використовується для перевірки GUI автоматизації через GVI та LLM response.

РОБОЧІ МЕТОДИ:
- activate_window_by_title(title="МАРК — Асистент (PyQt6)") - активація вікна агента
- GlobalVoiceInput()._insert_text(text) - вставка тексту через буфер обміну
- keyboard_press(key="Enter") - натискання Enter

Затримки:
- 30 секунд для ініціалізації
- 2 секунди перед вставкою тексту
- 2 секунди перед Enter
- 30 секунд для виконання плану + LLM summary
"""
import subprocess
import time
import os
import sys
from datetime import datetime

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

def main():
    print("=" * 60)
    print("Тест вставки через GlobalVoiceInput._insert_text")
    print("(GUI автоматизація через GVI)")
    print("=" * 60)

    # Створити папку для скріншотів
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshots_dir = rf"d:\Python\agent\TEST_GUI\screenshots_{timestamp}"
    os.makedirs(screenshots_dir, exist_ok=True)
    print(f"📁 Папка для скріншотів: {screenshots_dir}")

    # Функція для скріншота
    def take_screenshot(name):
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            path = os.path.join(screenshots_dir, f"{name}.png")
            screenshot.save(path)
            print(f"📸 Скріншот збережено: {name}.png")
        except Exception as e:
            print(f"❌ Помилка скріншота {name}: {e}")

    # 1. Очистити логи
    logs_dir = r"d:\Python\agent\debug_logs"
    if os.path.exists(logs_dir):
        for log_file in os.listdir(logs_dir):
            log_path = os.path.join(logs_dir, log_file)
            try:
                os.remove(log_path)
                print(f"✅ Видалено лог: {log_file}")
            except Exception as e:
                print(f"❌ Помилка видалення {log_file}: {e}")
    
    # 2. Запуск агента
    print("🚀 Запуск агента...")
    venv_python = r"D:\Python\TEXT\LLM_model\venv\Scripts\python.exe"
    script_path = r"d:\Python\agent\run_assistant_qt.py"
    process = subprocess.Popen(
        [venv_python, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        cwd=r"d:\Python\agent"
    )
    
    # Читання виводу в окремому потоці
    def read_output():
        for line in process.stdout:
            try:
                if line.strip():
                    print(f"[GUI] {line}", end='')
            except UnicodeDecodeError:
                pass
    
    import threading
    output_thread = threading.Thread(target=read_output, daemon=True)
    output_thread.start()
    
    # 3. Затримка для ініціалізації
    print("⏳ Зачекайте 30 секунд для ініціалізації...")
    time.sleep(30)
    take_screenshot("01_after_initialization")

    # 4. Активація вікна агента та вставка тексту через GlobalVoiceInput
    print("\n📝 Активація вікна агента та вставка тексту 'проаналізуй код d:\\Python\\agent' через GVI...")
    try:
        from functions.aaa_voice_input import activate_window_by_title
        from functions.tools_mouse_keyboard import keyboard_press
        from functions.global_voice_input import GlobalVoiceInput

        print("✅ Ініціалізація завершена")

        # Активація вікна агента
        print("📝 Активація вікна агента...")
        result = activate_window_by_title(title="МАРК — Асистент (PyQt6)")
        print(f"✅ Вікно активовано: {result}")
        print(f"   - hwnd: {result.get('hwnd')}")
        print(f"   - title: {result.get('title')}")
        print(f"   - foreground: {result.get('foreground')}")
        print(f"   - focus_error: {result.get('focus_error')}")
        take_screenshot("02_window_activated")

        # Вставка тексту через GlobalVoiceInput._insert_text_with_script
        print("⏳ Затримка 2 секунди перед вставкою тексту...")
        time.sleep(2)
        print("✅ Затримка завершена")
        
        text = "проаналізуй код d:\\Python\\agent"
        print(f"⌨️ Початок вставки тексту '{text}' через GlobalVoiceInput._insert_text_with_script...")
        
        gvi = GlobalVoiceInput()
        gvi._last_window_hwnd = result.get('hwnd')
        gvi._last_window_title = result.get('title')
        print(f"   - gvi._last_window_hwnd: {gvi._last_window_hwnd}")
        print(f"   - gvi._last_window_title: {gvi._last_window_title}")
        
        print("⌨️ Виклик gvi._insert_text_with_script(text)...")
        insert_result = gvi._insert_text_with_script(text)
        print(f"✅ Текст вставлено: {insert_result}")
        take_screenshot("03_text_inserted")

        # Натискання Enter
        print("⏳ Затримка 2 секунди перед Enter...")
        time.sleep(2)
        print("✅ Затримка завершена")
        print(f"⏎ Натискання Enter...")
        result = keyboard_press(key="Enter")
        print(f"✅ Enter натиснуто: {result}")

        # Зачекати відповіді (для виконання плану + LLM summary)
        print(f"⏳ Зачекайте 30 секунд для виконання плану + LLM summary...")
        for i in range(30):
            time.sleep(1)
            if i % 10 == 0:
                print(f"⏳ Пройшло {i} секунд...")
                take_screenshot(f"04_agentloop_{i}s")
    except Exception as e:
        print(f"❌ Помилка при вставці тексту: {e}")

    # Фінальний скріншот перед закриттям
    take_screenshot("05_before_close")

    # 7. Закриття програми
    print("❌ Закриття програми...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    
    # 7. Читання логів
    print("\n" + "=" * 60)
    print("ЛОГИ:")
    print("=" * 60)
    
    if os.path.exists(logs_dir):
        for log_file in os.listdir(logs_dir):
            log_path = os.path.join(logs_dir, log_file)
            print(f"\n📄 {log_file}:")
            print("-" * 40)
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content:
                        print(content)
                    else:
                        print("(пустий)")
            except Exception as e:
                print(f"❌ Помилка читання {log_file}: {e}")
    else:
        print("❌ Папка логів не існує")

    # Створити описовий файл
    description_path = os.path.join(screenshots_dir, "README.txt")
    with open(description_path, "w", encoding="utf-8") as f:
        f.write(f"Тест розуміння екрану AgentLoop\n")
        f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Задача: проаналізуй код d:\\Python\\agent\n")
        f.write(f"\nОпис скріншотів:\n")
        f.write(f"- 01_after_initialization.png: Після ініціалізації агента (30 сек)\n")
        f.write(f"- 02_window_activated.png: Після активації вікна агента\n")
        f.write(f"- 03_text_inserted.png: Після вставки тексту через GVI\n")
        f.write(f"- 04_agentloop_0s.png: AgentLoop запущено (0 сек)\n")
        f.write(f"- 04_agentloop_10s.png: AgentLoop виконується (10 сек)\n")
        f.write(f"- 04_agentloop_20s.png: AgentLoop виконується (20 сек)\n")
        f.write(f"- 05_before_close.png: Перед закриттям програми\n")

    print(f"\n📝 Опис збережено: {description_path}")
    print(f"📁 Папка зі скріншотами: {screenshots_dir}")

    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    main()
