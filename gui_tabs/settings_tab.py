"""Вкладка налаштувань."""
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QScrollArea,
    QPushButton,
)

from .base_tab import BaseTab
from .constants import (
    LANGUAGES,
    THEMES,
    MODELS,
    SettingsDefaults,
)


class SettingsTab(BaseTab):
    """Вкладка налаштувань."""

    def __init__(self, parent=None):
        self._settings = QSettings("MARK", "Assistant")
        super().__init__(parent)

    def _build_content(self, layout):
        """Побудувати контент вкладки налаштувань."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Група: Загальні налаштування
        general_group = self.create_group("Загальні налаштування", content_layout)
        general_layout = QVBoxLayout()

        general_layout.addWidget(QLabel("Мова інтерфейсу:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems(LANGUAGES)
        general_layout.addWidget(self.language_combo)

        general_layout.addWidget(QLabel("Тема:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES)
        general_layout.addWidget(self.theme_combo)

        self.auto_save = QCheckBox("Автоматичне збереження")
        self.auto_save.setChecked(SettingsDefaults.auto_save)
        general_layout.addWidget(self.auto_save)

        general_group.setLayout(general_layout)

        # Група: LLM налаштування
        llm_group = self.create_group("LLM Налаштування", content_layout)
        llm_layout = QVBoxLayout()

        llm_layout.addWidget(QLabel("Модель:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODELS)
        llm_layout.addWidget(self.model_combo)

        llm_layout.addWidget(QLabel("Температура:"))
        self.temperature_spin = QSpinBox()
        self.temperature_spin.setRange(0, 100)
        self.temperature_spin.setValue(SettingsDefaults.temperature)
        self.temperature_spin.setSuffix(" (%)")
        llm_layout.addWidget(self.temperature_spin)

        llm_layout.addWidget(QLabel("Максимальних токенів:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 8000)
        self.max_tokens_spin.setValue(SettingsDefaults.max_tokens)
        llm_layout.addWidget(self.max_tokens_spin)

        self.stream_response = QCheckBox("Потокова відповідь")
        self.stream_response.setChecked(SettingsDefaults.stream_response)
        llm_layout.addWidget(self.stream_response)

        llm_group.setLayout(llm_layout)

        # Група: Агент налаштування
        agent_group = self.create_group("Agent Налаштування", content_layout)
        agent_layout = QVBoxLayout()

        agent_layout.addWidget(QLabel("Максимальних кроків:"))
        self.max_steps_spin = QSpinBox()
        self.max_steps_spin.setRange(1, 100)
        self.max_steps_spin.setValue(SettingsDefaults.max_steps)
        agent_layout.addWidget(self.max_steps_spin)

        agent_layout.addWidget(QLabel("Максимальний час (сек):"))
        self.max_time_spin = QSpinBox()
        self.max_time_spin.setRange(10, 600)
        self.max_time_spin.setValue(SettingsDefaults.max_time)
        agent_layout.addWidget(self.max_time_spin)

        self.enable_ocr = QCheckBox("Увімкнути OCR")
        self.enable_ocr.setChecked(SettingsDefaults.enable_ocr)
        agent_layout.addWidget(self.enable_ocr)

        self.enable_vision = QCheckBox("Увімкнути Vision")
        self.enable_vision.setChecked(SettingsDefaults.enable_vision)
        agent_layout.addWidget(self.enable_vision)

        agent_group.setLayout(agent_layout)

        # Кнопки
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Зберегти")
        self.save_button.clicked.connect(self.save_settings)
        self.reset_button = QPushButton("Скинути")
        self.reset_button.clicked.connect(self.reset_settings)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.reset_button)
        content_layout.addLayout(buttons_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def save_settings(self):
        """Зберегти налаштування."""
        s = self._settings
        s.setValue("language_index", self.language_combo.currentIndex())
        s.setValue("theme_index", self.theme_combo.currentIndex())
        s.setValue("auto_save", self.auto_save.isChecked())
        s.setValue("model_index", self.model_combo.currentIndex())
        s.setValue("temperature", self.temperature_spin.value())
        s.setValue("max_tokens", self.max_tokens_spin.value())
        s.setValue("stream_response", self.stream_response.isChecked())
        s.setValue("max_steps", self.max_steps_spin.value())
        s.setValue("max_time", self.max_time_spin.value())
        s.setValue("enable_ocr", self.enable_ocr.isChecked())
        s.setValue("enable_vision", self.enable_vision.isChecked())
        s.sync()
        print("Налаштування збережено!")

    def reset_settings(self):
        """Скинути налаштування до значень за замовчуванням."""
        self.language_combo.setCurrentIndex(SettingsDefaults.language_index)
        self.theme_combo.setCurrentIndex(SettingsDefaults.theme_index)
        self.auto_save.setChecked(SettingsDefaults.auto_save)
        self.model_combo.setCurrentIndex(SettingsDefaults.model_index)
        self.temperature_spin.setValue(SettingsDefaults.temperature)
        self.max_tokens_spin.setValue(SettingsDefaults.max_tokens)
        self.stream_response.setChecked(SettingsDefaults.stream_response)
        self.max_steps_spin.setValue(SettingsDefaults.max_steps)
        self.max_time_spin.setValue(SettingsDefaults.max_time)
        self.enable_ocr.setChecked(SettingsDefaults.enable_ocr)
        self.enable_vision.setChecked(SettingsDefaults.enable_vision)
