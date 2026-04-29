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
from functions.logic_core import FunctionRegistry
from functions.logic_commands import VoiceAssistant
from functions.core_planner import Planner  #GPT
from functions.logic_audio import (
    should_ignore_command, correct_whisper_text, 
    check_volume, check_activation_word, remove_activation_word,
    text_similarity
)
from functions.logic_audio_filtering import get_audio_filter
from functions.logic_continuous_listener import create_continuous_listener
from functions.logic_tts import TTSEngine
from functions.config import (
    SAMPLE_RATE, LISTEN_DURATION, VOLUME_THRESHOLD,
    ACTIVATION_WORD, ACTIVATION_LISTEN_DURATION, COMMAND_LISTEN_DURATION, 
    MICROPHONE_DEVICE_ID, CONTINUOUS_MODE, 
    CONTINUOUS_LISTENING_ENABLED,
    ASSISTANT_NAME, ASSISTANT_EMOJI, ASSISTANT_DISPLAY_NAME,
    TTS_ENABLED, TTS_DEVICE, TTS_CACHE_DIR, TTS_VOICES_DIR,
    TTS_DEFAULT_VOICE, TTS_SPEECH_RATE, TTS_VOLUME, TTS_SPEAK_PREFIXES
)

from functions.logic_stt import get_stt_engine


def print_audio_diagnostics():
    """Вивести інформацію про мікрофон тільки коли потрібен голосовий режим."""
    try:
        print("\n" + "=" * 60)
        print("🎤 ДОСТУПНІ МІКРОФОНИ:")
        print("=" * 60)
        print(sd.query_devices())
        print("=" * 60 + "\n")

        if MICROPHONE_DEVICE_ID is not None:
            print(f"{Fore.YELLOW}🎤 Вибрано мікрофон #{MICROPHONE_DEVICE_ID}")
            device_info = sd.query_devices(MICROPHONE_DEVICE_ID)
            print(f"   Назва: {device_info['name']}")
            print(f"   Канали: {device_info['max_input_channels']}")
        else:
            print(f"{Fore.YELLOW}🎤 Використовується системний мікрофон за замовчуванням")
            default_input = sd.query_devices(kind='input')
            print(f"   Назва: {default_input['name']}")
        print()
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Діагностику мікрофона пропущено: {e}")


