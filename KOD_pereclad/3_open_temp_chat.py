#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
open_temp_chat.py — ЗАВЖДИ відкриває НОВИЙ тимчасовий чат у Gemini
Алгоритм: Ctrl+Shift+O (новий чат) → розгорнути меню → тимчасовий чат
"""

import time
import logging

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    raise RuntimeError(
        "Відсутні залежності. Виконайте:\n"
        "  pip install playwright\n"
        "  playwright install"
    ) from e

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("open_temp_chat")

DEFAULT_CDP_PORT = 9222
GEMINI_URL = "https://gemini.google.com/app"

# ─── Селектори ────────────────────────────────────────────────────────────────

TEMP_CHAT_SELECTORS = [
    'button[aria-label*="Temporary chat"]',
    'button[aria-label*="Тимчасовий чат"]',
    'button[mattooltip*="Тимчасовий"]',
    'button[title*="Temporary chat"]',
    'button[title*="Тимчасовий чат"]',
    'button:has-text("Temporary chat")',
    'button:has-text("Тимчасовий чат")',
    'div[role="button"][aria-label*="Temporary chat"]',
    'div[role="button"][aria-label*="Тимчасовий чат"]',
]

INPUT_SELECTORS = [
    'div[contenteditable="true"]',
    'textarea[aria-label*="prompt"]',
    'rich-textarea',
]

# ─── CDP / вкладка ────────────────────────────────────────────────────────────

def connect_to_chrome(cdp_port: int = DEFAULT_CDP_PORT, timeout_s: int = 5):
    url = f"http://127.0.0.1:{cdp_port}"
    start = time.time()
    last_err = None
    while time.time() - start < timeout_s:
        play = None
        try:
            play = sync_playwright().start()
            browser = play.chromium.connect_over_cdp(url)
            logger.info("✓ Підключено до Chrome CDP")
            return play, browser
        except Exception as e:
            last_err = e
            if play:
                try:
                    play.stop()
                except Exception:
                    pass
            time.sleep(0.7)
    raise RuntimeError(f"Не вдалося підключитися до Chrome: {last_err}")


def choose_target_page(browser):
    pages = []
    try:
        pages.extend(getattr(browser, "pages", []) or [])
    except Exception:
        pass
    try:
        for ctx in getattr(browser, "contexts", []) or []:
            for p in getattr(ctx, "pages", []) or []:
                if p not in pages:
                    pages.append(p)
    except Exception:
        pass

    for page in pages:
        try:
            if "gemini.google.com" in (page.url or "").lower():
                logger.info("✓ Знайдено вкладку Gemini")
                return page
        except Exception:
            continue

    if pages:
        return pages[0]
    try:
        return browser.new_page()
    except Exception:
        return None

# ─── Утиліти ──────────────────────────────────────────────────────────────────

def first_visible(page, selectors):
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                return loc.first
        except Exception:
            continue
    return None


def click_first_visible(page, selectors, timeout_ms: int = 2500) -> bool:
    loc = first_visible(page, selectors)
    if not loc:
        return False
    try:
        loc.click(timeout=timeout_ms)
        return True
    except Exception:
        return False

# ─── Перевірки стану ──────────────────────────────────────────────────────────

def temp_chat_button_visible(page) -> bool:
    return first_visible(page, TEMP_CHAT_SELECTORS) is not None


def temp_chat_active(page) -> bool:
    """Підтверджує що відкрито НОВИЙ порожній тимчасовий чат."""
    indicators = [
        'text="Тимчасові чати"',
        'text="Temporary chats"',
        'text="не відображаються в розділах"',
        'text="don\'t appear in Recent Chats"',
        'h1:has-text("Тимчасовий чат")',
        'h2:has-text("Тимчасовий чат")',
        'h1:has-text("Temporary chat")',
        'h2:has-text("Temporary chat")',
    ]
    for sel in indicators:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return True
        except Exception:
            continue
    return False

# ─── Крок 1: відкрити новий чат ───────────────────────────────────────────────

def start_new_chat(page) -> bool:
    """
    Відкриває НОВИЙ чат трьома способами (кожен наступний — fallback):
    1) Ctrl+Shift+O  — рідна гаряча клавіша Gemini
    2) Кнопка «Новий чат» у DOM
    3) Перехід на GEMINI_URL
    """
    logger.info("🔄 Відкриваємо новий чат...")

    # Спосіб 1: Ctrl+Shift+O
    try:
        page.keyboard.press("Control+Shift+O")
        page.wait_for_timeout(1200)
        logger.info("✓ Натиснуто Ctrl+Shift+O")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Ctrl+Shift+O не спрацював: {e}")

    # Спосіб 2: кнопка «Новий чат»
    new_chat_selectors = [
        'button[aria-label*="Новий чат"]',
        'button[aria-label*="New chat"]',
        'a[aria-label*="Новий чат"]',
        'a[aria-label*="New chat"]',
        'a[href="/app"]',
    ]
    if click_first_visible(page, new_chat_selectors):
        page.wait_for_timeout(1000)
        logger.info("✓ Натиснуто кнопку «Новий чат»")
        return True

    # Спосіб 3: goto
    try:
        logger.warning("⚠️ Переходимо на головну сторінку Gemini...")
        page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=12000)
        page.wait_for_timeout(1200)
        return True
    except Exception as e:
        logger.error(f"❌ Не вдалося відкрити новий чат: {e}")
        return False

# ─── Крок 2: розгорнути меню ──────────────────────────────────────────────────

def expand_sidebar(page) -> bool:
    """
    Розгортає бічне меню трьома методами:
    1) Прямі aria-label / title атрибути
    2) JS evaluate — перебір кнопок за текстом
    3) JS позиційний — кнопка у лівому верхньому куті
    """
    if temp_chat_button_visible(page):
        logger.info("✓ Меню вже розгорнуте")
        return True

    # Метод 1: прямі атрибутні селектори
    direct = [
        '[aria-label="Expand menu"]',
        '[aria-label="Розгорнути меню"]',
        '[aria-label="Expand sidebar"]',
        '[aria-label="Розгорнути бічну панель"]',
        '[title="Expand menu"]',
        '[title="Розгорнути меню"]',
        'button[aria-label*="Main menu"]',
        'button[jsname][aria-label*="menu" i]',
        'button[jsname][aria-label*="меню" i]',
        'button mat-icon[fonticon="menu"]',
        'button mat-icon[data-mat-icon-name="menu"]',
    ]
    for sel in direct:
        try:
            loc = page.locator(sel)
            if loc.count() == 0 or not loc.first.is_visible():
                continue
            aria = (loc.first.get_attribute("aria-label") or "").lower()
            if any(w in aria for w in ("collapse", "згорнути", "close")):
                continue
            loc.first.click(timeout=2000, force=True)
            page.wait_for_timeout(900)
            if temp_chat_button_visible(page):
                logger.info(f"✓ Меню розгорнуто (метод 1): {sel}")
                return True
        except Exception:
            continue

    # Метод 2: JS evaluate за текстом кнопок
    try:
        ok = page.evaluate("""() => {
            const kw = ['expand menu','розгорнути меню','expand sidebar',
                        'розгорнути бічну','toggle menu','toggle sidebar',
                        'open menu','відкрити меню'];
            for (const el of document.querySelectorAll('button,[role="button"]')) {
                const t = ((el.ariaLabel||'')+(el.title||'')+(el.textContent||'')).toLowerCase();
                if (kw.some(k => t.includes(k))) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) { el.click(); return true; }
                }
            }
            return false;
        }""")
        if ok:
            page.wait_for_timeout(900)
            if temp_chat_button_visible(page):
                logger.info("✓ Меню розгорнуто (метод 2 JS-текст)")
                return True
    except Exception as e:
        logger.debug(f"Метод 2 помилка: {e}")

    # Метод 3: JS позиційний — лівий верхній кут
    try:
        ok = page.evaluate("""() => {
            for (const el of document.querySelectorAll('button,[role="button"]')) {
                const r = el.getBoundingClientRect();
                if (r.x < 80 && r.y < 80 && r.width > 20 && r.height > 20) {
                    el.click(); return true;
                }
            }
            return false;
        }""")
        if ok:
            page.wait_for_timeout(900)
            if temp_chat_button_visible(page):
                logger.info("✓ Меню розгорнуто (метод 3 позиція)")
                return True
    except Exception as e:
        logger.debug(f"Метод 3 помилка: {e}")

    logger.warning("⚠️ Не вдалося розгорнути меню")
    return False

# ─── Крок 3: натиснути тимчасовий чат ────────────────────────────────────────

def click_temp_chat(page, timeout_s: int = 10) -> bool:
    """Натискає кнопку тимчасового чату; текстовий перебір як fallback."""
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        # Прямі селектори
        if click_first_visible(page, TEMP_CHAT_SELECTORS):
            logger.info("✓ Натиснуто кнопку тимчасового чату")
            return True

        # Текстовий перебір як fallback
        try:
            for btn in page.query_selector_all("button"):
                try:
                    text = (btn.inner_text() or "").lower()
                    aria = (btn.get_attribute("aria-label") or "").lower()
                    if "тимчасов" in text or "temporary" in text or "тимчасов" in aria:
                        btn.click()
                        logger.info(f"✓ Натиснуто (текст-пошук): «{btn.inner_text().strip()}»")
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        page.wait_for_timeout(500)

    logger.error("❌ Кнопку тимчасового чату не знайдено")
    return False

# ─── Головна функція ──────────────────────────────────────────────────────────

def open_new_temp_chat(page) -> bool:
    """
    Послідовність при кожному запуску:
    1. Переконатись що ми на Gemini
    2. Ctrl+Shift+O → новий чат (з fallback на кнопку / goto)
    3. Розгорнути меню (3 методи)
    4. Натиснути «Тимчасовий чат»
    5. Перевірити індикатори + фокус на поле вводу
    """
    if not page:
        return False

    try:
        page.bring_to_front()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(800)

        # Переконуємось що ми на Gemini
        if "gemini.google.com" not in (page.url or "").lower():
            logger.info(f"Перехід на {GEMINI_URL}")
            page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=12000)
            page.wait_for_timeout(1200)

        # Крок 1: завжди відкриваємо новий чат
        start_new_chat(page)
        page.wait_for_timeout(500)

        # Крок 2: розгорнути меню
        expand_sidebar(page)
        page.wait_for_timeout(300)

        # Крок 3: тимчасовий чат
        if not click_temp_chat(page, timeout_s=10):
            return False

        page.wait_for_timeout(1000)

        # Перевірка індикаторів (не блокуюча — кнопку вже натиснули)
        deadline = time.time() + 5
        while time.time() < deadline:
            if temp_chat_active(page):
                logger.info("✅ Підтверджено: НОВИЙ тимчасовий чат активний")
                break
            page.wait_for_timeout(600)

        # Фокус на поле вводу
        click_first_visible(page, INPUT_SELECTORS)
        logger.info("🎉 Готово до відправки повідомлення")
        return True

    except Exception as e:
        logger.error(f"❌ Помилка: {e}")
        return False

# ─── Точка входу ──────────────────────────────────────────────────────────────

def main(cdp_port: int = DEFAULT_CDP_PORT):
    play = None
    browser = None
    try:
        play, browser = connect_to_chrome(cdp_port=cdp_port)
        page = choose_target_page(browser)

        if not page:
            logger.error("❌ Не знайдено вкладку")
            return 1

        ok = open_new_temp_chat(page)
        return 0 if ok else 2

    finally:
        try:
            if play:
                play.stop()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main(cdp_port=9222))