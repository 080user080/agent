"""PDF processing tool (Phase 10).

Provides functions for:
- Reading text from PDF files
- Extracting pages
- Merging PDF files
- Creating PDF files from images
- Adding text to PDF
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except Exception:
    PYPDF2_AVAILABLE = False

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except Exception:
    PILLOW_AVAILABLE = False

try:
    import img2pdf
    IMG2PDF_AVAILABLE = True
except Exception:
    IMG2PDF_AVAILABLE = False


def read_pdf_text(file_path: str, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
    """Прочитати текст з PDF файлу.

    Args:
        file_path: Шлях до PDF файлу
        page_numbers: Список номерів сторінок для читання (0-based). Якщо None - всі сторінки.

    Returns:
        dict з success, text, pages_count, error
    """
    if not PYPDF2_AVAILABLE:
        return {"success": False, "error": "PyPDF2 не доступний (pip install PyPDF2)"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pages_count = len(pdf_reader.pages)
            
            if page_numbers is None:
                page_numbers = list(range(pages_count))
            
            text = ""
            for page_num in page_numbers:
                if 0 <= page_num < pages_count:
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n\n"
            
            return {
                "success": True,
                "text": text.strip(),
                "pages_count": pages_count,
                "pages_read": len(page_numbers)
            }
    except Exception as e:
        return {"success": False, "error": f"Помилка читання: {str(e)}"}


def get_pdf_info(file_path: str) -> Dict[str, Any]:
    """Отримати інформацію про PDF файл.

    Args:
        file_path: Шлях до PDF файлу

    Returns:
        dict з success, pages_count, metadata, error
    """
    if not PYPDF2_AVAILABLE:
        return {"success": False, "error": "PyPDF2 не доступний"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pages_count = len(pdf_reader.pages)
            metadata = pdf_reader.metadata
            
            return {
                "success": True,
                "pages_count": pages_count,
                "metadata": {
                    "title": metadata.get('/Title', ''),
                    "author": metadata.get('/Author', ''),
                    "subject": metadata.get('/Subject', ''),
                    "creator": metadata.get('/Creator', ''),
                    "producer": metadata.get('/Producer', ''),
                } if metadata else {}
            }
    except Exception as e:
        return {"success": False, "error": f"Помилка отримання інформації: {str(e)}"}


def extract_pages(file_path: str, output_path: str, page_numbers: List[int]) -> Dict[str, Any]:
    """Витягти сторінки з PDF і зберегти в новий файл.

    Args:
        file_path: Шлях до вихідного PDF файлу
        output_path: Шлях для збереження нового PDF
        page_numbers: Список номерів сторінок для витягування (0-based)

    Returns:
        dict з success, pages_extracted, error
    """
    if not PYPDF2_AVAILABLE:
        return {"success": False, "error": "PyPDF2 не доступний"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pdf_writer = PyPDF2.PdfWriter()
            
            pages_count = len(pdf_reader.pages)
            extracted_count = 0
            
            for page_num in page_numbers:
                if 0 <= page_num < pages_count:
                    page = pdf_reader.pages[page_num]
                    pdf_writer.add_page(page)
                    extracted_count += 1
            
            # Створити директорію якщо не існує
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            return {
                "success": True,
                "pages_extracted": extracted_count,
                "output_path": output_path
            }
    except Exception as e:
        return {"success": False, "error": f"Помилка витягування сторінок: {str(e)}"}


def merge_pdfs(file_paths: List[str], output_path: str) -> Dict[str, Any]:
    """Об'єднати кілька PDF файлів в один.

    Args:
        file_paths: Список шляхів до PDF файлів для об'єднання
        output_path: Шлях для збереження об'єднаного PDF

    Returns:
        dict з success, files_merged, error
    """
    if not PYPDF2_AVAILABLE:
        return {"success": False, "error": "PyPDF2 не доступний"}

    try:
        pdf_writer = PyPDF2.PdfWriter()
        merged_count = 0
        
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
                merged_count += 1
        
        # Створити директорію якщо не існує
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'wb') as output_file:
            pdf_writer.write(output_file)
        
        return {
            "success": True,
            "files_merged": merged_count,
            "output_path": output_path
        }
    except Exception as e:
        return {"success": False, "error": f"Помилка об'єднання: {str(e)}"}


def split_pdf(file_path: str, output_dir: str) -> Dict[str, Any]:
    """Розділити PDF на окремі сторінки.

    Args:
        file_path: Шлях до PDF файлу
        output_dir: Директорія для збереження окремих сторінок

    Returns:
        dict з success, pages_created, error
    """
    if not PYPDF2_AVAILABLE:
        return {"success": False, "error": "PyPDF2 не доступний"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        # Створити директорію якщо не існує
        os.makedirs(output_dir, exist_ok=True)
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pages_count = len(pdf_reader.pages)
            
            for i, page in enumerate(pdf_reader.pages):
                pdf_writer = PyPDF2.PdfWriter()
                pdf_writer.add_page(page)
                
                output_file = os.path.join(output_dir, f"page_{i+1}.pdf")
                with open(output_file, 'wb') as output:
                    pdf_writer.write(output)
            
            return {
                "success": True,
                "pages_created": pages_count,
                "output_dir": output_dir
            }
    except Exception as e:
        return {"success": False, "error": f"Помилка розділення: {str(e)}"}


def create_pdf_from_images(image_paths: List[str], output_path: str) -> Dict[str, Any]:
    """Створити PDF з зображень.

    Args:
        image_paths: Список шляхів до зображень
        output_path: Шлях для збереження PDF

    Returns:
        dict з success, images_added, error
    """
    if not PILLOW_AVAILABLE:
        return {"success": False, "error": "Pillow не доступний (pip install Pillow)"}
    
    if not IMG2PDF_AVAILABLE:
        return {"success": False, "error": "img2pdf не доступний (pip install img2pdf)"}

    try:
        # Завантажити зображення
        images = []
        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue
            with open(img_path, 'rb') as img_file:
                images.append(img_file.read())
        
        if not images:
            return {"success": False, "error": "Немає валідних зображень"}
        
        # Створити директорію якщо не існує
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Конвертувати в PDF
        with open(output_path, 'wb') as pdf_file:
            pdf_file.write(img2pdf.convert(images))
        
        return {
            "success": True,
            "images_added": len(images),
            "output_path": output_path
        }
    except Exception as e:
        return {"success": False, "error": f"Помилка створення PDF: {str(e)}"}


def rotate_pdf_pages(file_path: str, output_path: str, rotation: int = 90) -> Dict[str, Any]:
    """Повернути сторінки PDF.

    Args:
        file_path: Шлях до PDF файлу
        output_path: Шлях для збереження повернутого PDF
        rotation: Кут повороту (90, 180, 270)

    Returns:
        dict з success, pages_rotated, error
    """
    if not PYPDF2_AVAILABLE:
        return {"success": False, "error": "PyPDF2 не доступний"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pdf_writer = PyPDF2.PdfWriter()
            
            for page in pdf_reader.pages:
                page.rotate(rotation)
                pdf_writer.add_page(page)
            
            # Створити директорію якщо не існує
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            return {
                "success": True,
                "pages_rotated": len(pdf_reader.pages),
                "output_path": output_path
            }
    except Exception as e:
        return {"success": False, "error": f"Помилка повороту: {str(e)}"}


def add_watermark(file_path: str, watermark_text: str, output_path: str) -> Dict[str, Any]:
    """Додати водяний знак на PDF.

    Args:
        file_path: Шлях до PDF файлу
        watermark_text: Текст водяного знаку
        output_path: Шлях для збереження PDF з водяним знаком

    Returns:
        dict з success, pages_watermarked, error
    """
    if not PYPDF2_AVAILABLE:
        return {"success": False, "error": "PyPDF2 не доступний"}

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        # Створити водяний знак як PDF сторінку
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        watermark_path = os.path.join(os.path.dirname(output_path), "watermark.pdf")
        c = canvas.Canvas(watermark_path, pagesize=letter)
        c.setFillColorRGB(0.7, 0.7, 0.7)  # Сірий колір
        c.setFont("Helvetica", 50)
        c.drawString(100, 300, watermark_text)
        c.save()
        
        # Додати водяний знак на кожну сторінку
        with open(watermark_path, 'rb') as watermark_file:
            watermark_reader = PyPDF2.PdfReader(watermark_file)
            watermark_page = watermark_reader.pages[0]
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                pdf_writer = PyPDF2.PdfWriter()
                
                for page in pdf_reader.pages:
                    page.merge_page(watermark_page)
                    pdf_writer.add_page(page)
                
                # Створити директорію якщо не існує
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)
                
                # Видалити тимчасовий файл водяного знаку
                os.remove(watermark_path)
                
                return {
                    "success": True,
                    "pages_watermarked": len(pdf_reader.pages),
                    "output_path": output_path
                }
    except ImportError:
        return {"success": False, "error": "reportlab не доступний (pip install reportlab)"}
    except Exception as e:
        return {"success": False, "error": f"Помилка додавання водяного знаку: {str(e)}"}
