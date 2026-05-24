"""Валідація та критика згенерованих планів дій.

Виділений компонент перевірки коректності відповідей LLM-планувальника.
Виконує:
- Витяг JSON з тексту (стійкий до обірваних / невалідних відповідей).
- Нормалізацію плану до списку кроків.
- Перевірку безпеки плану (через реєстр та політики runtime).
- Валідацію окремого кроку після виконання.
- Детекцію помилок моделі / з'єднання.

Повертає структуровані результати (датакласи / namedtuple) замість сирих
булевих прапорців, що забезпечує зворотну сумісність із `Planner`.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from colorama import Fore
from ..runtime.core_tool_runtime import check_dangerous_content, check_ambiguous_content


# ---------------------------------------------------------------------------
# Data types для структурованих результатів валідації
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Результат валідації плану безпеки.

    Attributes:
        ok: True, якщо план пройшов перевірку.
        message: Текстове повідомлення (помилка або підсумок).
        ambiguous_warnings: Список м'яких попереджень про двозначні дії.
    """
    ok: bool = False
    message: str = ""
    ambiguous_warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


@dataclass
class StepValidationResult:
    """Результат валідації окремого кроку після виконання.

    Attributes:
        ok: True, якщо крок виконано успішно.
        message: Текстове повідомлення.
    """
    ok: bool = False
    message: str = ""

    def __bool__(self) -> bool:
        return self.ok


@dataclass
class JsonExtractResult:
    """Результат витягу JSON з тексту.

    Attributes:
        data: Витягнутий JSON-об'єкт/масив або None.
        error: Текст помилки, якщо витяг не вдався.
    """
    data: Optional[Any] = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.data is not None


# ---------------------------------------------------------------------------
# PlannerValidator
# ---------------------------------------------------------------------------


