#!/usr/bin/env python3
"""
Автоматизований тест для перевірки voice_input через кнопку мікрофона в GUI.

ПОСТІЙНИЙ ТЕСТ - НЕ ВИДАЛЯТИ!
Використовується для перевірки voice_input функції через кнопку 🎤 в GUI.

РОБОЧІ МЕТОДИ:
- Натискання кнопки мікрофона в GUI
- Перевірка логів voice_input

Затримки:
- 30 секунд для ініціалізації
- 15 секунд для виконання команди voice_input
"""
import os
import subprocess
import sys
import time

# Додати шлях до agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 60)
    print("Тест voice_input через кнопку мікрофона в GUI")
    print("=" * 60)

    python_exe = r"D:\Python\TEXT\LLM_model\venv\Scripts\python.exe"
    script_path = r"d:\Python\agent\run_assistant_qt.py"

    # Очистити STT логи перед тестом
    stt_debug_log = r"d:\Python\agent\logs\stt_debug.log"
    stt_logs_jsonl = r"d:\Python\agent\logs\stt_logs.jsonl"

    for log_file in [stt_debug_log, stt_logs_jsonl]:
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
                print(f"🗑️ Видалив лог: {log_file}")
            except Exception as e:
                print(f"⚠️ Не вдалося видалити {log_file}: {e}")

    # Запуск програми
    print(f"\n🚀 Запуск агента...")
    process = subprocess.Popen(
        [python_exe, script_path],
        cwd=r"d:\Python\agent",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
    )

    # Чекаємо ініціалізації
    print("⏳ Чекаю 30 секунд для ініціалізації агента...")
    time.sleep(30)

    # Тест voice_input через GUI (Planner розпізнає "_ 5" як voice_input)
    try:
        from functions.tools.tools_mouse_keyboard import activate_window_by_title, keyboard_type, keyboard_press

        print("\n📝 Активація вікна агента...")
        result = activate_window_by_title("МАРК — Асистент (PyQt6)")
        print(f"✅ Вікно активовано: {result}")

        print("⏳ Затримка 2 секунди перед введенням команди...")
        time.sleep(2)
        
        # Введення команди voice_input в поле вводу і натискання Enter
        print("⌨️ Введення команди 'voice_input 5'...")
        keyboard_type(text="voice_input 5")
        
        print("⏎ Натискання Enter...")
        keyboard_press("enter")

        print("⏳ Чекаю 15 секунд для виконання команди voice_input...")
        time.sleep(15)
        
    except Exception as e:
        print(f"❌ Помилка при тесті voice_input: {e}")
        import traceback
        traceback.print_exc()

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

    print(f"\n📄 {stt_debug_log}:")
    print("-" * 60)
    if os.path.exists(stt_debug_log):
        with open(stt_debug_log, "r", encoding="utf-8") as f:
            content = f.read()
            if content:
                print(content)
            else:
                print("(порожній)")
    else:
        print("(файл не існує)")

    print(f"\n📄 {stt_logs_jsonl}:")
    print("-" * 60)
    if os.path.exists(stt_logs_jsonl):
        with open(stt_logs_jsonl, "r", encoding="utf-8") as f:
            content = f.read()
            if content:
                print(content)
            else:
                print("(порожній)")
    else:
        print("(файл не існує)")

    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)


if __name__ == "__main__":
    main()
