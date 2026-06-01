#!/usr/bin/env python3
"""
Автоматизований тест для перевірки STT та комбінації клавіш Ctrl+F9.

ПОСТІЙНИЙ ТЕСТ - НЕ ВИДАЛЯТИ!
Використовується для перевірки псевдопотокового STT розпізнавання.

РОБОЧІ МЕТОДИ:
- activate_window_by_title() - активація вікна
- keyboard_hotkey() - натискання Ctrl+F9

Затримки:
- 30 секунд для ініціалізації
- 5 секунд для запису
- 2 секунди для розпізнавання
"""
import subprocess
import time
import os
import sys
from datetime import datetime

sys.path.insert(0, r"d:\Python\agent")

def main():
    print("=" * 60)
    print("Тест STT та комбінації клавіш Ctrl+F9")
    print("=" * 60)

    # Створити папку для скріншотів
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshots_dir = rf"d:\Python\agent\TEST_GUI\screenshots_stt_{timestamp}"
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

    # Очистити логи STT
    logs_dir = r"d:\Python\agent\logs"
    for log_file in ["stt_debug.log", "stt_logs.jsonl"]:
        log_path = os.path.join(logs_dir, log_file)
        if os.path.exists(log_path):
            try:
                os.remove(log_path)
                print(f"✅ Видалено лог: {log_file}")
            except Exception as e:
                print(f"❌ Помилка видалення {log_file}: {e}")

    # Запуск агента
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

    # Затримка для ініціалізації
    print("⏳ Зачекайте 30 секунд для ініціалізації...")
    time.sleep(30)
    take_screenshot("01_after_initialization")

    # Тест STT
    try:
        from functions.tools.tools_mouse_keyboard import keyboard_hotkey

        print("\n🎤 Тест STT - натискання Ctrl+F9...")
        print("⌨️ Натискання Ctrl+F9 (початок запису)...")
        result = keyboard_hotkey("ctrl", "f9")
        print(f"✅ Ctrl+F9 натиснуто: {result}")
        take_screenshot("02_after_first_hotkey")

        print("⏳ Чекаю 35 секунд для запису і розпізнавання чанків...")
        time.sleep(35)
        take_screenshot("03_during_recording")

        print("⌨️ Натискання Ctrl+F9 (зупинка запису)...")
        result = keyboard_hotkey("ctrl", "f9")
        print(f"✅ Ctrl+F9 натиснуто: {result}")
        take_screenshot("04_after_second_hotkey")

        print("⏳ Чекаю 3 секунди для розпізнавання...")
        time.sleep(3)
        take_screenshot("05_after_recognition")

    except Exception as e:
        print(f"❌ Помилка при тесті STT: {e}")
        import traceback
        traceback.print_exc()

    # Фінальний скріншот
    take_screenshot("06_before_close")

    # Закриття програми
    print("❌ Закриття програми...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

    # Читання логів STT
    print("\n" + "=" * 60)
    print("ЛОГИ STT:")
    print("=" * 60)

    for log_file in ["stt_debug.log", "stt_logs.jsonl"]:
        log_path = os.path.join(logs_dir, log_file)
        if os.path.exists(log_path):
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
            print(f"❌ {log_file} не існує")

    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    main()
