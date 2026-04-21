"""Тести для functions/conditions_windows.py.

Тести 100% Linux-friendly: всі lister-функції ін'єктуються, pygetwindow
та psutil не викликаються.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.conditions_windows import (  # noqa: E402
    condition_chat_idle,
    condition_process_finished,
    condition_process_running,
    condition_window_title_contains,
)


# ---------------------------------------------------------------------------
# condition_window_title_contains
# ---------------------------------------------------------------------------


class TestWindowTitle:
    def test_matches_substring_case_insensitive_by_default(self):
        lister = lambda: ["Notepad - Untitled", "Chrome - GitHub"]
        cond = condition_window_title_contains(
            "github", window_lister=lister
        )
        assert cond({}) is True

    def test_returns_false_when_no_match(self):
        lister = lambda: ["Notepad - Untitled"]
        cond = condition_window_title_contains(
            "windsurf", window_lister=lister
        )
        assert cond({}) is False

    def test_case_sensitive_mode(self):
        lister = lambda: ["Chrome - GitHub"]
        cond = condition_window_title_contains(
            "github", case_insensitive=False, window_lister=lister
        )
        assert cond({}) is False
        cond2 = condition_window_title_contains(
            "GitHub", case_insensitive=False, window_lister=lister
        )
        assert cond2({}) is True

    def test_empty_list_is_false(self):
        cond = condition_window_title_contains(
            "any", window_lister=lambda: []
        )
        assert cond({}) is False

    def test_lister_called_every_check(self):
        call_count = [0]

        def lister():
            call_count[0] += 1
            return ["Chrome"]

        cond = condition_window_title_contains(
            "chrome", window_lister=lister
        )
        cond({})
        cond({})
        cond({})
        assert call_count[0] == 3

    def test_dynamic_appearance(self):
        titles_state = [[]]

        def lister():
            return list(titles_state[0])

        cond = condition_window_title_contains(
            "dialog", window_lister=lister
        )
        assert cond({}) is False
        titles_state[0] = ["Important Dialog"]
        assert cond({}) is True
        titles_state[0] = []
        assert cond({}) is False


# ---------------------------------------------------------------------------
# condition_process_running
# ---------------------------------------------------------------------------


class TestProcessRunning:
    def test_matches_name_substring(self):
        lister = lambda: [
            {"pid": 1, "name": "explorer.exe"},
            {"pid": 200, "name": "notepad.exe"},
        ]
        cond = condition_process_running("notepad", process_lister=lister)
        assert cond({}) is True

    def test_case_insensitive_by_default(self):
        lister = lambda: [{"pid": 1, "name": "Notepad.exe"}]
        cond = condition_process_running("notepad", process_lister=lister)
        assert cond({}) is True

    def test_returns_false_when_no_match(self):
        lister = lambda: [{"pid": 1, "name": "explorer.exe"}]
        cond = condition_process_running("windsurf", process_lister=lister)
        assert cond({}) is False

    def test_matches_pid(self):
        lister = lambda: [
            {"pid": 42, "name": "python.exe"},
            {"pid": 100, "name": "other.exe"},
        ]
        cond = condition_process_running(42, process_lister=lister)
        assert cond({}) is True

    def test_pid_not_found(self):
        lister = lambda: [{"pid": 1, "name": "x"}]
        cond = condition_process_running(999, process_lister=lister)
        assert cond({}) is False

    def test_missing_name_field_safe(self):
        lister = lambda: [{"pid": 1, "name": None}]
        cond = condition_process_running("anything", process_lister=lister)
        assert cond({}) is False


# ---------------------------------------------------------------------------
# condition_process_finished
# ---------------------------------------------------------------------------


class TestProcessFinished:
    def test_not_firing_if_process_never_seen(self):
        lister = lambda: [{"pid": 1, "name": "other.exe"}]
        cond = condition_process_finished("notepad", process_lister=lister)
        # кілька викликів — процесу нема → вірно НЕ спрацьовує
        assert cond({}) is False
        assert cond({}) is False
        assert cond({}) is False

    def test_fires_once_after_process_disappears(self):
        state = [[{"pid": 1, "name": "notepad.exe"}]]

        def lister():
            return list(state[0])

        cond = condition_process_finished("notepad", process_lister=lister)
        # 1) процес живий
        assert cond({}) is False
        # 2) процес зник — condition має спрацювати
        state[0] = []
        assert cond({}) is True
        # 3) повторно — вже не спрацьовує (one-shot)
        assert cond({}) is False

    def test_survives_multiple_running_ticks(self):
        state = [[{"pid": 1, "name": "long.exe"}]]

        def lister():
            return list(state[0])

        cond = condition_process_finished("long", process_lister=lister)
        for _ in range(5):
            assert cond({}) is False  # ще живий
        state[0] = []
        assert cond({}) is True

    def test_accepts_pid(self):
        state = [[{"pid": 99, "name": "x"}]]

        def lister():
            return list(state[0])

        cond = condition_process_finished(99, process_lister=lister)
        assert cond({}) is False
        state[0] = []
        assert cond({}) is True


# ---------------------------------------------------------------------------
# condition_chat_idle
# ---------------------------------------------------------------------------


class TestChatIdle:
    def test_triggers_after_idle_period(self):
        clock = [100.0]
        snapshot = ["v1"]
        cond = condition_chat_idle(
            activity_fn=lambda: snapshot[0],
            idle_seconds=5.0,
            time_fn=lambda: clock[0],
        )
        # 1-й виклик — записує baseline
        assert cond({}) is False
        # ще 3 секунди — не досить
        clock[0] = 103.0
        assert cond({}) is False
        # 6 секунд — досить
        clock[0] = 106.0
        assert cond({}) is True

    def test_resets_on_activity(self):
        clock = [0.0]
        snapshot = ["a"]
        cond = condition_chat_idle(
            activity_fn=lambda: snapshot[0],
            idle_seconds=5.0,
            time_fn=lambda: clock[0],
        )
        cond({})
        clock[0] = 3.0
        snapshot[0] = "b"  # активність є — скидаємо
        assert cond({}) is False
        clock[0] = 7.0
        # з моменту зміни минуло 4 с — не idle
        assert cond({}) is False
        clock[0] = 9.0
        # з моменту зміни минуло 6 с — idle
        assert cond({}) is True

    def test_fires_once_per_idle_period(self):
        clock = [0.0]
        snapshot = ["x"]
        cond = condition_chat_idle(
            activity_fn=lambda: snapshot[0],
            idle_seconds=2.0,
            time_fn=lambda: clock[0],
        )
        cond({})
        clock[0] = 3.0
        assert cond({}) is True
        # якщо знову спитати без змін — вже не спрацює
        assert cond({}) is False
        clock[0] = 10.0
        assert cond({}) is False
        # нова активність → condition готова спрацювати знову
        snapshot[0] = "y"
        clock[0] = 11.0
        assert cond({}) is False
        clock[0] = 14.0
        assert cond({}) is True

    def test_exception_in_activity_fn_is_handled(self):
        def boom():
            raise RuntimeError("cannot read chat")

        cond = condition_chat_idle(
            activity_fn=boom,
            idle_seconds=1.0,
            time_fn=lambda: 0.0,
        )
        assert cond({}) is False
        assert cond({}) is False

    def test_none_values_are_compared(self):
        clock = [0.0]
        snapshot = [None]
        cond = condition_chat_idle(
            activity_fn=lambda: snapshot[0],
            idle_seconds=2.0,
            time_fn=lambda: clock[0],
        )
        cond({})
        clock[0] = 3.0
        # None == None → idle → спрацьовує
        assert cond({}) is True
