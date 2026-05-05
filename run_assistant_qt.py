"""Запуск асистента з PyQt6 GUI (основний GUI бекенд).

Архітектура: GUI у головному потоці (Qt вимагає), ядро у фоновому потоці.
Замість `queue.Queue + root.after()` (Tkinter) використовуємо Qt сигнали —
вони thread-safe і викликають слот у GUI-потоці автоматично.
"""
import os
import queue
import sys
import threading
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Завантажити user-налаштування ДО імпортів, що читають config.py
from functions.core_settings import get_settings  # noqa: E402
get_settings()

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core_gui_pyqt6 import MainWindowPyQt6  # noqa: E402
from main import AssistantCore  # noqa: E402
from functions.aaa_confirmation import set_gui_instance  # noqa: E402


def log_console(message: str) -> None:
    print(message, flush=True)


class AssistantAppQt:
    """Аналог AssistantApp для PyQt6 GUI."""

    def __init__(self):
        # gui_queue — Tkinter-сумісна черга, в яку core кладе повідомлення.
        # Окремий потік-діспетчер читає її і конвертує в Qt-сигнали через
        # gui.queue_message() (thread-safe).
        self.gui_queue: queue.Queue = queue.Queue()
        self.core: AssistantCore | None = None
        self.gui: MainWindowPyQt6 | None = None
        self.is_running = True
        self.gui_ready = threading.Event()

    # ─── Callback від GUI ─────────────────────────────────────────────────────

    def _handle_restart(self) -> None:
        """Обробка перезапуску асистента."""
        log_console("🔁 Перезавантаження агента...")
        import subprocess
        root_dir = os.path.dirname(os.path.abspath(__file__))
        run_script = os.path.join(root_dir, "run_assistant_qt.py")
        subprocess.Popen(
            [sys.executable, run_script],
            cwd=root_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
        )
        # Закрити поточне вікно
        if self.gui:
            app = QApplication.instance()
            if app:
                app.quit()

    def gui_callback(self, action: str, data=None) -> None:
        if not self.core:
            return
        
        # Mapping дій до обробників
        action_handlers = {
            'pause_listening': lambda: self.core.pause_listening(),
            'resume_listening': lambda: self.core.resume_listening(),
            'process_text': lambda: threading.Thread(
                target=self.core.process_text_command, args=(data,), daemon=True
            ).start(),
            'stop_execution': lambda: threading.Thread(
                target=self.core.stop_execution, daemon=True
            ).start(),
            'run_plan': lambda: threading.Thread(
                target=self.core.run_pending_plan, daemon=True
            ).start(),
            'run_agent': lambda: threading.Thread(
                target=self.core.run_agent_loop, args=(data,), daemon=True
            ).start(),
            'stop_plan': lambda: self.core.stop_plan_execution(),
            'start_windsurf_watch': lambda: self.core.start_windsurf_watch(),
            'stop_windsurf_watch': lambda: self.core.stop_windsurf_watch(),
            'restart': lambda: self._handle_restart(),
        }
        
        handler = action_handlers.get(action)
        if handler:
            handler()

    # ─── Диспетчер: gui_queue → Qt signal ─────────────────────────────────────

    def queue_dispatcher(self) -> None:
        """Читає gui_queue та конвертує повідомлення в Qt-сигнали (thread-safe).

        Виконується у фоновому потоці. Pyqt6 сигнали з не-GUI потоку автоматично
        ставляться в чергу подій GUI-потоку.
        """
        while self.is_running:
            try:
                msg_type, data = self.gui_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if not self.gui:
                continue
            try:
                self.gui.queue_message(msg_type, data)
            except Exception as e:
                log_console(f"[QUEUE-DISPATCH] помилка {msg_type}: {e}")

    # ─── Ядро у фоновому потоці ───────────────────────────────────────────────

    def run_core_in_thread(self) -> None:
        try:
            log_console("🔧 Ініціалізація ядра асистента (PyQt6)...")
            self.gui_ready.wait(timeout=10)
            time.sleep(0.3)

            self.core = AssistantCore(gui_queue=self.gui_queue)
            if not self.core.initialize_without_listener():
                log_console("❌ Помилка ініціалізації ядра")
                if self.gui:
                    self.gui.queue_message(
                        'add_message',
                        ('assistant', '❌ Помилка ініціалізації. Перевірте консоль.'),
                    )
                return

            log_console("✅ Ядро готове. Очікую команди через GUI (PyQt6)...")
            if self.gui:
                self.gui.queue_message('update_status', '✅ Готовий до роботи')

                pending_stt = getattr(self.core, '_pending_stt_controller', None)
                if pending_stt:
                    try:
                        self.gui.set_stt_controller(pending_stt)
                        log_console("✅ STT контролер передано в GUI")
                    except Exception as e:
                        log_console(f"⚠️ Не вдалося передати STT: {e}")

            while self.is_running:
                time.sleep(0.5)

        except Exception as e:
            log_console(f"❌ Критична помилка ядра: {e}")
            import traceback
            traceback.print_exc()
            if self.gui:
                self.gui.queue_message('add_message', ('assistant', f'❌ Помилка: {e}'))

    # ─── Запуск ───────────────────────────────────────────────────────────────

    def start(self) -> None:
        log_console("🚀 Запуск асистента МАРК з PyQt6 GUI...")

        # Ядро у фоновому потоці
        threading.Thread(target=self.run_core_in_thread, daemon=True).start()

        # Диспетчер gui_queue → Qt-сигнал у фоновому потоці
        threading.Thread(target=self.queue_dispatcher, daemon=True).start()

        # GUI у головному потоці (Qt вимагає)
        app = QApplication.instance() or QApplication(sys.argv)
        self.gui = MainWindowPyQt6(self.gui_callback)
        set_gui_instance(self.gui)
        self.gui_ready.set()
        self.gui.show()

        try:
            exit_code = app.exec()
        except KeyboardInterrupt:
            exit_code = 0
        finally:
            self.is_running = False
            log_console("👋 Додаток завершено")
        sys.exit(exit_code)


if __name__ == "__main__":
    AssistantAppQt().start()
