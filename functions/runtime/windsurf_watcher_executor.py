"""Windsurf Watcher Executor — міст між WindsurfWatcher та GUI.

Phase 12.5 (W1): GUI кнопка Start/Stop Windsurf Watch.

Аналогічно до PlanExecutor, але для WindsurfWatcher:
- start_windsurf_watch() — запускає WindsurfWatcherRunner
- stop_windsurf_watch() — зупиняє WindsurfWatcherRunner
- Live progress через GUI callback
- Summary для GUI
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("windsurf_watcher_executor")


@dataclass
class WindsurfWatchConfig:
    """Конфігурація Windsurf Watch."""
    idle_seconds: float = 2.0  # скільки секунд чекати тиші перед вважати відповідь завершеною
    poll_interval: float = 0.5  # як часто опитувати
    max_duration_seconds: float = 3600.0  # максимум 1 година
    max_responses: Optional[int] = 100  # максимум 100 відповідей
    keep_last_responses: int = 64  # скільки останніх відповідей зберігати
    window_lost_max: int = 5  # скільки разів підряд втрачати вікно перед зупинкою
    notify_on_response: bool = True  # показувати notify при новій відповіді
    heartbeat_interval: float = 60.0  # heartbeat кожну хвилину
    response_filter: Optional[Callable[[str], bool]] = None  # фільтр відповідей
    auto_scroll: bool = False  # автоматично скролити вниз якщо текст на межі видимого регіону
    auto_scroll_lines: int = 50  # скільки рядків тексту вважати "межею" для скролінгу


@dataclass
class WindsurfWatchState:
    """Стан Windsurf Watch (для GUI)."""
    is_running: bool = False
    started_at: float = 0.0
    responses_captured: int = 0
    snapshots_taken: int = 0
    window_lost_count: int = 0
    stop_reason: str = ""
    stop_requested: bool = False
    last_response: Optional[Dict[str, Any]] = None


# Тип callback для GUI повідомлень
GUICallback = Callable[[str, Any], None]


class WindsurfWatcherExecutor:
    """Executor для WindsurfWatcher з GUI інтеграцією."""

    def __init__(
        self,
        config: Optional[WindsurfWatchConfig] = None,
        gui_callback: Optional[GUICallback] = None,
    ):
        self.config = config or WindsurfWatchConfig()
        self.state = WindsurfWatchState()
        self.gui_callback = gui_callback
        self._runner: Optional[Any] = None
        self._stop_flag = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Запустити Windsurf Watch."""
        if self.state.is_running:
            logger.warning("Windsurf Watch вже запущено")
            return False

        try:
            from runtime.core_windsurf_watcher import (
                WindsurfWatcherConfig,
                WindsurfWatcherRunner,
                make_default_snapshot_fn,
                make_default_window_finder,
            )

            # Конвертуємо конфіг
            watcher_config = WindsurfWatcherConfig(
                name="windsurf_gui",
                idle_seconds=self.config.idle_seconds,
                poll_interval=self.config.poll_interval,
                max_duration_seconds=self.config.max_duration_seconds,
                max_responses=self.config.max_responses,
                keep_last_responses=self.config.keep_last_responses,
                window_lost_max=self.config.window_lost_max,
                notify_on_response=self.config.notify_on_response,
                log_dir="logs/windsurf_watch",
                heartbeat_interval=self.config.heartbeat_interval,
                response_filter=self.config.response_filter,
                auto_scroll=self.config.auto_scroll,
                auto_scroll_lines=self.config.auto_scroll_lines,
            )

            # Callback для нових відповідей
            def on_response(entry: Dict[str, Any]):
                self.state.last_response = entry
                self.state.responses_captured += 1
                if self.gui_callback:
                    self.gui_callback("windsurf_response", entry)

            # Створюємо runner
            self._runner = WindsurfWatcherRunner(
                config=watcher_config,
                window_finder=make_default_window_finder(),
                snapshot_fn=make_default_snapshot_fn(),
                on_response=on_response,
            )

            # Запускаємо в окремому треді
            self._stop_flag = False
            self.state.is_running = True
            self.state.started_at = time.time()
            self.state.stop_reason = ""

            self._runner.start()

            # Моніторинг тред для оновлення стану
            self._thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
            )
            self._thread.start()

            if self.gui_callback:
                self.gui_callback("windsurf_started", {"config": self.config})

            logger.info("Windsurf Watch запущено")
            return True

        except Exception as e:
            logger.error(f"Помилка запуску Windsurf Watch: {e}")
            self.state.is_running = False
            if self.gui_callback:
                self.gui_callback("windsurf_error", {"error": str(e)})
            return False

    def stop(self, reason: str = "manual") -> bool:
        """Зупинити Windsurf Watch."""
        if not self.state.is_running:
            logger.warning("Windsurf Watch не запущено")
            return False

        try:
            self.state.stop_requested = True
            self.state.stop_reason = reason

            if self._runner:
                self._runner.stop(reason=reason)

            self.state.is_running = False

            if self.gui_callback:
                self.gui_callback("windsurf_stopped", {"reason": reason, "state": self.state})

            logger.info(f"Windsurf Watch зупинено: {reason}")
            return True

        except Exception as e:
            logger.error(f"Помилка зупинки Windsurf Watch: {e}")
            if self.gui_callback:
                self.gui_callback("windsurf_error", {"error": str(e)})
            return False

    def get_state(self) -> Dict[str, Any]:
        """Отримати поточний стан."""
        if self._runner:
            summary = self._runner.summary()
            self.state.responses_captured = summary.get("responses_captured", 0)
            self.state.snapshots_taken = summary.get("snapshots_taken", 0)
            self.state.window_lost_count = summary.get("window_lost", 0)
            self.state.stop_reason = summary.get("stop_reason", "")

        return {
            "is_running": self.state.is_running,
            "started_at": self.state.started_at,
            "responses_captured": self.state.responses_captured,
            "snapshots_taken": self.state.snapshots_taken,
            "window_lost_count": self.state.window_lost_count,
            "stop_reason": self.state.stop_reason,
            "stop_requested": self.state.stop_requested,
            "last_response": self.state.last_response,
        }

    def _monitor_loop(self):
        """Моніторинг тред для оновлення стану."""
        while self.state.is_running and not self._stop_flag:
            time.sleep(1.0)

            if self._runner and self._runner.watcher:
                runner_state = self._runner.watcher.state
                if not runner_state.running:
                    # Watcher зупинився автоматично
                    self.state.is_running = False
                    self.state.stop_reason = runner_state.stop_reason or "auto"
                    if self.gui_callback:
                        self.gui_callback(
                            "windsurf_stopped",
                            {"reason": self.state.stop_reason, "state": self.state},
                        )
                    break
