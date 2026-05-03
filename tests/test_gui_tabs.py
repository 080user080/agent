"""Тести для GUI компонентів вкладок."""
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Створити QApplication для тестів
@pytest.fixture(scope="module")
def app():
    """PyQt6 QApplication для тестів."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def chat_tab(app):
    """Створити вкладку чату для тестів."""
    from gui_tabs.chat_tab import ChatTab
    tab = ChatTab()
    yield tab
    tab.close()


@pytest.fixture
def settings_tab(app):
    """Створити вкладку налаштувань для тестів."""
    from gui_tabs.settings_tab import SettingsTab
    tab = SettingsTab()
    yield tab
    tab.close()


@pytest.fixture
def logs_tab(app):
    """Створити вкладку логів для тестів."""
    from gui_tabs.logs_tab import LogsTab
    tab = LogsTab()
    yield tab
    tab.close()


@pytest.fixture
def statistics_tab(app):
    """Створити вкладку статистики для тестів."""
    from gui_tabs.statistics_tab import StatisticsTab
    tab = StatisticsTab()
    yield tab
    tab.close()


@pytest.fixture
def about_tab(app):
    """Створити вкладку про програму для тестів."""
    from gui_tabs.about_tab import AboutTab
    tab = AboutTab()
    yield tab
    tab.close()


@pytest.fixture
def tools_tab(app):
    """Створити вкладку інструментів для тестів."""
    from gui_tabs.tools_tab import ToolsTab
    tab = ToolsTab()
    yield tab
    tab.close()


class TestChatTab:
    """Тести для вкладки чату."""

    def test_initialization(self, chat_tab):
        """Перевірити ініціалізацію вкладки чату."""
        assert chat_tab.chat_history is not None
        assert chat_tab.message_input is not None
        assert chat_tab.send_button is not None
        assert chat_tab.chat_history.isReadOnly()

    def test_send_message(self, chat_tab):
        """Перевірити відправку повідомлення."""
        chat_tab.message_input.setText("Тестове повідомлення")
        chat_tab.send_message()

        # Повідомлення має бути додано в історію
        assert chat_tab.message_input.text() == ""
        # Перевірити, що історія не порожня (системне повідомлення + user)
        assert chat_tab.chat_history.toPlainText() != ""

    def test_quick_command(self, chat_tab):
        """Перевірити швидкі команди."""
        from gui_tabs.constants import QUICK_COMMANDS
        chat_tab.quick_command(QUICK_COMMANDS[0])
        assert chat_tab.message_input.text() == ""

    def test_add_message(self, chat_tab):
        """Перевірити додавання повідомлення."""
        initial_text = chat_tab.chat_history.toPlainText()
        chat_tab.add_message("user", "Тест")
        new_text = chat_tab.chat_history.toPlainText()
        assert len(new_text) > len(initial_text)


class TestSettingsTab:
    """Тести для вкладки налаштувань."""

    def test_initialization(self, settings_tab):
        """Перевірити ініціалізацію вкладки налаштувань."""
        assert settings_tab.language_combo is not None
        assert settings_tab.theme_combo is not None
        assert settings_tab.auto_save is not None
        assert settings_tab.model_combo is not None
        assert settings_tab.temperature_spin is not None
        assert settings_tab.max_tokens_spin is not None
        assert settings_tab.stream_response is not None
        assert settings_tab.max_steps_spin is not None
        assert settings_tab.max_time_spin is not None
        assert settings_tab.enable_ocr is not None
        assert settings_tab.enable_vision is not None
        assert settings_tab.save_button is not None
        assert settings_tab.reset_button is not None

    def test_default_values(self, settings_tab):
        """Перевірити значення за замовчуванням."""
        from gui_tabs.constants import SettingsDefaults
        assert settings_tab.language_combo.currentIndex() == SettingsDefaults.language_index
        assert settings_tab.theme_combo.currentIndex() == SettingsDefaults.theme_index
        assert settings_tab.auto_save.isChecked() == SettingsDefaults.auto_save
        assert settings_tab.model_combo.currentIndex() == SettingsDefaults.model_index
        assert settings_tab.temperature_spin.value() == SettingsDefaults.temperature
        assert settings_tab.max_tokens_spin.value() == SettingsDefaults.max_tokens
        assert settings_tab.stream_response.isChecked() == SettingsDefaults.stream_response
        assert settings_tab.max_steps_spin.value() == SettingsDefaults.max_steps
        assert settings_tab.max_time_spin.value() == SettingsDefaults.max_time
        assert settings_tab.enable_ocr.isChecked() == SettingsDefaults.enable_ocr
        assert settings_tab.enable_vision.isChecked() == SettingsDefaults.enable_vision

    def test_reset_settings(self, settings_tab):
        """Перевірити скидання налаштувань."""
        from gui_tabs.constants import SettingsDefaults
        # Змінити значення
        settings_tab.language_combo.setCurrentIndex(1)
        settings_tab.temperature_spin.setValue(50)
        settings_tab.enable_ocr.setChecked(False)

        # Скинути
        settings_tab.reset_settings()

        # Перевірити, що значення повернулися до дефолтних
        assert settings_tab.language_combo.currentIndex() == SettingsDefaults.language_index
        assert settings_tab.temperature_spin.value() == SettingsDefaults.temperature
        assert settings_tab.enable_ocr.isChecked() == SettingsDefaults.enable_ocr


class TestLogsTab:
    """Тести для вкладки логів."""

    def test_initialization(self, logs_tab):
        """Перевірити ініціалізацію вкладки логів."""
        assert logs_tab.level_combo is not None
        assert logs_tab.search_input is not None
        assert logs_tab.clear_button is not None
        assert logs_tab.logs_table is not None

    def test_test_logs_added(self, logs_tab):
        """Перевірити, що тестові логи додані."""
        from gui_tabs.constants import TEST_LOGS
        assert logs_tab.logs_table.rowCount() == len(TEST_LOGS)

    def test_add_log(self, logs_tab):
        """Перевірити додавання логу."""
        initial_count = logs_tab.logs_table.rowCount()
        logs_tab.add_log("INFO", "test_module", "Test message")
        assert logs_tab.logs_table.rowCount() == initial_count + 1

    def test_clear_logs(self, logs_tab):
        """Перевірити очищення логів."""
        logs_tab.clear_logs()
        assert logs_tab.logs_table.rowCount() == 0


class TestStatisticsTab:
    """Тести для вкладки статистики."""

    def test_initialization(self, statistics_tab):
        """Перевірити ініціалізацію вкладки статистики."""
        assert statistics_tab.total_requests_label is not None
        assert statistics_tab.tokens_label is not None
        assert statistics_tab.avg_time_label is not None
        assert statistics_tab.success_label is not None
        assert statistics_tab.failed_label is not None
        assert statistics_tab.avg_steps_label is not None
        assert statistics_tab.quota_progress is not None
        assert statistics_tab.refresh_button is not None

    def test_refresh_statistics(self, statistics_tab):
        """Перевірити оновлення статистики."""
        statistics_tab.refresh_statistics()
        # Перевірити, що значення оновилися (не "0")
        assert statistics_tab.total_requests_label.text() != "0"
        assert statistics_tab.tokens_label.text() != "0"


class TestAboutTab:
    """Тести для вкладки про програму."""

    def test_initialization(self, about_tab):
        """Перевірити ініціалізацію вкладки про програму."""
        # Вкладка має бути створена без помилок
        assert about_tab is not None


class TestToolsTab:
    """Тести для вкладки інструментів."""

    def test_initialization(self, tools_tab):
        """Перевірити ініціалізацію вкладки інструментів."""
        assert tools_tab.tools_table is not None
        assert tools_tab.execute_button is not None

    def test_test_tools_added(self, tools_tab):
        """Перевірити, що тестові інструменти додані."""
        from gui_tabs.constants import TEST_TOOLS
        assert tools_tab.tools_table.rowCount() == len(TEST_TOOLS)

    def test_execute_tool(self, tools_tab, capsys):
        """Перевірити виконання інструменту."""
        # Вибрати перший інструмент
        tools_tab.tools_table.selectRow(0)
        tools_tab.execute_tool()

        # Перевірити вивід в консоль
        captured = capsys.readouterr()
        assert "Виконання інструменту" in captured.out


class TestMainWindow:
    """Тести для головного вікна."""

    @pytest.fixture
    def main_window(self, app):
        """Створити головне вікно для тестів."""
        from gui_tabs.main_window import MultiTabGUI
        window = MultiTabGUI()
        yield window
        window.close()

    def test_initialization(self, main_window):
        """Перевірити ініціалізацію головного вікна."""
        assert main_window.tabs is not None
        assert main_window.status_timer is not None
        assert main_window.tabs.count() == 6  # 6 вкладок

    def test_tab_names(self, main_window):
        """Перевірити назви вкладок."""
        from gui_tabs.constants import TAB_NAMES
        expected_names = list(TAB_NAMES.values())
        for i, expected in enumerate(expected_names):
            assert main_window.tabs.tabText(i) == expected

    def test_tabs_movable(self, main_window):
        """Перевірити, що вкладки можна переміщувати."""
        assert main_window.tabs.isMovable()

    def test_status_bar(self, main_window):
        """Перевірити статус бар."""
        from gui_tabs.constants import APP_VERSION
        assert main_window.statusBar() is not None
        assert APP_VERSION in main_window.statusBar().currentMessage()


class TestConstants:
    """Тести для констант."""

    def test_role_colors(self):
        """Перевірити кольори ролей."""
        from gui_tabs.constants import ROLE_COLORS
        assert "user" in ROLE_COLORS
        assert "assistant" in ROLE_COLORS
        assert "system" in ROLE_COLORS

    def test_log_level_colors(self):
        """Перевірити кольори рівнів логів."""
        from gui_tabs.constants import LOG_LEVEL_COLORS
        assert "INFO" in LOG_LEVEL_COLORS
        assert "WARNING" in LOG_LEVEL_COLORS
        assert "ERROR" in LOG_LEVEL_COLORS
        assert "DEBUG" in LOG_LEVEL_COLORS

    def test_settings_defaults(self):
        """Перевірити дефолтні налаштування."""
        from gui_tabs.constants import SettingsDefaults
        assert SettingsDefaults.temperature == 70
        assert SettingsDefaults.max_tokens == 2000
        assert SettingsDefaults.max_steps == 10
        assert SettingsDefaults.enable_ocr is True
        assert SettingsDefaults.enable_vision is False

    def test_tab_names(self):
        """Перевірити назви вкладок."""
        from gui_tabs.constants import TAB_NAMES
        assert "chat" in TAB_NAMES
        assert "settings" in TAB_NAMES
        assert "logs" in TAB_NAMES
        assert "statistics" in TAB_NAMES
        assert "about" in TAB_NAMES
        assert "tools" in TAB_NAMES
