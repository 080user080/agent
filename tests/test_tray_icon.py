"""Тести для tray icon — Phase V11."""
import pytest
from unittest.mock import Mock, patch

from core_gui.tray_icon import TrayIcon, create_tray_icon


class TestTrayIcon:
    """Тести для TrayIcon."""

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", False)
    def test_tray_icon_not_available(self):
        """Tray icon коли pystray не встановлено."""
        icon = create_tray_icon()
        assert icon is None

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", True)
    def test_tray_icon_creation(self):
        """Створення tray icon."""
        on_show = Mock()
        on_quit = Mock()
        icon = TrayIcon(on_show, on_quit)

        assert icon.on_show == on_show
        assert icon.on_quit == on_quit
        assert icon.icon is None

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", True)
    def test_create_icon_image(self):
        """Створення іконки."""
        icon = TrayIcon()
        image = icon.create_icon_image()

        assert image is not None
        assert image.size == (64, 64)

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", True)
    def test_on_clicked(self):
        """Обробник кліку на іконку."""
        on_show = Mock()
        icon = TrayIcon(on_show=on_show)
        icon.on_clicked(None, None)

        on_show.assert_called_once()

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", True)
    def test_on_quit_clicked(self):
        """Обробник кліку на Quit."""
        on_quit = Mock()
        icon = TrayIcon(on_quit=on_quit)
        mock_icon = Mock()
        icon.on_quit_clicked(mock_icon, None)

        on_quit.assert_called_once()
        mock_icon.stop.assert_called_once()

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", False)
    def test_run_without_pystray(self):
        """Запуск без pystray."""
        icon = TrayIcon()
        icon.run()

        # Не повинен падати, просто повертає
        assert icon.icon is None

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", True)
    def test_stop_without_icon(self):
        """Зупинка без іконки."""
        icon = TrayIcon()
        icon.stop()

        # Не повинен падати
        assert icon.icon is None


class TestCreateTrayIcon:
    """Тести для create_tray_icon."""

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", False)
    def test_create_tray_icon_not_available(self):
        """Створення tray icon коли pystray не встановлено."""
        icon = create_tray_icon()
        assert icon is None

    @patch("core_gui.tray_icon.PYSTRAY_AVAILABLE", True)
    def test_create_tray_icon_available(self):
        """Створення tray icon коли pystray встановлено."""
        on_show = Mock()
        on_quit = Mock()
        icon = create_tray_icon(on_show, on_quit)

        assert icon is not None
        assert icon.on_show == on_show
        assert icon.on_quit == on_quit
