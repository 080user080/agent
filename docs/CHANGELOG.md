# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ✅ Додано
- Динамічне збільшення поля вводу в PyQt6 GUI (`_update_input_height`)
- Папка `debug_logs/` для логів відладки

### 🐛 Виправлено
- Виправлено зупинку STT розпізнавання при натисканні кнопки (додано `stt_controller.stop()`)
- Виправлено метод `_update_input_height` — тепер використовує `documentLayout().documentSize().height()` замість `blockCount()` для коректної роботи з автоперенесенням тексту

### 📝 Змінено
- Очищено TEST_GUI: залишено 10 актуальних тестів, видалено застарілі
- Оновлено TEST_GUI/README.md
- Tkinter GUI переміщено в `backup/tkinter_legacy/`
- `gui_tabs/` переміщено в `backup/gui_tabs/`
- Актуалізовано документацію: README.md, status.md, ARCHITECTURE.md, MODULES.md

### 📚 Документація
- Оновлено README.md під актуальну структуру проєкту
- Оновлено status.md — видалено завершені пріоритети, додано нові
- Оновлено docs/ARCHITECTURE.md — виправлено посилання на неіснуючі файли
- Оновлено docs/MODULES.md — додано dynamic input, виправлено геометрію вікна

## [2.1.0] - 2026-05-05

### ✅ Додано
- Модульна архітектура GUI вкладок (`gui_tabs/`)
- PyQt6 підтримка для багатовкладкового інтерфейсу
- Глобальний голосовий ввід (Global Voice Input) з hotkey на Windows
- Self-learning модуль для аналізу помилок та генерації правил
- AgentLoop з observe → plan → act → check циклом
- TaskSpecCompiler для структурованої декомпозиції задач
- UIA (Windows UI Automation) інтеграція з uiautomation/pywinauto
- Vision-LM провайдер для семантичного розуміння UI
- Browser CDP інтеграція для автоматизації Chrome

### 🐛 Виправлено
- Виправлено логіку кольорів у LogsTab (використовує QColor з hex)
- Виправлено дубльовані обробники в run_assistant.py
- Видалено мертвий код (TaskSpecCompiler закоментований блок)
- Виправлено опечатки в константах (Консек'ютівні → Послідовні, майто → майже)

### 📝 Змінено
- Рефакторинг main.py: виділено `_gui_notify()`, `_init_assistant_common()`
- Рефакторинг run_assistant.py: dict dispatch замість if/elif
- Рефакторинг gui_tabs: видалено зайві None ініціалізації
- Додано реальне збереження налаштувань через QSettings

### 📚 Документація
- Переміщено документацію в папку `docs/`
- Створено CHANGELOG.md, SECURITY.md, MODULES.md

## [2.0.0] - 2026-04-28

### ✅ Додано
- PyQt6 GUI (паралельно з Tkinter)
- SettingsTabQtMixin для динамічного рендерингу налаштувань
- ChatPanelQtMixin, PlanPanelQtMixin, ConfirmationQtMixin
- LLMEndpointsEditor для PyQt6
- AgentLoop інтеграція з GUI (кнопка "🤖 Агент")

### 📝 Змінено
- Додано GUI_BACKEND setting (tkinter/pyqt6)
- Створено run.py — універсальна точка входу

## [1.0.0] - 2026-04-26

### ✅ Додано
- Початковий проєкт
- Tkinter GUI
- STT/TTS підтримка
- Planner для планування задач
- FunctionRegistry для динамічного виклику функцій
