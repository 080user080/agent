#!/usr/bin/env python3
"""Інтеграційний тест для Global Voice Input з реальними вікнами."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from functions.global_voice_input import GlobalVoiceInput

def test_insert_segment_integration():
    """Інтеграційний тест вставки тексту в різні типи вікон."""
    print("=== Інтеграційний тест Global Voice Input ===")
    
    gvi = GlobalVoiceInput()
    
    # Отримати активне вікно
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    
    if hwnd:
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        
        gvi._last_window_hwnd = hwnd
        gvi._last_window_title = title
        
        print(f"Активне вікно: hwnd={hwnd}")
        print(f"Заголовок: {title}")
        
        # Отримати інформацію про цільовий контрол
        target_hwnd, class_name = gvi._resolve_focus_target(hwnd)
        print(f"Цільовий контрол: hwnd={target_hwnd}, class='{class_name}'")
        
        # Визначити стратегію вставки
        strategy = gvi._get_insert_strategy(class_name, title)
        print(f"Стратегія вставки: {strategy}")
        
        # Спробувати вставити тестовий текст
        test_text = f"Тест вставки: {title[:30]} [{strategy}]"
        print(f"\nСпроба вставити: '{test_text}'")
        
        result = gvi._insert_segment(test_text)
        print(f"Результат вставки: {result}")
        
        return result
    else:
        print("Не знайдено активного вікна")
        return False

if __name__ == "__main__":
    success = test_insert_segment_integration()
    print(f"\nТест {'пройшов успішно' if success else 'не пройшов'}")
