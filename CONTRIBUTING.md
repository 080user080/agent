# 🤝 Внесок в проєкт

Дякуємо за інтерес до проєкту! Цей документ допоможе вам розпочати.

---

## 🚀 Швидкий старт для розробників

### 1. Налаштування середовища

```bash
# Клонування
git clone <repo-url>
cd agent

# Віртуальне середовище (рекомендовано)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Залежності
pip install -r requirements.txt
pip install -r requirements-dev.txt  # dev залежності
```

### 2. Структура коду

```
functions/          # Бізнес-логіка
├── core_*.py      # Core модулі (планер, executor, пам'ять)
├── logic_*.py     # Логіка обробки
└── tools_*.py     # Інструменти

gui/               # GUI компоненти
├── main_gui.py    # Головне вікно
└── settings/      # Налаштування

tests/             # Тести
└── test_*.py      # pytest тести
```

### 3. Запуск для розробки

```bash
# З логуванням
python agent.py --debug

# Тільки консоль (без GUI)
python agent.py --cli

# Тести
python -m pytest tests/ -v

# Лінтер
flake8 functions/
black functions/
```

---

## 🏗️ Архітектура

### Додавання нового інструменту

1. **Визначити функцію** в `functions/tools_*.py`:
```python
def my_new_tool(param1: str, param2: int = 0) -> str:
    """Опис функції для LLM.
    
    Args:
        param1: Опис параметра
        param2: Опис опціонального параметра
    
    Returns:
        Результат виконання
    """
    # Реалізація
    return f"Результат: {param1}"
```

2. **Зареєструвати** в `functions/core_tool_runtime.py`:
```python
self.register("my_new_tool", my_new_tool, {
    "risk": "low",
    "confirm": False,
    "idempotent": True,  # True якщо без побічних ефектів
})
```

3. **Додати тест** в `tests/test_tools_*.py` (опціонально)

### Додавання нового core модуля

1. Створити файл `functions/core_my_module.py`
2. Експортувати клас:
```python
class MyModule:
    def __init__(self, registry):
        self.registry = registry
    
    def do_something(self):
        pass
```
3. Зареєструвати в `functions/core_tool_runtime.py`:
```python
self.register_core_module("my_module", core_my_module)
```

---

## 🧪 Тести

### Структура тестів

```python
# tests/test_my_module.py
import pytest
from functions.my_module import MyClass

class TestMyClass:
    """Група тестів для класу."""
    
    def test_feature_x(self):
        """Опис що тестуємо."""
        obj = MyClass()
        result = obj.feature_x()
        assert result == "expected"
    
    def test_feature_y_raises_error(self):
        """Тест помилки."""
        with pytest.raises(ValueError):
            MyClass.invalid_call()
```

### Запуск тестів

```bash
# Всі тести
pytest tests/ -v

# Конкретний файл
pytest tests/test_core_planner.py -v

# Конкретний тест
pytest tests/test_core_planner.py::TestPlanner::test_create_plan_simple -v

# З покриттям
pytest --cov=functions tests/
```

### Моки (mocks)

```python
from unittest.mock import Mock, patch

def test_with_mock():
    mock_llm = Mock(return_value='{"plan": []}')
    
    with patch('functions.logic_llm.ask_llm', mock_llm):
        result = some_function()
        assert result is not None
```

---

## 📝 Code Style

### Python
- **PEP 8** — стандартний стиль
- **Type hints** — де можливо
- **Docstrings** — Google style

```python
def function_name(param: str, optional: int = 0) -> bool:
    """Короткий опис.
    
    Args:
        param: Опис обов'язкового параметра
        optional: Опис опціонального параметра
    
    Returns:
        Опис повертаного значення
    
    Raises:
        ValueError: Коли виникає помилка
    """
    return True
```

### Коміти
- Короткі, зрозумілі повідомлення
- Префікси: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`

```bash
git commit -m "feat: додати retry механізм для планера"
git commit -m "fix: виправити парсинг JSON з лапками"
git commit -m "test: додати тести для core_memory"
```

---

## 🐛 Дебаг

### Логування

```python
from colorama import Fore

print(f"{Fore.CYAN}[DEBUG] Змінна: {value}")
```

### Відлагодження тестів

```bash
# Зупинитися на першій помилці
pytest -x

# Запустити з pdb
pytest --pdb

# Детальний вивід
pytest -vv
```

---

## 📋 Чекліст перед PR

- [ ] Код працює локально
- [ ] Тести проходять (`pytest tests/`)
- [ ] Лінтер не свариться (`flake8 functions/`)
- [ ] Додано/оновлено docstrings
- [ ] Оновлено `status.md` якщо потрібно

---

## 🆘 Допомога

Якщо виникли питання:
1. Перевірте `status.md` — там актуальний статус
2. Подивіться існуючі тести — приклади використання
3. Відкрийте issue з описом проблеми

---

Дякуємо за внесок! 🎉
