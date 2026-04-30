import os
import time
import yaml
import logging
import pyperclip
import sys
from pathlib import Path

# Налаштування логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("get_response")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception as e:
    print("Відсутні залежності. Виконайте:\n  pip install playwright\n  playwright install")
    raise

CONFIG_PATH = "config.yaml"

class ResponseGetter:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.play = None
        self.conn = None
        self.page = None
        self.last_response_status = None
    
    def connect_cdp(self):
        """Підключитися до браузера через CDP і знайти вкладку Google Gemini"""
        port = int(self.cfg.get("cdp_port", 9222))
        url = f"http://127.0.0.1:{port}"
        try:
            self.play = sync_playwright().start()
            self.conn = self.play.chromium.connect_over_cdp(url)
            
            # Отримуємо всі вкладки
            pages = []
            try:
                pages = self.conn.contexts[0].pages if self.conn.contexts else []
                if not pages:
                    pages = self.conn.pages
            except Exception as e:
                logger.error(f"Помилка отримання вкладок: {e}")
                return False
            
            logger.info(f"Знайдено {len(pages)} вкладок")
            
            # Логуємо всі знайдені вкладки для діагностики
            for i, page in enumerate(pages):
                try:
                    page_url = page.url or "невідомий URL"
                    page_title = page.title() or "без заголовка"
                    logger.info(f"Вкладка {i}: {page_title} - {page_url}")
                except Exception as e:
                    logger.info(f"Вкладка {i}: не вдалося отримати інформацію - {e}")
            
            # Шукаємо вкладку з заголовком "Google Gemini"
            gemini_page = None
            target_title = "Google Gemini"
            
            for page in pages:
                try:
                    page_title = page.title() or ""
                    page_url = page.url or ""
                    
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
                self.page = gemini_page
                logger.info(f"Обрано вкладку: {self.page.title()}")
                return True
            else:
                logger.error(f"Не знайдено вкладку з заголовком '{target_title}'")
                return False
            
        except Exception as e:
            logger.error("Не вдалося підключитися до CDP %s: %s", url, e)
            return False

    def activate_gemini_tab(self):
        """Активувати вкладку Gemini"""
        try:
            if self.page:
                self.page.bring_to_front()
                logger.info("Вкладка Gemini активована")
                time.sleep(1)
                return True
        except Exception as e:
            logger.error(f"Помилка активації вкладки: {e}")
        return False

    def wait_for_response_ready(self, timeout=120, poll_interval=2):
        """Очікувати готовність відповіді з періодичною перевіркою статусу"""
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

    def click_copy_button(self):
        """Динамічний пошук та клік кнопки копіювання (з вашого коду)"""
        logger.info("🔍 Динамічний пошук кнопки копіювання...")
        
        # Основний список селекторів для кнопки копіювання
        copy_selectors = [
            'copy-button button.icon-button',
            'button[aria-label*="Copy"]',
            'button[title*="Copy"]',
            'button[class*="copy"]',
            'button svg',
            'div[class*="copy"] button',
            'button[data-tooltip*="Copy"]',
            'button[data-testid*="copy"]',
            'button .icon-copy',
            'div.model-response-actions button',
        ]
        
        for selector in copy_selectors:
            try:
                buttons = self.page.query_selector_all(selector)
                if buttons:
                    # Беремо останню кнопку (найімовірніше для останньої відповіді)
                    last_button = buttons[-1]
                    
                    # Детальна інформація про кнопку для діагностики
                    try:
                        button_html = last_button.inner_html()
                        button_outer_html = last_button.evaluate("element => element.outerHTML")
                        logger.info(f"🔍 HTML кнопки: {button_outer_html[:200]}...")
                    except Exception:
                        pass
                    
                    logger.info(f"✅ Знайдено кнопку копіювання за селектором: {selector}")
                    
                    # Перевіряємо, чи кнопка видима та доступна
                    is_visible = last_button.is_visible()
                    is_enabled = last_button.is_enabled()
                    logger.info(f"📊 Статус кнопки: видима={is_visible}, доступна={is_enabled}")
                    
                    # Прокручуємо до кнопки для надійності
                    if not is_visible:
                        logger.warning("⚠️ Кнопка знайдена, але не видима. Спробую прокрутити до неї...")
                        try:
                            last_button.scroll_into_view_if_needed()
                            time.sleep(0.5)
                        except Exception as e:
                            logger.warning(f"Не вдалося прокрутити до кнопки: {e}")
                    
                    # Спроба кліку різними методами
                    click_success = False
                    click_methods = [
                        ("force JS click", lambda: self.page.evaluate(f"document.querySelector('{selector}').dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}))")),
                        ("JS click", lambda: self.page.evaluate(f"document.querySelector('{selector}').click()")),
                        ("звичайний клік", lambda: last_button.click()),
                        ("click з координатами", lambda: last_button.click(force=True))
                    ]
                    
                    for method_name, click_func in click_methods:
                        try:
                            logger.info(f"🖱️ Спроба {method_name}...")
                            click_func()
                            time.sleep(0.5)
                            click_success = True
                            logger.info(f"✅ {method_name} успішний!")
                            break
                        except Exception as e:
                            logger.debug(f"❌ {method_name} невдалий: {e}")
                            continue
                    
                    if click_success:
                        time.sleep(0.3)  # Затримка для копіювання в буфер
                        return True
                    else:
                        logger.error("❌ Всі спроби кліку невдалі для селектора: {selector}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Не вдалося знайти/натиснути кнопку копіювання за селектором '{selector}': {e}")
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
                        # Спроби кліку для кнопки в контейнері
                        try:
                            copy_btn.click()
                            time.sleep(0.3)
                            logger.info("✅ Кнопку копіювання знайдено в контейнері відповіді")
                            return True
                        except Exception as e:
                            logger.debug(f"Не вдалося клікнути кнопку в контейнері: {e}")
                            try:
                                self.page.evaluate("(element) => element.click()", copy_btn)
                                time.sleep(0.3)
                                logger.info("✅ Кнопку копіювання клікнуто через evaluate")
                                return True
                            except Exception:
                                continue
            except Exception as e:
                logger.debug(f"Помилка пошуку в контейнері '{container_sel}': {e}")
                continue
        
        logger.warning("❌ Кнопку копіювання не знайдено за жодним селектором")
        self.last_response_status = "copy_not_found"
        return False

    def read_response_dom_selector(self):
        """Читання відповіді з DOM за допомогою селекторів"""
        selectors = [
            'div[class*="assistant"]',
            'div[class*="message"]',
            'div[class*="chat"]',
            'article',
            'div[role="article"]',
        ]
        
        sent = getattr(self, "_sent_text", "") or ""
        for sel in selectors:
            try:
                elems = self.page.query_selector_all(sel)
                if elems:
                    # Перебираємо з кінця, щоб знайти перший елемент, який не є нашим відправленим текстом
                    for el in reversed(elems):
                        try:
                            text = el.inner_text() or ""
                        except Exception:
                            text = ""
                        if not text or not text.strip():
                            continue
                        # Пропускаємо елементи, які точно відповідають тому, що ми відправили
                        if sent and (sent.strip() == text.strip() or sent.strip() in text.strip()):
                            continue
                        # Ймовірно відповідь асистента
                        return text.strip()
            except Exception:
                continue
        return None

    def get_response(self, timeout=60):
        """Отримати відповідь від Gemini з динамічним пошуком кнопки"""
        max_retries = int(self.cfg.get("max_retries", 2))
        response_timeout = int(self.cfg.get("response_timeout", 120))
        on_missing_copy = str(self.cfg.get("on_missing_copy_button", "retry")).lower()

        if not self.wait_for_response_ready(timeout):
            logger.warning("Відповідь не готова за вказаний час")
            return None

        for attempt in range(max_retries):
            logger.info(f"📋 Спроба копіювання через кнопку 'Copy' ({attempt + 1}/{max_retries})...")
            try:
                copy_clicked = self.click_copy_button()
            except Exception as e:
                logger.debug("click_copy_button викликав виняток: %s", e)
                copy_clicked = False

            if not copy_clicked:
                logger.warning("Кнопку 'Copy' не знайдено або не вдалося натиснути")
                if on_missing_copy == "retry" and attempt < max_retries - 1:
                    logger.info("🔁 on_missing_copy=retry — повторна спроба через response_timeout")
                    time.sleep(response_timeout)
                    continue
                elif on_missing_copy == "skip":
                    logger.warning("⚠️ on_missing_copy=skip — пропускаємо файл")
                    self.last_response_status = "copy_not_found"
                    return None
                else:
                    logger.error("❌ on_missing_copy=stop — зупинка обробки")
                    self.last_response_status = "copy_not_found"
                    return None

            # Якщо кнопка натиснута — читаємо буфер
            try:
                time.sleep(0.5)
                clip = pyperclip.paste()
                if clip and clip.strip():
                    logger.info("✅ Відповідь успішно скопійована через кнопку 'Copy'")
                    return clip.strip()
                else:
                    logger.warning("⚠️ Буфер обміну порожній після натискання кнопки копіювання")
            except Exception as e:
                logger.error("❌ Помилка читання буфера після натискання 'Copy': %s", e)

            if attempt < max_retries - 1:
                logger.info(f"⏳ Очікування {response_timeout} секунд перед наступною спробою...")
                time.sleep(response_timeout)

        # Після всіх спроб з кнопкою Copy пробуємо читати через DOM-селектори
        logger.info("📖 Якщо Copy не дав результату — пробуємо DOM-селектори")
        try:
            response = self.read_response_dom_selector()
            if response:
                logger.info("✅ Відповідь успішно прочитано з DOM")
                return response
        except Exception as e:
            logger.error("Помилка читання з DOM: %s", e)

        logger.warning("❌ Не вдалося отримати відповідь жодним методом")
        return None

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
        cfg = yaml.safe_load(f) or {}

    defaults = {
        "input_folder": "input",
        "response_timeout": 120,
        "cdp_port": 9222,
        "max_retries": 2,
        "on_missing_copy_button": "retry"
    }
    
    for k, v in defaults.items():
        cfg.setdefault(k, v)

    return cfg

