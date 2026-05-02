"""Tray Icon для Global Voice Input - показує статус запису біля годинника."""
from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Optional

try:
    from PyQt6.QtWidgets import QSystemTrayIcon, QApplication
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
    from PyQt6.QtCore import Qt, QObject, pyqtSignal
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


class VoiceStatus(Enum):
    """Статус голосового введення."""
    IDLE = "idle"  # Синій - готовий
    RECORDING = "recording"  # Червоний - запис
    PROCESSING = "processing"  # Жовтий/помаранчевий - розпізнавання
    ERROR = "error"  # Сірий - помилка
    NO_MIC = "no_mic"  # Чорний - немає доступу до мікрофона


class _TrayStatusData:
    """Дані для оновлення статусу."""
    def __init__(self, status: VoiceStatus, text: str):
        self.status = status
        self.text = text


class VoiceTrayIcon(QObject):
    """Tray icon для показу статусу голосового введення."""

    # Сигнал для потокобезпечного оновлення (з будь-якого потоку)
    _update_requested = pyqtSignal(VoiceStatus, str)
    status_changed = pyqtSignal(str)  # Сигнал зміни статусу

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.current_status = VoiceStatus.IDLE
        self.app: Optional[QApplication] = None
        self._event_loop_thread: Optional[threading.Thread] = None
        self._should_run = False
        # Підключити сигнал до слота з QueuedConnection для міжпотокової безпеки
        self._update_requested.connect(self._do_set_status, Qt.ConnectionType.QueuedConnection)

    def initialize(self) -> bool:
        """Ініціалізувати tray icon."""
        if not PYQT6_AVAILABLE:
            print("[TrayIcon] PyQt6 не доступний - tray icon не буде показано")
            return False

        # Створити QApplication якщо не існує
        if QApplication.instance() is None:
            print("[TrayIcon] Створення QApplication...")
            self.app = QApplication([])
            self.app.setQuitOnLastWindowClosed(False)
            self._needs_own_event_loop = True
        else:
            print("[TrayIcon] Використовую існуючий QApplication")
            self.app = QApplication.instance()
            self._needs_own_event_loop = False

        self.tray_icon = QSystemTrayIcon()

        # Перевірити чи підтримується system tray
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[TrayIcon] System tray не доступний на цій системі")
            return False

        print("[TrayIcon] System tray доступний")

        # Встановити початковий статус (іконку) ПЕРЕД setVisible()
        self._do_set_status(VoiceStatus.IDLE, "")

        # Показати tray icon
        self.tray_icon.show()
        print("[TrayIcon] Tray icon показано")

        # Запустити Qt event loop в окремому потоці ТІЛЬКИ якщо створили свій QApplication
        if self._needs_own_event_loop:
            self._should_run = True
            self._event_loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._event_loop_thread.start()
            print("[TrayIcon] Qt event loop запущено в окремому потоці")
        else:
            print("[TrayIcon] Використовую існуючий Qt event loop")

        return True

    def _run_event_loop(self):
        """Запустити Qt event loop в окремому потоці."""
        if self.app:
            self._should_run = True
            while self._should_run:
                self.app.processEvents()
                time.sleep(0.01)

    def set_status(self, status: VoiceStatus, text: str = ""):
        """Встановити статус tray icon (потокобезпечно)."""
        thread_name = threading.current_thread().name
        print(f"[TrayIcon] set_status викликано з потоку {thread_name}: {status.value} - {text}")
        # Використовуємо QTimer.singleShot для оновлення в основному потоці Qt
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda s=status, t=text: self._do_set_status(s, t))
            print(f"[TrayIcon] QTimer.singleShot заплановано")
        except Exception as e:
            print(f"[TrayIcon] QTimer.singleShot не вдалося: {e}, оновлюю напряму")
            # Fallback: оновлюємо напряму якщо Qt недоступний
            self._do_set_status(status, text)

    def _do_set_status(self, status: VoiceStatus, text: str = ""):
        """Внутрішній метод - виконується в основному потоці Qt."""
        thread_name = threading.current_thread().name
        print(f"[TrayIcon] _do_set_status викликано з потоку {thread_name}: {status.value} - {text}")
        self.current_status = status

        if not self.tray_icon:
            print(f"[TrayIcon] tray_icon = None, не можу оновити статус")
            return

        # Створити іконку з кольором статусу
        icon = self._create_icon(status)

        # Встановити іконку
        self.tray_icon.setIcon(icon)

        # Встановити tooltip
        tooltip = self._get_tooltip(status, text)
        self.tray_icon.setToolTip(tooltip)

        print(f"[TrayIcon] Статус оновлено: {status.value} - {text}")

        # Відправити сигнал
        self.status_changed.emit(status.value)

    def _create_icon(self, status: VoiceStatus) -> QIcon:
        """Створити іконку мікрофона з кольором статусу."""
        # Розмір іконки
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Кольори для статусів
        colors = {
            VoiceStatus.IDLE: QColor(33, 150, 243),  # Синій
            VoiceStatus.RECORDING: QColor(244, 67, 54),  # Червоний
            VoiceStatus.PROCESSING: QColor(255, 152, 0),  # Помаранчевий
            VoiceStatus.ERROR: QColor(158, 158, 158),  # Сірий
            VoiceStatus.NO_MIC: QColor(0, 0, 0),  # Чорний
        }

        color = colors.get(status, colors[VoiceStatus.IDLE])

        # Намалювати коло з кольором статусу
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # Намалювати мікрофон (білий)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)

        # Ручка мікрофона
        mic_x = size // 2
        mic_y = size // 2 - 8
        mic_width = 16
        mic_height = 24

        # Верхня частина (овал)
        painter.drawEllipse(
            mic_x - mic_width // 2,
            mic_y,
            mic_width,
            mic_height
        )

        # Нижня частина (прямокутник)
        painter.drawRect(
            mic_x - 4,
            mic_y + mic_height,
            8,
            8
        )

        # Ніжка
        painter.drawRect(
            mic_x - 2,
            mic_y + mic_height + 8,
            4,
            6
        )

        # Основання
        painter.drawRect(
            mic_x - 8,
            mic_y + mic_height + 14,
            16,
            4
        )

        painter.end()

        return QIcon(pixmap)

    def _get_tooltip(self, status: VoiceStatus, text: str = "") -> str:
        """Отримати tooltip для статусу."""
        status_texts = {
            VoiceStatus.IDLE: "🎤 Готовий (натисніть Ctrl+Shift+G)",
            VoiceStatus.RECORDING: "🔴 Запис...",
            VoiceStatus.PROCESSING: "🔍 Розпізнавання...",
            VoiceStatus.ERROR: "❌ Помилка",
            VoiceStatus.NO_MIC: "🚫 Немає доступу до мікрофона",
        }

        tooltip = status_texts.get(status, "Голосовий ввод")
        if text:
            tooltip += f"\n{text}"
        return tooltip

    def show(self):
        """Показати tray icon."""
        if self.tray_icon:
            self.tray_icon.show()

    def hide(self):
        """Приховати tray icon."""
        if self.tray_icon:
            self.tray_icon.hide()

    def cleanup(self):
        """Очистити ресурси."""
        self._should_run = False
        if self._event_loop_thread:
            self._event_loop_thread.join(timeout=1)
            self._event_loop_thread = None
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None
        if self.app:
            self.app.quit()
            self.app = None


# Singleton
_tray_icon_instance: Optional[VoiceTrayIcon] = None


def get_voice_tray_icon() -> Optional[VoiceTrayIcon]:
    """Отримати singleton екземпляр VoiceTrayIcon."""
    global _tray_icon_instance
    if _tray_icon_instance is None:
        _tray_icon_instance = VoiceTrayIcon()
    return _tray_icon_instance
