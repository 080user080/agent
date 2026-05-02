# Налаштування LM Studio для AgentLoop (JSON Schema)

## Проблема

Моделі в LM Studio (qwen3, deepseek-coder) не підтримують OpenAI `tool_calls` через `/v1/chat/completions`. Виникає помилка:

```
http 400: Error rendering prompt with jinja template: "Unknown StringValue filter: safe"
```

## Рішення: JSON Schema (Structured Output)

JSON Schema змушує модель **завжди** повертати JSON у заданому форматі. ActionDecider парсить цей JSON.

---

## Спосіб 1: Через LM Studio UI (рекомендовано для тестування)

1. Відкрий LM Studio
2. Вибери модель (qwen3 або deepseek-coder)
3. Перейди у вкладку **Chat Settings** (⚙️ праворуч від чату)
4. Знайди секцію **Response Format**
5. Вибери **JSON Schema** (замість "Plain Text" або "JSON")
6. Встав схему нижче у поле **JSON Schema**
7. Натисни **Save**

### JSON Schema для AgentLoop

```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "description": "Ім'я інструменту для виконання. Спеціальні значення: 'done' (завершити), 'ask_user' (запитати користувача)."
    },
    "args": {
      "type": "object",
      "description": "Аргументи для інструменту. Об'єкт з ключ-значення. Для 'done': {'summary': 'результат', 'success': true/false}. Для 'ask_user': {'question': 'текст питання', 'options': ['варіант1', 'варіант2']}."
    },
    "reasoning": {
      "type": "string",
      "description": "Коротке пояснення чому обрано цю дію (1-2 речення)."
    }
  },
  "required": ["action", "args"],
  "additionalProperties": false
}
```

### System Prompt для LM Studio UI

У поле **System Prompt** (вкладка Chat Settings) встав:

```
Ти — агент, який керує комп'ютером користувача (миша, клавіатура, екран).
Тобі дано задачу і поточне спостереження екрану.
Твоя робота — повернути ОДИН наступний крок як JSON об'єкт.

Правила:
1. action — ім'я інструменту (list_directory, read_code_file, take_screenshot, done, ask_user, тощо)
2. args — об'єкт з аргументами для цього інструменту
3. reasoning — чому саме ця дія (1-2 речення)
4. Коли задача виконана — action="done", args={"summary": "результат"}
5. Якщо потрібна інформація від користувача — action="ask_user"
6. Ніколи не додавай markdown ```json, відповідай ТІЛЬКИ JSON об'єктом

Доступні інструменти (не всі):
- list_directory(directory) — показати файли в папці
- read_code_file(file_path) — прочитати файл
- take_screenshot() — зробити скріншот
- done(summary, success) — завершити задачу
- ask_user(question, options) — запитати користувача
```

---

## Спосіб 2: Через API (для AgentLoop автоматично)

У `functions/agent_loop.py` в метод `decide()` додати `response_format` до LLM-виклику:

```python
response = self._ask_llm_with_tools(
    messages=messages,
    tools=self._tools,
    tool_choice="auto",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "agent_action",
            "schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "args": {"type": "object"},
                    "reasoning": {"type": "string"}
                },
                "required": ["action", "args"]
            }
        }
    }
)
```

**Примітка:** Потрібно модифікувати `logic_llm_tools.py` щоб передавати `response_format` в запит.

---

## Перевірка

Після налаштування відправ тестове повідомлення в LM Studio:

```
ЗАДАЧА: Покажи файли в папці D:\\Python\\agent

ПОТОЧНЕ СПОСТЕРЕЖЕННЯ ЕКРАНУ:
Активне вікно: Провідник

ОСТАННІ ДІЇ:
(історія порожня — це перший крок)

Виклич ОДИН інструмент для наступного кроку.
```

**Очікувана відповідь:**
```json
{"action": "list_directory", "args": {"directory": "D:\\Python\\agent"}, "reasoning": "Потрібно переглянути файли в папці"}
```

Якщо модель повертає plain text замість JSON — перевір:
1. Чи ввімкнено JSON Schema в Response Format
2. Чи правильна схема (без помилок валідації)
3. Чи модель підтримує structured output (qwen3, llama 3.1+, mistral — так; deepseek-coder — може не підтримувати)

---

## Альтернатива: JSON Mode (простіше, менш надійно)

Якщо JSON Schema не працює, спробуй **JSON Mode**:

1. Chat Settings → Response Format → **JSON Mode**
2. Встав System Prompt з інструкцією "Відповідай ТІЛЬКИ JSON"

Це гарантує JSON-відповідь, але не перевіряє структуру (може бути не ті поля).

ActionDecider вже має fallback для цього — парсить JSON з content ігноруючи зайві поля.
