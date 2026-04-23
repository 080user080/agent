"""core_task_intake — Phase 13.1.

Парсить вільний текст ТЗ (natural language) у структурований `TaskSpec`
через LLM (через `ProviderRegistry`). Якщо LLM повертає список clarification
questions — викликає `ask_user` callback і повторює запит з уточненнями.

Використовує існуючу Phase 9/J-інфраструктуру (`logic_provider_registry`,
`logic_ai_adapter`). JSON-ввід парситься через `logic_llm.safe_json_loads`
(санітайзер для LLM-артефактів типу \\n у рядках).

Залежності:
- `ProviderRegistry` з PR #9–10 (LM Studio / OpenAI-compatible провайдери).
- `safe_json_loads` / `clean_llm_tokens` з `logic_llm.py`.

Цей модуль нічого не виконує — лише перетворює ТЗ у TaskSpec.
Далі TaskSpec іде у `core_plan_compiler.compile_plan_from_spec()`.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional

from .logic_ai_adapter import ChatMessage, ChatRequest, ROLE_SYSTEM, ROLE_USER
from .logic_llm import clean_llm_tokens, safe_json_loads
from .logic_provider_registry import ProviderRegistry, SelectionCriteria


# ---------------------------------------------------------------------------
# Domains / permission modes / constants
# ---------------------------------------------------------------------------

DOMAIN_CODE = "code"
DOMAIN_PHOTO_BATCH = "photo_batch"
DOMAIN_PRESENTATION = "presentation"
DOMAIN_WEB_RESEARCH = "web_research"
DOMAIN_MIXED = "mixed"
DOMAIN_UNKNOWN = "unknown"

ALLOWED_DOMAINS = (
    DOMAIN_CODE,
    DOMAIN_PHOTO_BATCH,
    DOMAIN_PRESENTATION,
    DOMAIN_WEB_RESEARCH,
    DOMAIN_MIXED,
    DOMAIN_UNKNOWN,
)

PERMISSION_CONFIRM_EACH = "confirm_each"
PERMISSION_AUTO_READ = "auto_read"
PERMISSION_AUTO_ALL = "auto_all"

ALLOWED_PERMISSIONS = (
    PERMISSION_CONFIRM_EACH,
    PERMISSION_AUTO_READ,
    PERMISSION_AUTO_ALL,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BudgetHints:
    """М'які обмеження, які інтаке витягає з ТЗ (або defaults).

    Значення `None` означає «не вказано» — TaskRunner тоді бере дефолт
    з `SessionBudget`. Негативні значення нормалізуються до `None`.
    """

    max_hours: Optional[float] = None
    max_cost_usd: Optional[float] = None
    max_ai_calls: Optional[int] = None

    def __post_init__(self) -> None:
        if self.max_hours is not None and self.max_hours <= 0:
            self.max_hours = None
        if self.max_cost_usd is not None and self.max_cost_usd <= 0:
            self.max_cost_usd = None
        if self.max_ai_calls is not None and self.max_ai_calls <= 0:
            self.max_ai_calls = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaskSpec:
    """Структурована форма ТЗ після intake-парсингу.

    Мінімум для валідного TaskSpec: `goal` непорожнє, `domain` у
    `ALLOWED_DOMAINS`. Решта полів — опційні; `create_task_spec_from_tz`
    нормалізує дефолти.
    """

    goal: str
    domain: str = DOMAIN_UNKNOWN
    domain_sub: str = ""
    deliverables: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    preferred_ai_order: List[str] = field(default_factory=list)
    permission_mode: str = PERMISSION_CONFIRM_EACH
    budget: BudgetHints = field(default_factory=BudgetHints)
    input_files: List[str] = field(default_factory=list)
    output_dir: str = ""
    raw_tz: str = ""
    task_id: str = ""
    created_at: float = 0.0
    clarifications: List["Clarification"] = field(default_factory=list)

    def __post_init__(self) -> None:
        goal = (self.goal or "").strip()
        if not goal:
            raise ValueError("TaskSpec.goal is required and cannot be empty")
        self.goal = goal
        if self.domain not in ALLOWED_DOMAINS:
            self.domain = DOMAIN_UNKNOWN
        if self.permission_mode not in ALLOWED_PERMISSIONS:
            self.permission_mode = PERMISSION_CONFIRM_EACH
        if not self.task_id:
            self.task_id = _make_task_id()
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["budget"] = self.budget.to_dict()
        payload["clarifications"] = [c.to_dict() for c in self.clarifications]
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> "TaskSpec":
        budget_raw = data.get("budget") or {}
        if isinstance(budget_raw, dict):
            budget = BudgetHints(
                max_hours=_opt_float(budget_raw.get("max_hours")),
                max_cost_usd=_opt_float(budget_raw.get("max_cost_usd")),
                max_ai_calls=_opt_int(budget_raw.get("max_ai_calls")),
            )
        else:
            budget = BudgetHints()
        clarifications_raw = data.get("clarifications") or []
        clarifications: List[Clarification] = []
        if isinstance(clarifications_raw, list):
            for entry in clarifications_raw:
                if isinstance(entry, dict):
                    clarifications.append(Clarification.from_dict(entry))
        return cls(
            goal=str(data.get("goal", "")),
            domain=str(data.get("domain", DOMAIN_UNKNOWN)),
            domain_sub=str(data.get("domain_sub", "")),
            deliverables=_str_list(data.get("deliverables")),
            constraints=_str_list(data.get("constraints")),
            preferred_ai_order=_str_list(data.get("preferred_ai_order")),
            permission_mode=str(data.get("permission_mode", PERMISSION_CONFIRM_EACH)),
            budget=budget,
            input_files=_str_list(data.get("input_files")),
            output_dir=str(data.get("output_dir", "")),
            raw_tz=str(data.get("raw_tz", "")),
            task_id=str(data.get("task_id", "")),
            created_at=float(data.get("created_at") or 0.0),
            clarifications=clarifications,
        )


@dataclass
class Clarification:
    """Пара питання-відповідь для неоднозначних місць у ТЗ."""

    question: str
    answer: str = ""
    options: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Clarification":
        return cls(
            question=str(data.get("question", "")),
            answer=str(data.get("answer", "")),
            options=_str_list(data.get("options")),
        )


class IntakeError(RuntimeError):
    """Помилка intake-процесу (LLM не відповів, JSON не валідний і т.д.)."""


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Ти — парсер вільного ТЗ для автономного агента MARK.
Твоя задача: прочитати ТЗ користувача і заповнити структурований JSON.

ОБОВ'ЯЗКОВІ ПОЛЯ:
- "goal" (string, непорожнє) — короткий опис кінцевої мети (1 речення)
- "domain" (enum) — одне з: "code", "photo_batch", "presentation",
  "web_research", "mixed", "unknown"

ОПЦІЙНІ ПОЛЯ:
- "domain_sub" (string) — уточнення: "django" / "react" / "pptx" / "upscale"
- "deliverables" (list[string]) — що конкретно має бути на виході
- "constraints" (list[string]) — технічні обмеження (стек, формат, ліміти)
- "preferred_ai_order" (list[string]) — якщо юзер сказав «спочатку Codex,
  потім Windsurf» — записати у цьому порядку. Інакше пустий список.
- "permission_mode" (enum) — "confirm_each" | "auto_read" | "auto_all"
  (якщо юзер сказав «всі команди дозволяй» → "auto_all")
- "budget" (object) — {"max_hours": float | null, "max_cost_usd": float | null,
  "max_ai_calls": int | null}. null коли не вказано.
- "input_files" (list[string]) — шляхи/маски з ТЗ (наприклад
  "D:/photos/in/*.jpg")
- "output_dir" (string) — куди скидати результат
- "clarification_questions" (list[object]) — якщо ТЗ неоднозначне, повернути
  список питань (кожне: {"question": "...", "options": ["a","b"]}). Інакше
  пустий список.

ПРАВИЛА:
1. Відповідай СТРОГО ОДНИМ JSON-об'єктом, без markdown-fence-ів, без
   коментарів.
2. Якщо ТЗ зовсім непридатне (порожнє, незрозуміле) — постав
   "domain"="unknown" і додай хоч одне clarification_question.
3. "goal" переформульовуй стисло, не копіюй ТЗ як є.
4. НЕ вигадуй input_files/output_dir — тільки якщо явно у ТЗ.
"""


