"""Tests for functions.logic_permission_gate (Phase 11.2)."""
from __future__ import annotations

import json

from functions.logic_permission_gate import (
    ACTION_READ_FILE,
    ACTION_RUN_COMMAND,
    ACTION_WRITE_FILE,
    Decision,
    PermissionGate,
    PermissionPolicy,
    PermissionRequest,
    always_allow,
    always_deny,
)


def _req_cmd(cmd: str) -> PermissionRequest:
    return PermissionRequest(action=ACTION_RUN_COMMAND, resource=cmd)


def _req_write(path: str) -> PermissionRequest:
    return PermissionRequest(action=ACTION_WRITE_FILE, resource=path)


def _req_read(path: str) -> PermissionRequest:
    return PermissionRequest(action=ACTION_READ_FILE, resource=path)


class TestAlwaysDeny:
    def test_rm_rf_root_denied(self):
        g = PermissionGate()
        d = g.check(_req_cmd("rm -rf /"))
        assert d.allow is False
        assert "deny pattern" in d.reason

    def test_sudo_denied(self):
        g = PermissionGate()
        d = g.check(_req_cmd("sudo apt install htop"))
        assert d.allow is False

    def test_fork_bomb_denied(self):
        g = PermissionGate()
        d = g.check(_req_cmd(":(){:|:&};:"))
        assert d.allow is False

    def test_mkfs_denied(self):
        g = PermissionGate()
        d = g.check(_req_cmd("mkfs.ext4 /dev/sda1"))
        assert d.allow is False

    def test_write_to_etc_denied(self):
        g = PermissionGate()
        d = g.check(_req_write("/etc/hosts"))
        assert d.allow is False


class TestAlwaysAllow:
    def test_git_status_allowed(self):
        g = PermissionGate(ask_fn=always_deny())
        d = g.ask(_req_cmd("git status"))
        assert d.allow is True
        assert "safe prefix" in d.reason

    def test_pytest_allowed(self):
        g = PermissionGate(ask_fn=always_deny())
        d = g.ask(_req_cmd("python -m pytest tests/"))
        assert d.allow is True

    def test_ls_allowed(self):
        g = PermissionGate(ask_fn=always_deny())
        d = g.ask(_req_cmd("ls -la"))
        assert d.allow is True

    def test_ruff_allowed(self):
        g = PermissionGate(ask_fn=always_deny())
        d = g.ask(_req_cmd("ruff check ."))
        assert d.allow is True


class TestProjectRoot:
    def test_write_inside_project_root_allowed(self, tmp_path):
        policy = PermissionPolicy(project_root=str(tmp_path))
        g = PermissionGate(policy=policy, ask_fn=always_deny())
        d = g.ask(_req_write(str(tmp_path / "file.txt")))
        assert d.allow is True
        assert "project_root" in d.reason

    def test_write_outside_project_root_asks(self, tmp_path):
        policy = PermissionPolicy(project_root=str(tmp_path))
        g = PermissionGate(policy=policy, ask_fn=always_allow())
        d = g.ask(_req_write("/home/otheruser/x.txt"))
        assert d.allow is True
        assert "always_allow" in d.reason

    def test_nested_path_allowed(self, tmp_path):
        policy = PermissionPolicy(project_root=str(tmp_path))
        g = PermissionGate(policy=policy, ask_fn=always_deny())
        d = g.ask(_req_write(str(tmp_path / "deep" / "nested" / "file.txt")))
        assert d.allow is True


class TestReadFileDefault:
    def test_read_file_allowed_by_default(self):
        g = PermissionGate(ask_fn=always_deny())
        d = g.ask(_req_read("/some/path/file.txt"))
        assert d.allow is True
        assert "safe by default" in d.reason

    def test_read_file_disabled(self):
        policy = PermissionPolicy(allow_read_file_anywhere=False)
        g = PermissionGate(policy=policy, ask_fn=always_deny())
        d = g.ask(_req_read("/some/path/file.txt"))
        assert d.allow is False


class TestSessionCache:
    def test_first_call_asks_then_caches(self):
        calls = {"n": 0}

        def ask(req):
            calls["n"] += 1
            return Decision.approve(reason="user approved", persist=False)

        g = PermissionGate(ask_fn=ask)
        d1 = g.ask(_req_cmd("unknown-cmd --flag"))
        d2 = g.ask(_req_cmd("unknown-cmd --flag"))
        assert d1.allow is True
        assert d2.allow is True
        assert calls["n"] == 1

    def test_session_cache_denies_persist(self):
        g = PermissionGate(
            ask_fn=lambda r: Decision.deny(reason="user denied")
        )
        d1 = g.ask(_req_cmd("unknown-cmd"))
        d2 = g.ask(_req_cmd("unknown-cmd"))
        assert d1.allow is False
        assert d2.allow is False
        assert "session" in d2.reason

    def test_reset_session_cache(self):
        calls = {"n": 0}

        def ask(req):
            calls["n"] += 1
            return Decision.approve()

        g = PermissionGate(ask_fn=ask)
        g.ask(_req_cmd("unknown-cmd"))
        g.reset_session_cache()
        g.ask(_req_cmd("unknown-cmd"))
        assert calls["n"] == 2


class TestPersistentAllow:
    def test_persist_true_written_to_disk(self, tmp_path):
        persist_path = tmp_path / "perms.json"
        g = PermissionGate(
            ask_fn=lambda r: Decision.approve(
                reason="user: always", persist=True
            ),
            persistent_allow_path=str(persist_path),
        )
        g.ask(_req_cmd("weird-cmd"))
        assert persist_path.exists()
        data = json.loads(persist_path.read_text(encoding="utf-8"))
        assert any("weird-cmd" in k for k in data.keys())

    def test_persistent_loaded_on_new_gate(self, tmp_path):
        persist_path = tmp_path / "perms.json"
        persist_path.write_text(
            json.dumps(
                {
                    f"{ACTION_RUN_COMMAND}::weird-cmd": {
                        "allow": True,
                        "reason": "prev",
                        "persist": True,
                    }
                }
            ),
            encoding="utf-8",
        )
        g = PermissionGate(
            ask_fn=always_deny(), persistent_allow_path=str(persist_path)
        )
        d = g.ask(_req_cmd("weird-cmd"))
        assert d.allow is True
        assert "persistent" in d.reason


class TestNoAskFn:
    def test_without_ask_fn_defaults_to_deny(self):
        g = PermissionGate()
        d = g.ask(_req_cmd("unknown"))
        assert d.allow is False
        assert "no ask_fn" in d.reason

    def test_set_ask_fn_later(self):
        g = PermissionGate()
        g.set_ask_fn(always_allow())
        d = g.ask(_req_cmd("unknown"))
        assert d.allow is True


class TestHistory:
    def test_history_records_both_request_and_decision(self):
        g = PermissionGate(ask_fn=always_allow())
        g.ask(_req_cmd("git status"))
        g.ask(_req_cmd("unknown-thing"))
        assert len(g.history) == 2
        entry = g.history[0]
        assert entry["request"]["action"] == ACTION_RUN_COMMAND
        assert "allow" in entry["decision"]


class TestDecisionBuilders:
    def test_approve_builder(self):
        d = Decision.approve(reason="ok", persist=True)
        assert d.allow is True and d.persist is True

    def test_deny_builder(self):
        d = Decision.deny(reason="no")
        assert d.allow is False and d.persist is False
