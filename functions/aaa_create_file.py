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
    description="створення txt або py файлу (за замовч. на робочому столі)",
    parameters={
        "filename": "назва файлу (можна без .txt) або повний шлях",
        "content": "текстовий вміст файлу"
    }
)
def create_file(filename=None, content="", filepath=None, path=None, name=None):
    """Створити файл (txt/py).

    Підтримує кілька ім'я аргументу (`filename`, `filepath`, `path`, `name`),
    бо LLM іноді плутається у назві параметра.
    """
    try:
        # Нормалізуємо аргумент імені файлу
        target = filename or filepath or path or name
        if not target:
            return make_tool_result(
                False,
                "❌ Не вказано назви файлу (очікувався filename / filepath)",
                error="missing_filename",
            )

        # Якщо шлях не абсолютний — кладемо на робочий стіл
        if not os.path.isabs(target):
            # Якщо немає розширення — додаємо .txt
            if "." not in os.path.basename(target):
                target += ".txt"
            filepath_abs = os.path.join(DESKTOP_PATH, target)
            display_name = target
        else:
            filepath_abs = target
            display_name = os.path.basename(target)
            # Створити батьківську папку якщо треба
            parent = os.path.dirname(filepath_abs)
            if parent:
                os.makedirs(parent, exist_ok=True)

        # Якщо relative-шлях містить каталоги — створюємо їх всередині Desktop
        parent_dir = os.path.dirname(filepath_abs)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(filepath_abs, "w", encoding="utf-8") as f:
            f.write(content or "")

        return make_tool_result(
            True,
            f"✅ Файл створено: {display_name}",
            data={"file_path": filepath_abs, "filename": display_name},
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка створення файлу: {str(e)}",
            error=str(e),
            retryable=True,
        )
