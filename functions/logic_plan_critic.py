"""Plan-critic LLM — самокритика плану перед виконанням (Phase 11.5).

Ідея: до того, як `TaskRunner.run(plan)` стартує, ми просимо LLM (через
`ProviderRegistry.chat()`) подивитись на план цілком і винести вердикт:

    ``approve``  — план ок, виконуй.
    ``concerns`` — є зауваження, але блокувати не треба (попередимо у звіті).
    ``redo``     — план небезпечний / нерозумний, треба переробити.

Це не замінює `PermissionGate` (той працює на рівні окремих дій), а лише
додає meta-шар: «чи весь план в цілому виглядає ок». Критик:

1. Отримує **серіалізований план + мета-інформацію** (contexto: project_root,
   поточні обмеження, політики інструментів).
2. Формує детермінованим білдером `system + user` промпт з інструкціями
   повернути JSON-вердикт у фіксованій схемі.
3. Парсить відповідь стійко (tolerates fenced ```json блоки, trailing commas,
   пропущені поля).
4. Повертає `CritiqueResult` з `verdict`, списком `Concern`, token usage.

Весь модуль **чистий pure-Python + `ProviderRegistry`**: жодних прямих
HTTP/файл-операцій, жодних глобальних синглтонів. Тестується мокнутим
`CallableProvider`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from functions.logic_ai_adapter import (
    ROLE_SYSTEM,
    ROLE_USER,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    UsageInfo,
)
from functions.logic_provider_registry import ProviderRegistry, SelectionCriteria
from functions.logic_task_runner import Plan, Task

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERDICT_APPROVE = "approve"
VERDICT_CONCERNS = "concerns"
VERDICT_REDO = "redo"

SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_BLOCK = "block"

_ALL_VERDICTS = {VERDICT_APPROVE, VERDICT_CONCERNS, VERDICT_REDO}
_ALL_SEVERITIES = {SEVERITY_INFO, SEVERITY_WARN, SEVERITY_BLOCK}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Concern:
    """Одне зауваження критика."""

    message: str
    severity: str = SEVERITY_WARN  # info | warn | block
    task_id: str = ""  # "" → зауваження до плану в цілому
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "severity": self.severity,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class CritiqueResult:
    """Результат критики плану."""

    verdict: str = VERDICT_APPROVE  # approve | concerns | redo
    summary: str = ""
    concerns: List[Concern] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    usage: UsageInfo = field(default_factory=UsageInfo)
    raw_response: str = ""
    parse_error: str = ""

    @property
    def ok(self) -> bool:
        """`True`, якщо план не треба перероблювати."""
        return self.verdict in (VERDICT_APPROVE, VERDICT_CONCERNS)

    @property
    def blocking(self) -> bool:
        """`True`, якщо виконувати план НЕ можна."""
        if self.verdict == VERDICT_REDO:
            return True
        return any(c.severity == SEVERITY_BLOCK for c in self.concerns)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "summary": self.summary,
            "concerns": [c.to_dict() for c in self.concerns],
            "provider": self.provider,
            "model": self.model,
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
                "cost_usd": self.usage.cost_usd,
            },
            "parse_error": self.parse_error,
        }


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize_task(task: Task) -> Dict[str, Any]:
    return {
        "id": task.id,
        "kind": task.kind,
        "name": task.name,
        "params": task.params,
        "on_error": task.on_error,
        "depends_on": list(task.depends_on),
    }


def serialize_plan(plan: Plan) -> Dict[str, Any]:
    """Серіалізує `Plan` у словник, придатний для JSON-prompt-у."""
    return {
        "name": plan.name,
        "metadata": dict(plan.metadata),
        "tasks": [_serialize_task(t) for t in plan.tasks],
    }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


SYSTEM_PROMPT_UA = (
    "Ти — критик планів виконання для автономного агента MARK.\n"
    "Тобі дають план (JSON) із послідовністю задач, які агент збирається\n"
    "виконати. Твоє завдання — знайти ризики, суперечності, зайві кроки\n"
    "та небезпечні операції. Оціни план у цілому.\n"
    "\n"
    "Відповідай **тільки** валідним JSON-об'єктом у такій схемі:\n"
    "{\n"
    '  "verdict": "approve" | "concerns" | "redo",\n'
    '  "summary": "коротко українською, <= 2 речення",\n'
    '  "concerns": [\n'
    "    {\n"
    '      "task_id": "<id задачі або пусто для плану в цілому>",\n'
    '      "severity": "info" | "warn" | "block",\n'
    '      "message": "чітко, що саме не так",\n'
    '      "suggestion": "як виправити (опційно)"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "\n"
    "Правила вердикту:\n"
    " - `approve`    — план ок, ризиків немає.\n"
    " - `concerns`   — є попередження, але виконати можна.\n"
    " - `redo`       — план містить `severity=block` зауваження або\n"
    "                   потребує принципової переробки.\n"
    "\n"
    "Не повертай нічого крім JSON. Не використовуй markdown-огорожі."
)


def build_critic_messages(
    plan: Plan,
    *,
    context: str = "",
    policies: Optional[Dict[str, Any]] = None,
    system_prompt: str = SYSTEM_PROMPT_UA,
) -> List[ChatMessage]:
    """Формує `[system, user]` повідомлення для LLM-критика."""
    plan_json = json.dumps(serialize_plan(plan), ensure_ascii=False, indent=2)
    user_parts: List[str] = []
    if context:
        user_parts.append(f"Контекст виконання:\n{context}")
    if policies:
        user_parts.append(
            "Активні обмеження політик:\n"
            + json.dumps(policies, ensure_ascii=False, indent=2)
        )
    user_parts.append("План на перевірку:\n" + plan_json)
    user_parts.append("Дай JSON-вердикт за схемою вище.")
    return [
        ChatMessage(role=ROLE_SYSTEM, content=system_prompt),
        ChatMessage(role=ROLE_USER, content="\n\n".join(user_parts)),
    ]


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_block(text: str) -> str:
    """Знаходить найбільший правдоподібний JSON-об'єкт у відповіді."""
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        return fence.group(1)
    # fallback: від першого '{' до останнього '}'
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        return text[first : last + 1]
    return ""


