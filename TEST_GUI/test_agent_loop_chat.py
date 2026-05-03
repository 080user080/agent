#!/usr/bin/env python3
"""
Тест відображення повідомлень в GUI чаті при запуску AgentLoop.
"""
import subprocess
import time
import sys
from pathlib import Path

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

# Налаштування логування в файл
log_file = Path(__file__).parent / "agent_loop_chat_test.log"
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
    print("Тест відображення повідомлень в GUI чаті при AgentLoop")
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
    
    # 3. Тест команди яка запускає AgentLoop
    print("\n📝 Тест команди 'аналізуй екран' (запускає AgentLoop)...")
    logger.info("Початок тесту команди 'аналізуй екран'")
    
    try:
        from functions.aaa_voice_input import activate_window_by_title
        from functions.tools_mouse_keyboard import keyboard_press
        from functions.global_voice_input import GlobalVoiceInput
        
        # Затримка для ініціалізації агента
        time.sleep(2)
        
        # Активація вікна агента
        print("📝 Активація вікна агента...")
        logger.info("Активація вікна агента...")
        result = activate_window_by_title(title="МАРК — Асистент (PyQt6)")
        print(f"✅ Вікно активовано: {result}")
        logger.info(f"Вікно активовано: {result}")
        
        # Вставка тексту через GlobalVoiceInput._insert_text
        time.sleep(1)
        text = "аналізуй екран"
        print(f"⌨️ Вставка тексту '{text}' через GlobalVoiceInput._insert_text...")
        logger.info(f"Вставка тексту '{text}' через GlobalVoiceInput._insert_text...")
        
        # Створити GlobalVoiceInput для вставки
        gvi = GlobalVoiceInput()
        gvi._last_window_hwnd = result.get('hwnd')
        gvi._last_window_title = result.get('title')
        
        insert_result = gvi._insert_text(text)
        print(f"✅ Текст вставлено: {insert_result}")
        logger.info(f"Текст вставлено: {insert_result}")
        
        # Натискання Enter
        time.sleep(2)
        print(f"⏎ Натискання Enter...")
        logger.info("Натискання Enter...")
        result = keyboard_press(key="Enter")
        print(f"✅ Enter натиснуто: {result}")
        logger.info(f"Enter натиснуто: {result}")
        
        # Зачекати виконання
        print("⏳ Зачекайте 20 секунд для виконання AgentLoop...")
        logger.info("Зачекайте 20 секунд для виконання AgentLoop")
        time.sleep(20)
        
        logger.info("Тест команди 'аналізуй екран' завершено")
        print("✅ Тест команди 'аналізуй екран' завершено")
        
    except Exception as e:
        logger.error(f"Помилка при тесті: {e}")
        import traceback
        traceback.print_exc()
        print(f"❌ Помилка при тесті: {e}")
    
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
