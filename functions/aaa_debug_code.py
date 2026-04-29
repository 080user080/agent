"""Автоматичне виправлення помилок в коді."""
import re

import requests
from colorama import Fore

from .config import LM_STUDIO_URL
from .core_tool_runtime import make_tool_result


def llm_function(name, description, parameters):
    """Декоратор для реєстрації функцій"""
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator


class AutoDebugger:
    """Автоматичне виправлення коду"""

    def __init__(self, max_attempts=10):
        self.max_attempts = max_attempts

    def parse_error(self, stderr):
        """Витягти інформацію про помилку"""
        lines = stderr.strip().split("\n")

        error_line = None
        error_type = None
        error_message = None

        for line in reversed(lines):
            if ":" in line and any(err in line for err in ["Error", "Exception"]):
                parts = line.split(":", 1)
                error_type = parts[0].strip()
                error_message = parts[1].strip() if len(parts) > 1 else ""
                break

        for line in lines:
            if "line" in line.lower():
                match = re.search(r"line\s+(\d+)", line, re.IGNORECASE)
                if match:
                    error_line = int(match.group(1))
                    break

        return {
            "type": error_type or "Unknown Error",
            "message": error_message or stderr,
            "line": error_line,
            "full_traceback": stderr,
        }

    def ask_llm_to_fix(self, code, error_info, attempt):
        """Попросити LLM виправити код"""
        print(f"{Fore.YELLOW}🔧 Спроба {attempt}/{self.max_attempts}: виправлення помилки...")

        prompt = f"""Виправ цей Python код. Він має помилку:

**Помилка:** {error_info['type']}
**Повідомлення:** {error_info['message']}
{f"**Рядок:** {error_info['line']}" if error_info['line'] else ""}

**Код з помилкою:**
```python
{code}
```

**Traceback:**
```
{error_info['full_traceback']}
```

Поверни ТІЛЬКИ виправлений код без пояснень. Формат відповіді:
```python
# виправлений код тут
```
"""

        try:
            response = requests.post(
                LM_STUDIO_URL,
                json={
                    "model": "local-model",
                    "messages": [
                        {"role": "system", "content": "Ти експерт з Python. Виправляй код швидко і точно."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2048,
                },
                timeout=60,
            )

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                code_match = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
                if code_match:
                    fixed_code = code_match.group(1).strip()
                    print(f"{Fore.GREEN}   ✅ LLM запропонував виправлення")
                    return fixed_code

                fixed_code = content.strip()
                lines = fixed_code.split("\n")
                code_lines = [l for l in lines if not l.strip().startswith("#") or l.strip().startswith("# ")]
                return "\n".join(code_lines)

            return None

        except Exception as e:
            print(f"{Fore.RED}   ❌ Помилка LLM: {e}")
            return None

    def debug_and_fix(self, code):
        """Виправити код автоматично (до max_attempts спроб)"""
        from .aaa_execute_python import execute_python

        print(f"{Fore.CYAN}🐛 Запуск автодебагера...")
        current_code = code

        for attempt in range(1, self.max_attempts + 1):
            result = execute_python(current_code, f"debug_attempt_{attempt}.py")

            if isinstance(result, dict) and "ok" in result:
                if result.get("ok"):
                    return {
                        "success": True,
                        "fixed_code": current_code,
                        "attempts": attempt,
                        "output": result.get("data", {}).get("output", ""),
                    }
                stderr = result.get("data", {}).get("stderr", "") or result.get("error", "") or result.get("message", "")
            elif isinstance(result, dict):
                if result.get("success"):
                    return {
                        "success": True,
                        "fixed_code": current_code,
                        "attempts": attempt,
                        "output": result.get("output", ""),
                    }
                stderr = result.get("stderr", "") or result.get("error", "")
            else:
                if "✅" in str(result):
                    return {
                        "success": True,
                        "fixed_code": current_code,
                        "attempts": attempt,
                        "output": str(result),
                    }
                stderr = str(result)

            if not stderr:
                break

            error_info = self.parse_error(stderr)

            if attempt >= self.max_attempts:
                break

            fixed_code = self.ask_llm_to_fix(current_code, error_info, attempt)
            if not fixed_code:
                break

            current_code = fixed_code

        return {
            "success": False,
            "attempts": attempt,
            "last_error": error_info if "error_info" in locals() else None,
            "last_code": current_code,
        }


_debugger = AutoDebugger(max_attempts=10)


@llm_function(
    name="debug_python_code",
    description="Автоматично виправити помилки в Python коді (до 10 спроб)",
    parameters={
        "code": "Python код з помилкою"
    }
)
def debug_python_code(code):
    """Автоматичне виправлення коду"""
    result = _debugger.debug_and_fix(code)

    if result["success"]:
        message = (
            f"✅ Код виправлено за {result['attempts']} спроб!\n\n"
            f"**Виправлений код:**\n```python\n{result['fixed_code']}\n```\n\n"
            f"**Результат:**\n{result['output']}"
        )
        return make_tool_result(
            True,
            message,
            data={
                "fixed_code": result["fixed_code"],
                "attempts": result["attempts"],
                "output": result.get("output", ""),
            },
        )

    error = result.get("last_error", {}) or {}
    message = (
        f"❌ Не вдалося виправити код за {result['attempts']} спроб.\n\n"
        f"**Остання помилка:** {error.get('type', 'Unknown')}: {error.get('message', 'N/A')}\n\n"
        f"**Останній код:**\n```python\n{result.get('last_code', code)}\n```"
    )
    return make_tool_result(
        False,
        message,
        data={
            "attempts": result["attempts"],
            "last_error": error,
            "last_code": result.get("last_code", code),
        },
        error=error.get("message", "debug_failed"),
        retryable=True,
    )
