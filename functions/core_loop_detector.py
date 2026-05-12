"""LoopDetector — виявлення зациклення агента.

Аналізує історію дій на предмет повторів ідентичних операцій.
Якщо агент повторює ту саму дію безрезультатно — вмикається
stuck_warning, який змушує LLM змінити стратегію.

Архітектура:
- LoopDetector тримає ковзне вікно останніх N дій
- Порівняння через action fingerprint (name + canonical args)
- is_looping() → True коли max_repeats однакових дій підряд
- reset() після виявлення — дає шанс новій стратегії
- is_stuck — прапор для decider (передається в stuck_warning)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("loop_detector")


def _action_fingerprint(action: str, args: Dict[str, Any]) -> str:
    """Створити стабільний fingerprint дії для порівняння.

    Нормалізує args через сортування JSON ключів, щоб
    {"x": 1, "y": 2} == {"y": 2, "x": 1}.
    """
    try:
        args_canonical = json.dumps(args, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        args_canonical = str(sorted(args.items()))
    return f"{action}:{args_canonical}"


@dataclass
class LoopEvent:
    """Запис про виявлене зациклення."""
    step: int
    action: str
    fingerprint: str
    repeat_count: int
    message: str


class LoopDetector:
    """Виявляє зациклення агента за повторами ідентичних дій.

    Ковзне вікно останніх `window_size` дій. Якщо всі дії у вікні
    мають однаковий fingerprint — це зациклення.

    Після виявлення:
    1. Встановлюється is_stuck = True
    2. Детектор скидається (reset) — дає шанс новій стратегії
    3. is_stuck передається в decider як stuck_warning
    4. Після успішної дії is_stuck скидається автоматично

    Args:
        max_repeats: Скільки однакових дій підряд = зациклення (default 3)
        window_size: Розмір ковзного вікна (default = max_repeats)
    """

    def __init__(self, max_repeats: int = 3, window_size: Optional[int] = None):
        self.max_repeats = max(2, max_repeats)
        self.window_size = window_size or self.max_repeats
        self._fingerprints: List[str] = []
        self._actions: List[Dict[str, Any]] = []
        self.is_stuck: bool = False
        self.loop_events: List[LoopEvent] = []
        self._total_loops_detected: int = 0
        self.loop_count: int = 0  # Лічильник глобальних зациклень для штрафного ліміту

    def is_looping(self, action: str, args: Dict[str, Any]) -> bool:
        """Перевірити чи поточна дія створює зациклення.

        Додає дію в історію і перевіряє чи всі дії у вікні однакові.

        Args:
            action: Ім'я дії (наприклад 'mouse_click', 'click_text')
            args: Аргументи дії

        Returns:
            True якщо виявлено зациклення
        """
        fp = _action_fingerprint(action, args)
        self._fingerprints.append(fp)
        self._actions.append({"action": action, "args": args})

        # Тримаємо лише window_size записів
        if len(self._fingerprints) > self.window_size:
            self._fingerprints = self._fingerprints[-self.window_size:]
            self._actions = self._actions[-self.window_size:]

        # Якщо вікно ще не заповнене — зациклення немає
        if len(self._fingerprints) < self.max_repeats:
            return False

        # Перевіряємо чи всі fingerprint у вікні однакові
        last_n = self._fingerprints[-self.max_repeats:]
        if all(fp == last_n[0] for fp in last_n):
            self.is_stuck = True
            self._total_loops_detected += 1
            self.loop_count += 1  # Інкрементуємо глобальний лічильник зациклень
            event = LoopEvent(
                step=len(self._actions),
                action=action,
                fingerprint=fp,
                repeat_count=self.max_repeats,
                message=(
                    f"⚠️ Зациклення: дія '{action}' повторюється "
                    f"{self.max_repeats} рази підряд з однаковими аргументами"
                ),
            )
            self.loop_events.append(event)
            logger.warning(event.message)
            print(f"[LoopDetector] {event.message}")
            # Скидаємо після виявлення — даємо шанс новій стратегії
            self.reset()
            return True

        return False

    def on_action_success(self) -> None:
        """Скинути is_stuck після успішної дії."""
        if self.is_stuck:
            self.is_stuck = False
            logger.info("LoopDetector: is_stuck скинуто — дія пройшла успішно")

    def reset(self) -> None:
        """Очистити історію детектора (після виявлення зациклення)."""
        self._fingerprints.clear()
        self._actions.clear()
        # НЕ скидаємо loop_count - це штрафний ліміт для сесії

    def full_reset(self) -> None:
        """Повне скидання для нової сесії."""
        self.reset()
        self.is_stuck = False
        self.loop_events.clear()
        self._total_loops_detected = 0
        self.loop_count = 0  # Скидаємо тільки при повному скиданні

    def should_force_fallback(self) -> bool:
        """Перевірити чи треба примусово перейти в fallback.

        Якщо зациклився вже двічі за одну сесію — негайно в fallback.

        Returns:
            True якщо треба примусово перейти в fallback
        """
        return self.loop_count >= 2

    @property
    def total_loops_detected(self) -> int:
        """Скільки разів зациклення було виявлено загалом."""
        return self._total_loops_detected

    def get_stuck_warning_message(self) -> str:
        """Повернути текст попередження для LLM промпту.

        Використовується коли is_stuck=True, щоб змусити модель
        змінити стратегію.
        """
        if not self.is_stuck:
            return ""

        last_event = self.loop_events[-1] if self.loop_events else None
        action_desc = f"'{last_event.action}'" if last_event else "останньої дії"
        repeat_count = last_event.repeat_count if last_event else self.max_repeats

        # Специфічна інструкція для list_directory
        if last_event and last_event.action == "list_directory":
            return (
                f"\n\n🚨 КРИТИЧНЕ ЗАУВАЖЕННЯ: Ти {repeat_count} разів поспіль викликав list_directory "
                f"без зміни вмісту папки. Папка НЕ ЗМІНИЛАСЯ. "
                f"ПЕРЕСТАНЬ ПЕРЕВІРЯТИ! Якщо файлу немає — СТВОРИ ЙОГО через write_file. "
                f"Не шукай файли, яких ще не створив — створи їх сам!"
            )

        return (
            f"\n\n🚨 КРИТИЧНЕ ЗАУВАЖЕННЯ: Ти щойно намагався виконати "
            f"дію {action_desc} {repeat_count} рази поспіль безрезультатно. "
            f"Цей метод НЕ ПРАЦЮЄ. Твоя наступна дія МАЄ бути іншою. "
            f"Спробуй інший шлях: використай іншу кнопку, гарячі клавіші, "
            f"пошук, зміни вікно або звернись до користувача через ask_user."
        )

    def get_loop_advice(self, action: Dict[str, Any]) -> str:
        """Повернути конкретну пораду для LLM на основі типу дії.

        Використовується коли LoopDetector виявив зациклення,
        щоб дати LLM зрозуміти ЧОМУ воно сталось і що робити замість цього.

        Args:
            action: Словник дії з ключами 'action' та 'args'

        Returns:
            Порада для LLM у вигляді рядка
        """
        action_name = action.get('action', '')
        args = action.get('args', {})

        if action_name == 'list_directory':
            return (
                "УВАГА: Ти вже тричі перевіряв цю папку. Вміст НЕ ЗМІНИВСЯ. "
                "Припини перевіряти список файлів. Якщо ти не бачиш потрібного файлу — "
                "це означає, що його НЕ ІСНУЄ, і ти маєш його СТВОРИТИ прямо зараз."
            )
        elif action_name == 'read_code_file':
            filepath = args.get('filepath', '')
            return (
                f"УВАГА: Ти вже читав файл '{filepath}' кілька разів. "
                f"Його вміст не зміниться, якщо ти його не зміниш. "
                f"Якщо тобі потрібно змінити файл — використай 'edit_file' або 'write_file'. "
                f"Якщо ти шукаєш щось інше — перерахуй аргументи функції."
            )
        elif action_name == 'execute_python' or action_name == 'oi_execute_with_healing':
            return (
                "УВАГА: Ти запускаєш той самий код повторно. "
                "Якщо код не працює — ЗМІНИ його, а не запускай знову. "
                "Додай print-и для діагностики, або перероби логіку."
            )
        elif action_name in ('take_screenshot', 'ocr_screen'):
            return (
                "УВАГА: Ти робиш скріншот екрану повторно, але нічого не змінюється. "
                "Екран залишається тим самим. Припини спостерігати — ПОЧНИ ДІЯТИ. "
                "Якщо не знаєш що робити — використай ask_user."
            )
        else:
            return (
                "Ти зациклився. Спробуй інший підхід. "
                "Зупинись, подумай, яка дійсно корисна дія зараз змінить стан системи."
            )

    def get_correction_hint(self, action_name: str) -> str:
        """Повернути "силову інструкцію" для впорскування в історію чату при виявленні циклу.

        Використовується коли LoopDetector виявив зациклення,
        щоб дати LLM більш категоричну інструкцію для виходу з циклу.

        Args:
            action_name: Назва дії, на якій зациклився агент

        Returns:
            Категорична інструкція для LLM
        """
        if action_name == 'list_directory':
            return (
                "УВАГА: Ти вже перевіряв цю папку 3 рази. Вміст не зміниться сам по собі! "
                "ПРИПИНИ викликати list_directory. Якщо файлу немає у списку — "
                "це означає, що його НЕМАЄ на диску. Твоя наступна дія МАЄ БУТИ write_file."
            )
        elif action_name == 'read_code_file':
            return (
                "УВАГА: Ти читаєш той самий файл повторно. Його вміст не зміниться. "
                "ПРИПИНИ читати! Твоя наступна дія МАЄ БУТИ write_file або edit_file."
            )
        elif action_name == 'execute_python' or action_name == 'oi_execute_with_healing':
            return (
                "УВАГА: Ти запускаєш той самий код повторно і він не працює. "
                "ПРИПИНИ запускати! Твоя наступна дія МАЄ БУТИ зміна коду, а не повторний запуск."
            )
        elif action_name in ('take_screenshot', 'ocr_screen'):
            return (
                "УВАГА: Ти робиш скріншот повторно, але екран не змінюється. "
                "ПРИПИНИ спостерігати! Твоя наступна дія МАЄ БУТИ дія, яка змінює стан."
            )
        return "Зміни стратегію, поточна дія неефективна."

    def get_stats(self) -> Dict[str, Any]:
        """Статистика детектора."""
        return {
            "is_stuck": self.is_stuck,
            "total_loops_detected": self._total_loops_detected,
            "window_size": self.window_size,
            "max_repeats": self.max_repeats,
            "current_window_length": len(self._fingerprints),
            "loop_events_count": len(self.loop_events),
        }


__all__ = ["LoopDetector", "LoopEvent", "_action_fingerprint"]
