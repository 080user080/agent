import os

from .core_tool_runtime import make_tool_result

DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")


def llm_function(name, description, parameters):
    """Декоратор для реєстрації функцій"""
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator


@llm_function(
    name="create_file",
    description="створення txt файлу на робочому столі",
    parameters={
        "filename": "назва файлу (можна без .txt)",
        "content": "текстовий вміст файлу"
    }
)
def create_file(filename, content):
    """Створити txt файл на робочому столі"""
    try:
        if "." not in filename:
            filename += ".txt"

        filepath = os.path.join(DESKTOP_PATH, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return make_tool_result(
            True,
            f"✅ Файл створено: {filename} на робочому столі",
            data={"file_path": filepath, "filename": filename},
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка створення файлу: {str(e)}",
            error=str(e),
            retryable=True,
        )
