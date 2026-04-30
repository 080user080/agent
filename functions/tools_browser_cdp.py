"""Browser automation через CDP (Chrome DevTools Protocol).

Підключається до ІСНУЮЧОГО Chrome з --remote-debugging-port=9222.
Не запускає новий браузер — працює з тим, що вже відкритий у користувача.

Інтегровано з KOD_pereclad: перевірений код для Gemini/ChatGPT/Claude/Windsurf.

Використання:
  1. Запустити Chrome: Start_3APYCK_Chrome_port_9222.bat
  2. Або агент запустить сам через cdp_ensure_chrome()
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .core_tool_runtime import make_tool_result
from .common_decorators import llm_function

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    Browser = None
    BrowserContext = None
    Page = None
    PLAYWRIGHT_AVAILABLE = False

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    pyperclip = None
    PYPERCLIP_AVAILABLE = False

logger = logging.getLogger("tools_browser_cdp")

# ─── Конфігурація ─────────────────────────────────────────────────────────────

CDP_PORT = 9222
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
CHROME_USER_DATA_DIR = r"C:\Temp\chrome_debug_profile"
CHROME_LAUNCH_TIMEOUT = 20

# ─── Стан з'єднання (singleton) ──────────────────────────────────────────────

_cdp_playwright = None
_cdp_browser = None       # CDP browser connection
_cdp_active_page = None   # Активна сторінка


# ─── Фрази-маркери відмови AI ────────────────────────────────────────────────

AI_REFUSAL_MARKERS = [
    "я штучний інтелект",
    "я є штучним інтелектом",
    "як штучний інтелект",
    "я мовна модель",
    "я великий мовний",
    "я не можу виконати",
    "я не здатний",
    "не маю потрібних функцій",
    "не маю можливості",
    "i'm an ai",
    "i am an ai",
    "as an ai",
    "i'm a language model",
    "i cannot perform",
    "я не в змозі",
    "ця задача виходить за межі",
    "це виходить за рамки моїх",
]


def is_ai_refusal(text: str) -> bool:
    """Перевіряє чи є відповідь відмовою AI."""
    if not text:
        return False
    lower = text.lower()
    for marker in AI_REFUSAL_MARKERS:
        if marker in lower:
            return True
    return False


# ─── Утиліти підключення ─────────────────────────────────────────────────────

def _is_port_open(host: str = "127.0.0.1", port: int = CDP_PORT) -> bool:
    """Перевірити чи відкритий CDP порт."""
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except Exception:
        return False


def _find_chrome_exe() -> Optional[str]:
    """Знайти шлях до Chrome."""
    for p in CHROME_PATHS:
        if os.path.isfile(p):
            return p
    return None


def _launch_chrome(port: int = CDP_PORT, url: str = "", timeout: int = CHROME_LAUNCH_TIMEOUT) -> bool:
    """Запустити Chrome з --remote-debugging-port якщо ще не запущений."""
    if _is_port_open("127.0.0.1", port):
        logger.info("CDP порт %s вже відкритий — Chrome працює.", port)
        return True

    chrome_path = _find_chrome_exe()
    if not chrome_path:
        logger.error("Chrome не знайдено. Встановіть Chrome або вкажіть шлях.")
        return False

    Path(CHROME_USER_DATA_DIR).mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={CHROME_USER_DATA_DIR}",
        "--no-default-browser-check",
        "--no-first-run",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-features=RendererCodeIntegrity",
    ]
    if url:
        cmd.append(url)

    logger.info("Запускаю Chrome: %s ...", chrome_path)
    try:
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        logger.error("Помилка запуску Chrome: %s", e)
        return False

    start = time.time()
    while time.time() - start < timeout:
        if _is_port_open("127.0.0.1", port):
            logger.info("Chrome запущено, CDP порт %s доступний.", port)
            return True
        time.sleep(1)

    logger.error("Chrome не відкрив CDP порт за %s секунд.", timeout)
    return False


def _connect_cdp(port: int = CDP_PORT, timeout_s: int = 5) -> Tuple[Any, Any]:
    """Підключитись до Chrome через CDP. Повертає (playwright, browser)."""
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright не встановлений. Виконайте: pip install playwright && playwright install chromium")

    url = f"http://127.0.0.1:{port}"
    start = time.time()
    last_err = None

    while time.time() - start < timeout_s:
        play = None
        try:
            play = sync_playwright().start()
            browser = play.chromium.connect_over_cdp(url)
            logger.info("Підключено до Chrome CDP %s", url)
            return play, browser
        except Exception as e:
            last_err = e
            if play:
                try:
                    play.stop()
                except Exception:
                    pass
            time.sleep(0.7)

    raise RuntimeError(f"Не вдалося підключитися до Chrome CDP: {last_err}")


def _get_all_pages(browser) -> List:
    """Отримати всі вкладки з усіх контекстів."""
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
    return pages


def _find_page_by(pages: List, title_pattern: str = "", url_pattern: str = "") -> Optional[Any]:
    """Знайти вкладку за заголовком або URL (регістронезалежно)."""
    title_lower = title_pattern.lower()
    url_lower = url_pattern.lower()

    for page in pages:
        try:
            page_title = (page.title() or "").lower()
            page_url = (page.url or "").lower()

            if title_lower and title_lower in page_title:
                return page
            if url_lower and url_lower in page_url:
                return page
        except Exception:
            continue
    return None


# ─── Управління з'єднанням (singleton) ───────────────────────────────────────

def _ensure_cdp_connection(port: int = CDP_PORT, auto_launch: bool = True) -> Tuple[Any, Any]:
    """Гарантувати CDP з'єднання. Якщо Chrome не запущений — запустити."""
    global _cdp_playwright, _cdp_browser

    # Якщо вже підключені — перевірити чи живе
    if _cdp_browser is not None:
        try:
            _get_all_pages(_cdp_browser)
            return _cdp_playwright, _cdp_browser
        except Exception:
            _disconnect_cdp()

    # Якщо порт не відкритий — спробувати запустити Chrome
    if auto_launch and not _is_port_open("127.0.0.1", port):
        if not _launch_chrome(port):
            raise RuntimeError("Не вдалося запустити Chrome з CDP портом")

    play, browser = _connect_cdp(port)
    _cdp_playwright = play
    _cdp_browser = browser
    return play, browser


