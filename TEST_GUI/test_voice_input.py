#!/usr/bin/env python3
"""
Автоматизований тест для перевірки voice_input функції через GUI.

ПОСТІЙНИЙ ТЕСТ - НЕ ВИДАЛЯТИ!
Використовується для перевірки voice_input функції через GUI.

РОБОЧІ МЕТОДИ:
- Введення команди "voice_input 5" в GUI
- Перевірка логів voice_input

Затримки:
- 30 секунд для ініціалізації
- 10 секунд для виконання команди voice_input
"""
import subprocess
import time
import sys

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

def main():
    print("=" * 60)
    print("Тест voice_input через GUI")
    print("=" * 60)

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
    
    # Затримка для ініціалізації
    print("⏳ Зачекайте 30 секунд для ініціалізації...")
    time.sleep(30)

    # Тест voice_input через GUI
    try:
        from functions.aaa_voice_input import activate_window_by_title
        from functions.global_voice_input import GlobalVoiceInput
        from functions.tools_mouse_keyboard import keyboard_type, keyboard_press

        print("\n📝 Активація вікна агента...")
        result = activate_window_by_title(title="МАРК — Асистент (PyQt6)")
        print(f"✅ Вікно активовано: {result}")

        # Введення команди voice_input
        print("⏳ Затримка 2 секунди перед введенням команди...")
        time.sleep(2)
        
        command = "voice_input 5"
        print(f"⌨️ Введення команди '{command}'...")
        keyboard_type(text=command)
        time.sleep(0.5)
        
        print("⏎ Натискання Enter...")
        keyboard_press(key="Enter")
        time.sleep(0.5)

        # Чекаємо виконання команди
        print("⏳ Чекаю 10 секунд для виконання команди voice_input...")
        time.sleep(10)
        
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

    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    main()
