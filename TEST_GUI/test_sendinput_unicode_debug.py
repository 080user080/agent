"""Debug-Loop тест для SendInput Unicode (error=87).

Проблема: SendInput Unicode не працює без активного вікна (error=87).
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_sendinput_unicode_with_active_window():
    """
    Етап 2: Тестовий сценарій для SendInput Unicode з активним вікном.
    
    Arrange: Відкрити Notepad, активувати вікно
    Act: Викликати _send_input_unicode
    Assert: Перевити результат
    """
    print("=" * 70)
    print("DEBUG-LOOP ЕТАП 2: Тест SendInput Unicode з активним вікном")
    print("=" * 70)
    
    # Arrange: Відкрити Notepad
    print("\n[TEST] Arrange: Відкрити Notepad")
    try:
        import subprocess
        subprocess.Popen(["notepad.exe"])
        time.sleep(1.0)  # Чекаємо відкриття
        print("[TEST] ✅ Notepad відкрито")
    except Exception as e:
        print(f"[TEST] ❌ Помилка відкриття Notepad: {e}")
        return False
    
    # Arrange: Активувати вікно Notepad
    print("\n[TEST] Arrange: Активувати вікно Notepad")
    try:
        import pyautogui
        import ctypes
        user32 = ctypes.windll.user32
        
        # Знайти Notepad вікно
        hwnd = user32.FindWindowW("Notepad", None)
        if hwnd == 0:
            print("[TEST] ❌ Не знайдено вікно Notepad")
            return False
        
        print(f"[TEST] Знайдено hwnd={hwnd}")
        
        # Активувати вікно
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        
        # Клікнути в центрі екрану для гарантії фокусу
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        time.sleep(0.1)
        
        print("[TEST] ✅ Вікно активовано")
    except Exception as e:
        print(f"[TEST] ❌ Помилка активації вікна: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Arrange: Підготувати текст для вставки
    test_text = "Test"
    print(f"\n[TEST] Arrange: test_text='{test_text}'")
    
    # Act: Викликати _send_input_unicode
    print("\n[TEST] Act: Виклик _send_input_unicode")
    try:
        from functions.global_voice_input import GlobalVoiceInput
        
        gvi = GlobalVoiceInput()
        result = gvi._send_input_unicode(test_text)
        print(f"[TEST] Результат: {result}")
    except Exception as e:
        print(f"[TEST] ❌ Помилка виклику: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Assert: Перевірити результат
    print("\n[TEST] Assert: Перевірка результату")
    if result:
        print("[TEST] ✅ SendInput Unicode успішний")
        time.sleep(0.5)
        
        # Закрити Notepad
        try:
            pyautogui.hotkey('alt', 'f4')
            time.sleep(0.2)
        except:
            pass
        
        return True
    else:
        print("[TEST] ❌ SendInput Unicode не успішний (очікувалося з error=87)")
        
        # Закрити Notepad
        try:
            pyautogui.hotkey('alt', 'f4')
            time.sleep(0.2)
        except:
            pass
        
        return False

def test_sendinput_unicode_without_active_window():
    """
    Етап 2: Тестовий сценарій для SendInput Unicode БЕЗ активного вікна.
    
    Arrange: Мінімізувати всі вікна, неактивне вікно
    Act: Викликати _send_input_unicode
    Assert: Перевити результат (очікується error=87)
    """
    print("\n" + "=" * 70)
    print("DEBUG-LOOP ЕТАП 2: Тест SendInput Unicode БЕЗ активного вікна")
    print("=" * 70)
    
    # Arrange: Мінімізувати всі вікна
    print("\n[TEST] Arrange: Мінімізувати всі вікна")
    try:
        import pyautogui
        # Показати робочий стіл (Win+D)
        pyautogui.hotkey('win', 'd')
        time.sleep(0.5)
        print("[TEST] ✅ Вікна мінімізовано")
    except Exception as e:
        print(f"[TEST] ❌ Помилка мінімізації: {e}")
        return False
    
    # Arrange: Підготувати текст для вставки
    test_text = "Test"
    print(f"\n[TEST] Arrange: test_text='{test_text}'")
    
    # Act: Викликати _send_input_unicode
    print("\n[TEST] Act: Виклик _send_input_unicode (без активного вікна)")
    try:
        from functions.global_voice_input import GlobalVoiceInput
        
        gvi = GlobalVoiceInput()
        result = gvi._send_input_unicode(test_text)
        print(f"[TEST] Результат: {result}")
    except Exception as e:
        print(f"[TEST] ❌ Помилка виклику: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Assert: Перевірити результат (очікується False з error=87)
    print("\n[TEST] Assert: Перевірка результату (очікується False)")
    if not result:
        print("[TEST] ✅ SendInput Unicode не успішний (як і очікувалося)")
        print("[TEST] Це підтверджує проблему: error=87 без активного вікна")
        return True
    else:
        print("[TEST] ⚠️ SendInput Unicode успішний (неочікувано)")
        return False

if __name__ == "__main__":
    print("DEBUG-LOOP: SendInput Unicode (error=87)")
    print("=" * 70)
    
    # Тест 1: З активним вікном
    result1 = test_sendinput_unicode_with_active_window()
    
    # Тест 2: Без активного вікна
    result2 = test_sendinput_unicode_without_active_window()
    
    print("\n" + "=" * 70)
    print("ПІДСУМКИ ТЕСТУ")
    print("=" * 70)
    print(f"Тест з активним вікном: {'✅ PASS' if result1 else '❌ FAIL'}")
    print(f"Тест без активного вікна: {'✅ PASS' if result2 else '❌ FAIL'}")
    
    if result1 and not result2:
        print("\n✅ Debug-Loop Етап 3: Аналіз підтвердив проблему")
        print("   - SendInput працює з активним вікном")
        print("   - SendInput не працює без активного вікна (error=87)")
        print("\n   Рішення: Додати перевірку активного вікна перед SendInput")
    else:
        print("\n⚠️ Результати тесту неочікувані")
