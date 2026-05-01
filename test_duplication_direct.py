#!/usr/bin/env python3
"""
Автоматизований тест для перевірки дублювання повідомлень (робочі методи).

ПОСТІЙНИЙ ТЕСТ - НЕ ВИДАЛЯТИ!
Використовується для перевірки GUI автоматизації та LLM response.

РОБОЧІ МЕТОДИ (підтверджено користувачем):
- activate_window_by_title(title="МАРК — Асистент (PyQt6)") - активація вікна агента
- keyboard_type(text="привіт") - вставка тексту в активне вікно
- keyboard_press(key="Enter") - натискання Enter

Затримки:
- 2 секунди до вставки тексту
- 10 секунд до перевірки відповіді
"""
import subprocess
import time
import os
import sys

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

def main():
    print("=" * 60)
    print("Автоматизований тест для перевірки дублювання повідомлень")
    print("(прямий виклик методу GUI)")
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
                pass  # Пропускаємо помилки кодування
    
    import threading
    output_thread = threading.Thread(target=read_output, daemon=True)
    output_thread.start()
    
    # 3. Затримка для ініціалізації
    print("⏳ Зачекайте 6 секунд для ініціалізації...")
    time.sleep(6)
    
    # 4. Активація вікна агента та вставка тексту (РОБОЧІ МЕТОДИ)
    print("\n📝 Активація вікна агента та вставка тексту 'відкрий браузер'...")
    try:
        from functions.aaa_voice_input import activate_window_by_title
        from functions.tools_mouse_keyboard import keyboard_type, keyboard_press
        
        # Затримки для ініціалізації агента
        time.sleep(6)
        
        # Активація вікна агента
        print("📝 Активація вікна агента та вставка тексту 'відкрий браузер'...")
        result = activate_window_by_title(title="МАРК — Асистент (PyQt6)")
        print(f"🔓 Активація вікна агента...")
        print(f"✅ Вікно активовано: {result}")
        
        # Вставка тексту
        time.sleep(1)
        text = "відкрий браузер"
        print(f"⌨️ Вставка тексту '{text}'...")
        result = keyboard_type(text=text)
        print(f"✅ Текст вставлено: {result}")
        
        # Натискання Enter
        time.sleep(0.5)
        print(f"⏎ Натискання Enter...")
        result = keyboard_press(key="Enter")
        print(f"✅ Enter натиснуто: {result}")
        
        # Зачекати відповіді
        print(f"⏳ Зачекайте 20 секунду для відповіді...")
        time.sleep(20)
    except Exception as e:
        print(f"❌ Помилка при вставці тексту: {e}")
    
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
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    main()
