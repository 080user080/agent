"""Тестовий скрипт для VoiceTrayIcon."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from functions.voice_tray_icon import get_voice_tray_icon, VoiceStatus

print("=" * 60)
print("ТЕСТ VOICE TRAY ICON")
print("=" * 60)

tray = get_voice_tray_icon()

if not tray.initialize():
    print("❌ Не вдалося ініціалізувати tray icon")
    sys.exit(1)

print("✅ Tray icon ініціалізовано")
print("\nТест статусів:")

# Тест IDLE
print("1. IDLE (синій)")
tray.set_status(VoiceStatus.IDLE, "Готовий")
time.sleep(2)

# Тест RECORDING
print("2. RECORDING (червоний)")
tray.set_status(VoiceStatus.RECORDING, "Запис...")
time.sleep(2)

# Тест PROCESSING
print("3. PROCESSING (помаранчевий)")
tray.set_status(VoiceStatus.PROCESSING, "Розпізнавання...")
time.sleep(2)

# Тест ERROR
print("4. ERROR (сірий)")
tray.set_status(VoiceStatus.ERROR, "Помилка")
time.sleep(2)

# Повернути IDLE
print("5. Повернення до IDLE")
tray.set_status(VoiceStatus.IDLE, "Готовий")

print("\n✅ Тест завершено")
print("Перевірте tray icon біля годинника")
print("Натисніть Enter для виходу...")
input()

tray.cleanup()
print("✅ Очищено")
