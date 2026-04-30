#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7_update_merged.py
Додає вміст нового файлу до злитого файлу при кожному виклику
З видаленням зайвих переносів рядків
"""

import os
import sys
import re
import logging
import yaml
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("update_merged")

CONFIG_PATH = "config.yaml"

def load_config():
    """Завантажити конфігурацію"""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Не знайдено файл {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    defaults = {
        "input_folder": "input",
        "output_folder": "output",
        "merged_filename": "merged_UKR.txt",
        "numeric_prefix_regex": r"^\d+",
    }

    for k, v in defaults.items():
        cfg.setdefault(k, v)
    
    return cfg

def get_output_folder():
    """Отримати правильний шлях до папки output з конфігурації"""
    cfg = load_config()
    input_folder = Path(cfg["input_folder"])
    output_folder = cfg["output_folder"]
    
    # Якщо output_folder не є абсолютним шляхом, робимо його відносно input_folder
    if not Path(output_folder).is_absolute():
        output_folder = input_folder / output_folder
    
    # Створюємо папку, якщо вона не існує
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"📁 Папка output: {output_folder}")
    return Path(output_folder)

def get_latest_ukr_file(output_folder):
    """Знайти найновіший файл _UKR.txt у папці output"""
    try:
        ukr_files = list(output_folder.glob("*_UKR.txt"))
        if not ukr_files:
            logger.warning(f"Не знайдено UKR файлів у папці: {output_folder}")
            return None
        
        # Сортуємо за часом модифікації (найновіший перший)
        ukr_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        logger.info(f"Знайдено {len(ukr_files)} UKR файлів, найновіший: {ukr_files[0].name}")
        return ukr_files[0]
    except Exception as e:
        logger.error(f"Помилка пошуку UKR файлів: {e}")
        return None

def normalize_line_breaks(text):
    """Нормалізувати переноси рядків: замінити послідовності з 2+ переносів на один перенос"""
    # Замінюємо будь-яку послідовність з 2+ переносів на один перенос
    normalized = re.sub(r'\n{3,}', '\n\n', text)
    # Видаляємо переноси на початку та в кінці тексту
    return normalized.strip()

def append_to_merged_file(output_folder_path, new_file_path):
    """Додати вміст нового файлу до злитого файлу з нормалізацією переносів"""
    try:
        cfg = load_config()
        merged_filename = cfg.get("merged_filename", "merged_UKR.txt")
        merged_file_path = output_folder_path / merged_filename
        
        # Читаємо вміст нового файлу
        new_content = new_file_path.read_text(encoding="utf-8").strip()
        if not new_content:
            logger.warning(f"Файл {new_file_path.name} порожній, нічого не додано")
            return
        
        # Нормалізуємо переноси в новому вмісті
        new_content_normalized = normalize_line_breaks(new_content)
        
        # Перевіряємо, чи вже існує злитий файл
        if merged_file_path.exists():
            # Читаємо існуючий вміст
            existing_content = merged_file_path.read_text(encoding="utf-8")
            
            # Нормалізуємо переноси в існуючому вмісті
            existing_content_normalized = normalize_line_breaks(existing_content)
            
            # Перевіряємо, чи новий вміст вже є в злитому файлі
            if new_content_normalized in existing_content_normalized:
                logger.info(f"Вміст файлу {new_file_path.name} вже є у злитому файлі, пропускаємо")
                return
            
            # Об'єднуємо вміст
            combined_content = existing_content_normalized + "\n" + new_content_normalized
            
            # Нормалізуємо переноси в об'єднаному вмісті
            final_content = normalize_line_breaks(combined_content)
            
            # Записуємо оновлений вміст
            merged_file_path.write_text(final_content, encoding="utf-8")
        else:
            # Створюємо новий злитий файл з нормалізованими переносами
            merged_file_path.write_text(new_content_normalized, encoding="utf-8")
        
        logger.info(f"✅ Вміст файлу {new_file_path.name} додано до злитого файлу (переноси нормалізовано)")
        
    except Exception as e:
        logger.error(f"❌ Помилка при додаванні до злитого файлу: {e}")

def main():
    try:
        # Отримуємо правильну папку output з конфігурації
        output_folder = get_output_folder()
        
        # Знаходимо найновіший UKR файл
        latest_file = get_latest_ukr_file(output_folder)
        if not latest_file:
            logger.warning("Не знайдено жодного UKR файлу для додавання")
            return 0
        
        # Додаємо його вміст до злитого файлу
        append_to_merged_file(output_folder, latest_file)
        return 0
        
    except Exception as e:
        logger.error(f"❌ Помилка при оновленні злитого файлу: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())