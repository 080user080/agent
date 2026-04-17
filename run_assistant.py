# run_assistant.py
"""Запуск асистента з GUI"""
import threading
import time
import queue
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core_gui import AssistantGUI
from main import AssistantCore
from functions.aaa_confirmation import set_gui_instance


def log_console(message):
    """Друк у консоль без буферизації."""
    print(message, flush=True)

class AssistantApp:
    def __init__(self):
        self.gui_queue = queue.Queue()
        self.core = None
        self.gui = None
        self.is_running = True

    def gui_callback(self, action, data=None):
        """Callback для GUI"""
        if not self.core:
            return
        if action == 'pause_listening':
            self.core.pause_listening()
        elif action == 'resume_listening':
            self.core.resume_listening()
        elif action == 'process_text':
            threading.Thread(
                target=self.core.process_text_command,
                args=(data,),
                daemon=True
            ).start()
        elif action == 'stop_execution':
            threading.Thread(
                target=self.core.stop_execution,
                daemon=True
            ).start()

    def process_gui_queue(self):
        """Обробляти повідомлення з черги і передавати в GUI"""
        if self.gui:
            try:
                while True:
                    msg_type, data = self.gui_queue.get_nowait()
                    if msg_type == 'add_message':
                        self.gui.queue_message('add_message', data)
                    elif msg_type == 'show_confirmation':
                        self.gui.queue_message('show_confirmation', data)
                    elif msg_type == 'update_status':
                        log_console(f"[STATUS] {data}")
                        self.gui.queue_message('update_status', data)
                    elif msg_type == 'update_progress':
                        self.gui.queue_message('update_progress', data)
                    elif msg_type == 'stream_start':
                        self.gui.queue_message('stream_start', None)
                    elif msg_type == 'stream_chunk':
                        self.gui.queue_message('stream_chunk', data)
                    elif msg_type == 'stream_end':
                        self.gui.queue_message('stream_end', None)
                    elif msg_type == 'execution_started':
                        log_console("[STATUS] Виконання запущено")
                        self.gui.queue_message('execution_started', None)
                    elif msg_type == 'execution_finished':
                        log_console("[STATUS] Виконання завершено")
                        self.gui.queue_message('execution_finished', None)
                    elif msg_type == 'plan_started':
                        self.gui.queue_message('plan_started', data)
                    elif msg_type == 'step_update':
                        self.gui.queue_message('step_update', data)
                    elif msg_type == 'plan_finished':
                        self.gui.queue_message('plan_finished', data)
                    elif msg_type == 'show_confirmation':
                        self.gui.queue_message('show_confirmation', data)
            except queue.Empty:
                pass

        # Якщо GUI ще живий — плануємо наступну перевірку
        if self.gui and self.gui.root.winfo_exists():
            self.gui.root.after(100, self.process_gui_queue)

    def run_core_in_thread(self):
        """Запустити ядро асистента в окремому потоці"""
        try:
            log_console("🔧 Ініціалізація ядра асистента...")
            log_console("[STATUS] Створення AssistantCore...")
            self.core = AssistantCore(gui_queue=self.gui_queue)
            log_console("[STATUS] Ядро створено, запускаю текстову ініціалізацію...")

            # Ініціалізуємо компоненти вручну, щоб не залежати від CONTINUOUS_LISTENING_ENABLED
            if not self.core.initialize_without_listener():
                log_console("❌ Помилка ініціалізації ядра")
                if self.gui:
                    self.gui.queue_message('add_message', ('assistant', '❌ Помилка ініціалізації. Перевірте консоль.'))
                return

            log_console("✅ Ядро готове. Очікую команди через GUI...")
            if self.gui:
                self.gui.queue_message('add_message', ('assistant', f'✅ Готовий до роботи! Введіть команду.'))
                self.gui.queue_message('update_status', '✅ Готовий до роботи')

            # Тримаємо потік живим
            while self.is_running:
                time.sleep(0.5)

        except Exception as e:
            log_console(f"❌ Критична помилка ядра: {e}")
            import traceback
            traceback.print_exc()
            if self.gui:
                self.gui.queue_message('add_message', ('assistant', f'❌ Помилка: {e}'))

    def start(self):
        """Запустити додаток — GUI в головному потоці"""
        log_console("🚀 Запуск асистента МАРК з GUI...")
        log_console("[STATUS] Старт GUI...")

        # Запускаємо ядро в окремому потоці
        core_thread = threading.Thread(target=self.run_core_in_thread, daemon=True)
        core_thread.start()

        # GUI — в головному потоці (обов'язково для Tkinter)
        self.gui = AssistantGUI(self.gui_callback)
        set_gui_instance(self.gui)
        log_console("[STATUS] GUI створено, очікую готовність ядра...")

        # Після того як GUI створений — запускаємо обробку черги через after()
        self.gui.root.after(200, self.process_gui_queue)

        try:
            self.gui.run()  # блокує головний потік до закриття вікна
        except KeyboardInterrupt:
            pass
        finally:
            self.is_running = False
            log_console("👋 Додаток завершено")


if __name__ == "__main__":
    app = AssistantApp()
    app.start()
