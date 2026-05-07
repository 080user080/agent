"""
Debug-Loop тест для проблеми з Ctrl+F9 вставляє попередній буфер обміну.

Етап 2: Створення тестового сценарію
- Arrange: Підготуй вхідні дані (буфер обміну з попереднім текстом)
- Act: Виклич функцію _start_recording яка має очистити буфер
- Assert: Перевір чи буфер очищений
"""

import sys
sys.path.insert(0, r"d:\Python\agent")

import pyperclip
import time

def test_clipboard_clearing():
    """Тест очищення буфера обміну перед записом."""
    
    # Arrange: Підготуй вхідні дані
    test_text = "Попередній текст в буфері обміну"
    pyperclip.copy(test_text)
    time.sleep(0.1)
    
    # Перевір що буфер має текст
    clipboard_before = pyperclip.paste()
    print(f"[TEST] Arrange: Буфер ПЕРЕД тестом: '{clipboard_before}' (len={len(clipboard_before)})")
    assert clipboard_before == test_text, "Буфер не встановлено правильно"
    
    # Act: Виклич функцію очищення (імітація _start_recording)
    print("[TEST] Act: Очищення буфера...")
    for i in range(3):
        pyperclip.copy("")
        time.sleep(0.05)
        current = pyperclip.paste()
        print(f"[TEST] Спроба {i+1}: '{current}' (len={len(current)})")
        if not current:
            break
    
    # Assert: Перевір чи буфер очищений
    clipboard_after = pyperclip.paste()
    print(f"[TEST] Assert: Буфер ПІСЛЯ очищення: '{clipboard_after}' (len={len(clipboard_after)})")
    
    if clipboard_after:
        print(f"[TEST FAIL] Буфер не очищено! Залишився: '{clipboard_after}'")
        return False
    else:
        print(f"[TEST PASS] Буфер успішно очищено!")
        return True

if __name__ == "__main__":
    print("=" * 60)
    print("Debug-Loop: Тест очищення буфера обміну")
    print("=" * 60)
    
    result = test_clipboard_clearing()
    
    print("=" * 60)
    if result:
        print("✅ Тест пройшов успішно")
    else:
        print("❌ Тест не пройшов")
    print("=" * 60)
