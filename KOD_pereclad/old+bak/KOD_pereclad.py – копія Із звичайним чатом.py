#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KOD_pereclad.py
Автоматизація передачі текстів у Google Gemini через вже відкритий Google Chrome (CDP).
Варіант 1: підключення до вже відкритого Chrome з --remote-debugging-port=9222

Вимоги:
pip install playwright pyyaml pyperclip
playwright install

Всі мої правки/правила помічено коментарем "#GPT".
"""
#GPT

import os
import re
import sys
import time
import json
import random
import logging
from pathlib import Path
from datetime import datetime

# Зовнішні бібліотеки
try:
    import yaml  # pyyaml
    import pyperclip
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception as e:
    print("Відсутні залежності. Виконайте:\n  pip install playwright pyyaml pyperclip\n  playwright install")
    raise

# Логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("KOD_pereclad")

# ===== DEFAULT CONFIG =====
#GPT
DEFAULT_CONFIG = {
    "gemini_url": "https://gemini.google.com/",
    "output_folder": "output",
    "merged_filename": "merged_UKR.txt",
    "use_numeric_prefix": True,
    "numeric_prefix_regex": r"^\d+",
    "template_message": "Зробити адаптивний переклад максимально точний. У відповіді тільки перекладений текст без жодних твоїх питань побажань чи вставок.",
    "hotkey_new_chat": "ctrl_shift_o",  # or 'search_and_ctrl_enter'
    "on_bad_response": "mark_for_manual",  # retry | mark_for_manual | skip
    "manual_tag": "_check",
    "max_retries": 2,
    "page_load_timeout": 30,
    "response_timeout": 10,
    "use_dom_method": ["copy_button", "js_full", "clipboard_via_js", "keyboard_copy"],
    "log_formats": ["txt", "json"],
    # CDP settings (variant 1)
    "connect_via_cdp": True,
    "cdp_port": 9222,
    "chrome_executable_path": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "chrome_user_data_dir": r"C:\Temp\chrome_debug_profile", 
    "auto_launch_chrome": True,
    "chrome_launch_timeout": 20,
    # GUI / input
    "input_folder": "",
}
CONFIG_PATH = Path("config.yaml")

# ===== Helpers: config load with encoding fallback =====
#GPT
def create_default_config(path: Path = CONFIG_PATH):
    content = yaml.safe_dump(DEFAULT_CONFIG, allow_unicode=True)
    path.write_text(content, encoding="utf-8")
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Не вдалося створити конфігураційний файл: {path}")
    logger.info(f"Створено config: {path}")

def load_config(path: Path = CONFIG_PATH):
    if not path.exists():
        create_default_config(path)
    # Спроба прочитати в UTF-8, якщо не вдається — cp1251
    text = None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        try:
            text = path.read_text(encoding="cp1251")
            logger.warning("config.yaml прочитано як cp1251. Рекомендую зберегти у UTF-8.")
        except Exception as e:
            logger.error("Не вдалось прочитати config.yaml: %s", e)
            raise
    cfg = yaml.safe_load(text) or {}
    # вписати дефолти, якщо чогось нема
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


# ===== GUI вибору папки (проста) =====
#GPT
def choose_input_folder_via_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as e:
        logger.error("tkinter недоступний. Вкажіть 'input_folder' у config.yaml")
        return ""
    # Більш надійна Windows-орієнтована реалізація: показати просте вікно з кнопкою.
    root = tk.Tk()
    result = {'path': ''}
    try:
        root.title('Вибір папки для перекладу')
        root.geometry('380x120')
        root.resizable(False, False)
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass
        from tkinter import ttk
        lbl = ttk.Label(root, text='Натисніть кнопку, щоб вибрати вхідну папку з файлами .txt', wraplength=360)
        lbl.pack(padx=10, pady=(10,6))
        def on_select():
            try:
                p = filedialog.askdirectory(parent=root, title='Виберіть вхідну папку з .txt файлами')
            except Exception:
                p = filedialog.askdirectory(title='Виберіть вхідну папку з .txt файлами')
            if p:
                result['path'] = p
            try:
                root.quit()
            except Exception as e:
                pass
        btn = ttk.Button(root, text='Вибрати папку', command=on_select)
        btn.pack(pady=(0,12))
        # Спроба підняти вікно у фокус (Windows)
        if os.name == 'nt':
            try:
                import ctypes
                root.update_idletasks()
                ctypes.windll.user32.SetForegroundWindow(root.winfo_id())
            except Exception:
                logger.debug("Не вдалося встановити фокус на вікно")
        try:
            root.mainloop()
        except Exception as e:
            logger.error("Помилка в GUI: %s", e)
    finally:
        try:
            root.attributes('-topmost', False)
        except Exception as e:
            logger.debug("Помилка при знятті topmost: %s", e)
        try:
            root.destroy()
        except Exception as e:
            pass
    return result['path'] or ''

# ===== Scan files by numeric prefix =====
#GPT
def scan_text_files(input_folder: Path, numeric_regex: str):
    files = [p for p in sorted(input_folder.iterdir()) if p.is_file() and p.suffix.lower() == ".txt"]
    numeric_files = []
    for p in files:
        m = re.match(numeric_regex, p.name)
        if m:
            try:
                prefix = int(m.group(0))
            except Exception:
                # Якщо дуже довге або починається з нулів — зберігаємо як є (use ordering by full name)
                prefix = None
            numeric_files.append((prefix if prefix is not None else float("inf"), p))
    numeric_files.sort(key=lambda x: (x[0], x[1].name))
    return [p for _, p in numeric_files]

# ===== Process logger =====
#GPT
class ProcessLogger:
    def __init__(self, out_folder: Path, formats=("txt","json")):
        self.out_folder = out_folder
        self.formats = formats
        self.records = []
        self.txt_path = out_folder / "process_log.txt"
        self.json_path = out_folder / "process_log.json"
        # Очистити попередній текстовий лог якщо існує
        if self.txt_path.exists():
            self.txt_path.unlink()

    def add(self, record: dict):
        self.records.append(record)
        with self.txt_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def finalize(self):
        with self.json_path.open("w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

# ===== Gemini controller: connect via CDP to existing Chrome =====
#GPT
class GeminiController:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.play = None
        self.conn = None
        self.context = None
        self.page = None
        self.last_response_status = None
    
    def is_connected(self):
        """Перевіряє, чи активне з'єднання"""
        try:
            return (self.conn and 
                    hasattr(self.conn, 'is_connected') and self.conn.is_connected())
        except Exception:
            return False

    def launch_chrome_with_debug(self):
        """Запускає Chrome з remote debugging портом"""
        try:
            import subprocess
            chrome_path = self.cfg["chrome_executable_path"]
            user_data_dir = self.cfg["chrome_user_data_dir"]
            port = self.cfg["cdp_port"]
            
            # Створюємо папку для профілю, якщо не існує
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)
            
            # Команда для запуску Chrome
            cmd = [
                chrome_path,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={user_data_dir}",
                "--no-default-browser-check",
                "--no-first-run",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding", 
                "--disable-features=RendererCodeIntegrity",
                self.cfg.get("gemini_url", "https://gemini.google.com/")
            ]
            
            logger.info(f"🚀 Запуск Chrome з параметрами: --remote-debugging-port={port}")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Покращене очікування запуску Chrome з кількома методами перевірки
            timeout = self.cfg.get("chrome_launch_timeout", 30)
            start_time = time.time()
            check_count = 0
            
            while (time.time() - start_time) < timeout:
                check_count += 1
                elapsed = int(time.time() - start_time)
                remaining = timeout - elapsed
                
                if check_count % 2 == 0:  # Кожні 2 перевірки (4 секунди)
                    logger.info(f"⏳ Очікування Chrome: {elapsed}с пройшло, {remaining}с залишилось")
                
                # Спосіб 1: Перевірка через socket (чи порт відкритий)
                if self.is_port_open('127.0.0.1', port):
                    # Спосіб 2: Перевірка через CDP підключення
                    try:
                        temp_play = sync_playwright().start()
                        temp_conn = temp_play.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                        temp_conn.close()
                        temp_play.stop()
                        logger.info(f"✅ Chrome готовий до підключення через {elapsed} секунд")
                        return True
                    except Exception as e:
                        logger.debug(f"CDP ще не готов: {e}")
                
                # Перевірка, чи процес Chrome ще працює
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    logger.error(f"❌ Chrome завершив роботу. Код: {process.returncode}")
                    if stderr:
                        logger.error(f"Помилка Chrome: {stderr}")
                    return False
                
                time.sleep(2)
                    
            logger.error(f"❌ Chrome не запустився за {timeout} секунд")
            # Примусово завершуємо процес, якщо він завис
            if process.poll() is None:
                process.terminate()
            return False
            
        except Exception as e:
            logger.error(f"❌ Помилка запуску Chrome: {e}")
            return False

    def is_port_open(self, host, port):
        """Перевіряє, чи порт відкритий"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def connect_cdp(self):
        port = int(self.cfg.get("cdp_port", 9222))
        url = f"http://127.0.0.1:{port}"
        try:
            self.play = sync_playwright().start()
            # Підключення до вже запущеного Chrome через CDP
            self.conn = self.play.chromium.connect_over_cdp(url)
            # Отримати сторінки (цілком імовірно, що є кілька targets). Вибираємо існуючі сторінки.
            pages = []
            # контексти в connect_over_cdp мають метод pages через .pages
            try:
                pages = self.conn.pages
            except Exception:
                # Іноді потрібен інший шлях
                pages = []
            # Якщо сторінок немає, створи нову
            if not pages:
                self.page = self.conn.new_page()
            else:
                # Переконаємось, що є принаймні 3 вкладки. Якщо менше — створимо.
                while len(pages) < 3:
                    pages.append(self.conn.new_page())
                self.page = pages[2]
            
            # Виконання F9.bat для фокусування вікна після підключення
            # f9_bat_path = r'd:\Python\TEXT\translation\KOD_pereclad\F9.bat'
            # logger.info(f"⌨️ Виконання F9.bat для фокусування вікна: {f9_bat_path}")
            # try:
            #     import subprocess
            #     result = subprocess.run(f9_bat_path, shell=True, capture_output=True, text=True, timeout=10)
            #     if result.returncode == 0:
            #         logger.info("✅ F9.bat успішно виконано")
            #     else:
            #         logger.error("❌ F9.bat повернув код помилки: %s", result.returncode)
            # except Exception as e:
            #     logger.error("❌ Помилка виконання F9.bat: %s", e)
            
            logger.info("Підключено до Chrome через CDP на %s", url)
            return True
        except Exception as e:
            logger.warning("Не вдалося підключитися до CDP %s: %s", url, e)
            # Автоматичний запуск Chrome, якщо налаштовано
            if self.cfg.get("auto_launch_chrome", True):
                logger.info("🔄 Спроба автоматичного запуску Chrome...")
                if self.launch_chrome_with_debug():
                    # Повторна спроба підключення після запуску Chrome
                    try:
                        if self.play is None:
                            self.play = sync_playwright().start()
                        self.conn = self.play.chromium.connect_over_cdp(url)
                        logger.info("✅ Підключено до Chrome після авто-запуску")
                        
                        # Отримуємо сторінки після підключення
                        pages = self.conn.pages
                        if not pages:
                            self.page = self.conn.new_page()
                        else:
                            while len(pages) < 3:
                                pages.append(self.conn.new_page())
                            self.page = pages[2]
                        
                        return True
                    except Exception as e2:
                        logger.error("❌ Повторне підключення не вдалося: %s", e2)
                else:
                    logger.error("❌ Не вдалося запустити Chrome автоматично")
            else:
                logger.warning("⚠️ Автоматичний запуск Chrome вимкнено в налаштуваннях")
                
            self.close()
            return False

    def ensure_third_tab_and_open_gemini(self):
        # Надійна логіка: знайти існуючу вкладку з Gemini або Google, інакше використати першу наявну вкладку, або створити нову.
        pages = []
        try:
            pages = getattr(self.conn, 'pages', None) or []
        except Exception:
            pages = []

        # Додатково спробуємо отримати сторінки з контекстів (залежно від версії playwright)
        try:
            contexts = getattr(self.conn, 'contexts', None) or []
            for ctx in contexts:
                try:
                    ctx_pages = getattr(ctx, 'pages', None) or []
                    for pg in ctx_pages:
                        if pg not in pages:
                            pages.append(pg)
                except Exception:
                    continue
        except Exception:
            pass

        # Шукаймо вкладку, яка вже відкрита на Gemini/Google
        chosen = None
        for pg in pages:
            try:
                u = ''
                t = ''
                try:
                    u = pg.url or ''
                except Exception:
                    u = ''
                try:
                    t = pg.title() or ''
                except Exception:
                    t = ''
                if 'gemini' in u.lower() or 'gemini' in t.lower() or 'google' in t.lower():
                    # Перевірити, чи сторінка доступна
                    if hasattr(pg, 'bring_to_front'):
                        chosen = pg
                    break
            except Exception:
                continue

        # Якщо не знайшли, використовуємо логіку запасного вибору
        try:
            if chosen is None:
                if len(pages) >= 3:
                    chosen = pages[2]
                elif pages:
                    # Шукаємо першу доступну сторінку
                    for pg in pages:
                        if hasattr(pg, 'bring_to_front'):
                            chosen = pg
                            break
                if chosen is None:
                    chosen = pages[0]
                else:
                    chosen = self.conn.new_page()
        except Exception:
            try:
                chosen = self.conn.new_page()
            except Exception:
                chosen = None

        self.page = chosen

        # Відкрити або перенаправити сторінку на Gemini
        try:
            if self.page:
                try:
                    self.page.bring_to_front()
                except Exception:
                    logger.warning("Не вдалося вивести сторінку на передній план")
                # Перевірити, чи ми вже на потрібній сторінці
                if 'gemini.google.com' in self.page.url:
                    return
                self.page.goto(self.cfg.get('gemini_url'), timeout=int(self.cfg.get('page_load_timeout',30))*1000)
                logger.info('Gemini відкрито/наведено у вкладці через CDP')
        except PlaywrightTimeoutError:
            logger.warning('Час очікування завантаження Gemini сплинув')

    def create_new_chat(self, method="ctrl_shift_o"):
        try:
            if method == "ctrl_shift_o":
                self.page.keyboard.press("Control+Shift+O")
            elif method == "search_and_ctrl_enter":
                self.page.keyboard.press("Control+F")
                self.page.keyboard.press("Control+Enter")
            else:
                logger.warning("Невідомий метод створення чату: %s", method)
        except Exception as e:
            logger.warning("Не вдалося виконати створення нового чату: %s", e)

    # Методи читання відповіді
    def read_response_dom_selector(self):
        selectors = [
            'div[class*="assistant"]',
            'div[class*="message"]',
            'div[class*="chat"]',
            'article',
            'div[role="article"]',
        ]
        # This method expects self._sent_text to be set (the text we sent).
        sent = getattr(self, "_sent_text", "") or ""
        for sel in selectors:
            try:
                elems = self.page.query_selector_all(sel)
                if elems:
                    # Iterate from the end to find the first element that is not our sent text
                    for el in reversed(elems):
                        try:
                            text = el.inner_text() or ""
                        except Exception:
                            text = ""
                        if not text or not text.strip():
                            continue
                        # Skip elements that exactly match what we sent (or contain large part of it)
                        if sent and (sent.strip() == text.strip() or sent.strip() in text.strip()):
                            continue
                        # Likely assistant response
                        return text.strip()
            except Exception:
                continue
        return None

    def read_response_clipboard_via_js(self):
        js = r"""
        (() => {
            const nodes = Array.from(document.querySelectorAll('div, p, span, article'));
            if(nodes.length === 0) return '';
            const last = nodes[nodes.length-1];
            return last.innerText || last.textContent || '';
        })();
        """
        try:
            res = self.page.evaluate(js)
            if res and isinstance(res, str) and res.strip():
                return res.strip()
        except Exception as e:
            logger.debug("clipboard_via_js failed: %s", e)
        return None

    def read_response_keyboard_copy(self):
        # disabled by #GPT per request — не використовувати keyboard-copy у цьому релізі
        return None

    # ===== Метод для знаходження та натискання кнопки копіювання =====
    def click_copy_button(self):
        """Спробувати знайти та натиснути кнопку копіювання відповіді асистента"""
        logger.info("🔍 Пошук кнопки копіювання...")
        copy_selectors = [
            'copy-button button.icon-button',  # Основний селектор для кнопки копіювання відповіді
            'button[aria-label*="Copy"]',
            'button[title*="Copy"]',
            'button[class*="copy"]',
            'button svg',  # Кнопки з іконкою копіювання
            'div[class*="copy"] button',
            'button[data-tooltip*="Copy"]',
            'button[data-testid*="copy"]',
            'button .icon-copy',  # Для іконок копіювання
            'div.model-response-actions button',  # Кнопки дій для відповіді моделі
        ]
        
        for selector in copy_selectors:
            try:
                buttons = self.page.query_selector_all(selector)
                if buttons:
                    # Беремо останню кнопку (найімовірніше для останньої відповіді)
                    last_button = buttons[-1]
                    last_button.click()
                    time.sleep(0.3)  # Затримка для копіювання в буфер
                    return True
            except Exception as e:
                logger.debug("Не вдалося знайти/натиснути кнопку копіювання за селектором '%s': %s", selector, e)
                continue
        
        # Додаткова спроба: шукаємо кнопку в контейнері відповіді асистента
        logger.info("🔍 Спроба знайти кнопку в контейнері відповіді асистента...")
        assistant_selectors = [
            'div[class*="assistant"]',
            'div[class*="model-response"]',
            'div[data-author="assistant"]',
            'div[role="article"]',
        ]
        
        for container_sel in assistant_selectors:
            try:
                containers = self.page.query_selector_all(container_sel)
                if containers:
                    last_container = containers[-1]  # Остання відповідь асистента
                    copy_btn = last_container.query_selector('button')
                    if copy_btn:
                        copy_btn.click()
                        time.sleep(0.3)
                        logger.info("✅ Кнопку копіювання знайдено в контейнері відповіді")
                        return True
            except Exception as e:
                logger.debug("Помилка пошуку в контейнері '%s': %s", container_sel, e)
                continue
        
        logger.warning("❌ Кнопку копіювання не знайдено за жодним селектором")
        return False

    def wait_for_response_ready(self, timeout=30, poll_interval=2):
        """
        Очікує готовність відповіді з періодичною перевіркою статусу
        Повертає True якщо відповідь готова, False якщо таймаут
        """
        logger.info(f"⏳ Очікування відповіді (максимум {timeout} секунд)")
        start_time = time.time()
        last_log_time = start_time
        poll_count = 0
        
        while (time.time() - start_time) < timeout:
            poll_count += 1
            current_time = time.time()
            elapsed = current_time - start_time
            remaining = timeout - elapsed
            
            # Інформативне логування кожні 10 секунд
            if current_time - last_log_time >= 10:
                logger.info(f"🔄 Статус генерації: {int(elapsed)}с пройшло, {int(remaining)}с залишилось")
                last_log_time = current_time
            
            # Спроба знайти кнопку копіювання як ознаку готовності
            copy_selectors = [
                'copy-button button.icon-button',
                'button[aria-label*="Copy"]',
                'button[title*="Copy"]',
                'button[class*="copy"]',
            ]
            
            for selector in copy_selectors:
                try:
                    button = self.page.query_selector(selector)
                    if button and button.is_visible():
                        logger.info(f"✅ Відповідь готова! Знайдено кнопку копіювання через {int(elapsed)} секунд")
                        self.last_response_status = f"ready_after_{int(elapsed)}s"
                        return True
                except Exception:
                    continue
            
            # Затримка між перевірками
            time.sleep(poll_interval)
        
        logger.warning(f"❌ Таймаут очікування відповіді ({timeout} секунд)")
        self.last_response_status = f"timeout_after_{timeout}s"
        return False

    def read_response(self):
        # Спочатку намагаємося скопіювати через кнопку Copy з кількома спробами
        max_retries = self.cfg.get("max_retries", 2)
        response_timeout = int(self.cfg.get("response_timeout", 18))
        
        for attempt in range(max_retries):
            logger.info(f"📋 Спроба копіювання через кнопку 'Copy' ({attempt + 1}/{max_retries})...")
            if self.click_copy_button():
                try:
                    clipboard_content = pyperclip.paste().strip()
                    if clipboard_content:
                        logger.info("✅ Відповідь успішно скопійована через кнопку 'Copy'")
                        return clipboard_content
                    else:
                        logger.warning("⚠️ Буфер обміну порожній після натискання кнопки копіювання")
                except Exception as e:
                    logger.error("❌ Не вдалося прочитати буфер після натискання кнопки копіювання: %s", e)
            
            # Затримка між спробами (використовуємо response_timeout як інтервал)
            if attempt < max_retries - 1:
                logger.info(f"⏳ Очікування {response_timeout} секунд перед наступною спробою...")
                time.sleep(response_timeout)

        # Якщо кнопка не спрацювала, намагаємося через DOM-селектори
        logger.info("📖 Спроба читання відповіді через DOM-селектори...")
        try:
            t = self.read_response_dom_selector()
            if t:
                logger.info("✅ Відповідь успішно отримана через DOM-селектори")
                return t
        except Exception as e:
            logger.debug("Помилка при читанні DOM-селекторами: %s", e)
        
        # Виконання F9.bat як останній спосіб
        f9_bat_path = r'd:\Python\TEXT\translation\KOD_pereclad\F9.bat'
        logger.info(f"⌨️ Виконання зовнішньої команди: {f9_bat_path}")
        try:
            import subprocess
            result = subprocess.run(f9_bat_path, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                time.sleep(0.5)
                clip = pyperclip.paste()
                if clip and clip.strip():
                    logger.info("✅ Відповідь отримана через зовнішню команду F9")
                    return clip.strip()
            else:
                logger.error("❌ F9.bat повернув код помилки: %s", result.returncode)
        except Exception as e:
            logger.error("❌ Помилка виконання F9.bat: %s", e)
        
        logger.warning("❌ Не вдалося отримати відповідь жодним методом")
        return None

    def close(self):
        try:
            if self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass
            if self.play:
                try:
                    self.play.stop()
                except Exception:
                    pass
        except Exception:
            pass

# ===== Config validation =====
#GPT
def validate_config(cfg: dict) -> bool:
    """Валідація конфігурації"""
    required_fields = ['gemini_url', 'cdp_port', 'output_folder']
    for field in required_fields:
        if field not in cfg or not cfg[field]:
            logger.error("Відсутнє обов'язкове поле конфігурації: %s", field)
            return False
    
    if not isinstance(cfg.get('cdp_port'), int) or cfg['cdp_port'] <= 0:
        logger.error("cdp_port повинен бути додатним цілим числом")
        return False
    
    return True

# ===== Response validation =====
#GPT
BAD_PHRASES = [
    "ось переклад", "ось перекладаю", "вам потрібно", "чи", "побажань", "потрібно уточнити",
    "i'm sorry", "as an ai", "i cannot", "i'm unable"
]
def validate_response_text(text: str) -> bool:
    #GPT: валідація тимчасово відключена
    return True

# ===== Manual intervention prompt =====
#GPT
def manual_intervention_prompt(filename):
    print(f"\nПів-автоматичний режим: проблема з файлом: {filename}")
    print("Варіанти: [c]ontinue - продовжити (повторити), [r]etry - повторити, [s]kip - пропустити, [q]uit - зупинити")
    while True:
        ch = input("Ваш вибір (c/r/s/q): ").strip().lower()
        if ch == "c":
            return "continue"
        if ch == "r":
            return "retry"
        if ch == "s":
            return "skip"
        if ch == "q":
            return "quit"

# ===== Main process =====
#GPT
def process_all(cfg: dict):
    # Treat empty string explicitly as 'not set' so GUI always opens when input_folder is empty
    raw_input = cfg.get("input_folder")
    if raw_input is None or (isinstance(raw_input, str) and raw_input.strip() == ""):
        chosen = choose_input_folder_via_gui()
        if not chosen:
            logger.error("Вхідну папку не обрано. Завершую.")
            return
        input_folder = Path(chosen).expanduser()
    else:
        input_folder = Path(raw_input).expanduser()
    output_folder = input_folder / cfg.get("output_folder", "output")
    output_folder.mkdir(parents=True, exist_ok=True)

    proc_logger = ProcessLogger(output_folder, formats=cfg.get("log_formats", ["txt","json"]))

    # Scan files
    files = scan_text_files(input_folder, cfg.get("numeric_prefix_regex", r"^\d+"))
    if not files:
        logger.info("Файлів для обробки не знайдено.")
        return
    
    if not validate_config(cfg):
        logger.error("Невірна конфігурація. Завершення.")
        return

    # Gemini controller via CDP
    if not cfg.get("connect_via_cdp", True):
        #GPT
        logger.error("Цей скрипт вимагає connect_via_cdp = true у config.yaml для варіанту 1.")
        return

    g = GeminiController(cfg)
    if not g.is_connected():
        logger.info("З'єднання не активне, підключаємось...")
    else:
        logger.info("Використовуємо існуюче з'єднання")
    if not g.connect_cdp():
        logger.error("Не вдалося підключитись до Chrome CDP. Переконайтесь, що Chrome запущений з --remote-debugging-port=%s", cfg.get("cdp_port"))
        return

    try:
        g.ensure_third_tab_and_open_gemini()
    except Exception as e:
        logger.error("Не вдалося підготувати вкладку Gemini: %s", e)
        g.close()
        return

    start_all = datetime.now()
    total_files = len(files)
    processed = 0

    for idx, fpath in enumerate(files, start=1):
        logger.info(f"Обробка {idx}/{total_files}: {fpath.name}")
        t0 = datetime.now()
        status = "ok"
        retries = 0
        action_taken = None
        output_name = fpath.stem + "_UKR" + fpath.suffix

        text = fpath.read_text(encoding="utf-8", errors="ignore")

        while True:
            try:
                # Формуємо повне повідомлення (шаблон + текст) і поміщаємо його у буфер.
                full_msg = cfg.get("template_message", DEFAULT_CONFIG["template_message"]) + "\n\n" + text
                
                # Надійне копіювання в буфер обміну з перевіркою
                clipboard_success = False
                for attempt in range(2):
                    try:
                        pyperclip.copy(full_msg)
                        if pyperclip.paste() == full_msg:
                            clipboard_success = True
                            break
                    except Exception as e:
                        logger.warning("Спроба %d копіювання в буфер не вдала: %s", attempt + 1, e)

                # Повернути фокус на 3-ю вкладку (якщо g.page у відповідній вкладці, легко - просто bring to front)
                try:
                    g.page.bring_to_front()
                    # Додаткові заходи для фокусування вікна
                    time.sleep(0.5)
                    
                    # Спроба активізації вікна через JavaScript
                    g.page.evaluate("() => { window.focus(); }")
                    time.sleep(0.3)
                    
                    # Спроба кліку на основну область сторінки для фокусу
                    g.page.mouse.click(100, 100)
                    time.sleep(0.3)
                    
                    # Додаткова перевірка, чи сторінка активна
                    if g.page.evaluate("() => document.hasFocus()"):
                        logger.info("✅ Вікно браузера у фокусі")
                    else:
                        logger.warning("⚠️ Увага: вікно браузера не у фокусі")
                except Exception:
                    logger.warning("⚠️ Не вдалося встановити фокус на вікно")

                # Затримка для стабілізації чату
                time.sleep(0.5)

                # Вставити шаблон + текст (вже у буфері), використати клавіші вставки
                if clipboard_success:
                    g.page.keyboard.press("Control+V")
                    time.sleep(0.5)  # Затримка для вставки
                    g.page.keyboard.press("Enter")
                else:
                    # Резервний метод: введення тексту напряму
                    logger.warning("Використання резервного методу введення тексту")
                    g.page.keyboard.type(full_msg)
                    time.sleep(0.8)  # Затримка для введення тексту
                    g.page.keyboard.press("Enter")

                # Затримка після відправки повідомлення
                time.sleep(2.0)

                #GPT
                # Визначення динамічного часу очікування відповіді на основі довжини тексту
                base_timeout = int(cfg.get("response_timeout") or 18)
                text_length = len(text)
                additional_time = 0
                
                if text_length >= 9500:
                    additional_time = base_timeout * 1.0  # +100% до часу очікування
                    logger.info(f"📏 Довгий текст ({text_length} символів): додаємо {additional_time} секунд до часу очікування")
                elif text_length >= 8000:
                    additional_time = base_timeout * 0.5  # +50% до часу очікування
                    logger.info(f"📏 Середній текст ({text_length} символів): додаємо {additional_time} секунд до часу очікування")
                elif text_length >= 5000:
                    additional_time = base_timeout * 0.35  # +35% до часу очікування
                    logger.info(f"📏 Помірний текст ({text_length} символів): додаємо {additional_time} секунд до часу очікування")
                
                dynamic_timeout = base_timeout + additional_time

                # Виконання F9.bat для фокусування вікна
                f9_bat_path = r'd:\Python\TEXT\translation\KOD_pereclad\F9.bat'
                logger.info(f"⌨️ Виконання F9.bat для фокусування вікна: {f9_bat_path}")
                try:
                    import subprocess
                    result = subprocess.run(f9_bat_path, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        logger.info("✅ F9.bat успішно виконано")
                    else:
                        logger.error("❌ F9.bat повернув код помилки: %s", result.returncode)
                except Exception as e:
                    logger.error("❌ Помилка виконання F9.bat: %s", e)

                # GPT: Покращене очікування відповіді з періодичною перевіркою
                logger.info(f"⏳ Очікування відповіді {dynamic_timeout} секунд...")
                response = None
                
                # Перевірити з'єднання перед читанням відповіді
                if not g.is_connected():
                    raise RuntimeError("Втрачено з'єднання з браузером")
                
                g._sent_text = full_msg  # Записуємо наше повідомлення для ігнорування echo
                
                # Використання покращеного очікування з перевіркою статусу
                poll_interval = 2  # Перевірка кожні 2 секунди
                if g.wait_for_response_ready(timeout=dynamic_timeout, poll_interval=poll_interval):
                    # Відповідь готова - негайно копіюємо
                    logger.info("🚀 Відповідь готова, починаємо копіювання...")
                    response = g.read_response()
                else:
                    # Таймаут, але все одно пробуємо прочитати (можливо відповідь частково готова)
                    logger.warning("⚠️ Таймаут очікування, але пробуємо прочитати відповідь...")
                    response = g.read_response()
                    
                    if not response:
                        # Якщо все ще немає відповіді, пропонуємо користувачу вибір
                        logger.error("❌ Генерація не завершена після таймауту")
                        choice = manual_intervention_prompt(fpath.name)
                        if choice == "continue":
                            # Продовжуємо спробу зі збільшеним таймаутом
                            logger.info("🔄 Продовження очікування...")
                            if g.wait_for_response_ready(timeout=dynamic_timeout + 10, poll_interval=1):
                                response = g.read_response()

                if not response:
                    logger.warning("Відповідь не отримано за timeout")
                    raise RuntimeError("no_response")

                # Валідація
                if response and validate_response_text(response):
                    outpath = output_folder / output_name
                    outpath.write_text(response, encoding="utf-8")
                    action_taken = "saved"
                    break
                else:
                    logger.warning("Відповідь не пройшла валідацію")
                    retries += 1
                    if cfg.get("on_bad_response") == "retry" and retries <= cfg.get("max_retries", 2):
                        backoff = random.randint(10, 20) * retries
                        logger.info(f"Ретрай #{retries} через backoff {backoff}s")
                        time.sleep(backoff)
                        continue
                    else:
                        if cfg.get("on_bad_response") in ("mark_for_manual", "mark_for_manual_if_failed", "mark"):
                            output_name = fpath.stem + "_UKR" + cfg.get("manual_tag", "_check") + fpath.suffix
                            outpath = output_folder / output_name
                            outpath.write_text(response or "", encoding="utf-8")
                            action_taken = "marked_manual"
                            break
                        elif cfg.get("on_bad_response") == "skip":
                            action_taken = "skipped"
                            break
                        else:
                            action_taken = "unknown_action"
                            break

            except Exception as e:
                logger.exception("Помилка під час обробки: %s", e)
                retries += 1
                if retries <= cfg.get("max_retries", 2):
                    # Backoff експоненційний
                    backoff = int(10 * (2 ** (retries - 1)))
                    logger.info(f"Затримка перед повтором: {backoff}s")
                    time.sleep(backoff)
                    continue
                else:
                    logger.error("Вичерпано всі ретраї. Переходимо в пів-автоматичний режим.")
                    choice = manual_intervention_prompt(fpath.name)
                    if choice == "continue":
                        retries = 0
                        continue
                    elif choice == "retry":
                        retries = 0
                        continue
                    elif choice == "skip":
                        action_taken = "skipped"
                        break
                    elif choice == "quit":
                        action_taken = "stopped_by_user"
                        break

        t1 = datetime.now()
        duration = (t1 - t0).total_seconds()
        proc_logger.add({
            "file": fpath.name,
            "output": output_name,
            "status": action_taken,
            "start": t0.isoformat(),
            "end": t1.isoformat(),
            "duration_s": duration,
            "retries": retries
        })

        processed += 1
    end_all = datetime.now()
    total_duration = (end_all - start_all).total_seconds()
    proc_logger.add({"summary": {"total_files": total_files, "processed": processed, "total_time_s": total_duration}})
    proc_logger.finalize()

    # Об'єднання файлів без маркування
    merged_path = output_folder / cfg.get("merged_filename", "merged_UKR.txt")
    with merged_path.open("w", encoding="utf-8") as out:
        # сортування за іменем щоб зберегти порядок
        for p in sorted(output_folder.iterdir()):
            if p.is_file() and p.suffix == ".txt" and p.name != merged_path.name and not p.name.startswith("process_log"):
                out.write(p.read_text(encoding="utf-8"))
                out.write("\n")

        logger.info(f"Готово. Оброблено {processed}/{total_files}. Загальний час: {total_duration:.1f}s")
        g.close()


# ===== Entry point =====
#GPT
def main() -> None:
    cfg = load_config(CONFIG_PATH)
    logger.info(f"response_timeout = {cfg.get('response_timeout')}")  #GPT
    # Якщо input_folder відсутній - GUI запросить
    if not cfg.get("input_folder"):
        logger.info("Вхідна папка не вказана у config.yaml. Буде відкрито вибір GUI.")
    process_all(cfg)

if __name__ == "__main__":
    main()