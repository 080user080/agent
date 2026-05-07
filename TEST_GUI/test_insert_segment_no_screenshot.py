#!/usr/bin/env python3
"""
Автоматизований тест для перевірки вставки тексту через GlobalVoiceInput._insert_segment.

БЕЗ СКРІНШОТІВ - спрощена версія test_aaa_osnova2_vstavka_GVI.py

РОБОЧІ МЕТОДИ:
- activate_window_by_title(title="Untitled - Notepad") - активація вікна Notepad
- GlobalVoiceInput()._insert_segment(text) - вставка тексту без RoboTask
- Пріоритет: WM_PASTE → SendInput Unicode → Ctrl+V

Затримки:
- 1 секунда для відкриття Notepad
- 0.2 секунди перед вставкою тексту
"""
import subprocess
import time
import sys
import ctypes

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

def main():
    print("=" * 60)
    print("Тест вставки через GlobalVoiceInput._insert_segment")
    print("(Без скріншотів, без RoboTask)")
    print("=" * 60)

    # 1. Відкрити Notepad
    print("📝 Відкриття Notepad...")
    try:
        subprocess.Popen(["notepad.exe"])
        time.sleep(1.0)
        print("✅ Notepad відкрито")
    except Exception as e:
        print(f"❌ Помилка відкриття Notepad: {e}")
        return False

    # 2. Отримати hwnd Notepad
    print("🔍 Отримання hwnd Notepad...")
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW("Notepad", None)
        if hwnd == 0:
            print("❌ Не знайдено вікно Notepad")
            return False
        print(f"✅ hwnd={hwnd}")
    except Exception as e:
        print(f"❌ Помилка отримання hwnd: {e}")
        return False

    # 3. Активація вікна
    print("📝 Активація вікна Notepad...")
    try:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        print("✅ Вікно активовано")
    except Exception as e:
        print(f"❌ Помилка активації: {e}")
        return False

    # 3.5 Очистити вміст Notepad
    print("🗑️ Очищення вмісту Notepad...")
    try:
        import pyautogui
        # Ctrl+A для виділення всього
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        # Delete для видалення
        pyautogui.press('delete')
        time.sleep(0.1)
        print("✅ Вміст очищено")
    except Exception as e:
        print(f"⚠️ Помилка очищення: {e}")

    # 4. Вставка тексту через _insert_segment
    print("\n⌨️ Вставка тексту через _insert_segment...")
    try:
        from functions.global_voice_input import GlobalVoiceInput

        text = "Привіт світ! Тест кирилиці."
        print(f"   Текст: '{text}'")

        gvi = GlobalVoiceInput.__new__(GlobalVoiceInput)
        gvi._last_window_hwnd = hwnd
        gvi._last_window_title = "Untitled - Notepad"

        print("   Виклик _insert_segment...")
        time.sleep(0.2)
        result = gvi._insert_segment(text)
        print(f"✅ Результат: {result}")
    except Exception as e:
        print(f"❌ Помилка вставки: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 5. Перевірка чи текст вставився
    print("\n🔍 Перевірка вставки тексту...")
    try:
        import pyautogui
        import pyperclip
        
        time.sleep(0.5)
        # Ctrl+A для виділення всього тексту
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        # Ctrl+C для копіювання
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.1)
        
        clipboard_text = pyperclip.paste()
        print(f"   Текст в Notepad: '{clipboard_text}'")
        
        if text in clipboard_text:
            print("✅ Текст коректно вставлений")
        else:
            print(f"⚠️ Текст не співпадає (очікувався '{text}')")
    except Exception as e:
        print(f"⚠️ Помилка перевірки тексту: {e}")

    # 6. Закрити Notepad
    print("\n❌ Закриття Notepad...")
    try:
        pyautogui.hotkey('alt', 'f4')
        time.sleep(0.2)
        print("✅ Notepad закрито")
    except Exception as e:
        print(f"⚠️ Помилка закриття: {e}")

    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)
    
    return result

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
