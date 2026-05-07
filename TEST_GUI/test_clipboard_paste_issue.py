"""
Debug-Loop тест для проблеми з вставкою буфера при Ctrl+F9.

Етап 2: Створення тестового сценарію
- Arrange: Підготуй вхідні дані (буфер обміну з попереднім текстом)
- Act: Імітуємо вставку тексту через різні методи
- Assert: Перевір що вставляється правильний текст
"""

import sys
sys.path.insert(0, r"d:\Python\agent")

import pyperclip
import time

def test_clipboard_paste_sequence():
    """Тест послідовності вставки тексту."""
    
    # Arrange: Підготуй вхідні дані
    old_text = "Попередній текст в буфері обміну"
    new_text = "Новий текст"
    
    # Встановити старий буфер
    pyperclip.copy(old_text)
    time.sleep(0.1)
    
    print(f"[TEST] Arrange: Буфер зі старим текстом: '{pyperclip.paste()}'")
    
    # Act 1: Очистити буфер (як в _start_recording)
    print("[TEST] Act 1: Очищення буфера...")
    for i in range(3):
        pyperclip.copy("")
        time.sleep(0.05)
        current = pyperclip.paste()
        print(f"[TEST] Спроба {i+1}: '{current}' (len={len(current)})")
        if not current:
            break
    
    print(f"[TEST] Буфер після очищення: '{pyperclip.paste()}'")
    
    # Act 2: Встановити новий текст (як перед вставкою)
    print(f"[TEST] Act 2: Встановлення нового тексту: '{new_text}'")
    pyperclip.copy(new_text)
    time.sleep(0.1)
    
    print(f"[TEST] Буфер перед вставкою: '{pyperclip.paste()}'")
    
    # Assert: Перевір що в буфері новий текст
    clipboard_check = pyperclip.paste()
    print(f"[TEST] Assert: Буфер: '{clipboard_check}'")
    
    if clipboard_check == new_text:
        print(f"[TEST PASS] В буфері правильний текст")
        return True
    else:
        print(f"[TEST FAIL] В буфері неправильний текст! Очікувано: '{new_text}', отримано: '{clipboard_check}'")
        return False

def test_win32_paste_simulation():
    """Імітація вставки через Win32 (як в _paste_into_window)."""
    
    # Arrange
    old_text = "Попередній текст"
    new_text = "Новий текст"
    
    pyperclip.copy(old_text)
    time.sleep(0.1)
    print(f"[TEST] Arrange: Буфер зі старим текстом: '{pyperclip.paste()}'")
    
    # Act: Очистити + вставити новий
    pyperclip.copy("")
    time.sleep(0.05)
    pyperclip.copy(new_text)
    time.sleep(0.1)
    
    # Assert
    clipboard_check = pyperclip.paste()
    print(f"[TEST] Assert: Буфер: '{clipboard_check}'")
    
    if clipboard_check == new_text:
        print(f"[TEST PASS] Win32 імітація пройшла")
        return True
    else:
        print(f"[TEST FAIL] Win32 імітація не пройшла")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Debug-Loop: Тест послідовності вставки буфера")
    print("=" * 60)
    
    print("\n--- Тест 1: Очищення + вставка ---")
    result1 = test_clipboard_paste_sequence()
    
    print("\n--- Тест 2: Win32 імітація ---")
    result2 = test_win32_paste_simulation()
    
    print("\n" + "=" * 60)
    if result1 and result2:
        print("✅ Всі тести пройшли успішно")
    else:
        print("❌ Деякі тести не пройшли")
    print("=" * 60)