def _disconnect_cdp():
    """Закрити CDP з'єднання (Chrome продовжує працювати)."""
    global _cdp_playwright, _cdp_browser, _cdp_active_page
    for obj in (_cdp_browser, _cdp_playwright):
        try:
            if obj and hasattr(obj, 'close'):
                obj.close()
            elif obj and hasattr(obj, 'stop'):
                obj.stop()
        except Exception:
            pass
    _cdp_browser = None
    _cdp_playwright = None
    _cdp_active_page = None


def _get_or_find_page(title: str = "", url: str = "") -> Any:
    """Знайти або створити сторінку через CDP."""
    global _cdp_active_page
    _, browser = _ensure_cdp_connection()
    pages = _get_all_pages(browser)

    if title or url:
        page = _find_page_by(pages, title_pattern=title, url_pattern=url)
        if page:
            _cdp_active_page = page
            return page

    # Якщо активна сторінка ще жива — повернути її
    if _cdp_active_page is not None:
        try:
            _ = _cdp_active_page.url
            return _cdp_active_page
        except Exception:
            _cdp_active_page = None

    # Повернути першу вкладку або створити нову
    if pages:
        _cdp_active_page = pages[0]
        return pages[0]

    try:
        page = browser.new_page()
        _cdp_active_page = page
        return page
    except Exception:
        return None


# ─── Утиліти для введення/виведення ──────────────────────────────────────────

def _first_visible(page, selectors: List[str]):
    """Знайти перший видимий елемент зі списку селекторів."""
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                return loc.first
        except Exception:
            continue
    return None


