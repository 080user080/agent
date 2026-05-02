#!/usr/bin/env python3
"""Автоматизований тест для перевірки дублювання повідомлень."""
import subprocess
import time
import os
import sys

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

def main():
    print("=" * 60)
    print("Автоматизований тест для перевірки дублювання повідомлень")
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
    
    # 2. Запуск програми через віртуальне середовище
    print("\n🚀 Запуск PyQt6 GUI...")
    python_exe = r"D:\Python\TEXT\LLM_model\venv\Scripts\python.exe"
    process = subprocess.Popen(
        [python_exe, "run.py", "--qt"],
        cwd=r"d:\Python\agent",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Виводимо stdout в реальному часі
    def read_output():
        while True:
            try:
                line = process.stdout.readline()
                if not line:
                    break
                print(f"[GUI] {line}", end='')
            except UnicodeDecodeError:
                pass  # Пропускаємо помилки кодування
    
    import threading
    output_thread = threading.Thread(target=read_output, daemon=True)
    output_thread.start()
    
    # 3. Затримка для ініціалізації
    print("⏳ Зачекайте 20 секунд для ініціалізації...")
    time.sleep(20)
    
    # 4. Фокус на поле вводу (клік по центру екрану)
    print("\n🖱️  Встановлення фокусу на поле вводу...")
    try:
        import pyautogui
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        print("✅ Фокус встановлено")
        time.sleep(1)  # Затримка після кліку
    except Exception as e:
        print(f"❌ Помилка встановлення фокусу: {e}")
    
    # 5. Вставка тексту "привіт" через pyautogui
    print("\n⌨️  Вставка тексту 'привіт'...")
    try:
        import pyautogui
        pyautogui.write("привіт", interval=0.05)
        print("✅ Текст вставлено через pyautogui")
    except Exception as e:
        print(f"❌ Помилка вставки тексту: {e}")
    
    # 6. Натискання Enter
    print("⏎ Натискання Enter...")
    try:
        import pyautogui
        pyautogui.press("Enter")
        print("✅ Enter натиснуто через pyautogui")
    except Exception as e:
        print(f"❌ Помилка натискання Enter: {e}")
    
    # 6. Затримка для відповіді
    print("⏳ Зачекайте 15 секунд для відповіді...")
    time.sleep(15)
    
    # 7. Закриття програми
    print("❌ Закриття програми...")
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
