"""Browser-based AI adapters — Phase 9.1.

Використовують Playwright для взаємодії з веб-інтерфейсами AI-інструментів
(Windsurf/Codeium, Cursor web).  Експериментальна функціональність.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .logic_ai_adapter import AIProvider, ChatRequest, ChatResponse, ChatMessage, ProviderCapabilities, UsageInfo


class BrowserProviderAdapter(AIProvider):
    """Базовий адаптер для AI-провайдерів через браузер (Playwright)."""

    name = "browser_base"
    display_name = "Browser Base"
    default_url = "about:blank"
    input_selectors: List[str] = ["textarea", "input[type=text]", "[contenteditable]"]
    response_selector: str = "body"
    submit_key: str = "Enter"
    wait_seconds: float = 15.0

    def __init__(
        self,
        url: Optional[str] = None,
        headless: bool = False,
        wait: Optional[float] = None,
        **kwargs: Any,
    ):
        caps = kwargs.pop("capabilities", None) or ProviderCapabilities(
            chat=True,
            max_context=128_000,
            streaming=False,
        )
        super().__init__(
            capabilities=caps,
            cost_per_1k_prompt=0.0,
            cost_per_1k_completion=0.0,
            **kwargs,
        )
        self.url = url or self.default_url
        self.headless = headless
        self.wait = wait if wait is not None else self.wait_seconds

    def available(self) -> bool:
        try:
            from .tools_playwright import _ensure_browser
            return True
        except Exception:
            return False

    def _format_prompt(self, request: ChatRequest) -> str:
        parts = []
        for msg in request.messages:
            role = msg.role
            content = msg.content
            parts.append(f"{role}: {content}")
        return "\n\n".join(parts)

    def chat(self, request: ChatRequest) -> ChatResponse:
        if not self.available():
            raise RuntimeError("Playwright not available")
        from .tools_playwright import playwright_navigate, playwright_get_text
        page = self._get_page()
        playwright_navigate(self.url)
        prompt = self._format_prompt(request)
        self._type_prompt(page, prompt)
        time.sleep(self.wait)
        text = playwright_get_text() or ""
        # Витягти відповідь за селектором, якщо можливо
        try:
            text = page.locator(self.response_selector).first.inner_text()
        except Exception:
            pass
        return ChatResponse(
            content=text,
            provider=self.name,
            model="browser",
            finish_reason="stop",
            usage=UsageInfo(
                prompt_tokens=self.estimate_tokens(request),
                completion_tokens=max(1, len(text) // 4),
                total_tokens=self.estimate_tokens(request) + max(1, len(text) // 4),
            ),
        )

    def _get_page(self):
        from .tools_playwright import _ensure_browser
        return _ensure_browser(headless=self.headless)

    def _type_prompt(self, page, prompt: str) -> bool:
        for sel in self.input_selectors:
            try:
                loc = page.locator(sel).first
                loc.fill(prompt)
                loc.press(self.submit_key)
                return True
            except Exception:
                continue
        raise RuntimeError("Не знайдено поле вводу на сторінці")


class WindsurfBrowserAdapter(BrowserProviderAdapter):
    """Адаптер для Windsurf (Codeium) через веб-інтерфейс."""

    name = "windsurf_browser"
    display_name = "Windsurf (Browser)"
    default_url = "https://codeium.com/live"
    input_selectors = [
        "textarea[placeholder*='message' i]",
        "textarea[placeholder*='prompt' i]",
        "textarea",
        "[contenteditable]",
    ]
    response_selector = ".chat-response, .message-content, [data-testid='chat-message']"


class CursorBrowserAdapter(BrowserProviderAdapter):
    """Адаптер для Cursor через веб-інтерфейс (якщо доступний)."""

    name = "cursor_browser"
    display_name = "Cursor (Browser)"
    default_url = "https://cursor.sh"
    input_selectors = ["textarea", "input[type=text]", "[contenteditable]"]
    response_selector = "body"
