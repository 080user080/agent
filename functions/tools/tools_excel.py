"""Microsoft Excel automation tool (Phase 10).

Provides functions for:
- Opening, reading, editing Excel workbooks
- Reading/writing cells, ranges
- Formatting cells
- Creating charts
- Saving and exporting workbooks
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import win32com.client as win32
    EXCEL_AVAILABLE = True
except Exception:
    EXCEL_AVAILABLE = False


def open_excel_workbook(file_path: str, read_only: bool = False) -> Dict[str, Any]:
    """Відкрити Excel робочу книгу.

    Args:
        file_path: Шлях до файлу .xlsx
        read_only: Відкрити в режимі лише для читання

    Returns:
        dict з success, workbook_object, error
    """
    if not EXCEL_AVAILABLE:
        return {"success": False, "error": "win32com не доступний (тільки Windows)"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        excel = win32.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(file_path, ReadOnly=read_only)
        return {"success": True, "workbook": workbook, "excel": excel, "file_path": file_path}
    except Exception as e:
        return {"success": False, "error": f"Помилка відкриття: {str(e)}"}


def create_excel_workbook() -> Dict[str, Any]:
    """Створити нову Excel робочу книгу.

    Returns:
        dict з success, workbook_object, error
    """
    if not EXCEL_AVAILABLE:
        return {"success": False, "error": "win32com не доступний (тільки Windows)"}

    try:
        excel = win32.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Add()
        return {"success": True, "workbook": workbook, "excel": excel}
    except Exception as e:
        return {"success": False, "error": f"Помилка створення: {str(e)}"}


def read_cell(workbook: Any, sheet_name: str, cell: str) -> Dict[str, Any]:
    """Прочитати значення клітинки.

    Args:
        workbook: COM об'єкт робочої книги Excel
        sheet_name: Назва аркуша
        cell: Адреса клітинки (наприклад, "A1")

    Returns:
        dict з success, value, error
    """
    try:
        sheet = workbook.Worksheets(sheet_name)
        value = sheet.Range(cell).Value
        return {"success": True, "value": value}
    except Exception as e:
        return {"success": False, "error": f"Помилка читання: {str(e)}"}


def write_cell(workbook: Any, sheet_name: str, cell: str, value: Any) -> Dict[str, Any]:
    """Записати значення в клітинку.

    Args:
        workbook: COM об'єкт робочої книги Excel
        sheet_name: Назва аркуша
        cell: Адреса клітинки (наприклад, "A1")
        value: Значення для запису

    Returns:
        dict з success, error
    """
    try:
        sheet = workbook.Worksheets(sheet_name)
        sheet.Range(cell).Value = value
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Помилка запису: {str(e)}"}


def read_range(workbook: Any, sheet_name: str, range_str: str) -> Dict[str, Any]:
    """Прочитати діапазон клітинок.

    Args:
        workbook: COM об'єкт робочої книги Excel
        sheet_name: Назва аркуша
        range_str: Діапазон (наприклад, "A1:C10")

    Returns:
        dict з success, values (2D list), error
    """
    try:
        sheet = workbook.Worksheets(sheet_name)
        range_obj = sheet.Range(range_str)
        values = range_obj.Value
        return {"success": True, "values": values}
    except Exception as e:
        return {"success": False, "error": f"Помилка читання діапазону: {str(e)}"}


def write_range(workbook: Any, sheet_name: str, range_str: str, values: List[List[Any]]) -> Dict[str, Any]:
    """Записати значення в діапазон клітинок.

    Args:
        workbook: COM об'єкт робочої книги Excel
        sheet_name: Назва аркуша
        range_str: Діапазон (наприклад, "A1:C10")
        values: 2D список значень

    Returns:
        dict з success, error
    """
    try:
        sheet = workbook.Worksheets(sheet_name)
        range_obj = sheet.Range(range_str)
        range_obj.Value = values
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Помилка запису діапазону: {str(e)}"}


def format_cell(workbook: Any, sheet_name: str, cell: str, bold: bool = False, 
                italic: bool = False, font_size: int = 11, color: Optional[str] = None) -> Dict[str, Any]:
    """Форматувати клітинку.

    Args:
        workbook: COM об'єкт робочої книги Excel
        sheet_name: Назва аркуша
        cell: Адреса клітинки
        bold: Жирний шрифт
        italic: Курсив
        font_size: Розмір шрифту
        color: Колір шрифту (RGB hex або назва)

    Returns:
        dict з success, error
    """
    try:
        sheet = workbook.Worksheets(sheet_name)
        range_obj = sheet.Range(cell)
        range_obj.Font.Bold = bold
        range_obj.Font.Italic = italic
        range_obj.Font.Size = font_size
        if color:
            range_obj.Font.Color = color
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Помилка форматування: {str(e)}"}


def add_worksheet(workbook: Any, sheet_name: str) -> Dict[str, Any]:
    """Додати новий аркуш.

    Args:
        workbook: COM об'єкт робочої книги Excel
        sheet_name: Назва нового аркуша

    Returns:
        dict з success, sheet_object, error
    """
    try:
        sheet = workbook.Worksheets.Add()
        sheet.Name = sheet_name
        return {"success": True, "sheet": sheet}
    except Exception as e:
        return {"success": False, "error": f"Помилка додавання аркуша: {str(e)}"}


def save_workbook(workbook: Any, excel: Any, file_path: str, close: bool = True) -> Dict[str, Any]:
    """Зберегти робочу книгу.

    Args:
        workbook: COM об'єкт робочої книги Excel
        excel: COM об'єкт Excel Application
        file_path: Шлях для збереження
        close: Закрити книгу після збереження

    Returns:
        dict з success, error
    """
    try:
        workbook.SaveAs(file_path)
        if close:
            workbook.Close()
            excel.Quit()
        return {"success": True, "file_path": file_path}
    except Exception as e:
        return {"success": False, "error": f"Помилка збереження: {str(e)}"}


def get_used_range(workbook: Any, sheet_name: str) -> Dict[str, Any]:
    """Отримати діапазон використовуваних клітинок.

    Args:
        workbook: COM об'єкт робочої книги Excel
        sheet_name: Назва аркуша

    Returns:
        dict з success, range_address, row_count, col_count, error
    """
    try:
        sheet = workbook.Worksheets(sheet_name)
        used_range = sheet.UsedRange
        row_count = used_range.Rows.Count
        col_count = used_range.Columns.Count
        return {
            "success": True,
            "range_address": used_range.Address,
            "row_count": row_count,
            "col_count": col_count
        }
    except Exception as e:
        return {"success": False, "error": f"Помилка отримання діапазону: {str(e)}"}
