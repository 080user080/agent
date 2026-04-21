"""SessionBudget — ліміти та kill-switch для довгих автономних сесій.

Phase 8 / I2. Працює разом з `logic_watcher` (I1), але ні від чого не залежить:
це чистий data-layer + arithmetics, повністю юніт-тестований.

Концепція: перед кожним кроком автоматичної сесії агент викликає
`budget.check()`. Метод повертає `True` якщо ще є квота, `False` — якщо треба
зупинитись. Після кроку викликаються `record_step` / `record_tokens` /
`record_cost`, щоб збільшити лічильники.

Kill-switch:
- Файл-маркер (`/tmp/marc-stop` за замовч.) — достатньо `touch`, щоб сесія
  зупинилася на найближчому `check()`.
- Callable-hook — довільна функція `() -> bool`, яка повертає `True` коли
  треба зупинитись (для гарячих клавіш / UI-кнопки «Стоп»).

Усі часові лічильники — секунди / штуки / центи долара (int або float).
Мережевих викликів немає, тож жодних моків для тестів не потрібно.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class SessionLimits:
    """Жорсткі обмеження автономної сесії.

    Поле `None` означає «без ліміту» (використовуйте обережно).
    """

    max_steps: Optional[int] = 500
    max_tokens: Optional[int] = 500_000
    max_duration_seconds: Optional[float] = 6 * 60 * 60  # 6h
    max_cost_usd: Optional[float] = 5.0
    max_errors: Optional[int] = 50


@dataclass
class SessionUsage:
    """Накопичені лічильники використання."""

    steps: int = 0
    tokens: int = 0
    errors: int = 0
    cost_usd: float = 0.0
    started_at: float = field(default_factory=time.monotonic)

    @property
    def duration_seconds(self) -> float:
        return time.monotonic() - self.started_at


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class BudgetCheckResult:
    """Результат виклику `budget.check()`.

    `ok=True`  → можна продовжувати.
    `ok=False` → зупинитись; `reason` описує, чого саме не вистачає.
    """

    ok: bool
    reason: str = ""
    metric: str = ""
    limit: Any = None
    current: Any = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class SessionBudget:
    """Трекер лімітів автономної сесії з kill-switch-ами."""

    def __init__(
        self,
        limits: Optional[SessionLimits] = None,
        *,
        stop_file: str | Path = "/tmp/marc-stop",
        kill_switch: Optional[Callable[[], bool]] = None,
    ):
        self.limits = limits or SessionLimits()
        self.usage = SessionUsage()
        self.stop_file = Path(stop_file)
        self._kill_switch = kill_switch
        self._manual_stop = False
        self._stop_reasons: List[str] = []

    # ----- Recording -------------------------------------------------------

    def record_step(self, n: int = 1) -> None:
        self.usage.steps += n

    def record_tokens(self, n: int) -> None:
        if n < 0:
            raise ValueError("tokens must be >= 0")
        self.usage.tokens += n

    def record_error(self, n: int = 1) -> None:
        self.usage.errors += n

    def record_cost(self, usd: float) -> None:
        if usd < 0:
            raise ValueError("cost_usd must be >= 0")
        self.usage.cost_usd += usd

    # ----- Kill-switches --------------------------------------------------

    def stop(self, reason: str = "manual") -> None:
        """Явна зупинка (наприклад, з UI-кнопки)."""
        self._manual_stop = True
        self._stop_reasons.append(reason)

    def _external_stop_triggered(self) -> Optional[str]:
        if self._manual_stop:
            return f"manual_stop: {self._stop_reasons[-1]}"
        if self.stop_file.exists():
            return f"stop_file: {self.stop_file}"
        if self._kill_switch is not None:
            try:
                if self._kill_switch():
                    return "kill_switch"
            except Exception as exc:  # noqa: BLE001
                # kill-switch має бути безпечним; якщо впав — не валимо сесію.
                return f"kill_switch_error: {exc}"
        return None

    # ----- Check ----------------------------------------------------------

    def check(self) -> BudgetCheckResult:
        """Повертає BudgetCheckResult. `.ok=False` → треба зупинитись."""
        external = self._external_stop_triggered()
        if external:
            return BudgetCheckResult(
                ok=False, reason=external, metric="external"
            )

        limits = self.limits
        u = self.usage

        # Перевіряємо пороги по черзі, повертаємо перший який пробито.
        def exceeded(
            current: Any,
            limit: Any,
            metric: str,
        ) -> Optional[BudgetCheckResult]:
            if limit is None:
                return None
            if current >= limit:
                return BudgetCheckResult(
                    ok=False,
                    reason=f"{metric} exceeded ({current} >= {limit})",
                    metric=metric,
                    limit=limit,
                    current=current,
                )
            return None

        for r in (
            exceeded(u.steps, limits.max_steps, "steps"),
            exceeded(u.tokens, limits.max_tokens, "tokens"),
            exceeded(u.errors, limits.max_errors, "errors"),
            exceeded(u.cost_usd, limits.max_cost_usd, "cost_usd"),
            exceeded(
                u.duration_seconds,
                limits.max_duration_seconds,
                "duration_seconds",
            ),
        ):
            if r is not None:
                return r

        return BudgetCheckResult(ok=True)

    def is_exhausted(self) -> bool:
        """Shortcut для швидкого if-ну."""
        return not self.check().ok

    # ----- Reporting -----------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        return {
            "limits": asdict(self.limits),
            "usage": {
                "steps": self.usage.steps,
                "tokens": self.usage.tokens,
                "errors": self.usage.errors,
                "cost_usd": self.usage.cost_usd,
                "duration_seconds": self.usage.duration_seconds,
            },
            "stopped": self._manual_stop,
        }

    def reset(self) -> None:
        self.usage = SessionUsage()
        self._manual_stop = False
        self._stop_reasons.clear()
