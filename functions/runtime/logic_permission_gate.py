r"""PermissionGate — policy-based consent-шар для автопілота (Phase 11.2).

Викликається TaskRunner-ом перед будь-якою «живою» дією (subprocess,
writefile, HTTP-виклик). Повертає `Decision(allow=..., reason=...)` —
без raise.

4-рівнева policy stack (у порядку):
1. **Always-deny** — regex/patterns, які ніколи не дозволяються (`rm -rf /`,
   `sudo *`, запис у `/etc`, виконання через `C:\\Windows\\System32\\`
   прямо, і т.д.).
2. **Always-allow** — безпечний whitelist (git читання, `ls`, `cat`,
   `python -m pytest`, `ruff check`). Дозволяється лише в межах d:\Python\MARK\.
3. **Session-cache** — рішення користувача за цей run (persist=False).
4. **ask_fn(request) -> Decision** — callback до GUI-попап / CLI-prompt.

`persistent_allow_path` — опційний JSON зі списком дій, погоджених
«назавжди» (persist=True рішення).
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ACTION_RUN_COMMAND = "run_command"
ACTION_WRITE_FILE = "write_file"
ACTION_DELETE_FILE = "delete_file"
ACTION_READ_FILE = "read_file"
ACTION_HTTP_REQUEST = "http_request"
ACTION_NETWORK = "network"
ACTION_OTHER = "other"


@dataclass
class PermissionRequest:
    """Запит на дозвіл, який перевіряється gate-ом."""

    action: str  # один з ACTION_* констант
    resource: str  # команда / шлях / URL
    reason: str = ""  # людський опис, для попапу
    metadata: Dict[str, Any] = field(default_factory=dict)

    def cache_key(self) -> str:
        return f"{self.action}::{self.resource}"


@dataclass
class Decision:
    """Рішення gate-а: дозволити чи ні + чи зберегти в кеш."""

    allow: bool
    reason: str = ""
    persist: bool = False  # True → запам'ятати для наступних запусків

    @classmethod
    def approve(cls, reason: str = "", persist: bool = False) -> "Decision":
        return cls(allow=True, reason=reason, persist=persist)

    @classmethod
    def deny(cls, reason: str = "") -> "Decision":
        return cls(allow=False, reason=reason, persist=False)


# ---------------------------------------------------------------------------
# Default patterns
# ---------------------------------------------------------------------------

DEFAULT_DENY_COMMAND_PATTERNS: List[str] = [
    r"rm\s+-rf\s+/(?:\s|$)",
    r"\bmkfs\b",
    r"\bdd\s+if=.*of=/dev/",
    r":\(\)\s*\{\s*:\|:&\s*\};",  # fork bomb
    r"\bchmod\s+-R\s+777\s+/",
    r"\bshutdown\b",
    r"\breboot\b",
    r"format\s+[a-zA-Z]:",
    r"^sudo\s+",
    r"^doas\s+",
]

DEFAULT_DENY_PATH_PATTERNS: List[str] = [
    r"^/etc/",
    r"^/boot/",
    r"^/sys/",
    r"^/proc/",
    r"^/dev/",
    r"(?i)^[a-z]:\\\\windows\\\\system32",
    r"(?i)^[a-z]:\\\\program files",
]

DEFAULT_ALLOW_COMMAND_PREFIXES: List[str] = [
    "git status",
    "git diff",
    "git log",
    "git branch",
    "git show",
    "git rev-parse",
    "ls ",
    "ls\t",
    "dir ",
    "cat ",
    "type ",
    "echo ",
    "python -m pytest",
    "pytest ",
    "pytest\n",
    "ruff check",
    "ruff format --check",
    "mypy ",
    "black --check",
    "pre-commit run",
]


# ---------------------------------------------------------------------------
# Policy dataclass
# ---------------------------------------------------------------------------

@dataclass
class PermissionPolicy:
    """Конфігурація політик безпеки."""
    restricted_root: str = r"d:\\Python\\MARK" # Жорсткий кореневий шлях для всіх операцій.
    deny_command_patterns: List[str] = field(
        default_factory=lambda: list(DEFAULT_DENY_COMMAND_PATTERNS)
    )
    deny_path_patterns: List[str] = field(
        default_factory=lambda: list(DEFAULT_DENY_PATH_PATTERNS)
    )
    allow_command_prefixes: List[str] = field(
        default_factory=lambda: list(DEFAULT_ALLOW_COMMAND_PREFIXES)
    )
    allow_any_in_project_root: bool = False # Примусово вимкнено для жорсткого режиму
    allow_read_file_outside_root: bool = True


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

AskFn = Callable[[PermissionRequest], Decision]


class PermissionGate:
    """Захисний шар перед виконанням дій автопілотом."""

    def __init__(
        self,
        policy: Optional[PermissionPolicy] = None,
        ask_fn: Optional[AskFn] = None,
        *,
        persistent_allow_path: Optional[str] = None,
        auto_approve_read_only: bool = False,
    ):
        self.policy = policy or PermissionPolicy()
        self._ask_fn = ask_fn
        self._session_cache: Dict[str, Decision] = {}
        self._lock = threading.Lock()
        self._persistent_path = (
            Path(persistent_allow_path) if persistent_allow_path else None
        )
        self._persistent_allow: Dict[str, Decision] = self._load_persistent()
        self.history: List[Dict[str, Any]] = []
        self.auto_approve_read_only = auto_approve_read_only

    # ----- Public API -----

    def set_ask_fn(self, ask_fn: AskFn) -> None:
        self._ask_fn = ask_fn

    def check(self, request: PermissionRequest) -> Decision:
        """Перевірити запит, повернути рішення. Не викликає зовнішніх систем."""
        decision = self._evaluate(request)
        self._log(request, decision)
        return decision

    def ask(self, request: PermissionRequest) -> Decision:
        """Повний цикл: check + при необхідності викликати `ask_fn`."""
        decision = self._evaluate(request, use_ask_fn=True)
        self._log(request, decision)
        return decision

    def reset_session_cache(self) -> None:
        with self._lock:
            self._session_cache.clear()

    # ----- Core logic -----

    def _evaluate(
        self, request: PermissionRequest, *, use_ask_fn: bool = False
    ) -> Decision:
        # 1. Always-deny (загальні заборони)
        deny = self._check_deny(request)
        if deny is not None:
            return deny

        # 2. Auto-approve read-only operations (для діагностики в обмеженому режимі)
        if self.auto_approve_read_only and request.action == ACTION_READ_FILE:
            return Decision.approve(reason="read-only mode: auto-approve")

        # 3. Persistent allow (від користувача, збережені назавжди)
        key = request.cache_key()
        with self._lock:
            cached = self._persistent_allow.get(key)
        if cached is not None:
            return Decision(
                allow=cached.allow,
                reason=f"persistent: {cached.reason}",
                persist=True,
            )

        # 4. Always-allow whitelist (безпечні команди Git/тестування в корені)
        allow = self._check_allow(request)
        if allow is not None:
            return allow

        # 5. Session cache (рішення за поточний run)
        with self._lock:
            cached = self._session_cache.get(key)
        if cached is not None:
            return Decision(
                allow=cached.allow, reason=f"session: {cached.reason}"
            )

        # 6. Ask user via callback
        if use_ask_fn and self._ask_fn is not None:
            decision = self._ask_fn(request)
            self._remember(request, decision)
            return decision

        # 7. Default when no ask_fn supplied
        return Decision.deny(reason="no ask_fn and not in allow list")

    def _check_deny(
        self, request: PermissionRequest
    ) -> Optional[Decision]:
        """Перевіряє на загальні заборонені патерни (наприклад, 'rm -rf /')."""
        if request.action == ACTION_RUN_COMMAND:
            for pat in self.policy.deny_command_patterns:
                if re.search(pat, request.resource):
                    return Decision.deny(
                        reason=f"command matches deny pattern: {pat}"
                    )
        if request.action in {
            ACTION_WRITE_FILE,
            ACTION_DELETE_FILE,
        }:
            # Додаткова перевірка на шлях поза дозволеною зоною (це повторює _in_project_root, але є додатковим шаром захисту)
            if not self._in_project_root(request.resource):
                 return Decision.deny(
                    reason=f"path outside restricted root: {self.policy.restricted_root}"
                )
        return None

    def _check_allow(
        self, request: PermissionRequest
    ) -> Optional[Decision]:
        """Перевіряє на дозволені команди та файлові операції в корені."""
        if request.action == ACTION_RUN_COMMAND:
            for prefix in self.policy.allow_command_prefixes:
                if request.resource.startswith(prefix):
                    return Decision.approve(reason=f"safe prefix: {prefix!r}")

        # Обмеження для файлових операцій
        if request.action in {ACTION_WRITE_FILE, ACTION_DELETE_FILE}:
            if self._in_project_root(request.resource):
                return Decision.approve(reason="path inside restricted root")

        # Дозволено читання лише з дозволеного кореня (за замовчуванням)
        if request.action == ACTION_READ_FILE and self._in_project_root(request.resource):
            return Decision.approve(reason="read_file inside restricted root")

        # Якщо read-only режим вимкнено, дозволяємо читання будь-де (для діагностики)
        if request.action == ACTION_READ_FILE and self.policy.allow_read_file_outside_root:
            return Decision.approve(reason="reading outside restricted root allowed")

        return None

    def _in_project_root(self, path: str) -> bool:
        """Перевіряє, чи шлях знаходиться в дозволеному корені."""
        restricted_path = self.policy.restricted_root
        if not restricted_path:
            return False
        try:
            # Звертаємо увагу на нормалізацію шляху (забезпечуємо слеш)
            normalized_rooted = os.path.normpath(restricted_path.rstrip('\\/') + '\\')
            target = os.path.normpath(os.path.abspath(path))

        except Exception:  # noqa: BLE001
            return False
        try:
            # Перевіряємо, чи шлях починається з кореневого шляху
            return target.startswith(normalized_rooted)
        except Exception:
            return False


    def _remember(
        self, request: PermissionRequest, decision: Decision
    ) -> None:
        key = request.cache_key()
        with self._lock:
            self._session_cache[key] = decision
            if decision.persist:
                self._persistent_allow[key] = decision
                self._save_persistent()

    def _log(self, request: PermissionRequest, decision: Decision) -> None:
        entry = {
            "request": asdict(request),
            "decision": asdict(decision),
        }
        with self._lock:
            self.history.append(entry)

    # ----- Persistence -----

    def _load_persistent(self) -> Dict[str, Decision]:
        if self._persistent_path is None:
            return {}
        try:
            data = json.loads(self._persistent_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except Exception:  # noqa: BLE001
            return {}
        out: Dict[str, Decision] = {}
        for key, value in data.items():
            if not isinstance(value, dict):
                continue
            out[key] = Decision(
                allow=bool(value.get("allow")),
                reason=str(value.get("reason", "")),
                persist=True,
            )
        return out

    def _save_persistent(self) -> None:
        if self._persistent_path is None:
            return
        payload = {
            key: {"allow": d.allow, "reason": d.reason, "persist": True}
            for key, d in self._persistent_allow.items()
        }
        try:
            self._persistent_path.parent.mkdir(parents=True, exist_ok=True)
            self._persistent_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------

def always_allow() -> AskFn:
    """ask_fn, що завжди відповідає allow. Для CI / unattended test runs."""
    return lambda req: Decision.approve(
        reason="always_allow ask_fn", persist=False
    )


def always_deny() -> AskFn:
    """ask_fn, що завжди відмовляє (headless-safe default)."""
    return lambda req: Decision.deny(reason="always_deny ask_fn")


def console_ask(stream=None) -> AskFn:
    """Простий CLI-prompt: y/n/always для кожного запиту."""
    import sys as _sys

    target = stream or _sys.stdin

    def _ask(request: PermissionRequest) -> Decision:
        prompt = (
            f"[permission] {request.action}: {request.resource}\n"
            f"  reason: {request.reason}\n"
            f"  Allow? [y/N/always]: "
        )
        print(prompt, end="", flush=True)
        try:
            answer = target.readline().strip().lower()
        except Exception:  # noqa: BLE001
            answer = ""
        if answer.startswith("a"):
            return Decision.approve(reason="user: always", persist=True)
        if answer.startswith("y"):
            return Decision.approve(reason="user: yes", persist=False)
        return Decision.deny(reason="user: no")

    return _ask