def _click_first_visible(page, selectors: List[str], timeout_ms: int = 2500) -> bool:
    """Клікнути перший видимий елемент."""
    loc = _first_visible(page, selectors)
    if not loc:
        return False
    try:
        loc.click(timeout=timeout_ms)
        return True
    except Exception:
        return False


def _type_via_clipboard(page, text: str) -> bool:
    """Ввести текст через буфер обміну (працює з будь-якою мовою/кирилицею)."""
    if not PYPERCLIP_AVAILABLE:
        logger.warning("pyperclip не встановлений, використовую page.keyboard.type()")
        page.keyboard.type(text)
        return True

    pyperclip.copy(text)
    time.sleep(0.15)
    page.keyboard.press("Control+V")
    time.sleep(0.2)
    return True


def _wait_for_response(page, timeout: int = 120, poll_interval: float = 2.0) -> bool:
    """Чекати поки з'явиться кнопка Copy (ознака готовності відповіді)."""
    copy_selectors = [
        'copy-button button.icon-button',
        'button[aria-label*="Copy"]',
        'button[title*="Copy"]',
        'button[class*="copy"]',
    ]
    start = time.time()
    while (time.time() - start) < timeout:
        for sel in copy_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    elapsed = int(time.time() - start)
                    logger.info("Відповідь готова через %sс", elapsed)
                    return True
            except Exception:
                continue
        time.sleep(poll_interval)

    logger.warning("Таймаут очікування відповіді (%sс)", timeout)
    return False


def _click_copy_button(page) -> bool:
    """Натиснути кнопку Copy для копіювання відповіді в буфер."""
    copy_selectors = [
        'copy-button button.icon-button',
        'button[aria-label*="Copy"]',
        'button[title*="Copy"]',
        'button[class*="copy"]',
        'div.model-response-actions button',
        'button[data-tooltip*="Copy"]',
    ]
    for sel in copy_selectors:
        try:
            buttons = page.query_selector_all(sel)
            if not buttons:
                continue
            # Остання кнопка = остання відповідь
            last_btn = buttons[-1]
            if last_btn.is_visible():
                # Спроба JS click (надійніше)
                try:
                    last_btn.evaluate("el => el.click()")
                except Exception:
                    last_btn.click()
                time.sleep(0.5)
                return True
        except Exception:
            continue
    return False


def _read_response_dom(page) -> Optional[str]:
    """Прочитати відповідь з DOM (fallback якщо Copy не спрацював)."""
    selectors = [
        'div.model-response-text',
        'div[class*="response-content"]',
        'div[class*="assistant"]',
        'div[class*="message"]',
        'article',
        'div[role="article"]',
    ]
    for sel in selectors:
        try:
            elems = page.query_selector_all(sel)
            if elems:
                last_el = elems[-1]
                text = last_el.inner_text() or ""
                if text.strip():
                    return text.strip()
        except Exception:
            continue
    return None


# ─── LLM-функції (інструменти агента) ────────────────────────────────────────

@llm_function(
    name="cdp_ensure_chrome",
    description="Запустити Chrome з debug-портом (якщо не запущений) і підключитися через CDP",
    parameters={
        "url": "URL для відкриття при запуску (необов'язково)",
        "port": "CDP порт (за замовчуванням 9222)"
    }
)
def cdp_ensure_chrome(url: str = "", port: int = CDP_PORT) -> Dict[str, Any]:
    """Переконатися що Chrome запущений з CDP і підключитися."""
    try:
        if not PLAYWRIGHT_AVAILABLE:
            return make_tool_result(False, "❌ Playwright не встановлений. pip install playwright && playwright install chromium")

        if url and not _is_port_open("127.0.0.1", port):
            _launch_chrome(port, url)
        _ensure_cdp_connection(port, auto_launch=True)
        pages = _get_all_pages(_cdp_browser)
        tabs_info = []
        for i, p in enumerate(pages):
            try:
                tabs_info.append(f"  [{i}] {p.title()} — {p.url}")
            except Exception:
                tabs_info.append(f"  [{i}] (недоступна)")
        tab_list = "\n".join(tabs_info) if tabs_info else "  (порожньо)"
        return make_tool_result(
            True,
            f"✅ Підключено до Chrome CDP (порт {port}). Вкладок: {len(pages)}\n{tab_list}",
            data={"port": port, "tabs_count": len(pages)}
        )
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e), retryable=True)


