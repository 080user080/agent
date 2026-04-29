"""LLMEndpointsEditor для PyQt6 — редагування списку LLM-ендпоінтів.

Аналог core_gui/llm_endpoints_editor.py для Tkinter.
"""
from __future__ import annotations

from typing import Any, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
)


class LLMEndpointItem:
    """Один ендпоінт LLM (model, provider, api_key, etc.)."""

    def __init__(self, data: dict):
        self.id = data.get("id", "")
        self.name = data.get("name", "")
        self.enabled = data.get("enabled", True)
        self.role = data.get("role", "primary")  # Додано role для endpoint_client.py
        self.type = data.get("type", "openai_compatible")  # Додано type
        self.url = data.get("url", "")  # Замінено base_url на url для endpoint_client.py
        self.model = data.get("model", "")
        self.provider = data.get("provider", "openai")
        self.api_key = data.get("api_key", "")
        self.temperature = data.get("temperature", 0.1)  # Додано temperature
        self.max_tokens = data.get("max_tokens", 1024)  # Додано max_tokens
        self.timeout = data.get("timeout", 60)  # Додано timeout
        self.script_command = data.get("script_command", "")  # Додано script_command
        self.script_output_file = data.get("script_output_file", "")  # Додано script_output_file
        self.rate_limit_mode = data.get("rate_limit_mode", "unlimited")  # Додано rate_limit_mode
        self.rate_limit_rpm = data.get("rate_limit_rpm", 0)  # Додано rate_limit_rpm
        self.rate_limit_total = data.get("rate_limit_total", 0)  # Додано rate_limit_total
        known_keys = {
            "id",
            "name",
            "enabled",
            "role",
            "type",
            "url",
            "model",
            "provider",
            "api_key",
            "temperature",
            "max_tokens",
            "timeout",
            "script_command",
            "script_output_file",
            "rate_limit_mode",
            "rate_limit_rpm",
            "rate_limit_total",
        }
        self.extra = {key: value for key, value in data.items() if key not in known_keys}

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "role": self.role,  # Додано role для endpoint_client.py
            "type": self.type,  # Додано type
            "url": self.url,  # Замінено base_url на url для endpoint_client.py
            "model": self.model,
            "provider": self.provider,
            "api_key": self.api_key,
            "temperature": self.temperature,  # Додано temperature
            "max_tokens": self.max_tokens,  # Додано max_tokens
            "timeout": self.timeout,  # Додано timeout
            "script_command": self.script_command,  # Додано script_command
            "script_output_file": self.script_output_file,  # Додано script_output_file
            "rate_limit_mode": self.rate_limit_mode,  # Додано rate_limit_mode
            "rate_limit_rpm": self.rate_limit_rpm,  # Додано rate_limit_rpm
            "rate_limit_total": self.rate_limit_total,  # Додано rate_limit_total
        }
        result.update(self.extra)
        return result


