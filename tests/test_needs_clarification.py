"""Тести для needs_clarification + pending context."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.gui.commands_planner import needs_clarification


def test_clear_commands():
    """Чіткі команди — без питань."""
    test_cases = [
        ("привіт", False),
        ("hello", False),
        ("порахуй 2+2", False),
        ("скільки буде 5*5", False),
        ("як тебе звати", False),
        ("що таке Python", False),
        ("поясни як працює список", False),
        ("відкрий файл config.json", False),
        ("відкрий програму блокнот", False),
        ("подивися файл logic_commands.py", False),
        ("подивись код у functions/planning", False),
        ("запусти програму калькулятор", False),
        ("напиши код для читання файлу", False),
        ("створи файл test.txt", False),
        ("створи папку проекту", False),
        ("виконай команду dir", False),
        ("виконай скрипт main.py", False),
        ("клікни на кнопку Пуск", False),
        ("створи функцію parse_json", False),
    ]
    for cmd, expected in test_cases:
        result, question = needs_clarification(cmd)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            print(f"{status} '{cmd}' → got {result}, expected {expected}")
        assert ok, f"FAIL: '{cmd}' → got {result}, expected {expected}"
    print(f"✅ test_clear_commands: {len(test_cases)} passed")


def test_ambiguous_verbs():
    """Дієслова без об'єкта — питаємо."""
    test_cases = [
        ("відкрий", True),
        ("подивися", True),
        ("подивись", True),
        ("виконай", True),
        ("запусти", True),
        ("покажи", True),
        ("перевір", True),
        ("напиши", True),
        ("створи", True),
        ("знайди", True),
        ("встав", True),
        ("скопіюй", True),
        ("видали", True),
        ("відкрий будь ласка", True),
        ("відкрий, будь ласка", True),
        ("запусти please", True),
        ("виконай.", True),
        ("відкрий!", True),
    ]
    for cmd, expected in test_cases:
        result, question = needs_clarification(cmd)
        ok = result == expected and (not expected or question)
        status = "✅" if ok else "❌"
        if not ok:
            detail = f"question='{question}'" if result else "no question"
            print(f"{status} '{cmd}' → got {result} ({detail}), expected {expected}")
        assert ok, f"FAIL: '{cmd}' → got {result}"
    print(f"✅ test_ambiguous_verbs: {len(test_cases)} passed")


def test_ambiguous_demonstrative():
    """Вказівні займенники — питаємо."""
    test_cases = [
        ("зроби це", True),
        ("зроби те", True),
        ("виправ це", True),
        ("виправ", True),
        ("поправ", True),
        ("перероби", True),
        ("перепиши", True),
    ]
    for cmd, expected in test_cases:
        result, question = needs_clarification(cmd)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            print(f"{status} '{cmd}' → got {result}, expected {expected}")
        assert ok, f"FAIL: '{cmd}' → got {result}"
    print(f"✅ test_ambiguous_demonstrative: {len(test_cases)} passed")


def test_project_without_object():
    """'подивися код' / 'покажи проект' без об'єкта — питаємо."""
    test_cases = [
        ("подивися код", True),
        ("подивись код", True),
        ("покажи проект", True),
        ("покажи код", True),
        ("відкрий код", True),
        ("відкрий проект", True),
        ("подивися проект", True),
    ]
    for cmd, expected in test_cases:
        result, question = needs_clarification(cmd)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            print(f"{status} '{cmd}' → got {result}, expected {expected}")
        assert ok, f"FAIL: '{cmd}' → got {result}"
    print(f"✅ test_project_without_object: {len(test_cases)} passed")


def test_chat_never_ambiguous():
    """CHAT команди — ніколи не питаємо, навіть якщо виглядають неоднозначно."""
    test_cases = [
        ("що таке відкрий", False),
        ("поясни що таке виконай", False),
        ("як працює запусти", False),
    ]
    for cmd, expected in test_cases:
        result, question = needs_clarification(cmd)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            print(f"{status} '{cmd}' → got {result}, expected {expected}")
        assert ok, f"FAIL: '{cmd}' → got {result}"
    print(f"✅ test_chat_never_ambiguous: {len(test_cases)} passed")


def test_question_pattern():
    """Прямі питання — ніколи не питаємо."""
    test_cases = [
        ("як відкрити файл", False),
        ("чому не працює", False),
        ("коли запустити", False),
        ("де лежить файл", False),
        ("хто створив", False),
        ("куди вставити текст", False),
        ("для чого це", False),
        ("навіщо це потрібно", False),
    ]
    for cmd, expected in test_cases:
        result, question = needs_clarification(cmd)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            print(f"{status} '{cmd}' → got {result}, expected {expected}")
        assert ok, f"FAIL: '{cmd}' → got {result}"
    print(f"✅ test_question_pattern: {len(test_cases)} passed")


def test_empty_input():
    """Порожній ввід — без питань."""
    result, question = needs_clarification("")
    assert result is False
    result, question = needs_clarification(None)
    assert result is False
    print("✅ test_empty_input passed")


if __name__ == "__main__":
    test_clear_commands()
    test_ambiguous_verbs()
    test_ambiguous_demonstrative()
    test_project_without_object()
    test_chat_never_ambiguous()
    test_question_pattern()
    test_empty_input()
    print("\n🎉 Всі тести пройдено!")