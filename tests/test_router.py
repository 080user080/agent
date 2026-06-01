"""Тести для RequestRouter."""
import pytest

from functions.llm.router import RequestRouter, RoutingDecision, TaskType


class TestRequestRouter:
    """Тести класифікації запитів."""

    def test_classify_code(self):
        """Класифікація код-задач."""
        router = RequestRouter()
        assert router.classify("напиши функцію для сортування") == TaskType.CODE
        assert router.classify("створи файл main.py") == TaskType.CODE
        assert router.classify("реалізуй клас User") == TaskType.CODE
        assert router.classify("def hello_world():") == TaskType.CODE
        assert router.classify("напиши скрипт") == TaskType.CODE

    def test_classify_debug(self):
        """Класифікація debug-задач."""
        router = RequestRouter()
        assert router.classify("помилка в коді") == TaskType.DEBUG
        assert router.classify("виправ цей баг") == TaskType.DEBUG
        assert router.classify("traceback: division by zero") == TaskType.DEBUG
        assert router.classify("програма не запускається") == TaskType.DEBUG

    def test_classify_gui(self):
        """Класифікація GUI-задач."""
        router = RequestRouter()
        assert router.classify("клікни на кнопку") == TaskType.GUI
        assert router.classify("відкрий програму блокнот") == TaskType.GUI
        assert router.classify("зроби скріншот") == TaskType.GUI
        assert router.classify("закрий вікно Chrome") == TaskType.GUI

    def test_classify_web(self):
        """Класифікація web-задач."""
        router = RequestRouter()
        assert router.classify("відкрий сайт google.com") == TaskType.WEB
        assert router.classify("перейди на сторінку") == TaskType.WEB
        assert router.classify("браузер відкрий сайт") == TaskType.WEB

    def test_classify_quick(self):
        """Класифікація quick-задач (без LLM)."""
        router = RequestRouter()
        assert router.classify("привіт") == TaskType.QUICK
        assert router.classify("дякую") == TaskType.QUICK
        assert router.classify("скільки часу") == TaskType.QUICK
        assert router.classify("що таке Python") == TaskType.QUICK

    def test_classify_general(self):
        """Класифікація загальних задач."""
        router = RequestRouter()
        assert router.classify("поясни як працює це") == TaskType.GENERAL
        assert router.classify("розкажи про історію") == TaskType.GENERAL
        assert router.classify("як мені краще вивчити програмування") == TaskType.GENERAL

    def test_route_with_available_providers(self):
        """Маршрутизація з доступними провайдерами."""
        router = RequestRouter()
        providers = {
            "orchestrator": None,
            "code_generator": None,
            "debugger": None,
        }

        decision = router.route("напиши код", providers)
        assert decision.task_type == TaskType.CODE
        assert decision.primary_provider_id == "code_generator"
        assert decision.fallback_chain == ["orchestrator", "debugger"]
        assert decision.requires_tools is True
        assert decision.context_budget == 4000

    def test_route_with_partial_providers(self):
        """Маршрутизація з частково доступними провайдерами."""
        router = RequestRouter()
        providers = {
            "orchestrator": None,
            "debugger": None,
        }

        decision = router.route("напиши код", providers)
        assert decision.primary_provider_id == "orchestrator"
        assert decision.fallback_chain == ["debugger"]

    def test_route_with_no_providers(self):
        """Маршрутизація без доступних провайдерів."""
        router = RequestRouter()
        providers = {}

        decision = router.route("напиши код", providers)
        assert decision.primary_provider_id == "orchestrator"
        assert decision.fallback_chain == []

    def test_route_quick_task(self):
        """Маршрутизація quick-задач (skip_llm=True)."""
        router = RequestRouter()
        providers = {"orchestrator": None}

        decision = router.route("привіт", providers)
        assert decision.task_type == TaskType.QUICK
        assert decision.skip_llm is True
        assert decision.context_budget == 500

    def test_route_debug_task(self):
        """Маршрутизація debug-задач (більший context_budget)."""
        router = RequestRouter()
        providers = {
            "orchestrator": None,
            "debugger": None,
        }

        decision = router.route("помилка в коді", providers)
        assert decision.task_type == TaskType.DEBUG
        assert decision.primary_provider_id == "debugger"
        assert decision.context_budget == 6000

    def test_route_gui_task(self):
        """Маршрутизація GUI-задач (requires_tools=True)."""
        router = RequestRouter()
        providers = {"orchestrator": None}

        decision = router.route("клікни на кнопку", providers)
        assert decision.task_type == TaskType.GUI
        assert decision.requires_tools is True
        assert decision.context_budget == 2000
