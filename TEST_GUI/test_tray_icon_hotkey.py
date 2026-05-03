#!/usr/bin/env python3
"""
Тест Tray Icon через Ctrl+F9 hotkey (реальний сценарій використання).

Тестує зміну іконки tray icon при натисканні Ctrl+F9.
"""
import subprocess
import time
import os
import sys
from pathlib import Path

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

# Налаштування логування в файл
log_file = Path(__file__).parent / "tray_icon_hotkey_test.log"
log_file.unlink(missing_ok=True)

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("Тест Tray Icon через Ctrl+F9 hotkey")
    print("=" * 60)
    logger.info(f"Логи будуть записані в: {log_file}")
    
    # 1. Запуск агента через віртуальне середовище
    print("🚀 Запуск агента через віртуальне середовище...")
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
                    logger.info(f"[GUI] {line.strip()}")
            except UnicodeDecodeError:
                pass
    
    import threading
    output_thread = threading.Thread(target=read_output, daemon=True)
    output_thread.start()
    
    # 2. Затримка для ініціалізації
    print("⏳ Зачекайте 20 секунд для ініціалізації...")
    logger.info("Зачекайте 20 секунд для ініціалізації...")
    time.sleep(20)
    
    # 3. Тест через Ctrl+F9 hotkey
    print("\n📝 Тест через Ctrl+F9 hotkey...")
    logger.info("Початок тесту через Ctrl+F9 hotkey")
    
    try:
        import pyautogui
        
        # Натиснути Ctrl+F9
        print("⌨️ Натискання Ctrl+F9...")
        logger.info("Натискання Ctrl+F9")
        pyautogui.hotkey('ctrl', 'f9')
        print("✅ Ctrl+F9 натиснуто")
        logger.info("Ctrl+F9 натиснуто")
        
        # Зачекати 10 секунд для запису голосу
        print("⏳ Зачекайте 10 секунд для запису голосу...")
        logger.info("Зачекайте 10 секунд для запису голосу")
        time.sleep(10)
        
        # Натиснути Ctrl+F9 ще раз для зупинки
        print("⌨️ Натискання Ctrl+F9 для зупинки...")
        logger.info("Натискання Ctrl+F9 для зупинки")
        pyautogui.hotkey('ctrl', 'f9')
        print("✅ Ctrl+F9 натиснуто для зупинки")
        logger.info("Ctrl+F9 натиснуто для зупинки")
        
        logger.info("Тест через Ctrl+F9 hotkey завершено")
        print("✅ Тест через Ctrl+F9 hotkey завершено")
        
    except Exception as e:
        logger.error(f"Помилка при тесті через hotkey: {e}")
        import traceback
        traceback.print_exc()
        print(f"❌ Помилка при тесті через hotkey: {e}")
    
    # 4. Затримка для спостереження
    print("\n⏳ Зачекайте 5 секунд для спостереження...")
    logger.info("Зачекайте 5 секунд для спостереження...")
    time.sleep(5)
    
    # 5. Закриття програми
    print("❌ Закриття програми...")
    logger.info("Закриття програми...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print(f"Логи записані в: {log_file}")
    print("=" * 60)
    logger.info("ТЕСТ ЗАВЕРШЕНО")

if __name__ == "__main__":
    main()
