"""
Скрипт для створення копії user_settings.json без секретів (API ключів).
Використовується для заливання в GitHub без розкриття секретів.
"""
import json
import os

def sync_settings_copy():
    """Створити копію user_settings.json без API ключів."""
    source_path = os.path.join(os.path.dirname(__file__), 'user_settings.json')
    target_path = os.path.join(os.path.dirname(__file__), 'user_settings_copy.json')
    
    try:
        # Читаємо оригінал
        with open(source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Очищаємо API ключі
        for endpoint in data.get('LLM_ENDPOINTS', []):
            endpoint['api_key'] = ''
        
        # Зберігаємо копію
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Копію створено: {target_path}")
        print(f"   API ключі видалено з {len(data.get('LLM_ENDPOINTS', []))} endpoint-ів")
        
    except Exception as e:
        print(f"❌ Помилка: {e}")

if __name__ == '__main__':
    sync_settings_copy()
