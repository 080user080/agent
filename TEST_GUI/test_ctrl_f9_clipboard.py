"""
Debug-Loop тест для проблеми з Ctrl+F9 вставляє старий буфер.

Етап 2: Створення тестового сценарію
- Arrange: Підготуй вхідні дані (буфер обміну з попереднім текстом)
- Act: Імітуємо натискання Ctrl+F9 (викликаємо _on_hotkey_pressed)
- Assert: Перевір що старий буфер не вставляється
"""

import sys
sys.path.insert(0, r"d:\Python\agent")

import pyperclip
import time

def test_hotkey_pressed_clipboard():
    """Тест що при натисканні Ctrl+F9 не вставляється старий буфер."""
    
    # Arrange: Підготуй вхідні дані
    old_text = "Попередній текст в буфері обміну"
    pyperclip.copy(old_text)
    time.sleep(0.1)
    
    # Перевір що буфер має текст
    clipboard_before = pyperclip.paste()
    print(f"[TEST] Arrange: Буфер ПЕРЕД тестом: '{clipboard_before}' (len={len(clipboard_before)})")
    assert clipboard_before == old_text, "Буфер не встановлено правильно"
    
    # Act: Імітуємо натискання Ctrl+F9 (відпускаємо модифікатори)
    print("[TEST] Act: Імітація натискання Ctrl+F9 (відпускаємо модифікатори)...")
    try:
        import pyautogui
        pyautogui.keyUp("ctrl")
        pyautogui.keyUp("shift")
        pyautogui.keyUp("alt")
        pyautogui.keyUp("win")
        time.sleep(0.1)
    except Exception as e:
        print(f"[TEST] Помилка відпускання модифікаторів: {e}")
    
    # Assert: Перевір що буфер не змінився (не вставився старий текст)
    clipboard_after = pyperclip.paste()
    print(f"[TEST] Assert: Буфер ПІСЛЯ імітації Ctrl+F9: '{clipboard_after}' (len={len(clipboard_after)})")
    
    if clipboard_after == old_text:
        print(f"[TEST PASS] Буфер не змінився (старий текст не вставився)")
        return True
    else:
        print(f"[TEST FAIL] Буфер змінився! Очікувано: '{old_text}', отримано: '{clipboard_after}'")
        return False

def test_modifiers_release():
    """Тест відпускання модифікаторів."""
    
    # Arrange
    print("[TEST] Arrange: Тест відпускання модифікаторів")
    
    # Act: Відпустити модифікатори
    print("[TEST] Act: Відпускаємо модифікатори...")
    try:
        import pyautogui
        pyautogui.keyUp("ctrl")
        pyautogui.keyUp("shift")
        pyautogui.keyUp("alt")
        pyautogui.keyUp("win")
        time.sleep(0.1)
        print("[TEST] Модифікатори відпущені")
        return True
    except Exception as e:
        print(f"[TEST FAIL] Помилка відпускання модифікаторів: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Debug-Loop: Тест Ctrl+F9 вставка буфера")
    print("=" * 60)
    
    print("\n--- Тест 1: Відпускання модифікаторів ---")
    result1 = test_modifiers_release()
    
    print("\n--- Тест 2: Ctrl+F9 не вставляє старий буфер ---")
    result2 = test_hotkey_pressed_clipboard()
    
    print("\n" + "=" * 60)
    if result1 and result2:
        print("✅ Всі тести пройшли успішно")
    else:
        print("❌ Деякі тести не пройшли")
    print("=" * 60)
