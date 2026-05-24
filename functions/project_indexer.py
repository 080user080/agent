"""
project_indexer.py — Repo Map: сканує проєкт і будує карту класів, функцій, імпортів.

Використовує тільки вбудований ast (без зовнішніх залежностей).
Результат зберігає у runtime/repo_map.json.
При помилці парсингу — логує і продовжує.
"""

import ast
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Папки, які ігноруємо при рекурсивному скануванні
IGNORE_DIRS = {"venv", "backup", "__pycache__", ".git", ".venv", "node_modules", ".mypy_cache", ".pytest_cache"}

# Корінь проєкту (рівень вище functions/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Вихідний файл
REPO_MAP_PATH = PROJECT_ROOT / "runtime" / "repo_map.json"


def _get_relative_path(abspath: Path) -> str:
    """Повертає шлях відносно кореня проєкту."""
    return str(abspath.relative_to(PROJECT_ROOT)).replace("\\", "/")


def _parse_py_file(filepath: Path) -> dict | None:
    """
    Парсить один .py файл через ast.
    Повертає dict з ключами: classes, functions, imports.
    Якщо помилка — логує і вертає None.
    """
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        logger.warning("SyntaxError in %s: %s", filepath, e)
        return None
    except Exception as e:
        logger.error("Unexpected error parsing %s: %s", filepath, e)
        return None

    classes = []
    functions = []
    raw_imports: list[str] = []

    for node in ast.walk(tree):
        # --- Класи ---
        if isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    # e.g. module.ClassName
                    parts = []
                    cur = base
                    while isinstance(cur, ast.Attribute):
                        parts.append(cur.attr)
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        parts.append(cur.id)
                    bases.append(".".join(reversed(parts)))
                else:
                    bases.append("<complex>")
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    methods.append(_format_function(item))
            doc = ast.get_docstring(node)
            classes.append({
                "name": node.name,
                "bases": bases,
                "methods": methods,
                "doc": doc.strip() if doc else None,
            })

        # --- Функції (тільки top-level, не методи) ---
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            # Перевіряємо чи це top-level (батько — модуль)
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    # Якщо функція всередині класу — це метод, пропускаємо
                    if node in ast.walk(parent) and node is not parent:
                        break
            else:
                functions.append(_format_function(node))

        # --- Імпорти (збираємо всі, потім відфільтруємо) ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                raw_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            # Для "from X import Y" — резолвимо сам модуль X, а не X.Y
            raw_imports.append(module)

    # Фільтруємо: залишаємо тільки внутрішні імпорти проєкту -> шляхи
    imports = sorted(set(
        resolved
        for mod_name in raw_imports
        if mod_name and (resolved := _resolve_import_to_path(mod_name)) is not None
    ))

    return {
        "classes": classes,
        "functions": functions,
        "imports": imports,
    }


def _format_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    """Форматує функцію/метод: ім'я, параметри з типами, docstring першого рядка."""
    params = []
    for arg in node.args.args:
        arg_info = {"name": arg.arg}
        if arg.annotation:
            arg_info["type"] = _format_annotation(arg.annotation)
        params.append(arg_info)

    # Аргументи зі значеннями за замовчуванням (просто інфа про назву, тип)
    if node.args.vararg:
        params.append({"name": f"*{node.args.vararg.arg}", "type": _format_annotation(node.args.vararg.annotation) if node.args.vararg.annotation else None})
    if node.args.kwonlyargs:
        for arg in node.args.kwonlyargs:
            arg_info = {"name": arg.arg}
            if arg.annotation:
                arg_info["type"] = _format_annotation(arg.annotation)
            params.append(arg_info)
    if node.args.kwarg:
        params.append({"name": f"**{node.args.kwarg.arg}", "type": _format_annotation(node.args.kwarg.annotation) if node.args.kwarg.annotation else None})

    return_type = _format_annotation(node.returns) if node.returns else None
    doc = ast.get_docstring(node)
    first_line_doc = doc.strip().split("\n")[0] if doc else None

    return {
        "name": node.name,
        "params": params,
        "return_type": return_type,
        "doc": first_line_doc,
    }


def _resolve_import_to_path(module_name: str) -> str | None:
    """
    Спроба перетворити ім'я модуля (напр. 'functions.project_indexer')
    на відносний шлях до файлу проєкту.
    Повертає шлях на зразок 'functions/project_indexer.py' або None, якщо це зовнішній імпорт.
    Враховує: звичайні файли .py та пакети з __init__.py
    """
    # Спроба 1: прямий файл .py (напр. functions/project_indexer.py)
    as_file = module_name.replace(".", "/") + ".py"
    if (PROJECT_ROOT / as_file).is_file():
        return as_file

    # Спроба 2: пакет з __init__.py (напр. functions/project_indexer/__init__.py)
    as_init = module_name.replace(".", "/") + "/__init__.py"
    if (PROJECT_ROOT / as_init).is_file():
        return as_init

    return None


def _format_annotation(annotation: ast.AST) -> str:
    """Перетворює ast-ноду анотації типу в рядок."""
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Attribute):
        parts = []
        cur = annotation
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    elif isinstance(annotation, ast.Subscript):
        # e.g. Optional[str], List[int]
        value = _format_annotation(annotation.value)
        if isinstance(annotation.slice, ast.Tuple):
            slice_str = ", ".join(_format_annotation(el) for el in annotation.slice.elts)
            return f"{value}[{slice_str}]"
        else:
            slice_str = _format_annotation(annotation.slice)
            return f"{value}[{slice_str}]"
    elif isinstance(annotation, ast.Constant):
        return str(annotation.value)
    elif isinstance(annotation, ast.BinOp):
        # e.g. str | int (Python 3.10+ union types)
        left = _format_annotation(annotation.left)
        right = _format_annotation(annotation.right)
        op = " | " if isinstance(annotation.op, ast.BitOr) else " "
        return f"{left}{op}{right}"
    elif isinstance(annotation, ast.Tuple):
        return ", ".join(_format_annotation(el) for el in annotation.elts)
    elif isinstance(annotation, ast.List):
        return f"[{', '.join(_format_annotation(el) for el in annotation.elts)}]"
    else:
        return repr(annotation)


