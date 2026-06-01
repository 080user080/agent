"""Базові тести для tools_excel.py (Phase 10)."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from functions.tools_excel import (
    EXCEL_AVAILABLE,
    add_worksheet,
    create_excel_workbook,
    format_cell,
    get_used_range,
    open_excel_workbook,
    read_cell,
    read_range,
    save_workbook,
    write_cell,
    write_range,
)


@pytest.fixture
def temp_excel_path():
    """Створити тимчасовий шлях для Excel файлу."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestExcelAvailability:
    """Тести доступності Excel."""

    def test_excel_available_flag(self):
        """Перевірити флаг доступності Excel."""
        assert isinstance(EXCEL_AVAILABLE, bool)


class TestOpenExcelWorkbook:
    """Тести відкриття Excel робочих книг."""

    def test_open_nonexistent_file(self):
        """Відкриття неіснуючого файлу."""
        result = open_excel_workbook("nonexistent.xlsx")
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()

    @patch("functions.tools_excel.EXCEL_AVAILABLE", False)
    def test_open_without_win32com(self):
        """Відкриття без win32com."""
        result = open_excel_workbook("test.xlsx")
        assert result["success"] is False
        assert "win32com" in result["error"].lower()


class TestCreateExcelWorkbook:
    """Тести створення Excel робочих книг."""

    @patch("functions.tools_excel.EXCEL_AVAILABLE", False)
    def test_create_without_win32com(self):
        """Створення без win32com."""
        result = create_excel_workbook()
        assert result["success"] is False
        assert "win32com" in result["error"].lower()


class TestReadCell:
    """Тести читання клітинок."""

    def test_read_cell_mock(self):
        """Читання клітинки з мок-об'єктом."""
        mock_workbook = MagicMock()
        mock_workbook.Worksheets.return_value.Range.return_value.Value = "Test"
        
        result = read_cell(mock_workbook, "Sheet1", "A1")
        assert result["success"] is True
        assert result["value"] == "Test"


class TestWriteCell:
    """Тести запису клітинок."""

    def test_write_cell_mock(self):
        """Запис клітинки в мок-об'єкт."""
        mock_workbook = MagicMock()
        mock_workbook.Worksheets.return_value.Range = MagicMock()
        
        result = write_cell(mock_workbook, "Sheet1", "A1", "Test")
        assert result["success"] is True
        mock_workbook.Worksheets.return_value.Range.Value = "Test"


class TestReadRange:
    """Тести читання діапазонів."""

    def test_read_range_mock(self):
        """Читання діапазону з мок-об'єктом."""
        mock_workbook = MagicMock()
        mock_workbook.Worksheets.return_value.Range.return_value.Value = [[1, 2], [3, 4]]
        
        result = read_range(mock_workbook, "Sheet1", "A1:B2")
        assert result["success"] is True
        assert result["values"] == [[1, 2], [3, 4]]


class TestWriteRange:
    """Тести запису діапазонів."""

    def test_write_range_mock(self):
        """Запис діапазону в мок-об'єкт."""
        mock_workbook = MagicMock()
        mock_workbook.Worksheets.return_value.Range = MagicMock()
        
        values = [[1, 2], [3, 4]]
        result = write_range(mock_workbook, "Sheet1", "A1:B2", values)
        assert result["success"] is True
        mock_workbook.Worksheets.return_value.Range.Value = values


class TestFormatCell:
    """Тести форматування клітинок."""

    def test_format_cell_mock(self):
        """Форматування клітинки в мок-об'єкті."""
        mock_workbook = MagicMock()
        mock_workbook.Worksheets.return_value.Range = MagicMock()
        
        result = format_cell(mock_workbook, "Sheet1", "A1", bold=True, italic=False, size=14)
        assert result["success"] is True
        mock_workbook.Worksheets.return_value.Range.Font.Bold = True
        mock_workbook.Worksheets.return_value.Range.Font.Size = 14


class TestAddWorksheet:
    """Тести додавання аркушів."""

    def test_add_worksheet_mock(self):
        """Додавання аркуша в мок-об'єкті."""
        mock_workbook = MagicMock()
        mock_workbook.Worksheets.Add.return_value = MagicMock()
        
        result = add_worksheet(mock_workbook, "NewSheet")
        assert result["success"] is True
        mock_workbook.Worksheets.Add.assert_called_once()


class TestSaveWorkbook:
    """Тести збереження робочих книг."""

    def test_save_workbook(self):
        """Збереження книги."""
        mock_workbook = MagicMock()
        mock_excel = MagicMock()
        path = "test.xlsx"
        
        result = save_workbook(mock_workbook, mock_excel, path, close=False)
        assert result["success"] is True
        assert result["file_path"] == path
        mock_workbook.SaveAs.assert_called_once_with(path)
        mock_workbook.Close.assert_not_called()
        mock_excel.Quit.assert_not_called()

    def test_save_and_close_workbook(self):
        """Збереження та закриття книги."""
        mock_workbook = MagicMock()
        mock_excel = MagicMock()
        path = "test.xlsx"
        
        result = save_workbook(mock_workbook, mock_excel, path, close=True)
        assert result["success"] is True
        mock_workbook.SaveAs.assert_called_once_with(path)
        mock_workbook.Close.assert_called_once()
        mock_excel.Quit.assert_called_once()


class TestGetUsedRange:
    """Тести отримання діапазону використовуваних клітинок."""

    def test_get_used_range_mock(self):
        """Отримання діапазону з мок-об'єкта."""
        mock_workbook = MagicMock()
        mock_workbook.Worksheets.return_value.UsedRange = MagicMock()
        mock_workbook.Worksheets.return_value.UsedRange.Address = "A1:C5"
        mock_workbook.Worksheets.return_value.UsedRange.Rows.Count = 5
        mock_workbook.Worksheets.return_value.UsedRange.Columns.Count = 3
        
        result = get_used_range(mock_workbook, "Sheet1")
        assert result["success"] is True
        assert result["range_address"] == "A1:C5"
        assert result["row_count"] == 5
        assert result["col_count"] == 3