def main():
    """Головна функція для отримання відповіді"""
    try:
        cfg = load_config()
        response_timeout = int(cfg.get("response_timeout", 120))
        
        # Визначаємо динамічний таймаут, якщо передано довжину тексту
        text_length = 0
        if len(sys.argv) >= 2:
            try:
                text_length = int(sys.argv[1])
            except ValueError:
                pass
        
        dynamic_timeout = response_timeout
        if text_length > 5000:
            dynamic_timeout = max(response_timeout, text_length // 100)
            logger.info(f"Довгий текст ({text_length} символів), збільшено таймаут до {dynamic_timeout} секунд")

        # Створюємо отримувач відповіді
        getter = ResponseGetter(cfg)
        
        # Підключаємося до браузера і знаходимо вкладку Google Gemini
        if not getter.connect_cdp():
            logger.error("Не вдалося підключитися до браузера або знайти вкладку Google Gemini")
            return None

        # Активуємо вкладку Gemini
        if not getter.activate_gemini_tab():
            logger.error("Не вдалося активувати вкладку Gemini")
            return False

        # Пауза для гарантії активації вкладки
        logger.info("Очікування 1 секунди для активації вкладки...")
        time.sleep(1)

        # Отримуємо відповідь
        response = getter.get_response(dynamic_timeout)
        
        if response:
            logger.info("Відповідь успішно отримано")
            # Виводимо відповідь в stdout для подальшого використання
            print(response)
            return True
        else:
            logger.warning("Не вдалося отримати відповідь")
            return False
            
    except Exception as e:
        logger.error(f"Помилка при отриманні відповіді: {e}")
        return False
    finally:
        if 'getter' in locals():
            getter.close()

if __name__ == "__main__":
    main()