def scan_project() -> dict:
    """
    Сканує кореневу папку проєкту, парсить всі .py файли.
    Повертає dict у форматі:
    {
        "relative/path/to/file.py": {
            "classes": [...],
            "functions": [...],
            "imports": [...]
        },
        ...
    }
    """
    result = {}
    py_files_found = 0
    py_files_parsed = 0
    py_files_errored = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Видаляємо ігноровані папки з dirs (щоб os.walk не заходив туди)
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if not file.endswith(".py"):
                continue
            py_files_found += 1
            abspath = Path(root) / file
            relpath = _get_relative_path(abspath)

            parsed = _parse_py_file(abspath)
            if parsed is not None:
                result[relpath] = parsed
                py_files_parsed += 1
            else:
                py_files_errored += 1
                logger.warning("Skipped %s due to parse error", relpath)

    logger.info(
        "Scan complete: %d .py files found, %d parsed, %d errors",
        py_files_found, py_files_parsed, py_files_errored,
    )
    return result


def build_repo_map(output_path: str | Path | None = None) -> str:
    """
    Будує карту проєкту і зберігає у JSON.
    Повертає шлях до файлу результату.
    """
    if output_path is None:
        output_path = REPO_MAP_PATH
    else:
        output_path = Path(output_path)

    data = scan_project()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Repo map saved to %s (%d files)", output_path, len(data))
    return str(output_path)


def get_repo_map() -> str:
    """
    Читає runtime/repo_map.json і повертає компактне текстове представлення.
    Якщо файл не існує — запускає індексування автоматично.
    Формат: файл.py → Клас.метод(args), функція(args)
    """
    map_path = REPO_MAP_PATH
    if not map_path.exists():
        logger.info("repo_map.json not found, building from scratch...")
        build_repo_map()

    try:
        data = json.loads(map_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read repo_map.json: %s", e)
        return f"# ERROR: cannot read repo map — {e}"

    lines: list[str] = []
    # Сортуємо файли за шляхом для стабільності
    for filepath in sorted(data.keys()):
        info = data[filepath]
        items: list[str] = []

        for cls in info.get("classes", []):
            name = cls["name"]
            bases = cls.get("bases", [])
            if bases:
                name += f"({', '.join(bases)})"
            methods = cls.get("methods", [])
            if methods:
                methods_str = ", ".join(
                    _compact_method_signature(m)
                    for m in methods
                )
                items.append(f"{name}.{{{methods_str}}}")
            else:
                items.append(name)

        for func in info.get("functions", []):
            items.append(_compact_method_signature(func))

        if items:
            lines.append(f"{filepath} => {'; '.join(items)}")
        else:
            lines.append(f"{filepath} => (no public symbols)")

    return "\n".join(lines)


def _compact_method_signature(func: dict) -> str:
    """Форматує функцію/метод в компактний рядок: name(arg: type, ...) -> return_type."""
    params_str = ", ".join(
        f"{p['name']}: {p['type']}" if p.get("type") else p["name"]
        for p in func.get("params", [])
    )
    sig = f"{func['name']}({params_str})"
    if func.get("return_type"):
        sig += f" -> {func['return_type']}"
    return sig


def get_file_dependents(filepath: str) -> list[str]:
    """
    Повертає список всіх файлів проєкту, які імпортують вказаний файл.

    Args:
        filepath: Відносний шлях до файлу (напр. "functions/core_settings.py")

    Returns:
        Список відносних шляхів файлів, що імпортують цей файл.
        Якщо таких немає — порожній список.
    """
    map_path = REPO_MAP_PATH
    if not map_path.exists():
        logger.info("repo_map.json not found, building from scratch...")
        build_repo_map()

    try:
        data = json.loads(map_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read repo_map.json: %s", e)
        return []

    target = filepath.replace("\\", "/")
    result: list[str] = []
    for relpath, info in data.items():
        if target in info.get("imports", []):
            result.append(relpath)

    return sorted(result)


def update_file_in_map(filepath: str | Path) -> bool:
    """
    Оновлює інформацію про один конкретний файл у repo_map.json.
    filepath — відносний шлях від кореня проєкту (напр. "functions/utils.py").
    Повертає True якщо оновлення успішне.
    """
    filepath = Path(filepath)
    if not filepath.is_absolute():
        filepath = PROJECT_ROOT / filepath

    if not filepath.exists():
        logger.warning("File not found: %s", filepath)
        return False

    map_path = REPO_MAP_PATH
    if not map_path.exists():
        logger.warning("repo_map.json not found, rebuilding from scratch")
        build_repo_map()
        return True

    try:
        data = json.loads(map_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read repo_map.json: %s", e)
        return False

    relpath = _get_relative_path(filepath)
    parsed = _parse_py_file(filepath)

    if parsed is not None:
        data[relpath] = parsed
    else:
        # Якщо парсинг не вдався — видаляємо запис (файл може бути пошкодженим)
        data.pop(relpath, None)

    map_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Updated repo map for %s", relpath)
    return True


# --- CLI-точка входу для ручного запуску ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    out = build_repo_map()
    print(f"Repo map saved to: {out}")