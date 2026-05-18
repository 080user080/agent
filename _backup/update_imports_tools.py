"""Оновлює всі імпорти `functions.tools_xxx` → `functions.tools.tools_xxx`."""
import os
import glob

TOOLS = [
    'tools_app_recognizer', 'tools_browser_cdp', 'tools_comfyui',
    'tools_excel', 'tools_ffmpeg', 'tools_image_pillow',
    'tools_mouse_keyboard', 'tools_notification', 'tools_ocr',
    'tools_pdf', 'tools_playwright', 'tools_screen_capture',
    'tools_ui_accessibility', 'tools_ui_detector', 'tools_visual_diff',
    'tools_window_manager', 'tools_windsurf', 'tools_word',
]

# Враховуємо відносні імпорти всередині functions/ (наприклад у ai_actors.py: `from .tools_xxx import`)
# та імпорти з patch('functions.tools_xxx...')
# та імпорти з @patch('functions.tools_xxx...') в тестах

# Пропускаємо папки:
SKIP_DIRS = {'.venv', 'venv', '__pycache__', '.git', 'backup', '_backup', 'TTS', 'node_modules'}
SKIP_PREFIXES = ('_', '.')  # пропускаємо приховані папки

count_updated = 0
count_files = 0

for root_dir, dirs, files in os.walk('.'):
    # Фільтруємо пропущені папки
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(SKIP_PREFIXES)]
    
    for file in files:
        if not file.endswith('.py'):
            continue
        fpath = os.path.join(root_dir, file)
        
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except:
            continue
        
        original = content
        
        # Оновлюємо імпорти
        for tool in TOOLS:
            old_import = f'functions.{tool}'
            new_import = f'functions.tools.{tool}'
            content = content.replace(old_import, new_import)
        
        if content != original:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
            count_files += 1
            print(f'  Updated: {fpath}')
            # Показуємо змінені рядки
            orig_lines = original.split('\n')
            new_lines = content.split('\n')
            for i, (ol, nl) in enumerate(zip(orig_lines, new_lines), 1):
                if ol != nl:
                    print(f'    L{i}: {nl.strip()}')

print(f'\nDone: {count_files} files updated.')