@llm_function(
    name="cdp_list_tabs",
    description="Показати всі відкриті вкладки Chrome",
    parameters={}
)
def cdp_list_tabs() -> Dict[str, Any]:
    """Список всіх вкладок Chrome."""
    try:
        _, browser = _ensure_cdp_connection()
        pages = _get_all_pages(browser)
        lines = []
        for i, p in enumerate(pages):
            try:
                lines.append(f"[{i}] {p.title()} — {p.url}")
            except Exception:
                lines.append(f"[{i}] (недоступна)")
        return make_tool_result(True, f"Вкладки Chrome ({len(pages)}):\n" + "\n".join(lines), data={"count": len(pages)})
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e))


@llm_function(
    name="cdp_open_tab",
    description="Відкрити URL у новій або існуючій вкладці Chrome",
    parameters={
        "url": "URL для відкриття",
        "reuse_tab": "Якщо true — шукати існуючу вкладку з цим URL (за замовчуванням true)"
    }
)
def cdp_open_tab(url: str, reuse_tab: bool = True) -> Dict[str, Any]:
    """Відкрити URL у Chrome через CDP."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        _, browser = _ensure_cdp_connection()

        # Шукаємо існуючу вкладку
        if reuse_tab:
            pages = _get_all_pages(browser)
            # Шукаємо за доменом
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            for p in pages:
                try:
                    if domain in (p.url or "").lower():
                        p.bring_to_front()
                        if p.url != url:
                            p.goto(url, wait_until="domcontentloaded", timeout=30000)
                        global _cdp_active_page
                        _cdp_active_page = p
                        title = p.title()
                        return make_tool_result(True, f"✅ Активовано існуючу вкладку: {title}", data={"url": url, "title": title, "reused": True})
                except Exception:
                    continue

        # Створюємо нову вкладку
        page = _get_or_find_page()
        if page and (not page.url or "about:blank" in page.url or "chrome://" in page.url):
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        else:
            contexts = getattr(browser, "contexts", []) or []
            if contexts:
                page = contexts[0].new_page()
            else:
                page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

        page.bring_to_front()
        _cdp_active_page = page
        title = page.title()
        return make_tool_result(True, f"✅ Відкрито: {title} ({url})", data={"url": url, "title": title, "reused": False})
    except Exception as e:
        return make_tool_result(False, f"❌ Помилка навігації: {e}", error=str(e), retryable=True)


@llm_function(
    name="cdp_switch_tab",
    description="Переключитися на вкладку Chrome за заголовком або URL",
    parameters={
        "title": "Пошук за заголовком (частковий збіг, необов'язково)",
        "url": "Пошук за URL (частковий збіг, необов'язково)",
        "index": "Індекс вкладки (необов'язково)"
    }
)
def cdp_switch_tab(title: str = "", url: str = "", index: int = -1) -> Dict[str, Any]:
    """Переключити активну вкладку."""
    try:
        _, browser = _ensure_cdp_connection()
        pages = _get_all_pages(browser)
        global _cdp_active_page

        if index >= 0:
            if index >= len(pages):
                return make_tool_result(False, f"❌ Індекс {index} поза діапазоном (вкладок: {len(pages)})")
            page = pages[index]
            page.bring_to_front()
            _cdp_active_page = page
            return make_tool_result(True, f"✅ Активовано вкладку [{index}]: {page.title()}")

        page = _find_page_by(pages, title_pattern=title, url_pattern=url)
        if page:
            page.bring_to_front()
            _cdp_active_page = page
            return make_tool_result(True, f"✅ Активовано: {page.title()} — {page.url}")

        return make_tool_result(False, f"❌ Вкладку не знайдено (title='{title}', url='{url}')")
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e))


@llm_function(
    name="cdp_type_text",
    description="Ввести текст у поле на сторінці Chrome (підтримує кирилицю через буфер обміну)",
    parameters={
        "text": "Текст для введення",
        "selector": "CSS-селектор поля (необов'язково — якщо пусто, вводить у активне поле)",
        "submit": "Натиснути Enter після введення (за замовчуванням false)"
    }
)
def cdp_type_text(text: str, selector: str = "", submit: bool = False) -> Dict[str, Any]:
    """Ввести текст через CDP."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        if selector:
            # Шукаємо конкретне поле
            input_selectors = [selector]
        else:
            # Типові селектори для полів вводу AI-чатів
            input_selectors = [
                'div.ql-editor[contenteditable="true"]',
                'rich-textarea[aria-label*="prompt" i]',
                'div.ql-editor.textarea',
                'textarea[aria-label*="prompt" i]',
                'textarea[placeholder*="message" i]',
                'div[contenteditable="true"]',
                'textarea',
            ]

        # Знаходимо та активуємо поле
        field_found = False
        for sel in input_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    time.sleep(0.1)
                    field_found = True
                    break
            except Exception:
                continue

        if not field_found and not selector:
            # Спроба клікнути у центр сторінки
            page.keyboard.press("Tab")
            time.sleep(0.1)

        # Вводимо текст через буфер обміну
        _type_via_clipboard(page, text)

        if submit:
            # Спочатку шукаємо кнопку Send
            send_selectors = [
                'button[aria-label*="Send" i]',
                'button[aria-label*="Надіслати" i]',
                'button[type="submit"]',
            ]
            clicked = _click_first_visible(page, send_selectors)
            if not clicked:
                page.keyboard.press("Enter")

        preview = text[:80] + "..." if len(text) > 80 else text
        return make_tool_result(True, f"✅ Введено текст ({len(text)} символів): {preview}", data={"length": len(text), "submitted": submit})
    except Exception as e:
        return make_tool_result(False, f"❌ Помилка введення: {e}", error=str(e))


