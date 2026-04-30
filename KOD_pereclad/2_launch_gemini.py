#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
launch_gemini.py
Запускає/підключається до Chrome з debug-портом і відкриває/активує вкладку Gemini.
Використано як приклад: KOD_pereclad.py. #GPT
"""
import time
import socket
import subprocess
import logging
from pathlib import Path

# Залежності: playwright, pyyaml (для можливості підвантажити конфіг, якщо потрібно)
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception as e:
    raise RuntimeError("Відсутні залежності. Виконайте:\n  pip install playwright pyyaml\n  playwright install") from e

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("launch_gemini")

# Налаштування — взято з KOD_pereclad.py (за потреби змініть шляхи)
DEFAULT = {
    "gemini_url": "https://gemini.google.com/app",
    "cdp_port": 9222,
    "chrome_executable_path": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "chrome_user_data_dir": r"C:\Temp\chrome_debug_profile",
    "chrome_launch_timeout": 20,
    "auto_launch_chrome": True,
}
# Якщо у вас є config.yaml поряд з цим скриптом — можна підвантажити і замінити DEFAULT (необов'язково)
CFG_PATH = Path("config.yaml")

def is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except Exception:
        return False

def launch_chrome_if_needed(chrome_path: str, user_data_dir: str, port: int, url: str, timeout: int = 20) -> bool:
    """Запускає Chrome з --remote-debugging-port якщо порт не слухає. #GPT"""
    if is_port_open("127.0.0.1", port):
        logger.info("CDP порт %s вже відкритий — не запускаю Chrome.", port)
        return True

    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-default-browser-check",
        "--no-first-run",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-features=RendererCodeIntegrity",
        url
    ]
    logger.info("Запускаю Chrome: %s ...", chrome_path)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        logger.error("Chrome не знайдено за шляхом: %s", chrome_path)
        return False
    except Exception as e:
        logger.error("Помилка запуску Chrome: %s", e)
        return False

    # Чекаємо коли порт відкриється або процес завершиться
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open("127.0.0.1", port):
            logger.info("Chrome запущено і CDP порт %s доступний.", port)
            return True
        if proc.poll() is not None:
            stdout, stderr = proc.communicate(timeout=1)
            logger.error("Chrome завершився з кодом %s. stderr: %s", proc.returncode, stderr)
            return False
        time.sleep(1)
    logger.error("Chrome не відкрив CDP порт за %s секунд.", timeout)
    return False

def choose_target_page(conn):
    """Покращена логіка вибору сторінки: шукаємо вкладку з 'Google Gemini' у заголовку або URL"""
    pages = []
    # підтримка варіантів API: conn.pages або контексти
    try:
        pages = getattr(conn, "pages", []) or []
    except Exception:
        pages = []
    # Пробуємо знайти додатково в контекстах
    try:
        contexts = getattr(conn, "contexts", []) or []
        for ctx in contexts:
            ctx_pages = getattr(ctx, "pages", []) or []
            for p in ctx_pages:
                if p not in pages:
                    pages.append(p)
    except Exception:
        pass

    # Якщо немає сторінок — створюємо нову
    if not pages:
        try:
            page = conn.new_page()
            return page
        except Exception:
            return None

    logger.info(f"Знайдено {len(pages)} вкладок")
    
    # Логуємо всі знайдені вкладки для діагностики
    for i, page in enumerate(pages):
        try:
            page_url = page.url or "невідомий URL"
            page_title = page.title() or "без заголовка"
            logger.info(f"Вкладка {i}: {page_title} - {page_url}")
        except Exception as e:
            logger.info(f"Вкладка {i}: не вдалося отримати інформацію - {e}")
    
    # Покращена логіка пошуку вкладки Gemini (з коду 3_open_temp_chat.py)
    gemini_page = None
    target_title = "Google Gemini"
    
    for page in pages:
        try:
            page_title = page.title() or ""
            page_url = page.url() or ""
            
            if target_title.lower() in page_title.lower():
                gemini_page = page
                logger.info(f"Знайдено вкладку за заголовком: {page_title}")
                break
            
            # Додатково перевіряємо URL
            if "gemini.google.com" in page_url:
                gemini_page = page
                logger.info(f"Знайдено вкладку за URL: {page_url}")
                break
                
        except Exception as e:
            logger.debug(f"Помилка перевірки вкладки: {e}")
            continue
    
    if gemini_page:
        logger.info(f"Обрано вкладку: {gemini_page.title()}")
        return gemini_page
    else:
        logger.error(f"Не знайдено вкладку з заголовком '{target_title}'")
        # Якщо не знайшли Gemini, повертаємо першу доступну вкладку
        return pages[0] if pages else None

