import os
import time
import yaml
import re
import pyperclip
import logging
import subprocess
from pathlib import Path

# Налаштування логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("send_to_temp_chat")

# Імпорт з оригінального коду
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception as e:
    print("Відсутні залежності. Виконайте:\n  pip install playwright\n  playwright install")
    raise

CONFIG_PATH = "config.yaml"
OPEN_CHAT_SCRIPT = "3_open_temp_chat.py"

class GeminiController:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.play = None
        self.conn = None
        self.context = None
        self.page = None
        self.last_response_status = None
    
    def connect_cdp(self):
        port = int(self.cfg.get("cdp_port", 9222))
        url = f"http://127.0.0.1:{port}"
        try:
            self.play = sync_playwright().start()
            self.conn = self.play.chromium.connect_over_cdp(url)
            
            # Отримати сторінки
            pages = []
            try:
                pages = self.conn.pages
            except Exception:
                pages = []
                
            if not pages:
                self.page = self.conn.new_page()
            else:
                while len(pages) < 3:
                    pages.append(self.conn.new_page())
                self.page = pages[2]
            
            logger.info("Підключено до Chrome через CDP на %s", url)
            return True
        except Exception as e:
            logger.error("Не вдалося підключитися до CDP %s: %s", url, e)
            return False

    def ensure_third_tab_and_open_gemini(self):
        """Відкрити або активувати вкладку Gemini"""
        pages = []
        try:
            pages = getattr(self.conn, 'pages', None) or []
        except Exception:
            pages = []

        chosen = None
        for pg in pages:
            try:
                u = pg.url or ''
                if 'gemini' in u.lower() or 'google' in u.lower():
                    chosen = pg
                    break
            except Exception:
                continue

        try:
            if chosen is None:
                if len(pages) >= 3:
                    chosen = pages[2]
                elif pages:
                    chosen = pages[0]
                else:
                    chosen = self.conn.new_page()
        except Exception:
            try:
                chosen = self.conn.new_page()
            except Exception:
                chosen = None

        self.page = chosen

        try:
            if not self.page:
                logger.error("Сторінка відсутня")
                return

            try:
                self.page.bring_to_front()
            except Exception:
                pass

            # Оновити сторінку
            try:
                logger.info("Оновлюю сторінку Gemini")
                self.page.reload(timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning("Час очікування при оновленні сторінки сплинув")
            except Exception as e:
                logger.debug("Помилка при перезавантаженні сторінки: %s", e)

            time.sleep(2.0)
            logger.info("Gemini готовий до роботи")
            return
        except Exception as e:
            logger.warning("Не вдалося підготувати вкладку Gemini: %s", e)
            return

    def wait_for_chat_input(self, timeout=10000):
        """Очікувати появу поля вводу чату"""
        logger.info("Очікування появи поля вводу чату...")
        
        input_selectors = [
            'textarea[aria-label*="Enter a prompt"]',
            'textarea[aria-label*="Введіть запит"]',
            'textarea[class*="input"]',
            'textarea',
            'div[contenteditable="true"]',
            'div[role="textbox"][contenteditable="true"]',
        ]

        for selector in input_selectors:
            try:
                logger.info(f"Перевірка селектора: {selector}")
                self.page.wait_for_selector(selector, timeout=timeout)
                logger.info(f"Знайдено поле вводу за селектором: {selector}")
                return True
            except Exception as e:
                logger.debug(f"Не вдалося знайти поле вводу за селектором {selector}: {e}")
                continue
                
        logger.error("Поле вводу не знайдено за жодним селектором")
        return False

    def send_text_to_chat(self, text: str) -> bool:
        """Надійно вставити текст у поле чату"""
        logger.info("Спроба вставки тексту в чат...")
        
        # Спочатку чекаємо на поле вводу
        if not self.wait_for_chat_input():
            logger.error("Не вдалося знайти поле вводу")
            return False

        input_selectors = [
            'textarea[aria-label*="Enter a prompt"]',
            'textarea[aria-label*="Введіть запит"]',
            'textarea[class*="input"]',
            'textarea',
            'div[contenteditable="true"]',
            'div[role="textbox"][contenteditable="true"]',
        ]

        for sel in input_selectors:
            try:
                el = self.page.query_selector(sel)
                if not el:
                    continue
                    
                # Перевірити, чи елемент видимий і доступний
                if not el.is_visible():
                    logger.debug(f"Елемент {sel} не видимий")
                    continue
                    
                tag = self.page.evaluate(f"() => document.querySelector('{sel}')?.tagName?.toLowerCase() || ''")
                logger.info(f"Знайдено елемент: {tag} за селектором {sel}")
                
                if tag in ('textarea', 'input'):
                    try:
                        # Очистити поле та вставити текст
                        el.click()
                        el.fill('')
                        el.fill(text)
                        time.sleep(0.5)
                        logger.info("Текст успішно вставлено в textarea/input")
                        return True
                    except Exception as e:
                        logger.debug(f"Помилка заповнення {sel}: {e}")
                        # Спроба через клавіатуру
                        try:
                            el.click()
                            self.page.keyboard.press("Control+A")
                            time.sleep(0.1)
                            self.page.keyboard.type(text)
                            time.sleep(0.5)
                            logger.info("Текст успішно вставлено через клавіатуру")
                            return True
                        except Exception as e2:
                            logger.debug(f"Помилка вставки через клавіатуру: {e2}")
                else:
                    # Contenteditable div
                    try:
                        el.click()
                        # Очистити вміст
                        self.page.evaluate(f"() => document.querySelector('{sel}').innerText = ''")
                        time.sleep(0.1)
                        # Вставити текст
                        self.page.keyboard.type(text)
                        time.sleep(0.5)
                        logger.info("Текст успішно вставлено в contenteditable")
                        return True
                    except Exception as e:
                        logger.debug(f"Помилка вставки в contenteditable {sel}: {e}")
            except Exception as e:
                logger.debug(f"Помилка обробки селектора {sel}: {e}")
                continue
                
        # Фолбек: спроба через буфер обміну
        logger.info("Спроба вставки через буфер обміну...")
        try:
            pyperclip.copy(text)
            time.sleep(0.5)
            
            # Знайти будь-яке поле вводу та сфокусуватися
            for sel in input_selectors:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    break
            
            self.page.keyboard.press("Control+V")
            time.sleep(0.5)
            logger.info("Текст успішно вставлено через буфер обміну")
            return True
        except Exception as e:
            logger.error(f"Помилка вставки через буфер обміну: {e}")
            return False

    def press_enter(self):
        """Натиснути Enter для відправки повідомлення"""
        try:
            self.page.keyboard.press("Enter")
            logger.info("Повідомлення відправлено (Enter)")
            return True
        except Exception as e:
            logger.error(f"Помилка при натисканні Enter: {e}")
            return False

    def click_copy_button(self):
        """Знайти та натиснути кнопку копіювання"""
        logger.info("Пошук кнопки копіювання...")
        copy_selectors = [
            'button[aria-label*="Copy"]',
            'button[title*="Copy"]',
            'button[class*="copy"]',
            'button svg',
            'div[class*="copy"] button',
            'button[data-test-id*="copy"]',
            'copy-button button',
        ]
        
        for selector in copy_selectors:
            try:
                buttons = self.page.query_selector_all(selector)
                if buttons:
                    # Шукаємо останню видиму кнопку
                    for button in reversed(buttons):
                        if button.is_visible():
                            button.click()
                            time.sleep(0.5)
                            logger.info(f"Кнопка копіювання знайдена та натиснута: {selector}")
                            return True
            except Exception as e:
                logger.debug("Не вдалося знайти кнопку за селектором '%s': %s", selector, e)
                continue
        
        logger.warning("Кнопку копіювання не знайдено")
        return False

    def wait_for_response_ready(self, timeout=60):
        """Очікувати готовність відповіді"""
        logger.info(f"Очікування відповіді ({timeout} секунд)")
        start_time = time.time()
        last_status = start_time
        
        while (time.time() - start_time) < timeout:
            current_time = time.time()
            
            # Логування кожні 10 секунд
            if current_time - last_status >= 10:
                elapsed = int(current_time - start_time)
                remaining = timeout - elapsed
                logger.info(f"Статус: {elapsed}с пройшло, {remaining}с залишилось")
                last_status = current_time
            
            # Спроба знайти кнопку копіювання
            copy_selectors = [
                'button[aria-label*="Copy"]',
                'button[title*="Copy"]',
                'button[class*="copy"]',
            ]
            
            for selector in copy_selectors:
                try:
                    button = self.page.query_selector(selector)
                    if button and button.is_visible():
                        logger.info("Відповідь готова! Знайдено кнопку копіювання")
                        return True
                except Exception:
                    continue
            
            # Також перевіряємо наявність тексту відповіді
            try:
                response_selectors = [
                    'div[class*="assistant"]',
                    'div[class*="message"]',
                    'div[class*="model-response"]',
                    'article',
                    'div[role="article"]',
                ]
                
                for selector in response_selectors:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        if element.is_visible():
                            text = element.inner_text()
                            if text and len(text.strip()) > 50:  # Припускаємо, що відповідь має бути довшою за 50 символів
                                logger.info("Знайдено потенційну відповідь")
                                return True
            except Exception:
                pass
            
            time.sleep(2)
        
        logger.warning(f"Таймаут очікування відповіді ({timeout} секунд)")
        return False

    def get_response(self, timeout=60):
        """Отримати відповідь від Gemini"""
        # Чекаємо, доки відповідь буде готова
        if not self.wait_for_response_ready(timeout):
            logger.warning("Відповідь не готова за вказаний час")
            return None

        # Натискаємо кнопку копіювання
        if self.click_copy_button():
            try:
                time.sleep(1)
                clip = pyperclip.paste()
                if clip and clip.strip():
                    logger.info("Відповідь успішно скопійована")
                    return clip.strip()
                else:
                    logger.warning("Буфер обміну порожній після копіювання")
            except Exception as e:
                logger.error("Помилка читання буфера: %s", e)

        # Якщо копіювання не вдалося, пробуємо прочитати напряму з DOM
        logger.info("Спроба читання відповіді з DOM...")
        try:
            response_selectors = [
                'div[class*="assistant"]',
                'div[class*="message"]',
                'div[class*="model-response"]',
                'article',
                'div[role="article"]',
            ]
            
            for selector in response_selectors:
                elements = self.page.query_selector_all(selector)
                for element in reversed(elements):
                    if element.is_visible():
                        text = element.inner_text()
                        if text and len(text.strip()) > 50:
                            logger.info("Відповідь успішно прочитано з DOM")
                            return text.strip()
        except Exception as e:
            logger.error("Помилка читання з DOM: %s", e)

        logger.warning("Не вдалося отримати відповідь")
        return None

    def refresh_page_connection(self):
        """Оновити підключення до сторінки після змін"""
        try:
            pages = self.conn.pages
            if pages:
                # Використовуємо останню вкладку (найімовірніше активну)
                self.page = pages[-1]
                logger.info("Підключення до сторінки оновлено")
                return True
        except Exception as e:
            logger.error("Помилка оновлення підключення до сторінки: %s", e)
        return False

    def close(self):
        """Закрити з'єднання"""
        try:
            if self.conn:
                self.conn.close()
            if self.play:
                self.play.stop()
        except Exception:
            pass

def load_config():
    """Завантажити конфігурацію"""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Не знайдено файл {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg_all = yaml.safe_load(f) or {}

    # Використовуємо секцію pereclad або шукаємо параметри
    if isinstance(cfg_all, dict) and "pereclad" in cfg_all:
        cfg = cfg_all["pereclad"]
    else:
        cfg = cfg_all

    # Дефолтні значення
    defaults = {
        "output_folder": "output",
        "merged_filename": "merged_UKR.txt",
        "numeric_prefix_regex": r"^\d+",
        "cdp_port": 9222,
        "response_timeout": 60
    }
    
    for k, v in defaults.items():
        cfg.setdefault(k, v)

    return cfg

def scan_files(folder, regex):
    """Сканувати файли за числовим префіксом"""
    files = [p for p in Path(folder).iterdir() if p.suffix.lower() == ".txt"]
    rx = re.compile(regex)
    ordered = []
    for f in files:
        m = rx.match(f.name)
        num = int(m.group()) if m else 999999
        ordered.append((num, f.name, f))
    ordered.sort()
    return [f[2] for f in ordered]

def save_output(text, out_folder, filename):
    """Зберегти результат"""
    Path(out_folder).mkdir(exist_ok=True, parents=True)
    out_file = Path(out_folder) / filename
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(text)

def call_open_temp_chat():
    """Викликати скрипт відкриття тимчасового чату"""
    logger.info("Виклик скрипта відкриття тимчасового чату...")
    try:
        result = subprocess.run(["python", OPEN_CHAT_SCRIPT], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("Скрипт відкриття чату успішно виконано")
        else:
            logger.warning(f"Скрипт повернув код {result.returncode}: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("Скрипт відкриття чату перевищив таймаут")
    except Exception as e:
        logger.error(f"Помилка виконання скрипта: {e}")

def main():
    """Головна функція"""
    try:
        cfg = load_config()
        
        input_folder = cfg["input_folder"]
        template = cfg["template_message"].strip()
        output_folder = cfg["output_folder"]
        numeric_rx = cfg["numeric_prefix_regex"]
        response_timeout = int(cfg.get("response_timeout", 60))

        files = scan_files(input_folder, numeric_rx)

        # Створюємо контролер Gemini
        g = GeminiController(cfg)
        
        # Підключаємося до браузера
        if not g.connect_cdp():
            logger.error("Не вдалося підключитися до браузера")
            return

        # Відкриваємо Gemini
        g.ensure_third_tab_and_open_gemini()

        for f in files:
            logger.info(f"Обробка: {f.name}")

            # 0. Викликаємо скрипт відкриття тимчасового чату
            call_open_temp_chat()
            time.sleep(3)

            # 1. Оновлюємо підключення до сторінки після відкриття нового чату
            if not g.refresh_page_connection():
                logger.warning("Не вдалося оновити підключення до сторінки")

            # 2. Зчитуємо текст файлу
            text = f.read_text(encoding="utf-8", errors="ignore")
            msg = template + "\n\n" + text

            # 3. Відправляємо повідомлення
            if not g.send_text_to_chat(msg):
                logger.error("Не вдалося відправити повідомлення. Пропускаємо файл.")
                continue

            # 4. Натискаємо Enter для відправки
            if not g.press_enter():
                logger.error("Не вдалося відправити повідомлення (Enter). Пропускаємо файл.")
                continue

            # 5. Очікуємо та отримуємо відповідь
            # Динамічний таймаут на основі довжини тексту
            text_length = len(text)
            dynamic_timeout = response_timeout
            if text_length > 5000:
                dynamic_timeout = max(response_timeout, text_length // 100)  # Додатковий час для довгих текстів
                logger.info(f"Довгий текст ({text_length} символів), збільшено таймаут до {dynamic_timeout} секунд")

            response = g.get_response(dynamic_timeout)
            if not response:
                logger.warning("Не вдалося отримати відповідь. Пропускаємо файл.")
                continue

            # 6. Зберігаємо результат
            out_name = f.stem + "_UKR.txt"
            save_output(response, output_folder, out_name)
            logger.info(f"Готово: {out_name}")

        logger.info("Всі файли оброблено")
        
    except Exception as e:
        logger.error("Критична помилка: %s", e)
    finally:
        if 'g' in locals():
            g.close()

if __name__ == "__main__":
    main()