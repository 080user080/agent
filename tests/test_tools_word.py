"""Базові тести для tools_word.py (Phase 10)."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from functions.tools.tools_word import (
    WORD_AVAILABLE,
    create_word_document,
    format_paragraph,
    insert_table,
    open_word_document,
    read_word_document,
    save_document,
    set_cell_text,
    write_text_to_document,
)


@pytest.fixture
def temp_doc_path():
    """Створити тимчасовий шлях для Word документу."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestWordAvailability:
    """Тести доступності Word."""

    def test_word_available_flag(self):
        """Перевірити флаг доступності Word."""
        assert isinstance(WORD_AVAILABLE, bool)


class TestOpenWordDocument:
    """Тести відкриття Word документів."""

    def test_open_nonexistent_file(self):
        """Відкриття неіснуючого файлу."""
        result = open_word_document("nonexistent.docx")
        assert result["success"] is False
        assert "не знайдено" in result["error"].lower()

    @patch("functions.tools.tools_word.WORD_AVAILABLE", False)
    def test_open_without_win32com(self):
        """Відкриття без win32com."""
        result = open_word_document("test.docx")
        assert result["success"] is False
        assert "win32com" in result["error"].lower()


class TestReadWordDocument:
    """Тести читання Word документів."""

    @patch("functions.tools.tools_word.WORD_AVAILABLE", False)
    def test_read_without_win32com(self):
        """Читання без win32com."""
        result = read_word_document("test.docx")
        assert result["success"] is False
        assert "win32com" in result["error"].lower()


class TestCreateWordDocument:
    """Тести створення Word документів."""

    @patch("functions.tools.tools_word.WORD_AVAILABLE", False)
    def test_create_without_win32com(self):
        """Створення без win32com."""
        result = create_word_document("test.docx")
        assert result["success"] is False
        assert "win32com" in result["error"].lower()


class TestWriteTextToDocument:
    """Тести запису тексту в документ."""

    def test_write_to_mock_document(self):
        """Запис тексту в мок-документ."""
        mock_doc = MagicMock()
        result = write_text_to_document(mock_doc, "Test text", at_end=True)
        assert result["success"] is True
        mock_doc.Content.InsertAfter.assert_called_once_with("Test text")

    def test_write_replace_content(self):
        """Заміна вмісту документа."""
        mock_doc = MagicMock()
        result = write_text_to_document(mock_doc, "New text", at_end=False)
        assert result["success"] is True
        assert mock_doc.Content.Text == "New text"


class TestFormatParagraph:
    """Тести форматування параграфів."""

    def test_format_paragraph(self):
        """Форматування параграфу."""
        mock_doc = MagicMock()
        mock_doc.Paragraphs.Last.Range = MagicMock()
        
        result = format_paragraph(mock_doc, bold=True, italic=False, size=14)
        assert result["success"] is True


class TestInsertTable:
    """Тести вставки таблиць."""

    def test_insert_table(self):
        """Вставка таблиці."""
        mock_doc = MagicMock()
        mock_doc.Range.return_value = MagicMock()
        
        result = insert_table(mock_doc, rows=3, cols=2)
        assert result["success"] is True
        mock_doc.Tables.Add.assert_called_once()


class TestSetCellText:
    """Тести запису тексту в клітинки таблиці."""

    def test_set_cell_text(self):
        """Запис тексту в клітинку."""
        mock_table = MagicMock()
        mock_table.Cell.return_value.Range = MagicMock()
        
        result = set_cell_text(mock_table, row=1, col=1, text="Test")
        assert result["success"] is True
        mock_table.Cell.assert_called_once_with(1, 1)


class TestSaveDocument:
    """Тести збереження документів."""

    def test_save_document(self):
        """Збереження документа."""
        mock_doc = MagicMock()
        mock_word = MagicMock()
        path = "test.docx"
        
        result = save_document(mock_doc, mock_word, path, close=False)
        assert result["success"] is True
        assert result["file_path"] == path
        mock_doc.SaveAs.assert_called_once_with(path)
        mock_doc.Close.assert_not_called()
        mock_word.Quit.assert_not_called()

    def test_save_and_close_document(self):
        """Збереження та закриття документа."""
        mock_doc = MagicMock()
        mock_word = MagicMock()
        path = "test.docx"
        
        result = save_document(mock_doc, mock_word, path, close=True)
        assert result["success"] is True
        mock_doc.SaveAs.assert_called_once_with(path)
        mock_doc.Close.assert_called_once()
        mock_word.Quit.assert_called_once()
