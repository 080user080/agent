# functions/tools_open_interpreter.py
"""Open Interpreter integration for self-healing code execution.

Provides fallback for execute_python when ModuleNotFoundError occurs.
Uses local LM Studio instead of OpenAI API.
"""
import os
import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class OIResult:
    """Result from Open Interpreter execution."""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0


class OpenInterpreterExecutor:
    """Executor for Open Interpreter with local LM Studio backend."""
    
    def __init__(self, lm_studio_url: str = "http://localhost:1234/v1/chat/completions"):
        """Initialize executor with local LM Studio URL.
        
        Args:
            lm_studio_url: URL of local LM Studio server (OpenAI-compatible)
        """
        self.lm_studio_url = lm_studio_url
        self._interpreter = None
        self._initialized = False
    
    def _initialize(self) -> bool:
        """Initialize Open Interpreter with local LM Studio.
        
        Returns:
            True if successful, False otherwise
        """
        if self._initialized:
            return True
        
        try:
            # Import interpreter (lazy import to avoid dependency issues)
            from interpreter import interpreter
            
            # Configure to use local LM Studio instead of OpenAI
            interpreter.llm.model = "local"
            interpreter.llm.api_base = self.lm_studio_url.replace("/chat/completions", "")
            interpreter.llm.api_key = ""  # No API key for local
            interpreter.llm.temperature = 0.1
            interpreter.llm.max_tokens = 2048
            
            # Disable auto-run for safety (will be controlled by auto_run parameter)
            interpreter.auto_run = False
            
            self._interpreter = interpreter
            self._initialized = True
            return True
            
        except ImportError as e:
            print(f"⚠️ Open Interpreter не встановлено: {e}")
            return False
        except Exception as e:
            print(f"⚠️ Помилка ініціалізації Open Interpreter: {e}")
            return False
    
    def execute_with_healing(
        self,
        code: str,
        task_description: str,
        auto_run: bool = True
    ) -> OIResult:
        """Execute code with self-healing via Open Interpreter.
        
        When ModuleNotFoundError occurs in normal execute_python,
        OI can install missing packages and retry.
        
        Args:
            code: Python code to execute
            task_description: Description of what the code should do (helps OI understand context)
            auto_run: If True, OI will auto-run installation commands
            
        Returns:
            OIResult with success status, output, and error if any
        """
        import time
        
        if not self._initialize():
            return OIResult(
                success=False,
                output="",
                error="Open Interpreter не вдалося ініціалізувати"
            )
        
        start_time = time.time()
        
        try:
            # Build prompt for Open Interpreter
            prompt = f"""Task: {task_description}

Code to execute:
```python
{code}
```

Please execute this code. If you encounter ModuleNotFoundError, install the missing package using pip and retry the execution.
"""
            
            # Execute via Open Interpreter
            if auto_run:
                # Use chat method with auto-run
                result = self._interpreter.chat(prompt, display=False)
            else:
                # Use chat without auto-run (safer)
                result = self._interpreter.chat(prompt, display=False)
            
            execution_time = time.time() - start_time
            
            # Parse result
            if result and hasattr(result, 'content'):
                output = str(result.content)
                return OIResult(
                    success=True,
                    output=output,
                    execution_time=execution_time
                )
            else:
                output = str(result) if result else "No output"
                return OIResult(
                    success=True,
                    output=output,
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            return OIResult(
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time
            )


# Singleton instance
_executor: Optional[OpenInterpreterExecutor] = None


def get_executor(lm_studio_url: Optional[str] = None) -> OpenInterpreterExecutor:
    """Get singleton Open Interpreter executor.
    
    Args:
        lm_studio_url: Optional custom LM Studio URL
        
    Returns:
        OpenInterpreterExecutor instance
    """
    global _executor
    
    if _executor is None:
        # Get LM Studio URL from settings if not provided
        if lm_studio_url is None:
            from .core_settings import get_setting
            lm_studio_url = get_setting("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
        
        _executor = OpenInterpreterExecutor(lm_studio_url=lm_studio_url)
    
    return _executor


def oi_execute_with_healing(
    code: str,
    task_description: str,
    auto_run: bool = True
) -> OIResult:
    """Execute code with self-healing via Open Interpreter.
    
    This is the main entry point for OI integration.
    Should be called when execute_python fails with ModuleNotFoundError.
    
    Args:
        code: Python code that failed to execute
        task_description: What the code should do (helps OI understand)
        auto_run: If True, OI will auto-run installation commands
        
    Returns:
        OIResult with execution results
    """
    from .core_settings import get_setting
    
    # Check if OI is enabled
    if not get_setting("OI_ENABLED", False):
        return OIResult(
            success=False,
            output="",
            error="Open Interpreter вимкнено в налаштуваннях (OI_ENABLED=False)"
        )
    
    executor = get_executor()
    return executor.execute_with_healing(code, task_description, auto_run)


def is_available() -> bool:
    """Check if Open Interpreter is available and enabled.
    
    Returns:
        True if OI can be used, False otherwise
    """
    from .core_settings import get_setting
    
    if not get_setting("OI_ENABLED", False):
        return False
    
    try:
        from interpreter import interpreter
        return True
    except ImportError:
        return False
