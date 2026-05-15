"""Playwright wrapper for browser automation (Phase 7/9)."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Any, Dict, Optional
from functions.core_tool_runtime import make_tool_result
from functions.common_decorators import llm_function

try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
except Exception as _pw_exc:  # noqa: BLE001
    sync_playwright = None  # type: ignore[misc,assignment]
    Page = None  # type: ignore[misc,assignment]
    Browser = None  # type: ignore[misc,assignment]
    BrowserContext = None  # type: ignore[misc,assignment]

_browser_instance: Optional[Browser] = None
_context_instance: Optional[BrowserContext] = None
_page_instance: Optional[Page] = None
_playwright_instance = None
_cdp_mode = False  # True якщо підключені через CDP до існуючого Chrome


def _is_cdp_port_open(port: int = 9222) -> bool:
    """Перевірити чи відкритий CDP порт."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except Exception:
        return False


def _ensure_browser(headless: bool = False, cdp_port: int = 9222, prefer_cdp: bool = True) -> Page:
    """Отримати сторінку браузера.

    Якщо Chrome з CDP портом доступний і prefer_cdp=True — підключається до нього.
    Інакше запускає новий Chromium.
    """
    global _browser_instance, _context_instance, _page_instance, _playwright_instance, _cdp_mode
    if _page_instance is not None and not _page_instance.is_closed():
        return _page_instance
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
    _playwright_instance = sync_playwright().start()

    # Спроба CDP підключення до існуючого Chrome
    if prefer_cdp and _is_cdp_port_open(cdp_port):
        try:
            _browser_instance = _playwright_instance.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
            _cdp_mode = True
            pages = []
            try:
                for ctx in getattr(_browser_instance, "contexts", []) or []:
                    pages.extend(getattr(ctx, "pages", []) or [])
            except Exception:
                pass
            if not pages:
                pages = getattr(_browser_instance, "pages", []) or []
            _page_instance = pages[0] if pages else _browser_instance.new_page()
            return _page_instance
        except Exception:
            _cdp_mode = False
            try:
                _playwright_instance.stop()
            except Exception:
                pass
            _playwright_instance = sync_playwright().start()

    # Fallback: запустити новий Chromium
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
    ]
    _browser_instance = _playwright_instance.chromium.launch(
        headless=headless,
        args=args,
    )
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    _context_instance = _browser_instance.new_context(
        viewport={"width": 1280, "height": 720},
        accept_downloads=True,
        user_agent=user_agent,
    )
    _page_instance = _context_instance.new_page()
    # Hide navigator.webdriver
    _page_instance.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    _cdp_mode = False
    return _page_instance


def _close_browser() -> None:
    global _browser_instance, _context_instance, _page_instance, _playwright_instance
    for obj in (_page_instance, _context_instance, _browser_instance, _playwright_instance):
        try:
            if obj and hasattr(obj, 'close'):
                obj.close()
            elif obj and hasattr(obj, 'stop'):
                obj.stop()
        except Exception:
            pass
    _page_instance = None
    _context_instance = None
    _browser_instance = None
    _playwright_instance = None


def _screenshot_dir() -> Path:
    d = Path("logs/screenshots")
    d.mkdir(parents=True, exist_ok=True)
    return d


@llm_function(name="playwright_navigate", description="Open URL in Playwright browser", parameters={"url": "site address (e.g. https://google.com)"})
def playwright_navigate(url: str) -> Dict[str, Any]:
    try:
        page = _ensure_browser()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = page.title()
        return make_tool_result(True, f"Opened: {title} ({url})", data={"url": url, "title": title})
    except Exception as exc:
        return make_tool_result(False, f"Navigation error: {exc}", error=str(exc), retryable=True)


@llm_function(name="playwright_click", description="Click element by CSS selector", parameters={"selector": "CSS selector (e.g. #submit)", "wait": "wait for element presence, sec (default 5)"})
def playwright_click(selector: str, wait: int = 5) -> Dict[str, Any]:
    try:
        page = _ensure_browser()
        page.wait_for_selector(selector, timeout=wait * 1000)
        page.click(selector)
        return make_tool_result(True, f"Clicked: {selector}")
    except Exception as exc:
        return make_tool_result(False, f"Click failed {selector}: {exc}", error=str(exc))


@llm_function(name="playwright_type", description="Type text into field by CSS selector", parameters={"selector": "CSS selector of input", "text": "text to type", "submit": "press Enter after typing (yes/no, default no)"})
def playwright_type(selector: str, text: str, submit=False) -> Dict[str, Any]:
    try:
        page = _ensure_browser()
        page.fill(selector, text)
        if isinstance(submit, str):
            submit = submit.lower() in ("yes", "true", "1", "y")
        if submit:
            page.press(selector, "Enter")
        return make_tool_result(True, f"Typed into {selector}")
    except Exception as exc:
        return make_tool_result(False, f"Type error: {exc}", error=str(exc))


@llm_function(name="playwright_screenshot", description="Screenshot current browser page", parameters={"selector": "optional CSS selector for element instead of full page", "full_page": "screenshot full page (yes/no, default no)"})
def playwright_screenshot(selector: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
    try:
        page = _ensure_browser()
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = _screenshot_dir() / f"pw_{ts}.png"
        if selector:
            el = page.query_selector(selector)
            if el is None:
                return make_tool_result(False, f"Element {selector} not found for screenshot")
            el.screenshot(path=str(path))
        else:
            page.screenshot(path=str(path), full_page=full_page)
        return make_tool_result(True, f"Screenshot saved: {path}", data={"path": str(path)})
    except Exception as exc:
        return make_tool_result(False, f"Screenshot error: {exc}", error=str(exc))


@llm_function(name="playwright_get_text", description="Get text from element or whole page", parameters={"selector": "CSS selector (empty = whole body)"})
def playwright_get_text(selector: Optional[str] = None) -> Dict[str, Any]:
    try:
        page = _ensure_browser()
        if selector:
            el = page.query_selector(selector)
            if el is None:
                return make_tool_result(False, f"Element {selector} not found")
            text = el.inner_text()
        else:
            text = page.inner_text("body")
        max_len = 8000
        truncated = len(text) > max_len
        if truncated:
            text = text[:max_len] + f"\n... [{len(text) - max_len} chars truncated]"
        return make_tool_result(True, f"Page text:\n{text}", data={"text": text, "truncated": truncated})
    except Exception as exc:
        return make_tool_result(False, f"Get text error: {exc}", error=str(exc))


@llm_function(name="playwright_evaluate", description="Execute JavaScript in page context", parameters={"js_code": "JavaScript code to run (e.g. document.title)"})
def playwright_evaluate(js_code: str) -> Dict[str, Any]:
    try:
        page = _ensure_browser()
        result = page.evaluate(js_code)
        return make_tool_result(True, f"JS result: {result}", data={"result": result})
    except Exception as exc:
        return make_tool_result(False, f"JS error: {exc}", error=str(exc))


@llm_function(name="playwright_close", description="Close Playwright browser and free resources", parameters={})
def playwright_close() -> Dict[str, Any]:
    _close_browser()
    return make_tool_result(True, "Playwright browser closed")


ALL_PLAYWRIGHT_TOOLS = [
    playwright_navigate,
    playwright_click,
    playwright_type,
    playwright_screenshot,
    playwright_get_text,
    playwright_evaluate,
    playwright_close,
]


def register_playwright_tools(registry):
    for tool in ALL_PLAYWRIGHT_TOOLS:
        if hasattr(tool, "_is_llm_function"):
            registry.register(tool)


def open_browser_playwright(url: str) -> Dict[str, Any]:
    return playwright_navigate(url)
