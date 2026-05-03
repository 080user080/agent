"""Вкладка про програму."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QGroupBox,
)

from .base_tab import BaseTab
from .constants import (
    APP_NAME,
    APP_VERSION,
    APP_DESCRIPTION,
    FEATURES,
    TECHNOLOGIES,
    LINKS,
)


class AboutTab(BaseTab):
    """Вкладка про програму."""

    def _build_content(self, layout):
        """Побудувати контент вкладки про програму."""
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Заголовок
        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #0078d4;")
        layout.addWidget(title)

        # Версія
        version = QLabel(f"Версія: {APP_VERSION}")
        version.setStyleSheet("font-size: 16px; color: #6c757d;")
        layout.addWidget(version)

        # Опис
        description = QLabel(APP_DESCRIPTION)
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 14px; margin: 20px 0;")
        layout.addWidget(description)

        # Особливості
        features_group = self.create_group("Особливості", layout)
        features_layout = QVBoxLayout()
        for feature in FEATURES:
            features_layout.addWidget(QLabel(feature))
        features_group.setLayout(features_layout)

        # Технології
        tech_group = self.create_group("Технології", layout)
        tech_layout = QVBoxLayout()
        for tech in TECHNOLOGIES:
            tech_layout.addWidget(QLabel(tech))
        tech_group.setLayout(tech_layout)

        # Посилання
        links_group = self.create_group("Посилання", layout)
        links_layout = QVBoxLayout()
        for link in LINKS.values():
            links_layout.addWidget(QLabel(link))
        links_group.setLayout(links_layout)

        layout.addStretch()
