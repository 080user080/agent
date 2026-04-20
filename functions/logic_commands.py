# functions/logic_commands.py
"""Обробка команд та VoiceAssistant"""
import threading
import time
from colorama import Fore, Back, Style
from .config import LM_STUDIO_URL, TTS_ENABLED, TTS_SPEAK_PREFIXES
from .logic_audio import correct_whisper_text, check_activation_word, remove_activation_word
class VoiceAssistant:
    # ... (ініціалізація)
    def __init__(self, stt_engine, registry, system_prompt, listener=None, gui_log_callback=None):
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
        
        self.planner = None  #GPT
        from .core_memory import MemoryManager
        self.memory = MemoryManager()  # довготривала + сесія + задачі
        # Підключаємо LLM-caller для генерації summary
        self.memory.set_llm_caller(self._memory_llm_caller)
        from .core_executor import TaskExecutor
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
                from .core_settings import get_setting
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
        if self.gui_log_callback:
            if sender == "assistant":
                from .config import TTS_SPEAK_PREFIXES, ASSISTANT_DISPLAY_NAME
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
        from .logic_llm import ask_llm
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
            from .core_settings import get_setting
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
    
    def speak_response(self, text):
        """Озвучити відповідь (викликається в окремому потоці)"""
        if not self.tts_enabled or not self.tts_engine:
            return
        
        if self.tts_engine.is_playing:
            print(f"{Fore.YELLOW}⚠️  TTS вже відтворює аудіо, пропускаю")
            return
        
        try:
            success = self.tts_engine.speak(text, wait=True)
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

            # --- Planner branch --- #GPT
            has_planner = hasattr(self, "planner") and self.planner is not None
            should_plan_flag = self.planner.should_plan(command_text) if has_planner else False
            print(f"{Fore.CYAN}🔍 [DEBUG] planner exists: {has_planner}, should_plan: {should_plan_flag}, text: '{command_text[:50]}...'")
            if has_planner and should_plan_flag:
                plan = self.planner.create_plan(command_text)
                if not plan:
                    # LLM не повернув валідний план — можливо помилка API
                    # Примітка: детальна помилка вже залогована в _detect_llm_error
                    print(f"{Fore.YELLOW}⚠️  Виконую напряму без планування...")
                    if self.gui_log_callback:
                        self.gui_log_callback("add_message", (
                            "assistant",
                            "⚠️ **Планер недоступний** — виконую без структурованого плану.\n\n"
                            "_Перевірте налаштування LLM у вкладці 'Налаштування' → 'LLM Ендпоінти'_"
                        ))
                    # Продовжуємо до звичайного LLM блоку нижче (не return!)
                elif plan:
                    is_safe, explanation = self.planner.validate_plan_safety(plan, command_text)
                    if not is_safe:
                        warning_msg = f"⚠️ План може бути небезпечним: {explanation}"
                        self.log_to_gui("assistant", warning_msg)
                        print(f"{Fore.RED}{warning_msg}{Fore.RESET}")
                        return

                    print(f"{Fore.MAGENTA}📋 План: {plan}")
                    # Панель плану сама покаже перелік; у чаті не дублюємо

                    # --- Ініціалізація TaskMemory ---
                    task_id = self.memory.start_task(command_text)
                    self.memory.record_task_plan(plan)
                    print(f"{Fore.CYAN}📝 Задача: {task_id}")

                    context = self.planner.build_execution_context(command_text, plan)

                    def execute_step(step):
                        if self.executor.stop_requested:
                            return {
                                "action": step.get("action"),
                                "status": "stopped",
                                "result": "⏹️ Виконання зупинено користувачем.",
                                "step": step,
                                "context": context.copy(),
                            }

                        prepared_step = self.planner.prepare_step(step, context)
                        action = prepared_step.get("action")
                        args = prepared_step.get("args", {})
                        risk = self.registry.get_tool_risk(action)

                        if risk == "blocked":
                            return {
                                "action": action,
                                "status": "blocked",
                                "result": f"⛔ Дію '{action}' заблоковано політикою безпеки.",
                                "validation": "blocked_by_policy",
                                "step": prepared_step,
                                "context": context.copy(),
                            }

                        # Двозначні дії (ambiguous) теж потребують підтвердження
                        needs_confirm = risk == "confirm_required" or prepared_step.get("requires_confirmation")
                        ambiguous_pattern = prepared_step.get("ambiguous_pattern")

                        if needs_confirm:
                            question = f"Підтвердити дію '{action}'?"
                            if action == "open_program":
                                question = f"Підтвердити відкриття програми '{args.get('program_name', '')}'?"
                            elif action == "close_program":
                                question = f"Підтвердити закриття програми '{args.get('process_name', '')}'?"
                            elif action == "add_allowed_program":
                                question = f"Підтвердити додавання програми '{args.get('program_name', '')}' у whitelist?"

                            if ambiguous_pattern:
                                question = f"⚠️ Двозначна дія (патерн: '{ambiguous_pattern}'). {question}"
                                # ambiguous логуємо у консоль, GUI показує в панелі
                                print(f"{Fore.YELLOW}⚠️ Двозначна дія в кроці '{action}' (патерн: '{ambiguous_pattern}'){Fore.RESET}")

                            # Не дублюємо в чат - панель плану вже показує "needs_confirmation"
                            confirmation_result = self.registry.execute_function(
                                "confirm_action",
                                {"action": action, "question": question},
                            )
                            confirmation_meta = getattr(self.registry, "last_tool_result", None)
                            if not confirmation_meta or not confirmation_meta.get("ok"):
                                return {
                                    "action": action,
                                    "status": "needs_confirmation",
                                    "result": confirmation_result,
                                    "validation": "confirmation_required",
                                    "step": prepared_step,
                                    "context": context.copy(),
                                }

                        # "▶️ Крок" тепер у панелі плану як running
                        print(f"{Fore.CYAN}▶️ Крок: {action}{Fore.RESET}")
                        result = self.registry.execute_function(action, args)
                        success, validation_message = self.planner._validate_step(action, args, result, context)
                        tool_meta = getattr(self.registry, "last_tool_result", None)

                        repair_step = None
                        replanned_steps = None
                        final_result = result
                        final_action = action
                        final_args = args

                        MAX_REPAIR_ATTEMPTS = 3  # Збільшено до 3
                        MAX_REPLAN_ATTEMPTS = 1

                        # === Багатоетапний repair цикл ===
                        if not success and not self.executor.stop_requested:
                            if tool_meta and tool_meta.get("needs_confirmation"):
                                return {
                                    "action": action,
                                    "status": "needs_confirmation",
                                    "result": result,
                                    "validation": validation_message,
                                    "step": prepared_step,
                                    "context": context.copy(),
                                }

                            repair_attempts = 0
                            current_action = action
                            current_args = args
                            current_result = result
                            current_step = prepared_step

                            while not success and repair_attempts < MAX_REPAIR_ATTEMPTS:
                                repair_attempts += 1
                                print(f"{Fore.YELLOW}⚠️ Крок не пройшов перевірку. Repair спроба {repair_attempts}/{MAX_REPAIR_ATTEMPTS}{Fore.RESET}")

                                # Запитуємо repair-стратегію у планера
                                repair_step = self.planner.propose_repair_step(
                                    command_text, current_step, current_result, context
                                )

                                if not repair_step:
                                    print(f"{Fore.YELLOW}⚠️ Планер не запропонував repair-стратегію{Fore.RESET}")
                                    break

                                repaired = self.planner.prepare_step(repair_step, context)
                                new_action = repaired.get("action")
                                new_args = repaired.get("args", {})

                                # Антициклічна перевірка: не повторюємо ідентичний крок
                                if new_action == current_action and new_args == current_args:
                                    print(f"{Fore.YELLOW}⚠️ Repair пропонує ідентичний крок — зупиняю repair{Fore.RESET}")
                                    break

                                # Виконуємо repair-крок
                                print(f"{Fore.CYAN}🔁 Repair-крок: {new_action}{Fore.RESET}")
                                current_action = new_action
                                current_args = new_args
                                current_result = self.registry.execute_function(new_action, new_args)
                                current_step = repaired
                                repair_step = repaired  # Зберігаємо для логу

                                # Перевіряємо результат
                                success, validation_message = self.planner._validate_step(
                                    new_action, new_args, current_result, context
                                )

                                if success:
                                    print(f"{Fore.GREEN}✅ Repair успішний на спробі {repair_attempts}{Fore.RESET}")
                                    break

                            # Оновлюємо фінальні значення після циклу repair
                            final_action = current_action
                            final_args = current_args
                            final_result = current_result
                            prepared_step = current_step

                            # Якщо repair не допоміг — пробуємо replan (один раз)
                            if not success:
                                replan_attempts = context.get("replan_attempts", 0)
                                if replan_attempts < MAX_REPLAN_ATTEMPTS:
                                    context["replan_attempts"] = replan_attempts + 1
                                    print(f"{Fore.MAGENTA}🧭 Repair не вдався, пробую перепланування...{Fore.RESET}")
                                    replanned_steps = self.planner.propose_replan(
                                        command_text, prepared_step, final_result, context, []
                                    )
                                    if replanned_steps:
                                        print(f"{Fore.MAGENTA}✅ Переплановано: додано {len(replanned_steps)} кроків{Fore.RESET}")
                                    else:
                                        print(f"{Fore.YELLOW}⚠️ Перепланування не дало результату{Fore.RESET}")

                        self.planner.update_context_from_result(
                            {"action": final_action, "args": final_args},
                            final_result,
                            context,
                        )

                        step_outcome = {
                            "action": final_action,
                            "status": "ok" if success else "error",
                            "result": final_result,
                            "validation": validation_message,
                            "step": prepared_step,
                            "repair_step": repair_step,
                            "append_steps": replanned_steps or [],
                            "context": context.copy(),
                        }
                        # Записати крок у TaskMemory
                        self.memory.record_task_step(step_outcome)
                        if step_outcome["status"] == "error":
                            self.memory.session.track_error()
                        return step_outcome

                    def on_plan_complete(results):
                        self.memory.update_task(command_text, plan, results)
                        error_count = sum(1 for item in results if isinstance(item, dict) and item.get("status") == "error")
                        blocked_count = sum(1 for item in results if isinstance(item, dict) and item.get("status") == "blocked")
                        confirm_count = sum(1 for item in results if isinstance(item, dict) and item.get("status") == "needs_confirmation")

                        # Визначити фінальний статус задачі
                        if blocked_count:
                            final_status = "aborted"
                        elif error_count:
                            final_status = "error"
                        elif confirm_count:
                            final_status = "cancelled"
                        else:
                            final_status = "success"

                        # Завершити TaskMemory (згенерує LLM summary)
                        self.memory.finish_task(final_status)
                        # Короткий фінальний підсумок у чат (панель показує деталі)
                        if blocked_count:
                            self.log_to_gui("assistant", f"⛔ Зупинено політикою безпеки.")
                        elif confirm_count:
                            self.log_to_gui("assistant", f"❓ Скасовано або не підтверджено.")
                        elif error_count:
                            self.log_to_gui("assistant", f"⚠️ Виконано з помилками.")
                        else:
                            self.log_to_gui("assistant", f"✅ Готово.")

                    self.executor.execute_plan_async(plan, execute_step, on_plan_complete)
                    return
            
            from .config import ASSISTANT_DISPLAY_NAME
            
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
            from .logic_llm import ask_llm, process_llm_response
            from .core_streaming import StreamingHandler

            # command_text вже додано в conversation_history на початку process_command
            # Підготовка повідомлень для LLM (conversation_history вже містить поточну команду)
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)
            
            # Використовуємо стрімінг, якщо доступний
            full_response = ""
            if self.streaming_handler:
                try:
                    print(f"{Fore.MAGENTA}🤔 [Думаю (стрімінг)...]")
                    start_llm = time.time()

                    # Почати streaming в GUI
                    if self.gui_log_callback:
                        self.gui_log_callback("stream_start", None)

                    # Буфер для накопичення тексту перед виведенням
                    buffer_data = {"text": "", "displayed": "", "count": 0}
                    MIN_BUFFER = 180  # ~2-3 речення перед виведенням
                    SENTENCE_END = ('. ', '! ', '? ', '\n')  # Кінці речень (з пробілом)

                    def flush_buffer():
                        """Вивести накопичений буфер в чат."""
                        if buffer_data["text"] and self.gui_log_callback:
                            # Виводимо тільки нову частину
                            new_part = buffer_data["text"][len(buffer_data["displayed"]):]
                            if new_part:
                                self.gui_log_callback("stream_chunk", new_part)
                                buffer_data["displayed"] = buffer_data["text"]

                    def on_chunk(chunk_text: str):
                        nonlocal full_response
                        full_response += chunk_text
                        buffer_data["text"] += chunk_text
                        buffer_data["count"] += 1

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

                    # Завершити streaming в GUI
                    if self.gui_log_callback:
                        self.gui_log_callback("stream_end", None)

                    llm_time = time.time() - start_llm
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️ Стрімінг не вдався: {e}, використовую звичайний запит")
                    # Fallback на звичайний запит (без вивантаження сирого у чат)
                    answer = ask_llm(command_text, self.conversation_history, self.system_prompt)
                    full_response = answer
            else:
                # Звичайний запит без стрімінгу
                print(f"{Fore.MAGENTA}🤔 [Думаю...]")
                if self.gui_log_callback:
                    self.gui_log_callback("update_status", "🤔 Думаю...")
                start_llm = time.time()
                answer = ask_llm(command_text, self.conversation_history, self.system_prompt)
                full_response = answer
                llm_time = time.time() - start_llm

            # Обробка відповіді та виконання функцій
            final_answer = process_llm_response(full_response, self.registry)

            # У чат виводимо ТІЛЬКИ чисту фінальну відповідь (без raw-токенів LLM)
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
            from .logic_llm import ask_llm
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

    def _manage_conversation_history(self, max_messages: int = 6, max_tokens: int = 1200, summarize_threshold: int = 8):
        """Адаптивне управління історією діалогу:
        - обмеження за к-стю повідомлень (max_messages)
        - обмеження за к-стю токенів (max_tokens, gpt-oss має 4000 context)
        - LLM-summary перших N при великій кількості
        """
        # Перевірка за к-стю повідомлень АБО токенів
        token_count = self._estimate_tokens(self.conversation_history)
        if len(self.conversation_history) <= max_messages and token_count <= max_tokens:
            return

        has_summary = any(
            msg.get("role") == "system" and "Summary" in msg.get("content", "")
            for msg in self.conversation_history
        )

        if len(self.conversation_history) > summarize_threshold and not has_summary:
            to_summarize = self.conversation_history[:5]
            try:
                summary_text = self.memory.summarize_conversation(to_summarize, max_messages=5)
            except Exception:
                summary_text = "попередня розмова (автоматично скорочено через обмеження контексту)"

            # Обмежуємо довжину summary, щоб не розрослося
            if len(summary_text) > 500:
                summary_text = summary_text[:500] + "..."

            self.conversation_history = [
                {"role": "system", "content": f"Summary: {summary_text}"}
            ] + self.conversation_history[5:]

        # Обрізаємо до max_messages
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
