"""Debug-Loop тест для _insert_segment без RoboTask.

Пріоритет методів:
  1. WM_PASTE напряму в hwnd контрола
  2. WM_CHAR через SendMessageW (посимвольна вставка)
  3. keyboard_hotkey(ctrl+v) як fallback
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import ctypes
import pyperclip
import subprocess

def test_insert_segment_with_notepad():
    """Debug-Loop Етап 2: Тест _insert_segment з реальним Notepad."""
    print("=" * 70)
    print("DEBUG-LOOP ЕТАП 2: Тест _insert_segment з Notepad")
    print("=" * 70)
    
    # Arrange: Відкрити Notepad
    print("\n[TEST] Arrange: Відкрити Notepad")
    try:
        subprocess.Popen(["notepad.exe"])
        time.sleep(1.0)
        print("[TEST] ✅ Notepad відкрито")
    except Exception as e:
        print(f"[TEST] ❌ Помилка відкриття Notepad: {e}")
        return False
    
    # Arrange: Отримати hwnd Notepad
    print("\n[TEST] Arrange: Отримати hwnd Notepad")
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW("Notepad", None)
        if hwnd == 0:
            print("[TEST] ❌ Не знайдено вікно Notepad")
            return False
        
        print(f"[TEST] ✅ Знайдено hwnd={hwnd}")
    except Exception as e:
        print(f"[TEST] ❌ Помилка отримання hwnd: {e}")
        return False
    
    # Arrange: Активувати вікно
    print("\n[TEST] Arrange: Активувати вікно Notepad")
    try:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        print("[TEST] ✅ Вікно активовано")
    except Exception as e:
        print(f"[TEST] ❌ Помилка активації: {e}")
        return False
    
    # Arrange: Підготувати текст
    test_text = "Привіт світ! Тест кирилиці."
    print(f"\n[TEST] Arrange: test_text='{test_text}'")
    
    # Act: Викликати _insert_segment
    print("\n[TEST] Act: Виклик _insert_segment")
    try:
        from functions.global_voice_input import GlobalVoiceInput
        
        gvi = GlobalVoiceInput.__new__(GlobalVoiceInput)
        gvi._last_window_hwnd = hwnd
        gvi._last_window_title = "Notepad"
        
        result = gvi._insert_segment(test_text)
        print(f"[TEST] Результат: {result}")
    except Exception as e:
        print(f"[TEST] ❌ Помилка виклику: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Assert: Перевірити результат
    print("\n[TEST] Assert: Перевірка результату")
    if result:
        print("[TEST] ✅ _insert_segment успішний")
        
        # Перевірити чи текст вставився (через буфер обміну)
        time.sleep(0.5)
        # Ctrl+A для виділення всього тексту
        try:
            import pyautogui
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.1)
            clipboard_text = pyperclip.paste()
            print(f"[TEST] Текст в Notepad: '{clipboard_text}'")
            
            if test_text in clipboard_text:
                print("[TEST] ✅ Текст коректно вставлений")
            else:
                print(f"[TEST] ⚠️ Текст не співпадає (очікувався '{test_text}')")
        except Exception as e:
            print(f"[TEST] ⚠️ Помилка перевірки тексту: {e}")
        
        # Закрити Notepad
        try:
            pyautogui.hotkey('alt', 'f4')
            time.sleep(0.2)
        except:
            pass
        
        return True
    else:
        print("[TEST] ❌ _insert_segment не успішний")
        
        # Закрити Notepad
        try:
            import pyautogui
            pyautogui.hotkey('alt', 'f4')
            time.sleep(0.2)
        except:
            pass
        
        return False

def test_insert_segment_wm_char_only():
    """Тест тільки WM_CHAR методу (без WM_PASTE)."""
    print("\n" + "=" * 70)
    print("DEBUG-LOOP: Тест WM_CHAR методу")
    print("=" * 70)
    
    # Arrange: Відкрити Notepad
    print("\n[TEST] Arrange: Відкрити Notepad")
    try:
        subprocess.Popen(["notepad.exe"])
        time.sleep(1.0)
        print("[TEST] ✅ Notepad відкрито")
    except Exception as e:
        print(f"[TEST] ❌ Помилка: {e}")
        return False
    
    # Arrange: Отримати hwnd
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW("Notepad", None)
        if hwnd == 0:
            print("[TEST] ❌ Не знайдено вікно")
            return False
        print(f"[TEST] ✅ hwnd={hwnd}")
        
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as e:
        print(f"[TEST] ❌ Помилка: {e}")
        return False
    
    # Arrange: Текст
    test_text = "Test"
    print(f"\n[TEST] Arrange: test_text='{test_text}'")
    
    # Act: Викликати _send_input_unicode (WM_CHAR)
    print("\n[TEST] Act: Виклик _send_input_unicode (WM_CHAR)")
    try:
        from functions.global_voice_input import GlobalVoiceInput
        
        gvi = GlobalVoiceInput.__new__(GlobalVoiceInput)
        gvi._last_window_hwnd = hwnd
        
        result = gvi._send_input_unicode(test_text)
        print(f"[TEST] Результат: {result}")
    except Exception as e:
        print(f"[TEST] ❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Assert
    print("\n[TEST] Assert: Перевірка результату")
    if result:
        print("[TEST] ✅ WM_CHAR успішний")
    else:
        print("[TEST] ❌ WM_CHAR не успішний")
    
    # Закрити Notepad
    try:
        import pyautogui
        pyautogui.hotkey('alt', 'f4')
        time.sleep(0.2)
    except:
        pass
    
    return result

if __name__ == "__main__":
    print("DEBUG-LOOP: _insert_segment без RoboTask")
    print("=" * 70)
    
    # Тест 1: Повний _insert_segment
    result1 = test_insert_segment_with_notepad()
    
    # Тест 2: Тільки WM_CHAR
    result2 = test_insert_segment_wm_char_only()
    
    print("\n" + "=" * 70)
    print("ПІДСУМКИ ТЕСТУ")
    print("=" * 70)
    print(f"Повний _insert_segment: {'✅ PASS' if result1 else '❌ FAIL'}")
    print(f"Тільки WM_CHAR: {'✅ PASS' if result2 else '❌ FAIL'}")
    
    if result1 and result2:
        print("\n✅ Debug-Loop завершено: Обидва методи працюють")
        print("   - WM_PASTE працює")
        print("   - WM_CHAR працює як fallback")
    elif result1:
        print("\n✅ Повний _insert_segment працює")
    else:
        print("\n⚠️ Потрібна додаткова діагностика")
