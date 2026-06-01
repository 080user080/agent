"""Act — фаза виконання дій агента: виклик інструментів, безпекові обмеження.

Phase 12.1 / Крок 2.3. Виділення шару виконання функцій, виклику інструментів
та безпекових обмежень з AgentLoop у власний модуль.

Відповідальність:
- Мапінг відповідей моделі на функції репозиторію
- Трекери лімітів дій (ідемпотентність write_file, блокування повторів)
- Захисне блокування небезпечних операцій Windows
- Перехоплення OS-помилок і трансляція в текстовий звіт для ШІ
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("act")


@dataclass
class ActionGuardConfig:
    """Конфігурація захисних механізмів виконання дій.

    Attributes:
        enable_write_fingerprint_blocking: Блокувати повторні ідентичні write_file
        enable_list_directory_guard: Блокувати повторний list_directory без write_file
        enable_failed_reads_guard: Блокувати повторне читання неіснуючих файлів
        enable_execute_python_target_tracking: Трекати write_targets у execute_python
    """
    enable_write_fingerprint_blocking: bool = True
    enable_list_directory_guard: bool = True
    enable_failed_reads_guard: bool = True
    enable_execute_python_target_tracking: bool = True


class ActionGuard:
    """Безпековий прошарок для контролю виконання дій агента.

    Інкапсулює всі механізми захисного блокування та трекінгу лімітів дій:
    - Блокування повторних write_file (ідемпотентність)
    - Блокування повторного читання неіснуючих файлів
    - Блокування повторного list_directory (A-B-A-B цикл)
    - Трекінг write_targets у execute_python
    - Запам'ятовування відсутніх файлів

    Кожен виклик локального інструменту перехоплює внутрішні OS-помилки
    й транслює їх у текстовий звіт для ШІ.
    """

    def __init__(self, config: Optional[ActionGuardConfig] = None):
        self.config = config or ActionGuardConfig()

        # Блокування повторних ідентичних write_file
        self._blocked_write_fingerprints: Set[str] = set()
        self._execute_python_write_targets: Set[str] = set()

        # Пам'ять про відсутні файли (для A-B-A-B циклів)
        self.failed_reads: Set[str] = set()

        # Чи був викликаний list_directory хоч раз (для заборони другого)
        self._list_directory_used: bool = False
        # Останній результат list_directory (файли)
        self._last_list_dir_files: List[str] = []
        # Чи був хоч один write_file після list_directory
        self._has_written_since_list_dir: bool = False

    # ─── Helper: extract python write targets ──────────────────────────────────

    @staticmethod
    def extract_python_write_targets(code: str) -> List[str]:
        """Best-effort detection of files written by generated Python code."""
        import os

        targets: List[str] = []
        patterns = [
            r"open\(\s*r?['\"]([^'\"]+)['\"]\s*,\s*['\"][^'\"]*w",
            r"with\s+open\(\s*r?['\"]([^'\"]+)['\"]\s*,\s*['\"][^'\"]*w",
            r"Path\(\s*r?['\"]([^'\"]+)['\"]\s*\)\.write_text\(",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, code, flags=re.IGNORECASE | re.DOTALL):
                path = match.group(1).strip()
                if path:
                    targets.append(os.path.normcase(os.path.abspath(path)))
        return sorted(set(targets))

    # ─── Core: execute action via registry ─────────────────────────────────────

    def execute(
        self,
        registry: Any,
        action: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Безпечно виконати дію через репозиторій.

        Перехоплює внутрішні OS-помилки й транслює їх у текстовий звіт для ШІ.

        Args:
            registry: FunctionRegistry для виконання функцій
            action: Назва дії
            args: Аргументи дії

        Returns:
            dict з ключами 'ok', 'result'/'error'
        """
        if action == "noop":
            return {"ok": True, "result": "noop"}

        try:
            result = registry.execute_function(action, args, auto_create=False)
            if isinstance(result, dict):
                return result
            return {"ok": True, "result": str(result)}
        except OSError as e:
            # Внутрішні OS-помилки → текстовий звіт для ШІ
            logger.error("OS error in action '%s': %s", action, e)
            return {
                "ok": False,
                "error": f"Системна помилка операційної системи: {e}",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Guards: pre-execution checks ──────────────────────────────────────────

    def check_read_file_guard(
        self,
        action: str,
        args: Dict[str, Any],
        gui_cb=None,
    ) -> Optional[Dict[str, Any]]:
        """Заблокувати повторне читання неіснуючого файлу.

        Args:
            action: Назва дії
            args: Аргументи дії
            gui_cb: Колбек для відправки повідомлень в GUI

        Returns:
            None якщо guard пропустив дію,
            dict-результат якщо дію заблоковано
        """
        if not self.config.enable_failed_reads_guard:
            return None
        if action != "read_code_file":
            return None

        filepath = args.get('filepath', '')
        if filepath in self.failed_reads:
            logger.warning("Блоковано повторне читання неіснуючого файлу: %s", filepath)
            if gui_cb:
                gui_cb('add_message', (
                    'assistant',
                    f'⛔ ПОМИЛКА КРИТИЧНА: Файл {filepath} вже був не знайдено. '
                    'ВІН НЕ З\'ЯВИТЬСЯ САМ. Тобі ЗАБОРОНЕНО читати його знову. '
                    'Негайно використай write_file, щоб СТВОРИТИ його.',
                ))
            return {
                "ok": False,
                "error": f"Файл {filepath} вже був не знайдено, читання заблоковано",
            }
        return None

    def check_list_directory_guard(
        self,
        action: str,
        args: Dict[str, Any],
        actions_history: List[Dict[str, Any]],
        gui_cb=None,
    ) -> Optional[Dict[str, Any]]:
        """Заблокувати повторний list_directory.

        Правила:
        1. Якщо list_directory вже викликаний, а write_file ще не було — блок.
        2. Якщо list_directory викликано >=2 рази за останні 4 кроки — блок.

        Args:
            action: Назва дії
            args: Аргументи дії
            actions_history: Історія дій для перевірки A-B-A-B циклів
            gui_cb: Колбек для відправки повідомлень в GUI

        Returns:
            None якщо guard пропустив дію,
            dict-результат якщо дію заблоковано
        """
        if not self.config.enable_list_directory_guard:
            return None
        if action != "list_directory":
            return None

        # list_directory вже викликаний, а write_file ще не було — БЛОКУЄМО
        if self._list_directory_used and not self._has_written_since_list_dir:
            logger.warning(
                "СУВОРО Блоковано повторний list_directory (ще не було write_file)"
            )
            if gui_cb:
                gui_cb('add_message', (
                    'assistant',
                    '⛔ КРИТИЧНА ПОМИЛКА: Ти ВЖЕ викликав list_directory. '
                    'Вміст папки НЕ ЗМІНИТЬСЯ, поки ти не створиш файл. '
                    'Твоя наступна дія МАЄ БУТИ write_file. '
                    'ЗАБОРОНЕНО викликати list_directory знову без write_file!',
                ))
            return {
                "ok": False,
                "error": "Повторний list_directory без write_file заблоковано",
            }

        # Рахуємо, скільки разів викликано list_directory за останні 4 кроків
        recent_actions = [a.get('action') for a in actions_history[-4:]]
        if recent_actions.count('list_directory') >= 2:
            logger.warning("Блоковано повторний list_directory (A-B-A-B цикл)")
            if gui_cb:
                gui_cb('add_message', (
                    'assistant',
                    '⛔ ПОМИЛКА: Ти вже двічі перевіряв папку за останні кроки. '
                    'Досить спостерігати! Почни створювати відсутні файли (write_file).',
                ))
            return {
                "ok": False,
                "error": "Повторний list_directory заблоковано",
            }
        return None

    def check_write_file_guard(
        self,
        action: str,
        args: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Заблокувати повторний write_file (ідемпотентна операція).

        Створює fingerprint на основі filepath + content.
        Якщо такий самий write_file вже виконувався — повертає ok.

        Args:
            action: Назва дії
            args: Аргументи дії

        Returns:
            None якщо guard пропустив дію,
            dict-результат якщо дію заблоковано (ok=True, "already written")
        """
        if not self.config.enable_write_fingerprint_blocking:
            return None
        if action != "write_file":
            return None

        # Створюємо fingerprint для порівняння
        try:
            fp = (
                f"write_file:{args.get('filepath', '')}:"
                f"{json.dumps(args.get('content', ''), sort_keys=True)}"
            )
        except Exception:
            fp = (
                f"write_file:{args.get('filepath', '')}:"
                f"{str(args.get('content', ''))}"
            )

        if fp in self._blocked_write_fingerprints:
            logger.info(
                "Ідемпотентний write_file пропущено: %s",
                args.get('filepath', ''),
            )
            return {
                "ok": True,
                "result": "already written, skipped",
            }
        return None

    def check_execute_python_guard(
        self,
        action: str,
        args: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Заблокувати повторний execute_python для тих самих write_targets.

        Аналізує код на write_targets, порівнює з попередніми.
        Якщо знаходить повтор — повертає ok з інформацією про пропуск.

        Args:
            action: Назва дії
            args: Аргументи дії

        Returns:
            None якщо guard пропустив дію,
            dict-результат якщо дію заблоковано (ok=True, "repeated skipped")
        """
        if not self.config.enable_execute_python_target_tracking:
            return None
        if action != "execute_python":
            return None

        code = str(args.get("code", "") or "")
        write_targets = self.extract_python_write_targets(code)
        repeated_targets = [
            t for t in write_targets if t in self._execute_python_write_targets
        ]
        if repeated_targets:
            target_list = ", ".join(repeated_targets)
            logger.info(
                "Repeated execute_python file write skipped: %s", target_list
            )
            return {
                "ok": True,
                "result": (
                    f"repeated execute_python file write skipped: {target_list}"
                ),
            }

        # Якщо не заблоковано — оновлюємо write_targets
        self._execute_python_write_targets.update(write_targets)
        return None

    # ─── Run all guards in order (convenience) ─────────────────────────────────

    def run_guards(
        self,
        action: str,
        args: Dict[str, Any],
        actions_history: List[Dict[str, Any]],
        gui_cb=None,
    ) -> Optional[Dict[str, Any]]:
        """Запустити всі pre-execution guards по порядку.

        Args:
            action: Назва дії
            args: Аргументи дії
            actions_history: Історія дій для перевірки A-B-A-B циклів
            gui_cb: Колбек для відправки повідомлень в GUI

        Returns:
            None якщо всі guards пропустили дію,
            dict-результат першого guard'а що спрацював
        """
        # Guard 1: read_file
        result = self.check_read_file_guard(action, args, gui_cb=gui_cb)
        if result is not None:
            return result

        # Guard 2: list_directory
        result = self.check_list_directory_guard(action, args, actions_history, gui_cb=gui_cb)
        if result is not None:
            return result

        # Guard 3: write_file (ідентичний вміст)
        result = self.check_write_file_guard(action, args)
        if result is not None:
            return result

        # Guard 4: execute_python (повторні write targets)
        result = self.check_execute_python_guard(action, args)
        if result is not None:
            return result

        # Всі guards пропустили
        return None

    # ─── Post-execution state updates ──────────────────────────────────────────

    def update_after_action(
        self,
        action: str,
        args: Dict[str, Any],
        act_result: Dict[str, Any],
    ) -> str:
        """Оновити стан guard'ів після виконання дії.

        Args:
            action: Назва дії яка була виконана
            args: Аргументи дії
            act_result: Результат виконання дії

        Returns:
            str — рядок прогресу (progress_line), порожній рядок якщо не потрібен
        """
        progress_line = ""

        # Зберігаємо результат list_directory для контексту
        if action == "list_directory" and act_result.get("ok"):
            self._list_directory_used = True
            result = act_result.get('result', '')
            if isinstance(result, str):
                self._last_list_dir_files = [
                    f.strip()
                    for f in result.split('\n')
                    if f.strip() and not f.startswith('[')
                ]
            elif isinstance(result, list):
                self._last_list_dir_files = [str(f) for f in result]
            else:
                self._last_list_dir_files = []
            logger.info(
                "ActionGuard: list_directory збережено (%d файлів)",
                len(self._last_list_dir_files),
            )

        # Автоматичний прогрес після write_file / edit_file
        if action in ("write_file", "edit_file") and act_result.get("ok"):
            if action == "write_file":
                self._has_written_since_list_dir = True
                try:
                    fp = (
                        f"write_file:{args.get('filepath', '')}:"
                        f"{json.dumps(args.get('content', ''), sort_keys=True)}"
                    )
                except Exception:
                    fp = (
                        f"write_file:{args.get('filepath', '')}:"
                        f"{str(args.get('content', ''))}"
                    )
                self._blocked_write_fingerprints.add(fp)

            filepath = args.get('filepath', '') or args.get('filename', '')
            filename = (
                filepath.split('/')[-1].split('\\')[-1]
                if filepath
                else 'unknown'
            )
            progress_line = f"✅ Створено: {filename}"
            logger.info("ActionGuard: додано прогрес: %s", progress_line)

        # Запам'ятовуємо відсутні файли
        if action == "read_code_file" and not act_result.get("ok"):
            result_str = str(
                act_result.get('error', '') + str(act_result.get('result', ''))
            )
            if (
                "Файл не знайдено" in result_str
                or "не існує" in result_str
                or "No such file" in result_str
            ):
                filepath = args.get('filepath', '')
                self.failed_reads.add(filepath)
                logger.info("Запам'ятовано відсутній файл: %s", filepath)

        return progress_line

    # ─── Reset for new session ─────────────────────────────────────────────────

    def reset(self):
        """Скинути всі стани guard'ів для нової сесії виконання."""
        self._blocked_write_fingerprints.clear()
        self._execute_python_write_targets.clear()
        self.failed_reads.clear()
        self._list_directory_used = False
        self._last_list_dir_files = []
        self._has_written_since_list_dir = False

    # ─── Properties for external access ────────────────────────────────────────

    @property
    def list_directory_used(self) -> bool:
        """Чи був хоч раз викликаний list_directory."""
        return self._list_directory_used

    @property
    def last_list_dir_files(self) -> List[str]:
        """Останній результат list_directory."""
        return self._last_list_dir_files

    @property
    def has_written_since_list_dir(self) -> bool:
        """Чи був write_file після list_directory."""
        return self._has_written_since_list_dir


__all__ = [
    "ActionGuard",
    "ActionGuardConfig",
]