@llm_function(
    name="cdp_get_response",
    description="Отримати відповідь AI з вкладки Chrome (чекає генерацію, копіює через кнопку Copy або читає DOM)",
    parameters={
        "timeout": "Максимальний час очікування відповіді в секундах (за замовчуванням 120)",
        "max_retries": "Кількість повторних спроб копіювання (за замовчуванням 2)"
    }
)
def cdp_get_response(timeout: int = 120, max_retries: int = 2) -> Dict[str, Any]:
    """Отримати відповідь AI з активної вкладки."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        # Чекаємо поки відповідь згенерується
        ready = _wait_for_response(page, timeout=timeout)

        # Спроба через кнопку Copy
        for attempt in range(max_retries):
            if _click_copy_button(page):
                time.sleep(0.5)
                if PYPERCLIP_AVAILABLE:
                    clip = pyperclip.paste()
                    if clip and clip.strip():
                        text = clip.strip()
                        refusal = is_ai_refusal(text)
                        return make_tool_result(
                            True,
                            f"✅ Відповідь отримано ({len(text)} символів)" + (" ⚠️ ВІДМОВА AI" if refusal else ""),
                            data={"text": text, "method": "copy_button", "ai_refusal": refusal, "length": len(text)}
                        )
            time.sleep(1)

        # Fallback: читаємо з DOM
        dom_text = _read_response_dom(page)
        if dom_text:
            refusal = is_ai_refusal(dom_text)
            return make_tool_result(
                True,
                f"✅ Відповідь з DOM ({len(dom_text)} символів)" + (" ⚠️ ВІДМОВА AI" if refusal else ""),
                data={"text": dom_text, "method": "dom_selector", "ai_refusal": refusal, "length": len(dom_text)}
            )

        if not ready:
            return make_tool_result(False, f"❌ Відповідь не з'явилась за {timeout}с", error="timeout")
        return make_tool_result(False, "❌ Не вдалося скопіювати відповідь", error="copy_failed")
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e))


@llm_function(
    name="cdp_get_page_text",
    description="Прочитати текст зі сторінки або елементу Chrome",
    parameters={
        "selector": "CSS-селектор (необов'язково — якщо пусто, читає всю сторінку)"
    }
)
def cdp_get_page_text(selector: str = "") -> Dict[str, Any]:
    """Прочитати текст зі сторінки."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        if selector:
            el = page.query_selector(selector)
            if not el:
                return make_tool_result(False, f"❌ Елемент '{selector}' не знайдено")
            text = el.inner_text()
        else:
            text = page.inner_text("body")

        max_len = 8000
        truncated = len(text) > max_len
        if truncated:
            text = text[:max_len] + f"\n... [{len(text) - max_len} символів обрізано]"

        return make_tool_result(True, f"Текст сторінки:\n{text}", data={"text": text, "truncated": truncated})
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e))


