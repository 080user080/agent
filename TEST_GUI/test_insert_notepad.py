#!/usr/bin/env python3
"""Тест для insert_text_smart з Блокнотом."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import subprocess
from functions.tools_mouse_keyboard import insert_text_smart

def test_notepad():
    """Тест вставки тексту в Блокнот."""
    print("=== Тест insert_text_smart в Блокнот ===")
    
    # Відкрити Блокнот
    try:
        notepad = subprocess.Popen(['notepad.exe'])
        time.sleep(1.0)  # Чекаємо щоб Блокнот відкрився
        print("Блокнот відкрито")
    except Exception as e:
        print(f"Помилка відкриття Блокноту: {e}")
        return
    
    # Тестовий текст з кирилицею
    test_text = "Тест insert_text_smart в Блокнот: Привіт світ! 🎉"
    print(f"Вставка тексту: '{test_text}'")
    
    # Викликати insert_text_smart
    result = insert_text_smart(test_text)
    print(f"Результат: {result}")
    
    # Чекаємо щоб текст вставився
    time.sleep(1.0)
    
    print("Текст вставлено. Блокнот залишиться відкритим для перевірки.")
    print("Закрийте Блокнот вручну через 5 секунд...")
    time.sleep(5)
    
    # Закрити Блокнот
    try:
        notepad.terminate()
        print("Блокнот закрито")
    except:
        pass

if __name__ == "__main__":
    test_notepad()