class LLMEndpointDialog(QDialog):
    """Діалог для додавання/редагування одного ендпоінту."""

    def __init__(self, item: Optional[LLMEndpointItem] = None, parent=None, total_items=1):
        super().__init__(parent)
        self.item = item if item else LLMEndpointItem({})
        self.total_items = total_items
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("LLM Ендпоінт")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Name
        layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit(self.item.name)
        layout.addWidget(self.name_edit)

        # Порядок запуску (role)
        layout.addWidget(QLabel("Порядок запуску:"))
        self.role_combo = QComboBox()
        # Генеруємо список цифр від 1 до total_items
        self.role_combo.addItems([str(i) for i in range(1, self.total_items + 1)])
        # Якщо role вже число, використовуємо його, інакше дефолт 1
        try:
            current_role_num = int(self.item.role)
            if 1 <= current_role_num <= self.total_items:
                self.role_combo.setCurrentText(str(current_role_num))
            else:
                self.role_combo.setCurrentText("1")
        except (ValueError, TypeError):
            # Якщо role не число, пробуємо знайти в мапі для сумісності зі старими даними
            role_map = {"primary": "1", "secondary": "2", "fallback": "3", "alternative": "4"}
            if self.item.role in role_map and int(role_map[self.item.role]) <= self.total_items:
                self.role_combo.setCurrentText(role_map[self.item.role])
            else:
                self.role_combo.setCurrentText("1")
        layout.addWidget(self.role_combo)

        # Type
        layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["openai_compatible", "script"])
        self.type_combo.setCurrentText(self.item.type)
        layout.addWidget(self.type_combo)

        # URL
        layout.addWidget(QLabel("URL:"))
        self.url_edit = QLineEdit(self.item.url)
        layout.addWidget(self.url_edit)

        # Model
        layout.addWidget(QLabel("Model:"))
        self.model_edit = QLineEdit(self.item.model)
        layout.addWidget(self.model_edit)

        # Provider
        layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic", "groq", "local", "custom"])
        self.provider_combo.setCurrentText(self.item.provider)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        layout.addWidget(self.provider_combo)

        # API Key
        layout.addWidget(QLabel("API Key (optional):"))
        self.api_key_edit = QLineEdit(self.item.api_key)
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.api_key_edit)

        # Temperature
        layout.addWidget(QLabel("Temperature:"))
        self.temperature_edit = QLineEdit(str(self.item.temperature))
        layout.addWidget(self.temperature_edit)

        # Max Tokens
        layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_edit = QLineEdit(str(self.item.max_tokens))
        layout.addWidget(self.max_tokens_edit)

        # Timeout
        layout.addWidget(QLabel("Timeout (s):"))
        self.timeout_edit = QLineEdit(str(self.item.timeout))
        layout.addWidget(self.timeout_edit)

        # Script command
        layout.addWidget(QLabel("Script command:"))
        self.script_command_edit = QLineEdit(self.item.script_command)
        layout.addWidget(self.script_command_edit)

        # Script output file
        layout.addWidget(QLabel("Script output file:"))
        self.script_output_file_edit = QLineEdit(self.item.script_output_file)
        layout.addWidget(self.script_output_file_edit)

        # Rate limit mode
        layout.addWidget(QLabel("Rate limit mode:"))
        self.rate_limit_mode_combo = QComboBox()
        self.rate_limit_mode_combo.addItems(["unlimited", "rpm", "total"])
        self.rate_limit_mode_combo.setCurrentText(self.item.rate_limit_mode)
        layout.addWidget(self.rate_limit_mode_combo)

        # Rate limit RPM
        layout.addWidget(QLabel("Max RPM:"))
        self.rate_limit_rpm_edit = QLineEdit(str(self.item.rate_limit_rpm))
        layout.addWidget(self.rate_limit_rpm_edit)

        # Rate limit total
        layout.addWidget(QLabel("Max total:"))
        self.rate_limit_total_edit = QLineEdit(str(self.item.rate_limit_total))
        layout.addWidget(self.rate_limit_total_edit)

        # Enabled
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(self.item.enabled)
        layout.addWidget(self.enabled_check)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_provider_changed(self, provider: str) -> None:
        """Автозаповнення url залежно від provider."""
        DEFAULT_URLS = {
            "openai": "https://api.openai.com/v1/chat/completions",
            "anthropic": "https://api.anthropic.com/v1/messages",
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "local": "http://localhost:1234/v1/chat/completions",
            "custom": "",
        }
        if provider in DEFAULT_URLS and not self.url_edit.text().strip():
            self.url_edit.setText(DEFAULT_URLS[provider])

    def get_item(self) -> LLMEndpointItem:
        self.item.name = self.name_edit.text().strip()
        # Зберігаємо role як число
        self.item.role = self.role_combo.currentText()
        self.item.type = self.type_combo.currentText()
        self.item.url = self.url_edit.text().strip()
        self.item.model = self.model_edit.text().strip()
        self.item.provider = self.provider_combo.currentText()
        self.item.api_key = self.api_key_edit.text().strip()
        try:
            self.item.temperature = float(self.temperature_edit.text().strip())
        except ValueError:
            self.item.temperature = 0.1
        try:
            self.item.max_tokens = int(self.max_tokens_edit.text().strip())
        except ValueError:
            self.item.max_tokens = 1024
        try:
            self.item.timeout = int(self.timeout_edit.text().strip())
        except ValueError:
            self.item.timeout = 60
        self.item.script_command = self.script_command_edit.text().strip()
        self.item.script_output_file = self.script_output_file_edit.text().strip()
        self.item.rate_limit_mode = self.rate_limit_mode_combo.currentText()
        try:
            self.item.rate_limit_rpm = int(self.rate_limit_rpm_edit.text().strip())
        except ValueError:
            self.item.rate_limit_rpm = 0
        try:
            self.item.rate_limit_total = int(self.rate_limit_total_edit.text().strip())
        except ValueError:
            self.item.rate_limit_total = 0
        self.item.enabled = self.enabled_check.isChecked()
        return self.item


