"""
Тести для модуля logic_scenario_runner.py

GUI Automation Phase 5 — Сценарії виконання.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestScenario:
    """Тести для класу Scenario."""

    def test_init(self):
        """Тест ініціалізації Scenario."""
        from functions.logic_scenario_runner import Scenario

        scenario = Scenario("test_scenario")
        assert scenario is not None
        assert scenario.name == "test_scenario"

    def test_add_step(self):
        """Тест додавання кроку."""
        from functions.logic_scenario_runner import Scenario

        scenario = Scenario("test_scenario")
        scenario.add_step("click", {"x": 100, "y": 200})

        assert len(scenario.steps) == 1

    def test_add_multiple_steps(self):
        """Тест додавання кількох кроків."""
        from functions.logic_scenario_runner import Scenario

        scenario = Scenario("test_scenario")
        scenario.add_step("click", {"x": 100, "y": 200})
        scenario.add_step("type", {"text": "hello"})
        scenario.add_step("click", {"x": 300, "y": 400})

        assert len(scenario.steps) == 3

    def test_execute(self):
        """Тест виконання сценарію."""
        from functions.logic_scenario_runner import Scenario

        scenario = Scenario("test_scenario")
        scenario.add_step("click", {"x": 100, "y": 200})

        with patch('functions.logic_scenario_runner.mouse_click'):
            result = scenario.execute()
            assert result is not None


class TestScenarioRunner:
    """Тести для класу ScenarioRunner."""

    def test_init(self):
        """Тест ініціалізації ScenarioRunner."""
        from functions.logic_scenario_runner import ScenarioRunner

        runner = ScenarioRunner()
        assert runner is not None

    def test_register_scenario(self):
        """Тест реєстрації сценарію."""
        from functions.logic_scenario_runner import ScenarioRunner, Scenario

        runner = ScenarioRunner()
        scenario = Scenario("test_scenario")
        scenario.add_step("click", {"x": 100, "y": 200})

        runner.register_scenario(scenario)
        assert "test_scenario" in runner.scenarios

    def test_run_scenario(self):
        """Тест виконання сценарію."""
        from functions.logic_scenario_runner import ScenarioRunner, Scenario

        runner = ScenarioRunner()
        scenario = Scenario("test_scenario")
        scenario.add_step("click", {"x": 100, "y": 200})
        runner.register_scenario(scenario)

        with patch('functions.logic_scenario_runner.mouse_click'):
            result = runner.run_scenario("test_scenario")
            assert result is not None

    def test_list_scenarios(self):
        """Тест списку сценаріїв."""
        from functions.logic_scenario_runner import ScenarioRunner, Scenario

        runner = ScenarioRunner()
        scenario1 = Scenario("scenario1")
        scenario2 = Scenario("scenario2")
        runner.register_scenario(scenario1)
        runner.register_scenario(scenario2)

        result = runner.list_scenarios()
        assert len(result) == 2


class TestScenarioStorage:
    """Тести для зберігання сценаріїв."""

    def test_save_scenario(self):
        """Тест збереження сценарію."""
        from functions.logic_scenario_runner import Scenario, ScenarioStorage

        scenario = Scenario("test_scenario")
        scenario.add_step("click", {"x": 100, "y": 200})

        storage = ScenarioStorage()
        with patch('functions.logic_scenario_runner.Path'):
            storage.save(scenario)

    def test_load_scenario(self):
        """Тест завантаження сценарію."""
        from functions.logic_scenario_runner import ScenarioStorage

        storage = ScenarioStorage()
        with patch('functions.logic_scenario_runner.Path'):
            result = storage.load("test_scenario")
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
