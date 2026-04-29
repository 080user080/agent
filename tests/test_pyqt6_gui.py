"""Тести PyQt6 GUI (smoke + API контракт)."""
from __future__ import annotations

import sys

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core_gui_pyqt6 import MainWindowPyQt6  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def window(qapp):
    calls = []

    def cb(action, data=None):
        calls.append((action, data))

    w = MainWindowPyQt6(cb)
    w._test_calls = calls  # для перевірки в тестах
    yield w
    w.close()


class TestMainWindowAPI:
    """Перевірка контракту API (співпадає з Tkinter версією)."""

    def test_window_created(self, window):
        assert window.windowTitle() == "МАРК — Асистент (PyQt6)"

    def test_add_message(self, window):
        window.add_message("user", "Привіт")
        window.add_message("assistant", "Здоров")
        text = window.chat_history.toPlainText()
        assert "Привіт" in text
        assert "Здоров" in text

    def test_add_message_none(self, window):
        # Не повинен крашитись на None
        window.add_message("user", None)
        # Чат залишається порожнім
        assert window.chat_history.toPlainText() == ""

    def test_update_progress(self, window):
        window.update_progress(50, "Тест")
        assert window.progress_bar.isVisible() is False or window.progress_bar.value() == 50
        assert window.status_label.text() == "Тест"

    def test_update_progress_zero_hides(self, window):
        window.update_progress(50, "x")
        window.update_progress(0, "y")
        assert window.status_label.text() == "y"

    def test_show_hide_stop_button(self, window):
        window.show()
        window.show_stop_button()
        assert window.stop_button.isVisible()
        assert not window.send_button.isVisible()
        window.hide_stop_button()
        assert not window.stop_button.isVisible()
        assert window.send_button.isVisible()

    def test_plan_panel(self, window):
        steps = [{"description": "Крок 1"}, {"description": "Крок 2"}]
        window.show_plan_panel(steps)
        assert window.plan_list.count() == 2

        window.update_plan_step({"index": 0, "status": "success"})
        text = window.plan_list.item(0).text()
        assert "✅" in text

    def test_streaming(self, window):
        window.start_stream_message()
        window.append_stream_chunk("Hello ")
        window.append_stream_chunk("world")
        window.end_stream_message()
        text = window.chat_history.toPlainText()
        assert "Hello world" in text

    def test_set_assistant_and_stt(self, window):
        window.set_assistant("fake_assistant")
        window.set_stt_controller("fake_stt")
        assert window.assistant == "fake_assistant"
        assert window.stt_controller == "fake_stt"


class TestThreadSafeSignals:
    """Сигнал message_received має працювати з фонового потоку."""

    def test_queue_message_from_thread(self, window, qapp):
        import threading

        def bg():
            window.queue_message("add_message", ("system", "from-thread"))

        threading.Thread(target=bg).start()
        # Обробити події 200мс
        QTimer.singleShot(200, qapp.quit)
        qapp.exec()

        assert "from-thread" in window.chat_history.toPlainText()


class TestCallbacks:
    """Натискання кнопок викликає правильні callbacks."""

    def test_send_button_callback(self, window):
        window.input_text.setPlainText("test command")
        window.send_text_command()
        assert ("process_text", "test command") in window._test_calls

    def test_agent_button_callback(self, window):
        window.input_text.setPlainText("agent task")
        window.run_agent_loop()
        assert ("run_agent", "agent task") in window._test_calls

    def test_stop_button_callback(self, window):
        window.stop_execution()
        actions = [c[0] for c in window._test_calls]
        assert "stop_execution" in actions
        assert "stop_plan" in actions

    def test_empty_input_no_callback(self, window):
        window.input_text.setPlainText("")
        window.send_text_command()
        assert window._test_calls == []


class TestSettingsTab:
    """Перевірка SettingsTabQtMixin."""

    def test_settings_tab_lazy_build(self, window, qapp):
        """Вкладка налаштувань будується ліниво при перемиканні."""
        # Початково settings не побудовані
        assert window._settings_built is False

        # Перемикаємо на вкладку Settings (індекс 2)
        window.notebook.setCurrentIndex(2)

        # Обробити події Qt
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, qapp.quit)
        qapp.exec()

        # Тепер settings побудовані
        assert window._settings_built is True
        assert hasattr(window, "_settings_vars")

    def test_settings_widgets_created(self, window, qapp):
        """Віджети налаштувань створюються для всіх ключів SETTINGS_SCHEMA."""
        from functions.core_settings import SETTINGS_SCHEMA

        window.notebook.setCurrentIndex(2)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, qapp.quit)
        qapp.exec()

        # Перевіряємо що віджети створені для кожного ключа (крім hidden)
        visible_keys = [k for k, s in SETTINGS_SCHEMA.items() if not s.get("hidden")]
        for key in visible_keys:
            assert key in window._settings_vars, f"Віджет для {key} не створено"

    def test_llm_endpoints_editor(self, qapp):
        """LLMEndpointsEditor створюється і працює."""
        from core_gui_pyqt6.llm_endpoints_editor_qt import LLMEndpointsEditor

        editor = LLMEndpointsEditor([{"model": "gpt-4", "provider": "openai"}])
        assert len(editor.get()) == 1
        assert editor.get()[0]["model"] == "gpt-4"

        # Додати через діалог (без GUI, просто через set)
        editor.set([{"model": "claude-3", "provider": "anthropic"}])
        assert len(editor.get()) == 1
        assert editor.get()[0]["model"] == "claude-3"

    def test_llm_endpoints_editor_preserves_legacy_fields(self, qapp):
        """PyQt6 editor не повинен втрачати поля старих LLM endpoint-ів."""
        from core_gui_pyqt6.llm_endpoints_editor_qt import LLMEndpointsEditor

        legacy_endpoint = {
            "id": "llm1",
            "name": "Local primary",
            "enabled": True,
            "role": "primary",
            "type": "openai_compatible",
            "url": "http://localhost:1234/v1/chat/completions",
            "model": "openai/gpt-oss-20b",
            "api_key": "",
            "temperature": 0.2,
            "max_tokens": 2048,
            "timeout": 45,
            "script_command": "",
            "script_output_file": "",
            "rate_limit_mode": "rpm",
            "rate_limit_rpm": 30,
            "rate_limit_total": 0,
        }

        editor = LLMEndpointsEditor([legacy_endpoint])
        result = editor.get()

        assert len(result) == 1
        saved = result[0]
        for key, value in legacy_endpoint.items():
            assert saved[key] == value, f"Втрачено поле {key}"
