"""Тест LLM JSON output без GUI"""
import sys
sys.path.insert(0, 'd:\\Python\\agent')

from functions.logic_llm_tools import ask_llm_with_tools

messages = [
    {"role": "system", "content": "Ти — агент, який аналізує код. Поверни JSON: {\"action\": \"ім'я_інструменту\", \"args\": {...}, \"reasoning\": \"пояснення\"}. Доступні інструменти: list_directory(directory), read_code_file(filepath), done(summary)."},
    {"role": "user", "content": "ЗАДАЧА: проаналізуй код d:\\Python\\agent\nПОТОЧНИЙ КРОК: 0 (максимум 3-5 кроків для аналізу коду)\n\nПОТОЧНЕ СПОСТЕРЕЖЕННЯ ЕКРАНУ:\n(немає спостереження)\n\nОСТАННІ ДІЇ:\n(немає історії)\n\nВиклич ОДИН інструмент для наступного кроку. Якщо задача виконана — виклич `done`."},
]

try:
    response = ask_llm_with_tools(
        messages=messages,
        tools=[],  # Без function-calling
        tool_choice=None,
    )
    print(f"Response type: {type(response)}")
    print(f"Response content: {response.content[:500]}")
    print(f"Response tool_calls: {getattr(response, 'tool_calls', None)}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
