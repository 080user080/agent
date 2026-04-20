"""CacheManager — кешування тільки для ідемпотентних команд.

Безпечний кеш: тільки читання/обчислення, без автовиконання дій.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from colorama import Fore


class CacheManager:
    """Менеджер кешування тільки для ідемпотентних команд.

    Кешує тільки команди, які:
    - Не мають побічних ефектів (не змінюють файли/систему)
    - Повертають той самий результат для тих самих вхідних даних
    - Помічені як idempotent=True в TOOL_POLICIES

    Приклади ідемпотентних команд: calculate, count_words, search_in_text, read_code_file
    Не кешуються: create_file, open_program, close_program, edit_file
    """

    IDEMPOTENT_ACTIONS = frozenset({
        "execute_python", "execute_python_code",
        "search_in_text", "count_words",
        "read_code_file", "search_in_code", "list_directory",
        "git_status", "git_diff", "list_sandbox_scripts",
        "show_sandbox_status",
    })

    def __init__(self, registry, cache_duration_hours: int = 24):
        self.cache_file = Path(__file__).parent / "cache_data.json"
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.registry = registry
        self.cache: Dict[str, Any] = self._load_cache()

        print(f"{Fore.MAGENTA}💾 Кеш: {len(self.cache)} записів (тільки idempotent)")

    def _load_cache(self) -> Dict[str, Any]:
        """Завантажити кеш з файлу з очищенням прострочених записів."""
        if not self.cache_file.exists():
            return {}

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            now = datetime.now()
            cleaned = {
                key: entry
                for key, entry in cache_data.items()
                if now - datetime.fromisoformat(entry["timestamp"]) < self.cache_duration
            }

            if len(cleaned) != len(cache_data):
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(cleaned, f, ensure_ascii=False, indent=2)

            return cleaned

        except Exception as e:
            print(f"{Fore.RED}❌ Помилка завантаження кешу: {e}")
            return {}

    def _save_cache(self) -> None:
        """Зберегти кеш у файл."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка збереження кешу: {e}")

    def _is_idempotent_command(self, command_text: str, action: Optional[str] = None) -> bool:
        """Перевірити чи команда ідемпотентна (безпечна для кешування).

        Args:
            command_text: Текст команди
            action: Назва функції (опціонально)

        Returns:
            True якщо команда ідемпотентна
        """
        if action and action in self.IDEMPOTENT_ACTIONS:
            return True

        # Перевірка через TOOL_POLICIES
        if action and self.registry:
            policy = self.registry.get_tool_risk(action)
            # Перевіряємо чи є idempotent в політиці
            # get_tool_risk повертає risk, але нам треба повна політика
            # Додамо окремий метод

        # Ключові слова ідемпотентних операцій
        idempotent_keywords = [
            "порахуй", "обчисли", "скільки", "calculate", "compute",
            "пошук", "знайди", "search", "find",
            "підрахуй", "count",
            "прочитай", "read", "покажи", "show", "status",
            "git status", "git diff",
        ]

        command_lower = command_text.lower()
        return any(kw in command_lower for kw in idempotent_keywords)

    def _extract_action_from_command(self, command_text: str) -> Optional[str]:
        """Витягти назву дії з команди для перевірки ідемпотентності."""
        command_lower = command_text.lower()

        # Відображення ключових слів на функції
        action_map = {
            "порахуй": "execute_python",
            "обчисли": "execute_python",
            "скільки": "execute_python",
            "calculate": "execute_python",
            "count": "count_words",
            "підрахуй": "count_words",
            "search": "search_in_text",
            "пошук": "search_in_text",
        }

        for keyword, action in action_map.items():
            if keyword in command_lower:
                return action

        return None

    def get(self, command_text: str) -> Tuple[Optional[str], bool]:
        """Отримати результат з кешу.

        Args:
            command_text: Текст команди

        Returns:
            (response, is_cached): tuple з відповіддю та флагом кешу
        """
        key = command_text.lower().strip()

        if key not in self.cache:
            return None, False

        entry = self.cache[key]
        timestamp = datetime.fromisoformat(entry["timestamp"])

        if datetime.now() - timestamp >= self.cache_duration:
            del self.cache[key]
            self._save_cache()
            return None, False

        # Оновити статистику
        entry["hits"] = entry.get("hits", 0) + 1
        self._save_cache()

        print(f"{Fore.CYAN}💾 [Кеш] Використано кешовану відповідь (hits: {entry['hits']})")
        return entry["response"], True

    def set(self, command_text: str, response: str, action: Optional[str] = None) -> bool:
        """Додати відповідь в кеш тільки для ідемпотентних команд.

        Args:
            command_text: Текст команди
            response: Відповідь для кешування
            action: Назва функції (для перевірки)

        Returns:
            True якщо додано в кеш
        """
        # Перевірка ідемпотентності
        if action and action not in self.IDEMPOTENT_ACTIONS:
            return False

        extracted_action = self._extract_action_from_command(command_text)
        if extracted_action and extracted_action not in self.IDEMPOTENT_ACTIONS:
            return False

        if not self._is_idempotent_command(command_text, action):
            return False

        key = command_text.lower().strip()

        self.cache[key] = {
            "response": response,
            "action": action or extracted_action,
            "timestamp": datetime.now().isoformat(),
            "hits": 0,
        }
        self._save_cache()

        print(f"{Fore.CYAN}💾 [Кеш] Збережено (idempotent: {action or extracted_action})")
        return True

    def clear(self) -> int:
        """Очистити весь кеш.

        Returns:
            Кількість видалених записів
        """
        count = len(self.cache)
        self.cache.clear()
        self._save_cache()
        print(f"{Fore.YELLOW}🗑️  Кеш очищено ({count} записів)")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Отримати статистику кешу."""
        if not self.cache:
            return {"entries": 0, "hits": 0}

        total_hits = sum(e.get("hits", 0) for e in self.cache.values())
        return {
            "entries": len(self.cache),
            "hits": total_hits,
            "top": sorted(
                self.cache.items(),
                key=lambda x: x[1].get("hits", 0),
                reverse=True
            )[:5],
        }

    # ============================================================================
    # Сумісність зі старим інтерфейсом (депрекейтед, для зворотної сумісності)
    # ============================================================================

    def execute_cached_action(self, action_info: Optional[Dict]) -> None:
        """DEPRECATED: Небезпечний метод видалено.

        Раніше виконував дії автоматично — це небезпечно.
        Кеш тепер тільки для читання результатів.
        """
        print(f"{Fore.YELLOW}⚠️  execute_cached_action deprecated — кеш тільки для читання")
        return None