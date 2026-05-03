#!/usr/bin/env python3
"""
Автоматизований тест для виконання різних завдань через GUI.

ПОСТІЙНИЙ ТЕСТ - НЕ ВИДАЛЯТИ!
Використовується для перевірки GUI автоматизації через GVI з різними командами.

РОБОЧИ МЕТОД:
- GlobalVoiceInput()._insert_text_with_script(text) - вставка тексту через Shift+F10

Завдання для тестування:
1. "аналізуй екран" — screen analysis tools
2. "проаналізуй код d:\Python\agent" — code analysis
3. "перелік файлів в d:\Python\agent" — directory listing

Затримки:
- 6 секунд для ініціалізації
- 1 секунда перед вставкою тексту
- 2 секунди перед Enter
- 30 секунд для виконання кожного завдання
"""
import subprocess
import time
import os
import sys

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

def main():
    print("=" * 60)
    print("Тест виконання різних завдань через GUI")
    print("(GUI автоматизація через GVI)")
    print("=" * 60)
    
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
    print("⏳ Зачекайте 6 секунд для ініціалізації...")
    time.sleep(6)
    
    # 4. Список завдань для тестування
    tasks = [
        "аналізуй екран",
        "проаналізуй код d:\\Python\\agent",
        "перелік файлів в d:\\Python\\agent"
    ]
    
    try:
        from functions.aaa_voice_input import activate_window_by_title
        from functions.tools_mouse_keyboard import keyboard_press
        from functions.global_voice_input import GlobalVoiceInput

        for i, task in enumerate(tasks, 1):
            print(f"\n{'='*60}")
            print(f"ЗАВДАННЯ {i}/{len(tasks)}: {task}")
            print(f"{'='*60}")
            
            # Затримка для ініціалізації агента
            print("⏳ Затримка 6 секунд для ініціалізації агента...")
            time.sleep(6)
            print("✅ Затримка завершена")

            # Активація вікна агента
            print("📝 Активація вікна агента...")
            result = activate_window_by_title(title="МАРК — Асистент (PyQt6)")
            print(f"✅ Вікно активовано: {result}")
            print(f"   - hwnd: {result.get('hwnd')}")
            print(f"   - title: {result.get('title')}")
            print(f"   - foreground: {result.get('foreground')}")
            print(f"   - focus_error: {result.get('focus_error')}")

            # Вставка тексту через GlobalVoiceInput._insert_text_with_script
            print("⏳ Затримка 1 секунда перед вставкою тексту...")
            time.sleep(1)
            print("✅ Затримка завершена")
            
            print(f"⌨️ Початок вставки тексту '{task}' через GlobalVoiceInput._insert_text_with_script...")
            
            gvi = GlobalVoiceInput()
            gvi._last_window_hwnd = result.get('hwnd')
            gvi._last_window_title = result.get('title')
            print(f"   - gvi._last_window_hwnd: {gvi._last_window_hwnd}")
            print(f"   - gvi._last_window_title: {gvi._last_window_title}")
            
            print("⌨️ Виклик gvi._insert_text_with_script(text)...")
            insert_result = gvi._insert_text_with_script(task)
            print(f"✅ Текст вставлено: {insert_result}")

            # Натискання Enter
            print("⏳ Затримка 2 секунди перед Enter...")
            time.sleep(2)
            print("✅ Затримка завершена")
            print(f"⏎ Натискання Enter...")
            result = keyboard_press(key="Enter")
            print(f"✅ Enter натиснуто: {result}")

            # Зачекати відповіді
            print(f"⏳ Зачекайте 30 секунд для виконання завдання...")
            for j in range(30):
                time.sleep(1)
                if j % 10 == 0:
                    print(f"⏳ Пройшло {j} секунд...")
            
            print(f"✅ Завдання {i} завершено")
    except Exception as e:
        print(f"❌ Помилка при виконанні завдань: {e}")
    
    # 7. Закриття програми
    print("\n❌ Закриття програми...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    
    # 8. Читання логів
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
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    main()
