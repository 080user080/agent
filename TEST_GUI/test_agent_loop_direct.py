#!/usr/bin/env python3
"""
Прямий тест AgentLoop без GUI.

Перевіряє чи AgentLoop працює з реальною задачею і чи додається повідомлення користувача в GUI чергу.
"""
import sys
import os
import queue
import threading

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

# Використовувати віртуальне середовище
venv_python = r"D:\Python\TEXT\LLM_model\venv\Scripts\python.exe"
if sys.executable != venv_python:
    print(f"⚠️  Потрібно запускати через віртуальне середовище: {venv_python}")
    print(f"   Поточний Python: {sys.executable}")
    import subprocess
    result = subprocess.run([venv_python, __file__])
    sys.exit(result.returncode)

def main():
    print("=" * 60)
    print("Прямий тест AgentLoop з GUI чергою")
    print("=" * 60)
    
    # Створити GUI чергу
    gui_queue = queue.Queue()
    
    # Потік для читання GUI черги
    messages = []
    stop_reading = False
    def read_gui_queue():
        while not stop_reading:
            try:
                msg = gui_queue.get(timeout=0.5)
                messages.append(msg)
                print(f"[GUI MESSAGE] {msg}")
                if msg[0] == 'add_message':
                    print(f"  -> {msg[1][0]}: {msg[1][1][:50]}...")
            except queue.Empty:
                continue
    
    # Запустити потік читання
    reader_thread = threading.Thread(target=read_gui_queue, daemon=True)
    reader_thread.start()
    
    # Ініціалізація AssistantCore
    from main import AssistantCore
    
    print("🚀 Ініціалізація AssistantCore...")
    core = AssistantCore()
    
    # Встановити GUI чергу
    core.gui_queue = gui_queue
    
    # Ініціалізація (без listener для тесту)
    print("⏳ Ініціалізація (без listener)...")
    success = core.initialize_without_listener()
    if not success:
        print("❌ Помилка ініціалізації")
        return
    
    print("✅ AssistantCore готовий")
    
    # Перевірка чи AgentLoop існує
    if not hasattr(core, 'agent_loop') or core.agent_loop is None:
        print("❌ AgentLoop не ініціалізовано")
        return
    
    print("✅ AgentLoop готовий")
    
    # Тестова задача
    task = "аналізуй екран"
    print(f"\n📝 Задача: {task}")
    
    # Запуск AgentLoop через process_text_command (як це робить GUI)
    print("🤖 Запуск через process_text_command...")
    try:
        core.process_text_command(task)
        # Зачекати завершення
        time.sleep(30)
    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
    
    # Зупинити читання черги
    stop_reading = True
    reader_thread.join(timeout=2)
    
    # Перевірити повідомлення
    print(f"\n📊 Отримано {len(messages)} повідомлень з GUI черги")
    
    # Перевірити чи є повідомлення користувача
    user_messages = [msg for msg in messages if msg[0] == 'add_message' and msg[1][0] == 'user']
    if user_messages:
        print(f"✅ Знайдено {len(user_messages)} повідомлень користувача:")
        for msg in user_messages:
            print(f"  - {msg[1][1]}")
    else:
        print("❌ Повідомлення користувача НЕ знайдено!")
    
    # Перевірити чи є повідомлення асистента
    assistant_messages = [msg for msg in messages if msg[0] == 'add_message' and msg[1][0] == 'assistant']
    if assistant_messages:
        print(f"✅ Знайдено {len(assistant_messages)} повідомлень асистента:")
        for msg in assistant_messages:
            print(f"  - {msg[1][1][:50]}...")
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    import time
    main()