class LLMEndpointsEditor(QFrame):
    """Редактор списку LLM-ендпоінтів для PyQt6.

    API:
        - get() -> List[dict] — поточний список ендпоінтів
        - set(List[dict]) — встановити список
        - changed — сигнал при зміні
    """

    changed = pyqtSignal()

    def __init__(self, value: List[dict] | None = None, parent=None):
        super().__init__(parent)
        self.items: List[LLMEndpointItem] = [LLMEndpointItem(d) for d in (value or [])]
        self._sorted_indices: List[int] = []
        self._init_ui()
        self._refresh_list()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("➕ Додати")
        add_btn.clicked.connect(self._add_item)
        toolbar.addWidget(add_btn)

        edit_btn = QPushButton("✏️ Редагувати")
        edit_btn.clicked.connect(self._edit_item)
        toolbar.addWidget(edit_btn)

        copy_btn = QPushButton("📋 Скопіювати")
        copy_btn.clicked.connect(self._copy_item)
        toolbar.addWidget(copy_btn)

        remove_btn = QPushButton("🗑️ Видалити")
        remove_btn.clicked.connect(self._remove_item)
        toolbar.addWidget(remove_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # List
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._edit_item)
        layout.addWidget(self.list_widget)

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        # Сортуємо items за цифровим role
        def get_role_order(item):
            try:
                return int(item.role) if item.role else 999
            except (ValueError, TypeError):
                # Для сумісності зі старими текстовими role
                role_map = {"primary": 1, "secondary": 2, "fallback": 3, "alternative": 4}
                return role_map.get(item.role, 999)

        sorted_items = sorted(self.items, key=get_role_order)
        # Зберігаємо відсортовані індекси для коректного редагування
        self._sorted_indices = [self.items.index(item) for item in sorted_items]

        for item in sorted_items:
            status = "✅" if item.enabled else "❌"
            api_status = "✅" if item.api_key else "❌"
            text = f"{status} "
            if item.role:
                text += f"[порядок={item.role}] "
            if item.name:
                text += f"{item.name} "
            if item.url:
                text += f"URL ({item.url}) "
            if item.model:
                text += f"Модель({item.model}) "
            text += f"API ({api_status})"
            self.list_widget.addItem(text)

    def _add_item(self) -> None:
        dlg = LLMEndpointDialog(parent=self, total_items=len(self.items) + 1)
        if dlg.exec():
            self.items.append(dlg.get_item())
            self._refresh_list()
            self.changed.emit()

    def _edit_item(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._sorted_indices):
            return
        # Отримуємо реальний індекс в self.items через _sorted_indices
        actual_index = self._sorted_indices[row]
        if actual_index < 0 or actual_index >= len(self.items):
            return
        dlg = LLMEndpointDialog(self.items[actual_index], parent=self, total_items=len(self.items))
        if dlg.exec():
            self.items[actual_index] = dlg.get_item()
            self._refresh_list()
            self.changed.emit()

    def _copy_item(self) -> None:
        """Копіювати налаштування вибраної LLM моделі на новий рядок."""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._sorted_indices):
            return
        # Отримуємо реальний індекс в self.items через _sorted_indices
        actual_index = self._sorted_indices[row]
        if actual_index < 0 or actual_index >= len(self.items):
            return
        # Копіюємо дані вибраного елементу
        original_data = self.items[actual_index].to_dict()
        # Змінюємо id щоб уникнути дублювання
        original_data["id"] = ""
        # Змінюємо name додавши копію
        if original_data.get("name"):
            original_data["name"] = f"{original_data['name']} (copy)"
        # Створюємо новий елемент з скопійованими даними
        new_item = LLMEndpointItem(original_data)
        self.items.append(new_item)
        self._refresh_list()
        self.changed.emit()

    def _remove_item(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._sorted_indices):
            return
        # Отримуємо реальний індекс в self.items через _sorted_indices
        actual_index = self._sorted_indices[row]
        if actual_index < 0 or actual_index >= len(self.items):
            return
        del self.items[actual_index]
        self._refresh_list()
        self.changed.emit()

    def get(self) -> List[dict]:
        """Повернути поточний список як List[dict]."""
        return [item.to_dict() for item in self.items]

    def set(self, value: List[dict]) -> None:
        """Встановити список з List[dict]."""
        self.items = [LLMEndpointItem(d) for d in (value or [])]
        self._refresh_list()
