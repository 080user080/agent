"""Тести для core_planner.py

Запуск: python -m pytest tests/test_core_planner.py -v
"""
import pytest
import sys
import os

# Додаємо parent directory в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.core_planner import Planner


class MockAssistant:
    """Мок-об'єкт для тестів планера."""

    def __init__(self):
        self.conversation_history = []
        self.system_prompt = "Ти тестовий асистент."

    def ask_llm(self, prompt: str) -> str:
        """Мок LLM — повертає відповіді для тестів."""
        # За замовчуванням повертаємо простий план
        return '[{"action": "create_file", "args": {"filename": "test.txt", "content": "hello"}}]'


@pytest.fixture
def planner():
    """Фікстура для створення планера."""
    assistant = MockAssistant()
    return Planner(assistant)


class TestShouldPlan:
    """Тести для методу should_plan."""

    def test_should_plan_multistep_task(self, planner):
        """Повинен планувати багатокрокові задачі."""
        task = "Спочатку створи файл, потім відкрий його, далі відсортуй"
        assert planner.should_plan(task) is True

    def test_should_plan_coding_task(self, planner):
        """Повинен планувати кодові задачі."""
        task = "Знайди функцію в коді і виправи баг"
        assert planner.should_plan(task) is True

    def test_should_not_plan_simple_task(self, planner):
        """Не повинен планувати прості задачі."""
        task = "Привіт"
        assert planner.should_plan(task) is False

    def test_should_not_plan_short_task(self, planner):
        """Не повинен планувати короткі задачі."""
        task = "2+2"
        assert planner.should_plan(task) is False


class TestIsCodingTask:
    """Тести для детекції кодових задач."""

    def test_coding_task_with_code(self, planner):
        """Повинен розпізнати кодову задачу."""
        task = "Прочитай файл main.py і знайди функцію hello"
        assert planner._is_coding_task(task) is True

    def test_coding_task_with_refactor(self, planner):
        """Повинен розпізнати рефакторинг."""
        task = "Рефакторинг коду в utils.py"
        assert planner._is_coding_task(task) is True

    def test_non_coding_task(self, planner):
        """Не повинен розпізнати звичайну задачу як кодову."""
        task = "Створи список покупок"
        assert planner._is_coding_task(task) is False


class TestExtractJson:
    """Тести для витягання JSON з відповідей LLM."""

    def test_extract_json_array(self, planner):
        """Витягує JSON-масив."""
        text = '[{"action": "create_file", "args": {}}]'
        result = planner._extract_json(text)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["action"] == "create_file"

    def test_extract_json_from_code_block(self, planner):
        """Витягує JSON з markdown блоку."""
        text = '```json\n[{"action": "test"}]\n```'
        result = planner._extract_json(text)
        assert isinstance(result, list)

    def test_extract_json_with_extra_text(self, planner):
        """Витягує JSON навколо тексту."""
        text = 'Ось план:\n[{"action": "test"}]\nГотово!'
        result = planner._extract_json(text)
        assert isinstance(result, list)

    def test_extract_json_invalid_returns_none(self, planner):
        """Повертає None для невалідного JSON."""
        text = "це не json"
        result = planner._extract_json(text)
        assert result is None


class TestNormalizePlan:
    """Тести для нормалізації плану."""

    def test_normalize_valid_plan(self, planner):
        """Нормалізує валідний план."""
        raw = [
            {"action": "create_file", "args": {"filename": "test.txt"}},
            {"action": "read_file", "args": {"filepath": "test.txt"}},
        ]
        result = planner.normalize_plan(raw)
        assert len(result) == 2
        assert result[0]["action"] == "create_file"

    def test_normalize_with_goal_and_validation(self, planner):
        """Зберігає goal і validation поля."""
        raw = [
            {
                "action": "test",
                "args": {},
                "goal": "test goal",
                "validation": "test validation",
            }
        ]
        result = planner.normalize_plan(raw)
        assert result[0]["goal"] == "test goal"
        assert result[0]["validation"] == "test validation"

    def test_normalize_empty_returns_empty(self, planner):
        """Повертає пустий список для пустого вводу."""
        assert planner.normalize_plan([]) == []
        assert planner.normalize_plan(None) == []
        assert planner.normalize_plan({}) == []


class TestCreatePlan:
    """Тести для створення плану (інтеграційні)."""

    def test_create_plan_returns_list(self, planner):
        """Повинен повертати список кроків."""
        plan = planner.create_plan("Створи файл test.txt з текстом 'hello'")
        assert isinstance(plan, list)

    def test_create_plan_with_mock_response(self, planner):
        """Тест з контрольованим mock-відповіддю."""
        # Підміняємо ask_llm для цього тесту
        planner.assistant.ask_llm = lambda prompt: '[{"action": "create_file", "filename": "test.txt", "content": "hello"}]'

        plan = planner.create_plan("Створи файл")
        assert len(plan) > 0
        assert plan[0]["action"] == "create_file"


class TestValidateStep:
    """Тести для валідації кроків."""

    def test_validate_successful_step(self, planner):
        """Валідує успішний крок."""
        success, message = planner._validate_step(
            "create_file",
            {"filename": "test.txt"},
            {"success": True, "message": "✅ Файл створено"},
            {},
        )
        assert success is True
        assert "✅" in message

    def test_validate_failed_step(self, planner):
        """Валідує провалений крок."""
        success, message = planner._validate_step(
            "create_file",
            {"filename": "test.txt"},
            {"success": False, "error": "❌ Помилка"},
            {},
        )
        assert success is False
        assert "❌" in message or "⚠️" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
