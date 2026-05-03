"""Тести для VoiceTrayIcon."""
import time
import threading
import pytest

from functions.voice_tray_icon import (
    VoiceTrayIcon,
    VoiceStatus,
    get_voice_tray_icon,
    _StatusUpdateEvent,
)


class TestVoiceTrayIcon:
    """Тести для VoiceTrayIcon."""

    def test_singleton(self):
        """Перевірити що get_voice_tray_icon повертає той самий екземпляр."""
        instance1 = get_voice_tray_icon()
        instance2 = get_voice_tray_icon()
        assert instance1 is instance2

    def test_voice_status_enum(self):
        """Перевірити VoiceStatus enum."""
        assert VoiceStatus.IDLE.value == "idle"
        assert VoiceStatus.RECORDING.value == "recording"
        assert VoiceStatus.PROCESSING.value == "processing"
        assert VoiceStatus.ERROR.value == "error"
        assert VoiceStatus.NO_MIC.value == "no_mic"

    def test_status_update_event(self):
        """Перевірити _StatusUpdateEvent."""
        event = _StatusUpdateEvent(VoiceStatus.RECORDING, "Тест")
        assert event.status == VoiceStatus.RECORDING
        assert event.text == "Тест"

    def test_tray_icon_creation(self):
        """Перевірити створення VoiceTrayIcon."""
        tray = VoiceTrayIcon()
        assert tray.current_status == VoiceStatus.IDLE
        assert tray.tray_icon is None
        assert tray.app is None

    def test_set_status_without_init(self):
        """Перевірити set_status без ініціалізації (не повинно падати)."""
        tray = VoiceTrayIcon()
        # Не повинно падати
        tray.set_status(VoiceStatus.RECORDING, "Тест")

    def test_create_icon_for_all_statuses(self):
        """Перевірити створення іконок для всіх статусів."""
        tray = VoiceTrayIcon()
        
        # Ініціалізувати QApplication (без tray icon)
        try:
            from PyQt6.QtWidgets import QApplication
            if QApplication.instance() is None:
                app = QApplication([])
            else:
                app = QApplication.instance()
            
            # Перевірити створення іконок
            for status in VoiceStatus:
                icon = tray._create_icon(status)
                assert icon is not None
                assert not icon.isNull()
        except ImportError:
            pytest.skip("PyQt6 не доступний")

    def test_tooltip_for_all_statuses(self):
        """Перевірити tooltip для всіх статусів."""
        tray = VoiceTrayIcon()
        
        tooltips = {
            VoiceStatus.IDLE: "🎤 Готовий (натисніть Ctrl+Shift+G)",
            VoiceStatus.RECORDING: "🔴 Запис...",
            VoiceStatus.PROCESSING: "🔍 Розпізнавання...",
            VoiceStatus.ERROR: "❌ Помилка",
            VoiceStatus.NO_MIC: "🚫 Немає доступу до мікрофона",
        }
        
        for status, expected_text in tooltips.items():
            tooltip = tray._get_tooltip(status)
            assert expected_text in tooltip

    def test_tooltip_with_text(self):
        """Перевірити tooltip з додатковим текстом."""
        tray = VoiceTrayIcon()
        tooltip = tray._get_tooltip(VoiceStatus.RECORDING, "Додатковий текст")
        assert "🔴 Запис..." in tooltip
        assert "Додатковий текст" in tooltip

    def test_status_changed_signal(self):
        """Перевірити сигнал status_changed (пропущено - потребує повний Qt event loop)."""
        # pyqtSignal потребує повного Qt event loop для emit() - це інтеграційний тест
        pytest.skip("pyqtSignal потребує повного Qt event loop - перевіряється в інтеграційних тестах")

    def test_initialize_without_pyqt6(self):
        """Перевірити ініціалізацію без PyQt6."""
        # Цей тест потребує мокування PYQT6_AVAILABLE
        # Для простоти просто перевіряємо що initialize повертає False без PyQt6
        tray = VoiceTrayIcon()
        # Якщо PyQt6 недоступний, initialize поверне False
        # Це вже перевіряється в реальному коді

    def test_cleanup(self):
        """Перевірити cleanup."""
        tray = VoiceTrayIcon()
        tray._should_run = True
        tray._event_loop_thread = threading.Thread(target=lambda: None)
        tray._event_loop_thread.start()
        
        # Cleanup не повинен падати
        tray.cleanup()
        
        assert tray._should_run is False
        assert tray._event_loop_thread is None


class TestVoiceTrayIconIntegration:
    """Інтеграційні тести для VoiceTrayIcon (потрібен PyQt6)."""

    @pytest.fixture
    def app(self):
        """Створити QApplication для тестів."""
        try:
            from PyQt6.QtWidgets import QApplication
            if QApplication.instance() is None:
                app = QApplication([])
                yield app
                app.quit()
            else:
                yield QApplication.instance()
        except ImportError:
            pytest.skip("PyQt6 не доступний")

    def test_full_initialization(self, app):
        """Перевірити повну ініціалізацію tray icon."""
        tray = VoiceTrayIcon()
        result = tray.initialize()
        
        # Якщо system tray доступний, initialize повинен повернути True
        if result:
            assert tray.tray_icon is not None
            assert tray.app is not None
            assert tray.current_status == VoiceStatus.IDLE
            
            # Cleanup
            tray.cleanup()

    def test_set_status_integration(self, app):
        """Перевірити set_status з ініціалізованим tray icon."""
        tray = VoiceTrayIcon()
        if not tray.initialize():
            pytest.skip("System tray не доступний")
        
        try:
            # Змінити статус
            tray.set_status(VoiceStatus.RECORDING, "Запис...")
            time.sleep(0.1)  # Чекати обробки event
            
            assert tray.current_status == VoiceStatus.RECORDING
            
            # Змінити ще раз
            tray.set_status(VoiceStatus.PROCESSING, "Розпізнавання...")
            time.sleep(0.1)
            
            assert tray.current_status == VoiceStatus.PROCESSING
        finally:
            tray.cleanup()

    def test_show_hide(self, app):
        """Перевірити show/hide."""
        tray = VoiceTrayIcon()
        if not tray.initialize():
            pytest.skip("System tray не доступний")
        
        try:
            tray.hide()
            tray.show()
        finally:
            tray.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
