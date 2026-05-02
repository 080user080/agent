"""Простий тест VoiceTrayIcon без STT."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.voice_tray_icon import get_voice_tray_icon, VoiceStatus
from PyQt6.QtCore import QTimer

print("=" * 60)
print("ПРОСТИЙ ТЕСТ VOICE TRAY ICON")
print("=" * 60)

tray = get_voice_tray_icon()

if not tray.initialize():
    print("[FAIL] Не вдалося ініціалізувати tray icon")
    print("Перевірте чи встановлено PyQt6")
    sys.exit(1)

print("[OK] Tray icon ініціалізовано")
print("\nПеревірте іконку біля годинника Windows")
print("\nТест статусів (кожен 3 секунди):")

statuses = [
    (VoiceStatus.IDLE, "Готовий (синій)"),
    (VoiceStatus.RECORDING, "Запис... (червоний)"),
    (VoiceStatus.PROCESSING, "Розпізнавання... (помаранчевий)"),
    (VoiceStatus.ERROR, "Помилка (сірий)"),
]

current_index = [0]

def change_status():
    if current_index[0] < len(statuses):
        status, desc = statuses[current_index[0]]
        print(f"  {desc}")
        tray.set_status(status, desc.split()[0])
        current_index[0] += 1
        QTimer.singleShot(3000, change_status)
    else:
        print("\nПовернення до IDLE")
        tray.set_status(VoiceStatus.IDLE, "Готовий")
        print("\n[OK] Тест завершено")
        # Вийти з event loop через 2 секунди
        QTimer.singleShot(2000, tray.app.quit)

# Запустити таймер
QTimer.singleShot(1000, change_status)

# Запустити event loop
if tray.app:
    tray.app.exec()

tray.cleanup()
print("[OK] Очищено")
