# functions/gui/logic_commands.py
"""Маршрутизатор подій GUI — легкий диспетчер, який перенаправляє вхідні події
інтерфейсу до відповідних модулів (commands_streaming, commands_audio, commands_planner).

Не містить бізнес-логіки. Всі складні операції делегуються в спеціалізовані модулі.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional
from colorama import Fore

from functions.config import LM_STUDIO_URL, TTS_ENABLED, ASSISTANT_DISPLAY_NAME

# Делегація в спеціалізовані модулі
from .commands_streaming import stream_llm_response
from .commands_audio import (
    set_tts_engine as _set_tts_engine,
    should_speak_response as _should_speak_response,
    extract_speakable_text as _extract_speakable_text,
    filter_code_for_tts as _filter_code_for_tts,
    speak_response as _speak_response,
    speak_if_possible as _speak_if_possible,
)
from .commands_planner import (
    needs_clarification,
    run_agent_loop_for_voice,
)
from functions.audio.logic_audio import check_activation_word, remove_activation_word


class VoiceAssistant:
    """Голосовий асистент — маршрутизатор подій GUI.

    Публічний API для chat_panel_qt.py та інших UI-компонентів.
    Усі методи зберігають зворотну сумісність.
    Бізнес-логіка делегується в commands_streaming, commands_audio, commands_planner.
    """

    def __init__(self, stt_engine, registry, system_prompt, listener=None,
                 gui_log_callback=None, context_controller=None):
        self.stt_engine = stt_engine
        self.registry = registry
        self.system_prompt = system_prompt
        self.conversation_history = []
        self.is_listening = True
        self.last_command_time = 0
        self.command_cooldown = 2
        self.listener = listener
        self.gui_log_callback = gui_log_callback
        self.context_controller = context_controller
        self.planner = None  # GPT

        from ..runtime.core_memory import MemoryManager
        self.memory = MemoryManager()
        self.memory.set_llm_caller(self._memory_llm_caller)

        from ..runtime.core_executor import TaskExecutor
        self.executor = TaskExecutor(gui_callback=self.gui_log_callback)

        # TTS
        self.tts_engine = None
        self.tts_enabled = TTS_ENABLED

        # Стан для уточнення неоднозначних команд
        self._pending_clarification: Optional[str] = None
        self._skip_clarification: bool = False

        # Callback для AgentLoop (встановлюється ззовні, з main.py)
        self.agent_loop_callback: Optional[Callable[[str], None]] = None

        # Core модулі
        self.dispatcher = None
        self.cache_manager = None
        self.streaming_handler = None
        self.streaming_handler_enabled = False

        dispatcher_module = registry.get_core_module('dispatcher')
        if dispatcher_module:
            self.dispatcher = dispatcher_module.Dispatcher(registry)
            print(f"{Fore.MAGENTA}⚡ Диспетчер активовано")

        cache_module = registry.get_core_module('cache')
        if cache_module:
            self.cache_manager = cache_module.CacheManager(registry)
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

    # ──────────────────────────────────────────────
    # Публічний API — методи для UI-компонентів
    # ──────────────────────────────────────────────

    def log_to_gui(self, sender: str, message: str) -> None:
        """Відправити повідомлення в GUI."""
        if not message or (isinstance(message, str) and not message.strip()):
            return
        if self.gui_log_callback:
            if sender == "assistant":
                from ..config import TTS_SPEAK_PREFIXES
                for prefix in TTS_SPEAK_PREFIXES:
                    if message.strip().startswith(prefix):
                        message = message.strip()[len(prefix):].strip()
                        break
                message = f"{ASSISTANT_DISPLAY_NAME}: {message}"
            self.gui_log_callback(sender, message)
        else:
            if sender == "user":
                print(f"{Fore.CYAN}👑 ВИ: {Fore.WHITE}{message}")
            else:
                print(f"{Fore.GREEN}{ASSISTANT_DISPLAY_NAME}: {Fore.WHITE}{message}")

    def set_tts_engine(self, tts_engine) -> None:
        """Встановити TTS двигун — делегує в commands_audio."""
        _set_tts_engine(self, tts_engine)

    def ask_llm(self, prompt: str, minimal: bool = True) -> str:
        """Обгортка для виклику LLM.

        Args:
            prompt: Промпт для LLM.
            minimal: Якщо True (для Planner), не включає великий system_prompt
                     та conversation_history.
        """
        from ..llm import ask_llm
        if minimal:
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

    def execute_function(self, action: str, params: dict) -> Any:
        """Виконати функцію через реєстр (для Planner)."""
        return self.registry.execute_function(action, params)

    def set_planner(self, planner) -> None:
        """Встановити планувальник."""
        self.planner = planner  # GPT

    def should_speak_response(self, response_text: str) -> bool:
        """Перевірити, чи потрібно озвучувати відповідь — делегує в commands_audio."""
        return _should_speak_response(self.tts_enabled, self.tts_engine)

    def extract_speakable_text(self, response_text: str) -> str:
        """Витягнути текст для озвучення — делегує в commands_audio."""
        return _extract_speakable_text(response_text)

    def filter_code_for_tts(self, text: str) -> str:
        """Видалити код і спец символи для кращого озвучування — делегує в commands_audio."""
        return _filter_code_for_tts(text)

    def speak_response(self, text: str) -> None:
        """Озвучити відповідь — делегує в commands_audio."""
        _speak_response(self.tts_engine, text)

    # ──────────────────────────────────────────────
    # Основний маршрутизатор подій
    # ──────────────────────────────────────────────

    def process_command(self, command_text: str, from_gui: bool = False) -> None:
        """Обробити команду — маршрутизатор подій GUI.

        Перенаправляє:
        - voice_input → commands_planner (AgentLoop)
        - Привітання/прості питання → локальні відповіді
        - LLM-запити → commands_streaming + commands_audio
        """
        try:
            # Лічильник команд
            self.memory.session.track_command()

            # ✨ Адаптивне управління історією
            self._manage_conversation_history()

            # ✨ Додаємо команду в історію
            self._history_already_added = False
            if not self.conversation_history or \
               self.conversation_history[-1].get("content") != command_text:
                self.conversation_history.append({"role": "user", "content": command_text})
                self._history_already_added = True

            # ── 1. Гілка voice_input ────────────────────────
            if command_text.strip().lower().startswith("voice_input"):
                print(f"{Fore.CYAN}🎤 [DEBUG] voice_input команда → AgentLoop")
                if hasattr(self, 'agent_loop') and self.agent_loop:
                    run_agent_loop_for_voice(
                        command_text,
                        agent_loop=self.agent_loop,
                        gui_log_callback=self.gui_log_callback,
                    )
                    if self.gui_log_callback:
                        self.gui_log_callback("update_status", '✅ Готовий до роботи')
                    return
                else:
                    print(f"{Fore.YELLOW}⚠️ AgentLoop недоступний для voice_input")

            # ── 2. Аудіо-гілка: активаційне слово (тільки для голосу) ──
            if not from_gui:
                if not check_activation_word(command_text):
                    print(f"{Fore.LIGHTBLACK_EX}zzz Ігнорую (немає звертання): '{command_text}'")
                    return
                clean_command = remove_activation_word(command_text)
                if not clean_command or len(clean_command.strip()) < 3:
                    print(f"{Fore.YELLOW}⚠️ Звертання є, але команди немає: '{command_text}'")
                    return
                command_text = clean_command

            # ── 3. Перевірка pending clarification ──────────
            if self._pending_clarification is not None:
                # Це відповідь на уточнення — об'єднуємо і виконуємо без перевірки
                command_text = self._pending_clarification + " " + command_text
                self._pending_clarification = None
                self._skip_clarification = True
                print(f"{Fore.CYAN}🔄 [Уточнення] Об'єднано: '{command_text}'")

            # ── 4. Привітання та прості питання ─────────────
            # 🔥 Всі команди йдуть до LLM (навіть привітання)
            # LLM сам вирішить, як відповісти, спираючись на system prompt
            # if self._try_simple_response(command_text):
            #     return

            # ── 5. Перевірка неоднозначності перед LLM ──────
            # Якщо команда неоднозначна — питаємо уточнення замість LLM
            # Після об'єднання (крок 3) — завжди виконуємо без перевірки
            if not self._skip_clarification:
                needs_q, clarification = needs_clarification(command_text)
                if needs_q and clarification:
                    print(f"{Fore.YELLOW}❓ [Уточнення] Команда неоднозначна: '{command_text}'")
                    # Зберігаємо поточну команду як pending
                    self._pending_clarification = command_text
                    # Відправляємо питання в GUI
                    self.log_to_gui("assistant", clarification)
                    self._speak_if_needed(clarification)
                    if self.gui_log_callback:
                        self.gui_log_callback("update_status", "❓ Уточнення...")
                    print(f"{Fore.LIGHTBLACK_EX}❓ Питання: {clarification}")
                    return
            else:
                self._skip_clarification = False

            # ── 6. Логуємо команду в GUI ────────────────────
            # Не дублюємо user-повідомлення — GUI вже додає його через send_text_command
            print(f"{Fore.CYAN}🎯 {'[GUI] ' if from_gui else '[Аудіо] '}Команда: '{command_text}'")

            start_total = time.time()

            # ── 7. Кеш ──────────────────────────────────────
            skip_cache = hasattr(self, "planner") and self.planner and \
                         self.planner.should_plan(command_text)

            if self._is_cache_enabled() and not skip_cache:
                cached_response, is_cached = self.cache_manager.get(command_text)
                if is_cached and cached_response:
                    print(f"{Fore.CYAN}💾 [Кеш] Використано кешовану відповідь")
                    self.log_to_gui("assistant", cached_response)
                    self._speak_if_needed(cached_response)
                    if self.gui_log_callback:
                        self.gui_log_callback("update_status", "💾 Кеш")
                    print(f"{Fore.LIGHTBLACK_EX}⏱️  0.00с (кеш)")
                    return

            # ── 8. Швидкий маршрут (диспетчер) ──────────────
            if self.dispatcher:
                quick_result = self.dispatcher.try_quick_route(command_text)
                if quick_result:
                    elapsed = time.time() - start_total
                    print(f"{Fore.YELLOW}⚡ [Швидкий маршрут]")
                    self.log_to_gui("assistant", quick_result)
                    self._speak_if_needed(quick_result)
                    print(f"{Fore.LIGHTBLACK_EX}⏱️  {elapsed:.2f}с")
                    if self._is_cache_enabled():
                        self.cache_manager.set(command_text, quick_result)
                    return

            # ── 9. LLM-маршрут (стрімінг + обробка) ────────
            self._execute_llm_and_process(command_text, start_total, skip_cache)

        except Exception as e:
            error_msg = f"❌ Помилка: {e}"
            self.log_to_gui("assistant", error_msg)
            if self.gui_log_callback:
                self.gui_log_callback("update_status", error_msg)
            print(f"{Fore.RED}{error_msg}")
            import traceback
            traceback.print_exc()

    # ──────────────────────────────────────────────
    # Внутрішні допоміжні методи (роутинг)
    # ──────────────────────────────────────────────

    def _try_simple_response(self, command_text: str) -> bool:
        """Перевірити, чи команда є простим привітанням/питанням.

        Якщо так — відповісти локально без LLM і повернути True.
        Інакше — повернути False.
        """
        greetings = (
            "привіт", "вітаю", "добрий день", "доброго дня",
            "вечір добрий", "доброго вечора", "ранок добрий", "доброго ранку",
            "hello", "hi", "hey",
        )
        simple_questions = (
            "як тебе звати", "як ти називаєшся", "як твоє ім'я", "хто ти", "хто ти такий",
            "what's your name", "what is your name", "who are you",
        )
        command_lower = command_text.strip().lower()

        if command_lower in greetings:
            response = "Привіт! Я готовий допомогти. Що ви хочете зробити?"
        elif command_lower in simple_questions:
            response = (
                "Я — голосовий асистент МАРК. Я можу виконувати команди, "
                "управляти вікнами, вводити текст, запускати програми та інші дії."
            )
        else:
            return False

        self.log_to_gui("assistant", response)
        self._speak_if_needed(response)
        return True

    def _execute_llm_and_process(
        self,
        command_text: str,
        start_total: float,
        skip_cache: bool,
    ) -> None:
        """Виконати LLM-запит (стрімінг або звичайний) і обробити результат.

        Виділено з process_command для чистоти маршрутизатора.
        """
        from ..llm import ask_llm, process_llm_response

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.conversation_history)

        full_response = ""
        used_streaming = False
        llm_time = 0.0

        # ── Спроба стрімінгу ───────────────────────────────
        if self.streaming_handler:
            try:
                print(f"{Fore.MAGENTA}🤔 [Думаю (стрімінг)...]")
                if self.gui_log_callback:
                    self.gui_log_callback("update_status", "🤔 Думаю...")
                start_llm = time.time()
                used_streaming = True

                full_response = stream_llm_response(
                    streaming_handler=self.streaming_handler,
                    messages=messages,
                    gui_log_callback=self.gui_log_callback,
                )
                llm_time = time.time() - start_llm
                self._update_status_after_llm(llm_time)
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ Стрімінг не вдався: {e}, використовую звичайний запит")
                full_response = self._fallback_llm(command_text)
                used_streaming = True  # ✅ Запобігає подвійному виклику

        # ── Звичайний запит (тільки якщо стрімінг не спрацював) ──
        if not used_streaming:
            print(f"{Fore.MAGENTA}🤔 [Думаю...]")
            if self.gui_log_callback:
                self.gui_log_callback("update_status", "🤔 Думаю...")
            start_llm = time.time()
            answer = ask_llm(command_text, self.conversation_history, self.system_prompt)
            full_response = answer
            llm_time = time.time() - start_llm
            print(f"[DEBUG] _execute_llm_and_process: llm_time={llm_time:.2f}с")
            self._update_status_after_llm(llm_time)

        # ── Обробка відповіді та виконання функцій ──────────
        final_answer = process_llm_response(full_response, self.registry, command_text)

        if final_answer:
            self.log_to_gui("assistant", final_answer)

        # Додаємо відповідь до історії
        self.conversation_history.append({"role": "assistant", "content": full_response})

        # ═══ Перевірка: чи LLM попросив AgentLoop? ═══
        if final_answer and final_answer.startswith("__AGENT_LOOP__:"):
            agent_task = final_answer[len("__AGENT_LOOP__:"):].strip()
            print(f"{Fore.CYAN}🤖 LLM попросив AgentLoop: '{agent_task[:60]}...'")
            if self.agent_loop_callback:
                self.agent_loop_callback(agent_task)
            # Не озвучуємо технічний маркер
            return

        # Озвучення
        self._speak_if_needed(final_answer)

        # Кешування (крім planner-команд і не-idempotent)
        if self._is_cache_enabled() and not skip_cache:
            cached = self.cache_manager.set(command_text, final_answer)
            if not cached:
                print(f"{Fore.LIGHTBLACK_EX}💾 [Кеш] Пропущено (не idempotent)")

        elapsed = time.time() - start_total
        print(f"{Fore.LIGHTBLACK_EX}⏱️  {elapsed:.2f}с (LLM: {llm_time:.2f}с)")

        # Адаптивне управління історією
        self._manage_conversation_history()

    def _fallback_llm(self, command_text: str) -> str:
        """Fallback на звичайний запит LLM (без стрімінгу).
        
        Використовує call_endpoint напряму, щоб уникнути дублювання повідомлень,
        яке виникає при використанні ask_llm (бо conversation_history вже містить command_text).
        """
        from ..llm.endpoint_client import get_primary_endpoint, call_endpoint
        
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.conversation_history)
        
        start_llm = time.time()
        primary = get_primary_endpoint()
        if primary:
            success, result = call_endpoint(primary, messages)
            if success:
                llm_time = time.time() - start_llm
                print(f"[DEBUG] _fallback_llm: llm_time={llm_time:.2f}с")
                self._update_status_after_llm(llm_time)
                return result
        
        # Якщо primary не спрацював — пробуємо через ask_llm (як запасний варіант)
        from ..llm import ask_llm
        answer = ask_llm(command_text, self.conversation_history, self.system_prompt)
        llm_time = time.time() - start_llm
        self._update_status_after_llm(llm_time)
        return answer

    def _update_status_after_llm(self, llm_time: float) -> None:
        """Оновити статус-бар після відповіді LLM."""
        if not self.gui_log_callback:
            print(f"[DEBUG _update_status_after_llm] gui_log_callback is None, time={llm_time:.2f}с")
            return
        try:
            from ..llm import get_primary_endpoint
            ep = get_primary_endpoint()
            llm_name = ep.get("name", "LLM")
            msg = f"📊 LLM: {llm_name} · {llm_time:.1f}с ✅"
            print(f"[DEBUG _update_status_after_llm] sending: '{msg}' via gui_log_callback={self.gui_log_callback.__name__ if hasattr(self.gui_log_callback, '__name__') else 'stream_wrapper'}")
            self.gui_log_callback("update_status", msg)
        except Exception as e:
            print(f"[DEBUG _update_status_after_llm] exception in try: {e}")
            msg = f"📊 LLM: · {llm_time:.1f}с ✅"
            self.gui_log_callback("update_status", msg)

    def _speak_if_needed(self, text: str) -> None:
        """Озвучити текст, якщо TTS увімкнено — делегує в commands_audio.

        Об'єднує should_speak_response + extract_speakable_text + speak_response
        в один виклик через speak_if_possible.
        """
        if not text:
            return
        _speak_if_possible(self.tts_enabled, self.tts_engine, text)

    # ──────────────────────────────────────────────
    # Інші методи (залишаються без змін)
    # ──────────────────────────────────────────────

    def _memory_llm_caller(self, prompt: str) -> str:
        """Callable для MemoryManager — безпечний виклик LLM без історії."""
        try:
            from ..llm import ask_llm
            return ask_llm(
                prompt, [],
                "Ти — асистент для підсумків. Відповідай коротко і по суті.",
            )
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

    def _manage_conversation_history(
        self,
        max_messages: int = None,
        max_tokens: int = None,
        summarize_threshold: int = None,
    ) -> None:
        """Адаптивне управління історією діалогу з підсумовуванням (Sliding Window).

        Ліміти беруться з SETTINGS_SCHEMA (HISTORY_MAX_MESSAGES, HISTORY_MAX_TOKENS),
        якщо не передані явно.

        Виправлено: не обрізаємо історію до 2 повідомлень агресивно.
        Використовуємо ковзне вікно за токенами та підсумовування тільки
        при критичному перевищенні ліміту.
        """
        from ..runtime.core_settings import get_setting
        if max_messages is None:
            max_messages = get_setting("HISTORY_MAX_MESSAGES", 25)
        if max_tokens is None:
            max_tokens = get_setting("HISTORY_MAX_TOKENS", 32000)
        if summarize_threshold is None:
            # Підсумовуємо тільки коли повідомлень значно більше ліміту
            summarize_threshold = max(max_messages * 2, 20)

        token_count = self._estimate_tokens(self.conversation_history)
        token_limit_ratio = token_count / max_tokens if max_tokens > 0 else 0
        print(
            f"{Fore.LIGHTBLACK_EX}[DEBUG] Conversation history: "
            f"{len(self.conversation_history)} messages, "
            f"~{token_count} tokens (limit: {max_messages} msgs, {max_tokens} tokens, "
            f"usage: {token_limit_ratio:.1%})"
        )

        # Якщо і токени, і кількість повідомлень в ліміті — нічого не робимо
        if len(self.conversation_history) <= max_messages and token_count <= max_tokens:
            return

        # ── Підсумовування: тільки якщо токенів > 80% ліміту ─────────────────
        needs_summarize = (
            token_limit_ratio > 0.80
            and len(self.conversation_history) > summarize_threshold
        )

        if needs_summarize:
            # Залишаємо половину ліміту після підсумовування
            keep_after_summary = max(max_messages // 2, 5)
            to_summarize = self.conversation_history[:-keep_after_summary]
            try:
                summary_text = self.memory.summarize_conversation(to_summarize, max_messages=3)
                if len(summary_text) > 800:
                    summary_text = summary_text[:800] + "..."
                self.conversation_history = [
                    {"role": "system", "content": f"Контекст попередньої розмови: {summary_text}"},
                ] + self.conversation_history[-keep_after_summary:]
                print(
                    f"{Fore.LIGHTBLACK_EX}[DEBUG] Conversation summarized, "
                    f"keeping {keep_after_summary} recent messages "
                    f"(tokens: {token_limit_ratio:.1%}). "
                    f"Now {len(self.conversation_history)} msgs."
                )
            except Exception as e:
                print(f"{Fore.YELLOW}[WARNING] Failed to summarize conversation: {e}")
                # Fallback: не чіпаємо історію, просто попереджаємо

        # ── Обрізання за кількістю повідомлень (тільки якщо суттєве перевищення) ──
        if len(self.conversation_history) > max_messages * 1.5:
            if self.conversation_history and self.conversation_history[0].get("role") == "system":
                self.conversation_history = (
                    [self.conversation_history[0]]
                    + self.conversation_history[-(max_messages - 1):]
                )
            else:
                self.conversation_history = self.conversation_history[-max_messages:]

        # ── Обрізання за токенами (тільки коли критично) ──────────────────────
        while self._estimate_tokens(self.conversation_history) > max_tokens and \
              len(self.conversation_history) > 2:
            removed = False
            for i, msg in enumerate(self.conversation_history):
                if msg.get("role") != "system" and i > 0:
                    del self.conversation_history[i]
                    removed = True
                    break
            if not removed:
                # Якщо не вдалося видалити жодного повідомлення — виходимо
                break
