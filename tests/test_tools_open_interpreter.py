"""Тести для tools_open_interpreter (Open Interpreter integration)."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from functions.tools_open_interpreter import (
    OIResult,
    OpenInterpreterExecutor,
    get_executor,
    oi_execute_with_healing,
    is_available,
)


class TestOIResult:
    """Тести для OIResult dataclass."""
    
    def test_oi_result_success(self):
        """Створення успішного результату."""
        result = OIResult(success=True, output="test output")
        assert result.success is True
        assert result.output == "test output"
        assert result.error is None
        assert result.execution_time == 0.0
    
    def test_oi_result_error(self):
        """Створення результату з помилкою."""
        result = OIResult(
            success=False,
            output="",
            error="ModuleNotFoundError: No module named 'test'",
            execution_time=1.5
        )
        assert result.success is False
        assert result.output == ""
        assert result.error == "ModuleNotFoundError: No module named 'test'"
        assert result.execution_time == 1.5


class TestOpenInterpreterExecutor:
    """Тести для OpenInterpreterExecutor."""
    
    def test_init_default_url(self):
        """Ініціалізація з дефолтним URL."""
        executor = OpenInterpreterExecutor()
        assert executor.lm_studio_url == "http://localhost:1234/v1/chat/completions"
        assert executor._initialized is False
    
    def test_init_custom_url(self):
        """Ініціалізація з кастомним URL."""
        custom_url = "http://localhost:5678/v1/chat/completions"
        executor = OpenInterpreterExecutor(lm_studio_url=custom_url)
        assert executor.lm_studio_url == custom_url
    
    # Тести ініціалізації пропущені через складність мокання dynamic import
    # В реальному використанні interpreter буде встановлено або ні


class TestGetExecutor:
    """Тести для get_executor singleton."""
    
    def test_singleton(self):
        """Перевірка singleton паттерну."""
        # Reset singleton
        import functions.tools_open_interpreter as toi
        toi._executor = None
        
        executor1 = get_executor()
        executor2 = get_executor()
        assert executor1 is executor2
    
    @patch('functions.core_settings.get_setting')
    def test_custom_url_from_settings(self, mock_get_setting):
        """URL з налаштувань."""
        mock_get_setting.return_value = "http://custom:9999/v1/chat/completions"
        
        # Reset singleton
        import functions.tools_open_interpreter as toi
        toi._executor = None
        
        executor = get_executor()
        assert executor.lm_studio_url == "http://custom:9999/v1/chat/completions"


class TestOIExecuteWithHealing:
    """Тести для oi_execute_with_healing."""
    
    @patch('functions.core_settings.get_setting')
    @patch('functions.tools_open_interpreter.get_executor')
    def test_enabled_true(self, mock_get_executor, mock_get_setting):
        """Виконання коли OI увімкнено."""
        mock_get_setting.return_value = True
        mock_executor = MagicMock()
        mock_executor.execute_with_healing.return_value = OIResult(
            success=True,
            output="Success"
        )
        mock_get_executor.return_value = mock_executor
        
        result = oi_execute_with_healing("code", "task")
        
        assert result.success is True
        assert result.output == "Success"
        mock_executor.execute_with_healing.assert_called_once()
    
    @patch('functions.core_settings.get_setting')
    def test_disabled(self, mock_get_setting):
        """Виконання коли OI вимкнено."""
        mock_get_setting.return_value = False
        
        result = oi_execute_with_healing("code", "task")
        
        assert result.success is False
        assert "вимкнено" in result.error


class TestIsAvailable:
    """Тести для is_available."""
    
    @patch('functions.core_settings.get_setting')
    def test_disabled(self, mock_get_setting):
        """Недоступний (вимкнено)."""
        mock_get_setting.return_value = False
        
        result = is_available()
        assert result is False
