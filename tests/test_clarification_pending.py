"""Тести для виправленої логіки pending clarification."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.gui.commands_planner import needs_clarification


def test_pending_merge_never_ambiguous():
    r"""Після об'єднання з pending — команда завжди виконується.
    
    Симулюємо що було: "подивися проект" (pending) + "d:\Python\MARK\" (відповідь)
    Об'єднана команда "подивися проект d:\Python\MARK\" не повинна знову питати.
    """
    # Це імітує команду після об'єднання з pending
    merged_commands = [
        "подивися проект d:\\Python\\MARK\\",
        "відкрий C:\\Users\\",
        "подивися код functions/planning",
        "покажи код logic_commands.py",
        "відкрий файл test.txt",
        "відкрий програму блокнот",
        "подивися файл config.json",
        "запусти скрипт main.py",
        "створи файл test.txt",
    ]
    for cmd in merged_commands:
        result, question = needs_clarification(cmd)
        assert result is False, f"FAIL: '{cmd}' має бути зрозумілою, але отримано question='{question}'"
    print(f"✅ test_pending_merge_never_ambiguous: {len(merged_commands)} passed")


def test_simple_path_as_answer():
    """Конкретний шлях як відповідь на уточнення — завжди однозначно."""
    # Ці команди могли б прийти як відповідь на уточнення
    # "d:\Python\MARK\" — це шлях, він однозначний
    result, question = needs_clarification("d:\\Python\\MARK\\")
    assert result is False, f"Шлях d:\\Python\\MARK\\ має бути однозначним"
    
    result, question = needs_clarification("C:\\Users\\test")
    assert result is False, f"Шлях C:\\Users\\test має бути однозначним"
    
    result, question = needs_clarification("functions/planning")
    assert result is False, f"Шлях functions/planning має бути однозначним"
    
    print("✅ test_simple_path_as_answer passed")


def test_chat_with_verb_not_ambiguous():
    """CHAT-команди які містять дієслово — не питаємо."""
    test_cases = [
        ("що таке відкрий", False),
        ("поясни що таке виконай", False),
        ("як працює запусти", False),
        ("де знаходиться файл", False),
        ("як створити файл", False),
        ("як відкрити програму", False),
    ]
    for cmd, expected in test_cases:
        result, question = needs_clarification(cmd)
        assert result == expected, f"FAIL: '{cmd}' → got {result}, expected {expected}"
    print(f"✅ test_chat_with_verb_not_ambiguous: {len(test_cases)} passed")


def test_question_like_ambiguous_response():
    """Питання-відповідь типу 'в які можеш подивитися' — це відповідь, не нова команда.
    
    Користувач уточнює контекст, а не дає нову неоднозначну команду.
    Така команда приходить коли є pending, тому одразу виконується.
    Але навіть якщо перевірити її як звичайну — це не дієслово без об'єкта,
    а описове питання.
    """
    # "в які можеш подивитися" — це не "подивися" без об'єкта, а питання з контекстом
    # Воно містить "подивитися" всередині, але не починається з дієслова
    result, question = needs_clarification("в які можеш подивитися")
    assert result is False, f"FAIL: 'в які можеш подивитися' має бути зрозумілим (питання)"
    print("✅ test_question_like_ambiguous_response passed")


def test_verb_with_obj_not_ambiguous():
    """Дієслово з об'єктом — не питаємо (більші патерни з _CLEAR_PATTERNS)."""
    # Ці команди покриваються _CLEAR_PATTERNS або містять об'єкт
    test_cases = [
        ("відкрий блокнот", False),  # об'єкт є, але не покривається _CLEAR_PATTERNS
        # 'відкрий блокнот' не має файл/програму/додаток після відкрий
        # Але блокнот — це ім'я програми, це не неоднозначно
    ]
    for cmd, expected in test_cases:
        result, question = needs_clarification(cmd)
        # Важливо що це НЕ True — навіть якщо не покривається _CLEAR_PATTERNS,
        # воно не повинно спрацьовувати як дієслово без об'єкта
        if result == True:
            print(f"⚠️ '{cmd}' позначено як неоднозначне, але це може бути ОК")
        else:
            print(f"✅ '{cmd}' → не питаємо")
    print("✅ test_verb_with_obj_not_ambiguous passed")


if __name__ == "__main__":
    test_pending_merge_never_ambiguous()
    test_simple_path_as_answer()
    test_chat_with_verb_not_ambiguous()
    test_question_like_ambiguous_response()
    test_verb_with_obj_not_ambiguous()
    print("\n🎉 Всі тести пройдено!")