def _build_user_prompt(tz_text: str, clarifications: List[Clarification]) -> str:
    parts = [f"ТЗ користувача:\n---\n{tz_text.strip()}\n---"]
    if clarifications:
        parts.append("Попередні уточнення від користувача:")
        for c in clarifications:
            if c.answer:
                parts.append(f"- Питання: {c.question}\n  Відповідь: {c.answer}")
    parts.append(
        "Поверни JSON згідно зі схемою з system-промпту. "
        "Якщо clarification_questions не потрібні — постав порожній список."
    )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_block(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        return fence.group(1)
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        return text[first : last + 1]
    return ""


def _str_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None and str(item).strip()]
    return []


def _opt_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _opt_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _make_task_id() -> str:
    return f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_intake_response(
    response_text: str,
    *,
    raw_tz: str,
    previous_clarifications: Optional[List[Clarification]] = None,
) -> "IntakeResult":
    """Витягнути TaskSpec + можливі clarification_questions з LLM-відповіді.

    Цей метод виділений, щоб його можна було тестувати окремо без ходіння
    у мережу.
    """
    cleaned = clean_llm_tokens(response_text or "")
    block = _extract_json_block(cleaned)
    if not block:
        raise IntakeError(
            f"LLM response did not contain a JSON object: {response_text!r}"
        )
    try:
        payload = safe_json_loads(block)
    except json.JSONDecodeError as exc:
        raise IntakeError(f"JSON parse error: {exc}") from exc
    if not isinstance(payload, dict):
        raise IntakeError(f"Expected JSON object, got {type(payload).__name__}")

    questions_raw = payload.get("clarification_questions") or []
    pending_questions: List[Clarification] = []
    if isinstance(questions_raw, list):
        for entry in questions_raw:
            if isinstance(entry, dict):
                q = str(entry.get("question", "")).strip()
                if not q:
                    continue
                opts_raw = entry.get("options") or []
                options = _str_list(opts_raw)
                pending_questions.append(Clarification(question=q, options=options))
            elif isinstance(entry, str) and entry.strip():
                pending_questions.append(Clarification(question=entry.strip()))

    try:
        spec_payload = dict(payload)
        spec_payload.pop("clarification_questions", None)
        spec_payload["raw_tz"] = raw_tz
        spec_payload["clarifications"] = [
            c.to_dict() for c in (previous_clarifications or [])
        ]
        spec = TaskSpec.from_dict(spec_payload)
    except ValueError as exc:
        if pending_questions:
            return IntakeResult(spec=None, pending_questions=pending_questions)
        raise IntakeError(f"TaskSpec validation failed: {exc}") from exc

    return IntakeResult(spec=spec, pending_questions=pending_questions)


