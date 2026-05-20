# functions/logic_commands.py
"""Обробка команд та VoiceAssistant"""
import threading
import time
from colorama import Fore, Back, Style
from functions.config import LM_STUDIO_URL, TTS_ENABLED, TTS_SPEAK_PREFIXES
from functions.audio.logic_audio import correct_whisper_text, check_activation_word, remove_activation_word
class VoiceAssistant:
    # ... (ініціалізація)
    def __init__(self, stt_engine, registry, system_prompt, listener=None, gui_log_callback=None, context_controller=None):
        self.stt_engine = stt_engine
        self.registry = registry
        self.system_prompt = system_prompt
        self.conversation_history = []
        self.is_listening = True
        self.last_command_time = 0
        self.command_cooldown = 2
        self.listener = listener
        
        # GUI логування
        self.gui_log_callback = gui_log_callback
        
        # ContextController для спільної пам'яті з AgentLoop
        self.context_controller = context_controller
        
        self.planner = None  #GPT
        from ..runtime.core_memory import MemoryManager
        self.memory = MemoryManager()  # довготривала + сесія + задачі
        # Підключаємо LLM-caller для генерації summary
        self.memory.set_llm_caller(self._memory_llm_caller)
        from ..runtime.core_executor import TaskExecutor
        # Створюємо виконавець з колбеком для GUI
        self.executor = TaskExecutor(gui_callback=self.gui_log_callback)
        
        # TTS двигун
        self.tts_engine = None
        self.tts_enabled = TTS_ENABLED
        
        # Отримати core модулі
        self.dispatcher = None
        self.cache_manager = None
        self.streaming_handler = None
        
        dispatcher_module = registry.get_core_module('dispatcher')
        if dispatcher_module:
            self.dispatcher = dispatcher_module.Dispatcher(registry)
            print(f"{Fore.MAGENTA}⚡ Диспетчер активовано")
        # ... решта __init__
        cache_module = registry.get_core_module('cache')
        if cache_module:
            self.cache_manager = cache_module.CacheManager(registry)
            # Статус кешу читається з налаштувань при кожному запиті
            try:
                from ..runtime.core_settings import get_setting
                cache_on = bool(get_setting("CACHE_ENABLED", False))
            except Exception:
                cache_on = False
            status = "УВІМКНЕНО" if cache_on else "ВИМКНЕНО"
            print(f"{Fore.MAGENTA}💾 Кеш: {status} (можна змінити в Налаштуваннях)")
        
        streaming_module = registry.get_core_module('streaming')
        if streaming_module:
            self.streaming_handler = streaming_module.StreamingHandler(LM_STUDIO_URL)
            self.streaming_handler_enabled = True
            print(f"{Fore.MAGENTA}⚡ Стрімінг активовано")
        print(f"{Fore.CYAN}🔊 TTS статус: {'УВІМКНЕНО' if self.tts_enabled else 'ВИМКНЕНО'}")
    
    def log_to_gui(self, sender, message):
        """Відправити повідомлення в GUI"""
        if not message or (isinstance(message, str) and not message.strip()):
            return
        if self.gui_log_callback:
            if sender == "assistant":
                from ..config import TTS_SPEAK_PREFIXES, ASSISTANT_DISPLAY_NAME
                # Видаляємо будь-які префікси, якщо вони вже є
                for prefix in TTS_SPEAK_PREFIXES:
                    if message.strip().startswith(prefix):
                        message = message.strip()[len(prefix):].strip()
                        break
                # Додаємо стандартний префікс
                message = f"{ASSISTANT_DISPLAY_NAME}: {message}"
            
            self.gui_log_callback(sender, message)
        else:
            # Fallback до консолі
            if sender == "user":
                print(f"{Fore.CYAN}👑 ВИ: {Fore.WHITE}{message}")
            else:
                print(f"{Fore.GREEN}{ASSISTANT_DISPLAY_NAME}: {Fore.WHITE}{message}")
    
    def set_tts_engine(self, tts_engine):
        """Встановити TTS двигун"""
        self.tts_engine = tts_engine
        if tts_engine and self.tts_enabled:
            print(f"{Fore.GREEN}✅ TTS двигун встановлено")
        else:
            print(f"{Fore.YELLOW}⚠️  TTS двигун не встановлено або вимкнено")

    def ask_llm(self, prompt: str, minimal: bool = True) -> str:
        """Обгортка для виклику LLM.
        
        Args:
            prompt: Промпт для LLM
            minimal: Якщо True (для Planner), не включає великий system_prompt 
                     та conversation_history — щоб не переповнювати контекст.
        """
        from ..llm import ask_llm
        if minimal:
            # Мінімальний system prompt для планера (без списку функцій — він у prompt)
            minimal_system = "Ти — планувальник. Відповідай тільки JSON без пояснень."
            return ask_llm(prompt, [], minimal_system)
        return ask_llm(prompt, self.conversation_history, self.system_prompt)

    def _is_cache_enabled(self) -> bool:
        """Перевірити, чи дозволено кешування (з user-налаштувань)."""
        if not self.cache_manager:
            return False
        try:
            from ..runtime.core_settings import get_setting
            return bool(get_setting("CACHE_ENABLED", False))
        except Exception:
            return False

    def execute_function(self, action: str, params: dict):
        """Виконати функцію через реєстр (для Planner)."""
        return self.registry.execute_function(action, params)
    
    def set_planner(self, planner):
        """Встановити планувальник"""
        self.planner = planner  #GPT
    
    def should_speak_response(self, response_text):
        """Перевірити, чи потрібно озвучувати відповідь"""
        if not self.tts_enabled or not self.tts_engine or not self.tts_engine.is_ready:
            return False
        
        if not response_text or len(response_text.strip()) == 0:
            return False
            
        return True
    
    def extract_speakable_text(self, response_text):
        """Витягнути текст для озвучення (без префіксів)"""
        clean_text = response_text.strip()
        for prefix in TTS_SPEAK_PREFIXES:
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix):].strip()
        return clean_text

    def filter_code_for_tts(self, text: str) -> str:
        """Видалити код і спец символи для кращого озвучування."""
        import re

        # Видалити кодові блоки (```...```)
        text = re.sub(r'```[\s\S]*?```', '', text)

        # Видалити inline code (`...`)
        text = re.sub(r'`[^`]+`', '', text)

        # Видалити JSON та інші структуровані дані
        text = re.sub(r'\{[\s\S]*?\}', '', text)
        text = re.sub(r'\[[\s\S]*?\]', '', text)

        # Видалити спец символи для коду
        text = re.sub(r'[{}[\]()<>]', '', text)

        # Замінити технічні терміни на прості фрази
        text = text.replace('✅', 'завдання виконано')
        text = text.replace('❌', 'завдання не виконано')
        text = text.replace('⚠️', 'увага')
        text = text.replace('❓', 'питання')

        # Видалити зайві пробіли та переноси рядків
        text = re.sub(r'\s+', ' ', text).strip()

        return text
    
    def speak_response(self, text):
        """Озвучити відповідь (викликається в окремому потоці)"""
        if not self.tts_enabled or not self.tts_engine:
            return

        if self.tts_engine.is_playing:
            print(f"{Fore.YELLOW}⚠️  TTS вже відтворює аудіо, пропускаю")
            return

        # Фільтруємо код і спец символи для кращого озвучування
        text_to_speak = self.filter_code_for_tts(text)

        try:
            success = self.tts_engine.speak(text_to_speak, wait=True)
            if not success:
                print(f"{Fore.RED}❌ Не вдалося озвучити відповідь")
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка озвучення: {e}")
            import traceback
            traceback.print_exc()
    
    def process_command(self, command_text, from_gui=False):
        """Обробити команду"""
        try:
            # Лічильник команд у сесії
            self.memory.session.track_command()

            # ✨ Спочатку обрізаємо стару історію, щоб планер/LLM не отримали overflow
            self._manage_conversation_history()

            # ✨ ЗАВЖДИ додаємо команду в історію ДО будь-якої гілки (planner/LLM/кеш).
            # Це дає planner-у контекст попередніх повідомлень.
            self._history_already_added = False
            if not self.conversation_history or self.conversation_history[-1].get("content") != command_text:
                self.conversation_history.append({"role": "user", "content": command_text})
                self._history_already_added = True

            # Після A0: process_command більше не класифікує task vs chat.
            # Це робиться в main.py:process_text_command → AgentLoop.
            # process_command тут — тільки для STT-вводу (голосовий режим).
            # Якщо команда потребує виконання — main.py:process_text_command
            # спрямує її в AgentLoop.
            from ..config import ASSISTANT_DISPLAY_NAME
            
            print(f"{Fore.CYAN}[DEBUG logic_commands] BEFORE remove_activation_word: command_text='{command_text}', from_gui={from_gui}")
            
            # --- Voice input branch --- (перевіряємо ДО remove_activation_word)
            if command_text.strip().lower().startswith("voice_input"):
                print(f"{Fore.CYAN}🎤 [DEBUG] voice_input команда виявлена, використовуємо AgentLoop")
                if hasattr(self, 'agent_loop') and self.agent_loop:
                    # Використовувати AgentLoop для voice_input
                    print(f"{Fore.CYAN}🎤 [DEBUG] Виклик run_agent_loop для voice_input")
                    result = self.run_agent_loop(command_text)
                    if self.gui_log_callback:
                        self.gui_log_callback("update_status", '✅ Готовий до роботи')
                    return
                else:
                    print(f"{Fore.YELLOW}⚠️ AgentLoop недоступний для voice_input")
            
            # Для GUI команди - пропускаємо перевірку активаційного слова
            if not from_gui:
                # 1. ПЕРЕВІРКА АКТИВАЦІЙНОГО СЛОВА (ТІЛЬКИ ДЛЯ АУДІО)
                if not check_activation_word(command_text):
                    print(f"{Fore.LIGHTBLACK_EX}zzz Ігнорую (немає звертання): '{command_text}'")
                    return
                
                # 2. ВИДАЛЕННЯ АКТИВАЦІЙНОГО СЛОВА (ТІЛЬКИ ДЛЯ АУДІО)
                clean_command = remove_activation_word(command_text)
                
                if not clean_command or len(clean_command.strip()) < 3:
                    print(f"{Fore.YELLOW}⚠️  Звертання є, але команди немає: '{command_text}'")
                    return
                
                command_text = clean_command
            
            print(f"[DEBUG logic_commands] AFTER remove_activation_word: command_text='{command_text}'")

            # Фільтр для простих привітань та питань (не відправляти в LLM)
            greetings = ("привіт", "вітаю", "добрий день", "доброго дня", "вечір добрий", "доброго вечора", "ранок добрий", "доброго ранку", "hello", "hi", "hey")
            simple_questions = (
                "як тебе звати", "як ти називаєшся", "як твоє ім'я", "хто ти", "хто ти такий",
                "what's your name", "what is your name", "who are you"
            )
            command_lower = command_text.strip().lower()
            if command_lower in greetings:
                response = "Привіт! Я готовий допомогти. Що ви хочете зробити?"
                self.log_to_gui("assistant", response)
                if self.should_speak_response(response):
                    speakable_text = self.extract_speakable_text(response)
                    if speakable_text:
                        threading.Thread(
                            target=self.speak_response,
                            args=(speakable_text,),
                            daemon=True
                        ).start()
                return
            elif command_lower in simple_questions:
                response = "Я — голосовий асистент МАРК. Я можу виконувати команди, управляти вікнами, вводити текст, запускати програми та інші дії."
                self.log_to_gui("assistant", response)
                if self.should_speak_response(response):
                    speakable_text = self.extract_speakable_text(response)
                    if speakable_text:
                        threading.Thread(
                            target=self.speak_response,
                            args=(speakable_text,),
                            daemon=True
                        ).start()
                return

            # 3. Логуємо команду в GUI (для всіх типів)
            self.log_to_gui("user", command_text)
            
            print(f"{Fore.CYAN}🎯 {'[GUI] ' if from_gui else '[Аудіо] '}Команда: '{command_text}'")
            
            start_total = time.time()

            # Кеш вимикається для planner-команд (інакше повторна задача підхоплює стару відповідь)
            skip_cache = hasattr(self, "planner") and self.planner and self.planner.should_plan(command_text)

            # Перевірка кешу (тільки якщо увімкнено в налаштуваннях)
            if self._is_cache_enabled() and not skip_cache:
                cached_response, is_cached = self.cache_manager.get(command_text)
                if is_cached and cached_response:
                    print(f"{Fore.CYAN}💾 [Кеш] Використано кешовану відповідь")
                    self.log_to_gui("assistant", cached_response)

                    if self.should_speak_response(cached_response):
                        speakable_text = self.extract_speakable_text(cached_response)
                        if speakable_text:
                            threading.Thread(
                                target=self.speak_response,
                                args=(speakable_text,),
                                daemon=True
                            ).start()
                    
                    print(f"{Fore.LIGHTBLACK_EX}⏱️  0.00с")
                    return
            
            # Швидкий маршрут
            if self.dispatcher:
                quick_result = self.dispatcher.try_quick_route(command_text)
                if quick_result:
                    elapsed = time.time() - start_total
                    print(f"{Fore.YELLOW}⚡ [Швидкий маршрут]")
                    self.log_to_gui("assistant", quick_result)
                    
                    if self.should_speak_response(quick_result):
                        speakable_text = self.extract_speakable_text(quick_result)
                        if speakable_text:
                            threading.Thread(
                                target=self.speak_response,
                                args=(speakable_text,),
                                daemon=True
                            ).start()
                    
                    print(f"{Fore.LIGHTBLACK_EX}⏱️  {elapsed:.2f}с")
                    
                    if self._is_cache_enabled():
                        self.cache_manager.set(command_text, quick_result)  # Кешує тільки idempotent
                    return
            
            # LLM маршрут
            from ..llm import ask_llm, process_llm_response
            from ..core_streaming import StreamingHandler

            # command_text вже додано in conversation_history на початку process_command
            # Підготовка повідомлень для LLM (conversation_history вже містить поточну команду)
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)
            
            # Використовуємо стрімінг, якщо доступний
            full_response = ""
            used_streaming = False
            if self.streaming_handler:
                try:
                    print(f"{Fore.MAGENTA}🤔 [Думаю (стрімінг)...]")
                    if self.gui_log_callback:
                        self.gui_log_callback("update_status", "🤔 Думаю...")
                    start_llm = time.time()
                    used_streaming = True

                    # Не викликаємо stream_start - всі відповіді додаватимуться через log_to_gui
                    # без дублювання префікса "⚡ МАРК:"

                    # Буфер для накопичення тексту перед виведенням
                    buffer_data = {"text": "", "displayed": "", "count": 0}
                    MIN_BUFFER = 180  # ~2-3 речення перед виведенням
                    SENTENCE_END = ('. ', '! ', '? ', '\n')  # Кінці речень (з пробілом)

                    def flush_buffer():
                        """Не виводимо в streaming - всі відповіді додаватимуться через log_to_gui"""
                        pass

                    def on_chunk(chunk_text: str):
                        nonlocal full_response
                        full_response += chunk_text
                        buffer_data["text"] += chunk_text
                        buffer_data["count"] += 1

                        # Перевіряємо чи це JSON - якщо так, не показуємо в streaming
                        temp_text = buffer_data["text"].strip()
                        if temp_text.startswith('{'):
                            # Це JSON - не показуємо в streaming взагалі
                            return

                        # Перевіряємо чи треба flush (кінець речення або накопичено достатньо)
                        should_flush = (
                            buffer_data["text"].rstrip().endswith(SENTENCE_END) or
                            len(buffer_data["text"]) - len(buffer_data["displayed"]) >= MIN_BUFFER
                        )

                        if should_flush and self.gui_log_callback:
                            flush_buffer()

                        # Оновлюємо статус-бар (кожні 10 токенів)
                        if self.gui_log_callback and buffer_data["count"] % 10 == 0:
                            self.gui_log_callback(
                                "update_status",
                                f"🤔 Думаю... ({buffer_data['count']} токенів)",
                            )

                    self.streaming_handler.stream_response_with_callback(messages, on_chunk)

                    # Фінальний flush залишку
                    if buffer_data["text"] and len(buffer_data["text"]) > len(buffer_data["displayed"]):
                        flush_buffer()

                    # Не викликаємо stream_end - всі відповіді додаватимуться через log_to_gui
                    
                    llm_time = time.time() - start_llm
                    
                    if self.gui_log_callback:
                        from ..llm import get_primary_endpoint
                        ep = get_primary_endpoint()
                        llm_name = ep.get("name", "LLM")
                        status_msg = f"✅ {llm_name} ({llm_time:.1f}с)"
                        print(f"[DEBUG] Updating status: {status_msg}")
                        self.gui_log_callback("update_status", status_msg)
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️ Стрімінг не вдався: {e}, використовую звичайний запит")
                    # Fallback на звичайний запит (без вивантаження сирого у чат)
                    start_llm = time.time()  # Встановлюємо start_llm для fallback
                    answer = ask_llm(command_text, self.conversation_history, self.system_prompt)
                    full_response = answer
                    llm_time = time.time() - start_llm
            else:
                # Звичайний запит без стрімінгу
                print(f"{Fore.MAGENTA}🤔 [Думаю...]")
                if self.gui_log_callback:
                    self.gui_log_callback("update_status", "🤔 Думаю...")
                start_llm = time.time()
                answer = ask_llm(command_text, self.conversation_history, self.system_prompt)
                full_response = answer
                llm_time = time.time() - start_llm
                if self.gui_log_callback:
                    from ..llm import get_primary_endpoint
                    ep = get_primary_endpoint()
                    llm_name = ep.get("name", "LLM")
                    self.gui_log_callback("update_status", f"✅ {llm_name} ({llm_time:.1f}с)")

            # Обробка відповіді та виконання функцій
            final_answer = process_llm_response(full_response, self.registry, command_text)

            # Виводимо результат виконання дій в чат
            if final_answer:
                self.log_to_gui("assistant", final_answer)
                
            # Додаємо відповідь до історії
            self.conversation_history.append({"role": "assistant", "content": full_response})
            
            # Озвучення
            if self.should_speak_response(final_answer):
                speakable_text = self.extract_speakable_text(final_answer)
                if speakable_text:
                    threading.Thread(
                        target=self.speak_response,
                        args=(speakable_text,),
                        daemon=True
                    ).start()
            
            # Зберегти в кеш (крім planner-команд, і тільки idempotent)
            if self._is_cache_enabled() and not skip_cache:
                cached = self.cache_manager.set(command_text, final_answer)
                if not cached:
                    print(f"{Fore.LIGHTBLACK_EX}💾 [Кеш] Пропущено (не idempotent)")
            
            elapsed = time.time() - start_total
            print(f"{Fore.LIGHTBLACK_EX}⏱️  {elapsed:.2f}с (LLM: {llm_time:.2f}с)")

            # Адаптивне управління історією діалогу
            self._manage_conversation_history()

        except Exception as e:
            error_msg = f"❌ Помилка: {e}"
            self.log_to_gui("assistant", error_msg)
            print(f"{Fore.RED}{error_msg}")
            import traceback
            traceback.print_exc()

    def _memory_llm_caller(self, prompt: str) -> str:
        """Callable для MemoryManager - безпечний виклик LLM без історії діалогу."""
        try:
            from ..llm import ask_llm
            # Передаємо порожню історію, щоб LLM не плутав контексти
            return ask_llm(prompt, [], "Ти - асистент для підсумків. Відповідай коротко і по суті.")
        except Exception as e:
            print(f"⚠️ _memory_llm_caller помилка: {e}")
            return ""

    def _estimate_tokens(self, messages) -> int:
        """Грубо оцінити к-сть токенів у списку повідомлень (1 токен ≈ 4 символи)."""
        total_chars = 0
        for m in messages:
            content = m.get("content", "") if isinstance(m, dict) else str(m)
            total_chars += len(str(content))
        return total_chars // 4

    def _manage_conversation_history(self, max_messages: int = 2, max_tokens: int = 2000, summarize_threshold: int = 6):
        """Адаптивне управління історією діалогу з підсумовуванням (Sliding Window):
        - обмеження за к-стю повідомлень (max_messages)
        - обмеження за к-стю токенів (max_tokens, gpt-oss має 4000 context)
        - LLM-summary старих повідомлень при великій кількості
        """
        # Перевірка за к-стю повідомлень АБО токенів
        token_count = self._estimate_tokens(self.conversation_history)
        print(f"{Fore.LIGHTBLACK_EX}[DEBUG] Conversation history: {len(self.conversation_history)} messages, ~{token_count} tokens (limit: {max_messages} msgs, {max_tokens} tokens)")
        if len(self.conversation_history) <= max_messages and token_count <= max_tokens:
            return

        # Ковзне вікно з підсумовуванням
        if len(self.conversation_history) > summarize_threshold:
            # Беремо старі повідомлення для підсумовування (крім останніх 2)
            to_summarize = self.conversation_history[:-2]
            try:
                # Формуємо текст діалогу для підсумовування
                dialog_text = "\n".join([
                    f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                    for msg in to_summarize
                ])
                
                # Використовуємо існуючий механізм підсумовування через memory
                summary_text = self.memory.summarize_conversation(to_summarize, max_messages=3)
                
                # Обмежуємо довжину summary
                if len(summary_text) > 500:
                    summary_text = summary_text[:500] + "..."
                
                # Очищуємо і залишаємо факти + 2 останніх повідомлення
                self.conversation_history = [
                    {"role": "system", "content": f"Контекст попередньої розмови: {summary_text}"}
                ] + self.conversation_history[-2:]
                
                print(f"{Fore.LIGHTBLACK_EX}[DEBUG] Conversation summarized, keeping 2 recent messages")
            except Exception as e:
                print(f"{Fore.YELLOW}[WARNING] Failed to summarize conversation: {e}")
                # Fallback: просте обрізання
                self.conversation_history = self.conversation_history[-max_messages:]

        # Обрізаємо до max_messages (якщо ще перевищує)
        if len(self.conversation_history) > max_messages:
            if self.conversation_history and self.conversation_history[0].get("role") == "system":
                self.conversation_history = (
                    [self.conversation_history[0]] + self.conversation_history[-(max_messages - 1):]
                )
            else:
                self.conversation_history = self.conversation_history[-max_messages:]

        # Якщо все ще перевищуємо токен-ліміт — агресивно обрізаємо хвіст
        while self._estimate_tokens(self.conversation_history) > max_tokens and len(self.conversation_history) > 2:
            # Видаляємо найстаріше не-system повідомлення
            removed = False
            for i, msg in enumerate(self.conversation_history):
                if msg.get("role") != "system":
                    del self.conversation_history[i]
                    removed = True
                    break
            if not removed:
                break