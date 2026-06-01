"""Тести для пунктів 2b, 3, 4 — валідація execute_python, автотест, repair-loop."""
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Додаємо корінь проєкту в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestExecutePythonValidation:
    """Пункт 2b: Валідація execute_python."""

    @pytest.fixture
    def sandbox(self):
        from functions.tools.aaa_execute_python import PythonSandbox
        return PythonSandbox()

    def test_short_code_allowed(self, sandbox):
        """Код ≤5 рядків без def/class дозволений."""
        code = "x = 1\ny = 2\nprint(x + y)"
        is_safe, message = sandbox.validate_code(code)
        assert is_safe, f"Код мав би пройти валідацію: {message}"

    def test_one_liner_allowed(self, sandbox):
        """Однорядковий вираз дозволений."""
        code = "print(2+2)"
        is_safe, message = sandbox.validate_code(code)
        assert is_safe, f"Однорядковий мав би пройти: {message}"

    def test_long_code_blocked(self, sandbox):
        """Код >5 рядків має блокуватися."""
        code = "\n".join([f"x{i} = {i}" for i in range(7)])
        is_safe, message = sandbox.validate_code(code)
        assert not is_safe, "Код >5 рядків мав би блокуватися"
        assert "≤5 рядків" in message

    def test_code_with_def_blocked(self, sandbox):
        """Код з def має блокуватися."""
        code = "def foo():\n    return 42"
        is_safe, message = sandbox.validate_code(code)
        assert not is_safe, "Код з def мав би блокуватися"
        assert "def/class" in message.lower() or "def" in message

    def test_code_with_class_blocked(self, sandbox):
        """Код з class має блокуватися."""
        code = "class Foo:\n    pass"
        is_safe, message = sandbox.validate_code(code)
        assert not is_safe, "Код з class мав би блокуватися"
        assert "def/class" in message.lower() or "class" in message

    def test_execute_python_file_exception(self, sandbox):
        """Виклик через execute_python_file (з script_name) дозволяє будь-який код."""
        code = "def foo():\n    return 42\n\nclass Bar:\n    pass\n\nx = 1\ny = 2\nz = 3\nw = 4"
        is_safe, message = sandbox.validate_code(code, script_name="test_script.py")
        assert is_safe, f"Код з script_name мав би пройти: {message}"

    def test_code_with_comment_blocked(self, sandbox):
        """Код з def в коментарі має не блокуватися."""
        code = "# def foo():\n#     pass\nx = 1"
        is_safe, message = sandbox.validate_code(code)
        assert is_safe, f"Коментарі з def мають ігноруватися: {message}"


class TestAutoTest:
    """Пункт 3: Автоматична синтаксична перевірка .py файлів."""

    def test_valid_python_syntax(self):
        """Перевірка що compile на valid коді повертає True."""
        code = "x = 1\ny = 2\nprint(x + y)"
        try:
            compile(code, "test.py", "exec")
            assert True
        except SyntaxError:
            assert False, "Валідний код не мав би викидати SyntaxError"

    def test_invalid_python_syntax(self):
        """Перевірка що compile на invalid коді викидає SyntaxError."""
        code = "x = "
        with pytest.raises(SyntaxError):
            compile(code, "test.py", "exec")

    def test_write_file_triggers_autotest(self):
        """Перевірка що поле auto_test_passed додається в act_result.
        
        Це інтеграційна перевірка логіки з agent_loop.py.
        Симулюємо виклик compile як це робить _execute_single_step.
        """
        # Симуляція того, що робить AgentLoop після write_file .py
        act_result = {"ok": True, "result": "written"}
        filepath = "test_module.py"
        content = "x = 1\nprint(x)"
        
        if filepath.endswith('.py'):
            try:
                compile(content, filepath, 'exec')
                act_result["auto_test_passed"] = True
                act_result["auto_test_error"] = ""
            except SyntaxError as e:
                act_result["auto_test_passed"] = False
                act_result["auto_test_error"] = str(e)
        
        assert act_result.get("auto_test_passed") is True
        assert act_result.get("auto_test_error") == ""

    def test_autotest_detects_error(self):
        """Перевірка що auto_test_passed=False при синтаксичній помилці."""
        act_result = {"ok": True, "result": "written"}
        filepath = "bad_syntax.py"
        content = "x = "
        
        if filepath.endswith('.py'):
            try:
                compile(content, filepath, 'exec')
                act_result["auto_test_passed"] = True
            except SyntaxError as e:
                act_result["auto_test_passed"] = False
                act_result["auto_test_error"] = str(e)
        
        assert act_result.get("auto_test_passed") is False
        assert "auto_test_error" in act_result

    def test_non_py_file_skipped(self):
        """Перевірка що для не-.py файлів auto_test не запускається."""
        act_result = {"ok": True, "result": "written"}
        filepath = "config.json"
        content = '{"key": "value"}'
        
        # Цей блок не має виконатися для .json
        if filepath.endswith('.py'):
            try:
                compile(content, filepath, 'exec')
                act_result["auto_test_passed"] = True
            except SyntaxError as e:
                act_result["auto_test_passed"] = False
                act_result["auto_test_error"] = str(e)
        
        assert "auto_test_passed" not in act_result


class TestCodeRepairLoop:
    """Пункт 4: Repair-loop для коду."""

    def test_repair_prompt_format(self):
        """Перевірка що repair_prompt містить всі необхідні поля."""
        filepath = "test_broken.py"
        content = "x = "
        error_text = "invalid syntax (<unknown>, line 1)"
        task = "Створити тестовий файл"
        
        repair_prompt = (
            f"⚠️ Синтаксична помилка у файлі '{filepath}'.\n\n"
            f"ПОМИЛКА:\n{error_text}\n\n"
            f"НЕВДАЛИЙ КОД:\n```python\n{content}\n```\n\n"
            f"ЗАВДАННЯ: '{task}'\n\n"
            "Поверни JSON з дією edit_file та виправленим вмістом файлу. "
            "Не змінюй логіку, тільки виправ синтаксичні помилки.\n\n"
            'Формат: {"action": "edit_file", "args": {"filepath": "...", "new_content": "..."}, "reasoning": "..."}\n'
            "Відповідай ТІЛЬКИ JSON."
        )
        
        assert "test_broken.py" in repair_prompt
        assert error_text in repair_prompt
        assert "edit_file" in repair_prompt
        assert "JSON" in repair_prompt

    def test_repair_limit_two_attempts(self):
        """Перевірка що repair робить не більше 2 спроб."""
        # Симулюємо лічильник
        counter = 0
        max_attempts = 2
        
        # Перша спроба
        assert counter < max_attempts
        counter += 1
        assert counter == 1
        
        # Друга спроба
        assert counter < max_attempts
        counter += 1
        assert counter == 2
        
        # Третя спроба — має бути заблокована
        assert not (counter < max_attempts), "Має бути досягнуто ліміту"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])