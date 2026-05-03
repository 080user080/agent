"""Вкладка статистики."""
import random
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QGroupBox,
)

from .base_tab import BaseTab


class StatisticsTab(BaseTab):
    """Вкладка статистики."""

    def __init__(self, parent=None):
        self.total_requests_label = None
        self.tokens_label = None
        self.avg_time_label = None
        self.success_label = None
        self.failed_label = None
        self.avg_steps_label = None
        self.quota_progress = None
        self.refresh_button = None
        super().__init__(parent)

    def _build_content(self, layout):
        """Побудувати контент вкладки статистики."""
        # Група: Використання LLM
        llm_group = self.create_group("Використання LLM", layout)
        llm_layout = QVBoxLayout()

        llm_layout.addWidget(QLabel("Загальна кількість запитів:"))
        self.total_requests_label = QLabel("0")
        self.total_requests_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        llm_layout.addWidget(self.total_requests_label)

        llm_layout.addWidget(QLabel("Використано токенів:"))
        self.tokens_label = QLabel("0")
        self.tokens_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        llm_layout.addWidget(self.tokens_label)

        llm_layout.addWidget(QLabel("Середній час відповіді:"))
        self.avg_time_label = QLabel("0.0 с")
        self.avg_time_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        llm_layout.addWidget(self.avg_time_label)

        llm_group.setLayout(llm_layout)

        # Група: Виконання задач
        tasks_group = self.create_group("Виконання задач", layout)
        tasks_layout = QVBoxLayout()

        tasks_layout.addWidget(QLabel("Успішних задач:"))
        self.success_label = QLabel("0")
        self.success_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #107c10;")
        tasks_layout.addWidget(self.success_label)

        tasks_layout.addWidget(QLabel("Невдалих задач:"))
        self.failed_label = QLabel("0")
        self.failed_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #c53030;")
        tasks_layout.addWidget(self.failed_label)

        tasks_layout.addWidget(QLabel("Середня кількість кроків:"))
        self.avg_steps_label = QLabel("0.0")
        self.avg_steps_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        tasks_layout.addWidget(self.avg_steps_label)

        tasks_group.setLayout(tasks_layout)

        # Прогрес бар
        layout.addWidget(QLabel("Використання квоти:"))
        self.quota_progress = QProgressBar()
        self.quota_progress.setValue(45)
        self.quota_progress.setFormat("%p%")
        layout.addWidget(self.quota_progress)

        # Кнопка оновлення
        self.refresh_button = QPushButton("Оновити статистику")
        self.refresh_button.clicked.connect(self.refresh_statistics)
        layout.addWidget(self.refresh_button)

        # Додати тестові дані
        self.refresh_statistics()

    def refresh_statistics(self):
        """Оновити статистику випадковими даними."""
        self.total_requests_label.setText(str(random.randint(100, 1000)))
        self.tokens_label.setText(str(random.randint(10000, 100000)))
        self.avg_time_label.setText(f"{random.uniform(0.5, 5.0):.1f} с")
        self.success_label.setText(str(random.randint(50, 200)))
        self.failed_label.setText(str(random.randint(5, 20)))
        self.avg_steps_label.setText(f"{random.uniform(2.0, 10.0):.1f}")
        self.quota_progress.setValue(random.randint(10, 90))
