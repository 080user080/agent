"""
Тести для модуля logic_scenario_runner.py

GUI Automation Phase 5 — Сценарії виконання.
"""

import pytest
from unittest.mock import patch
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestScenario:
    """Тести для класу Scenario."""

    def test_init(self):
        """Тест ініціалізації Scenario."""
        from functions.gui.logic_scenario_runner import Scenario

        scenario = Scenario(name="test", description="desc", steps=[])
        assert scenario is not None
        assert scenario.name == "test"

    def test_add_step(self):
        """Тест структури сценарію."""
        from functions.gui.logic_scenario_runner import Scenario, ScenarioStep

        step = ScenarioStep("click", "desc", {"description": "test_button"})
        scenario = Scenario(name="test", description="desc", steps=[step])

        assert len(scenario.steps) == 1
        assert scenario.steps[0].step_type == "click"


class TestScenarioRunner:
    """Тести для класу ScenarioRunner."""

    def test_init(self):
        """Тест ініціалізації ScenarioRunner."""
        from functions.gui.logic_scenario_runner import ScenarioRunner

        runner = ScenarioRunner()
        assert runner is not None

    def test_run_scenario(self):
        """Тест виконання сценарію."""
        from functions.gui.logic_scenario_runner import ScenarioRunner, Scenario, ScenarioStep

        runner = ScenarioRunner()
        step = ScenarioStep("click", "desc", {"description": "test_button"})
        scenario = Scenario(name="test_scenario", description="desc", steps=[step])

        with patch('functions.gui.logic_scenario_runner.click_element') as mock_click:
            mock_click.return_value = {"success": True}
            result = runner.run_scenario(scenario)
            assert result.success is True

    def test_list_scenarios(self):
        """Тест списку сценаріїв."""
        from functions.gui.logic_scenario_runner import ScenarioRunner

        runner = ScenarioRunner()
        # Сценарії в runner тепер управляються через файлову систему
        scenarios = runner.list_scenarios()
        assert isinstance(scenarios, list)


class TestScenarioStorage:
    """Тести для зберігання сценаріїв."""

    def test_save_scenario(self):
        """Тест збереження сценарію."""
        from functions.gui.logic_scenario_runner import Scenario, ScenarioRunner, ScenarioStep

        step = ScenarioStep("click", "desc", {"x": 100, "y": 200})
        scenario = Scenario(name="test_scenario", description="description", steps=[step])

        runner = ScenarioRunner()
        with patch('functions.gui.logic_scenario_runner.Path'):
            runner.save_scenario(scenario)

    def test_load_scenario(self):
        """Тест завантаження сценарію."""
        from functions.gui.logic_scenario_runner import ScenarioRunner

        runner = ScenarioRunner()
        with patch('functions.gui.logic_scenario_runner.Path'):
            result = runner.load_scenario("test_scenario")
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
