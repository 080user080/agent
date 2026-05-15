"""
Скрипт: замінити 5-рядкові файли-заглушки tools_*.py в functions/
на повноцінний код з functions/tools/tools_*.py та functions/gui/tools_*.py.

Варіант 3: згорнути реструктуризацію назад для цих модулів.
Оригінали в functions/tools/ та functions/gui/ залишаються недоторканими.
"""

import os
import shutil

# Мапа: цільовий файл-заглушка -> файл-джерело
STUBS = {
    # Група 1: джерела з functions/tools/
    "functions/tools_app_recognizer.py": "functions/tools/tools_app_recognizer.py",
    "functions/tools_browser_cdp.py": "functions/tools/tools_browser_cdp.py",
    "functions/tools_comfyui.py": "functions/tools/tools_comfyui.py",
    "functions/tools_excel.py": "functions/tools/tools_excel.py",
    "functions/tools_ffmpeg.py": "functions/tools/tools_ffmpeg.py",
    "functions/tools_image_pillow.py": "functions/tools/tools_image_pillow.py",
    "functions/tools_notification.py": "functions/tools/tools_notification.py",
    "functions/tools_pdf.py": "functions/tools/tools_pdf.py",
    "functions/tools_playwright.py": "functions/tools/tools_playwright.py",
    "functions/tools_windsurf.py": "functions/tools/tools_windsurf.py",
    "functions/tools_word.py": "functions/tools/tools_word.py",
    # Група 2: джерела з functions/gui/
    "functions/tools_mouse_keyboard.py": "functions/gui/tools_mouse_keyboard.py",
    "functions/tools_ocr.py": "functions/gui/tools_ocr.py",
    "functions/tools_screen_capture.py": "functions/gui/tools_screen_capture.py",
    "functions/tools_ui_accessibility.py": "functions/gui/tools_ui_accessibility.py",
    "functions/tools_ui_detector.py": "functions/gui/tools_ui_detector.py",
    "functions/tools_visual_diff.py": "functions/gui/tools_visual_diff.py",
    "functions/tools_window_manager.py": "functions/gui/tools_window_manager.py",
}


def fix_stubs():
    base = os.path.dirname(os.path.abspath(__file__))
    count = 0
    errors = []

    for target_rel, source_rel in STUBS.items():
        target = os.path.join(base, target_rel)
        source = os.path.join(base, source_rel)

        # Перевіряємо що ціль — це заглушка (5 рядків, або починається з # Re-export)
        if not os.path.exists(target):
            errors.append(f"Ціль не існує: {target_rel}")
            continue

        if not os.path.exists(source):
            errors.append(f"Джерело не існує: {source_rel}")
            continue

        with open(target, encoding="utf-8") as f:
            first_line = f.readline()
        is_stub = first_line.startswith("# Re-export") or first_line.startswith("# Re-export")

        if not is_stub:
            errors.append(f"Ціль {target_rel} не схожа на заглушку (перший рядок: {first_line!r})")
            continue

        # Копіюємо код з джерела в ціль
        shutil.copy2(source, target)
        count += 1
        print(f"  ✓ {target_rel} <- {source_rel}")

    print(f"\n✅ Оновлено файлів: {count}")
    if errors:
        print(f"❌ Помилок: {len(errors)}")
        for e in errors:
            print(f"   {e}")

    return count, errors


if __name__ == "__main__":
    fix_stubs()