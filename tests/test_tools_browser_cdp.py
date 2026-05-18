"""Тести для browser CDP tools — ЕТАП 5."""
from unittest.mock import MagicMock, patch

import pytest

from functions.tools import tools_browser_cdp as cdp


# ─── Mocks helpers ────────────────────────────────────────────────────────────

def _mock_page(**overrides):
    """Створити mock-сторінку Playwright."""
    page = MagicMock()
    page.url = overrides.get("url", "https://example.com")
    page.title.return_value = overrides.get("title", "Example")
    page.inner_text.return_value = overrides.get("body_text", "Hello world")
    return page


@pytest.fixture(autouse=True)
def _reset_cdp_globals():
    """Скинути глобальні CDP змінні перед кожним тестом."""
    cdp._cdp_playwright = None
    cdp._cdp_browser = None
    cdp._cdp_active_page = None
    yield
    cdp._cdp_playwright = None
    cdp._cdp_browser = None
    cdp._cdp_active_page = None


# ─── is_ai_refusal ────────────────────────────────────────────────────────────

class TestAIRefusal:
    def test_refusal_uk(self):
        assert cdp.is_ai_refusal("я штучний інтелект і не можу") is True

    def test_refusal_en(self):
        assert cdp.is_ai_refusal("I'm an AI language model") is True

    def test_normal_response(self):
        assert cdp.is_ai_refusal("Звичайна відповідь без відмови") is False

    def test_empty(self):
        assert cdp.is_ai_refusal("") is False

    def test_none(self):
        assert cdp.is_ai_refusal(None) is False


# ─── Connection management ────────────────────────────────────────────────────

class TestConnection:
    def test_is_port_open_closed(self):
        # Невідомий високий порт — закритий
        assert cdp._is_port_open("127.0.0.1", 65530) is False

    def test_find_chrome_exe_returns_path_or_none(self):
        result = cdp._find_chrome_exe()
        # Може бути None або шлях
        assert result is None or isinstance(result, str)


# ─── cdp_click_text ───────────────────────────────────────────────────────────

class TestClickText:
    def test_click_text_no_page(self):
        with patch.object(cdp, "_get_or_find_page", return_value=None):
            result = cdp.cdp_click_text("Submit")
            assert result["ok"] is False
            assert "сторінки" in result["message"].lower()

    def test_click_text_get_by_text(self):
        page = _mock_page()
        loc = MagicMock()
        loc.count.return_value = 1
        page.get_by_text.return_value = loc

        with patch.object(cdp, "_get_or_find_page", return_value=page):
            result = cdp.cdp_click_text("Submit")
            assert result["ok"] is True
            assert result["data"]["method"] == "get_by_text"
            loc.first.click.assert_called_once()

    def test_click_text_role_fallback(self):
        page = _mock_page()
        # get_by_text повертає 0 елементів
        loc_text = MagicMock()
        loc_text.count.return_value = 0
        page.get_by_text.return_value = loc_text

        # get_by_role(button) — знайдено
        loc_role = MagicMock()
        loc_role.count.return_value = 1
        page.get_by_role.return_value = loc_role

        with patch.object(cdp, "_get_or_find_page", return_value=page):
            result = cdp.cdp_click_text("Submit")
            assert result["ok"] is True
            assert "role:" in result["data"]["method"]


# ─── cdp_wait_for_text ────────────────────────────────────────────────────────

