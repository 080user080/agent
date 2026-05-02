#!/usr/bin/env python3
"""
Тест для діагностики LLM endpoint.

ПОСТІЙНИЙ ТЕСТ - НЕ ВИДАЛЯТИ!
Використовується для перевірки доступності та роботи LLM endpoints.
"""
import sys
import os
sys.path.insert(0, r"d:\Python\agent")

def test_endpoint():
    print("=" * 60)
    print("Тест LLM Endpoint")
    print("=" * 60)
    
    # Отримуємо endpoint з налаштувань
    from functions.core_settings import get_setting
    endpoints = get_setting("LLM_ENDPOINTS", [])
    
    print(f"\nЗнайдено {len(endpoints)} endpoint(s):")
    for i, ep in enumerate(endpoints):
        print(f"\n[{i}] {ep.get('name', 'unnamed')}")
        print(f"    Role: {ep.get('role')}")
        print(f"    Type: {ep.get('type')}")
        print(f"    URL: {ep.get('url')}")
        print(f"    Model: {ep.get('model')}")
    
    # Знаходимо primary endpoint
    primary = None
    for ep in endpoints:
        role = ep.get("role")
        if role == "1" or role == "primary":
            primary = ep
            break
    
    if not primary and endpoints:
        primary = endpoints[0]
    
    if not primary:
        print("\n❌ Не знайдено жодного endpoint")
        return False
    
    print(f"\n🎯 Primary endpoint: {primary.get('name')}")
    print(f"    URL: {primary.get('url')}")
    print(f"    Model: {primary.get('model')}")
    
    # Тестуємо endpoint через provider
    try:
        from functions.providers_openai_compatible import OpenAICompatibleProvider
        from functions.logic_ai_adapter import ChatRequest, ChatMessage
        
        provider = OpenAICompatibleProvider(
            base_url=primary.get("url").replace("/chat/completions", ""),
            api_key=primary.get("api_key") or "",
            model=primary.get("model"),
        )
        
        test_message = "Привіт! Відповідь одним словом: так."
        print(f"\n📤 Тестовий запит: '{test_message}'")
        
        response = provider.chat(ChatRequest(
            messages=[ChatMessage(role="user", content=test_message)]
        ))
        
        print(f"\n📥 Response status: {response.finish_reason}")
        print(f"    Content: {response.content[:100] if response.content else '(пусто)'}")
        
        if response.error:
            print(f"❌ Error: {response.error}")
            return False
        
        if not response.content:
            print("❌ Порожня відповідь")
            return False
        
        print("✅ Endpoint працює коректно")
        return True
        
    except Exception as e:
        print(f"\n❌ Помилка при тестуванні: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_endpoint()
    sys.exit(0 if success else 1)
