"""Step-Check — очікувані стани до/після виконання задачі (Phase 12.1).

Проблема, яку розв'язуємо: зараз `TaskRunner` вирішує «задача OK» лише за
`status` від handler-а. Якщо handler скаже `STATUS_OK`, але реальний стан
системи не досягнутий (файл не створено, вікно не відкрилось) — агент
цього не помітить.

Рішення: до кожної `Task` опційно додається список **очікувань**
(`ExpectSpec`), які перевіряються:

- `precheck`  — **перед** запуском (санітарна перевірка стану світу;
                  якщо вже не виконане — задача пропускається з
                  `STATUS_PRECHECK_FAILED`).
- `expect`    — **після** запуску (Actor-Critic MVP; якщо хоч одне
                  не спрацювало → статус `STATUS_EXPECT_FAILED`, яким
                  можна тригерити repair-цикл у наступних фазах).

Evaluator-и — розширюваний registry, щоб легко додавати нові види
(image_match, http_status) без правлення основного модуля. Всі убудовані
evaluator-и cross-platform-safe (з опційним fallback-ом для
Windows-specific, коли відсутній `pygetwindow` / `psutil`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants — закритий словник kind-ів першої ітерації
# ---------------------------------------------------------------------------

EXPECT_FILE_EXISTS = "file_exists"
EXPECT_FILE_MISSING = "file_missing"
EXPECT_STDOUT_CONTAINS = "stdout_contains"
EXPECT_STDERR_CONTAINS = "stderr_contains"
EXPECT_RETURN_CODE = "return_code"
EXPECT_WINDOW_TITLE_CONTAINS = "window_title_contains"
EXPECT_PROCESS_RUNNING = "process_running"
EXPECT_PROCESS_NOT_RUNNING = "process_not_running"
EXPECT_NO_ERROR_IN_REPORT = "no_error_in_report"
EXPECT_OK_COUNT_AT_LEAST = "ok_count_at_least"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ExpectSpec:
    """Одне очікування: `kind` + параметри."""

    kind: str
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpectSpec":
        kind = data.get("kind")
        if not kind:
            raise ValueError(f"expect spec missing 'kind': {data!r}")
        params = {k: v for k, v in data.items() if k != "kind"}
        return cls(kind=str(kind), params=params)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, **self.params}


@dataclass
class ExpectationResult:
    """Результат перевірки одного `ExpectSpec`."""

    kind: str
    ok: bool
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "ok": self.ok,
            "reason": self.reason,
            "details": self.details,
        }


@dataclass
class ExpectContext:
    """Контекст, доступний evaluator-у."""

    task_id: str = ""
    task_kind: str = ""
    handler_result: Dict[str, Any] = field(default_factory=dict)
    report_totals: Dict[str, Any] = field(default_factory=dict)
    previous_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cwd: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)


EvaluatorFn = Callable[[ExpectSpec, ExpectContext], ExpectationResult]


# ---------------------------------------------------------------------------
# Built-in evaluators
# ---------------------------------------------------------------------------


def _resolve_path(path_raw: str, cwd: Optional[str]) -> Path:
    path = Path(path_raw)
    if not path.is_absolute() and cwd:
        path = Path(cwd) / path
    return path


def _eval_file_exists(spec: ExpectSpec, ctx: ExpectContext) -> ExpectationResult:
    path_raw = spec.params.get("path")
    if not path_raw:
        return ExpectationResult(
            kind=spec.kind, ok=False, reason="missing 'path' in expect"
        )
    path = _resolve_path(str(path_raw), ctx.cwd)
    exists = path.exists()
    return ExpectationResult(
        kind=spec.kind,
        ok=exists,
        reason="" if exists else f"file not found: {path}",
        details={"path": str(path)},
    )


def _eval_file_missing(spec: ExpectSpec, ctx: ExpectContext) -> ExpectationResult:
    path_raw = spec.params.get("path")
    if not path_raw:
        return ExpectationResult(
            kind=spec.kind, ok=False, reason="missing 'path' in expect"
        )
    path = _resolve_path(str(path_raw), ctx.cwd)
    missing = not path.exists()
    return ExpectationResult(
        kind=spec.kind,
        ok=missing,
        reason="" if missing else f"file unexpectedly present: {path}",
        details={"path": str(path)},
    )


def _eval_stdout_contains(
    spec: ExpectSpec, ctx: ExpectContext
) -> ExpectationResult:
    value = str(spec.params.get("value", ""))
    if not value:
        return ExpectationResult(
            kind=spec.kind, ok=False, reason="missing 'value'"
        )
    stdout = str(ctx.handler_result.get("stdout_tail", ""))
    ok = value in stdout
    return ExpectationResult(
        kind=spec.kind,
        ok=ok,
        reason="" if ok else f"stdout does not contain {value!r}",
        details={"stdout_len": len(stdout)},
    )


def _eval_stderr_contains(
    spec: ExpectSpec, ctx: ExpectContext
) -> ExpectationResult:
    value = str(spec.params.get("value", ""))
    if not value:
        return ExpectationResult(
            kind=spec.kind, ok=False, reason="missing 'value'"
        )
    err = str(ctx.handler_result.get("error", ""))
    ok = value in err
    return ExpectationResult(
        kind=spec.kind,
        ok=ok,
        reason="" if ok else f"stderr does not contain {value!r}",
    )


def _eval_return_code(spec: ExpectSpec, ctx: ExpectContext) -> ExpectationResult:
    expected = spec.params.get("value", 0)
    meta = ctx.handler_result.get("metadata") or {}
    actual = meta.get("return_code")
    if actual is None:
        return ExpectationResult(
            kind=spec.kind,
            ok=False,
            reason="handler did not report return_code",
        )
    ok = int(actual) == int(expected)
    return ExpectationResult(
        kind=spec.kind,
        ok=ok,
        reason="" if ok else f"expected return_code={expected}, got {actual}",
        details={"expected": expected, "actual": actual},
    )


def _eval_window_title_contains(
    spec: ExpectSpec, ctx: ExpectContext
) -> ExpectationResult:
    substr = str(spec.params.get("value", ""))
    if not substr:
        return ExpectationResult(
            kind=spec.kind, ok=False, reason="missing 'value'"
        )
    try:
        import pygetwindow  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return ExpectationResult(
            kind=spec.kind,
            ok=False,
            reason=f"pygetwindow unavailable: {exc}",
        )
    try:
        titles = [w.title for w in pygetwindow.getAllWindows() if w.title]
    except Exception as exc:  # noqa: BLE001
        return ExpectationResult(
            kind=spec.kind, ok=False, reason=f"enumeration failed: {exc}"
        )
    matching = [t for t in titles if substr in t]
    ok = bool(matching)
    return ExpectationResult(
        kind=spec.kind,
        ok=ok,
        reason="" if ok else f"no window title contains {substr!r}",
        details={"match_count": len(matching)},
    )


def _eval_process_running(
    spec: ExpectSpec, ctx: ExpectContext
) -> ExpectationResult:
    name = str(spec.params.get("name", "")).lower()
    if not name:
        return ExpectationResult(
            kind=spec.kind, ok=False, reason="missing 'name'"
        )
    try:
        import psutil  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return ExpectationResult(
            kind=spec.kind, ok=False, reason=f"psutil unavailable: {exc}"
        )
    running = False
    count = 0
    for proc in psutil.process_iter(["name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
        except Exception:  # noqa: BLE001
            continue
        if pname == name or pname.startswith(name):
            running = True
            count += 1
    return ExpectationResult(
        kind=spec.kind,
        ok=running,
        reason="" if running else f"process {name!r} not running",
        details={"count": count},
    )


def _eval_process_not_running(
    spec: ExpectSpec, ctx: ExpectContext
) -> ExpectationResult:
    res = _eval_process_running(spec, ctx)
    # invert; propagate psutil/unavailable errors as-is.
    if "unavailable" in res.reason:
        return res
    inverted_ok = not res.ok
    return ExpectationResult(
        kind=spec.kind,
        ok=inverted_ok,
        reason="" if inverted_ok else f"process {spec.params.get('name')!r} still running",
        details=res.details,
    )


def _eval_no_error_in_report(
    spec: ExpectSpec, ctx: ExpectContext
) -> ExpectationResult:
    errors = int(ctx.report_totals.get("error", 0))
    ok = errors == 0
    return ExpectationResult(
        kind=spec.kind,
        ok=ok,
        reason="" if ok else f"report has {errors} error step(s)",
        details={"error_count": errors},
    )


def _eval_ok_count_at_least(
    spec: ExpectSpec, ctx: ExpectContext
) -> ExpectationResult:
    threshold = int(spec.params.get("value", 1))
    ok_count = int(ctx.report_totals.get("ok", 0))
    ok = ok_count >= threshold
    return ExpectationResult(
        kind=spec.kind,
        ok=ok,
        reason="" if ok else f"only {ok_count} ok steps, need >= {threshold}",
        details={"ok_count": ok_count, "threshold": threshold},
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ExpectRegistry:
    """Mapping kind → evaluator function. Thread-safety — не потрібна (
    реєструється один раз на старті).
    """

    def __init__(self) -> None:
        self._map: Dict[str, EvaluatorFn] = {}
        self._install_builtins()

    def register(self, kind: str, fn: EvaluatorFn) -> None:
        self._map[kind] = fn

    def unregister(self, kind: str) -> bool:
        return self._map.pop(kind, None) is not None

    def kinds(self) -> List[str]:
        return sorted(self._map.keys())

    def get(self, kind: str) -> Optional[EvaluatorFn]:
        return self._map.get(kind)

    def evaluate(
        self, spec: ExpectSpec, ctx: ExpectContext
    ) -> ExpectationResult:
        fn = self._map.get(spec.kind)
        if fn is None:
            return ExpectationResult(
                kind=spec.kind,
                ok=False,
                reason=f"unknown expect kind: {spec.kind!r}",
            )
        try:
            return fn(spec, ctx)
        except Exception as exc:  # noqa: BLE001
            return ExpectationResult(
                kind=spec.kind,
                ok=False,
                reason=f"evaluator raised {type(exc).__name__}: {exc}",
            )

    def evaluate_all(
        self, specs: List[ExpectSpec], ctx: ExpectContext
    ) -> List[ExpectationResult]:
        return [self.evaluate(s, ctx) for s in specs]

    def _install_builtins(self) -> None:
        self.register(EXPECT_FILE_EXISTS, _eval_file_exists)
        self.register(EXPECT_FILE_MISSING, _eval_file_missing)
        self.register(EXPECT_STDOUT_CONTAINS, _eval_stdout_contains)
        self.register(EXPECT_STDERR_CONTAINS, _eval_stderr_contains)
        self.register(EXPECT_RETURN_CODE, _eval_return_code)
        self.register(EXPECT_WINDOW_TITLE_CONTAINS, _eval_window_title_contains)
        self.register(EXPECT_PROCESS_RUNNING, _eval_process_running)
        self.register(EXPECT_PROCESS_NOT_RUNNING, _eval_process_not_running)
        self.register(EXPECT_NO_ERROR_IN_REPORT, _eval_no_error_in_report)
        self.register(EXPECT_OK_COUNT_AT_LEAST, _eval_ok_count_at_least)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_expect_list(raw: Any) -> List[ExpectSpec]:
    """Толерантно перетворює `raw` (None / list / dict) на список `ExpectSpec`."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [ExpectSpec.from_dict(raw)]
    if not isinstance(raw, list):
        raise ValueError(f"expect must be list or dict, got {type(raw).__name__}")
    specs: List[ExpectSpec] = []
    for idx, entry in enumerate(raw):
        if isinstance(entry, ExpectSpec):
            specs.append(entry)
        elif isinstance(entry, dict):
            specs.append(ExpectSpec.from_dict(entry))
        else:
            raise ValueError(
                f"expect[{idx}] must be dict or ExpectSpec, got {type(entry).__name__}"
            )
    return specs


def all_ok(results: List[ExpectationResult]) -> bool:
    return all(r.ok for r in results)


def failures(results: List[ExpectationResult]) -> List[ExpectationResult]:
    return [r for r in results if not r.ok]


__all__ = [
    "EXPECT_FILE_EXISTS",
    "EXPECT_FILE_MISSING",
    "EXPECT_STDOUT_CONTAINS",
    "EXPECT_STDERR_CONTAINS",
    "EXPECT_RETURN_CODE",
    "EXPECT_WINDOW_TITLE_CONTAINS",
    "EXPECT_PROCESS_RUNNING",
    "EXPECT_PROCESS_NOT_RUNNING",
    "EXPECT_NO_ERROR_IN_REPORT",
    "EXPECT_OK_COUNT_AT_LEAST",
    "ExpectSpec",
    "ExpectationResult",
    "ExpectContext",
    "EvaluatorFn",
    "ExpectRegistry",
    "parse_expect_list",
    "all_ok",
    "failures",
]
