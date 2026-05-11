"""Файлові операції для AgentLoop."""
from pathlib import Path
from .common_decorators import llm_function


@llm_function(
    name="write_file",
    description="Створити або перезаписати текстовий файл",
    parameters={
        "filepath": "Шлях до файлу (відносний або абсолютний)",
        "content": "Вміст файлу",
    }
)
def write_file(filepath: str, content: str) -> dict:
    """Створити або перезаписати текстовий файл.

    Args:
        filepath: Шлях до файлу (відносний або абсолютний)
        content: Вміст файлу

    Returns:
        dict: {'ok': True, 'result': 'Файл створено: {path}'} або помилка
    """
    try:
        path = Path(filepath)
        # Створити батьківські директорії якщо потрібно
        path.parent.mkdir(parents=True, exist_ok=True)
        # Записати файл
        path.write_text(content, encoding='utf-8')
        return {'ok': True, 'result': f'Файл створено: {filepath}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def list_directory(directory: str = '.') -> dict:
    """Показати вміст директорії.

    Args:
        directory: Шлях до директорії (за замовчуванням поточна)

    Returns:
        dict: {'ok': True, 'result': 'вміст директорії'} або помилка
    """
    try:
        path = Path(directory)
        if not path.is_dir():
            return {'ok': False, 'error': f'Не директорія: {directory}'}

        items = []
        for item in sorted(path.iterdir()):
            if item.is_dir():
                items.append(f'📂 {item.name}/')
            else:
                items.append(f'📄 {item.name} ({item.stat().st_size} байт)')

        result = f'📁 ВМІСТ ПАПКИ {directory} (Всього: {len(items)}):\n  ' + '\n  '.join(items) + '\n--- КІНЕЦЬ СПИСКУ ---'
        return {'ok': True, 'result': result}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def read_file(filepath: str) -> dict:
    """Прочитати вміст текстового файлу.

    Args:
        filepath: Шлях до файлу

    Returns:
        dict: {'ok': True, 'result': 'вміст файлу'} або помилка
    """
    try:
        path = Path(filepath)
        content = path.read_text(encoding='utf-8')
        return {'ok': True, 'result': content}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
