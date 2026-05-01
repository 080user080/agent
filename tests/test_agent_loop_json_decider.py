"""Тест AgentLoop + ActionDecider з JSON parsing fallback (без tool-calling)."""
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

sys.path.insert(0, r"d:\Python\agent")

from functions.agent_loop import (
    ActionDecider,
    AgentAction,
    AgentLoop,
    AgentLoopConfig,
    AgentState,
    Observation,
)


@dataclass
class FakeResponse:
    """Фейкова LLM-відповідь з content замість tool_calls."""
    content: str = ""
    error: Optional[str] = None
    tool_calls: Optional[List[Any]] = None


def fake_ask_llm_json(content_json: dict) -> FakeResponse:
    """Повернути LLM-відповідь з JSON у content."""
    return FakeResponse(content=json.dumps(content_json, ensure_ascii=False))


def fake_ask_llm_markdown(content_json: dict) -> FakeResponse:
    """Повернути LLM-відповідь з JSON у markdown code block."""
    json_str = json.dumps(content_json, ensure_ascii=False)
    return FakeResponse(content=f"```json\n{json_str}\n```")


def fake_ask_llm_plain(text: str) -> FakeResponse:
    """Повернути LLM-відповідь з plain text (done fallback)."""
    return FakeResponse(content=text)


class TestActionDeciderJsonParsing:
    """Тест парсингу JSON з content."""

    def setup_method(self):
        self.decider = ActionDecider(
            ask_llm_with_tools_fn=None,
            tools_schema=[],
            tool_aliases={},
        )

    def _call_decide(self, response: FakeResponse) -> AgentAction:
        """Хелпер: викликати decide з фейковою LLM-функцією."""
        def fake_llm(**kwargs):
            return response
        self.decider._ask_llm_with_tools = fake_llm
        return self.decider.decide(
            goal="test",
            observation=None,
            history=[],
        )

    def test_plain_json(self):
        """JSON прямо в content."""
        action = self._call_decide(fake_ask_llm_json({
            "action": "list_directory",
            "args": {"directory": "d:\\Python\\agent"},
            "reasoning": "переглянути файли",
        }))
        assert action.name == "list_directory"
        assert action.arguments == {"directory": "d:\\Python\\agent"}
        assert "переглянути файли" in action.reasoning

    def test_markdown_json(self):
        """JSON у markdown code block."""
        action = self._call_decide(fake_ask_llm_markdown({
            "action": "done",
            "args": {"summary": "Готово"},
            "reasoning": "завершення",
        }))
        assert action.name == "done"
        assert action.arguments == {"summary": "Готово"}

    def test_plain_text_fallback(self):
        """Plain text без JSON → done."""
        action = self._call_decide(fake_ask_llm_plain("Задача виконана"))
        assert action.name == "done"
        assert action.arguments.get("summary") == "Задача виконана"

    def test_empty_response(self):
        """Порожня відповідь → done з дефолтним summary."""
        action = self._call_decide(FakeResponse(content=""))
        assert action.name == "done"
        assert "Задачу завершено" in action.arguments.get("summary", "")

    def test_invalid_json(self):
        """Невалідний JSON → done fallback."""
        action = self._call_decide(FakeResponse(content='{"broken json'))
        assert action.name == "done"

    def test_ask_user(self):
        """ask_user action."""
        action = self._call_decide(fake_ask_llm_json({
            "action": "ask_user",
            "args": {"question": "Продовжити?"},
            "reasoning": "потрібне підтвердження",
        }))
        assert action.name == "ask_user"
        assert action.arguments == {"question": "Продовжити?"}


class TestAgentLoopJsonDecider:
    """Тест AgentLoop з JSON Decider (інтеграційний)."""

    def setup_method(self):
        self.config = AgentLoopConfig(
            max_steps=10,
            max_duration_seconds=30.0,
            enable_ocr=False,
            enable_ui_elements=False,
            enable_llm_decider=True,
        )
        self.loop = AgentLoop(config=self.config)
        self.loop.registry = _FakeRegistry()

    def test_json_decider_integration(self):
        """AgentLoop виконує кроки з JSON decider."""
        steps = [
            {"action": "list_directory", "args": {}, "reasoning": "крок 1"},
            {"action": "done", "args": {"summary": "Готово"}, "reasoning": "кінець"},
        ]
        step_iter = iter(steps)

        def fake_llm(**kwargs):
            try:
                step = next(step_iter)
                return FakeResponse(content=json.dumps(step, ensure_ascii=False))
            except StopIteration:
                return FakeResponse(content=json.dumps(
                    {"action": "done", "args": {"summary": "Готово"}}, ensure_ascii=False
                ))

        decider = ActionDecider(
            ask_llm_with_tools_fn=fake_llm,
            tools_schema=[],
            tool_aliases={"list_directory": "list_directory"},
        )
        self.loop.decider = decider

        result = self.loop.run("test task")

        assert result["ok"] is True
        assert result["steps"] >= 1
        assert "Готово" in result.get("summary", "")


class _FakeRegistry:
    """Фейковий registry для тестів."""

    def execute_function(self, name: str, args: dict) -> dict:
        if name == "list_directory":
            return {"ok": True, "result": ["file1.py", "file2.py"]}
        if name == "noop":
            return {"ok": True, "result": "noop"}
        return {"ok": True, "result": f"executed {name}"}


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
