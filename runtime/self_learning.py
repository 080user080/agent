"""Self-Learning Module — логування, аналіз помилок, skills база.

Збирає логи виконання задач, аналізує помилки за допомогою LLM,
генерує правила для майбутнього використання.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class SelfLearning:
    """Модуль самонавчання — аналіз помилок та накопичення skills."""

    def __init__(self, data_dir: str = None):
        """
        Args:
            data_dir: Директорія для зберігання логів та skills (default: runtime/self_learning)
        """
        if data_dir is None:
            # runtime/self_learning в корені проекту (runtime/self_learning.py → agent/)
            project_root = Path(__file__).parent.parent
            self.data_dir = project_root / "runtime" / "self_learning"
        else:
            self.data_dir = Path(data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.logs_file = self.data_dir / "execution_logs.jsonl"
        self.skills_file = self.data_dir / "skills.json"
        self.rules_file = self.data_dir / "rules.json"

        # Завантажити існуючі skills та rules
        self.skills: Dict[str, Any] = self._load_json(self.skills_file, {})
        self.rules: List[Dict[str, Any]] = self._load_json(self.rules_file, [])

    def _load_json(self, file_path: Path, default: Any) -> Any:
        """Завантажити JSON файл."""
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Помилка завантаження {file_path}: {e}")
        return default

    def _save_json(self, file_path: Path, data: Any) -> None:
        """Зберегти JSON файл."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  Помилка збереження {file_path}: {e}")

    def log_execution(
        self,
        task: str,
        result: str,
        success: bool,
        error: Optional[str] = None,
        steps: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Залогувати виконання задачі.

        Args:
            task: Опис задачі
            result: Результат виконання
            success: Чи успішно виконано
            error: Текст помилки (якщо є)
            steps: Список кроків виконання
            metadata: Додаткові метадані
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "result": result,
            "success": success,
            "error": error,
            "steps": steps or [],
            "metadata": metadata or {},
        }

        # Додати в JSONL (append-only)
        with open(self.logs_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

        print(f"📝 Logged execution: success={success}, task='{task[:50]}...'")

    def analyze_errors(self, limit: int = 10) -> List[Dict]:
        """Аналіз останніх помилок.

        Args:
            limit: Кількість останніх записів для аналізу

        Returns:
            Список помилок з додатковою інформацією
        """
        if not self.logs_file.exists():
            return []

        errors = []
        with open(self.logs_file, 'r', encoding='utf-8') as f:
            for line in f:
                entry = json.loads(line)
                if not entry.get("success") and entry.get("error"):
                    errors.append(entry)
                    if len(errors) >= limit:
                        break

        return errors

    def generate_rules_from_errors(self, llm_client=None) -> List[Dict]:
        """Генерувати правила з помилок за допомогою LLM.

        Args:
            llm_client: LLM клієнт для аналізу (опціонально)

        Returns:
            Список згенерованих правил
        """
        errors = self.analyze_errors(limit=5)
        if not errors:
            print("📊 Немає помилок для аналізу")
            return []

        if llm_client is None:
            # Простий heuristic аналіз без LLM
            return self._heuristic_rules(errors)

        # LLM аналіз
        prompt = self._build_analysis_prompt(errors)
        try:
            response = llm_client.generate(prompt)
            rules = self._parse_rules_from_response(response)
            return rules
        except Exception as e:
            print(f"⚠️  Помилка LLM аналізу: {e}")
            return self._heuristic_rules(errors)

    def _heuristic_rules(self, errors: List[Dict]) -> List[Dict]:
        """Heuristic генерація правил без LLM."""
        rules = []

        # Аналіз error messages
        error_patterns = {}
        for entry in errors:
            error = entry.get("error", "")
            if "not found" in error.lower() or "не знайдено" in error.lower():
                error_patterns["element_not_found"] = error_patterns.get("element_not_found", 0) + 1
            if "timeout" in error.lower():
                error_patterns["timeout"] = error_patterns.get("timeout", 0) + 1
            if "permission" in error.lower():
                error_patterns["permission"] = error_patterns.get("permission", 0) + 1

        # Генеруємо правила на основі патернів
        if error_patterns.get("element_not_found", 0) > 1:
            rules.append({
                "condition": "element_not_found",
                "action": "scroll_and_search",
                "description": "Якщо елемент не знайдено — прокрутити і повторити пошук",
                "priority": "high",
                "confidence": 0.8,
            })

        if error_patterns.get("timeout", 0) > 1:
            rules.append({
                "condition": "timeout",
                "action": "increase_timeout",
                "description": "Якщо timeout — збільшити час очікування",
                "priority": "medium",
                "confidence": 0.7,
            })

        return rules

    def _build_analysis_prompt(self, errors: List[Dict]) -> str:
        """Побудувати prompt для LLM аналізу."""
        prompt = "Аналізуй наступні помилки виконання задач і запропонуй правила для уникнення їх у майбутньому.\n\n"
        prompt += "Формат правил: JSON список з полями: condition, action, description, priority (high/medium/low).\n\n"
        prompt += "Помилки:\n"

        for i, entry in enumerate(errors, 1):
            prompt += f"{i}. Task: {entry.get('task')}\n"
            prompt += f"   Error: {entry.get('error')}\n"
            prompt += f"   Steps: {entry.get('steps', [])}\n\n"

        prompt += "\nЗапропонуй 3-5 правил у JSON форматі:"
        return prompt

    def _parse_rules_from_response(self, response: str) -> List[Dict]:
        """Парсинг правил з LLM відповіді."""
        try:
            # Спроба знайти JSON в відповіді
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                rules = json.loads(json_str)
                return rules
        except Exception as e:
            print(f"⚠️  Помилка парсингу правил: {e}")

        return []

    def add_skill(self, name: str, pattern: str, action: str, metadata: Dict = None) -> None:
        """Додати skill в базу.

        Args:
            name: Назва skill
            pattern: Патерн/умова активації
            action: Дія для виконання
            metadata: Додаткові метадані
        """
        skill_id = f"skill_{len(self.skills) + 1}"
        self.skills[skill_id] = {
            "id": skill_id,
            "name": name,
            "pattern": pattern,
            "action": action,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "usage_count": 0,
        }

        self._save_json(self.skills_file, self.skills)
        print(f"✅ Skill додано: {name}")

    def get_skill(self, pattern: str) -> Optional[Dict]:
        """Отримати skill за патерном."""
        for skill in self.skills.values():
            if pattern.lower() in skill.get("pattern", "").lower():
                # Increment usage count
                skill["usage_count"] = skill.get("usage_count", 0) + 1
                self._save_json(self.skills_file, self.skills)
                return skill
        return None

    def get_stats(self) -> Dict:
        """Отримати статистику самонавчання."""
        total_logs = 0
        success_count = 0
        error_count = 0

        if self.logs_file.exists():
            with open(self.logs_file, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = json.loads(line)
                    total_logs += 1
                    if entry.get("success"):
                        success_count += 1
                    else:
                        error_count += 1

        return {
            "total_executions": total_logs,
            "successful": success_count,
            "failed": error_count,
            "success_rate": success_count / total_logs if total_logs > 0 else 0,
            "skills_count": len(self.skills),
            "rules_count": len(self.rules),
        }


# ==================== Singleton для використання ====================

_self_learning_instance: Optional[SelfLearning] = None


def get_self_learning(data_dir: str = None) -> SelfLearning:
    """Отримати singleton екземпляр SelfLearning."""
    global _self_learning_instance
    if _self_learning_instance is None:
        _self_learning_instance = SelfLearning(data_dir)
    return _self_learning_instance