# p_302_open_temp_chat.py
"""
Модуль P_302: Open Temp Chat
Інструмент для швидкого відкриття тимчасового чату в Gemini через CDP
Повністю автономний модуль - не потребує зовнішніх імпортів
"""
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("Playwright не встановлено. Виконайте: pip install playwright")


# Модель конфігурації
class OpenTempChatConfig(BaseModel):
    """Модель конфігурації для модуля відкриття тимчасового чату"""
    enabled: bool = Field(False, description="Чи увімкнено модуль відкриття чату")
    cdp_port: int = Field(9222, description="Порт для CDP підключення")
    wait_after_reload: float = Field(2.0, description="Час очікування після перезавантаження сторінки")
    connection_timeout: int = Field(12, description="Таймаут підключення до Chrome (секунди)")


def prepare_config_models() -> Dict[str, Any]:
    """
    ОБОВ'ЯЗКОВА: Повертає моделі конфігурації для модуля
    """
    return {"open_temp_chat": OpenTempChatConfig}


def check_dependencies() -> Dict[str, Any]:
    """
    ОПЦІЙНА: Перевіряє наявність залежностей модуля
    """
    try:
        from playwright.sync_api import sync_playwright
        return {
            "all_available": True,
            "playwright": True,
            "missing_packages": []
        }
    except ImportError:
        return {
            "all_available": False,
            "playwright": False,
            "missing_packages": ["playwright"]
        }


# Функції з оригінального скрипту (адаптовані)
def connect_to_chrome(cdp_port: int = 9222, timeout_s: int = 10):
    """Підключаємось до вже запущеного Chrome через CDP"""
    url = f"http://127.0.0.1:{cdp_port}"
    play = None
    conn = None
    start = time.time()
    while True:
        try:
            play = sync_playwright().start()
            conn = play.chromium.connect_over_cdp(url)
            logging.info("Підключено до CDP: %s", url)
            return play, conn
        except Exception as e:
            elapsed = time.time() - start
            if elapsed >= timeout_s:
                if play:
                    try:
                        play.stop()
                    except Exception:
                        pass
                raise RuntimeError(f"Не вдалося підключитися до Chrome CDP за {timeout_s}s: {e}")
            time.sleep(0.5)


def choose_target_page(conn):
    """Проста логіка вибору сторінки"""
    pages = []
    try:
        pages = getattr(conn, "pages", []) or []
    except Exception:
        pages = []
    
    try:
        contexts = getattr(conn, "contexts", []) or []
        for ctx in contexts:
            ctx_pages = getattr(ctx, "pages", []) or []
            for p in ctx_pages:
                if p not in pages:
                    pages.append(p)
    except Exception:
        pass

    if not pages:
        try:
            page = conn.new_page()
            return page
        except Exception:
            return None

    for p in pages:
        try:
            url = ""
            title = ""
            try:
                url = p.url or ""
            except Exception:
                url = ""
            try:
                title = p.title() or ""
            except Exception:
                title = ""
            if 'gemini' in url.lower() or 'gemini' in title.lower() or 'google' in title.lower():
                return p
        except Exception:
            continue

    return pages[0]


def expand_menu_if_needed(page):
    """Розгортає меню, якщо є кнопка з текстом 'Розгорнути меню' - ПРАКТИЧНА РЕАЛІЗАЦІЯ"""
    try:
        logging.info("🔍 Пошук кнопки розгортання меню...")
        
        # Основний селектор з вашого HTML
        main_menu_selector = 'button[data-test-id="side-nav-menu-button"]'
        
        try:
            # Чекаємо появу кнопки головного меню
            page.wait_for_selector(main_menu_selector, timeout=5000)
            menu_button = page.query_selector(main_menu_selector)
            
            if menu_button:
                logging.info("✅ Знайдено кнопку головного меню, натискаю...")
                
                # Перевіряємо видимість
                if menu_button.is_visible():
                    logging.info("Кнопка видима, клікаю...")
                else:
                    logging.info("Кнопка не видима, але спробую клікнути...")
                
                # Спроби кліку різними методами
                click_methods = [
                    ("звичайний клік", lambda: menu_button.click()),
                    ("JS клік", lambda: page.evaluate("(element) => element.click()", menu_button)),
                    ("force клік", lambda: menu_button.click(force=True)),
                ]
                
                for method_name, click_func in click_methods:
                    try:
                        logging.info(f"Спроба {method_name}...")
                        click_func()
                        time.sleep(1)  # Затримка для розгортання меню
                        logging.info(f"✅ {method_name} успішний!")
                        return True
                    except Exception as e:
                        logging.debug(f"❌ {method_name} невдалий: {e}")
                        continue
                        
        except Exception as e:
            logging.debug(f"Не вдалося знайти/клікнути головне меню: {e}")
        
        # Альтернативні селектори
        alternative_selectors = [
            'button[aria-label*="Головне меню"]',
            'button[aria-label*="Menu"]',
            'button[title*="Menu"]',
            'button.mat-icon-button',  # Material Design кнопки
            '.main-menu-button',
        ]
        
        for selector in alternative_selectors:
            try:
                button = page.query_selector(selector)
                if button:
                    logging.info(f"✅ Знайдено альтернативну кнопку меню: {selector}")
                    button.click()
                    time.sleep(1)
                    return True
            except Exception as e:
                logging.debug(f"Помилка з селектором {selector}: {e}")
                continue
        
        # Пошук за текстом
        try:
            menu_button_by_text = page.query_selector('button:has-text("Розгорнути меню")')
            if menu_button_by_text:
                logging.info("✅ Знайдено кнопку за текстом 'Розгорнути меню'")
                menu_button_by_text.click()
                time.sleep(1)
                return True
        except Exception as e:
            logging.debug(f"Помилка пошуку за текстом: {e}")
        
        logging.info("❌ Кнопку розгортання меню не знайдено")
        return False
        
    except Exception as e:
        logging.error(f"❌ Критична помилка при розгортанні меню: {e}")
        return False


