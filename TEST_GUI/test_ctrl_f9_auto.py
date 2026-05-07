"""
Debug-Loop тест для автоматичного натискання Ctrl+F9.

Етап 2: Створення тестового сценарію
- Arrange: Підготуй вхідні дані (буфер обміну з попереднім текстом)
- Act: Запускаємо GlobalVoiceInput і натискаємо Ctrl+F9 автоматично
- Assert: Перевір що старий буфер не вставляється
"""

import sys
sys.path.insert(0, r"d:\Python\agent")

import pyperclip
import time
import threading

def test_ctrl_f9_auto():
    """Автоматичний тест натискання Ctrl+F9."""
    
    # Arrange: Підготуй вхідні дані
    old_text = "Попередній текст в буфері обміну"
    pyperclip.copy(old_text)
    time.sleep(0.1)
    
    print(f"[TEST] Arrange: Буфер ПЕРЕД тестом: '{pyperclip.paste()}' (len={len(pyperclip.paste())})")
    
    # Act: Запускаємо GlobalVoiceInput і натискаємо Ctrl+F9
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
        print("[TEST] Очікування натискання Ctrl+F9...")
        
        # Автоматично натискаємо Ctrl+F9 через 2 секунди
        def press_hotkey():
            time.sleep(2)
            print("[TEST] Автоматичне натискання Ctrl+F9...")
            try:
                import pyautogui
                pyautogui.hotkey('ctrl', 'f9')
                print("[TEST] Ctrl+F9 натиснуто")
            except Exception as e:
                print(f"[TEST] Помилка натискання Ctrl+F9: {e}")
        
        press_thread = threading.Thread(target=press_hotkey, daemon=True)
        press_thread.start()
        
        # Чекаємо 5 секунд для обробки
        time.sleep(5)
        
        # Зупинити GlobalVoiceInput
        gvi.stop()
        
        # Assert: Перевір що буфер не змінився (не вставився старий текст)
        clipboard_after = pyperclip.paste()
        print(f"[TEST] Assert: Буфер ПІСЛЯ Ctrl+F9: '{clipboard_after}' (len={len(clipboard_after)})")
        
        if clipboard_after == old_text:
            print(f"[TEST PASS] Буфер не змінився (старий текст не вставився)")
            return True
        else:
            print(f"[TEST FAIL] Буфер змінився! Очікувано: '{old_text}', отримано: '{clipboard_after}'")
            return False
            
    except Exception as e:
        print(f"[TEST FAIL] Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Debug-Loop: Автоматичний тест Ctrl+F9")
    print("=" * 60)
    
    result = test_ctrl_f9_auto()
    
    print("\n" + "=" * 60)
    if result:
        print("✅ Тест пройшов успішно")
    else:
        print("❌ Тест не пройшов")
    print("=" * 60)
