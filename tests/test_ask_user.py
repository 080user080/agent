"""Тести для ask_user функціональності — Phase V6."""
import pytest
from unittest.mock import Mock, MagicMock

from functions.logic_task_runner import _handler_ask_user, TaskContext, Task, TaskRunner, ExecutionReport
from functions.agent_loop import AgentLoop, AgentState, Observation


class TestAskUserHandler:
    """Тести для _handler_ask_user."""

    def test_ask_user_with_callback(self):
        """ask_user з callback."""
        callback = Mock(return_value="так")
        runner = TaskRunner(ask_user_callback=callback)

        task = Task(
            id="test-1",
            kind="ask_user",
            params={"question": "Продовжити?", "options": ["так", "ні"]},
        )
        ctx = TaskContext(
            task=task,
            runner=runner,
            report=ExecutionReport(plan_name="test"),
            gate=Mock(),
            previous_results={},
        )

        result = _handler_ask_user(ctx)

        assert result["ok"] == True
        assert result["answer"] == "так"
        callback.assert_called_once_with("Продовжити?", ["так", "ні"])

    def test_ask_user_without_callback(self):
        """ask_user без callback."""
        runner = TaskRunner(ask_user_callback=None)

        task = Task(
            id="test-1",
            kind="ask_user",
            params={"question": "Питання"},
        )
        ctx = TaskContext(
            task=task,
            runner=runner,
            report=ExecutionReport(plan_name="test"),
            gate=Mock(),
            previous_results={},
        )

        result = _handler_ask_user(ctx)

        assert result["ok"] == False
        assert "not set" in result["error"]

    def test_ask_user_callback_error(self):
        """ask_user з помилкою в callback."""
        callback = Mock(side_effect=Exception("Test error"))
        runner = TaskRunner(ask_user_callback=callback)

        task = Task(
            id="test-1",
            kind="ask_user",
            params={"question": "Питання"},
        )
        ctx = TaskContext(
            task=task,
            runner=runner,
            report=ExecutionReport(plan_name="test"),
            gate=Mock(),
            previous_results={},
        )

        result = _handler_ask_user(ctx)

        assert result["ok"] == False
        assert "Test error" in result["error"]


class TestAgentLoopAskUser:
    """Тести для ask_user в AgentLoop."""

    def test_agent_loop_init_with_callback(self):
        """AgentLoop з ask_user callback."""
        callback = Mock()
        assistant = Mock()
        loop = AgentLoop(assistant, ask_user_callback=callback)

        assert loop.ask_user_callback == callback

    def test_handle_ask_user_step_with_callback(self):
        """_handle_ask_user_step з callback."""
        callback = Mock(return_value="варіант 1")
        assistant = Mock()
        loop = AgentLoop(assistant, ask_user_callback=callback)

        step = {
            "action": "click",
            "args": {"x": 100, "y": 200},
            "ask_user": {
                "question": "Яку кнопку натиснути?",
                "options": ["варіант 1", "варіант 2"],
            }
        }
        state = AgentState(step=0)

        result = loop._handle_ask_user_step(step, state, total_steps=5, from_compiled=False)

        assert result["action"] == "click"
        assert result["args"]["user_answer"] == "варіант 1"
        assert result["step_index"] == 0
        assert result["total_steps"] == 5
        callback.assert_called_once_with("Яку кнопку натиснути?", ["варіант 1", "варіант 2"])

    def test_handle_ask_user_step_without_callback(self):
        """_handle_ask_user_step без callback."""
        assistant = Mock()
        loop = AgentLoop(assistant, ask_user_callback=None)

        step = {
            "action": "click",
            "args": {"x": 100, "y": 200},
            "ask_user": {"question": "Питання"}
        }
        state = AgentState(step=0)

        result = loop._handle_ask_user_step(step, state, total_steps=5, from_compiled=False)

        assert result["action"] == "click"
        assert result["error"] == "ask_user_callback not set"

    def test_handle_ask_user_step_with_error(self):
        """_handle_ask_user_step з помилкою в callback."""
        callback = Mock(side_effect=Exception("Error"))
        assistant = Mock()
        loop = AgentLoop(assistant, ask_user_callback=callback)

        step = {
            "action": "click",
            "args": {},
            "ask_user": {"question": "Питання"}
        }
        state = AgentState(step=0)

        result = loop._handle_ask_user_step(step, state, total_steps=5, from_compiled=False)

        assert result["action"] == "noop"
        assert result["error"] == "Error"

    def test_plan_with_ask_user_compiled_plan(self):
        """plan() з ask_user в CompiledPlan."""
        callback = Mock(return_value="так")
        assistant = Mock()
        loop = AgentLoop(assistant, ask_user_callback=callback)

        # Створюємо CompiledPlan з ask_user кроком
        from functions.task_spec import CompiledPlan, TaskSpec, Domain, Priority
        task_spec = TaskSpec(
            description="тест",
            domain=Domain.CODE,
            priority=Priority.MEDIUM
        )
        compiled_plan = CompiledPlan(
            task_spec=task_spec,
            steps=[
                {
                    "action": "click",
                    "args": {"x": 100},
                    "ask_user": {"question": "Продовжити?", "options": ["так", "ні"]}
                },
                {"action": "type", "args": {"text": "hello"}}
            ]
        )
        loop.set_compiled_plan(compiled_plan)

        obs = Observation()
        state = AgentState(step=0)

        result = loop.plan("тест", obs, state)

        assert result["action"] == "click"
        assert result["user_answer"] == "так"
        assert result["from_compiled_plan"] == True
