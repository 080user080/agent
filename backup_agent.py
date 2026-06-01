#!/usr/bin/env python3
"""Створює 7z-архів проєкту в d:\Python\agent_backup з виключеннями."""

import subprocess, shutil, time, os
from pathlib import Path

REPO = Path(r"d:\Python\agent")
BACKUP_DIR = Path(r"d:\Python\agent_backup")
SZ = r"c:\Program Files\7-Zip\7z.exe"

EXCLUDE_DIRS = [
    ".git", "pytest_cache", ".ruff_cache", ".vscode", ".windsurf",
    "__pycache__", "backup", "debug_logs", "logs", "macros",
    "scenarios", "TEST_GUI", "tests", "TTS", "tts_cache", "voices",
]

EXCLUDE_FILES = [
    "Full_*.txt", "High_*.txt", "Low_*.txt", "Medium_*.txt",
    ".coverage", "2.0.0", "requirements.txt", "requirements-dev.txt",
    "coverage.xml",
]

BACKUP_RETENTION_DAYS = 30  # видаляти бекапи старші за N днів


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    archive_name = f"{timestamp}.7z"
    archive_path = BACKUP_DIR / archive_name

    print(f"=== Creating backup: {archive_name} ===")

    # Будуємо команду
    cmd = [
        SZ, "a", "-t7z", "-mx5", "-r",
        str(archive_path),
        str(REPO),
    ]
    for d in EXCLUDE_DIRS:
        cmd.append(f"-xr!{d}\\")
    for f in EXCLUDE_FILES:
        cmd.append(f"-xr!{f}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[ERROR] Backup creation FAILED!")
        print(result.stderr)
        return False

    print(f"=== Backup created: {archive_path} ===")

    # Видалення старих бекапів
    print(f"=== Cleaning backups older than {BACKUP_RETENTION_DAYS} days ===")
    now = time.time()
    cutoff = now - BACKUP_RETENTION_DAYS * 86400
    for f in BACKUP_DIR.glob("*.7z"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            print(f"  Deleted old backup: {f.name}")

    return True


if __name__ == "__main__":
    main()