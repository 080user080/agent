#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1_folder_loader.py - Вибір папки з файлами для перекладу
"""

import os
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

CONFIG_PATH = "config.yaml"


def choose_folder_gui():
    """GUI-вибір папки."""
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)  # Робимо вікно поверх інших
        folder = filedialog.askdirectory(
            title="Виберіть папку з файлами для перекладу"
        )
        root.destroy()
        return folder
    except Exception as e:
        print(f"❌ Помилка при виборі папки: {e}")
        return None


def update_only_input_folder(new_folder: str, config_path: str = CONFIG_PATH):
    """
    Оновлює ТІЛЬКИ одну строку input_folder: "...".
    Інші настройки НЕ чіпає.
    """
    try:
        if not os.path.exists(config_path):
            print("❌ config.yaml не знайдено.")
            return False

        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        updated = False

        for line in lines:
            if line.strip().startswith("input_folder:"):
                # Зберігаємо початкові пробіли та формат
                prefix = line.split("input_folder:")[0]
                new_line = f'{prefix}input_folder: "{new_folder}"\n'
                new_lines.append(new_line)
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            print("⚠️ В config.yaml немає рядка 'input_folder:'. Додаю його в кінець.")
            new_lines.append(f'input_folder: "{new_folder}"\n')

        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print(f"✅ input_folder оновлено на: {new_folder}")
        return True
    except Exception as e:
        print(f"❌ Помилка при оновленні конфігу: {e}")
        return False


def get_input_folder():
    """Якщо в конфізі порожньо або не існує — питає користувача."""
    folder_from_cfg = ""

    # Читаємо config.yaml без YAML (без зміни формату)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("input_folder:"):
                        # Виділяємо значення як є
                        part = line.split("input_folder:", 1)[1].strip()
                        folder_from_cfg = part.strip(' "\'')
                        break
        except Exception as e:
            print(f"⚠️ Помилка читання конфігу: {e}")

    # Перевіряємо чи папка існує
    if folder_from_cfg and os.path.exists(folder_from_cfg) and os.path.isdir(folder_from_cfg):
        print(f"✔ Використовую папку з конфіга: {folder_from_cfg}")
        return Path(folder_from_cfg)
    elif folder_from_cfg:
        print(f"⚠️ Папка з конфіга не існує або не є папкою: {folder_from_cfg}")

    # Якщо папка пуста, не існує або не вказана → питаємо користувача
    print("📁 Папка не вказана, не існує або не є папкою — відкриваю вибір...")
    
    chosen = choose_folder_gui()

    if not chosen or not os.path.exists(chosen):
        print("❌ Папку не вибрано або вона не існує")
        return None

    # Оновлюємо конфіг
    if update_only_input_folder(chosen):
        return Path(chosen)
    else:
        print("⚠️ Не вдалося оновити конфіг, але продовжуємо з вибраною папкою")
        return Path(chosen)


def main():
    """Основна функція скрипта."""
    print("🔍 Пошук папки з файлами для перекладу...")
    
    try:
        folder = get_input_folder()
        
        if folder:
            # Перевіряємо чи є файли в папці
            txt_files = list(folder.glob("*.txt"))
            if txt_files:
                print(f"📂 Папка: {folder}")
                print(f"📄 Знайдено {len(txt_files)} .txt файлів")
                return folder
            else:
                print(f"⚠️ У папці {folder} не знайдено .txt файлів")
                # Все одно повертаємо папку - можливо файли додадуть пізніше
                return folder
        else:
            print("❌ Не вдалося отримати папку для роботи")
            return None
            
    except Exception as e:
        print(f"💥 Критична помилка: {e}")
        return None


if __name__ == "__main__":
    try:
        result = main()
        if result:
            print("✅ Скрипт успішно завершено")
            sys.exit(0)  # Успішний вихід
        else:
            print("❌ Скрипт завершився з помилкою")
            sys.exit(1)  # Вихід з помилкою
    except KeyboardInterrupt:
        print("\n⏹️ Скрипт перервано користувачем")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Непередбачена помилка: {e}")
        sys.exit(1)