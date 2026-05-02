"""Тест для VoiceTrayIcon - перевірка чи працює tray icon окремо."""
import sys
import os
import time

# Додати шлях до проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.voice_tray_icon import VoiceTrayIcon, VoiceStatus

def test_tray_icon():
    print("=" * 60)
    print("Тест VoiceTrayIcon")
    print("=" * 60)
    
    # Створити tray icon
    print("\n1. Створення VoiceTrayIcon...")
    tray = VoiceTrayIcon()
    
    # Ініціалізувати
    print("\n2. Ініціалізація tray icon...")
    if tray.initialize():
        print("✅ Tray icon ініціалізовано успішно")
    else:
        print("❌ Не вдалося ініціалізувати tray icon")
        return
    
    # Почекати трохи
    print("\n3. Чекаємо 2 секунди...")
    time.sleep(2)
    
    # Змінити статус на RECORDING
    print("\n4. Зміна статусу на RECORDING...")
    tray.set_status(VoiceStatus.RECORDING, "Запис...")
    time.sleep(2)
    
    # Змінити статус на PROCESSING
    print("\n5. Зміна статусу на PROCESSING...")
    tray.set_status(VoiceStatus.PROCESSING, "Розпізнавання...")
    time.sleep(2)
    
    # Змінити статус на IDLE
    print("\n6. Зміна статусу на IDLE...")
    tray.set_status(VoiceStatus.IDLE, "Готовий")
    time.sleep(2)
    
    # Змінити статус на ERROR
    print("\n7. Зміна статусу на ERROR...")
    tray.set_status(VoiceStatus.ERROR, "Помилка")
    time.sleep(2)
    
    # Повернути на IDLE
    print("\n8. Повернення на IDLE...")
    tray.set_status(VoiceStatus.IDLE, "Готовий")
    time.sleep(2)
    
    # Cleanup
    print("\n9. Очищення ресурсів...")
    tray.cleanup()
    print("✅ Тест завершено")

if __name__ == "__main__":
    test_tray_icon()
