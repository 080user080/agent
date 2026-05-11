# 🔌 API

## Огляд

Цей документ описує API для інтеграції з агентом. Наразі API знаходиться в розробці.

## FunctionRegistry API

### Реєстрація функції

```python
from functions.logic_core import FunctionRegistry

def my_function(param: str) -> str:
    """Опис функції."""
    return f"Result: {param}"

FunctionRegistry.register("my_function", my_function)
```

### Виклик функції

```python
result = FunctionRegistry.call("my_function", param="test")
```

## GUI Callback API

### Відправка команди в ядро

```python
# Tkinter
gui_callback('process_text', 'Створи файл test.py')

# PyQt6
gui_callback('process_text', 'Створи файл test.py')
```

### Доступні callback-и

| Callback | Параметри | Опис |
|----------|-----------|------|
| `process_text` | `text: str` | Обробка текстової команди |
| `run_agent` | `task: str` | Запуск AgentLoop |
| `run_plan` | - | Виконання плану |
| `stop_plan` | - | Зупинення плану |
| `stop_execution` | - | Зупинення виконання |
| `pause_listening` | - | Призупинити слухання |
| `resume_listening` | - | Відновити слухання |
| `start_windsurf_watch` | - | Запустити Windsurf Watch |
| `stop_windsurf_watch` | - | Зупинити Windsurf Watch |

## LLM API

### Запит до LLM

```python
from functions.logic_llm import ask_llm

response = ask_llm("Привіт, як справи?")
```

### Запит з tool-calling

```python
from functions.logic_llm import ask_llm_with_tools

tools = [
    {"name": "create_file", "description": "Створити файл"},
    {"name": "execute_python", "description": "Виконати код"}
]

response = ask_llm_with_tools("Створи файл hello.py", tools)
```

## AssistantCore API

### Ініціалізація

```python
from main import AssistantCore
import queue

gui_queue = queue.Queue()
core = AssistantCore(gui_queue=gui_queue)
core.initialize_without_listener()
```

### Обробка команди

```python
core.process_text_command("Створи файл test.py")
```

### Запуск AgentLoop

```python
core.run_agent_loop("Створи проєкт з 3 файлами")
```

## GUI Queue API

### Повідомлення в GUI

```python
gui_queue.put(('add_message', ('assistant', 'Привіт!')))
gui_queue.put(('update_status', 'Готовий'))
gui_queue.put(('update_progress', 50))
```

### Типи повідомлень

| Тип | Параметри | Опис |
|-----|-----------|------|
| `add_message` | `(sender, message)` | Додати повідомлення в чат |
| `update_status` | `status: str` | Оновити статус |
| `update_progress` | `value: int` | Оновити прогрес |
| `stream_start` | - | Початок стрімінгу |
| `stream_chunk` | `chunk: str` | Чанк стрімінгу |
| `stream_end` | - | Кінець стрімінгу |
| `show_confirmation` | `question: str` | Показати підтвердження |
| `execution_started` | - | Виконання запущено |
| `execution_finished` | - | Виконання завершено |
| `plan_started` | `plan: dict` | План запущено |
| `step_update` | `step: dict` | Крок оновлено |
| `plan_finished` | `stats: dict` | План завершено |

## LoopDetector API

### Ініціалізація

```python
from functions.core_loop_detector import LoopDetector

# max_repeats: скільки однакових дій = зациклення (default 3)
ld = LoopDetector(max_repeats=3)
```

### Перевірка на зациклення

```python
# Повертає True якщо дія створює зациклення
is_loop = ld.is_looping("click", {"x": 100, "y": 200})

# Отримати статус stuck
if ld.is_stuck:
    print("Агент зациклився")
```

### Обробка успішних дій

```python
# Скидає is_stuck після успішної дії
ld.on_action_success()
```

### Попередження для LLM

```python
# Текст попередження для промпту
warning = ld.get_stuck_warning_message()
# Вмістить "КРИТИЧНЕ ЗАУВАЖЕННЯ: Ти щойно намагався..."
```

### Статистика

```python
stats = ld.get_stats()
# {'is_stuck': False, 'total_loops_detected': 2, ...}
```

### Скидання

```python
ld.reset()           # Очистити історію (після виявлення)
ld.full_reset()      # Повне скидання для нової сесії
```

## Global Voice Input API

### Ініціалізація

```python
from functions.global_voice_input import GlobalVoiceInput

def on_voice_text(text: str):
    print(f"Розпізнано: {text}")

def on_status(status: str):
    print(f"Статус: {status}")

gvi = GlobalVoiceInput(
    hotkey="ctrl+shift+v",
    callback=on_voice_text,
    status_callback=on_status
)
gvi.start()
```

### Зупинення

```python
gvi.stop()
```

## Примітка

API знаходиться в активній розробці. Деталі можуть змінюватися.