def parse_critique_payload(payload: Dict[str, Any]) -> CritiqueResult:
    """Приводить dict до `CritiqueResult` зі стійкою валідацією."""
    verdict_raw = str(payload.get("verdict", "")).strip().lower()
    verdict = verdict_raw if verdict_raw in _ALL_VERDICTS else VERDICT_CONCERNS
    summary = str(payload.get("summary", "")).strip()

    concerns: List[Concern] = []
    raw_list = payload.get("concerns") or []
    if isinstance(raw_list, list):
        for entry in raw_list:
            if not isinstance(entry, dict):
                continue
            sev_raw = str(entry.get("severity", SEVERITY_WARN)).strip().lower()
            sev = sev_raw if sev_raw in _ALL_SEVERITIES else SEVERITY_WARN
            msg = str(entry.get("message", "")).strip()
            if not msg:
                continue
            concerns.append(
                Concern(
                    task_id=str(entry.get("task_id", "")).strip(),
                    severity=sev,
                    message=msg,
                    suggestion=str(entry.get("suggestion", "")).strip(),
                )
            )

    # Якщо модель поставила verdict=approve, але серед concerns є block —
    # піднімаємо вердикт до redo. Це stability guard: LLM-и часто
    # суперечать собі.
    if verdict == VERDICT_APPROVE and any(
        c.severity == SEVERITY_BLOCK for c in concerns
    ):
        verdict = VERDICT_REDO
    elif verdict == VERDICT_APPROVE and concerns:
        verdict = VERDICT_CONCERNS

    return CritiqueResult(verdict=verdict, summary=summary, concerns=concerns)


def parse_critic_response(response: ChatResponse) -> CritiqueResult:
    """Парсить `ChatResponse` → `CritiqueResult` або `verdict=concerns` + parse_error."""
    result = CritiqueResult(
        provider=response.provider,
        model=response.model,
        usage=response.usage,
        raw_response=response.content,
    )
    if not response.ok:
        result.verdict = VERDICT_CONCERNS
        result.parse_error = response.error or "provider error"
        result.summary = "critic provider failed; treat plan cautiously"
        return result

    block = _extract_json_block(response.content or "")
    if not block:
        result.verdict = VERDICT_CONCERNS
        result.parse_error = "no JSON object found"
        result.summary = "critic returned free-form text"
        return result

    try:
        payload = json.loads(block)
    except json.JSONDecodeError as exc:
        result.verdict = VERDICT_CONCERNS
        result.parse_error = f"json decode: {exc}"
        result.summary = "critic returned invalid JSON"
        return result

    if not isinstance(payload, dict):
        result.verdict = VERDICT_CONCERNS
        result.parse_error = "top-level payload is not an object"
        return result

    parsed = parse_critique_payload(payload)
    result.verdict = parsed.verdict
    result.summary = parsed.summary
    result.concerns = parsed.concerns
    return result


