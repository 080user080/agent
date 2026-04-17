"""Інструменти для роботи з кодом - читання файлів, пошук, редагування."""
import os
import re
import subprocess
from pathlib import Path

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


# Максимальний розмір файлу для читання (щоб не вантажити великі файли)
MAX_FILE_SIZE = 1_000_000  # 1 MB
MAX_READ_LINES = 2000


def _resolve_path(filepath: str) -> str:
    """Нормалізувати шлях: якщо не абсолютний - шукати на Desktop."""
    if os.path.isabs(filepath):
        return filepath
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    return os.path.join(desktop, filepath)


@llm_function(
    name="read_code_file",
    description="Прочитати вміст файлу (txt, py, json, md тощо) з опціональним обмеженням рядків",
    parameters={
        "filepath": "Повний шлях до файлу або відносний шлях від Desktop",
        "start_line": "(опціонально) номер першого рядка (1-indexed), за замовчуванням 1",
        "max_lines": "(опціонально) максимум рядків для читання, за замовчуванням 500",
    },
)
def read_code_file(filepath, start_line=1, max_lines=500):
    """Прочитати файл з обмеженням кількості рядків."""
    try:
        resolved = _resolve_path(filepath)

        if not os.path.exists(resolved):
            return make_tool_result(
                False,
                f"❌ Файл не знайдено: {resolved}",
                error="file_not_found",
            )

        file_size = os.path.getsize(resolved)
        if file_size > MAX_FILE_SIZE:
            return make_tool_result(
                False,
                f"❌ Файл занадто великий: {file_size} байт (ліміт {MAX_FILE_SIZE})",
                error="file_too_large",
                data={"file_size": file_size, "limit": MAX_FILE_SIZE},
            )

        try:
            start_line = int(start_line)
            max_lines = min(int(max_lines), MAX_READ_LINES)
        except (ValueError, TypeError):
            start_line, max_lines = 1, 500

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        end_line = min(start_line + max_lines - 1, total_lines)
        selected = all_lines[start_line - 1:end_line]

        content = "".join(selected)
        truncated = end_line < total_lines

        message = (
            f"📄 Файл: {os.path.basename(resolved)}\n"
            f"Рядки {start_line}-{end_line} з {total_lines}"
            f"{' (обрізано)' if truncated else ''}\n\n{content}"
        )

        return make_tool_result(
            True,
            message,
            data={
                "file_path": resolved,
                "content": content,
                "start_line": start_line,
                "end_line": end_line,
                "total_lines": total_lines,
                "truncated": truncated,
            },
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка читання файлу: {str(e)}",
            error=str(e),
            retryable=True,
        )


@llm_function(
    name="search_in_code",
    description="Пошук по файлах у директорії за регулярним виразом або текстом",
    parameters={
        "pattern": "Шаблон для пошуку (регулярний вираз або звичайний текст)",
        "directory": "(опціонально) директорія для пошуку, за замовчуванням поточна",
        "file_pattern": "(опціонально) glob-шаблон файлів, наприклад '*.py', за замовчуванням усі",
        "max_results": "(опціонально) максимум результатів, за замовчуванням 50",
    },
)
def search_in_code(pattern, directory=None, file_pattern="*", max_results=50):
    """Пошук по файлах за патерном."""
    try:
        if not directory:
            directory = os.getcwd()
        directory = os.path.abspath(directory)

        if not os.path.isdir(directory):
            return make_tool_result(
                False,
                f"❌ Директорія не знайдена: {directory}",
                error="directory_not_found",
            )

        try:
            max_results = int(max_results)
        except (ValueError, TypeError):
            max_results = 50

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Якщо невалідний regex - використовуємо як звичайний текст
            regex = re.compile(re.escape(pattern), re.IGNORECASE)

        matches = []
        files_checked = 0
        # Пропускаємо великі/непотрібні директорії
        skip_dirs = {".git", "__pycache__", "node_modules", "venv", ".venv", "dist", "build", "TTS"}

        for root, dirs, files in os.walk(directory):
            # Модифікуємо dirs in-place, щоб os.walk пропустив ці директорії
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for filename in files:
                if not Path(filename).match(file_pattern):
                    continue

                filepath = os.path.join(root, filename)
                try:
                    if os.path.getsize(filepath) > MAX_FILE_SIZE:
                        continue
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        for line_no, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append({
                                    "file": filepath,
                                    "line": line_no,
                                    "text": line.rstrip(),
                                })
                                if len(matches) >= max_results:
                                    break
                    files_checked += 1
                except Exception:
                    continue

                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        if not matches:
            return make_tool_result(
                True,
                f"🔍 Нічого не знайдено для '{pattern}' у {directory} (перевірено {files_checked} файлів)",
                data={"matches": [], "files_checked": files_checked},
            )

        # Формуємо повідомлення
        lines_out = [f"🔍 Знайдено {len(matches)} збігів для '{pattern}':"]
        for m in matches[:20]:  # Показуємо перші 20 у тексті
            rel = os.path.relpath(m["file"], directory)
            lines_out.append(f"  {rel}:{m['line']}: {m['text'][:120]}")
        if len(matches) > 20:
            lines_out.append(f"  ... і ще {len(matches) - 20}")

        return make_tool_result(
            True,
            "\n".join(lines_out),
            data={
                "matches": matches,
                "total": len(matches),
                "files_checked": files_checked,
                "directory": directory,
            },
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка пошуку: {str(e)}",
            error=str(e),
            retryable=True,
        )