def open_temp_chat_on_page(page, wait_after_reload: float = 2.0, max_attempts: int = 3):
    """Оновлює сторінку та намагається клікнути кнопку 'Тимчасовий чат' з кількома спробами"""
    if page is None:
        logging.error("Сторінка не передана")
        return False

    for attempt in range(max_attempts):
        logging.info(f"🔄 Спроба {attempt + 1}/{max_attempts} відкриття тимчасового чату...")
        
        try:
            # Завжди намагаємось розгорнути меню ПЕРЕД пошуком кнопки чату
            if attempt >= 0:  # З першої ж спроби
                logging.info("🔍 Спроба розгорнути меню...")
                menu_expanded = expand_menu_if_needed(page)
                if menu_expanded:
                    logging.info("✅ Меню розгорнуто, чекаю 2 секунди...")
                    time.sleep(2)
                else:
                    logging.info("❌ Меню не вдалося розгорнути, продовжую...")

            # Тільки для першої спроби робимо повне перезавантаження
            if attempt == 0:
                try:
                    page.reload(timeout=30000)
                    logging.info("🔁 Сторінка перезавантажена")
                except PlaywrightTimeoutError:
                    logging.warning("Перезавантаження сторінки timeout, продовжую...")
                except Exception:
                    logging.debug("reload викликав виняток, ігнорую")

                try:
                    page.wait_for_load_state('networkidle', timeout=4000)
                except Exception:
                    pass
            
            time.sleep(wait_after_reload)

            selectors = [
                'button[data-test-id="temp-chat-button"]',
                'button[aria-label*="Тимчасовий чат"]',
                'button[mattooltip*="Тимчасовий чат"]',
                'button.temp-chat-button',
                'button:has-text("Тимчасовий чат")',
                'button:has-text("Temporary chat")',
                'button[aria-label*="Temporary chat"]'
            ]

            chat_found = False
            for sel in selectors:
                try:
                    el = None
                    try:
                        page.wait_for_selector(sel, timeout=3000)
                        el = page.query_selector(sel)
                    except Exception:
                        el = page.query_selector(sel)
                    
                    if not el:
                        logging.debug(f"Селектор {sel} не знайдено")
                        continue

                    logging.info(f"✅ Знайдено селектор: {sel} — пробую клік.")
                    
                    # Перевіряємо видимість
                    if not el.is_visible():
                        logging.info("Елемент не видимий, прокручую...")
                        try:
                            el.scroll_into_view_if_needed()
                            time.sleep(0.5)
                        except Exception:
                            pass

                    # Спроби кліку
                    click_methods = [
                        ("JS клік", lambda: page.evaluate(f"document.querySelector('{sel}').click()")),
                        ("звичайний клік", lambda: el.click(timeout=3000)),
                        ("force клік", lambda: el.click(force=True)),
                    ]
                    
                    clicked = False
                    for method_name, click_func in click_methods:
                        try:
                            logging.info(f"🖱️ Спроба {method_name}...")
                            click_func()
                            clicked = True
                            logging.info(f"✅ {method_name} успішний!")
                            break
                        except Exception as e:
                            logging.debug(f"❌ {method_name} невдалий: {e}")
                            continue

                    if not clicked:
                        logging.debug(f"Не вдалось клікнути селектором {sel}")
                        continue

                    # Перевірка успішності
                    time.sleep(2.0)
                    try:
                        body_text = page.inner_text('body') or ""
                    except Exception:
                        body_text = ""
                    
                    indicators = [
                        "Тимчасовий чат", 
                        "temporary chat", 
                        "не використовуються для навчання", 
                        "зберігаються протягом"
                    ]
                    
                    for ind in indicators:
                        if ind.lower() in body_text.lower():
                            logging.info(f"✅ Індикатор тимчасового чату знайдено: {ind}")
                            
                            # Фокус на полі вводу
                            focus_selectors = [
                                'textarea[aria-label*="Enter a prompt"]',
                                'textarea[aria-label*="Введіть запит"]',
                                'div[contenteditable="true"]',
                                'textarea'
                            ]
                            for fs in focus_selectors:
                                try:
                                    field = page.query_selector(fs)
                                    if field and field.is_visible():
                                        field.click()
                                        time.sleep(0.3)
                                        #page.keyboard.press("Tab")
                                        logging.info(f"✅ Фокус на полі вводу встановлено: {fs}")
                                        break
                                except Exception:
                                    continue
                            
                            chat_found = True
                            break

                    if chat_found:
                        logging.info("🎉 Тимчасовий чат успішно відкрито!")
                        return True
                    else:
                        logging.warning("⚠️ Індикатор тимчасового чату не знайдено після кліку")

                except Exception as e:
                    logging.debug(f"Помилка при обробці селектора {sel}: {e}")
                    continue

            if not chat_found:
                logging.warning(f"❌ Не знайдено жодного селектора для 'Тимчасовий чат' у спробі {attempt + 1}")
                if attempt < max_attempts - 1:
                    logging.info(f"⏳ Чекаю 2 секунди перед наступною спробою...")
                    time.sleep(2)

        except Exception as e:
            logging.exception(f"❌ Помилка у спробі {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                logging.info(f"⏳ Чекаю 2 секунди перед наступною спробою...")
                time.sleep(2)

    logging.error("💥 Не вдалося відкрити тимчасовий чат після всіх спроб")
    return False


def _run_open_temp_chat(cdp_port: int, wait_after_reload: float, connection_timeout: int) -> int:
    """Головна логіка відкриття тимчасового чату"""
    play = None
    conn = None
    try:
        play, conn = connect_to_chrome(cdp_port=cdp_port, timeout_s=connection_timeout)
        page = choose_target_page(conn)
        if not page:
            logging.error("❌ Не знайдено доступної сторінки/вкладки у Chrome")
            return 1
        
        ok = open_temp_chat_on_page(page, wait_after_reload=wait_after_reload, max_attempts=3)
        if ok:
            logging.info("✅ Операція завершена: 'Тимчасовий чат' відкрито")
            return 0
        else:
            logging.error("❌ Не вдалося відкрити 'Тимчасовий чат'")
            return 2
    finally:
        try:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            if play:
                try:
                    play.stop()
                except Exception:
                    pass
        except Exception:
            pass


def initialize(app_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    ОБОВ'ЯЗКОВА: Головна функція ініціалізації модуля
    """
    config = app_context['config']
    logger = app_context['logger'].getChild('OpenTempChat')
    
    if not hasattr(config, 'open_temp_chat') or not config.open_temp_chat.enabled:
        logger.info("Модуль відкриття тимчасового чату вимкнено в конфігурації")
        return None
    
    chat_config = config.open_temp_chat
    logger.info("🔧 Ініціалізація модуля відкриття тимчасового чату...")
    
    deps_status = check_dependencies()
    if not deps_status["all_available"]:
        logger.error("❌ Відсутні залежності для модуля відкриття чату")
        return {
            "status": "error",
            "error": "Відсутні залежності",
            "missing_packages": deps_status["missing_packages"]
        }
    
    try:
        logger.info(f"🚀 Запуск відкриття тимчасового чату на порті {chat_config.cdp_port}...")
        
        exit_code = _run_open_temp_chat(
            cdp_port=chat_config.cdp_port,
            wait_after_reload=chat_config.wait_after_reload,
            connection_timeout=chat_config.connection_timeout
        )
        
        if exit_code == 0:
            logger.info("✅ Тимчасовий чат успішно відкрито")
            return {
                "status": "success",
                "exit_code": exit_code,
                "message": "Тимчасовий чат успішно відкрито"
            }
        else:
            logger.warning(f"⚠️ Відкриття чату завершено з кодом: {exit_code}")
            return {
                "status": "completed_with_warnings",
                "exit_code": exit_code,
                "message": f"Відкриття чату завершено з кодом: {exit_code}"
            }
            
    except Exception as e:
        logger.error(f"❌ Помилка при відкритті тимчасового чату: {e}")
        return {
            "status": "error",
            "error": str(e),
            "module": "open_temp_chat"
        }


def stop(app_context: Dict[str, Any]) -> None:
    """
    ОПЦІЙНА: Функція для коректного закриття модуля
    """
    logger = app_context['logger'].getChild('OpenTempChat')
    logger.info("Модуль відкриття тимчасового чату коректно завершує роботу")