class PlannerValidator:
    """Валідатор планів — ізольована логіка перевірки відповідей моделі.

    Не має залежності від `Planner` або `assistant`.
    Для роботи потребує лише registry (опційно) на етапі перевірки безпеки.
    """

    # Регулярний вираз для пошуку шляхів файлів у результаті
    _FILE_PATH_RE = re.compile(
        r"✅ Файл створено:\s*([^\n]+?)(?:\s+на робочому столі)?$",
        re.IGNORECASE,
    )

    # ------------------------------------------------------------------
    # LLM error detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_llm_error(response: str, task: str) -> bool:
        """Детектувати помилки моделі або з'єднання.

        Args:
            response: Відповідь від LLM.
            task: Оригінальна задача (не використовується в цій реалізації,
                  але залишено для зворотної сумісності сигнатури).

        Returns:
            True якщо це помилка (помилка вже залогована).
        """
        response_lower = response.lower()

        # Помилка: модель не завантажена
        if "модель не завантажена" in response_lower or "no models loaded" in response_lower:
            print(f"{Fore.RED}❌ Планер: Модель LM Studio не завантажена{Fore.RESET}")
            print(f"{Fore.YELLOW}⚠️  Перейдіть у вкладку 'Налаштування' → 'LLM Ендпоінти' для налаштування{Fore.RESET}")
            return True

        # Помилка: не вдається підключитися
        if "не відповідає" in response_lower or "не вдається підключитися" in response_lower:
            print(f"{Fore.RED}❌ Планер: Немає з'єднання з LM Studio{Fore.RESET}")
            return True

        # Інші API помилки (починаються з "❌" або "Помилка:")
        if response.startswith("❌") or response.startswith("Помилка:"):
            print(f"{Fore.RED}❌ Планер: Помилка LLM API — виконую без планування{Fore.RESET}")
            return True

        return False

    # ------------------------------------------------------------------
    # JSON extraction (стійкий до обірваних / невалідних відповідей)
    # ------------------------------------------------------------------

    @staticmethod
    def extract_json(text: str) -> JsonExtractResult:
        """Витягнути JSON-масив або об'єкт з відповіді LLM.

        Підтримує:
        - Прибирання токенів ``<|channel|>``, ``<|message|>`` тощо.
        - Код у блоках ```json ... ```.
        - Список об'єктів без зовнішніх ``[]``: ``{...}, {...}`` → ``[{...}, {...}]``.

        Args:
            text: Сирий текст відповіді LLM.

        Returns:
            ``JsonExtractResult`` з витягнутими даними або кодом помилки.
            Ніколи не кидає винятків.
        """
        if not text:
            return JsonExtractResult(error="empty text")

        from functions.llm.response_parser import safe_json_loads

        try:
            # 1. Прибираємо LLM-токени типу <|channel|>, <|message|>, constrain, ...
            cleaned = re.sub(r'<\|[^|]*\|>', '', text)
            cleaned = re.sub(
                r'\b(channel|constrain|message|final)\b\s*:?',
                '',
                cleaned,
                flags=re.IGNORECASE,
            ).strip()

            # 2. Витягаємо з ```json ... ``` блоку, якщо є
            code_block = re.search(
                r'```(?:json)?\s*(.*?)\s*```', cleaned, re.DOTALL | re.IGNORECASE
            )
            if code_block:
                cleaned = code_block.group(1).strip()

            candidates: List[str] = []

            # 3. Повний масив [...] з найдальшими дужками
            arr_start = cleaned.find('[')
            arr_end = cleaned.rfind(']')
            if arr_start != -1 and arr_end > arr_start:
                candidates.append(cleaned[arr_start: arr_end + 1])

            # 4. Об'єкт {...} з найдальшими дужками
            obj_start = cleaned.find('{')
            obj_end = cleaned.rfind('}')
            if obj_start != -1 and obj_end > obj_start:
                obj_block = cleaned[obj_start: obj_end + 1]
                candidates.append(obj_block)
                # 5. Fallback: обгортаємо в [...] якщо там багато об'єктів через кому
                #    (LLM іноді забуває зовнішні дужки)
                if '},' in obj_block or '} ,' in obj_block or '}\n' in obj_block:
                    candidates.append('[' + obj_block + ']')

            for candidate in candidates:
                try:
                    data = safe_json_loads(candidate)
                    return JsonExtractResult(data=data)
                except Exception:
                    continue

            return JsonExtractResult(error="no valid JSON found")
        except Exception as exc:
            return JsonExtractResult(error=f"extraction failed: {exc}")

    # ------------------------------------------------------------------
    # Plan normalization
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_plan(raw_plan: Any) -> List[Dict[str, Any]]:
        """Нормалізувати план до списку кроків.

        Args:
            raw_plan: Сирі дані (очікується список словників).

        Returns:
            Список нормалізованих кроків або порожній список.
        """
        if not isinstance(raw_plan, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for step in raw_plan:
            if not isinstance(step, dict):
                continue

            action = str(step.get("action", "")).strip()
            args = step.get("args", {})
            if not action or not isinstance(args, dict):
                continue

            normalized.append(
                {
                    "action": action,
                    "args": args,
                    "goal": str(step.get("goal", "")).strip(),
                    "validation": str(step.get("validation", "")).strip(),
                }
            )
        return normalized

    # ------------------------------------------------------------------
    # Safety validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_plan_safety(
        plan: List[Dict[str, Any]],
        task: str,
        registry: Optional[Any] = None,
    ) -> ValidationResult:
        """Перевірити план на безпеку з використанням централізованих політик.

        Args:
            plan: Список кроків плану.
            task: Оригінальна задача.
            registry: Реєстр функцій (``assistant.registry``).

        Returns:
            ``ValidationResult`` з прапорцем ``ok`` та повідомленням.
        """
        if not plan:
            return ValidationResult(ok=False, message="План порожній або не згенерувався.")

        if not registry:
            return ValidationResult(ok=False, message="Недоступний реєстр функцій.")

        available = set(registry.functions.keys())
        ambiguous_warnings = []

        for idx, step in enumerate(plan, 1):
            action = step.get("action", "")
            if action not in available:
                return ValidationResult(
                    ok=False,
                    message=f"У плані є невідома функція: {action}",
                )

            args = step.get("args", {})
            if not isinstance(args, dict):
                return ValidationResult(
                    ok=False,
                    message=f"Некоректні параметри у кроці {action}",
                )

            # Заборона time.sleep в execute_python
            if action in ("execute_python", "execute_python_code"):
                code = args.get("code", "")
                if "time.sleep" in code or "import time" in code:
                    return ValidationResult(
                        ok=False,
                        message=(
                            f"У кроці #{idx} '{action}' знайдено time.sleep — "
                            "використовуйте keyboard_type/keyboard_press "
                            "для взаємодії з вікнами"
                        ),
                    )

            risk = registry.get_tool_risk(action)
            step["risk"] = risk

            if risk == "confirm_required":
                step["requires_confirmation"] = True

            if risk == "blocked":
                return ValidationResult(
                    ok=False,
                    message=f"Функція {action} заблокована політикою runtime.",
                )

            # Централізована перевірка небезпечного контенту
            raw_text = json.dumps(step, ensure_ascii=False)
            dangerous = check_dangerous_content(raw_text)
            if dangerous:
                return ValidationResult(
                    ok=False,
                    message=(
                        f"У кроці #{idx} '{action}' знайдено небезпечний "
                        f"патерн: '{dangerous}'"
                    ),
                )

            # М'яке попередження для двозначних дій
            ambiguous = check_ambiguous_content(raw_text)
            if ambiguous:
                ambiguous_warnings.append(
                    f"крок #{idx} '{action}' (патерн: '{ambiguous}')"
                )
                # Примусово підвищуємо рівень підтвердження
                step["requires_confirmation"] = True
                step["ambiguous_pattern"] = ambiguous

        summary = f"План із {len(plan)} кроків пройшов перевірку."
        if ambiguous_warnings:
            summary += (
                " ⚠️ Двозначні дії потребують підтвердження: "
                f"{', '.join(ambiguous_warnings)}"
            )

        return ValidationResult(ok=True, message=summary, ambiguous_warnings=ambiguous_warnings)

    # ------------------------------------------------------------------
    # Step validation (after execution)
    # ------------------------------------------------------------------

    @staticmethod
    def extract_file_path(result_text: str) -> Optional[str]:
        """Спробувати витягти шлях або назву створеного файлу.

        Args:
            result_text: Текст результату виконання кроку.

        Returns:
            Абсолютний шлях до файлу або None.
        """
        if not result_text:
            return None

        match = PlannerValidator._FILE_PATH_RE.search(result_text.strip())
        if match:
            path = match.group(1).strip()
            if not os.path.isabs(path):
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                path = os.path.join(desktop, path)
            return path
        return None

    @staticmethod
    def validate_step(
        action: str,
        args: Dict[str, Any],
        result: str,
        context: Dict[str, Any],
        registry: Optional[Any] = None,
    ) -> StepValidationResult:
        """Перевірити, чи крок відпрацював успішно.

        Args:
            action: Назва дії.
            args: Аргументи кроку.
            result: Текст результату виконання.
            context: Поточний контекст виконання.
            registry: Реєстр функцій (опційно).

        Returns:
            ``StepValidationResult`` з прапорцем ``ok`` та повідомленням.
        """
        tool_meta = None
        if registry:
            tool_meta = getattr(registry, "last_tool_result", None)

        if tool_meta and tool_meta.get("action") == action:
            if tool_meta.get("ok"):
                return StepValidationResult(
                    ok=True,
                    message=tool_meta.get("message", "Крок успішний."),
                )
            if tool_meta.get("needs_confirmation"):
                return StepValidationResult(
                    ok=False,
                    message=(
                        tool_meta.get("error")
                        or "Крок потребує підтвердження користувача."
                    ),
                )
            return StepValidationResult(
                ok=False,
                message=(
                    tool_meta.get("error")
                    or tool_meta.get("message", "Крок завершився помилкою.")
                ),
            )

        if not isinstance(result, str):
            return StepValidationResult(
                ok=False,
                message="Результат кроку не є текстом.",
            )

        if result.startswith("❌") or "помилка" in result.lower():
            return StepValidationResult(ok=False, message=result)

        if action == "create_file":
            file_path = PlannerValidator.extract_file_path(result)
            if file_path and os.path.exists(file_path):
                return StepValidationResult(ok=True, message="Файл створено.")
            return StepValidationResult(ok=False, message="Файл не підтверджено на диску.")

        if action == "edit_file":
            filepath = args.get("filepath")
            if filepath and not os.path.isabs(filepath):
                filepath = os.path.join(os.path.expanduser("~"), "Desktop", filepath)
            if filepath and os.path.exists(filepath):
                return StepValidationResult(ok=True, message="Файл відредаговано.")
            return StepValidationResult(
                ok="✅" in result,
                message="Результат редагування не підтверджено.",
            )

        if action in {
            "execute_python",
            "execute_python_code",
            "execute_python_file",
            "debug_python_code",
        }:
            return StepValidationResult(
                ok=True,
                message="Python-крок завершився без явної помилки.",
            )

        if action == "open_program":
            ok = "✅" in result or "Відкрив" in result or "Відкрито" in result
            return StepValidationResult(ok=ok, message=result)

        if action == "close_program":
            ok = "успішно" in result.lower() or "закрита" in result.lower()
            return StepValidationResult(ok=ok, message=result)

        if action == "list_directory":
            # list_directory успішний якщо результат не починається з помилки
            return StepValidationResult(
                ok=not result.startswith("❌"),
                message=result,
            )

        if action == "confirm_action":
            ok = (
                '"status": "confirmed"' in result
                or "confirmed" in result.lower()
                or "cancelled" in result.lower()
            )
            return StepValidationResult(ok=ok, message=result)

        return StepValidationResult(
            ok=True,
            message="Крок не потребує додаткової перевірки.",
        )

    # ------------------------------------------------------------------
    # Convenience: повний цикл валідації відповіді LLM
    # ------------------------------------------------------------------

    @classmethod
    def validate_llm_response(
        cls,
        response: str,
        task: str,
        registry: Optional[Any] = None,
    ) -> Tuple[Optional[List[Dict[str, Any]]], ValidationResult]:
        """Повний цикл: перевірка помилок → extract JSON → нормалізація → безпека.

        Args:
            response: Відповідь LLM.
            task: Оригінальна задача.
            registry: Реєстр функцій (опційно, для safety validation).

        Returns:
            ``(plan, safety_result)``:
            - ``plan``: нормалізований план або None, якщо валідація не пройдена.
            - ``safety_result``: результат перевірки безпеки.
        """
        # Крок 1: перевірка помилок моделі
        if cls.detect_llm_error(response, task):
            return None, ValidationResult(
                ok=False,
                message="LLM повернув помилку з'єднання/моделі.",
            )

        # Крок 2: витяг JSON
        extracted = cls.extract_json(response)
        if not extracted.ok:
            return None, ValidationResult(
                ok=False,
                message=f"Не вдалося витягти JSON: {extracted.error}",
            )

        # Крок 3: нормалізація
        plan = cls.normalize_plan(extracted.data)
        if not plan:
            return None, ValidationResult(
                ok=False,
                message="План порожній після нормалізації.",
            )

        # Крок 4: перевірка безпеки (якщо є registry)
        if registry is not None:
            safety = cls.validate_plan_safety(plan, task, registry)
            if not safety.ok:
                return None, safety
            return plan, safety

        return plan, ValidationResult(ok=True, message="План пройшов базову валідацію.")


__all__ = [
    "PlannerValidator",
    "ValidationResult",
    "StepValidationResult",
    "JsonExtractResult",
]