@llm_function(
    name="list_directory",
    description="Показати вміст директорії (файли та підпапки)",
    parameters={
        "directory": "(опціонально) шлях до директорії, за замовчуванням поточна",
    },
)
def list_directory(directory=None):
    """Перелічити файли в директорії."""
    try:
        if not directory:
            directory = os.getcwd()
        directory = os.path.abspath(directory)

        if not os.path.isdir(directory):
            return make_tool_result(
                False,
                f"❌ Директорія не знайдена: {directory}",
                error="directory_not_found",
            )

        items = []
        for entry in sorted(os.listdir(directory)):
            full = os.path.join(directory, entry)
            is_dir = os.path.isdir(full)
            try:
                size = os.path.getsize(full) if not is_dir else None
            except OSError:
                size = None

            items.append({
                "name": entry,
                "is_dir": is_dir,
                "size": size,
                "path": full,
            })

        # Формуємо повідомлення
        lines_out = [f"📁 Вміст {directory}:"]
        for item in items:
            if item["is_dir"]:
                lines_out.append(f"  📂 {item['name']}/")
            else:
                size_str = f" ({item['size']} байт)" if item["size"] is not None else ""
                lines_out.append(f"  📄 {item['name']}{size_str}")

        return make_tool_result(
            True,
            "\n".join(lines_out),
            data={"directory": directory, "items": items, "count": len(items)},
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка: {str(e)}",
            error=str(e),
            retryable=True,
        )


@llm_function(
    name="git_status",
    description="Показати git status для проєкту",
    parameters={
        "directory": "(опціонально) шлях до репозиторію, за замовчуванням поточна директорія",
    },
)
def git_status(directory=None):
    """Виконати git status."""
    try:
        if not directory:
            directory = os.getcwd()
        directory = os.path.abspath(directory)

        if not os.path.isdir(os.path.join(directory, ".git")):
            return make_tool_result(
                False,
                f"❌ Не git-репозиторій: {directory}",
                error="not_a_git_repo",
            )

        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )

        if result.returncode != 0:
            return make_tool_result(
                False,
                f"❌ git status помилка: {result.stderr}",
                error=result.stderr,
                retryable=True,
            )

        output = result.stdout.strip() or "✅ Чиста робоча копія"
        return make_tool_result(
            True,
            f"🌿 Git status у {directory}:\n{output}",
            data={"directory": directory, "status": output},
        )
    except FileNotFoundError:
        return make_tool_result(
            False,
            "❌ git не встановлено або не знайдено в PATH",
            error="git_not_found",
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка: {str(e)}",
            error=str(e),
            retryable=True,
        )


@llm_function(
    name="git_diff",
    description="Показати git diff для поточних незакомічених змін",
    parameters={
        "directory": "(опціонально) шлях до репозиторію, за замовчуванням поточна директорія",
        "staged": "(опціонально) true для --staged, за замовчуванням false",
    },
)
def git_diff(directory=None, staged=False):
    """Виконати git diff."""
    try:
        if not directory:
            directory = os.getcwd()
        directory = os.path.abspath(directory)

        if not os.path.isdir(os.path.join(directory, ".git")):
            return make_tool_result(
                False,
                f"❌ Не git-репозиторій: {directory}",
                error="not_a_git_repo",
            )

        # Нормалізуємо staged (може прийти як bool або як рядок)
        is_staged = staged is True or (isinstance(staged, str) and staged.lower() in ("true", "1", "yes"))

        cmd = ["git", "diff"]
        if is_staged:
            cmd.append("--staged")

        result = subprocess.run(
            cmd,
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )

        if result.returncode != 0:
            return make_tool_result(
                False,
                f"❌ git diff помилка: {result.stderr}",
                error=result.stderr,
                retryable=True,
            )

        output = result.stdout
        if not output.strip():
            return make_tool_result(
                True,
                "✅ Немає змін" + (" (staged)" if is_staged else ""),
                data={"directory": directory, "diff": "", "staged": is_staged},
            )

        # Обрізаємо якщо занадто довгий
        preview = output[:3000] + ("\n... (обрізано)" if len(output) > 3000 else "")
        return make_tool_result(
            True,
            f"📝 Git diff{'(staged)' if is_staged else ''}:\n{preview}",
            data={"directory": directory, "diff": output, "staged": is_staged, "size": len(output)},
        )
    except FileNotFoundError:
        return make_tool_result(
            False,
            "❌ git не встановлено або не знайдено в PATH",
            error="git_not_found",
        )
    except Exception as e:
        return make_tool_result(
            False,
            f"❌ Помилка: {str(e)}",
            error=str(e),
            retryable=True,
        )