def activate_gemini_tab(page):
    """Активувати вкладку Gemini"""
    try:
        if page:
            page.bring_to_front()
            logger.info("Вкладка Gemini активована")
            time.sleep(0.8)
            return True
    except Exception as e:
        logger.error(f"Помилка активації вкладки: {e}")
    return False

def connect_and_open_gemini(cdp_port: int, gemini_url: str, launch_if_missing: bool = True) -> bool:
    """Підключається до Chrome через CDP, знаходить/відкриває вкладку Gemini. #GPT"""
    url = f"http://127.0.0.1:{cdp_port}"
    play = None
    conn = None
    try:
        play = sync_playwright().start()
        conn = play.chromium.connect_over_cdp(url)
        logger.info("Підключено до CDP %s", url)
    except Exception as e:
        logger.warning("Не вдалося підключитися до CDP: %s", e)
        if launch_if_missing:
            logger.info("Спроба автозапуску Chrome...")
            ok = launch_chrome_if_needed(
                DEFAULT["chrome_executable_path"],
                DEFAULT["chrome_user_data_dir"],
                cdp_port,
                gemini_url,
                timeout=DEFAULT["chrome_launch_timeout"]
            )
            if not ok:
                if play:
                    try: play.stop()
                    except Exception: pass
                return False
            # Повторна спроба підключення
            try:
                conn = play.chromium.connect_over_cdp(url)
                logger.info("Підключено до CDP після автозапуску.")
            except Exception as e2:
                logger.error("Повторне підключення не вдалось: %s", e2)
                try: play.stop()
                except Exception: pass
                return False
        else:
            return False

    try:
        # Використовуємо покращену логіку пошуку вкладки Gemini з 3_open_temp_chat.py
        page = choose_target_page(conn)
        
        if page:
            logger.info("Знайдено існуючу вкладку Gemini — активую.")
            try:
                page.bring_to_front()
            except Exception:
                logger.debug("bring_to_front недоступний, спробую focus через evaluate.")
                try:
                    # намагатимемося сфокусувати таб через CDP evaluate
                    page.evaluate("window.focus && window.focus()")
                except Exception:
                    pass
            # Переконаємось, що URL відкритий (іноді потрібно перезавантажити)
            try:
                if not page.url or "about:blank" in page.url:
                    page.goto(gemini_url, timeout=30000)
            except Exception:
                pass
            return True

        # Якщо не знайдено — відкриваємо нову вкладку з Gemini
        logger.info("Вкладка Gemini не знайдена — відкриваю нову вкладку.")
        try:
            new_page = conn.new_page()
            new_page.goto(gemini_url, timeout=45000)
            # даємо час на завантаження
            try:
                new_page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            try:
                new_page.bring_to_front()
            except Exception:
                pass
            logger.info("Відкрито нову вкладку Gemini.")
            return True
        except Exception as e:
            logger.error("Не вдалося відкрити нову вкладку: %s", e)
            return False

    finally:
        # Закриваємо з'єднання, але залишаємо сам Chrome працювати
        try:
            if conn:
                conn.close()
        except Exception:
            pass
        try:
            if play:
                play.stop()
        except Exception:
            pass

def main():
    cdp_port = DEFAULT["cdp_port"]
    gemini_url = DEFAULT["gemini_url"]
    # Якщо потрібно — підвантажити config.yaml і оновити змінні
    if CFG_PATH.exists():
        try:
            import yaml
            cfg = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}
            cdp_port = int(cfg.get("cdp_port", cdp_port))
            gemini_url = cfg.get("gemini_url", gemini_url)
            DEFAULT["chrome_executable_path"] = cfg.get("chrome_executable_path", DEFAULT["chrome_executable_path"])
            DEFAULT["chrome_user_data_dir"] = cfg.get("chrome_user_data_dir", DEFAULT["chrome_user_data_dir"])
            DEFAULT["chrome_launch_timeout"] = int(cfg.get("chrome_launch_timeout", DEFAULT["chrome_launch_timeout"]))
        except Exception:
            logger.debug("Не вдалося прочитати config.yaml — використовую DEFAULT.")

    success = connect_and_open_gemini(cdp_port=cdp_port, gemini_url=gemini_url, launch_if_missing=DEFAULT["auto_launch_chrome"])
    if not success:
        logger.error("Операція неуспішна.")
        raise SystemExit(1)
    logger.info("Готово.")
    raise SystemExit(0)

if __name__ == "__main__":
    main()