import os
import shutil
from datetime import datetime

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


@llm_function(
    name="edit_file",
    description="редагування txt або py файлів з автоматичним бекапом",
    parameters={
        "filepath": "повний шлях до файлу або назва файлу на робочому столі",
        "new_content": "новий вміст файлу (повністю замінить старий)"
    }
)
def edit_file(filepath, new_content):
    """Редагувати файл з бекапом. Якщо файл не існує — створити його (upsert)."""
    try:
        if not os.path.isabs(filepath):
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            filepath = os.path.join(desktop, filepath)

        if not filepath.endswith((".txt", ".py")):
            return make_tool_result(
                False,
                "❌ Можна редагувати тільки .txt або .py файли",
                error="unsupported_extension",
            )

        filename = os.path.basename(filepath)
        file_existed = os.path.exists(filepath)

        # Якщо файлу немає — створюємо новий (upsert). Це запобігає зацикленню,
        # коли planner плутає create_file/edit_file.
        if not file_existed:
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return make_tool_result(
                True,
                f"✅ Файл створено: {filename}",
                data={"file_path": filepath, "filename": filename, "created": True},
            )

        # Файл існує — робимо бекап і редагуємо
        backup_dir = os.path.join(os.path.dirname(filepath), "backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{filename}.backup_{timestamp}")

        shutil.copy2(filepath, backup_path)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        return make_tool_result(
            True,
            f"✅ Файл відредаговано: {filename}\n📦 Бекап збережено: {os.path.basename(backup_path)}",
            data={"file_path": filepath, "backup_path": backup_path, "filename": filename},
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка редагування: {str(e)}",
            error=str(e),
            retryable=True,
        )
