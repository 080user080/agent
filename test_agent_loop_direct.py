#!/usr/bin/env python3
"""
Прямий тест AgentLoop без GUI.

Перевіряє чи AgentLoop працює з реальною задачею.
"""
import sys
import os

# Додаємо шлях до functions
sys.path.insert(0, r"d:\Python\agent")

def main():
    print("=" * 60)
    print("Прямий тест AgentLoop")
    print("=" * 60)
    
    # Ініціалізація AssistantCore
    from main import AssistantCore
    
    print("🚀 Ініціалізація AssistantCore...")
    core = AssistantCore()
    
    # Ініціалізація
    print("⏳ Ініціалізація...")
    success = core.initialize()
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
    task = "проаналізуй код d:\\Python\\agent"
    print(f"\n📝 Задача: {task}")
    
    # Запуск AgentLoop
    print("🤖 Запуск AgentLoop...")
    try:
        result = core.run_agent_loop(task)
        print(f"✅ AgentLoop завершено: {result}")
    except Exception as e:
        print(f"❌ Помилка AgentLoop: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    main()
