"""Тести для tools_windsurf (Phase 12.5)."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from functions import tools_windsurf as tw


# ---------------------------------------------------------------------------
# normalize / hash / diff
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_empty_text(self):
        assert tw.normalize_text("") == ""

    def test_collapses_whitespace(self):
        assert tw.normalize_text("hello\n\n  world\t\t!") == "hello world !"

    def test_strips_leading_trailing(self):
        assert tw.normalize_text("   foo bar   ") == "foo bar"

    def test_removes_cursor_markers(self):
        assert tw.normalize_text("hello▌") == "hello"
        assert tw.normalize_text("foo█bar▎baz") == "foobarbaz"

    def test_cursor_blink_same_hash(self):
        """Дві версії тексту з різним cursor-блінком мають ОДНАКОВИЙ хеш."""
        h1 = tw.compute_text_hash("Hello world▌")
        h2 = tw.compute_text_hash("Hello world█")
        h3 = tw.compute_text_hash("Hello world")
        assert h1 == h2 == h3


class TestDiff:
    def test_same_text_not_changed(self):
        d = tw.diff_snapshots("hello", "hello")
        assert d.changed is False
        assert d.new_text == ""
        assert d.previous_hash == d.current_hash

    def test_append_tail_returns_diff(self):
        d = tw.diff_snapshots("User: hi", "User: hi  Bot: hello!")
        assert d.changed is True
        assert d.new_text == "Bot: hello!"

    def test_completely_different_returns_full_current(self):
        d = tw.diff_snapshots("old content", "totally different stuff")
        assert d.changed is True
        assert d.new_text == "totally different stuff"

    def test_empty_previous_returns_full_current(self):
        d = tw.diff_snapshots("", "fresh response")
        assert d.changed is True
        assert d.new_text == "fresh response"


# ---------------------------------------------------------------------------
# find_windsurf_window
# ---------------------------------------------------------------------------


class TestFindWindow:
    def _windows(self, *entries: Dict[str, Any]) -> List[Dict[str, Any]]:
        return list(entries)

    def test_returns_none_when_empty(self):
        assert tw.find_windsurf_window(window_lister=lambda: []) is None

    def test_matches_by_title_substring(self):
        win = tw.find_windsurf_window(
            window_lister=lambda: self._windows(
                {"hwnd": 1, "title": "Chrome", "process_name": "chrome.exe"},
                {"hwnd": 42, "title": "Project — Windsurf", "process_name": "electron.exe"},
            )
        )
        assert win is not None
        assert win["hwnd"] == 42

    def test_matches_by_process_name(self):
        win = tw.find_windsurf_window(
            window_lister=lambda: self._windows(
                {"hwnd": 7, "title": "Untitled", "process_name": "Windsurf.exe"},
            )
        )
        assert win is not None
        assert win["hwnd"] == 7

    def test_custom_patterns(self):
        win = tw.find_windsurf_window(
            title_patterns=["codex-ide"],
            window_lister=lambda: self._windows(
                {"hwnd": 99, "title": "my codex-ide project", "process_name": "app"},
            ),
        )
        assert win is not None
        assert win["hwnd"] == 99

    def test_lister_exception_returns_none(self):
        def bad_lister():
            raise RuntimeError("boom")

        assert tw.find_windsurf_window(window_lister=bad_lister) is None

    def test_case_insensitive(self):
        win = tw.find_windsurf_window(
            window_lister=lambda: self._windows(
                {"hwnd": 5, "title": "WINDSURF - Editor", "process_name": "App"},
            )
        )
        assert win is not None
        assert win["hwnd"] == 5

    def test_returns_copy_not_reference(self):
        shared = {"hwnd": 1, "title": "Windsurf", "process_name": "x"}
        win = tw.find_windsurf_window(window_lister=lambda: [shared])
        assert win is not None
        win["hwnd"] = 999
        assert shared["hwnd"] == 1  # original not mutated


# ---------------------------------------------------------------------------
# snapshot_fn
# ---------------------------------------------------------------------------


class TestSnapshotFn:
    def test_default_snapshot_with_ok_ocr(self):
        calls: List[int] = []

        def fake_ocr(hwnd: int) -> Dict[str, Any]:
            calls.append(hwnd)
            return {"text": "User: hello\n\nBot: hi   ▌", "ok": True}

        snap = tw.make_default_snapshot_fn(ocr_window_fn=fake_ocr)
        text = snap({"hwnd": 42})
        assert text == "User: hello Bot: hi"
        assert calls == [42]

    def test_snapshot_ocr_failure_returns_empty(self):
        def fake_ocr(hwnd: int) -> Dict[str, Any]:
            return {"text": "", "ok": False}

        snap = tw.make_default_snapshot_fn(ocr_window_fn=fake_ocr)
        assert snap({"hwnd": 1}) == ""

    def test_snapshot_ocr_exception_returns_empty(self):
        def bad_ocr(hwnd: int) -> Dict[str, Any]:
            raise RuntimeError("ocr-unavailable")

        # make_default_snapshot_fn ловить виняток ззовні? — Ні, voting на
        # правилах дефолтного адаптера (_default_ocr_window робить wrap),
        # але через inject ми bypass-им це. Для user-facing snapshot-fn
        # очікуємо, що обгортка ззовні.
        snap = tw.make_default_snapshot_fn(ocr_window_fn=bad_ocr)
        with pytest.raises(RuntimeError):
            snap({"hwnd": 1})

    def test_snapshot_missing_hwnd_returns_empty(self):
        def fake_ocr(hwnd: int) -> Dict[str, Any]:
            return {"text": "ignored"}

        snap = tw.make_default_snapshot_fn(ocr_window_fn=fake_ocr)
        assert snap({"title": "no hwnd"}) == ""


# ---------------------------------------------------------------------------
# WindsurfState
# ---------------------------------------------------------------------------


class TestWindsurfState:
    def test_register_response_increments_counter(self):
        st = tw.WindsurfState()
        diff = tw.diff_snapshots("", "new response text")
        entry = st.register_response(at=100.0, diff=diff)
        assert st.responses_captured == 1
        assert st.last_response_hash == diff.current_hash
        assert entry["text"] == "new response text"
        assert entry["at"] == 100.0

    def test_register_response_trims_buffer(self):
        st = tw.WindsurfState()
        for i in range(10):
            diff = tw.diff_snapshots("", f"resp-{i}")
            st.register_response(at=float(i), diff=diff, max_keep=3)
        assert st.responses_captured == 10
        assert len(st.responses) == 3
        assert st.responses[-1]["text"] == "resp-9"
        assert st.responses[0]["text"] == "resp-7"
