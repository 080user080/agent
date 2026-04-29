"""Tray icon для глобального керування агентом."""
import threading
from typing import Optional, Callable, TYPE_CHECKING

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

if TYPE_CHECKING:
    from PIL import Image


class TrayIcon:
    """Tray icon для агента."""

    def __init__(self, on_show: Optional[Callable] = None, on_quit: Optional[Callable] = None):
        """
        Ініціалізувати tray icon.

        Args:
            on_show: Callback для показу GUI
            on_quit: Callback для виходу
        """
        self.on_show = on_show
        self.on_quit = on_quit
        self.icon = None
        self._thread = None

    def create_icon_image(self):
        """Створити іконку для tray."""
        if not PYSTRAY_AVAILABLE:
            return None
        # Створюємо просту іконку
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (64, 64), color=(0, 100, 200))
        draw = ImageDraw.Draw(image)
        draw.text((10, 20), "AI", fill=(255, 255, 255))
        return image

    def on_clicked(self, icon, item):
        """Обробник кліку на іконку."""
        if self.on_show:
            self.on_show()

    def on_quit_clicked(self, icon, item):
        """Обробник кліку на Quit."""
        if self.on_quit:
            self.on_quit()
        icon.stop()

    def run(self):
        """Запустити tray icon в окремому потоці."""
        if not PYSTRAY_AVAILABLE:
            print("pystray не встановлено, tray icon недоступний")
            return

        if self.icon is not None:
            return  # Уже запущено

        import pystray

        icon_image = self.create_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Показати", self.on_clicked),
            pystray.MenuItem("Вихід", self.on_quit_clicked),
        )

        self.icon = pystray.Icon("Agent", icon_image, menu=menu)

        def _run_icon():
            self.icon.run()

        self._thread = threading.Thread(target=_run_icon, daemon=True)
        self._thread.start()

    def stop(self):
        """Зупинити tray icon."""
        if self.icon:
            self.icon.stop()
            self.icon = None
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None


def create_tray_icon(on_show: Optional[Callable] = None, on_quit: Optional[Callable] = None) -> Optional[TrayIcon]:
    """Створити tray icon."""
    if not PYSTRAY_AVAILABLE:
        return None
    return TrayIcon(on_show, on_quit)
