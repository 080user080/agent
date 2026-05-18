"""Міграція 16 файлів-заглушок з кореня functions/ у підпапки."""

import os
import sys

# Маппінг: файл -> цільова підпапка
MAPPING = {
    'core_action_recorder': 'runtime',
    'core_cache': 'runtime',
    'core_gui_guardian': 'gui',
    'core_memory': 'runtime',
    'core_plan_compiler': 'planning',
    'core_planner': 'planning',
    'core_planner_critic': 'planning',
    'core_planner_runner': 'planning',
    'core_session_budget': 'runtime',
    'core_settings': 'runtime',  # копія є в llm теж, але runtime основна
    'core_tool_runtime': 'runtime',
    'core_undo_manager': 'runtime',
    'logic_expectations': 'planning',
    'logic_task_runner': 'planning',
    'task_spec': 'planning',
    'voice_tray_icon': 'gui',
}

SKIP_DIRS = {'.venv', 'venv', '__pycache__', '.git', 'backup', '_backup', 'TTS', 'node_modules'}
SKIP_PREFIXES = ('_', '.')

def update_imports():
    """Оновлює всі імпорти у проєкті."""
    count = 0
    for root_dir, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(SKIP_PREFIXES)]
        
        for file in files:
            if not file.endswith('.py'):
                continue
            fpath = os.path.join(root_dir, file)
            
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except:
                continue
            
            original = content
            changed = False
            
            for module_name, target in MAPPING.items():
                # Випадок 1: from functions.<module_name> import ... або import functions.<module_name>
                old_import = f'functions.{module_name}'
                new_import = f'functions.{target}.{module_name}'
                
                # Заміняємо тільки точні збіги (не functions.core_settings.function_name)
                # Використовуємо replace з обережністю
                new_content = content.replace(old_import, new_import)
                if new_content != content:
                    changed = True
                    content = new_content
                    
                # Випадок 2: відносні імпорти з кореня functions/ (.xxx import)
                # Тільки для файлів, які зараз в functions/ корені
                # from .<module_name> import ...
            
            if changed:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(content)
                count += 1
                print(f'  Updated: {fpath}')
    
    print(f'\nTotal: {count} files updated')

def check_remaining_imports():
    """Перевірити чи залишились старі імпорти."""
    print('\n=== Checking remaining old imports ===')
    found = False
    for root_dir, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(SKIP_PREFIXES)]
        
        for file in files:
            if not file.endswith('.py'):
                continue
            fpath = os.path.join(root_dir, file)
            
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except:
                continue
            
            for module_name in MAPPING:
                old_import = f'functions.{module_name}'
                # Шукаємо тільки якщо це ціле слово (не functions.core_settings.something)
                if old_import in content:
                    # Перевіряємо, чи це не вже оновлений шлях
                    target = MAPPING[module_name]
                    new_import = f'functions.{target}.{module_name}'
                    if new_import not in content:
                        # Знайшли старий імпорт
                        for lineno, line in enumerate(content.split('\\n'), 1):
                            if old_import in line and new_import not in line:
                                print(f'  OLD: {fpath}:{lineno}: {line.strip()}')
                                found = True
    
    if not found:
        print('  All imports are clean!')

if __name__ == '__main__':
    update_imports()
    check_remaining_imports()