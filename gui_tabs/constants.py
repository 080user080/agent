"""Константи для GUI вкладок."""
from dataclasses import dataclass


# Кольори для ролей в чаті
ROLE_COLORS: dict[str, str] = {
    "user": "#0078d4",
    "assistant": "#107c10",
    "system": "#6c757d",
}


# Кольори для рівнів логів
LOG_LEVEL_COLORS: dict[str, str] = {
    "INFO": "#000000",
    "WARNING": "#d48806",
    "ERROR": "#c53030",
    "DEBUG": "#6c757d",
}


# Швидкі команди для чату
QUICK_COMMANDS = ["Привіт", "Допомога", "Статус", "Очистити"]


# Назви вкладок
TAB_NAMES = {
    "chat": "💬 Чат",
    "settings": "⚙️ Налаштування",
    "logs": "📋 Логи",
    "statistics": "📊 Статистика",
    "about": "ℹ️ Про програму",
    "tools": "🔧 Інструменти",
}


# Тестові логи
TEST_LOGS = [
    ("INFO", "agent_loop", "AgentLoop запущено"),
    ("INFO", "llm", "З'єднання з LLM встановлено"),
    ("WARNING", "agent_loop", "Послідовні невдачі: 2"),
    ("ERROR", "registry", "Функція не знайдена: unknown_function"),
    ("DEBUG", "decider", "JSON парсинг успішний"),
    ("INFO", "gui", "Вікно оновлено"),
    ("WARNING", "llm", "Квота майже вичерпана"),
    ("INFO", "agent_loop", "Завдання завершено успішно"),
]


# Тестові інструменти
TEST_TOOLS = [
    ("take_screenshot", "Зробити скріншот екрану", "Активний"),
    ("ocr_screen", "Розпізнати текст з екрану", "Активний"),
    ("mouse_click", "Клікнути мишкою", "Активний"),
    ("keyboard_type", "Ввести текст", "Активний"),
    ("list_directory", "Показати файли в папці", "Активний"),
    ("read_code_file", "Прочитати файл коду", "Активний"),
    ("find_text_on_screen", "Знайти текст на екрані", "Активний"),
    ("open_program", "Відкрити програму", "Активний"),
]


# Особливості програми
FEATURES = [
    "✅ Інтеграція з LM Studio та OpenAI",
    "✅ Підтримка function-calling та JSON parsing",
    "✅ AgentLoop для автоматизації задач",
    "✅ OCR та Vision capabilities",
    "✅ Гнучка система плагінів",
    "✅ GUI на PyQt6",
]


# Технології
TECHNOLOGIES = [
    "Python 3.10+",
    "PyQt6",
    "PIL (Pillow)",
    "pytesseract",
    "requests",
]


@dataclass
class SettingsDefaults:
    """Дефолтні значення налаштувань."""
    language_index: int = 0
    theme_index: int = 0
    auto_save: bool = True
    model_index: int = 0
    temperature: int = 70
    max_tokens: int = 2000
    stream_response: bool = True
    max_steps: int = 10
    max_time: int = 60
    enable_ocr: bool = True
    enable_vision: bool = False


# Список мов
LANGUAGES = ["Українська", "English", "Русский"]


# Список тем
THEMES = ["Світла", "Темна", "Системна"]


# Список моделей
MODELS = ["GPT-OSS-20B", "DeepSeek-Coder", "Gemini-Pro", "Claude-3"]


# Рівні логів для фільтрації
LOG_LEVELS = ["Всі", "INFO", "WARNING", "ERROR", "DEBUG"]


# Посилання
LINKS = {
    "github": "GitHub: https://github.com/your-repo",
    "docs": "Документація: https://docs.example.com",
    "license": "Ліцензія: MIT",
}


# Версія програми
APP_VERSION = "2.0.0"


# Назва програми
APP_NAME = "МАРК — AI Асистент"


# Опис програми
APP_DESCRIPTION = (
    "МАРК — це інтелектуальний асистент на основі LLM, "
    "який допомагає виконувати задачі на комп'ютері, "
    "аналізувати код, працювати з GUI та багато іншого."
)
