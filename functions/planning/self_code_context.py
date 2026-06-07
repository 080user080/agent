"""self_code_context — Self-context builder та Gap analyzer (Phase 1.1-1.2).

Дає агенту здатність аналізувати власний код та визначати
що треба змінити/додати для виконання задачі.

Phase: Self-Coding Agent Pipeline — Фаза 1.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("self_code_context")


def build_self_context(task: str) -> Dict[str, Any]:
    """Побудувати контекст для LLM на основі поточного стану коду.

    Використовує існуючі ``get_repo_map()``, ``search_in_code()``,
    ``read_code_file()`` з ``aaa_code_tools.py``.

    Args:
        task: Текст задачі яку треба виконати.

    Returns:
        Dict з ключами:
          - ``task``: вихідна задача
          - ``repo_map``: карта проєкту (якщо доступна)
          - ``relevant_files``: список релевантних файлів
          - ``file_contents``: {filepath: content} для релевантних файлів
          - ``errors``: список помилок під час збору контексту
    """
    context: Dict[str, Any] = {
        "task": task,
        "repo_map": "",
        "relevant_files": [],
        "file_contents": {},
        "errors": [],
    }

    # 1. Отримати карту проєкту
    try:
        from functions.project_indexer import get_repo_map
        repo_map = get_repo_map()
        context["repo_map"] = repo_map or ""
    except Exception as e:
        logger.debug("build_self_context: get_repo_map failed: %s", e)
        context["errors"].append(f"repo_map: {e}")

    # 2. Пошук релевантних файлів (якщо доступний aaa_code_tools)
    try:
        from functions.tools.aaa_code_tools import search_in_code
        # Простий пошук по ключових словах з задачі
        keywords = _extract_keywords(task)
        for keyword in keywords[:5]:  # максимум 5 пошуків
            try:
                results = search_in_code(
                    pattern=keyword,
                    directory=".",
                    file_pattern="*.py",
                )
                if isinstance(results, dict) and results.get("ok"):
                    for match in results.get("matches", []):
                        filepath = match.get("file", "")
                        if filepath and filepath not in context["relevant_files"]:
                            context["relevant_files"].append(filepath)
            except Exception as e:
                logger.debug("search_in_code error for '%s': %s", keyword, e)
    except ImportError:
        logger.debug("aaa_code_tools not available for search")
    except Exception as e:
        context["errors"].append(f"search: {e}")

    # 3. Читання релевантних файлів (максимум 5 найважливіших)
    try:
        from functions.tools.aaa_code_tools import read_code_file
        for filepath in context["relevant_files"][:5]:
            try:
                result = read_code_file(filepath=filepath, max_lines=200)
                if isinstance(result, dict) and result.get("ok"):
                    context["file_contents"][filepath] = result.get("content", "")
                elif isinstance(result, str):
                    context["file_contents"][filepath] = result
            except Exception as e:
                logger.debug("read_code_file error for '%s': %s", filepath, e)
    except ImportError:
        logger.debug("aaa_code_tools not available for reading")
    except Exception as e:
        context["errors"].append(f"read: {e}")

    logger.info(
        "build_self_context: task='%s', files=%d, errors=%d",
        task[:50], len(context["file_contents"]), len(context["errors"]),
    )
    return context


def analyze_gap(
    task: str,
    context: Dict[str, Any],
    llm_callback=None,
) -> Dict[str, Any]:
    """Визначити що треба змінити/додати для виконання задачі.

    Через LLM аналізує поточний контекст та повертає список
    файлів для зміни з описом змін.

    Args:
        task: Текст задачі.
        context: Контекст від ``build_self_context()``.
        llm_callback: Функція ``(messages) -> str`` для виклику LLM.
            Якщо None — повертає базовий аналіз без LLM.

    Returns:
        Dict з ключами:
          - ``files_to_change``: [{filepath, description, action}]
          - ``summary``: короткий підсумок
          - ``needs_llm``: чи потрібен LLM для фінального аналізу
    """
    result: Dict[str, Any] = {
        "files_to_change": [],
        "summary": "",
        "needs_llm": llm_callback is None,
    }

    # Якщо немає LLM — повертаємо базовий аналіз
    if llm_callback is None:
        result["summary"] = (
            "Потрібен LLM для аналізу. "
            "Поточний контекст: "
            f"{len(context.get('file_contents', {}))} файлів, "
            f"{len(context.get('relevant_files', []))} релевантних."
        )
        result["needs_llm"] = True
        return result

    # Формуємо промпт для LLM
    prompt = _build_gap_analysis_prompt(task, context)

    try:
        response = llm_callback([
            {"role": "system", "content": (
                "Ти — аналітик коду. Проаналізуй задачу та поточний стан коду. "
                "Поверни JSON з полями: files_to_change (список), summary (рядок)."
            )},
            {"role": "user", "content": prompt},
        ])

        if isinstance(response, str):
            import json as _json
            try:
                data = _json.loads(response)
                result["files_to_change"] = data.get("files_to_change", [])
                result["summary"] = data.get("summary", "")
            except _json.JSONDecodeError:
                result["summary"] = response[:500]
        elif isinstance(response, dict):
            result["files_to_change"] = response.get("files_to_change", [])
            result["summary"] = response.get("summary", "")
    except Exception as e:
        logger.warning("analyze_gap LLM call failed: %s", e)
        result["summary"] = f"LLM помилка: {e}"

    return result


# ── Допоміжні ──────────────────────────────────────────────────────────────


def _extract_keywords(task: str) -> List[str]:
    """Витягти ключові слова з задачі для пошуку."""
    # Простий extraction: розбити на слова, відфільтрувати стоп-слова
    stop_words = {
        "та", "або", "але", "в", "у", "на", "з", "із", "що", "як",
        "це", "для", "від", "до", "не", "ти", "я", "ми", "ви",
        "the", "a", "an", "is", "are", "was", "and", "or", "but",
        "to", "of", "in", "on", "for", "with", "from", "by",
        "створи", "напиши", "відкрий", "прочитай", "видали",
        "make", "write", "open", "read", "delete",
    }
    words = task.lower().split()
    keywords = [w.strip(".,!?;:'\"") for w in words if len(w) > 2]
    keywords = [w for w in keywords if w not in stop_words]
    return keywords[:10]


def _build_gap_analysis_prompt(task: str, context: Dict[str, Any]) -> str:
    """Побудувати промпт для gap-аналізу."""
    lines = [f"ЗАДАЧА: {task}\n"]

    if context.get("relevant_files"):
        lines.append("РЕЛЕВАНТНІ ФАЙЛИ:")
        for f in context["relevant_files"][:10]:
            lines.append(f"  - {f}")

    if context.get("file_contents"):
        lines.append("\nВМІСТ ФАЙЛІВ (обрізано):")
        for filepath, content in context["file_contents"].items():
            lines.append(f"\n--- {filepath} ---")
            lines.append(content[:2000])  # максимум 2000 символів на файл
            if len(content) > 2000:
                lines.append(f"... ({len(content)} символів всього)")

    lines.append("""
ПОВЕРНИ JSON:
{
  "files_to_change": [
    {"filepath": "шлях/до/файлу", "description": "що змінити", "action": "edit|create"}
  ],
  "summary": "короткий підсумок змін"
}
""")
    return "\n".join(lines)


__all__ = ["build_self_context", "analyze_gap"]