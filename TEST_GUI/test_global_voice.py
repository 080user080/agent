"""Діагностичний скрипт для глобального голосового введення."""
import sys
import os

# Додати шлях до project root
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from functions.runtime.core_settings import get_setting, get_settings

print("=" * 60)
print("ДІАГНОСТИКА ГЛОБАЛЬНОГО ГОЛОСОВОГО ВВЕДЕННЯ")
print("=" * 60)

# Завантажити налаштування
settings = get_settings()

# Перевірити налаштування
enabled = get_setting("GLOBAL_VOICE_ENABLED", False)
hotkey = get_setting("GLOBAL_VOICE_HOTKEY", "ctrl+shift+v")

print(f"\nНалаштування:")
print(f"  GLOBAL_VOICE_ENABLED: {enabled}")
print(f"  GLOBAL_VOICE_HOTKEY: {hotkey}")

if not enabled:
    print("\n❌ Глобальне голосове введення ВИМКНЕНО")
    print("   Увімкніть GLOBAL_VOICE_ENABLED в налаштуваннях GUI")
    sys.exit(1)

print("\n✅ Глобальне голосове введення увімкнено")

# Спробувати ініціалізувати
try:
    from functions.global_voice_input import GlobalVoiceInput, HotkeyHook, MOD_CONTROL, MOD_SHIFT
    
    print("\nТест HotkeyHook:")
    hook = HotkeyHook(hotkey)
    print(f"  Hotkey: {hotkey}")
    print(f"  Pynput available: {hook.pynput_available}")

    if hook.pynput_available:
        print("  ✅ HotkeyHook готовий до використання")
    else:
        print("  ⚠️  pynput не встановлено - hotkey не працюватиме")
    
    print("\nТест GlobalVoiceInput:")
    
    def on_text(text):
        print(f"  🎯 Розпізнано: {text}")
    
    def on_status(status):
        print(f"  📊 Статус: {status}")
    
    gvi = GlobalVoiceInput(
        hotkey=hotkey,
        callback=on_text,
        status_callback=on_status
    )
    
    print("  Спроба запуску...")
    if gvi.start():
        print("  ✅ GlobalVoiceInput запущено успішно")
        print(f"  Hotkey: {hotkey}")
        print("\nНатисніть hotkey для тесту...")
        print("Натисніть Ctrl+C для зупинки")
        
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nЗупинка...")
            gvi.stop()
            print("✅ Зупинено")
    else:
        print("  ❌ Не вдалося запустити GlobalVoiceInput")
        print("  Перевірте логи для деталей")
        
except Exception as e:
    print(f"\n❌ Помилка: {e}")
    import traceback
    traceback.print_exc()
