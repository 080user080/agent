#!/usr/bin/env python3
"""
Тест звичайного чату з LLM (просте повідомлення "привіт").
"""
import subprocess
import time
import sys
from pathlib import Path

# Налаштування логування в файл
log_file = Path(__file__).parent / "chat_simple_test.log"
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
    print("Тест звичайного чату з LLM")
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
    print("⏳ Зачекайте 10 секунд для ініціалізації...")
    logger.info("Зачекайте 10 секунд для ініціалізації...")
    time.sleep(10)
    
    # 3. Тест простого повідомлення через GUI
    print("\n📝 Тест простого повідомлення 'привіт'...")
    logger.info("Початок тесту простого повідомлення")
    
    try:
        import pyautogui
        
        # Активувати вікно агента
        print("📝 Активація вікна агента...")
        pyautogui.hotkey('alt', 'tab')
        time.sleep(0.5)
        
        # Вставити текст "привіт"
        print("⌨️ Вставка тексту 'привіт'...")
        pyautogui.write('привіт')
        time.sleep(0.5)
        
        # Натиснути Enter
        print("⏎ Натискання Enter...")
        pyautogui.press('enter')
        print("✅ Enter натиснуто")
        logger.info("Enter натиснуто")
        
        # Зачекати відповіді
        print("⏳ Зачекайте 15 секунд для відповіді...")
        logger.info("Зачекайте 15 секунд для відповіді")
        time.sleep(15)
        
        logger.info("Тест простого повідомлення завершено")
        print("✅ Тест простого повідомлення завершено")
        
    except Exception as e:
        logger.error(f"Помилка при тесті чату: {e}")
        import traceback
        traceback.print_exc()
        print(f"❌ Помилка при тесті чату: {e}")
    
    # 4. Затримка для спостереження
    print("\n⏳ Зачекайте 2 секунди для спостереження...")
    logger.info("Зачекайте 2 секунди для спостереження...")
    time.sleep(2)
    
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
