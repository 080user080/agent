"""
Захист від небезпечних GUI дій (GUI Guardian).

GUI Automation Phase 6 — безпечна робота з реальним UI.
Рівні ризику, sandbox режим, preview дій.
"""

import re
import time
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum


class GUIRiskLevel(Enum):
    """Рівні ризику GUI дій."""
    LOW = "low"           # Без підтвердження
    MEDIUM = "medium"     # Підтвердження в статус-барі
    HIGH = "high"         # Явне підтвердження
    CRITICAL = "critical" # Заблоковано


@dataclass
class RiskAssessment:
    """Оцінка ризику дії."""
    level: GUIRiskLevel
    score: float  # 0.0 - 1.0
    reasons: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class SafetyZone:
    """Безпечна зона для дій."""
    x: int
    y: int
    width: int
    height: int
    allowed_apps: List[str] = field(default_factory=list)


class GUIGuardian:
    """
    Guardian для GUI автоматизації.
    Аналізує дії на небезпечність, контролює sandbox.
    """

    # Небезпечні патерни в текстах кнопок/дій
    DANGEROUS_PATTERNS: List[str] = [
        r"\bвидалити\b", r"\bdelete\b", r"\bremove\b", r"\berase\b",
        r"\bformat\b", r"\bformatuj\b", r"\bwipe\b",
        r"\bочистити\b", r"\bclear all\b", r"\breset\b",
        r"\buninstall\b", r"\bдеінсталювати\b",
        r"\bdisable\b", r"\bвимкнути\b",
        r"\bstop\b.*\bservice", r"\bkill\b.*\bprocess",
        r"\bshutdown\b", r"\brestart\b", r"\bперезавантажити\b",
        r"\bexit\b", r"\bquit\b", r"\bвийти\b",
    ]

    # Патерни відправки даних
    SENDING_PATTERNS: List[str] = [
        r"\bsend\b", r"\bsubmit\b", r"\bpublish\b",
        r"\bвідправити\b", r"\bнадіслати\b", r"\bопублікувати\b",
        r"\bpost\b", r"\bshare\b", r"\bподілитися\b",
    ]

    # Системні вікна
    SYSTEM_WINDOWS: List[str] = [
        "uac", "user account control", "контроль облікових записів",
        "task manager", "диспетчер задач",
        "registry editor", "редактор реєстру", "regedit",
        "group policy", "групова політика",
        "device manager", "диспетчер пристроїв",
        "disk management", "керування дисками",
        "services", "служби",
        "firewall", "брандмауер",
    ]

    def __init__(self):
        self.sandbox_mode = False
        self.allowed_region: Optional[SafetyZone] = None
        self.allowed_applications: Set[str] = set()
        self.blocked_applications: Set[str] = set()
        self.risk_threshold = GUIRiskLevel.HIGH

        # Лічильники для rate limiting
        self._action_count = 0
        self._last_action_time = 0.0
        self._max_actions_per_minute = 60

        # Історія для аналізу
        self._recent_actions: List[Dict[str, Any]] = []
        self._max_history = 20

    # ==================== SANDBOX РЕЖИМ ====================

    def enable_sandbox_mode(
        self,
        allowed_region: Optional[Tuple[int, int, int, int]] = None,
        allowed_apps: Optional[List[str]] = None
    ):
        """
        Увімкнути sandbox режим.

        Args:
            allowed_region: (x, y, width, height) — дозволена зона
            allowed_apps: Список дозволених програм
        """
        self.sandbox_mode = True

        if allowed_region:
            self.allowed_region = SafetyZone(
                x=allowed_region[0],
                y=allowed_region[1],
                width=allowed_region[2],
                height=allowed_region[3]
            )

        if allowed_apps:
            self.allowed_applications = set(allowed_apps)

    def disable_sandbox_mode(self):
        """Вимкнути sandbox режим."""
        self.sandbox_mode = False
        self.allowed_region = None
        self.allowed_applications.clear()

    def set_allowed_region(self, x: int, y: int, width: int, height: int):
        """Встановити дозволену зону."""
        self.allowed_region = SafetyZone(x=x, y=y, width=width, height=height)

    def set_allowed_applications(self, app_names: List[str]):
        """Встановити дозволені програми."""
        self.allowed_applications = set(app_names)

    def add_blocked_application(self, app_name: str):
        """Додати програму в чорний список."""
        self.blocked_applications.add(app_name.lower())

    # ==================== АНАЛІЗ РИЗИКУ ====================

    def assess_risk(
        self,
        action: str,
        params: Dict[str, Any],
        target_text: Optional[str] = None
    ) -> RiskAssessment:
        """
        Оцінити ризик дії.

        Args:
            action: Тип дії ("click", "type", "delete", ...)
            params: Параметри
            target_text: Текст цільового елементу

        Returns:
            RiskAssessment
        """
        reasons = []
        suggestions = []
        score = 0.0

        # Аналізуємо текст цілі
        text_to_check = target_text or ""
        text_lower = text_to_check.lower()

        # Перевірка на небезпечні патерни
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                reasons.append(f"Небезпечний патерн: '{pattern}'")
                score += 0.3
                suggestions.append("Перевірте чи справді потрібно це робити")

        # Перевірка на відправку даних
        for pattern in self.SENDING_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                reasons.append(f"Можлива відправка даних: '{pattern}'")
                score += 0.2
                suggestions.append("Перевірте що саме відправляється")

        # Тип дії
        if action in ("delete", "remove", "format", "wipe"):
            reasons.append(f"Деструктивна дія: {action}")
            score += 0.4
            suggestions.append("Цю дію неможливо відкатити")

        if action == "click" and "system" in str(params.get("window_class", "")).lower():
            reasons.append("Системне вікно")
            score += 0.3

        # Перевірка на системні вікна
        window_title = str(params.get("window_title", "")).lower()
        for sys_win in self.SYSTEM_WINDOWS:
            if sys_win in window_title:
                reasons.append(f"Системне вікно: {sys_win}")
                score += 0.5
                suggestions.append("Дії в системних вікнах можуть бути небезпечними")

        # Перевірка sandbox
        if self.sandbox_mode:
            x = params.get("x", 0)
            y = params.get("y", 0)

            if self.allowed_region:
                if not (self.allowed_region.x <= x <= self.allowed_region.x + self.allowed_region.width and
                        self.allowed_region.y <= y <= self.allowed_region.y + self.allowed_region.height):
                    reasons.append("За межами дозволеної зони")
                    score += 0.5

        # Визначаємо рівень
        if score >= 0.8:
            level = GUIRiskLevel.CRITICAL
        elif score >= 0.5:
            level = GUIRiskLevel.HIGH
        elif score >= 0.2:
            level = GUIRiskLevel.MEDIUM
        else:
            level = GUIRiskLevel.LOW

        return RiskAssessment(
            level=level,
            score=min(score, 1.0),
            reasons=reasons,
            suggestions=suggestions
        )

    def is_action_allowed(
        self,
        action: str,
        params: Dict[str, Any],
        target_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Перевірити чи дозволена дія.

        Returns:
            {"allowed": bool, "reason": str, "risk": RiskAssessment}
        """
        assessment = self.assess_risk(action, params, target_text)

        # Критичний ризик — блокуємо
        if assessment.level == GUIRiskLevel.CRITICAL:
            return {
                "allowed": False,
                "reason": f"CRITICAL RISK: {'; '.join(assessment.reasons)}",
                "risk": assessment
            }

        # Sandbox перевірки
        if self.sandbox_mode:
            # Перевірка додатків
            app_name = str(params.get("application", "")).lower()
            if self.allowed_applications and app_name not in self.allowed_applications:
                return {
                    "allowed": False,
                    "reason": f"Sandbox: програма '{app_name}' не в whitelist",
                    "risk": assessment
                }

            if app_name in self.blocked_applications:
                return {
                    "allowed": False,
                    "reason": f"Sandbox: програма '{app_name}' в blacklist",
                    "risk": assessment
                }

        # Rate limiting
        current_time = time.time()
        if current_time - self._last_action_time < 1.0:  # Мінімум 1 сек між діями
            self._action_count += 1
            if self._action_count > self._max_actions_per_minute:
                return {
                    "allowed": False,
                    "reason": "Rate limit: забагато дій за хвилину",
                    "risk": assessment
                }
        else:
            self._action_count = 1

        self._last_action_time = current_time

        # Зберігаємо в історію
        self._recent_actions.append({
            "action": action,
            "params": params,
            "time": current_time,
            "risk_level": assessment.level.value
        })
        if len(self._recent_actions) > self._max_history:
            self._recent_actions.pop(0)

        return {
            "allowed": True,
            "reason": "OK",
            "risk": assessment
        }

    # ==================== PREVIEW ТА SIMULATION ====================

    def preview_action(self, action: str, params: Dict[str, Any]) -> str:
        """
        Створити опис того що буде зроблено.

        Args:
            action: Тип дії
            params: Параметри

        Returns:
            Текстовий опис
        """
        descriptions = {
            "mouse_click": lambda p: f"Клік миші в координатах ({p.get('x', '?')}, {p.get('y', '?')})",
            "keyboard_type": lambda p: f"Введення тексту: '{p.get('text', '')[:30]}...'" if len(str(p.get('text', ''))) > 30 else f"Введення тексту: '{p.get('text', '')}'",
            "click_element": lambda p: f"Клік по елементу: '{p.get('description', '?')}'",
            "type_in_field": lambda p: f"Введення в поле '{p.get('field', '?')}': '{p.get('text', '')[:20]}...'",
            "fill_form": lambda p: f"Заповнення форми з {len(p.get('field_dict', {}))} полями",
            "open_menu": lambda p: f"Відкриття меню: '{p.get('menu_name', '?')}'",
            "handle_dialog": lambda p: f"Обробка діалогу: {p.get('action', '?')}",
            "delete_file": lambda p: f"ВИДАЛЕННЯ файлу: {p.get('path', '?')}",
            "move_file": lambda p: f"Переміщення: {p.get('source', '?')} → {p.get('destination', '?')}",
        }

        if action in descriptions:
            return descriptions[action](params)

        return f"Дія: {action} з параметрами {str(params)[:100]}"

    def simulate_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        "Сухий" прогін дії без виконання.

        Returns:
            {"would_succeed": bool, "preview": str, "risk": RiskAssessment}
        """
        preview = self.preview_action(action, params)
        risk = self.assess_risk(action, params)

        # Симуляція успіху
        would_succeed = risk.level != GUIRiskLevel.CRITICAL

        # Додаткові перевірки
        issues = []
        if action == "click_element":
            # Перевіримо чи елемент існує
            from .logic_context_analyzer import analyze_current_context
            context = analyze_current_context()
            if not context.get("success"):
                would_succeed = False
                issues.append("Не вдалося проаналізувати екран")

        return {
            "would_succeed": would_succeed,
            "preview": preview,
            "risk": risk,
            "issues": issues,
            "message": f"Симуляція: {preview} — {'Успіх' if would_succeed else 'Провал'}"
        }

    # ==================== ЗВІТИ ТА ІСТОРІЯ ====================

    def get_safety_report(self) -> str:
        """
        Згенерувати звіт про безпеку.

        Returns:
            Текстовий звіт
        """
        lines = [
            "GUI Guardian Safety Report",
            "=" * 30,
            f"Sandbox mode: {'ON' if self.sandbox_mode else 'OFF'}",
        ]

        if self.sandbox_mode:
            if self.allowed_region:
                r = self.allowed_region
                lines.append(f"Allowed region: ({r.x}, {r.y}, {r.width}, {r.height})")
            if self.allowed_applications:
                lines.append(f"Allowed apps: {', '.join(self.allowed_applications)}")
            if self.blocked_applications:
                lines.append(f"Blocked apps: {', '.join(self.blocked_applications)}")

        lines.extend([
            "",
            f"Recent actions: {len(self._recent_actions)}",
            f"Risk threshold: {self.risk_threshold.value}",
        ])

        if self._recent_actions:
            risk_counts = {}
            for a in self._recent_actions:
                level = a.get("risk_level", "unknown")
                risk_counts[level] = risk_counts.get(level, 0) + 1

            lines.append("\nRisk distribution:")
            for level, count in sorted(risk_counts.items()):
                lines.append(f"  {level}: {count}")

        return "\n".join(lines)

    def get_blocked_actions_history(self) -> List[Dict[str, Any]]:
        """Отримати історію заблокованих дій."""
        return [
            a for a in self._recent_actions
            if a.get("blocked", False)
        ]


# ==================== ПУБЛІЧНИЙ API ====================

_guardian = None


def get_guardian() -> GUIGuardian:
    """Отримати singleton GUIGuardian."""
    global _guardian
    if _guardian is None:
        _guardian = GUIGuardian()
    return _guardian


def enable_sandbox_mode(
    allowed_region: Optional[Tuple[int, int, int, int]] = None,
    allowed_apps: Optional[List[str]] = None
):
    """Увімкнути sandbox."""
    get_guardian().enable_sandbox_mode(allowed_region, allowed_apps)


def disable_sandbox_mode():
    """Вимкнути sandbox."""
    get_guardian().disable_sandbox_mode()


def set_allowed_region(x: int, y: int, width: int, height: int):
    """Встановити дозволену зону."""
    get_guardian().set_allowed_region(x, y, width, height)


def set_allowed_applications(app_names: List[str]):
    """Встановити дозволені програми."""
    get_guardian().set_allowed_applications(app_names)


def add_blocked_application(app_name: str):
    """Додати в blacklist."""
    get_guardian().add_blocked_application(app_name)


def assess_risk(
    action: str,
    params: Dict[str, Any],
    target_text: Optional[str] = None
) -> Dict[str, Any]:
    """Оцінити ризик."""
    assessment = get_guardian().assess_risk(action, params, target_text)
    return {
        "level": assessment.level.value,
        "score": assessment.score,
        "reasons": assessment.reasons,
        "suggestions": assessment.suggestions
    }


def is_action_allowed(
    action: str,
    params: Dict[str, Any],
    target_text: Optional[str] = None
) -> Dict[str, Any]:
    """Перевірити чи дія дозволена."""
    return get_guardian().is_action_allowed(action, params, target_text)


def preview_action(action: str, params: Dict[str, Any]) -> str:
    """Отримати preview дії."""
    return get_guardian().preview_action(action, params)


def simulate_action(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Симулювати дію."""
    return get_guardian().simulate_action(action, params)


def get_safety_report() -> str:
    """Отримати звіт безпеки."""
    return get_guardian().get_safety_report()


# Декоратор для перевірки перед виконанням

def guarded(action_name: str, require_confirmation_for: List[str] = None):
    """
    Декоратор для захищених функцій.

    Usage:
        @guarded("click", require_confirmation_for=["high", "critical"])
        def mouse_click(x, y):
            ...
    """
    require_confirmation_for = require_confirmation_for or ["high", "critical"]

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Формуємо params
            params = {"args": args, **kwargs}

            # Перевіряємо
            check = is_action_allowed(action_name, params)

            if not check["allowed"]:
                return {
                    "success": False,
                    "blocked": True,
                    "reason": check["reason"],
                    "message": f"Дія заблокована: {check['reason']}"
                }

            # Перевіряємо рівень ризику
            risk = check.get("risk", {})
            level = risk.get("level", "low")

            if level in require_confirmation_for:
                # Тут можна додати GUI підтвердження
                # Поки що просто логуємо
                print(f"[GUARDIAN] HIGH RISK ACTION: {action_name}")
                print(f"  Reasons: {risk.get('reasons', [])}")

            # Виконуємо
            return func(*args, **kwargs)

        return wrapper
    return decorator
