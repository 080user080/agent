"""Скрипт для міграції tools_*.py з кореня functions/ у підпапки tools/ або gui/."""

import os
import re
import shutil
from pathlib import Path

ROOT = Path("functions")
TOOLS_DIR = ROOT / "tools"
GUI_DIR = ROOT / "gui"

def find_files():
    """Знайти всі tools_*.py в корені та визначити цільову папку."""
    files = sorted([f for f in os.listdir(ROOT) if f.startswith("tools_") and f.endswith(".py")])
    result = {}
    for f in files:
        name = f.replace(".py", "")
        target = None
        if (TOOLS_DIR / f).exists():
            target = "tools"
        elif (GUI_DIR / f).exists():
            target = "gui"
        result[name] = {"file": f, "target": target}
    return result

def find_imports(module_name):
    """Знайти всі імпорти старого модуля у проєкті."""
    pattern_import = re.compile(rf'^.*?import\s+functions\.{re.escape(module_name)}\b.*$', re.MULTILINE)
    pattern_from = re.compile(rf'^.*?from\s+functions\.{re.escape(module_name)}\b\s+import\s+.*$', re.MULTILINE)
    pattern_patch = re.compile(rf"patch\('functions\.{re.escape(module_name)}\b")
    pattern_mock = re.compile(rf"['\"]functions\.{re.escape(module_name)}\.[\w.]+['\"]")

    matches = []
    for root_dir, dirs, files in os.walk("."):
        # Пропускаємо backup, .venv, TTS, __pycache__
        skip_dirs = {".venv", "venv", "__pycache__", ".git", "backup", "_backup", "TTS"}
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith("_")]
        
        for file in files:
            if not file.endswith(".py"):
                continue
            fpath = os.path.join(root_dir, file)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except:
                continue
            
            for lineno, line in enumerate(content.split("\n"), 1):
                if pattern_import.match(line) or pattern_from.match(line) or pattern_patch.search(line):
                    matches.append((fpath, lineno, line.strip()))
    return matches

def update_imports(module_name, new_module_path):
    """Оновити імпорти зі старого шляху на новий."""
    old_import = f"functions.{module_name}"
    new_import = new_module_path
    count = 0
    for root_dir, dirs, files in os.walk("."):
        skip_dirs = {".venv", "venv", "__pycache__", ".git", "backup", "_backup", "TTS"}
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith("_")]
        
        for file in files:
            if not file.endswith(".py"):
                continue
            fpath = os.path.join(root_dir, file)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except:
                continue
            
            if old_import in content:
                new_content = content.replace(old_import, new_import)
                if new_content != content:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"  Updated: {fpath}")
                    count += 1
    return count

def main():
    files_map = find_files()
    print("=== Tools files in functions/ root ===")
    for name, info in files_map.items():
        target = info["target"] or "MISSING"
        print(f"  {info['file']} -> {target}/")
    
    print("\n=== Checking imports ===")
    for name in sorted(files_map.keys()):
        info = files_map[name]
        if not info["target"]:
            print(f"\n⚠️  {info['file']}: no target directory, skipping")
            continue
        imports = find_imports(name)
        if imports:
            print(f"\n{info['file']} -> {info['target']}/ ({len(imports)} import locations)")
            for fpath, lineno, line in imports:
                print(f"    {fpath}:{lineno}: {line}")
        else:
            print(f"\n{info['file']} -> {info['target']}/ (no direct imports found)")
    
    # Показуємо тільки, не змінюємо автоматично
    print("\n\n=== DRY RUN COMPLETE. Run with --execute to apply ===")

if __name__ == "__main__":
    main()