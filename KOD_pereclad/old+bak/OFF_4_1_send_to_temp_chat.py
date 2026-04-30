import os
import time
import yaml
import logging
import subprocess
from pathlib import Path

# Налаштування логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("open_chat")

CONFIG_PATH = "config.yaml"
OPEN_CHAT_SCRIPT = "3_open_temp_chat.py"

def load_config():
    """Завантажити конфігурацію"""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Не знайдено файл {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg_all = yaml.safe_load(f) or {}

    if isinstance(cfg_all, dict) and "pereclad" in cfg_all:
        cfg = cfg_all["pereclad"]
    else:
        cfg = cfg_all

    defaults = {"cdp_port": 9222}
    for k, v in defaults.items():
        cfg.setdefault(k, v)

    return cfg

def call_open_temp_chat():
    """Викликати скрипт відкриття тимчасового чату"""
    logger.info("Виклик скрипта відкриття тимчасового чату...")
    try:
        result = subprocess.run(["python", OPEN_CHAT_SCRIPT], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("Скрипт відкриття чату успішно виконано")
            return True
        else:
            logger.warning(f"Скрипт повернув код {result.returncode}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Скрипт відкриття чату перевищив таймаут")
        return False
    except Exception as e:
        logger.error(f"Помилка виконання скрипта: {e}")
        return False

def main():
    """Головна функція для відкриття чату"""
    try:
        cfg = load_config()
        
        # 1. Викликаємо скрипт відкриття тимчасового чату
        if not call_open_temp_chat():
            logger.error("Не вдалося відкрити чат")
            return False

        # 2. Чекаємо завершення відкриття чату
        time.sleep(3)
        
        logger.info("Чат успішно відкрито")
        return True
        
    except Exception as e:
        logger.error(f"Помилка при відкритті чату: {e}")
        return False

if __name__ == "__main__":
    main()