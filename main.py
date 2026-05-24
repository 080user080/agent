# main.py
"""Головний файл запуску з GUI інтеграцією"""
import os
import sys
import time
import threading
import queue
from pathlib import Path
from colorama import Fore, Back, Style, init

# Ініціалізувати colorama
init(autoreset=True)

# Зміна робочої директорії на корінь проєкту
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Для правильного показу українських символів в консолі Windows
if os.name == 'nt':
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True, write_through=True)
    sys.stderr.reconfigure(encoding='utf-8', line_buffering=True, write_through=True)
    
    import io
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True, write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True, write_through=True)

# Додати шляхи до CUDA бібліотек
venv_path = sys.prefix
nvidia_paths = [
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cublas', 'bin'),
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cudnn', 'bin'),
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cuda_runtime', 'bin'),
]

for path in nvidia_paths:
    if os.path.exists(path):
        os.environ['PATH'] = path + os.pathsep + os.environ['PATH']
        try:
            os.add_dll_directory(path)
        except:
            pass

import sounddevice as sd
import numpy as np
import torch
import requests

# Імпорт модулів
from functions.runtime.logic_core import FunctionRegistry
from functions.gui.logic_commands import VoiceAssistant
from functions.planning.core_planner import Planner  #GPT
from functions.audio.logic_audio import (
    should_ignore_command, correct_whisper_text, 
    check_volume, check_activation_word, remove_activation_word,
    text_similarity
)
from functions.audio.initializer import AudioInitializer
from functions.config import (
    SAMPLE_RATE, LISTEN_DURATION, VOLUME_THRESHOLD,
    ACTIVATION_WORD, ACTIVATION_LISTEN_DURATION, COMMAND_LISTEN_DURATION, 
    MICROPHONE_DEVICE_ID, CONTINUOUS_MODE, 
    CONTINUOUS_LISTENING_ENABLED,
    ASSISTANT_NAME, ASSISTANT_EMOJI, ASSISTANT_DISPLAY_NAME,
    TTS_ENABLED, TTS_DEVICE, TTS_CACHE_DIR, TTS_VOICES_DIR,
    TTS_DEFAULT_VOICE, TTS_SPEECH_RATE, TTS_VOLUME, TTS_SPEAK_PREFIXES
)



