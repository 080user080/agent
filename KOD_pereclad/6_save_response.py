import os
import sys
import re
import logging
import yaml
from pathlib import Path

# Налаштування логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("save_response")

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
        "log_formats": ["txt"],
        "manual_tag": "_check",
        "merged_filename": "merged_UKR.txt",
        "numeric_prefix_regex": r"^\d+",
    }

    for k, v in defaults.items():
        cfg.setdefault(k, v)

    # Переконатися, що output_folder - це підпапка input_folder
    input_folder = cfg["input_folder"]
    output_folder = cfg["output_folder"]
    if not output_folder.startswith(input_folder):
        cfg["output_folder"] = str(Path(input_folder) / output_folder)
    
    return cfg

def get_input_file_from_args():
    """Отримати вхідний файл з аргументів командного рядка"""
    if len(sys.argv) >= 2:
        input_file_path = Path(sys.argv[1])
        logger.info(f"Отримано файл з аргументів: {input_file_path}")
        return input_file_path
    else:
        logger.error("❌ Не вказано файл для збереження в аргументах")
        return None

def save_output(text, out_folder: Path, filename):
    """Зберегти результат у файл"""
    out_folder.mkdir(parents=True, exist_ok=True)
    out_file = out_folder / filename
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(text)
    
    # Більше не викликаємо update_merged_file тут - буде викликатися окремо після обробки всіх файлів
    return out_file

def read_clipboard():
    """Спроба прочитати текст з буфера обміну"""
    try:
        import pyperclip
        data = pyperclip.paste()
        if isinstance(data, str) and data:
            return data
    except Exception:
        pass

    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        data = root.clipboard_get()
        root.destroy()
        if isinstance(data, str) and data:
            return data
    except Exception:
        pass

    return None

def get_response_text_from_clipboard():
    """Отримати текст відповіді ТІЛЬКИ з буфера обміну"""
    max_attempts = 3
    for attempt in range(max_attempts):
        clip = read_clipboard()
        if clip and clip.strip():
            logger.info(f"✅ Текст успішно отримано з буфера обміну (спроба {attempt + 1})")
            return clip.strip()
        
        logger.warning(f"⚠️ Буфер обміну порожній (спроба {attempt + 1}/{max_attempts})")
        if attempt < max_attempts - 1:
            import time
            time.sleep(0.5)
    
    return None

def update_merged_file(output_folder_path):
    """Повністю перезаписує злитий файл з усіма перекладеними текстами"""
    try:
        cfg = load_config()
        merged_filename = cfg.get("merged_filename", "merged_UKR.txt")
        merged_file_path = Path(output_folder_path) / merged_filename
        numeric_rx = re.compile(cfg.get("numeric_prefix_regex", r"^\d+"))
        
        # Знаходимо всі перекладені файли у вихідній папці
        ukr_files = list(Path(output_folder_path).glob("*_UKR.txt"))
        
        if not ukr_files:
            logger.warning("Не знайдено перекладених файлів для об'єднання")
            return
        
        # Сортуємо файли за числовим префіксом
        ordered_files = []
        for file_path in ukr_files:
            # Отримуємо оригінальну основу імені файлу (без _UKR)
            stem = file_path.stem
            if stem.endswith('_UKR'):
                original_stem = stem[:-4]
            else:
                original_stem = stem
                
            match = numeric_rx.match(original_stem)
            num = int(match.group()) if match else 999999
            ordered_files.append((num, file_path))
        
        ordered_files.sort(key=lambda x: x[0])
        
        # Повністю перезаписуємо злитий файл
        with open(merged_file_path, "w", encoding="utf-8") as merged_file:
            for i, (num, file_path) in enumerate(ordered_files):
                # Читаємо вміст файлу та видаляємо зайві переноси на початку та вкінці
                content = file_path.read_text(encoding="utf-8").strip()
                
                # Записуємо вміст без зайвих переносів
                if content:
                    merged_file.write(content)
                    # Додаємо один перенос між файлами (не після останнього)
                    if i < len(ordered_files) - 1:
                        merged_file.write("\n")
        
        logger.info(f"Перезаписано злитий файл: {merged_file_path}")
        logger.info(f"Об'єднано {len(ordered_files)} файлів")
        
    except Exception as e:
        logger.error(f"Помилка при оновленні злитого файлу: {e}")

def main():
    """Головна логіка: зберегти відповідь з буфера обміну для поточного файлу"""
    try:
        cfg = load_config()
    except Exception as e:
        logger.error("Не вдалося завантажити конфіг: %s", e)
        sys.exit(1)

    # Отримуємо вхідний файл з аргументів
    input_file = get_input_file_from_args()
    if not input_file:
        logger.error("❌ Не вказано файл для збереження")
        sys.exit(2)

    # Отримуємо текст ВИКЛЮЧНО з буфера обміну
    response_text = get_response_text_from_clipboard()
    if not response_text:
        logger.error("❌ Не вдалося отримати текст з буфера обміну. Переконайтеся, що відповідь скопійована.")
        sys.exit(3)

    try:
        # Створюємо ім'я вихідного файлу
        stem = input_file.stem
        suffix = input_file.suffix
        out_name = f"{stem}_UKR{suffix}"
        
        # Зберігаємо у вихідній папці
        output_folder = Path(cfg["output_folder"])
        saved_path = save_output(response_text, output_folder, out_name)
        logger.info("✅ Результат збережено: %s", saved_path)
        
        # Оновлюємо злитий файл тільки якщо це останній файл (перевіряємо за наявністю спеціального маркера)
        # Або взагалі не оновлюємо тут - буде викликатися окремо
        sys.exit(0)
        
    except Exception as e:
        logger.error("❌ Помилка при збереженні результату: %s", e)
        sys.exit(4)

if __name__ == "__main__":
    main()