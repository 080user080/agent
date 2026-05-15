"""Microsoft Word automation tool (Phase 10).

Provides functions for:
- Opening, reading, editing Word documents
- Formatting text, paragraphs
- Inserting tables, images
- Saving and exporting documents
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import win32com.client as win32
    WORD_AVAILABLE = True
except Exception:
    WORD_AVAILABLE = False


def open_word_document(file_path: str) -> Dict[str, Any]:
    """Відкрити Word документ.

    Args:
        file_path: Шлях до файлу .docx

    Returns:
        dict з success, doc_object, error
    """
    if not WORD_AVAILABLE:
        return {"success": False, "error": "win32com не доступний (тільки Windows)"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(file_path)
        return {"success": True, "doc": doc, "word": word, "file_path": file_path}
    except Exception as e:
        return {"success": False, "error": f"Помилка відкриття: {str(e)}"}


def read_word_document(file_path: str) -> Dict[str, Any]:
    """Прочитати текст з Word документа.

    Args:
        file_path: Шлях до файлу .docx

    Returns:
        dict з success, text, error
    """
    if not WORD_AVAILABLE:
        return {"success": False, "error": "win32com не доступний (тільки Windows)"}

    try:
        result = open_word_document(file_path)
        if not result.get("success"):
            return result

        doc = result["doc"]
        word = result["word"]
        text = doc.Content.Text

        doc.Close(False)
        word.Quit()

        return {"success": True, "text": text, "length": len(text)}
    except Exception as e:
        return {"success": False, "error": f"Помилка читання: {str(e)}"}


def create_word_document(file_path: str) -> Dict[str, Any]:
    """Створити новий Word документ.

    Args:
        file_path: Шлях для збереження файлу .docx

    Returns:
        dict з success, doc_object, error
    """
    if not WORD_AVAILABLE:
        return {"success": False, "error": "win32com не доступний (тільки Windows)"}

    try:
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Add()
        return {"success": True, "doc": doc, "word": word, "file_path": file_path}
    except Exception as e:
        return {"success": False, "error": f"Помилка створення: {str(e)}"}


def write_text_to_document(doc: Any, text: str, at_end: bool = True) -> Dict[str, Any]:
    """Додати текст в документ.

    Args:
        doc: COM об'єкт документа Word
        text: Текст для вставки
        at_end: Якщо True, додає в кінець, інакше замінює весь вміст

    Returns:
        dict з success, error
    """
    try:
        if at_end:
            doc.Content.InsertAfter(text)
        else:
            doc.Content.Text = text
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Помилка запису: {str(e)}"}


def save_document(doc: Any, word: Any, file_path: str, close: bool = True) -> Dict[str, Any]:
    """Зберегти документ.

    Args:
        doc: COM об'єкт документа Word
        word: COM об'єкт Word Application
        file_path: Шлях для збереження
        close: Закрити документ після збереження

    Returns:
        dict з success, error
    """
    try:
        doc.SaveAs(file_path)
        if close:
            doc.Close()
            word.Quit()
        return {"success": True, "file_path": file_path}
    except Exception as e:
        return {"success": False, "error": f"Помилка збереження: {str(e)}"}


def format_paragraph(doc: Any, bold: bool = False, italic: bool = False, size: int = 11) -> Dict[str, Any]:
    """Форматувати останній параграф.

    Args:
        doc: COM об'єкт документа Word
        bold: Жирний шрифт
        italic: Курсив
        size: Розмір шрифту

    Returns:
        dict з success, error
    """
    try:
        para = doc.Paragraphs.Last
        para.Range.Bold = bold
        para.Range.Italic = italic
        para.Range.Font.Size = size
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Помилка форматування: {str(e)}"}


def insert_table(doc: Any, rows: int, cols: int) -> Dict[str, Any]:
    """Вставити таблицю в документ.

    Args:
        doc: COM об'єкт документа Word
        rows: Кількість рядків
        cols: Кількість стовпчиків

    Returns:
        dict з success, table_object, error
    """
    try:
        table = doc.Tables.Add(doc.Range(), rows, cols)
        return {"success": True, "table": table}
    except Exception as e:
        return {"success": False, "error": f"Помилка вставки таблиці: {str(e)}"}


def set_cell_text(table: Any, row: int, col: int, text: str) -> Dict[str, Any]:
    """Встановити текст в клітинку таблиці.

    Args:
        table: COM об'єкт таблиці Word
        row: Номер рядка (1-based)
        col: Номер стовпчика (1-based)
        text: Текст для вставки

    Returns:
        dict з success, error
    """
    try:
        cell = table.Cell(row, col)
        cell.Range.Text = text
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Помилка запису в клітинку: {str(e)}"}