@dataclass
class IntakeResult:
    """Результат одного раунду intake-парсингу."""

    spec: Optional[TaskSpec]
    pending_questions: List[Clarification] = field(default_factory=list)


AskUserFn = Callable[[str, List[str]], str]


def create_task_spec_from_tz(
    tz_text: str,
    *,
    registry: ProviderRegistry,
    ask_user: Optional[AskUserFn] = None,
    criteria: Optional[SelectionCriteria] = None,
    max_rounds: int = 3,
    save_to: Optional[Path] = None,
) -> TaskSpec:
    """Перетворити вільне ТЗ у `TaskSpec`.

    Алгоритм:
    1. Запитати LLM → `IntakeResult`.
    2. Якщо є `pending_questions` і є `ask_user` → задати по одному
       питанню, накопичити відповіді, переопитати LLM з уточненнями.
    3. Максимум `max_rounds` раундів (інакше — віддати TaskSpec як є або
       підняти IntakeError).
    4. Якщо `save_to` вказано — записати JSON TaskSpec-а.
    """
    if not (tz_text or "").strip():
        raise ValueError("tz_text is required and cannot be empty")
    if max_rounds < 1:
        raise ValueError("max_rounds must be >= 1")

    clarifications: List[Clarification] = []
    last_result: Optional[IntakeResult] = None

    for _ in range(max_rounds):
        request = ChatRequest(
            messages=[
                ChatMessage(role=ROLE_SYSTEM, content=_SYSTEM_PROMPT),
                ChatMessage(
                    role=ROLE_USER,
                    content=_build_user_prompt(tz_text, clarifications),
                ),
            ],
            temperature=0.1,
        )
        response = registry.chat(request, criteria=criteria)
        if not response.ok:
            raise IntakeError(
                f"LLM provider error: {response.error or response.finish_reason}"
            )
        last_result = parse_intake_response(
            response.content,
            raw_tz=tz_text,
            previous_clarifications=clarifications,
        )
        if last_result.pending_questions and ask_user is not None:
            for q in last_result.pending_questions:
                answer = ask_user(q.question, list(q.options))
                clarifications.append(
                    Clarification(
                        question=q.question,
                        answer=answer or "",
                        options=list(q.options),
                    )
                )
            continue
        break

    if last_result is None or last_result.spec is None:
        raise IntakeError(
            "Intake failed: LLM kept asking clarifications without producing a "
            "valid TaskSpec"
        )

    spec = last_result.spec
    if clarifications:
        spec.clarifications = list(clarifications)

    if save_to is not None:
        save_task_spec(spec, save_to)

    return spec


def save_task_spec(spec: TaskSpec, path: Path) -> None:
    """Зберегти TaskSpec у JSON-файл (створює батьківські директорії)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = spec.to_dict()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_task_spec(path: Path) -> TaskSpec:
    """Завантажити TaskSpec з JSON-файлу."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return TaskSpec.from_dict(payload)
