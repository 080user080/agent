"""AI Orchestrator — Phase 9.3.

Оркестратор керує делегуванням задач між AI-провайдерами через `ProviderRegistry`.
Функціонал:
- `decompose_task` — розбиття задачі на підзадачі (заглушка або через LLM).
- `delegate` — делегування задачі з fallback-ланцюгом.
- `delegate_parallel` — паралельна делегація на кілька провайдерів.
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from functions.llm.logic_ai_adapter import ChatRequest, ChatResponse
from functions.llm.logic_provider_registry import ProviderRegistry, SelectionCriteria


@dataclass
class SubTask:
    """Підзадача, що виникла при декомпозиції."""

    description: str
    index: int = 0
    assigned_provider: Optional[str] = None
    result: Optional[ChatResponse] = None
    error: str = ""


@dataclass
class OrchestrationResult:
    """Результат оркестрації."""

    original_task: str
    sub_tasks: List[SubTask] = field(default_factory=list)
    final_answer: str = ""
    all_ok: bool = False
    errors: List[str] = field(default_factory=list)


class Orchestrator:
    """Оркестратор для делегування задач AI-провайдерам."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    # -----------------------------------------------------------------------
    # Decomposition
    # -----------------------------------------------------------------------

    def decompose_task(self, task: str, llm_fallback: bool = False) -> List[str]:
        """Розбиває задачу на підзадачі.

        Args:
            task: Опис задачі.
            llm_fallback: Якщо True — спробувати делегувати LLM для декомпозиції.

        Returns:
            Список підзадач (як мінімум `[task]`).
        """
        if not llm_fallback:
            # Заглушка: проста декомпозиція за ключовими словами
            steps = [s.strip() for s in task.split("\n") if s.strip()]
            if len(steps) > 1:
                return steps
            return [task]

        # Спробувати делегувати LLM для декомпозиції
        try:
            prompt = (
                f"Розбий наступну задачу на підзадачі (кожна з нового рядка):\n{task}\n"
                "Відповідай тільки списком підзадач, без пояснень."
            )
            criteria = SelectionCriteria(chat=True, prefer_cheapest=True)
            response = self.registry.chat(prompt, criteria, max_retries=2)
            if response and response.content:
                lines = [l.strip("- ").strip() for l in response.content.split("\n") if l.strip()]
                return lines or [task]
        except Exception:  # noqa: BLE001
            pass
        return [task]

    # -----------------------------------------------------------------------
    # Delegation
    # -----------------------------------------------------------------------

    def delegate(
        self,
        task: str,
        criteria: Optional[SelectionCriteria] = None,
    ) -> ChatResponse:
        """Делегує задачу через fallback-ланцюг `ProviderRegistry.chat`.

        Args:
            task: Текст задачі або повідомлення.
            criteria: Критерії вибору провайдерів (якщо None — chat=True, cheapest).

        Returns:
            ChatResponse або кидає RuntimeError якщо всі провайдери впали.
        """
        criteria = criteria or SelectionCriteria(chat=True, prefer_cheapest=True)
        return self.registry.chat(task, criteria, max_retries=3)

    def delegate_parallel(
        self,
        task: str,
        criteria: Optional[SelectionCriteria] = None,
        max_providers: int = 3,
    ) -> OrchestrationResult:
        """Паралельна делегація задачі на кілька провайдерів.

        Args:
            task: Текст задачі.
            criteria: Критерії вибору провайдерів.
            max_providers: Максимальна кількість провайдерів для паралельного запиту.

        Returns:
            OrchestrationResult з відповідями кожного провайдера.
        """
        criteria = criteria or SelectionCriteria(chat=True, prefer_cheapest=True)
        providers = self.registry.select_many(criteria)
        chosen = providers[:max_providers]
        sub_tasks: List[SubTask] = []

        def _run_one(name: str) -> SubTask:
            st = SubTask(description=task, index=0, assigned_provider=name)
            try:
                provider = self.registry.get(name)
                if provider is None or not provider.available():
                    st.error = f"Provider '{name}' unavailable"
                    return st
                req = ChatRequest(model="", messages=[{"role": "user", "content": task}])  # type: ignore
                st.result = provider.chat(req)
            except Exception as exc:  # noqa: BLE001
                st.error = str(exc)
            return st

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_providers) as pool:
            futures = [pool.submit(_run_one, name) for name in chosen]
            for future in concurrent.futures.as_completed(futures):
                sub_tasks.append(future.result())

        # Вибрати найкращу відповідь (перша успішна)
        best = next((st for st in sub_tasks if st.result is not None and st.result.content), None)
        errors = [st.error for st in sub_tasks if st.error]
        return OrchestrationResult(
            original_task=task,
            sub_tasks=sub_tasks,
            final_answer=best.result.content if best else "",
            all_ok=best is not None,
            errors=errors,
        )

    # -----------------------------------------------------------------------
    # High-level orchestration
    # -----------------------------------------------------------------------

    def run(
        self,
        task: str,
        criteria: Optional[SelectionCriteria] = None,
        parallel: bool = False,
    ) -> OrchestrationResult:
        """Основний entry-point: декомпозиція + делегування.

        Args:
            task: Текст задачі.
            criteria: Критерії вибору провайдерів.
            parallel: Якщо True — використати `delegate_parallel`, інакше `delegate`.

        Returns:
            OrchestrationResult.
        """
        sub_task_descriptions = self.decompose_task(task)
        if len(sub_task_descriptions) == 1 and not parallel:
            try:
                response = self.delegate(sub_task_descriptions[0], criteria)
                return OrchestrationResult(
                    original_task=task,
                    sub_tasks=[SubTask(description=sub_task_descriptions[0], result=response)],
                    final_answer=response.content,
                    all_ok=True,
                )
            except Exception as exc:  # noqa: BLE001
                return OrchestrationResult(
                    original_task=task,
                    errors=[str(exc)],
                )

        # Декомпозиція + паралельна/послідовна делегація підзадач
        results: List[OrchestrationResult] = []
        for i, sub in enumerate(sub_task_descriptions):
            if parallel:
                res = self.delegate_parallel(sub, criteria)
            else:
                try:
                    resp = self.delegate(sub, criteria)
                    res = OrchestrationResult(
                        original_task=sub,
                        sub_tasks=[SubTask(description=sub, index=i, result=resp)],
                        final_answer=resp.content,
                        all_ok=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    res = OrchestrationResult(
                        original_task=sub,
                        errors=[str(exc)],
                    )
            results.append(res)

        combined = OrchestrationResult(
            original_task=task,
            all_ok=all(r.all_ok for r in results),
        )
        combined.sub_tasks = [st for r in results for st in r.sub_tasks]
        combined.errors = [e for r in results for e in r.errors]
        combined.final_answer = "\n".join(
            r.final_answer for r in results if r.final_answer
        )
        return combined