class TestWaitForText:
    def test_wait_for_text_no_page(self):
        with patch.object(cdp, "_get_or_find_page", return_value=None):
            result = cdp.cdp_wait_for_text("Loading...", timeout=1)
            assert result["ok"] is False

    def test_wait_for_text_get_by_text_success(self):
        page = _mock_page()
        loc = MagicMock()
        page.get_by_text.return_value = loc
        loc.first.wait_for.return_value = None  # немає виключення = знайдено

        with patch.object(cdp, "_get_or_find_page", return_value=page):
            result = cdp.cdp_wait_for_text("Готово", timeout=2)
            assert result["ok"] is True
            assert result["data"]["method"] == "get_by_text"

    def test_wait_for_text_polling_fallback(self):
        page = _mock_page(body_text="Some Готово text")
        # get_by_text викидає
        loc = MagicMock()
        loc.first.wait_for.side_effect = Exception("not found")
        page.get_by_text.return_value = loc

        with patch.object(cdp, "_get_or_find_page", return_value=page):
            result = cdp.cdp_wait_for_text("Готово", timeout=2)
            assert result["ok"] is True
            assert result["data"]["method"] == "polling"

    def test_wait_for_text_timeout(self):
        page = _mock_page(body_text="нема такого")
        loc = MagicMock()
        loc.first.wait_for.side_effect = Exception("not found")
        page.get_by_text.return_value = loc

        with patch.object(cdp, "_get_or_find_page", return_value=page):
            result = cdp.cdp_wait_for_text("Готово", timeout=1)
            assert result["ok"] is False
            assert result.get("error") == "timeout"


# ─── cdp_fill ─────────────────────────────────────────────────────────────────

class TestFill:
    def test_fill_no_page(self):
        with patch.object(cdp, "_get_or_find_page", return_value=None):
            result = cdp.cdp_fill("input", "text")
            assert result["ok"] is False

    def test_fill_css_success(self):
        page = _mock_page()
        page.fill.return_value = None

        with patch.object(cdp, "_get_or_find_page", return_value=page):
            result = cdp.cdp_fill("input[name='q']", "search query")
            assert result["ok"] is True
            assert result["data"]["method"] == "css"
            page.fill.assert_called_once()

    def test_fill_label_fallback(self):
        page = _mock_page()
        page.fill.side_effect = Exception("css not found")
        loc = MagicMock()
        loc.count.return_value = 1
        page.get_by_label.return_value = loc

        with patch.object(cdp, "_get_or_find_page", return_value=page):
            result = cdp.cdp_fill("Username", "alice")
            assert result["ok"] is True
            assert result["data"]["method"] == "label"


# ─── cdp_open_tab ─────────────────────────────────────────────────────────────

class TestOpenTab:
    def test_open_tab_normalizes_url(self):
        page = MagicMock()
        page.url = ""
        page.title.return_value = "Example"
        browser = MagicMock()
        browser.contexts = []
        browser.new_page.return_value = page

        with patch.object(cdp, "_ensure_cdp_connection", return_value=(None, browser)), \
             patch.object(cdp, "_get_all_pages", return_value=[]), \
             patch.object(cdp, "_get_or_find_page", return_value=page):
            result = cdp.cdp_open_tab("example.com", reuse_tab=False)
            assert result["ok"] is True
            # URL мав нормалізуватися до https://
            page.goto.assert_called()
            args = page.goto.call_args[0]
            assert args[0].startswith("https://")


# ─── Registration ─────────────────────────────────────────────────────────────

class TestRegistration:
    def test_all_cdp_tools_count(self):
        # 15 tools зареєстровано
        assert len(cdp.ALL_CDP_TOOLS) == 15

    def test_new_tools_in_list(self):
        names = {t.__name__ for t in cdp.ALL_CDP_TOOLS}
        assert "cdp_click_text" in names
        assert "cdp_wait_for_text" in names
        assert "cdp_fill" in names

    def test_register_to_registry(self):
        registry = MagicMock()
        cdp.register_cdp_tools(registry)
        # Має бути викликано register для кожного llm_function
        assert registry.register.call_count >= 15

    def test_tools_in_tool_policies(self):
        from functions.runtime.core_tool_runtime import TOOL_POLICIES
        assert "cdp_click_text" in TOOL_POLICIES
        assert "cdp_wait_for_text" in TOOL_POLICIES
        assert "cdp_fill" in TOOL_POLICIES

    def test_browser_aliases_resolve(self):
        from functions.planning.logic_agent_tools_schema import TOOL_NAME_ALIASES
        assert TOOL_NAME_ALIASES["browser_click_text"] == "cdp_click_text"
        assert TOOL_NAME_ALIASES["browser_fill"] == "cdp_fill"
        assert TOOL_NAME_ALIASES["browser_wait_for"] == "cdp_wait_for_text"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
