"""self_code_patcher — Code patch generator для Self-Coding Agent Pipeline.

Генерує патчі (змінену частину коду) через LLM, валідує синтаксис
та безпеку перед поверненням.

Phase: Self-Coding Agent Pipeline — Фаза 2, 3.
"""
from __future__ import annotations

import ast
import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("self_code_patcher")


def generate_patch(
    file_path: str,
    task: str,
    context: Dict[str, Any],
    llm_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Згенерувати патч для файлу на основі задачі.

    Функція:
    1. Читає поточний вміст файлу через ``read_code_file()``
    2. Через LLM генерує змінену частину (не весь файл)
    3. Перед поверненням валідує через ``PythonSandbox.validate_code()``
    4. Якщо синтаксис невалідний — повертає помилку, не записує файл

    Args:
        file_path: Шлях до файлу який потрібно змінити.
        task: Опис задачі/зміни.
        context: Контекст від ``build_self_context()`` або подібний.
            Має містити ``file_contents`` (dict filepath→content).
        llm_callback: Функція ``(messages) -> str`` для виклику LLM.
            Якщо None — генерується базова заглушка.

    Returns:
        Dict з ключами:
          - ``ok``: bool — чи вдалося згенерувати валідний патч
          - ``patch``: str — згенерований патч (код)
          - ``old_content``: str — оригінальний вміст файлу
          - ``new_content``: str — повний вміст файлу після застосування
          - ``error``: str | None — текст помилки якщо ok=False
          - ``validation``: dict — результат валідації
    """
    result: Dict[str, Any] = {
        "ok": False,
        "patch": "",
        "old_content": "",
        "new_content": "",
        "error": None,
        "validation": {},
    }

    # 1. Прочитати поточний вміст файлу
    old_content = _read_file_content(file_path, context)
    if old_content is None:
        result["error"] = f"Не вдалося прочитати файл: {file_path}"
        return result
    result["old_content"] = old_content

    # 2. Згенерувати патч через LLM
    if llm_callback is not None:
        patch = _generate_patch_via_llm(file_path, task, old_content, context, llm_callback)
    else:
        patch = _generate_stub_patch(file_path, task, old_content)

    if not patch:
        result["error"] = "LLM не зміг згенерувати патч"
        return result

    result["patch"] = patch

    # 3. Побудувати повний вміст після застосування патчу
    new_content = _apply_patch(old_content, patch, file_path)
    if new_content is None:
        result["error"] = "Не вдалося застосувати патч до файлу"
        return result
    result["new_content"] = new_content

    # 4. Валідація синтаксису (ast.parse)
    syntax_ok, syntax_msg = _validate_syntax(new_content, file_path)
    if not syntax_ok:
        result["error"] = f"Синтаксична помилка після застосування патчу: {syntax_msg}"
        result["validation"] = {"syntax_ok": False, "message": syntax_msg}
        return result

    # 5. Валідація безпеки через PythonSandbox (якщо доступний)
    safety_ok, safety_msg = _validate_safety(new_content, file_path)
    result["validation"] = {
        "syntax_ok": True,
        "safety_ok": safety_ok,
        "syntax_message": syntax_msg,
        "safety_message": safety_msg,
    }

    if not safety_ok:
        result["error"] = f"Порушення безпеки: {safety_msg}"
        return result

    result["ok"] = True
    logger.info(
        "generate_patch: file='%s', task='%s', patch_len=%d",
        file_path, task[:50], len(patch),
    )
    return result


# ── Допоміжні функції ────────────────────────────────────────────────────────


def _read_file_content(
    file_path: str, context: Dict[str, Any]
) -> Optional[str]:
    """Прочитати вміст файлу: спочатку з контексту, потім з диску."""
    # Спроба 1: з контексту
    file_contents = context.get("file_contents", {})
    if file_path in file_contents:
        return file_contents[file_path]

    # Спроба 2: через read_code_file
    try:
        from functions.tools.aaa_code_tools import read_code_file
        result = read_code_file(filepath=file_path)
        if isinstance(result, dict) and result.get("ok"):
            return result.get("content", "")
        elif isinstance(result, str):
            return result
    except ImportError:
        logger.debug("read_code_file not available")
    except Exception as e:
        logger.debug("read_code_file error: %s", e)

    # Спроба 3: пряме читання
    try:
        from pathlib import Path
        path = Path(file_path)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.debug("Direct file read error: %s", e)

    return None


def _generate_patch_via_llm(
    file_path: str,
    task: str,
    old_content: str,
    context: Dict[str, Any],
    llm_callback: Callable,
) -> Optional[str]:
    """Згенерувати патч через LLM callback."""
    # Обрізаємо контент для промпту (максимум 4000 символів)
    truncated_content = old_content[:4000]
    if len(old_content) > 4000:
        truncated_content += f"\n... (обрізано, всього {len(old_content)} символів)"

    # Додатковий контекст
    repo_map = context.get("repo_map", "")
    relevant = context.get("relevant_files", [])
    context_info = ""
    if repo_map:
        context_info += f"\n\nРЕПО-МАПА:\n{repo_map[:1000]}"
    if relevant:
        context_info += f"\n\nРЕЛЕВАНТНІ ФАЙЛИ:\n" + "\n".join(f"  - {f}" for f in relevant[:10])

    system_prompt = (
        "Ти — досвідчений Python-розробник. "
        "Твоє завдання — згенерувати ОДНУ функцію або блок коду яка вирішує задачу.\n\n"
        "ПРАВИЛА:\n"
        "1. Повертай ТІЛЬКИ Python-код, без markdown-обгорток\n"
        "2. Не змінюй сигнатуру функції якщо вона не згадана в задачі\n"
        "3. Зберігай стиль коду оригіналу\n"
        "4. Додавай docstring для нових функцій\n"
        "5. Якщо потрібно замінити існуючу функцію — поверни нову версію повністю"
    )

    user_prompt = (
        f"ФАЙЛ: {file_path}\n"
        f"ЗАДАЧА: {task}\n"
        f"{context_info}\n\n"
        f"ПОТОЧНИЙ ВМІСТ ФАЙЛУ:\n```python\n{truncated_content}\n```\n\n"
        f"Згенеруй змінений код або нову функцію для вирішення задачі. "
        f"Поверни ТІЛЬКИ Python-код:"
    )

    try:
        response = llm_callback([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        if isinstance(response, str):
            return _clean_llm_response(response)
        elif isinstance(response, dict):
            return _clean_llm_response(response.get("content", response.get("code", "")))

    except Exception as e:
        logger.warning("LLM call failed for generate_patch: %s", e)

    return None


def _clean_llm_response(response: str) -> str:
    """Очистити відповідь LLM від markdown-обгорток та зайвого тексту."""
    code = response.strip()

    # Видаляємо markdown code blocks
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    elif code.startswith("```"):
        code = code[len("```"):].strip()

    if code.endswith("```"):
        code = code[:-3].strip()

    # Видаляємо коментарі-пояснення до/після коду
    lines = code.split("\n")
    code_lines = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        # Починаємо з першого рядка коду (не коментар)
        if not in_code:
            if stripped and not stripped.startswith("#") and not stripped.startswith("\"\"\""):
                in_code = True
            elif stripped.startswith("#") or stripped.startswith("\"\"\""):
                continue  # пропускаємо пояснення
        if in_code:
            code_lines.append(line)

    return "\n".join(code_lines).strip()


def _generate_stub_patch(
    file_path: str, task: str, old_content: str
) -> Optional[str]:
    """Згенерувати заглушку-патч без LLM (для тестування/фолбеку)."""
    # Повертаємо оригінальний контент з доданим TODO-коментарем
    stub = (
        f"# TODO: [self_code_patcher] Задача: {task}\n"
        f"# Файл: {file_path}\n"
        f"# Це заглушка — підключіть LLM для реального кодування\n"
    )
    return stub


def _apply_patch(
    old_content: str, patch: str, file_path: str
) -> Optional[str]:
    """Застосувати патч до оригінального вмісту.

    Стратегія:
    - Якщо патч містить повну версію функції з тією ж назвою —
      замінюємо стару функцію на нову
    - Якщо патч не містить жодної функції з оригіналу —
      додаємо в кінець файлу
    """
    # Спроба 1: Заміна функції
    new_content = _try_function_replacement(old_content, patch, file_path)
    if new_content is not None:
        return new_content

    # Спроба 2: Дописати в кінець
    return old_content.rstrip() + "\n\n" + patch


def _try_function_replacement(
    old_content: str, patch: str, file_path: str
) -> Optional[str]:
    """Спробувати замінити функцію в оригіналі на нову версію з патчу."""
    try:
        # Знаходимо назви функцій у патчі
        patch_tree = ast.parse(patch)
        patch_funcs = {}
        for node in ast.walk(patch_tree):
            if isinstance(node, ast.FunctionDef):
                start = node.lineno - 1
                end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else start + 50
                func_lines = patch.split("\n")[start:end]
                patch_funcs[node.name] = "\n".join(func_lines)

        if not patch_funcs:
            return None

        # Знаходимо функції в оригіналі
        old_tree = ast.parse(old_content)
        old_lines = old_content.split("\n")

        for node in ast.walk(old_tree):
            if isinstance(node, ast.FunctionDef) and node.name in patch_funcs:
                start = node.lineno - 1
                end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else start + 50

                # Замінюємо
                new_lines = old_lines[:start] + patch_funcs[node.name].split("\n") + old_lines[end:]
                return "\n".join(new_lines)

    except SyntaxError:
        # Якщо патч або оригінал не парсяться — fallback
        pass
    except Exception as e:
        logger.debug("_try_function_replacement error: %s", e)

    return None


def _validate_syntax(code: str, file_path: str) -> tuple[bool, str]:
    """Перевірити синтаксис коду через ast.parse."""
    try:
        ast.parse(code)
        return True, "OK"
    except SyntaxError as e:
        return False, f"Рядок {e.lineno}: {e.msg}"


def _validate_safety(code: str, file_path: str) -> tuple[bool, str]:
    """Перевірити код на безпеку через PythonSandbox.validate_code()."""
    try:
        from functions.tools.aaa_execute_python import PythonSandbox
        sandbox = PythonSandbox()
        is_safe, message = sandbox.validate_code(code, file_path)
        return is_safe, message
    except ImportError:
        logger.debug("PythonSandbox not available — skipping safety check")
        # Якщо PythonSandbox недоступний — базова перевірка
        return _basic_safety_check(code)
    except Exception as e:
        logger.debug("Safety validation error: %s", e)
        return _basic_safety_check(code)


def _basic_safety_check(code: str) -> tuple[bool, str]:
    """Базова перевірка безпеки (fallback коли PythonSandbox недоступний)."""
    forbidden = [
        "os.system",
        "shutil.rmtree",
        "subprocess.call",
        "__import__('os')",
        "__import__('subprocess')",
        "eval(",
        "exec(",
        "compile(",
    ]

    for pattern in forbidden:
        if pattern in code:
            return False, f"Знайдено небезпечний виклик: {pattern}"

    return True, "Базова перевірка пройдена (PythonSandbox недоступний)"


# ── Фаза 3: Верифікація та rollback ──────────────────────────────────────────


def verify_edit(
    file_path: str,
    task: str,
    llm_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Повторна верифікація зміненого файлу після застосування патчу.

    Функція:
    1. Повторно читає змінений файл через ``read_code_file()``
    2. Через LLM (якщо доступний) перевіряє чи зміна відповідає задачі
    3. Без LLM — перевіряє синтаксис через ``ast.parse``
    4. Оновлює repo map через ``update_file_in_map()``
    5. Повертає ``{ok, summary, warnings}``

    Args:
        file_path: Шлях до зміненого файлу.
        task: Опис задачі/зміни що мала бути виконана.
        llm_callback: Функція ``(messages) -> str`` для LLM-перевірки.
            Якщо None — базова перевірка синтаксису.

    Returns:
        Dict з ключами:
          - ``ok``: bool — чи зміна відповідає задачі
          - ``summary``: str — короткий опис результату верифікації
          - ``warnings``: list[str] — список попереджень
    """
    warnings: List[str] = []
    summary = ""

    # 1. Прочитати змінений файл
    content = _read_file_content(file_path, context={})
    if content is None:
        return {
            "ok": False,
            "summary": f"Не вдалося прочитати файл: {file_path}",
            "warnings": [f"Файл не знайдено або нечитабельний: {file_path}"],
        }

    # 2. Базова перевірка синтаксису
    syntax_ok, syntax_msg = _validate_syntax(content, file_path)
    if not syntax_ok:
        warnings.append(f"Синтаксична помилка: {syntax_msg}")

    # 3. LLM-перевірка (якщо доступний)
    if llm_callback is not None:
        llm_result = _verify_via_llm(file_path, task, content, llm_callback)
        if llm_result is not None:
            summary = llm_result.get("summary", "")
            if not llm_result.get("ok", False):
                warnings.extend(llm_result.get("warnings", []))
                # LLM вважає що зміна невдала
                _update_repo_map(file_path)
                return {
                    "ok": False,
                    "summary": summary or "LLM-верифікація: зміна не відповідає задачі",
                    "warnings": warnings,
                }
        else:
            warnings.append("LLM-верифікація недоступна — виконано базову перевірку")
    else:
        # Без LLM — лише синтаксична перевірка
        if syntax_ok:
            summary = f"Базова перевірка: синтаксис OK, файл {file_path} валідний"
        else:
            summary = f"Базова перевірка: синтаксична помилка у {file_path}"

    # 4. Оновити repo map
    _update_repo_map(file_path)

    ok = syntax_ok and not any("критична" in w.lower() for w in warnings)
    logger.info(
        "verify_edit: file='%s', ok=%s, warnings=%d",
        file_path, ok, len(warnings),
    )
    return {
        "ok": ok,
        "summary": summary or ("Верифікація пройдена" if ok else "Верифікація не пройдена"),
        "warnings": warnings,
    }


def _verify_via_llm(
    file_path: str,
    task: str,
    content: str,
    llm_callback: Callable,
) -> Optional[Dict[str, Any]]:
    """Перевірити зміну через LLM."""
    truncated = content[:4000]
    if len(content) > 4000:
        truncated += f"\n... (обрізано, всього {len(content)} символів)"

    system_prompt = (
        "Ти — досвідчений Python-розробник-ревізор.\n"
        "Тобі надано файл після зміни та оригінальну задачу.\n"
        "Твоє завдання — оцінити чи зміна коректно вирішує задачу.\n\n"
        "ПОВЕРНИ JSON (без markdown-обгорток):\n"
        '{"ok": true/false, "summary": "короткий опис", "warnings": ["попередження"]}'
    )

    user_prompt = (
        f"ФАЙЛ ПІСЛЯ ЗМІНИ: {file_path}\n"
        f"ЗАДАЧА: {task}\n\n"
        f"ВМІСТ ФАЙЛУ:\n```python\n{truncated}\n```\n\n"
        f"Оціни чи зміна відповідає задачі. Поверни JSON:"
    )

    try:
        response = llm_callback([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        text = ""
        if isinstance(response, str):
            text = response
        elif isinstance(response, dict):
            text = response.get("content", response.get("code", str(response)))

        return _parse_verify_response(text)

    except Exception as e:
        logger.warning("LLM verify_edit call failed: %s", e)
        return None


def _parse_verify_response(text: str) -> Optional[Dict[str, Any]]:
    """Парсинг відповіді LLM для верифікації."""
    text = text.strip()

    # Видаляємо markdown-обгортки
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        data = json.loads(text)
        return {
            "ok": bool(data.get("ok", False)),
            "summary": str(data.get("summary", "")),
            "warnings": list(data.get("warnings", [])),
        }
    except json.JSONDecodeError:
        # Спроба знайти JSON у тексті
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(text[start:end])
                return {
                    "ok": bool(data.get("ok", False)),
                    "summary": str(data.get("summary", "")),
                    "warnings": list(data.get("warnings", [])),
                }
        except (json.JSONDecodeError, ValueError):
            pass

    logger.debug("Cannot parse LLM verify response: %s", text[:200])
    return None


def _update_repo_map(file_path: str) -> bool:
    """Оновити repo map для файлу."""
    try:
        from functions.project_indexer import update_file_in_map
        return update_file_in_map(file_path)
    except ImportError:
        logger.debug("update_file_in_map not available")
        return False
    except Exception as e:
        logger.debug("update_file_in_map error: %s", e)
        return False


def rollback_edit(
    file_path: str,
    snapshot_id: str,
    task: str,
    verify_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Автоматичний rollback зміни якщо верифікація не пройдена.

    Виконує:
    1. Відновлення стану через ``UndoManager.restore_snapshot()``
    2. Логування невдалої спроби через ``SelfLearning.log_execution()``
    3. Повернення детального звіту

    Args:
        file_path: Шлях до файлу який було змінено.
        snapshot_id: ID snapshot для відновлення.
        task: Опис задачі що виконувалась.
        verify_result: Результат ``verify_edit()`` що повернув ``ok=False``.

    Returns:
        Dict з ключами:
          - ``ok``: bool — чи вдалося відновити стан
          - ``restored``: bool — чи був виконаний restore
          - ``summary``: str — опис результату
          - ``verify_result``: dict — оригінальний verify_result
          - ``error``: str | None — текст помилки
    """
    result: Dict[str, Any] = {
        "ok": False,
        "restored": False,
        "summary": "",
        "verify_result": verify_result,
        "error": None,
    }

    # 1. Відновити snapshot
    try:
        from functions.runtime.core_undo_manager import get_undo_manager
        undo_manager = get_undo_manager()
        restore_result = undo_manager.restore_snapshot(snapshot_id)

        if restore_result.get("success"):
            result["restored"] = True
            result["summary"] = f"Rollback виконано: snapshot {snapshot_id} відновлено"
            result["ok"] = True
        else:
            msg = restore_result.get("message", "Невідома помилка")
            result["summary"] = f"Rollback невдалий: {msg}"
            result["error"] = msg
    except ImportError:
        msg = "UndoManager недоступний"
        result["summary"] = f"Rollback неможливий: {msg}"
        result["error"] = msg
        logger.error("rollback_edit: UndoManager not available")
    except Exception as e:
        msg = f"Помилка rollback: {e}"
        result["summary"] = msg
        result["error"] = str(e)
        logger.error("rollback_edit error: %s", e)

    # 2. Залогувати невдалу спробу через SelfLearning
    try:
        from functions.runtime.self_learning import get_self_learning
        learner = get_self_learning()
        learner.log_execution(
            task=f"Self-edit: {task}",
            result=result["summary"],
            success=False,
            error=f"Verification failed: {verify_result.get('warnings', [])}",
            metadata={
                "file_path": file_path,
                "snapshot_id": snapshot_id,
                "verify_result": verify_result,
            },
        )
    except ImportError:
        logger.debug("SelfLearning not available — skipping log")
    except Exception as e:
        logger.debug("SelfLearning log error: %s", e)

    logger.info(
        "rollback_edit: file='%s', restored=%s, snapshot='%s'",
        file_path, result["restored"], snapshot_id,
    )
    return result


def verify_and_maybe_rollback(
    file_path: str,
    task: str,
    snapshot_id: str,
    llm_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Комбінована операція: верифікація + автоматичний rollback при невдачі.

    Обгортає ``verify_edit()`` та ``rollback_edit()`` в один виклик.

    Args:
        file_path: Шлях до зміненого файлу.
        task: Опис задачі/зміни.
        snapshot_id: ID snapshot для можливого rollback.
        llm_callback: Функція ``(messages) -> str`` для LLM-перевірки.

    Returns:
        Dict з ключами:
          - ``verified``: bool — чи пройшла верифікація
          - ``rolled_back``: bool — чи був виконаний rollback
          - ``verify_result``: dict — результат ``verify_edit()``
          - ``rollback_result``: dict | None — результат ``rollback_edit()``
    """
    verify_result = verify_edit(file_path, task, llm_callback)

    result: Dict[str, Any] = {
        "verified": verify_result["ok"],
        "rolled_back": False,
        "verify_result": verify_result,
        "rollback_result": None,
    }

    if not verify_result["ok"]:
        rollback_result = rollback_edit(
            file_path=file_path,
            snapshot_id=snapshot_id,
            task=task,
            verify_result=verify_result,
        )
        result["rolled_back"] = rollback_result.get("restored", False)
        result["rollback_result"] = rollback_result

    return result


# ── Публічний API ─────────────────────────────────────────────────────────────


__all__ = ["generate_patch", "verify_edit", "rollback_edit", "verify_and_maybe_rollback"]
