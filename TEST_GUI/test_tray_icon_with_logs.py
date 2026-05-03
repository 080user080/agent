"""Тест Tray Icon з логуванням в файл."""
import sys
import os
from pathlib import Path

# Додати кореневу директорію в path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Налаштування логування в файл
log_file = Path(__file__).parent / "tray_icon_test.log"
log_file.unlink(missing_ok=True)

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

print(f"Логи будуть записані в: {log_file}")
print("=" * 60)

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer, QCoreApplication
    from functions.voice_tray_icon import VoiceTrayIcon, VoiceStatus

    # Створити QApplication
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    # Створити tray icon
    tray = VoiceTrayIcon()
    logger.info("VoiceTrayIcon створено")

    # Ініціалізувати
    result = tray.initialize()
    logger.info(f"initialize() повернув: {result}")

    if not result:
        logger.error("Не вдалося ініціалізувати tray icon")
        sys.exit(1)

    # Тест зміни статусів
    def test_status_changes():
        logger.info("Початок тесту зміни статусів")
        
        statuses = [
            (VoiceStatus.IDLE, "Готовий"),
            (VoiceStatus.RECORDING, "Запис..."),
            (VoiceStatus.PROCESSING, "Розпізнавання..."),
            (VoiceStatus.ERROR, "Помилка"),
            (VoiceStatus.NO_MIC, "Немає мікрофона"),
            (VoiceStatus.IDLE, "Готовий"),
        ]
        
        for i, (status, text) in enumerate(statuses):
            logger.info(f"Встановлення статусу {i+1}/{len(statuses)}: {status} - {text}")
            tray.set_status(status, text)
            QCoreApplication.processEvents()
            QTimer.singleShot(500, lambda: None)  # Чекати 0.5 сек
            QCoreApplication.processEvents()
            logger.info(f"Статус встановлено: {tray.current_status}")
        
        logger.info("Тест зміни статусів завершено")
        logger.info(f"Логи записані в: {log_file}")
        app.quit()

    # Запустити тест через QTimer щоб Qt event loop міг обробити події
    QTimer.singleShot(100, test_status_changes)

    # Запустити Qt event loop
    app.exec()

except ImportError as e:
    logger.error(f"PyQt6 не доступний: {e}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Помилка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
