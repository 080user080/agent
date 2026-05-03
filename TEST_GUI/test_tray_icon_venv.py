#!/usr/bin/env python3
"""
Тест Tray Icon з логуванням в файл (запуск через віртуальне середовище).

Тестує зміну іконки tray icon при зміні статусів Global Voice Input.
"""
import subprocess
import time
import os
import sys
from pathlib import Path

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

# Налаштування логування в файл
log_file = Path(__file__).parent / "tray_icon_venv_test.log"
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
    print("Тест Tray Icon (запуск через віртуальне середовище)")
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
    
    # 3. Тест зміни статусів tray icon
    print("\n📝 Тест зміни статусів tray icon...")
    logger.info("Початок тесту зміни статусів tray icon")
    
    try:
        from functions.voice_tray_icon import get_voice_tray_icon, VoiceStatus
        
        # Отримати tray icon (вже ініціалізований в GUI)
        tray = get_voice_tray_icon()
        logger.info(f"Tray icon отримано: {tray}")
        logger.info(f"Tray icon app: {tray.app}")
        
        if tray.app is None:
            logger.error("Tray icon не ініціалізований (app is None)")
            print("❌ Tray icon не ініціалізований")
            return
        
        # Тест зміни статусів
        statuses = [
            (VoiceStatus.IDLE, "Готовий"),
            (VoiceStatus.RECORDING, "Запис..."),
            (VoiceStatus.PROCESSING, "Розпізнавання..."),
            (VoiceStatus.ERROR, "Помилка"),
            (VoiceStatus.NO_MIC, "Немає мікрофона"),
            (VoiceStatus.IDLE, "Готовий"),
        ]
        
        for i, (status, text) in enumerate(statuses):
            logger.info(f"Встановлення статусу {i+1}/{len(statuses)}: {status} - {text}")
            print(f"📝 Встановлення статусу {i+1}/{len(statuses)}: {status} - {text}")
            
            tray.set_status(status, text)
            time.sleep(2)  # Чекати 2 секунди для візуалізації
            
            logger.info(f"Поточний статус: {tray.current_status}")
            print(f"✅ Поточний статус: {tray.current_status}")
        
        logger.info("Тест зміни статусів завершено")
        print("✅ Тест зміни статусів завершено")
        
    except Exception as e:
        logger.error(f"Помилка при тесті tray icon: {e}")
        import traceback
        traceback.print_exc()
        print(f"❌ Помилка при тесті tray icon: {e}")
    
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