@llm_function(
    name="cdp_click",
    description="Клікнути елемент на сторінці Chrome за CSS-селектором",
    parameters={
        "selector": "CSS-селектор елементу",
        "force": "Примусовий клік навіть якщо елемент перекритий (за замовчуванням false)"
    }
)
def cdp_click(selector: str, force: bool = False) -> Dict[str, Any]:
    """Клікнути елемент через CDP."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        page.wait_for_selector(selector, timeout=5000)
        page.click(selector, force=force)
        return make_tool_result(True, f"✅ Клікнуто: {selector}")
    except Exception as e:
        return make_tool_result(False, f"❌ Клік не вдався ({selector}): {e}", error=str(e))


@llm_function(
    name="cdp_click_text",
    description="Клікнути по елементу з вказаним текстом (через Playwright get_by_text — стійкіше за CSS).",
    parameters={
        "text": "Текст всередині елемента (точний або частковий, регістронезалежно)",
        "exact": "True — точний збіг; False — частковий (за замовчуванням)",
        "timeout": "Таймаут пошуку у секундах (за замовчуванням 5)",
    }
)
def cdp_click_text(text: str, exact: bool = False, timeout: int = 5) -> Dict[str, Any]:
    """Клікнути по тексту на сторінці (без CSS-селектора)."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        timeout_ms = int(timeout * 1000)

        # Спроба 1: Playwright get_by_text (нативний, найстійкіший)
        try:
            loc = page.get_by_text(text, exact=exact)
            if loc.count() > 0:
                loc.first.click(timeout=timeout_ms)
                return make_tool_result(True, f"✅ Клікнуто (text): {text}", data={"method": "get_by_text"})
        except Exception:
            pass

        # Спроба 2: get_by_role з name
        for role in ("button", "link", "menuitem", "tab"):
            try:
                loc = page.get_by_role(role, name=text, exact=exact)
                if loc.count() > 0:
                    loc.first.click(timeout=timeout_ms)
                    return make_tool_result(True, f"✅ Клікнуто (role={role}): {text}", data={"method": f"role:{role}"})
            except Exception:
                continue

        # Спроба 3: XPath fallback
        try:
            xpath = f"//*[contains(normalize-space(.), '{text}')]" if not exact else f"//*[normalize-space(.)='{text}']"
            page.click(f"xpath={xpath}", timeout=timeout_ms)
            return make_tool_result(True, f"✅ Клікнуто (xpath): {text}", data={"method": "xpath"})
        except Exception as e:
            return make_tool_result(False, f"❌ Текст '{text}' не знайдено або клік не вдався: {e}", error=str(e))
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e), retryable=True)