# ---------------------------------------------------------------------------
# PlanCritic
# ---------------------------------------------------------------------------


@dataclass
class PlanCritic:
    """LLM-критик, що оцінює `Plan` перед виконанням."""

    registry: ProviderRegistry
    model: Optional[str] = None
    temperature: float = 0.1
    max_tokens: Optional[int] = 600
    criteria: Optional[SelectionCriteria] = None
    system_prompt: str = SYSTEM_PROMPT_UA

    def review(
        self,
        plan: Plan,
        *,
        context: str = "",
        policies: Optional[Dict[str, Any]] = None,
    ) -> CritiqueResult:
        """Надсилає план критику й повертає `CritiqueResult`."""
        messages = build_critic_messages(
            plan,
            context=context,
            policies=policies,
            system_prompt=self.system_prompt,
        )
        request = ChatRequest(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            metadata={"purpose": "plan_critic", "plan_name": plan.name},
        )
        response = self.registry.chat(request, criteria=self.criteria)
        return parse_critic_response(response)


# ---------------------------------------------------------------------------
# Integration helper
# ---------------------------------------------------------------------------


ReplanFn = Callable[[Plan, CritiqueResult], Optional[Plan]]


@dataclass
class CriticRunResult:
    """Результат `review_and_run_plan()` (до та після виконання)."""

    critique: CritiqueResult
    executed: bool
    attempts: int  # скільки критик-циклів знадобилось (1 = approve з першого разу)
    final_plan: Plan
    run_result: Optional[Any] = None  # RunResult з TaskRunner, якщо executed
    stop_reason: str = ""


def review_and_run_plan(
    plan: Plan,
    *,
    critic: PlanCritic,
    runner: Any,  # TaskRunner (без типу, щоб уникнути імпорт-циклу та testability)
    max_redos: int = 1,
    replan_fn: Optional[ReplanFn] = None,
    context: str = "",
    policies: Optional[Dict[str, Any]] = None,
    report: Optional[Any] = None,
) -> CriticRunResult:
    """Виконує план, попередньо пропустивши його через критика.

    Цикл:
      1. `critic.review(plan)` → якщо `blocking` і ще лишились спроби
         + є `replan_fn` → отримати нову версію плану і повторити.
      2. Якщо зрештою вердикт все ще `blocking` → `executed=False`.
      3. Інакше → `runner.run(plan)`.
    """
    current = plan
    attempts = 0
    last_critique: CritiqueResult = CritiqueResult()
    while True:
        attempts += 1
        last_critique = critic.review(
            current, context=context, policies=policies
        )
        if not last_critique.blocking:
            break
        if attempts > max_redos or replan_fn is None:
            return CriticRunResult(
                critique=last_critique,
                executed=False,
                attempts=attempts,
                final_plan=current,
                stop_reason=(
                    "critic blocked plan; "
                    f"verdict={last_critique.verdict}, "
                    f"concerns={len(last_critique.concerns)}"
                ),
            )
        replanned = replan_fn(current, last_critique)
        if replanned is None:
            return CriticRunResult(
                critique=last_critique,
                executed=False,
                attempts=attempts,
                final_plan=current,
                stop_reason="replan_fn returned None",
            )
        current = replanned

    run_result = runner.run(current, report=report) if report else runner.run(current)
    return CriticRunResult(
        critique=last_critique,
        executed=True,
        attempts=attempts,
        final_plan=current,
        run_result=run_result,
    )


__all__ = [
    "VERDICT_APPROVE",
    "VERDICT_CONCERNS",
    "VERDICT_REDO",
    "SEVERITY_INFO",
    "SEVERITY_WARN",
    "SEVERITY_BLOCK",
    "Concern",
    "CritiqueResult",
    "PlanCritic",
    "CriticRunResult",
    "serialize_plan",
    "build_critic_messages",
    "parse_critic_response",
    "parse_critique_payload",
    "review_and_run_plan",
]