class AssistantCore:
    """Ядро асистента з інтеграцією GUI"""
    
    def __init__(self, gui_queue=None):
        self.gui_queue = gui_queue
        self.stt_engine = None
        self.tts_engine = None
        self.stt_load_time = 0.0  # Час завантаження STT
        self.tts_load_time = 0.0  # Час завантаження TTS
        self.registry = None
        self.audio_filter = None
        self.listener = None
        self.assistant = None
        self.planner = None  #GPT
        self.is_running = False
        self.self_learning = None  # Self-learning module

        # Черги для спілкування між потоками
        self.command_queue = queue.Queue()
        self.message_queue = queue.Queue()
    
    # Технічні події — передаються як сигнали, а не текст у чат
    _TECHNICAL_EVENTS = frozenset({
        'update_progress', 'update_status',
        'execution_started', 'execution_finished',
        'plan_started', 'step_update', 'plan_finished',
        'show_confirmation',
    })

    # Маппінг стрімінгових подій
    _STREAM_EVENTS = {
        'assistant_stream_start': ('stream_start', None),
        'assistant_stream_chunk': ('stream_chunk', '{message}'),
        'assistant_stream_end': ('stream_end', None),
    }

    def log_to_gui(self, sender, message):
        """Відправити повідомлення в GUI"""
        if self.gui_queue:
            if sender in self._TECHNICAL_EVENTS:
                self.gui_queue.put((sender, message))
                return

            stream = self._STREAM_EVENTS.get(sender)
            if stream:
                msg_type, template = stream
                data = message if '{' not in template else template.format(message=message)
                self.gui_queue.put((msg_type, data))
                return

            # Видаляємо префікси для assistant
            if sender == "assistant":
                from functions.config import TTS_SPEAK_PREFIXES
                for prefix in TTS_SPEAK_PREFIXES:
                    if message and isinstance(message, str) and message.strip().startswith(prefix):
                        message = message.strip()[len(prefix):].strip()
                        break
            
            self.gui_queue.put(('add_message', (sender, message)))
        else:
            from functions.config import ASSISTANT_DISPLAY_NAME
            if sender == "user":
                print(f"{Fore.CYAN}👑 ВИ: {Fore.WHITE}{message}")
            else:
                print(f"{Fore.GREEN}{ASSISTANT_DISPLAY_NAME}: {Fore.WHITE}{message}")

    def _gui_notify(self, status_msg: str, chat_msg: str | None = None):
        """Допоміжний метод: відправити статус + чат-повідомлення в GUI."""
        if not self.gui_queue:
            return
        self.gui_queue.put(('update_status', status_msg))
        if chat_msg:
            self.gui_queue.put(('add_message', ('assistant', chat_msg)))
    
    def transcribe_audio(self, audio, stt_engine, audio_filter):
        """Транскрибувати аудіо через STT двигун"""
        try:
            print(f"{Fore.CYAN}🔧 Початкова довжина: {len(audio)/SAMPLE_RATE:.1f}с")
            
            text = stt_engine.transcribe(audio)
            
            print(f"{Fore.GREEN}✅ Розпізнано: '{text}'")
            
            return text.strip()
            
        except Exception as e:
            print(f"{Fore.RED}   ❌ Помилка транскрипції: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def record_audio_with_countdown(self, duration, sample_rate, label="Запис"):
        """Записати аудіо з зворотнім відліком"""
        print(f"{Fore.CYAN}🎤 {label}: ", end="", flush=True)
        
        audio_data = []
        
        def callback(indata, frames, time_info, status):
            audio_data.append(indata.copy())
        
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype=np.float32,
            device=MICROPHONE_DEVICE_ID,
            callback=callback
        )
        
        stream.start()
        
        for i in range(duration, 0, -1):
            print(f"{Fore.YELLOW}{i}", end="", flush=True)
            time.sleep(1)
            if i > 1:
                print(f"{Fore.LIGHTBLACK_EX}...", end="", flush=True)
        
        stream.stop()
        stream.close()
        
        print(f" {Fore.GREEN}✓")
        
        if audio_data:
            audio = np.concatenate(audio_data, axis=0)
            return np.squeeze(audio)
        else:
            return np.array([])
    
    def check_lm_studio(self):
        """Перевірити primary endpoint. Для локального LM Studio — автозавантаження моделі."""
        from functions.runtime.core_initializer_checks import check_lm_studio_readiness
        return check_lm_studio_readiness()
    
    def process_text_command(self, text):
        """Обробити текстову команду з GUI — всі команди йдуть до LLM."""
        if not text or len(text.strip()) == 0:
            return

        print(f"[DEBUG] process_text_command: '{text[:80]}...'")
        
        # Логуємо повідомлення користувача в GUI
        if self.gui_queue:
            self.gui_queue.put(('add_message', ('user', text)))

        # Всі команди йдуть до LLM через assistant.process_command
        # (він сам додає в conversation_history, використовує стрімінг,
        #  обробляє відповіді, озвучує TTS, кешує)
        print(f"[DEBUG] Sending to LLM via process_command: '{text[:60]}...'")
        if self.assistant:
            try:
                self.assistant.process_command(text, from_gui=True)
            except Exception as e:
                print(f"[ERROR] process_command failed: {e}")
                if self.gui_queue:
                    self.gui_queue.put(('add_message', ('assistant', f'❌ Помилка: {e}')))
        else:
            if self.gui_queue:
                self.gui_queue.put(('add_message', ('assistant', '⏳ Зачекайте ініціалізації асистента...')))
    
    def stop_execution(self):
        """Остановить текущее выполнение плана."""
        if self.assistant and hasattr(self.assistant, 'executor'):
            self.assistant.executor.stop()
            if self.gui_queue:
                self.gui_queue.put(('execution_finished', None))
                self.gui_queue.put(('add_message', ('assistant', '⏹️ Виконання зупинено користувачем.')))
        # Також зупинити PlanExecutor
        if getattr(self, 'plan_executor', None):
            self.plan_executor.request_stop()

    def run_pending_plan(self):
        """Виконати план, що очікує (викликається з GUI кнопки 'Виконати план')."""
        # Пріоритет: TaskSpecCompiler → AgentLoop → PlanExecutor (legacy)
        task = self._get_last_user_command() or ""

        if not task:
            if self.gui_queue:
                self.gui_queue.put(('add_message', ('assistant', '❌ Немає задачі для виконання.')))
            return

        # Запускаємо через AgentLoop
        self.run_agent_loop(task)

    def _classify_task(self, task: str) -> str:
        """Швидка класифікація завдання без LLM.

        Returns:
            FILE_OP — файлові операції (не потрібен екран)
            CODE_OP — виконання коду (не потрібен екран)
            CHAT — питання (просто відповідь)
            GUI_ACTION — GUI дії (потрібен екран)
            AGENT — fallback — повний AgentLoop
        """
        task_lower = task.lower()

        # Файлові операції — не потрібен екран
        file_keywords = ["створи файл", "запиши файл", "прочитай файл",
                         "видали файл", "перейменуй", "create file", "write file", "read file"]
        if any(k in task_lower for k in file_keywords):
            return "FILE_OP"

        # Питання — просто відповідь
        question_keywords = ["що таке", "поясни", "як працює",
                            "what is", "explain", "how does"]
        if any(k in task_lower for k in question_keywords):
            return "CHAT"

        # GUI дії — потрібен екран
        gui_keywords = ["клікни", "відкрий програму", "натисни",
                        "знайди на екрані", "click", "open app", "екран", "вікно", "кнопк"]
        if any(k in task_lower for k in gui_keywords):
            return "GUI_ACTION"

        return "AGENT"  # fallback — повний AgentLoop (включає виконання коду)

    def _execute_direct(self, task: str, action: str) -> None:
        """Пряме виконання функції без AgentLoop (для простих операцій)."""
        print(f"[DEBUG] Direct execution: {action} for task: {task[:50]}...")

        import re

        if self.gui_queue:
            self.gui_queue.put(('update_status', f'📝 Пряме виконання: {action}'))

        try:
            # Використовуємо registry для виконання
            registry = getattr(self, 'registry', None)
            if not registry:
                if self.gui_queue:
                    self.gui_queue.put(('add_message', ('assistant', '❌ Registry не доступний')))
                return

            if action == "write_file":
                # Парсинг параметрів з завдання
                filepath_match = re.search(r'["\']?([^"\']+\.(txt|py|md|json))["\']?', task, re.IGNORECASE)
                content_match = re.search(r'["\']?([^"\']+)["\']?\s*з текстом\s*["\']?([^"\']+)["\']?', task, re.IGNORECASE)

                filepath = filepath_match.group(1) if filepath_match else "output.txt"
                content = content_match.group(2) if content_match else ""

                result = registry.execute_function("write_file", {"filepath": filepath, "content": content}, auto_create=False)
                msg = f'✅ Файл створено: {filepath}' if result.get('ok') else f'❌ Помилка: {result.get("error")}'

            elif action == "execute_python":
                # Витягти Python код з тексту завдання
                code = self._extract_python_code(task)
                if not code:
                    msg = "❌ Не вдалося витягти Python код з завдання"
                else:
                    result = registry.execute_function("execute_python", {"code": code}, auto_create=False)
                    # execute_python повертає dict з полями ok, message, data
                    if isinstance(result, dict):
                        msg = result.get('message', 'Виконано') if result.get('ok') else f'❌ Помилка: {result.get("error")}'
                    else:
                        # Якщо повернулось щось інше (наприклад str)
                        msg = str(result)

            else:
                msg = f'❌ Невідома дія: {action}'

            if self.gui_queue:
                self.gui_queue.put(('add_message', ('assistant', msg)))
                self.gui_queue.put(('update_status', '✅ Готовий до роботи'))

        except Exception as e:
            print(f"[ERROR] Direct execution failed: {e}")
            if self.gui_queue:
                self.gui_queue.put(('add_message', ('assistant', f'❌ Помилка виконання: {e}')))

    def _extract_python_code(self, task: str) -> str:
        """Витягти Python код з тексту завдання.

        Підтримує:
        - ```python``` блоки
        - Рядки що починаються з import, def, class, print
        """
        import re

        # Спроба 1: витягти з ```python``` блоку
        code_block_match = re.search(r'```python\s*\n(.*?)\n```', task, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            return code_block_match.group(1).strip()

        # Спроба 2: витягти з ``` блоку без мови
        code_block_match = re.search(r'```\s*\n(.*?)\n```', task, re.DOTALL)
        if code_block_match:
            code = code_block_match.group(1).strip()
            # Перевірити чи це Python код
            if any(kw in code for kw in ['import ', 'def ', 'class ', 'print(']):
                return code

        # Спроба 3: знайти рядки що виглядають як Python код
        lines = task.split('\n')
        code_lines = []
        in_code = False

        for line in lines:
            stripped = line.strip()
            # Початок коду
            if any(stripped.startswith(kw) for kw in ['import ', 'from ', 'def ', 'class ', 'print(']):
                in_code = True
                code_lines.append(line)
            elif in_code:
                # Продовження коду (відступи або порожній рядок між блоками)
                if line.startswith(' ') or line.startswith('\t') or stripped == '':
                    code_lines.append(line)
                else:
                    # Кінець коду
                    break

        if code_lines:
            return '\n'.join(code_lines).strip()

        return ""

    def run_agent_loop(self, task: str):
        """Запустити AgentLoop для задачі через AgentCoordinator (делегує в commands_planner)."""
        from functions.gui.commands_planner import run_agent_loop as _run_agent_loop
        _run_agent_loop(
            task,
            gui_queue=self.gui_queue,
            agent_coordinator=getattr(self, 'agent_coordinator', None),
            agent_loop=getattr(self, 'agent_loop', None),
            assistant=getattr(self, 'assistant', None),
            timeout=45.0,
        )

    def stop_plan_execution(self):
        """Зупинити виконання плану (з GUI кнопки 'Стоп план', делегує в commands_planner)."""
        from functions.gui.commands_planner import stop_plan_execution as _stop_plan_execution
        _stop_plan_execution(
            agent_loop=getattr(self, 'agent_loop', None),
            agent_coordinator=getattr(self, 'agent_coordinator', None),
            plan_executor=getattr(self, 'plan_executor', None),
            assistant=getattr(self, 'assistant', None),
            gui_queue=self.gui_queue,
        )

    def start_windsurf_watch(self):
        """Запустити Windsurf Watch (з GUI кнопки)."""
        if getattr(self, 'windsurf_watcher', None):
            self.windsurf_watcher.start()

    def stop_windsurf_watch(self):
        """Зупинити Windsurf Watch (з GUI кнопки)."""
        if getattr(self, 'windsurf_watcher', None):
            self.windsurf_watcher.stop(reason="manual")

    def set_pending_plan(self, steps):
        """Зберегти план для виконання кнопкою 'Виконати план'."""
        self._pending_plan_steps = steps

    def _get_last_user_command(self) -> str:
        """Отримати останню команду користувача."""
        if self.assistant and hasattr(self.assistant, 'conversation_history'):
            for msg in reversed(self.assistant.conversation_history):
                if msg.get('role') == 'user':
                    return msg.get('content', '')
        return ""
    
    def pause_listening(self):
        """Призупинити слухання"""
        if self.listener:
            self.listener.pause_listening()
            print(f"{Fore.YELLOW}⏸️  Запис призупинено")
    
    def resume_listening(self):
        """Відновити слухання"""
        if self.listener:
            self.listener.resume_listening()
            print(f"{Fore.YELLOW}▶️  Запис відновлено")
    
    def initialize(self):
        """Ініціалізація асистента (з безперервним прослуховуванням)"""
        print(f"{Back.BLUE}{Fore.WHITE}{'='*60}")
        print(f"{Back.BLUE}{Fore.WHITE}{ASSISTANT_EMOJI} {ASSISTANT_NAME} - Голосовий Асистент {Style.RESET_ALL}")
        print(f"{Back.BLUE}{Fore.WHITE}{'='*60}{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}🔧 Завантаження модулів...")
        start_time = time.time()
        self.registry = FunctionRegistry()
        load_time = time.time() - start_time
        print(f"{Fore.LIGHTBLACK_EX}⏱️  {load_time:.2f}с")

        # Аудіо-ініціалізація через AudioInitializer (один виклик)
        audio = AudioInitializer(gui_queue=self.gui_queue)
        audio_result = audio.init_all(with_listener=CONTINUOUS_LISTENING_ENABLED)

        self.stt_engine = audio_result["stt_engine"]
        self.stt_load_time = audio_result["stt_load_time"]
        self.audio_filter = audio_result["audio_filter"]
        self.tts_engine = audio_result["tts_engine"]
        self.tts_load_time = audio_result["tts_load_time"]
        self.listener = audio_result["listener"]

        if not self.stt_engine:
            return False

        # Self-learning module
        print(f"\n{Fore.CYAN}🧠 Ініціалізація модуля самонавчання...")
        try:
            from functions.runtime.self_learning import get_self_learning
            self.self_learning = get_self_learning()
            stats = self.self_learning.get_stats()
            print(f"{Fore.GREEN}✅ Self-learning module готовий")
            print(f"{Fore.CYAN}   Виконань: {stats['total_executions']}")
            print(f"{Fore.CYAN}   Успішність: {stats['success_rate']:.1%}")
            print(f"{Fore.CYAN}   Skills: {stats['skills_count']}")
            print(f"{Fore.CYAN}   Rules: {stats['rules_count']}")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Не вдалося ініціалізувати self-learning: {e}")
            self.self_learning = None

        print(f"\n{Fore.CYAN}🔌 Підключення до LM Studio...")
        if not self.check_lm_studio():
            return False

        print(f"\n{Fore.YELLOW}{'='*60}")
        print(f"{Fore.YELLOW}📦 Функцій: {Fore.WHITE}{len(self.registry.functions)}")
        for func_name in self.registry.functions.keys():
            print(f"{Fore.CYAN}   • {func_name}")
        print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")

        system_prompt = self.registry.get_system_prompt()

        # Безперервний слухач — вже створено в init_all(with_listener=True)
        if CONTINUOUS_LISTENING_ENABLED:
            if not self.listener:
                print(f"{Fore.RED}❌ Не вдалося створити слухача")
                return False
        else:
            self.listener = None
            return False

        # Спільна ініціалізація VoiceAssistant + Planner + TTS
        self._init_assistant_common(system_prompt)

        # Передати listener в TTS
        if self.tts_engine and self.listener:
            self.tts_engine.listener = self.listener

        print(f"{Fore.GREEN}✅ Асистент готовий")
        return True

    def _init_assistant_common(self, system_prompt: str):
        """Спільна ініціалізація VoiceAssistant, Planner, TTS — використовується обома init-методами."""
        def custom_log(sender, message):
            self.log_to_gui(sender, message)

        self.assistant = VoiceAssistant(
            self.stt_engine,
            self.registry,
            system_prompt,
            listener=self.listener,
            gui_log_callback=custom_log
        )

        # --- Planner init --- #GPT
        self.planner = Planner(self.assistant)  #GPT
        if hasattr(self.assistant, "set_planner"):
            self.assistant.set_planner(self.planner)  #GPT

        # Встановити TTS двигун в асистента
        if self.tts_engine:
            self.assistant.set_tts_engine(self.tts_engine)

    def initialize_without_listener(self):
        """Ініціалізація асистента БЕЗ безперервного прослуховування (текстовий режим)"""
        print(f"\n{Back.BLUE} {ASSISTANT_EMOJI} {ASSISTANT_NAME} - Текстовий режим {Style.RESET_ALL}\n")

        # Загальний таймер ініціалізації
        init_start_time = time.time()

        # Реєстр функцій
        print(f"{Fore.CYAN}🔧 Завантаження функцій...")
        self.registry = FunctionRegistry()

        # Аудіо-ініціалізація через AudioInitializer (один виклик, без слухача)
        audio = AudioInitializer(gui_queue=self.gui_queue)
        audio_result = audio.init_all(with_listener=False)

        self.stt_engine = audio_result["stt_engine"]
        self.stt_load_time = audio_result["stt_load_time"]
        self.audio_filter = audio_result["audio_filter"]
        self.tts_engine = audio_result["tts_engine"]
        self.tts_load_time = audio_result["tts_load_time"]

        if self.gui_queue and self.tts_engine:
            self.gui_queue.put(('add_message', ('assistant', '✅ Готовий до роботи! Введіть команду.')))

        # LM Studio
        print(f"\n{Fore.CYAN}🔌 Підключення до LM Studio...")
        if not self.check_lm_studio():
            return False

        # Listener = None (текстовий режим)
        self.listener = None

        # Спільна ініціалізація VoiceAssistant + Planner + TTS
        system_prompt = self.registry.get_system_prompt()
        self._init_assistant_common(system_prompt)

        # --- PlanExecutor init (S2: GUI ↔ TaskRunner bridge) ---
        try:
            from functions.planning.plan_executor import PlanExecutor
            self.plan_executor = PlanExecutor(
                assistant=self.assistant,
                gui_callback=lambda msg_type, data: self.log_to_gui(msg_type, data),
            )
            self._pending_plan_steps = None  # Кроки, що чекають виконання
            print(f"{Fore.GREEN}✅ PlanExecutor готовий")
        except Exception as e:
            self.plan_executor = None
            print(f"{Fore.YELLOW}⚠️  PlanExecutor недоступний: {e}")

        # --- WindsurfWatcherExecutor init (Phase 12.5: Windsurf Watch GUI) ---
        try:
            from functions.runtime.windsurf_watcher_executor import WindsurfWatcherExecutor
            self.windsurf_watcher = WindsurfWatcherExecutor(
                gui_callback=lambda msg_type, data: self.log_to_gui(msg_type, data),
            )
            print(f"{Fore.GREEN}✅ WindsurfWatcherExecutor готовий")
        except Exception as e:
            self.windsurf_watcher = None
            print(f"{Fore.YELLOW}⚠️  WindsurfWatcherExecutor недоступний: {e}")

        # --- Ініціалізація STT контролера для GUI (кнопка мікрофона) ---
        from functions.runtime.core_settings import get_setting
        stt_enabled = get_setting("STT_ENABLED", False)
        if stt_enabled and self.gui_queue is not None:
            try:
                from functions.audio.core_stt_listener import get_stt_controller
                
                # 🔥 Callback для оновлення іконки в трей коли GUI кнопка активна
                def tray_status_callback(status, text=""):
                    if hasattr(self, 'global_voice_input') and self.global_voice_input:
                        try:
                            self.global_voice_input._update_tray_status(status, text)
                        except Exception as e:
                            print(f"[STT] Помилка оновлення tray: {e}")
                
                print(f"\n{Fore.CYAN}🎤 Ініціалізація голосових команд для GUI...")
                stt_controller = get_stt_controller(
                    process_command_callback=self.process_text_command,
                    gui_queue=self.gui_queue,
                    tray_status_callback=tray_status_callback
                )
                if stt_controller:
                    # GUI може ще не бути готовим - відкладене встановлення через чергу
                    self._pending_stt_controller = stt_controller
                    print(f"{Fore.GREEN}✅ STT контролер створено, буде передано в GUI")
                else:
                    print(f"{Fore.YELLOW}⚠️  STT контролер не створено")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Не вдалося ініціалізувати STT контролер: {e}")
                import traceback
                traceback.print_exc()

        # --- AgentLoop init через AgentCoordinator (Phase 12.1+: observe → plan → act → check) ---
        try:
            from functions.planning.agent_coordinator import build_agent_coordinator

            self.agent_coordinator = build_agent_coordinator(
                assistant=self.assistant,
                registry=self.registry,
                gui_queue=self.gui_queue,
                gui_log_callback=lambda sender, msg: self.log_to_gui(sender, msg),
            )
            if self.agent_coordinator and self.agent_coordinator.agent_loop:
                self.agent_loop = self.agent_coordinator.agent_loop
                print(f"{Fore.GREEN}✅ AgentLoop готовий (через AgentCoordinator)")
            else:
                self.agent_loop = None
                print(f"{Fore.YELLOW}⚠️  AgentLoop недоступний (через AgentCoordinator)")

            # Виконати чергу задач, якщо є
            if hasattr(self, '_pending_tasks') and self._pending_tasks:
                for task in self._pending_tasks:
                    print(f"[DEBUG] Виконую чергову задачу: {task[:50]}...")
                    self.run_agent_loop(task)
                self._pending_tasks = []
        except Exception as e:
            self.agent_coordinator = None
            self.agent_loop = None
            print(f"{Fore.YELLOW}⚠️  AgentLoop недоступний: {e}")
            import traceback
            traceback.print_exc()

        # --- TaskSpecCompiler init (S3: TaskSpec → compile() MVP) ---
        try:
            from functions.planning.task_spec import TaskSpecCompiler
            self.task_spec_compiler = TaskSpecCompiler(
                assistant=self.assistant,
                registry=self.registry,
            )
            print(f"{Fore.GREEN}✅ TaskSpecCompiler готовий")
        except Exception as e:
            self.task_spec_compiler = None
            print(f"{Fore.YELLOW}⚠️  TaskSpecCompiler недоступний: {e}")

        # --- Ініціалізація Global Voice Input (глобальний hook для голосового вводу) ---
        try:
            from functions.runtime.core_settings import get_setting
            global_voice_enabled = get_setting("GLOBAL_VOICE_ENABLED", False)
            hotkey = get_setting("GLOBAL_VOICE_HOTKEY", "ctrl+shift+v")
            print(f"\n{Fore.CYAN}🎙️  Global Voice Input: enabled={global_voice_enabled}, hotkey={hotkey}")
            if global_voice_enabled:
                from functions.global_voice_input import GlobalVoiceInput

                print(f"\n{Fore.CYAN}🎙️  Ініціалізація глобального голосового вводу (hotkey: {hotkey})...")

                def on_voice_status(status: str):
                    """Callback для статусу."""
                    print(f"{Fore.CYAN}   [Global Voice] {status}")

                # Callback для отримання розпізнаного тексту — передаємо в process_text_command
                def on_voice_text(text: str):
                    """Callback для розпізнаного тексту."""
                    if text and self.gui_queue:
                        self.gui_queue.put(('add_message', ('user', f"[ГОЛОС] {text}")))
                        self.process_text_command(text)

                self.global_voice_input = GlobalVoiceInput(
                    hotkey=hotkey,
                    callback=on_voice_text,
                    status_callback=on_voice_status
                )

                if self.global_voice_input.start():
                    print(f"{Fore.GREEN}✅ Глобальний голосовий ввід запущено")
                else:
                    print(f"{Fore.YELLOW}⚠️  Не вдалося запустити глобальний голосовий ввід")
                    self.global_voice_input = None
            else:
                print(f"{Fore.YELLOW}⏭️  Global Voice Input вимкнено (GLOBAL_VOICE_ENABLED=False)")
                self.global_voice_input = None
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Не вдалося ініціалізувати глобальний голосовий ввід: {e}")
            import traceback
            traceback.print_exc()
            self.global_voice_input = None

        print(f"\n{Fore.GREEN}✅ Асистент готовий")
        
        # Загальний час ініціалізації
        init_time = time.time() - init_start_time
        print(f"{Fore.CYAN}⏱️  Час ініціалізації: {init_time:.1f}с")
        
        # Додати повідомлення в GUI чат незалежно від статусу TTS
        if self.gui_queue:
            self.gui_queue.put(('add_message', ('assistant', f'✅ Готовий до роботи! ({init_time:.1f}с)')))
        
        return True
    
    def run(self):
        """Запустити асистента"""
        if CONTINUOUS_LISTENING_ENABLED:
            if not self.initialize():
                return
        else:
            if not self.initialize_without_listener():
                return
        
        if CONTINUOUS_LISTENING_ENABLED:
            print(f"\n{Back.CYAN}{Fore.BLACK} 🎧 РЕЖИМ БЕЗПЕРЕРВНОГО ПРОСЛУХОВУВАННЯ {Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💡 Говоріть природньо, асистент завжди слухає")
        else:
            print(f"\n{Back.CYAN}{Fore.BLACK} 📝 ТЕКСТОВИЙ РЕЖИМ {Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💡 Вводьте команди в GUI. Голосовий ввід доступний через функцію 'voice_input'.")
        
        if self.tts_engine and self.tts_engine.is_ready:
            print(f"{Fore.CYAN}💬 TTS активовано: відповіді озвучуватимуться")
            if CONTINUOUS_LISTENING_ENABLED:
                print(f"{Fore.CYAN}   Запис буде автоматично призупинятися під час озвучення")
        
        print(f"{Fore.LIGHTBLACK_EX}💡 Ctrl+C для виходу")
        print()
        
        self.gui.set_assistant(self)

        # --- Ініціалізація STT контролера для голосових команд ---
        from functions.audio.core_stt_listener import get_stt_controller
        from functions.config import STT_ENABLED

        if STT_ENABLED:
            print(f"\n{Fore.CYAN}🎤 Ініціалізація голосових команд...")
            try:
                # 🔥 Callback для оновлення іконки в трей коли GUI кнопка активна
                def tray_status_callback(status, text=""):
                    if hasattr(self, 'global_voice_input') and self.global_voice_input:
                        try:
                            self.global_voice_input._update_tray_status(status, text)
                        except Exception as e:
                            print(f"[STT] Помилка оновлення tray: {e}")
                
                stt_controller = get_stt_controller(
                    process_command_callback=self.process_text_command,
                    tray_status_callback=tray_status_callback
                )
                if stt_controller:
                    self.gui.set_stt_controller(stt_controller)
                    print(f"{Fore.GREEN}✅ Голосові команди готові (натисніть 🎤 в чаті)")
                else:
                    print(f"{Fore.YELLOW}⚠️  STT контролер не створено (перевірте налаштування)")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Не вдалося ініціалізувати STT: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"\n{Fore.YELLOW}⏭️  Голосові команди вимкнено (STT_ENABLED=False)")

        print()

        if CONTINUOUS_LISTENING_ENABLED:
            self._run_continuous_mode()
        else:
            self._run_text_mode()
    
    def _run_continuous_mode(self):
        """Запустити безперервне прослуховування"""
        def transcribe_wrapper(audio):
            return self.transcribe_audio(audio, self.stt_engine, self.audio_filter)
        
        try:
            # Запустити безперервне прослуховування
            self.listener.start(transcribe_wrapper, self.assistant)
            self.is_running = True
            
            # Тримати основний потік активним
            while self.is_running and self.listener.is_listening:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}👋 Вимикаюся...")
            self.stop()
    
    def _run_text_mode(self):
        """Працювати в текстовому режимі (очікування команд через GUI)"""
        self.is_running = True
        try:
            while self.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}👋 Вимикаюся...")
            self.stop()
    
    def stop(self):
        """Зупинити асистента"""
        print(f"\n{Fore.YELLOW}🛑 Зупиняю асистента...")
        self.is_running = False
        
        if self.listener:
            self.listener.stop()
        
        if self.assistant:
            self.assistant.is_listening = False
        
        if self.tts_engine:
            self.tts_engine.stop()
        
        print(f"{Fore.GREEN}✅ Асистент зупинено")

def main():
    """Головна функція запуску"""
    core = AssistantCore()
    core.run()

if __name__ == "__main__":
    main()