@llm_function(
    name="cdp_wait_for_text",
    description="Чекати появи тексту на сторінці (для синхронізації з динамічним контентом).",
    parameters={
        "text": "Текст для очікування",
        "timeout": "Максимальний час очікування у секундах (за замовчуванням 30)",
    }
)
def cdp_wait_for_text(text: str, timeout: int = 30) -> Dict[str, Any]:
    """Чекати поки на сторінці з'явиться вказаний текст."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        timeout_ms = int(timeout * 1000)

        # Спроба 1: get_by_text + wait_for visible
        try:
            loc = page.get_by_text(text)
            loc.first.wait_for(state="visible", timeout=timeout_ms)
            return make_tool_result(True, f"✅ Текст '{text}' з'явився", data={"method": "get_by_text"})
        except Exception:
            pass

        # Спроба 2: polling через JS
        start = time.time()
        poll = 0.5
        while time.time() - start < timeout:
            try:
                content = page.inner_text("body")
                if text in content:
                    return make_tool_result(True, f"✅ Текст '{text}' знайдено в body", data={"method": "polling"})
            except Exception:
                pass
            time.sleep(poll)

        return make_tool_result(False, f"❌ Текст '{text}' не з'явився за {timeout}с", error="timeout")
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e))


@llm_function(
    name="cdp_fill",
    description="Заповнити поле за CSS-селектором або міткою (label) текстом (через Playwright fill).",
    parameters={
        "selector_or_label": "CSS-селектор (наприклад input[name='q']) або текст мітки поля",
        "text": "Текст для введення",
    }
)
def cdp_fill(selector_or_label: str, text: str) -> Dict[str, Any]:
    """Заповнити поле через Playwright fill (надійніше за keyboard.type)."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        # Спроба 1: як CSS-селектор
        try:
            page.fill(selector_or_label, text, timeout=5000)
            return make_tool_result(True, f"✅ Заповнено '{selector_or_label}' ({len(text)} символів)", data={"method": "css"})
        except Exception:
            pass

        # Спроба 2: як label
        try:
            loc = page.get_by_label(selector_or_label)
            if loc.count() > 0:
                loc.first.fill(text, timeout=5000)
                return make_tool_result(True, f"✅ Заповнено label '{selector_or_label}'", data={"method": "label"})
        except Exception:
            pass

        # Спроба 3: placeholder
        try:
            loc = page.get_by_placeholder(selector_or_label)
            if loc.count() > 0:
                loc.first.fill(text, timeout=5000)
                return make_tool_result(True, f"✅ Заповнено placeholder '{selector_or_label}'", data={"method": "placeholder"})
        except Exception:
            pass

        return make_tool_result(False, f"❌ Поле '{selector_or_label}' не знайдено")
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e), retryable=True)


