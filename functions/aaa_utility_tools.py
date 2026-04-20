"""Утилітарні функції: create_folder, search_in_text, count_words."""
import os
import re

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
    name="create_folder",
    description="створення нової папки (за замовч. на робочому столі)",
    parameters={
        "folder_name": "назва папки або повний шлях",
    }
)
def create_folder(folder_name=None, path=None, name=None, foldername=None):
    """Створити папку. Якщо шлях відносний — на Desktop."""
    try:
        target = folder_name or foldername or path or name
        if not target:
            return make_tool_result(
                False,
                "❌ Не вказано назви папки (folder_name)",
                error="missing_folder_name",
            )

        if not os.path.isabs(target):
            target_abs = os.path.join(DESKTOP_PATH, target)
            display_name = target
        else:
            target_abs = target
            display_name = os.path.basename(target.rstrip(os.sep))

        os.makedirs(target_abs, exist_ok=True)
        return make_tool_result(
            True,
            f"✅ Папка створена: {display_name}",
            data={"folder_path": target_abs, "folder_name": display_name},
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка створення папки: {str(e)}",
            error=str(e),
            retryable=True,
        )


@llm_function(
    name="search_in_text",
    description="пошук підрядка або регулярного виразу в тексті",
    parameters={
        "text": "текст для пошуку",
        "query": "що шукати (підрядок або regex)",
    }
)
def search_in_text(text="", query="", regex=False, pattern=None, search=None):
    """Шукати query в text. Повертає кількість збігів і позиції."""
    try:
        query = query or pattern or search
        if not query:
            return make_tool_result(
                False,
                "❌ Не вказано що шукати (query)",
                error="missing_query",
            )
        if not text:
            return make_tool_result(
                True,
                "📄 Текст порожній — 0 збігів",
                data={"count": 0, "matches": []},
            )

        if regex:
            matches = [(m.start(), m.group()) for m in re.finditer(query, text)]
        else:
            matches = []
            start = 0
            while True:
                idx = text.find(query, start)
                if idx < 0:
                    break
                matches.append((idx, query))
                start = idx + len(query)

        count = len(matches)
        if count == 0:
            msg = f"🔍 '{query}' не знайдено"
        else:
            positions = ", ".join(str(m[0]) for m in matches[:10])
            msg = f"🔍 '{query}' знайдено {count} раз (позиції: {positions})"
        return make_tool_result(
            True,
            msg,
            data={"count": count, "matches": matches},
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка пошуку: {str(e)}",
            error=str(e),
        )


@llm_function(
    name="count_words",
    description="підрахунок слів у тексті",
    parameters={
        "text": "текст для підрахунку",
    }
)
def count_words(text="", content=None, string=None):
    """Порахувати кількість слів у тексті."""
    try:
        text = text or content or string or ""
        if not text:
            return make_tool_result(
                True,
                "📊 0 слів (текст порожній)",
                data={"words": 0, "chars": 0, "lines": 0},
            )
        words = text.split()
        word_count = len(words)
        char_count = len(text)
        line_count = text.count("\n") + 1
        return make_tool_result(
            True,
            f"📊 Слів: {word_count} | Символів: {char_count} | Рядків: {line_count}",
            data={"words": word_count, "chars": char_count, "lines": line_count},
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка підрахунку: {str(e)}",
            error=str(e),
        )
