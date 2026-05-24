"""
tools_project_indexer.py — обгортка для реєстрації інструментів індексації проєкту.

Автоматично підхоплюється FunctionRegistry (tools_*.py завантажуються auto).
Імпортує та реекспортує публічні функції з project_indexer.py.
"""

from functions.project_indexer import (
    get_repo_map as _get_repo_map_impl,
    update_file_in_map as _update_file_in_map_impl,
    build_repo_map as _build_repo_map_impl,
    get_file_dependents as _get_file_dependents_impl,
)


def get_repo_map() -> str:
    """
    Отримати компактну карту проєкту (Repo Map).

    Читає runtime/repo_map.json, повертає текст у форматі:
    файл.py → Клас.метод(args), функція(args)

    Якщо карта відсутня — автоматично запускає індексування.
    """
    return _get_repo_map_impl()


def update_repo_map(filepath: str) -> str:
    """
    Оновити інформацію про один файл у Repo Map після змін.

    Args:
        filepath: Шлях до файлу (відносно кореня проєкту).

    Returns:
        "✅ updated" або "❌ error: ..."
    """
    try:
        ok = _update_file_in_map_impl(filepath)
        return "✅ updated" if ok else f"❌ error: file not found or parse error"
    except Exception as e:
        return f"❌ error: {e}"


def rebuild_repo_map() -> str:
    """
    Повністю перебудувати Repo Map (повне сканування проєкту).

    Returns:
        Шлях до збереженого runtime/repo_map.json.
    """
    return _build_repo_map_impl()


def get_file_dependents(filepath: str) -> str:
    """
    Показати всі файли проєкту, які імпортують вказаний файл.

    Args:
        filepath: Відносний шлях до файлу (напр. "functions/core_settings.py")

    Returns:
        Список файлів у форматі:
        "📦 Залежні файли для functions/core_settings.py:
         1. functions/logic_commands.py
         2. main.py"
        Або: "ℹ️ Файл 'X' ніхто не імпортує в проєкті"
        Або: "❌ Помилка: ..."
    """
    try:
        dependents = _get_file_dependents_impl(filepath)
        if not dependents:
            return f"ℹ️ Файл '{filepath}' ніхто не імпортує в проєкті"
        lines = [f"📦 Залежні файли для {filepath}:"]
        for i, dep in enumerate(dependents, 1):
            lines.append(f" {i}. {dep}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Помилка: {e}"
