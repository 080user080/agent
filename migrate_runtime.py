#!/usr/bin/env python3
"""
Одноразовий скрипт міграції JSON-файлів у нову структуру runtime/.

Переносить:
  runtime/user_settings.json          → runtime/settings/user_settings.json
  functions/runtime/agent_memory.json → runtime/memory/long_term_memory.json
  logs/*.json (checkpoints)           → runtime/checkpoints/
  functions/runtime/cache_data.json   → runtime/cache/cache_data.json
  macros/*.json                       → runtime/macros/
  profiles/*.json                     → runtime/profiles/
  logs/gui_actions.jsonl              → runtime/logs/gui_actions.jsonl
  logs/screenshots/*                  → runtime/logs/screenshots/
  logs/audit.jsonl                    → runtime/logs/audit.jsonl
  logs/snapshots/*                    → runtime/snapshots/

Скрипт безпечний — НЕ видаляє старі файли, лише копіює, якщо ціль не існує.
"""
import json
import os
import shutil
import sys
from pathlib import Path

# === Конфігурація ===
PROJECT_ROOT = Path(__file__).resolve().parent
RUNTIME = PROJECT_ROOT / "runtime"
FUNCTIONS_RUNTIME = PROJECT_ROOT / "functions" / "runtime"
LOGS = PROJECT_ROOT / "logs"
MACROS = PROJECT_ROOT / "macros"
PROFILES = PROJECT_ROOT / "profiles"

# === Нова структура ===
SETTINGS_DIR = RUNTIME / "settings"
MEMORY_DIR = RUNTIME / "memory"
CHECKPOINTS_DIR = RUNTIME / "checkpoints"
CACHE_DIR = RUNTIME / "cache"
MACROS_DIR = RUNTIME / "macros"
PROFILES_DIR = RUNTIME / "profiles"
SELF_LEARNING_DIR = RUNTIME / "self_learning"
LOGS_DIR = RUNTIME / "logs"
SNAPSHOTS_DIR = RUNTIME / "snapshots"

# === Список міграцій: (source, dest, is_dir) ===
MIGRATIONS = [
    # user_settings.json
    (RUNTIME / "user_settings.json", SETTINGS_DIR / "user_settings.json", False),

    # agent_memory.json → long_term_memory.json
    (FUNCTIONS_RUNTIME / "agent_memory.json", MEMORY_DIR / "long_term_memory.json", False),

    # cache_data.json (був у functions/runtime/)
    (FUNCTIONS_RUNTIME / "cache_data.json", CACHE_DIR / "cache_data.json", False),

    # macros/ (вся директорія)
    (MACROS, MACROS_DIR, True),

    # profiles/ (вся директорія)
    (PROFILES, PROFILES_DIR, True),

    # logs/gui_actions.jsonl
    (LOGS / "gui_actions.jsonl", LOGS_DIR / "gui_actions.jsonl", False),

    # logs/screenshots/ (вся директорія)
    (LOGS / "screenshots", LOGS_DIR / "screenshots", True),

    # logs/audit.jsonl
    (LOGS / "audit.jsonl", LOGS_DIR / "audit.jsonl", False),

    # logs/snapshots/ (вся директорія)
    (LOGS / "snapshots", SNAPSHOTS_DIR, True),

    # self_learning/ (вже в runtime/)
    # (залишається на місці, нічого не робимо)
]

# === Створення директорій ===
DIRS = [
    SETTINGS_DIR, MEMORY_DIR, CHECKPOINTS_DIR, CACHE_DIR,
    MACROS_DIR, PROFILES_DIR, LOGS_DIR, SNAPSHOTS_DIR,
]
for d in DIRS:
    d.mkdir(parents=True, exist_ok=True)
    print(f"[DIR] {d}/")

# === Виконання міграції ===
copied = 0
skipped = 0
errors = 0

for src, dst, is_dir in MIGRATIONS:
    if not src.exists():
        print(f"[SKIP] {src} — не існує, пропускаємо")
        skipped += 1
        continue

    if is_dir:
        # Копіюємо вміст директорії
        for item in src.iterdir():
            dest_item = dst / item.name
            if dest_item.exists():
                skipped += 1
                continue
            if item.is_file():
                shutil.copy2(item, dest_item)
                print(f"[COPY] {item} -> {dest_item}")
                copied += 1
            elif item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
                print(f"[DIR]  {item}/ -> {dest_item}/")
                copied += 1
    else:
        if dst.exists():
            print(f"[SKIP] {dst} — вже існує, пропускаємо")
            skipped += 1
            continue
        try:
            shutil.copy2(src, dst)
            print(f"[COPY] {src} -> {dst}")
            copied += 1
        except Exception as e:
            print(f"[ERROR] Помилка копіювання {src}: {e}")
            errors += 1

# === Підсумок ===
print()
print("=" * 60)
print("Міграція завершена!")
print(f"  Сколійовано: {copied}")
print(f"  Пропущено (вже існує або не знайдено): {skipped}")
print(f"  Помилок: {errors}")
print()
print("[WARN] Старі файли НЕ видалено. Якщо все працює — видаліть вручну:")
print("   - functions/runtime/agent_memory.json")
print("   - functions/runtime/cache_data.json")
print("   - runtime/user_settings.json (старий)")
print("   - logs/ (якщо пуста після міграції)")
print("   - macros/ (якщо пуста після міграції)")
print("   - profiles/ (якщо пуста після міграції)")
print("=" * 60)