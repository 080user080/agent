"""Виправляє відносні імпорти у functions/ для 16 файлів-заглушок."""

import os

# Маппінг: старий відносний імпорт -> новий відносний імпорт
# Ключ: файл у якому робимо заміну (суфікс шляху)
REPLACEMENTS = {
    '.core_settings': '.runtime.core_settings',
    '.core_tool_runtime': '.runtime.core_tool_runtime',
    '.core_memory': '.runtime.core_memory',
    '.core_cache': '.runtime.core_cache',
    '.core_action_recorder': '.runtime.core_action_recorder',
    '.core_undo_manager': '.runtime.core_undo_manager',
    '.core_session_budget': '.runtime.core_session_budget',
    '.core_planner': '.planning.core_planner',
    '.core_planner_critic': '.planning.core_planner_critic',
    '.core_planner_runner': '.planning.core_planner_runner',
    '.core_plan_compiler': '.planning.core_plan_compiler',
    '.core_gui_guardian': '.gui.core_gui_guardian',
    '.voice_tray_icon': '.gui.voice_tray_icon',
    '.logic_expectations': '.planning.logic_expectations',
    '.logic_task_runner': '.planning.logic_task_runner',
    '.task_spec': '.planning.task_spec',
}

# Додаткові: заміни для `..core_settings` (з підпапок)
REPLACEMENTS_PARENT = {}
for old, new in REPLACEMENTS.items():
    # `..` означає піднятися на рівень вище (тобто з підпапки до кореня functions/)
    parent_old = old.replace('.', '..', 1)  # .xxx -> ..xxx
    parent_new = new.replace('.', '..', 1)
    REPLACEMENTS_PARENT[parent_old] = parent_new


def fix_files():
    count = 0
    for root, dirs, files in os.walk('functions'):
        for f in files:
            if not f.endswith('.py') or f == '__init__.py':
                continue
            fp = os.path.join(root, f)
            try:
                with open(fp, 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read()
            except:
                continue
            
            original = content
            changed = False
            
            # Вибираємо які заміни робити:
            # Якщо файл в підпапці (root != 'functions'), то використовуємо `..` заміни
            if root != 'functions':
                # файл в підпапці, використовуємо `..` 
                replacements_to_use = REPLACEMENTS_PARENT
            else:
                # файл в корені functions/, використовуємо `.`
                replacements_to_use = REPLACEMENTS
            
            for old, new in replacements_to_use.items():
                # Тільки замінюємо на лініях з import
                lines = content.split('\n')
                new_lines = []
                for line in lines:
                    if 'import' in line and old in line and new not in line:
                        line = line.replace(old, new)
                        changed = True
                    new_lines.append(line)
                content = '\n'.join(new_lines)
            
            if changed:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(content)
                count += 1
                print(f'  Fixed: {fp}')
    
    print(f'\nTotal: {count} files fixed')

if __name__ == '__main__':
    fix_files()