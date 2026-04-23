"""TaskRunner — верхній рівень автономії (Phase 11.1).

Читає `Plan` (упорядкований список `Task`), виконує послідовно з інтеграцією:
- `PermissionGate` — допуск до кожної потенційно-живої дії.
- `ExecutionReport` — структурований звіт із таймінгами.
- `SessionBudget` — kill-switch на 3-6 годин.
- `ProviderRegistry` (опційно) — handler `call_provider`.

Дизайн:
- Handler-реєстр: `kind -> Callable`. Ззовні можна додавати/заміняти
  обробники (наприклад `delegate_to_windsurf` додасться у J4-PR).
- Kind-и, які вміють з коробки:
  - `noop`, `sleep`, `log` (безпечні).
  - `run_command` (через subprocess + PermissionGate).
  - `read_file` / `write_file` (через PermissionGate).
  - `call_provider` (через ProviderRegistry, якщо передана).
  - `sub_plan` (рекурсивний виклик TaskRunner).
- On-error: `stop` | `skip` | `retry[:n]` (retry з backoff).
- Всі потенційно блокуючі операції мають injection-точки (subprocess_runner,
  sleep_fn, time_fn) → тести 100% offline.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .logic_execution_report import (
    STATUS_DENIED,
    STATUS_ERROR,
    STATUS_EXPECT_FAILED,
    STATUS_OK,
    STATUS_PRECHECK_FAILED,
    STATUS_SKIPPED,
    ExecutionReport,
    StepReport,
)
from .logic_expectations import (
    ExpectContext,
    ExpectRegistry,
    ExpectSpec,
    ExpectationResult,
    all_ok,
    failures,
    parse_expect_list,
)
from .logic_permission_gate import (
    ACTION_READ_FILE,
    ACTION_RUN_COMMAND,
    ACTION_WRITE_FILE,
    Decision,
    PermissionGate,
    PermissionRequest,
)

ON_ERROR_STOP = "stop"
ON_ERROR_SKIP = "skip"
ON_ERROR_RETRY = "retry"


@dataclass
class Task:
    """Один крок плану."""

    id: str
    kind: str
    name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    on_error: str = ON_ERROR_STOP  # stop | skip | retry
    max_retries: int = 2
    retry_delay_s: float = 1.0
    depends_on: List[str] = field(default_factory=list)
    precheck: List[ExpectSpec] = field(default_factory=list)
    expect: List[ExpectSpec] = field(default_factory=list)

    def display(self) -> str:
        return self.name or self.id


@dataclass
class Plan:
    """Упорядкований список `Task`-ів + метадані."""

    name: str
    tasks: List[Task] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        tasks_raw = data.get("tasks") or []
        tasks: List[Task] = []
        for idx, entry in enumerate(tasks_raw):
            if not isinstance(entry, dict):
                raise ValueError(f"task #{idx} is not a dict: {entry!r}")
            tid = entry.get("id") or f"t{idx + 1}"
            kind = entry.get("kind")
            if not kind:
                raise ValueError(f"task #{idx} missing 'kind'")
            tasks.append(
                Task(
                    id=str(tid),
                    kind=str(kind),
                    name=entry.get("name", ""),
                    params=dict(entry.get("params") or {}),
                    on_error=entry.get("on_error", ON_ERROR_STOP),
                    max_retries=int(entry.get("max_retries", 2)),
                    retry_delay_s=float(entry.get("retry_delay_s", 1.0)),
                    depends_on=list(entry.get("depends_on") or []),
                    precheck=parse_expect_list(entry.get("precheck")),
                    expect=parse_expect_list(entry.get("expect")),
                )
            )
        return cls(
            name=str(data.get("name") or "(unnamed plan)"),
            tasks=tasks,
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def from_json(cls, payload: str) -> "Plan":
        return cls.from_dict(json.loads(payload))

    @classmethod
    def from_file(cls, path: str) -> "Plan":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


HandlerFn = Callable[["TaskContext"], Dict[str, Any]]


@dataclass
class TaskContext:
    """Що отримує handler."""

    task: Task
    runner: "TaskRunner"
    report: ExecutionReport
    gate: PermissionGate
    previous_results: Dict[str, Dict[str, Any]]


@dataclass
class RunResult:
    """Що повертає `TaskRunner.run(plan)`."""

    report: ExecutionReport
    all_ok: bool
    stopped_early: bool = False
    stop_reason: str = ""


class TaskRunner:
    """Core orchestrator. Thread-safe через per-instance lock навколо state."""

    def __init__(
        self,
        gate: Optional[PermissionGate] = None,
        *,
        subprocess_runner: Optional[Callable[..., Any]] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        time_fn: Callable[[], float] = time.time,
        should_stop_fn: Optional[Callable[[], bool]] = None,
        budget: Any = None,
        registry: Any = None,
        expect_registry: Optional[ExpectRegistry] = None,
        cwd: Optional[str] = None,
    ):
        self.gate = gate or PermissionGate()
        self.handlers: Dict[str, HandlerFn] = {}
        self._subprocess = subprocess_runner or subprocess.run
        self._sleep = sleep_fn
        self._time = time_fn
        self._should_stop = should_stop_fn
        self.budget = budget
        self.registry = registry
        self.expect_registry = expect_registry or ExpectRegistry()
        self.cwd = cwd
        self._lock = threading.Lock()

        self._install_builtin_handlers()

    # ----- Handler registration -----

    def register(self, kind: str, handler: HandlerFn) -> None:
        with self._lock:
            self.handlers[kind] = handler

    def unregister(self, kind: str) -> bool:
        with self._lock:
            return self.handlers.pop(kind, None) is not None

    def _install_builtin_handlers(self) -> None:
        self.register("noop", _handler_noop)
        self.register("log", _handler_log)
        self.register("log_task_spec", _handler_log_task_spec)
        self.register("sleep", _handler_sleep)
        self.register("run_command", _handler_run_command)
        self.register("read_file", _handler_read_file)
        self.register("write_file", _handler_write_file)
        self.register("call_provider", _handler_call_provider)
        self.register("sub_plan", _handler_sub_plan)
        self.register("batch_task", _handler_batch_task)

    # ----- Core loop -----

    def run(
        self,
        plan: Plan,
        *,
        report: Optional[ExecutionReport] = None,
    ) -> RunResult:
        report = report or ExecutionReport(plan_name=plan.name, time_fn=self._time)
        previous: Dict[str, Dict[str, Any]] = {}
        stopped_early = False
        stop_reason = ""
        all_ok = True

        for task in plan.tasks:
            # budget check
            if self._budget_says_stop():
                stopped_early = True
                stop_reason = "budget exhausted"
                break
            if self._should_stop and self._should_stop():
                stopped_early = True
                stop_reason = "should_stop_fn returned True"
                break

            # depends_on gating
            missing = [
                dep
                for dep in task.depends_on
                if previous.get(dep, {}).get("status") != STATUS_OK
            ]
            if missing:
                step = StepReport(
                    task_id=task.id,
                    task_name=task.display(),
                    kind=task.kind,
                    status=STATUS_SKIPPED,
                    started_at=self._time(),
                    finished_at=self._time(),
                    summary=f"dependencies not ok: {', '.join(missing)}",
                )
                report.record(step)
                previous[task.id] = {"status": STATUS_SKIPPED}
                continue

            step = self._run_one(task, report, previous)
            report.record(step)
            previous[task.id] = {
                "status": step.status,
                "summary": step.summary,
                "stdout_tail": step.stdout_tail,
                "error": step.error,
            }

            if step.status != STATUS_OK:
                all_ok = False
                if task.on_error == ON_ERROR_STOP:
                    stopped_early = True
                    stop_reason = f"task {task.id} failed (on_error=stop)"
                    break

        report.mark_finished()
        return RunResult(
            report=report,
            all_ok=all_ok,
            stopped_early=stopped_early,
            stop_reason=stop_reason,
        )

    # ----- Per-task execution -----

    def _run_one(
        self,
        task: Task,
        report: ExecutionReport,
        previous: Dict[str, Dict[str, Any]],
    ) -> StepReport:
        handler = self.handlers.get(task.kind)
        if handler is None:
            return StepReport(
                task_id=task.id,
                task_name=task.display(),
                kind=task.kind,
                status=STATUS_ERROR,
                started_at=self._time(),
                finished_at=self._time(),
                error=f"unknown kind: {task.kind!r}",
            )

        attempts = 1
        if task.on_error == ON_ERROR_RETRY:
            attempts = max(1, task.max_retries + 1)

        # ----- Step-Check: precheck (pre-handler). Якщо хоч одне не ok —
        # handler не запускаємо взагалі.
        if task.precheck:
            pre_results = self._evaluate_expectations(
                task.precheck, task=task, report=report,
                previous=previous, handler_result={},
            )
            if not all_ok(pre_results):
                now = self._time()
                failed = failures(pre_results)
                reasons = "; ".join(f"{r.kind}: {r.reason}" for r in failed)
                return StepReport(
                    task_id=task.id,
                    task_name=task.display(),
                    kind=task.kind,
                    status=STATUS_PRECHECK_FAILED,
                    started_at=now,
                    finished_at=now,
                    duration_s=0.0,
                    summary=f"precheck failed: {reasons}",
                    error=reasons,
                    metadata={
                        "precheck_results": [r.to_dict() for r in pre_results],
                    },
                )

        last_step: Optional[StepReport] = None
        for attempt in range(attempts):
            started = self._time()
            ctx = TaskContext(
                task=task,
                runner=self,
                report=report,
                gate=self.gate,
                previous_results=previous,
            )
            try:
                result = handler(ctx)
                if not isinstance(result, dict):
                    result = {"summary": str(result)}
            except Exception as exc:  # noqa: BLE001
                result = {
                    "status": STATUS_ERROR,
                    "error": f"{type(exc).__name__}: {exc}",
                }

            finished = self._time()
            status = str(result.get("status") or STATUS_OK)
            metadata = dict(result.get("metadata") or {})

            # ----- Actor-Critic MVP: expect (post-handler). Лише якщо
            # handler сам не впав і є що перевіряти.
            expect_results: List[ExpectationResult] = []
            if task.expect and status == STATUS_OK:
                expect_results = self._evaluate_expectations(
                    task.expect, task=task, report=report,
                    previous=previous, handler_result=result,
                )
                if not all_ok(expect_results):
                    failed = failures(expect_results)
                    reasons = "; ".join(
                        f"{r.kind}: {r.reason}" for r in failed
                    )
                    status = STATUS_EXPECT_FAILED
                    result["summary"] = (
                        (result.get("summary") or "")
                        + ("; " if result.get("summary") else "")
                        + f"expect failed: {reasons}"
                    )
                    result["error"] = reasons
            if expect_results:
                metadata["expect_results"] = [
                    r.to_dict() for r in expect_results
                ]

            step = StepReport(
                task_id=task.id,
                task_name=task.display(),
                kind=task.kind,
                status=status,
                started_at=started,
                finished_at=finished,
                duration_s=max(0.0, finished - started),
                summary=str(result.get("summary") or ""),
                stdout_tail=str(result.get("stdout_tail") or ""),
                error=str(result.get("error") or ""),
                cost_usd=float(result.get("cost_usd") or 0.0),
                prompt_tokens=int(result.get("prompt_tokens") or 0),
                completion_tokens=int(result.get("completion_tokens") or 0),
                metadata=metadata,
            )
            last_step = step
            if status == STATUS_OK or task.on_error != ON_ERROR_RETRY:
                break
            if attempt < attempts - 1:
                self._sleep(task.retry_delay_s)

        assert last_step is not None
        return last_step

    def _evaluate_expectations(
        self,
        specs: List[ExpectSpec],
        *,
        task: Task,
        report: ExecutionReport,
        previous: Dict[str, Dict[str, Any]],
        handler_result: Dict[str, Any],
    ) -> List[ExpectationResult]:
        totals = report.totals() if report is not None else {}
        by_status = dict(totals.get("by_status") or {})
        ctx = ExpectContext(
            task_id=task.id,
            task_kind=task.kind,
            handler_result=handler_result,
            report_totals={
                **by_status,
                "steps_total": int(totals.get("steps_total", 0) or 0),
            },
            previous_results=previous,
            cwd=self.cwd,
            extras={"plan_metadata": {}},
        )
        return self.expect_registry.evaluate_all(specs, ctx)

    # ----- Budget -----

    def _budget_says_stop(self) -> bool:
        if self.budget is None:
            return False
        should_stop = getattr(self.budget, "should_stop", None)
        if callable(should_stop):
            try:
                return bool(should_stop())
            except Exception:  # noqa: BLE001
                return False
        return False


# ---------------------------------------------------------------------------
# Built-in handlers
# ---------------------------------------------------------------------------


def _handler_noop(ctx: TaskContext) -> Dict[str, Any]:
    note = ctx.task.params.get("note", "")
    return {"status": STATUS_OK, "summary": note or "noop"}


def _handler_log(ctx: TaskContext) -> Dict[str, Any]:
    message = str(ctx.task.params.get("message", ""))
    ctx.report.add_event(f"[{ctx.task.id}] {message}")
    return {"status": STATUS_OK, "summary": message}


def _handler_log_task_spec(ctx: TaskContext) -> Dict[str, Any]:
    """Safe placeholder handler — логує `TaskSpec`-поля з `task.params`.

    Використовується `SkeletonPipeline` (Phase 13 S6 MVP) щоб наскрізний
    Plan міг бути виконаний (хоча й без корисної дії). Коли домен отримує
    реальний pipeline (S7+), skeleton перестає реєструватись і handler
    не викликається у виробничому потоці.
    """
    goal = str(ctx.task.params.get("spec_goal", ""))
    domain = str(ctx.task.params.get("spec_domain", ""))
    task_id = str(ctx.task.params.get("spec_task_id", ""))
    placeholder = bool(ctx.task.params.get("placeholder_step"))
    summary = (
        f"log_task_spec: task_id={task_id!r} domain={domain!r} goal={goal[:80]!r}"
    )
    ctx.report.add_event(f"[{ctx.task.id}] {summary}")
    return {
        "status": STATUS_OK,
        "summary": summary,
        "metadata": {"placeholder_step": placeholder},
    }


def _handler_sleep(ctx: TaskContext) -> Dict[str, Any]:
    seconds = float(ctx.task.params.get("seconds", 0.0))
    ctx.runner._sleep(seconds)
    return {"status": STATUS_OK, "summary": f"slept {seconds:g}s"}


def _handler_run_command(ctx: TaskContext) -> Dict[str, Any]:
    cmd = ctx.task.params.get("cmd") or ctx.task.params.get("command")
    if not cmd:
        return {"status": STATUS_ERROR, "error": "missing 'cmd' in params"}
    cwd = ctx.task.params.get("cwd")
    timeout = float(ctx.task.params.get("timeout", 60.0))

    decision = ctx.gate.ask(
        PermissionRequest(
            action=ACTION_RUN_COMMAND,
            resource=str(cmd),
            reason=ctx.task.params.get("reason", "run_command"),
            metadata={"cwd": cwd, "task_id": ctx.task.id},
        )
    )
    if not decision.allow:
        return {
            "status": STATUS_DENIED,
            "summary": f"denied: {decision.reason}",
            "error": decision.reason,
        }

    shell = bool(ctx.task.params.get("shell", isinstance(cmd, str)))
    try:
        proc = ctx.runner._subprocess(
            cmd,
            shell=shell,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": STATUS_ERROR,
            "error": f"{type(exc).__name__}: {exc}",
        }

    stdout = getattr(proc, "stdout", "") or ""
    stderr = getattr(proc, "stderr", "") or ""
    return_code = int(getattr(proc, "returncode", 0))
    status = STATUS_OK if return_code == 0 else STATUS_ERROR
    summary = (
        f"exit={return_code}, stdout_len={len(stdout)}, stderr_len={len(stderr)}"
    )
    return {
        "status": status,
        "summary": summary,
        "stdout_tail": stdout[-500:],
        "error": stderr.strip()[:500] if return_code != 0 else "",
        "metadata": {"return_code": return_code},
    }


def _handler_read_file(ctx: TaskContext) -> Dict[str, Any]:
    path = ctx.task.params.get("path")
    if not path:
        return {"status": STATUS_ERROR, "error": "missing 'path'"}
    decision = ctx.gate.ask(
        PermissionRequest(
            action=ACTION_READ_FILE,
            resource=str(path),
            reason="read_file",
            metadata={"task_id": ctx.task.id},
        )
    )
    if not decision.allow:
        return {"status": STATUS_DENIED, "error": decision.reason}
    try:
        content = Path(path).read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {"status": STATUS_ERROR, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "status": STATUS_OK,
        "summary": f"read {len(content)} chars",
        "metadata": {"content": content},
    }


def _handler_write_file(ctx: TaskContext) -> Dict[str, Any]:
    path = ctx.task.params.get("path")
    content = ctx.task.params.get("content", "")
    if not path:
        return {"status": STATUS_ERROR, "error": "missing 'path'"}
    decision = ctx.gate.ask(
        PermissionRequest(
            action=ACTION_WRITE_FILE,
            resource=str(path),
            reason="write_file",
            metadata={"task_id": ctx.task.id},
        )
    )
    if not decision.allow:
        return {"status": STATUS_DENIED, "error": decision.reason}
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {"status": STATUS_ERROR, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "status": STATUS_OK,
        "summary": f"wrote {len(str(content))} chars",
    }


def _handler_call_provider(ctx: TaskContext) -> Dict[str, Any]:
    if ctx.runner.registry is None:
        return {"status": STATUS_ERROR, "error": "no provider registry bound"}
    prompt = ctx.task.params.get("prompt")
    if not prompt:
        return {"status": STATUS_ERROR, "error": "missing 'prompt'"}
    try:
        from .logic_ai_adapter import (
            ROLE_SYSTEM,
            ROLE_USER,
            ChatMessage,
            ChatRequest,
        )
    except ImportError as exc:
        return {
            "status": STATUS_ERROR,
            "error": f"logic_ai_adapter unavailable: {exc}",
        }

    messages: List[ChatMessage] = []
    system = ctx.task.params.get("system")
    if system:
        messages.append(ChatMessage(role=ROLE_SYSTEM, content=str(system)))
    messages.append(ChatMessage(role=ROLE_USER, content=str(prompt)))

    request = ChatRequest(
        messages=messages,
        model=ctx.task.params.get("model"),
        temperature=float(ctx.task.params.get("temperature", 0.2)),
    )
    try:
        response = ctx.runner.registry.chat(request)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": STATUS_ERROR,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not getattr(response, "ok", False):
        return {
            "status": STATUS_ERROR,
            "error": getattr(response, "error", "") or "provider failed",
        }
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    cost = float(getattr(usage, "cost_usd", 0.0) or 0.0)
    return {
        "status": STATUS_OK,
        "summary": (response.content or "")[:200],
        "cost_usd": cost,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "metadata": {
            "provider": getattr(response, "provider", ""),
            "full_content": response.content,
        },
    }


def _handler_sub_plan(ctx: TaskContext) -> Dict[str, Any]:
    sub = ctx.task.params.get("plan")
    if isinstance(sub, dict):
        plan = Plan.from_dict(sub)
    elif isinstance(sub, Plan):
        plan = sub
    else:
        return {"status": STATUS_ERROR, "error": "'plan' must be dict or Plan"}
    result = ctx.runner.run(plan, report=ctx.report)
    return {
        "status": STATUS_OK if result.all_ok else STATUS_ERROR,
        "summary": f"sub-plan {plan.name}: {len(plan.tasks)} task(s), all_ok={result.all_ok}",
    }


def _handler_batch_task(ctx: TaskContext) -> Dict[str, Any]:
    """Phase 13 S8a — batch primitive.

    Виконує один і той самий під-task для кожного елемента списку `items`.
    Для кожного елемента будується свіжий `Task` на основі `task_template`,
    `item` інжектиться у params під ключем `item_param` (default: "item").
    Виконання — послідовне (concurrency — майбутнє розширення).

    Params:
      items: List[Any] — обовʼязково, елементи для ітерації.
      task_template: dict — обовʼязково, шаблон під-таска з полями:
        kind (str, required), params (dict, optional),
        on_error (str, optional), max_retries (int, optional),
        retry_delay_s (float, optional), expect (list, optional).
      item_param: str — ключ у params під який кладеться поточний item
        (default: "item").
      item_id_prefix: str — префікс для id під-таска (default: parent_id).
      on_item_error: "stop" | "skip" — поведінка на рівні batch
        (default: "skip" — пропустити проблемний item, продовжити).
      max_failures: int — якщо кількість fail > max_failures → батч
        зупиняється (default: -1 — без ліміту).
      progress_every: int — скільки items записувати у report.events
        (default: 10, -1 — не логувати).

    Returns:
      status: STATUS_OK якщо failures <= max_failures (або без ліміту)
        і `on_item_error != "stop"` АБО не було стопу.
      summary: агрегований рядок "N items: X ok, Y failed, Z skipped".
      metadata.items_total / items_ok / items_failed / items_skipped
      metadata.per_item: список {index, item_id, status, error}.
    """
    params = ctx.task.params
    items = params.get("items")
    template = params.get("task_template")

    if not isinstance(items, list):
        return {
            "status": STATUS_ERROR,
            "error": "'items' must be a list",
        }
    if not isinstance(template, dict) or not template.get("kind"):
        return {
            "status": STATUS_ERROR,
            "error": "'task_template' must be a dict with 'kind'",
        }

    item_param = str(params.get("item_param", "item"))
    id_prefix = str(params.get("item_id_prefix", ctx.task.id))
    on_item_error = str(params.get("on_item_error", ON_ERROR_SKIP))
    max_failures = int(params.get("max_failures", -1))
    progress_every = int(params.get("progress_every", 10))

    if on_item_error not in (ON_ERROR_STOP, ON_ERROR_SKIP):
        return {
            "status": STATUS_ERROR,
            "error": (
                f"'on_item_error' must be 'stop' or 'skip', got {on_item_error!r}"
            ),
        }

    items_total = len(items)
    ok = 0
    failed = 0
    skipped = 0
    stopped_early = False
    per_item: List[Dict[str, Any]] = []
    previous: Dict[str, Dict[str, Any]] = dict(ctx.previous_results)

    for idx, item in enumerate(items):
        # кооперативна зупинка
        runner = ctx.runner
        if runner._budget_says_stop():
            stopped_early = True
            break
        if runner._should_stop and runner._should_stop():
            stopped_early = True
            break

        item_id = f"{id_prefix}__item_{idx}"
        sub_params = dict(template.get("params") or {})
        sub_params[item_param] = item
        sub_params.setdefault("batch_index", idx)
        sub_task = Task(
            id=item_id,
            kind=str(template["kind"]),
            name=str(template.get("name") or f"item #{idx}"),
            params=sub_params,
            on_error=str(template.get("on_error", ON_ERROR_STOP)),
            max_retries=int(template.get("max_retries", 2)),
            retry_delay_s=float(template.get("retry_delay_s", 1.0)),
            depends_on=[],
            precheck=parse_expect_list(template.get("precheck")),
            expect=parse_expect_list(template.get("expect")),
        )

        step = runner._run_one(sub_task, ctx.report, previous)
        ctx.report.record(step)
        previous[item_id] = {
            "status": step.status,
            "summary": step.summary,
            "error": step.error,
        }
        per_item.append({
            "index": idx,
            "item_id": item_id,
            "status": step.status,
            "error": step.error,
        })

        if step.status == STATUS_OK:
            ok += 1
        elif step.status == STATUS_SKIPPED:
            skipped += 1
        else:
            failed += 1
            if on_item_error == ON_ERROR_STOP:
                stopped_early = True
                break
            if max_failures >= 0 and failed > max_failures:
                stopped_early = True
                break

        if progress_every > 0 and (idx + 1) % progress_every == 0:
            ctx.report.add_event(
                f"[{ctx.task.id}] batch progress: "
                f"{idx + 1}/{items_total} (ok={ok} fail={failed} skip={skipped})"
            )

    summary = (
        f"batch: {items_total} items, ok={ok}, failed={failed}, skipped={skipped}"
        + (" (stopped early)" if stopped_early else "")
    )
    # агрегований статус: OK тільки якщо жодна помилка і не було ранньої зупинки
    over_limit = max_failures >= 0 and failed > max_failures
    is_ok = (failed == 0) and not stopped_early and not over_limit
    return {
        "status": STATUS_OK if is_ok else STATUS_ERROR,
        "summary": summary,
        "metadata": {
            "items_total": items_total,
            "items_ok": ok,
            "items_failed": failed,
            "items_skipped": skipped,
            "stopped_early": stopped_early,
            "per_item": per_item,
        },
    }


__all__ = [
    "ON_ERROR_RETRY",
    "ON_ERROR_SKIP",
    "ON_ERROR_STOP",
    "Decision",
    "Plan",
    "RunResult",
    "StepReport",
    "Task",
    "TaskContext",
    "TaskRunner",
]
