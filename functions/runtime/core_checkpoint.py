"""Checkpoint/Resume infrastructure (Phase 12.4).

Дозволяє агенту зберігати стан виконання і відновлюватись після краш-а або зупинки.
Це основа для довгих сесій 3-6 год (S5).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("checkpoint")


@dataclass
class CheckpointData:
    """Дані чекпоїнту."""
    task_id: str
    task_description: str
    current_step: int
    total_steps: int
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Конвертувати в dict для JSON."""
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "state": self.state,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointData":
        """Створити з dict."""
        return cls(
            task_id=data["task_id"],
            task_description=data["task_description"],
            current_step=data["current_step"],
            total_steps=data["total_steps"],
            state=data.get("state", {}),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", 0.0),
        )


class CheckpointManager:
    """Менеджер чекпоїнтів для збереження/відновлення стану."""

    def __init__(self, checkpoint_dir: Optional[Path] = None):
        self.checkpoint_dir = checkpoint_dir or Path("logs/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, task_id: str) -> Path:
        """Отримати шлях до файлу чекпоїнту."""
        return self.checkpoint_dir / f"{task_id}.json"

    def save(self, checkpoint: CheckpointData) -> bool:
        """Зберегти чекпоїнт."""
        try:
            path = self._get_checkpoint_path(checkpoint.task_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Checkpoint saved: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    def load(self, task_id: str) -> Optional[CheckpointData]:
        """Завантажити чекпоїнт."""
        try:
            path = self._get_checkpoint_path(task_id)
            if not path.exists():
                return None

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            checkpoint = CheckpointData.from_dict(data)
            logger.info(f"Checkpoint loaded: {path}")
            return checkpoint
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def delete(self, task_id: str) -> bool:
        """Видалити чекпоїнт."""
        try:
            path = self._get_checkpoint_path(task_id)
            if path.exists():
                path.unlink()
                logger.info(f"Checkpoint deleted: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
            return False

    def list_checkpoints(self) -> list[str]:
        """Список ідентифікаторів чекпоїнтів."""
        try:
            return [f.stem for f in self.checkpoint_dir.glob("*.json")]
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            return []

    def cleanup_old_checkpoints(self, max_age_hours: float = 24.0) -> int:
        """Видалити старі чекпоїнти."""
        try:
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            deleted = 0

            for path in self.checkpoint_dir.glob("*.json"):
                if now - path.stat().st_mtime > max_age_seconds:
                    path.unlink()
                    deleted += 1

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old checkpoints")
            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup old checkpoints: {e}")
            return 0


# ─── Singleton instance ────────────────────────────────────────────────────────

_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager(checkpoint_dir: Optional[Path] = None) -> CheckpointManager:
    """Отримати singleton CheckpointManager."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager(checkpoint_dir)
    return _checkpoint_manager