def run_audio_smoke_test():
    """Короткий тест запису лише для голосового режиму."""
    try:
        print("🧪 Тестовий запис 2 секунди...")
        test_audio = sd.rec(
            int(2 * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.float32,
            device=MICROPHONE_DEVICE_ID,
            blocking=True
        )
        volume = np.abs(test_audio).mean()
        print(f"   Середня гучність: {volume:.6f}")
        print(f"   Поріг: {VOLUME_THRESHOLD}")

        if volume < 0.01:
            print(f"{Fore.RED}   ⚠️  ДУЖЕ ТИХО! Гучність {volume:.6f} < 0.01")
            print(f"{Fore.YELLOW}   💡 Підвищіть гучність мікрофона:")
            print(f"{Fore.YELLOW}      1. Правий клік на звук → Налаштування")
            print(f"{Fore.YELLOW}      2. Введення → Властивості")
            print(f"{Fore.YELLOW}      3. Рівні → Мікрофон 100% + Підсилення +20dB")
        elif volume > VOLUME_THRESHOLD:
            print("   ✅ Мікрофон працює!")
        else:
            print("   ❌ Занадто тихо")
        print()
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Тест аудіо пропущено: {e}")

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
    
    def log_to_gui(self, sender, message):
        """Відправити повідомлення в GUI"""
        if self.gui_queue:
            # --- Технічні події від TaskExecutor та planner (НЕ чат) ---
            # Ці msg_type потрапляють у GUI як сигнали, а не текст
            TECHNICAL_EVENTS = {
                'update_progress', 'update_status',
                'execution_started', 'execution_finished',
                'plan_started', 'step_update', 'plan_finished',
                'show_confirmation',
            }
            if sender in TECHNICAL_EVENTS:
                self.gui_queue.put((sender, message))
                return

            # Нові типи для стрімінгу
            if sender == "assistant_stream_start":
                self.gui_queue.put(('stream_start', None))
                return
            elif sender == "assistant_stream_chunk":
                self.gui_queue.put(('stream_chunk', message))
                return
            elif sender == "assistant_stream_end":
                self.gui_queue.put(('stream_end', None))
                return

            # Видаляємо префікси для assistant
            if sender == "assistant":
                from functions.config import TTS_SPEAK_PREFIXES
                for prefix in TTS_SPEAK_PREFIXES:
                    if message and isinstance(message, str) and message.strip().startswith(prefix):
                        message = message.strip()[len(prefix):].strip()
                        break
            
            # Відправляємо чисте повідомлення
            self.gui_queue.put(('add_message', (sender, message)))
        else:
            # Fallback до консолі
            from functions.config import ASSISTANT_DISPLAY_NAME
            if sender == "user":
                print(f"{Fore.CYAN}👑 ВИ: {Fore.WHITE}{message}")
            else:
                print(f"{Fore.GREEN}{ASSISTANT_DISPLAY_NAME}: {Fore.WHITE}{message}")
    
    def load_stt_model(self):
        """Завантажити STT двигун"""
        try:
            stt_engine = get_stt_engine()
            available_models = stt_engine.get_available_models()
            
            if not available_models:
                print(f"{Fore.RED}   ❌ Немає доступних моделей STT")
                raise Exception("Не вдалося завантажити жодну модель STT")
            
            print(f"   ✅ Моделі завантажені: {', '.join(available_models)}")
            print(f"   🎯 Пристрій: {stt_engine.device}")
            
            return stt_engine
            
        except Exception as e:
            print(f"   ❌ Помилка завантаження моделей STT: {e}")
            raise
    
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
        import subprocess
        import os

        LMS_PATH = os.path.expanduser(r"~\.lmstudio\bin\lms.exe")
        BASE_URL = "http://localhost:1234"

        # Отримати primary endpoint з налаштувань
        def get_primary_endpoint():
            try:
                from functions.core_settings import get_setting
                endpoints = get_setting("LLM_ENDPOINTS", [])
                # Шукаємо endpoint з role="1" або "primary"
                for ep in endpoints:
                    role = ep.get("role")
                    if role == "1" or role == "primary":
                        if (ep.get("enabled") and ep.get("model") and ep.get("url")):
                            return ep
                # Якщо не знайдено role="1" або "primary", шукаємо endpoint з найменшим цифровим role
                enabled_endpoints = [ep for ep in endpoints if ep.get("enabled") and ep.get("model") and ep.get("url")]
                if enabled_endpoints:
                    # Сортуємо за цифровим role
                    def get_role_order(ep):
                        try:
                            return int(ep.get("role", 999)) if ep.get("role") else 999
                        except (ValueError, TypeError):
                            role_map = {"primary": 1, "secondary": 2, "fallback": 3, "alternative": 4}
                            return role_map.get(ep.get("role"), 999)
                    enabled_endpoints.sort(key=get_role_order)
                    return enabled_endpoints[0]
            except:
                pass
            return None

        print(f"{Fore.CYAN}🔌 Перевірка primary LLM endpoint...")

        primary_ep = get_primary_endpoint()

        if not primary_ep:
            print(f"{Fore.YELLOW}⚠️  Primary модель не налаштована")
            print(f"{Fore.YELLOW}💡 Налаштуйте модель в GUI: Налаштування → LLM Моделі")
            return False

        DESIRED_MODEL = primary_ep.get("model")
        PRIMARY_URL = primary_ep.get("url", "")
        
        print(f"{Fore.CYAN}   Primary модель: {DESIRED_MODEL}")
        print(f"{Fore.CYAN}   URL: {PRIMARY_URL}")

        # Якщо URL НЕ локальний LM Studio — пропускаємо автозавантаження
        if "localhost" not in PRIMARY_URL and "127.0.0.1" not in PRIMARY_URL:
            print(f"{Fore.GREEN}✅ Віддалений API (Gemini/OpenAI/etc) — LM Studio не потрібен")
            return True

        # Допоміжна функція: перевірити чи модель РЕАЛЬНО відповідає на запит
        def is_model_ready():
            try:
                # Спробуємо зробити тестовий запит — це перевірить чи модель в пам'яті
                test_response = requests.post(
                    f"{BASE_URL}/v1/chat/completions",
                    json={
                        "model": DESIRED_MODEL,
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 5,
                        "temperature": 0
                    },
                    timeout=5
                )
                if test_response.status_code == 200:
                    return True
                # Якщо помилка "model not found" або "no model loaded" — модель не готова
                error_text = test_response.text.lower()
                if "no model loaded" in error_text or "model not found" in error_text:
                    return False
                # Інші помилки — можливо модель завантажена але є інші проблеми
                return test_response.status_code == 200
            except Exception:
                return False

        # Перевірити чи модель вже завантажена (список + реальна перевірка)
        try:
            response = requests.get(f"{BASE_URL}/v1/models", timeout=2)
            if response.status_code == 200:
                data = response.json()
                models = [m['id'] for m in data.get('data', [])]
                if DESIRED_MODEL in models:
                    # Модель є в списку, але перевіримо чи вона реально відповідає
                    print(f"{Fore.CYAN}   Модель є в списку, перевіряю чи готова до роботи...")
                    if is_model_ready():
                        print(f"{Fore.GREEN}✅ Модель завантажена і готова: {DESIRED_MODEL}")
                        return True
                    else:
                        print(f"{Fore.YELLOW}⚠️  Модель є в списку, але не завантажена в пам'ять")
        except Exception as e:
            print(f"{Fore.YELLOW}   Не вдалося перевірити список моделей: {e}")

        print(f"{Fore.CYAN}🤖 Завантаження {DESIRED_MODEL}...")

        try:
            # Завантажити модель через lms.exe
            process = subprocess.Popen(
                [LMS_PATH, "load", DESIRED_MODEL],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )

            print(f"{Fore.CYAN}⏳ Очікування завантаження (до 30с)...")

            # Перевіряти чи модель РЕАЛЬНО завантажена через тестовий запит
            for i in range(30):
                time.sleep(1)

                # Спершу перевіримо чи модель в списку
                try:
                    response = requests.get(f"{BASE_URL}/v1/models", timeout=1)
                    if response.status_code == 200:
                        data = response.json()
                        models = [m['id'] for m in data.get('data', [])]
                        if DESIRED_MODEL in models:
                            # Модель в списку — тепер перевіримо чи вона відповідає
                            if is_model_ready():
                                print(f"{Fore.GREEN}✅ Модель завантажена і готова за {i+1}с!")
                                return True
                except:
                    pass

                if i % 5 == 0 and i > 0:
                    print(f"{Fore.LIGHTBLACK_EX}   {i}с... очікую завантаження в пам'ять")

            # Фінальна перевірка
            if is_model_ready():
                print(f"{Fore.GREEN}✅ Модель завантажена і готова!")
                return True
            else:
                print(f"{Fore.YELLOW}⚠️  Модель завантажена в список, але не відповідає на запити")
                print(f"{Fore.YELLOW}   Можливо, завантаження ще триває або потрібно перезавантажити LM Studio")
                return False

        except Exception as e:
            print(f"{Fore.RED}❌ Помилка автозавантаження: {e}")
            print(f"{Fore.YELLOW}💡 Завантажте модель вручну в LM Studio")
            return False
    
    def process_text_command(self, text):
        """Обробити текстову команду з GUI"""
        if not text or len(text.strip()) == 0:
            return

        # Лог команди виводиться в process_command (щоб не дублювалося)
        if self.assistant:
            self.assistant.process_command(text, from_gui=True)
    
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

    def run_agent_loop(self, task: str):
        """Запустити AgentLoop для задачі (основний шлях виконання).

        Пріоритет: TaskSpecCompiler → AgentLoop → PlanExecutor (legacy)
        """
        if not task:
            if self.gui_queue:
                self.gui_queue.put(('add_message', ('assistant', '❌ Немає задачі для виконання.')))
            return

        execution_success = False
        execution_error = None
        execution_steps = []

        try:
            # Спробувати TaskSpecCompiler (S3)
            if getattr(self, 'task_spec_compiler', None):
                if self.gui_queue:
                    self.gui_queue.put(('update_status', '📝 Компілюю TaskSpec...'))
                try:
                    spec = self.task_spec_compiler.parse(task)
                    compiled_plan = self.task_spec_compiler.compile(spec)
                    is_valid, msg = self.task_spec_compiler.validate_plan(compiled_plan)

                    if is_valid and compiled_plan.steps:
                        execution_steps = [
                            {"action": step.action, "goal": step.goal}
                            for step in compiled_plan.steps
                        ]
                        if self.gui_queue:
                            self.gui_queue.put(('add_message', ('assistant', f'📋 План: {len(compiled_plan.steps)} кроків (домен: {spec.domain.value})')))

                        # Встановити план в AgentLoop і запустити
                        if getattr(self, 'agent_loop', None):
                            self.agent_loop.set_compiled_plan(compiled_plan)
                            if self.gui_queue:
                                self.gui_queue.put(('update_status', '🤖 AgentLoop: observe → plan → act → check'))
                            result = self.agent_loop.run(task)
                            execution_success = True
                        # Fallback до PlanExecutor
                        elif getattr(self, 'plan_executor', None):
                            self.plan_executor.execute_plan(compiled_plan.steps, task)
                            execution_success = True
                        return
                    else:
                        if self.gui_queue:
                            self.gui_queue.put(('add_message', ('assistant', f'⚠️ {msg}')))
                except Exception as e:
                    execution_error = str(e)
                    if self.gui_queue:
                        self.gui_queue.put(('add_message', ('assistant', f'⚠️ TaskSpec: {e}')))

            # AgentLoop без CompiledPlan
            if getattr(self, 'agent_loop', None):
                if self.gui_queue:
                    self.gui_queue.put(('update_status', '🤖 AgentLoop: observe → plan → act → check'))
                result = self.agent_loop.run(task)
                execution_success = True
                return

            # Fallback до PlanExecutor (legacy)
            steps = None
            if self.assistant:
                steps = getattr(self.assistant, '_last_plan', None)

            if not steps:
                steps = getattr(self, '_pending_plan_steps', None)

            if not steps and getattr(self, 'plan_executor', None):
                steps = self.plan_executor.create_plan(task)

            if not steps:
                if self.gui_queue:
                    self.gui_queue.put(('add_message', ('assistant', '❌ Не вдалося створити план')))
                execution_error = "Failed to create plan"
                return

            if getattr(self, 'plan_executor', None):
                self._pending_plan_steps = None
                self.plan_executor.execute_plan(steps, task)
                execution_success = True

        except Exception as e:
            execution_error = str(e)
            execution_success = False
            if self.gui_queue:
                self.gui_queue.put(('add_message', ('assistant', f'❌ Помилка виконання: {e}')))
        finally:
            # Логування в self-learning
            if self.self_learning:
                self.self_learning.log_execution(
                    task=task,
                    result="success" if execution_success else "failed",
                    success=execution_success,
                    error=execution_error,
                    steps=execution_steps,
                    metadata={"method": "agent_loop"}
                )

    def stop_plan_execution(self):
        """Зупинити виконання плану (з GUI кнопки 'Стоп план')."""
        if getattr(self, 'agent_loop', None):
            self.agent_loop.request_stop()
        if getattr(self, 'plan_executor', None):
            self.plan_executor.request_stop()
        # Також зупинити основний executor
        if self.assistant and hasattr(self.assistant, 'executor'):
            self.assistant.executor.stop()

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
        """Ініціалізація асистента"""
        print(f"{Back.BLUE}{Fore.WHITE}{'='*60}")
        print(f"{Back.BLUE}{Fore.WHITE}{ASSISTANT_EMOJI} {ASSISTANT_NAME} - Голосовий Асистент {Style.RESET_ALL}")
        print(f"{Back.BLUE}{Fore.WHITE}{'='*60}{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}🔧 Завантаження модулів...")
        start_time = time.time()
        self.registry = FunctionRegistry()
        load_time = time.time() - start_time
        print(f"{Fore.LIGHTBLACK_EX}⏱️  {load_time:.2f}с")

        print_audio_diagnostics()
        run_audio_smoke_test()

        # Перевірка чи увімкнено STT
        from functions.core_settings import get_setting
        stt_enabled = get_setting("STT_ENABLED", False)

        if stt_enabled:
            if self.gui_queue:
                print(f"{Fore.CYAN}[GUI] Відправка повідомлення: 🔊 Завантаження STT моделей...")
                self.gui_queue.put(('update_status', '🔊 Завантаження STT моделей...'))
                self.gui_queue.put(('add_message', ('assistant', '🔊 Завантаження STT моделей... зачекайте')))
            print(f"\n{Fore.CYAN}🔊 Завантаження STT моделей...")
            start_time = time.time()

            try:
                self.stt_engine = self.load_stt_model()
                stt_time = time.time() - start_time
                print(f"{Fore.LIGHTBLACK_EX}⏱️  {stt_time:.2f}с")
                if self.gui_queue:
                    print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ✅ STT готовий")
                    self.gui_queue.put(('update_status', f'✅ STT готовий ({stt_time:.1f}с)'))
                    self.gui_queue.put(('add_message', ('assistant', f'✅ STT готовий! ({stt_time:.1f}с)')))
            except Exception as e:
                print(f"{Fore.RED}❌ Не вдалося завантажити модель розпізнавання мови")
                print(f"{Fore.RED}   Деталі: {e}")
                if self.gui_queue:
                    print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ❌ Помилка STT")
                    self.gui_queue.put(('update_status', '❌ Помилка STT'))
                    self.gui_queue.put(('add_message', ('assistant', f'❌ Помилка завантаження STT: {e}')))
                return False
        else:
            print(f"\n{Fore.YELLOW}⏭️  STT вимкнено в налаштуваннях")
            self.stt_engine = None
        
        # Ініціалізація аудіо фільтра
        print(f"\n{Fore.CYAN}🎛️  Ініціалізація аудіо фільтрів...")
        start_time = time.time()
        self.audio_filter = get_audio_filter(SAMPLE_RATE)
        filter_time = time.time() - start_time
        print(f"{Fore.LIGHTBLACK_EX}⏱️  {filter_time:.2f}с")

        # Ініціалізація Self-learning module
        print(f"\n{Fore.CYAN}🧠 Ініціалізація модуля самонавчання...")
        try:
            from functions.self_learning import get_self_learning
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
        
        # Ініціалізація TTS
        self.tts_engine = None
        if TTS_ENABLED:
            if self.gui_queue:
                print(f"{Fore.CYAN}[GUI] Відправка повідомлення: 🔊 Ініціалізація TTS двигуна...")
                self.gui_queue.put(('update_status', '🔊 Ініціалізація TTS двигуна...'))
                self.gui_queue.put(('add_message', ('assistant', '🔊 Ініціалізація TTS двигуна... зачекайте')))
            print(f"\n{Fore.CYAN}🔊 Ініціалізація TTS двигуна...")
            start_time = time.time()

            try:
                self.tts_engine = TTSEngine()
                tts_time = time.time() - start_time
                if self.tts_engine.is_ready:
                    print(f"{Fore.GREEN}✅ TTS двигун готовий")
                    print(f"{Fore.CYAN}   Голоси: {', '.join(self.tts_engine.get_voices())}")
                    print(f"{Fore.CYAN}   Швидкість: {self.tts_engine.speech_rate}")
                    print(f"{Fore.CYAN}   Гучність: {self.tts_engine.volume}")
                    print(f"{Fore.CYAN}   Пристрій: {self.tts_engine.device}")
                    print(f"{Fore.LIGHTBLACK_EX}⏱️  {tts_time:.2f}с")
                    if self.gui_queue:
                        print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ✅ TTS готовий")
                        self.gui_queue.put(('update_status', f'✅ TTS готовий ({tts_time:.1f}с)'))
                        self.gui_queue.put(('add_message', ('assistant', f'✅ TTS готовий! ({tts_time:.1f}с)')))
                else:
                    print(f"{Fore.RED}❌ TTS двигун не готовий")
                    self.tts_engine = None
                    if self.gui_queue:
                        print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ❌ TTS не готовий")
                        self.gui_queue.put(('update_status', '❌ TTS не готовий'))
                        self.gui_queue.put(('add_message', ('assistant', '❌ TTS не готовий')))
            except Exception as e:
                print(f"{Fore.RED}❌ Помилка ініціалізації TTS: {e}")
                import traceback
                traceback.print_exc()
                self.tts_engine = None
                if self.gui_queue:
                    print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ❌ Помилка TTS")
                    self.gui_queue.put(('update_status', '❌ Помилка TTS'))
                    self.gui_queue.put(('add_message', ('assistant', f'❌ Помилка ініціалізації TTS: {e}')))
        else:
            print(f"\n{Fore.YELLOW}⚠️  TTS вимкнено в налаштуваннях")
        
        print(f"\n{Fore.CYAN}🔌 Підключення до LM Studio...")
        if not self.check_lm_studio():
            return False
        
        print(f"\n{Fore.YELLOW}{'='*60}")
        print(f"{Fore.YELLOW}📦 Функцій: {Fore.WHITE}{len(self.registry.functions)}")
        for func_name in self.registry.functions.keys():
            print(f"{Fore.CYAN}   • {func_name}")
        print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
        
        system_prompt = self.registry.get_system_prompt()
        
        # Створити listener лише якщо увімкнено безперервне прослуховування
        if CONTINUOUS_LISTENING_ENABLED:
            print(f"\n{Fore.CYAN}🎧 Створення безперервного слухача...")
            self.listener = create_continuous_listener(
                SAMPLE_RATE, 
                self.audio_filter, 
                MICROPHONE_DEVICE_ID,
                CONTINUOUS_MODE
            )
            if not self.listener:
                print(f"{Fore.RED}❌ Не вдалося створити слухача")
                return False
        else:
            self.listener = None
            return False
        
        # Створити асистента
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

        # передаємо planner в асистента #GPT
        if hasattr(self.assistant, "set_planner"):
            self.assistant.set_planner(self.planner)  #GPT
        
        # Передати listener в TTS
        if self.tts_engine and self.listener:
            self.tts_engine.listener = self.listener
        
        # Встановити TTS двигун в асистента
        if self.tts_engine:
            self.assistant.set_tts_engine(self.tts_engine)
        
        print(f"{Fore.GREEN}✅ Асистент готовий")
        
        return True

    def initialize_without_listener(self):
        """Ініціалізація асистента БЕЗ безперервного прослуховування (текстовий режим)"""
        from colorama import Back, Style
        from functions.logic_core import FunctionRegistry
        from functions.logic_commands import VoiceAssistant
        from functions.logic_audio_filtering import get_audio_filter
        from functions.logic_tts import TTSEngine
        from functions.config import (
            SAMPLE_RATE, TTS_ENABLED, ASSISTANT_NAME, ASSISTANT_EMOJI
        )

        print(f"\n{Back.BLUE} {ASSISTANT_EMOJI} {ASSISTANT_NAME} - Текстовий режим {Style.RESET_ALL}\n")

        # Загальний таймер ініціалізації
        init_start_time = time.time()

        # Реєстр функцій
        print(f"{Fore.CYAN}🔧 Завантаження функцій...")
        self.registry = FunctionRegistry()

        # Перевірка STT
        from functions.core_settings import get_setting
        stt_enabled = get_setting("STT_ENABLED", False)

        if stt_enabled:
            if self.gui_queue:
                print(f"{Fore.CYAN}[GUI] Відправка повідомлення: 🔊 Завантаження STT моделей...")
                self.gui_queue.put(('update_status', '🔊 Завантаження STT моделей...'))
                self.gui_queue.put(('add_message', ('assistant', '🔊 Завантаження STT моделей... зачекайте')))
            print(f"\n{Fore.CYAN}🔊 Завантаження STT...")
            start_time = time.time()
            try:
                self.stt_engine = self.load_stt_model()
                stt_time = time.time() - start_time
                self.stt_load_time = stt_time  # Зберігаємо час завантаження STT
                print(f"{Fore.GREEN}✅ STT готовий")
                if self.gui_queue:
                    print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ✅ STT готовий")
                    self.gui_queue.put(('update_status', f'✅ STT готовий ({stt_time:.1f}с)'))
                    self.gui_queue.put(('add_message', ('assistant', f'✅ STT готовий! ({stt_time:.1f}с)')))
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  STT недоступний: {e}")
                self.stt_engine = None
                if self.gui_queue:
                    print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ❌ Помилка STT")
                    self.gui_queue.put(('update_status', '❌ Помилка STT'))
                    self.gui_queue.put(('add_message', ('assistant', f'❌ Помилка завантаження STT: {e}')))
        else:
            self.stt_engine = None
            print(f"\n{Fore.YELLOW}⏭️  Автозапуск STT вимкнено в налаштуваннях")

        # Аудіо фільтр
        self.audio_filter = get_audio_filter(SAMPLE_RATE)

        # TTS
        self.tts_engine = None
        if TTS_ENABLED:
            if self.gui_queue:
                print(f"{Fore.CYAN}[GUI] Відправка повідомлення: 🔊 Ініціалізація TTS двигуна...")
                self.gui_queue.put(('update_status', '🔊 Ініціалізація TTS двигуна...'))
                self.gui_queue.put(('add_message', ('assistant', '🔊 Ініціалізація TTS двигуна... зачекайте')))
            print(f"\n{Fore.CYAN}🔊 Ініціалізація TTS...")
            start_time = time.time()
            try:
                self.tts_engine = TTSEngine()
                tts_time = time.time() - start_time
                self.tts_load_time = tts_time  # Зберігаємо час завантаження TTS
                if not self.tts_engine.is_ready:
                    self.tts_engine = None
                    if self.gui_queue:
                        print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ❌ TTS не готовий")
                        self.gui_queue.put(('update_status', '❌ TTS не готовий'))
                        self.gui_queue.put(('add_message', ('assistant', '❌ TTS не готовий')))
                else:
                    print(f"{Fore.GREEN}✅ TTS готовий")
                    if self.gui_queue:
                        print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ✅ TTS готовий")
                        self.gui_queue.put(('update_status', f'✅ TTS готовий ({tts_time:.1f}с)'))
                        self.gui_queue.put(('add_message', ('assistant', f'✅ TTS готовий! ({tts_time:.1f}с)')))
                        self.gui_queue.put(('add_message', ('assistant', f'✅ Готовий до роботи! Введіть команду.')))
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  TTS недоступний: {e}")
                self.tts_engine = None
                if self.gui_queue:
                    print(f"{Fore.CYAN}[GUI] Відправка повідомлення: ❌ Помилка TTS")
                    self.gui_queue.put(('update_status', '❌ Помилка TTS'))
                    self.gui_queue.put(('add_message', ('assistant', f'❌ Помилка ініціалізації TTS: {e}')))

        # LM Studio
        print(f"\n{Fore.CYAN}🔌 Підключення до LM Studio...")
        if not self.check_lm_studio():
            return False

        # Listener = None (текстовий режим)
        self.listener = None

        # VoiceAssistant
        system_prompt = self.registry.get_system_prompt()

        def custom_log(sender, message):
            self.log_to_gui(sender, message)

        self.assistant = VoiceAssistant(
            self.stt_engine,
            self.registry,
            system_prompt,
            listener=None,
            gui_log_callback=custom_log
        )

        # --- Planner init --- #GPT
        self.planner = Planner(self.assistant)  #GPT

        if hasattr(self.assistant, "set_planner"):
            self.assistant.set_planner(self.planner)  #GPT

        # --- PlanExecutor init (S2: GUI ↔ TaskRunner bridge) ---
        try:
            from functions.plan_executor import PlanExecutor
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
            from functions.windsurf_watcher_executor import WindsurfWatcherExecutor
            self.windsurf_watcher = WindsurfWatcherExecutor(
                gui_callback=lambda msg_type, data: self.log_to_gui(msg_type, data),
            )
            print(f"{Fore.GREEN}✅ WindsurfWatcherExecutor готовий")
        except Exception as e:
            self.windsurf_watcher = None
            print(f"{Fore.YELLOW}⚠️  WindsurfWatcherExecutor недоступний: {e}")

        # --- Ініціалізація STT контролера для GUI (кнопка мікрофона) ---
        if stt_enabled and self.gui_queue is not None:
            try:
                from functions.core_stt_listener import get_stt_controller
                print(f"\n{Fore.CYAN}🎤 Ініціалізація голосових команд для GUI...")
                stt_controller = get_stt_controller(
                    process_command_callback=self.process_text_command
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

        # --- AgentLoop init (Phase 12.1: observe → plan → act → check) ---
        try:
            from functions.agent_loop import AgentLoop, AgentLoopConfig
            self.agent_loop = AgentLoop(
                assistant=self.assistant,
                registry=self.registry,
                config=AgentLoopConfig(
                    max_steps=50,
                    max_duration_seconds=3600.0,
                    enable_ocr=True,
                ),
            )
            self.agent_loop.gui_cb = lambda msg_type, data: self.log_to_gui(msg_type, data)
            print(f"{Fore.GREEN}✅ AgentLoop готовий")
        except Exception as e:
            self.agent_loop = None
            print(f"{Fore.YELLOW}⚠️  AgentLoop недоступний: {e}")

        # --- TaskSpecCompiler init (S3: TaskSpec → compile() MVP) ---
        try:
            from functions.task_spec import TaskSpecCompiler
            self.task_spec_compiler = TaskSpecCompiler(
                assistant=self.assistant,
                registry=self.registry,
            )
            print(f"{Fore.GREEN}✅ TaskSpecCompiler готовий")
        except Exception as e:
            self.task_spec_compiler = None
            print(f"{Fore.YELLOW}⚠️  TaskSpecCompiler недоступний: {e}")

        if self.tts_engine:
            self.assistant.set_tts_engine(self.tts_engine)

        # --- Ініціалізація STT контролера для GUI (кнопка мікрофона) ---
        if stt_enabled and self.gui_queue is not None:
            try:
                from functions.core_stt_listener import get_stt_controller
                print(f"\n{Fore.CYAN}🎤 Ініціалізація голосових команд для GUI...")
                stt_controller = get_stt_controller(
                    process_command_callback=self.process_text_command
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

        # --- Ініціалізація Global Voice Input (глобальний hook для голосового вводу) ---
        try:
            from functions.core_settings import get_setting
            global_voice_enabled = get_setting("GLOBAL_VOICE_ENABLED", False)
            if global_voice_enabled:
                from functions.global_voice_input import GlobalVoiceInput

                hotkey = get_setting("GLOBAL_VOICE_HOTKEY", "ctrl+shift+v")
                print(f"\n{Fore.CYAN}🎙️  Ініціалізація глобального голосового вводу (hotkey: {hotkey})...")

                def on_voice_text(text: str):
                    """Callback для розпізнаного тексту."""
                    print(f"{Fore.GREEN}🎯 Глобальний голосовий ввод: '{text}'")
                    # Відправити в GUI як команду
                    if self.gui_queue:
                        self.gui_queue.put(('add_message', ('user', text)))
                        self.process_text_command(text)

                def on_voice_status(status: str):
                    """Callback для статусу."""
                    print(f"{Fore.CYAN}   [Global Voice] {status}")

                self.global_voice_input = GlobalVoiceInput(
                    hotkey=hotkey,
                    callback=on_voice_text,
                    status_callback=on_voice_status
                )

                if self.global_voice_input.start():
                    print(f"{Fore.GREEN}✅ Глобальний голосовий вввід запущено")
                else:
                    print(f"{Fore.YELLOW}⚠️  Не вдалося запустити глобальний голосовий вввід")
                    self.global_voice_input = None
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Не вдалося ініціалізувати глобальний голосовий вввід: {e}")
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
        from functions.core_stt_listener import get_stt_controller
        from functions.config import STT_ENABLED

        if STT_ENABLED:
            print(f"\n{Fore.CYAN}🎤 Ініціалізація голосових команд...")
            try:
                stt_controller = get_stt_controller(
                    process_command_callback=self.process_text_command
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
