"""AgentObserver — фаза спостереження (обгортка над observe).

Винесено з AgentLoop.observe() для модульності (Phase 7.1).
Зберігає зворотню сумісність: AgentLoop делегує спостереження цьому класу.
"""
from __future__ import annotations

import logging
from typing import Optional

from functions.agent.observe import ObserveConfig, Observation, observe as _observe

logger = logging.getLogger("agent_observer")


class AgentObserver:
    """Фаза спостереження для AgentLoop.

    Обгортає ``functions.agent.observe.observe()`` та зберігає
    конфігурацію каналів збору даних (OCR, Vision, UIA, UI Elements).

    Args:
        assistant: Об'єкт VoiceAssistant (для Vision-LM провайдера).
        config: Конфігурація каналів спостереження.
    """

    def __init__(
        self,
        assistant,
        config: Optional[ObserveConfig] = None,
    ):
        self.assistant = assistant
        self.config = config or ObserveConfig(
            enable_ocr=True,
            enable_uia=False,
            enable_vision=False,
            enable_ui_elements=True,
            skip_observe_for_simple=False,
        )

    def observe(self, task: str) -> Observation:
        """Виконати спостереження системи для поточної задачі.

        Args:
            task: Текст поточної задачі (для skip_observe_for_simple).

        Returns:
            Observation зі зібраними даними (скріншот, OCR, UI тощо).
        """
        try:
            return _observe(
                config=self.config,
                assistant=self.assistant,
                task=task,
            )
        except Exception as e:
            logger.error("AgentObserver.observe() failed: %s", e)
            # Повернути мінімальне спостереження замість crash
            return Observation(
                metadata={"error": str(e), "fallback": True},
            )


__all__ = ["AgentObserver"]