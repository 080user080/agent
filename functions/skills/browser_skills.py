"""Browser Skills — високорівневі операції з браузером.

Реалізовані skills:
- OpenBrowser: Відкрити браузер (Chrome/Edge) на вказаному URL.
- SearchGoogle: Виконати пошук в Google і повернути результати.
- FillForm: Заповнити форму на сторінці.

Використовує наявні інструменти (tools_browser_cdp, tools_playwright)
або subprocess як fallback.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from .base import BaseSkill, SkillError, SkillResult

logger = logging.getLogger("skills.browser")


class OpenBrowser(BaseSkill):
    """Відкрити браузер на вказаному URL.

    Parameters:
        url: URL для відкриття.
        browser: "chrome" (default) або "edge".
        headless: True для headless режиму (default: False).
        wait_seconds: Скільки секунд чекати після відкриття (default: 2).

    Returns:
        SkillResult з даними:
        - url: відкритий URL
        - method: який метод використано (playwright / cdp / subprocess)
    """

    name = "open_browser"
    description = "Відкрити браузер на вказаному URL"

    async def execute(
        self,
        ctx: Any,
        url: str = "about:blank",
        browser: str = "chrome",
        headless: bool = False,
        wait_seconds: float = 2.0,
        **kwargs: Any,
    ) -> SkillResult:
        self.logger.info("Opening %s with %s (headless=%s)", url, browser, headless)
        method = "subprocess"

        try:
            # Спроба 1: Playwright
            if self._has_playwright():
                result = await self._open_with_playwright(url, browser, headless)
                if result.success:
                    result.metadata["method"] = "playwright"
                    return result
                logger.warning("Playwright failed, fallback to subprocess")

            # Спроба 2: CDP (Chrome DevTools Protocol)
            if self._has_cdp():
                result = self._open_with_cdp(url, browser)
                if result.success:
                    result.metadata["method"] = "cdp"
                    return result
                logger.warning("CDP failed, fallback to subprocess")

            # Спроба 3: subprocess (найнадійніший fallback)
            self._open_with_subprocess(url, browser)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            return SkillResult(
                success=True,
                data={"url": url, "browser": browser, "method": "subprocess"},
            )

        except Exception as exc:  # noqa: BLE001
            error_msg = f"Failed to open browser: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg)
            return SkillResult(success=False, data=None, error=error_msg)

    # -- private helpers -----------------------------------------------------

    def _has_playwright(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def _has_cdp(self) -> bool:
        try:
            from functions.tools.tools_browser_cdp import (  # noqa: F401
                cdp_navigate,
            )
            return True
        except ImportError:
            return False

    async def _open_with_playwright(
        self, url: str, browser: str, headless: bool,
    ) -> SkillResult:
        try:
            from playwright.async_api import async_playwright

            browser_type = "chromium" if browser in ("chrome", "chromium") else browser
            async with async_playwright() as p:
                # Використовуємо існуючий екземпляр з контексту, якщо є
                launch_options = {"headless": headless}
                instance = await getattr(p, browser_type).launch(**launch_options)
                page = await instance.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                await page.close()

            return SkillResult(success=True, data={"url": url})
        except Exception as exc:  # noqa: BLE001
            return SkillResult(success=False, error=str(exc))

    def _open_with_cdp(self, url: str, browser: str) -> SkillResult:
        try:
            # Використовуємо CDP через devtools
            import subprocess
            import http.client
            import json

            # Знаходимо порт Chrome DevTools
            # Типовий порт: 9222
            conn = http.client.HTTPConnection("127.0.0.1", 9222, timeout=2)
            conn.request("GET", "/json/new?" + quote_plus(url))
            resp = conn.getresponse()
            if resp.status == 200:
                data = json.loads(resp.read())
                conn.close()
                return SkillResult(success=True, data={
                    "url": url,
                    "target": data.get("id", ""),
                    "method": "cdp",
                })
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        return SkillResult(success=False, error="CDP not available")

    def _open_with_subprocess(self, url: str, browser: str) -> None:
        """Відкрити URL через subprocess (найнадійніший спосіб)."""
        if browser == "edge":
            subprocess.Popen(
                ["cmd", "/c", "start", "msedge", url],
                shell=True,
            )
        elif browser == "firefox":
            subprocess.Popen(
                ["cmd", "/c", "start", "firefox", url],
                shell=True,
            )
        else:
            # Chrome / default
            subprocess.Popen(
                ["cmd", "/c", "start", "chrome", url],
                shell=True,
            )


class SearchGoogle(BaseSkill):
    """Виконати пошук в Google і повернути результати.

    Parameters:
        query: Пошуковий запит.
        num_results: Максимальна кількість результатів (default: 5).

    Returns:
        SkillResult з даними:
        - query: пошуковий запит.
        - results: список словників {title, url, snippet}.
    """

    name = "search_google"
    description = "Виконати пошук в Google"

    async def execute(
        self,
        ctx: Any,
        query: str = "",
        num_results: int = 5,
        **kwargs: Any,
    ) -> SkillResult:
        if not query:
            return SkillResult(success=False, error="query is required")

        self.logger.info("Searching Google for: %s", query)
        url = f"https://www.google.com/search?q={quote_plus(query)}&num={min(num_results, 10)}"

        results: List[Dict[str, str]] = []

        # Спроба 1: Через playwright
        if self._has_playwright():
            try:
                results = await self._search_with_playwright(url)
                if results:
                    return SkillResult(
                        success=True,
                        data={"query": query, "results": results},
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Playwright search failed: %s", exc)

        # Спроба 2: Через requests + BeautifulSoup
        try:
            results = self._search_with_requests(url)
            if results:
                return SkillResult(
                    success=True,
                    data={"query": query, "results": results},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Requests search failed: %s", exc)

        # Fallback: повернути помилку
        return SkillResult(
            success=False,
            error="Could not search Google (Playwright/requests not available)",
        )

    # -- private helpers -----------------------------------------------------

    def _has_playwright(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    async def _search_with_playwright(
        self, url: str,
    ) -> List[Dict[str, str]]:
        from playwright.async_api import async_playwright

        results: List[Dict[str, str]] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            # Парсимо результати пошуку
            items = await page.query_selector_all("div.g")
            for item in items[:5]:
                try:
                    title_el = await item.query_selector("h3")
                    link_el = await item.query_selector("a")
                    snippet_el = await item.query_selector("div.VwiC3b")

                    title = await title_el.inner_text() if title_el else ""
                    href = await link_el.get_attribute("href") if link_el else ""
                    snippet = await snippet_el.inner_text() if snippet_el else ""

                    if title:
                        results.append({
                            "title": title,
                            "url": href or "",
                            "snippet": snippet,
                        })
                except Exception:  # noqa: BLE001
                    continue

            await browser.close()

        return results

    def _search_with_requests(self, url: str) -> List[Dict[str, str]]:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results: List[Dict[str, str]] = []
        for g in soup.select("div.g")[:5]:
            title_el = g.select_one("h3")
            link_el = g.select_one("a")
            snippet_el = g.select_one("div.VwiC3b, span.aCOpRe")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": link_el.get("href", "") if link_el else "",
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })
        return results


class FillForm(BaseSkill):
    """Заповнити форму на веб-сторінці.

    Parameters:
        url: URL сторінки з формою (опційно, якщо сторінка вже відкрита).
        fields: Словник {selector: value} для заповнення полів.
        submit_selector: CSS-селектор кнопки submit (опційно).
        wait_after: Секунд чекати після заповнення (default: 1).

    Returns:
        SkillResult з даними:
        - filled_fields: кількість заповнених полів.
        - submitted: чи була натиснута кнопка submit.
    """

    name = "fill_form"
    description = "Заповнити форму на веб-сторінці"

    async def execute(
        self,
        ctx: Any,
        url: str = "",
        fields: Optional[Dict[str, str]] = None,
        submit_selector: str = "",
        wait_after: float = 1.0,
        **kwargs: Any,
    ) -> SkillResult:
        fields = fields or {}
        if not fields:
            return SkillResult(success=False, error="fields is required")

        self.logger.info(
            "Filling form at %s with %d fields",
            url or "(current page)", len(fields),
        )

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()

                if url:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(1000)

                filled_count = 0
                for selector, value in fields.items():
                    try:
                        await page.fill(selector, value)
                        filled_count += 1
                        self.logger.debug("Filled %s = %s", selector, value)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.warning(
                            "Failed to fill %s: %s", selector, exc,
                        )

                submitted = False
                if submit_selector:
                    try:
                        await page.click(submit_selector)
                        submitted = True
                        self.logger.info("Clicked submit: %s", submit_selector)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.warning(
                            "Failed to click submit %s: %s",
                            submit_selector, exc,
                        )

                await page.wait_for_timeout(int(wait_after * 1000))
                await browser.close()

            return SkillResult(
                success=True,
                data={
                    "filled_fields": filled_count,
                    "total_fields": len(fields),
                    "submitted": submitted,
                },
            )

        except Exception as exc:  # noqa: BLE001
            error_msg = f"FillForm failed: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg)
            return SkillResult(success=False, error=error_msg)


__all__ = [
    "OpenBrowser",
    "SearchGoogle",
    "FillForm",
]