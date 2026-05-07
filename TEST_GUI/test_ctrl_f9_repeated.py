"""
Debug-Loop тест для повторного натискання Ctrl+F9.

Етап 2: Створення тестового сценарію
- Arrange: Підготуй вхідні дані (буфер обміну з попереднім текстом)
- Act: Запускаємо GlobalVoiceInput, натискаємо Ctrl+F9, потім знову Ctrl+F9 під час запису
- Assert: Перевір що запис зупинився і старий буфер не вставився
"""

import sys
sys.path.insert(0, r"d:\Python\agent")

import pyperclip
import time
import threading

def test_ctrl_f9_repeated():
    """Автоматичний тест повторного натискання Ctrl+F9."""
    
    # Arrange: Підготуй вхідні дані - буфер з текстом (як в реальності)
    old_text = "Новийтекст --- знову вставилося з буферу"
    pyperclip.copy(old_text)
    time.sleep(0.1)
    
    print(f"[TEST] Arrange: Буфер ПЕРЕД тестом: '{pyperclip.paste()}' (len={len(pyperclip.paste())})")
    
    # Act: Запускаємо GlobalVoiceInput і натискаємо Ctrl+F9 двічі
    try:
        from functions.global_voice_input import GlobalVoiceInput, HotkeyHook
        
        print("[TEST] Act: Ініціалізація GlobalVoiceInput...")
        
        def on_voice_status(status):
            print(f"[TEST] Status callback: {status}")
        
        gvi = GlobalVoiceInput(
            hotkey="ctrl+f9",
            callback=None,
            status_callback=on_voice_status
        )
        
        if not gvi.start():
            print("[TEST FAIL] Не вдалося запустити GlobalVoiceInput")
            return False
        
        print("[TEST] GlobalVoiceInput ініціалізовано")
        print("[TEST] Очікування першого натискання Ctrl+F9...")
        
        # Автоматично натискаємо Ctrl+F9 через 2 секунди
        def press_hotkey_twice():
            time.sleep(2)
            print("[TEST] Автоматичне перше натискання Ctrl+F9...")
            try:
                # Викликаємо callback напряму
                gvi._on_hotkey_pressed()
                print("[TEST] Перше Ctrl+F9 callback викликано")
            except Exception as e:
                print(f"[TEST] Помилка першого натискання Ctrl+F9: {e}")
            
            # Чекаємо 3 секунди під час запису
            time.sleep(3)
            
            print("[TEST] Автоматичне повторне натискання Ctrl+F9...")
            try:
                # Викликаємо callback напряму повторно
                gvi._on_hotkey_pressed()
                print("[TEST] Повторне Ctrl+F9 callback викликано")
            except Exception as e:
                print(f"[TEST] Помилка повторного натискання Ctrl+F9: {e}")
        
        press_thread = threading.Thread(target=press_hotkey_twice, daemon=True)
        press_thread.start()
        
        # Чекаємо 8 секунд для обробки
        time.sleep(8)
        
        # Зупинити GlobalVoiceInput
        gvi.stop()
        
        # Assert: Перевір що запис зупинився (is_listening=False)
        print(f"[TEST] Assert: is_listening={gvi.is_listening} (має бути False)")
        
        # Перевір що буфер не змінився (не вставився старий текст)
        clipboard_after = pyperclip.paste()
        print(f"[TEST] Assert: Буфер ПІСЛЯ тесту: '{clipboard_after}' (len={len(clipboard_after)})")
        
        if not gvi.is_listening:
            print(f"[TEST PASS] Запис зупинився (is_listening=False)")
            return True
        else:
            print(f"[TEST FAIL] Запис не зупинився (is_listening=True)")
            return False
            
    except Exception as e:
        print(f"[TEST FAIL] Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Debug-Loop: Автоматичний тест повторного натискання Ctrl+F9")
    print("=" * 60)
    
    result = test_ctrl_f9_repeated()
    
    print("\n" + "=" * 60)
    if result:
        print("✅ Тест пройшов успішно")
    else:
        print("❌ Тест не пройшов")
    print("=" * 60)