@llm_function(
    name="cdp_screenshot",
    description="Зробити скріншот поточної сторінки Chrome",
    parameters={
        "selector": "CSS-селектор елементу (необов'язково — якщо пусто, скріншот всієї сторінки)"
    }
)
def cdp_screenshot(selector: str = "") -> Dict[str, Any]:
    """Зробити скріншот через CDP."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        d = Path("logs/screenshots")
        d.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = d / f"cdp_{ts}.png"

        if selector:
            el = page.query_selector(selector)
            if not el:
                return make_tool_result(False, f"❌ Елемент '{selector}' не знайдено")
            el.screenshot(path=str(path))
        else:
            page.screenshot(path=str(path))

        return make_tool_result(True, f"✅ Скріншот збережено: {path}", data={"path": str(path)})
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e))


@llm_function(
    name="cdp_evaluate_js",
    description="Виконати JavaScript на поточній сторінці Chrome",
    parameters={"code": "JavaScript код для виконання"}
)
def cdp_evaluate_js(code: str) -> Dict[str, Any]:
    """Виконати JavaScript через CDP."""
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки")

        result = page.evaluate(code)
        return make_tool_result(True, f"JS результат: {result}", data={"result": result})
    except Exception as e:
        return make_tool_result(False, f"❌ JS помилка: {e}", error=str(e))


@llm_function(
    name="cdp_send_to_ai",
    description="Відправити промпт до AI у вкладці Chrome (Gemini/ChatGPT/Claude) і отримати відповідь",
    parameters={
        "prompt": "Текст промпту для відправки",
        "wait_timeout": "Час очікування відповіді в секундах (за замовчуванням 120)",
        "max_retries": "Кількість повторних спроб при відмові AI (за замовчуванням 2)"
    }
)
def cdp_send_to_ai(prompt: str, wait_timeout: int = 120, max_retries: int = 2) -> Dict[str, Any]:
    """Відправити промпт і отримати відповідь (end-to-end).

    Об'єднує: ввести текст → відправити → чекати → скопіювати відповідь.
    При відмові AI — повторює з новим чатом.
    """
    try:
        page = _get_or_find_page()
        if not page:
            return make_tool_result(False, "❌ Немає активної сторінки. Спочатку cdp_open_tab()")

        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning("Повторна спроба %s/%s (відмова AI)", attempt, max_retries)
                # Спроба відкрити новий чат
                try:
                    page.keyboard.press("Control+Shift+O")
                    time.sleep(1.2)
                except Exception:
                    pass

            # Знаходимо поле вводу
            input_selectors = [
                'div.ql-editor[contenteditable="true"]',
                'rich-textarea[aria-label*="prompt" i]',
                'div.ql-editor.textarea',
                'textarea[aria-label*="prompt" i]',
                'textarea[placeholder*="message" i]',
                'div[contenteditable="true"][role="textbox"]',
                'div[contenteditable="true"]',
                'textarea',
            ]

            field_clicked = False
            for sel in input_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        time.sleep(0.1)
                        field_clicked = True
                        break
                except Exception:
                    continue

            if not field_clicked:
                return make_tool_result(False, "❌ Не знайдено поле вводу на сторінці")

            # Вводимо текст
            _type_via_clipboard(page, prompt)
            time.sleep(0.2)

            # Відправляємо
            send_selectors = [
                'button[aria-label*="Send" i]',
                'button[aria-label*="Надіслати" i]',
                'button[type="submit"]',
            ]
            if not _click_first_visible(page, send_selectors):
                page.keyboard.press("Enter")

            time.sleep(1)

            # Чекаємо відповідь
            _wait_for_response(page, timeout=wait_timeout)

            # Копіюємо
            response_text = None
            if _click_copy_button(page):
                time.sleep(0.5)
                if PYPERCLIP_AVAILABLE:
                    clip = pyperclip.paste()
                    if clip and clip.strip():
                        response_text = clip.strip()

            if not response_text:
                response_text = _read_response_dom(page)

            if not response_text:
                return make_tool_result(False, "❌ Не вдалося отримати відповідь")

            # Перевірка на відмову AI
            if is_ai_refusal(response_text):
                if attempt < max_retries:
                    logger.warning("AI відмовив, повторюю...")
                    time.sleep(1)
                    continue
                return make_tool_result(
                    False,
                    f"❌ AI відмовив після {max_retries + 1} спроб",
                    data={"text": response_text, "ai_refusal": True}
                )

            return make_tool_result(
                True,
                f"✅ Відповідь отримано ({len(response_text)} символів)",
                data={"text": response_text, "ai_refusal": False, "attempt": attempt + 1, "length": len(response_text)}
            )

        return make_tool_result(False, "❌ Вичерпано спроби")
    except Exception as e:
        return make_tool_result(False, f"❌ {e}", error=str(e))


@llm_function(
    name="cdp_disconnect",
    description="Відключитися від Chrome CDP (Chrome продовжує працювати)",
    parameters={}
)
def cdp_disconnect() -> Dict[str, Any]:
    """Відключити CDP з'єднання."""
    _disconnect_cdp()
    return make_tool_result(True, "✅ CDP з'єднання закрито. Chrome продовжує працювати.")


# ─── Реєстрація ──────────────────────────────────────────────────────────────

ALL_CDP_TOOLS = [
    cdp_ensure_chrome,
    cdp_list_tabs,
    cdp_open_tab,
    cdp_switch_tab,
    cdp_type_text,
    cdp_get_response,
    cdp_get_page_text,
    cdp_click,
    cdp_click_text,
    cdp_wait_for_text,
    cdp_fill,
    cdp_screenshot,
    cdp_evaluate_js,
    cdp_send_to_ai,
    cdp_disconnect,
]


def register_cdp_tools(registry):
    """Зареєструвати CDP інструменти в реєстрі."""
    for tool in ALL_CDP_TOOLS:
        if hasattr(tool, "_is_llm_function"):
            registry.register(tool)
