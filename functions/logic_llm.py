# functions/logic_llm.py
"""Робота з LLM"""
import re
import json
import requests
from colorama import Fore
from .config import LM_STUDIO_URL


def sanitize_json_string(text: str) -> str:
    """Екранувати сирі переноси рядка/табуляції всередині JSON string-значень.

    LLM часто генерує JSON з реальними \\n всередині полів типу `code`,
    що ламає `json.loads`. Ця функція проходить текст і екранує control-
    символи (\\n, \\r, \\t) тільки всередині лапок.
    """
    if not text:
        return text

    result = []
    in_string = False
    escape = False

    for ch in text:
        if escape:
            # Попередній символ був \, пропускаємо поточний як-є
            result.append(ch)
            escape = False
            continue

        if ch == "\\" and in_string:
            result.append(ch)
            escape = True
            continue

        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue

        if in_string:
            # Екрануємо сирі control chars усередині string
            if ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            elif ord(ch) < 0x20:
                result.append(f"\\u{ord(ch):04x}")
            else:
                result.append(ch)
        else:
            result.append(ch)

    return "".join(result)


def safe_json_loads(text: str):
    """Спробувати `json.loads`, а при помилці — після санітизації."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        sanitized = sanitize_json_string(text)
        return json.loads(sanitized)


def clean_llm_tokens(text: str) -> str:
    """Прибрати службові токени з відповіді LLM (gpt-oss / lm-studio / openai-чат-формат).

    Видаляє:
    - `<|channel|>`, `<|message|>`, `<|start|>`, `<|end|>`, ...
    - Метадані каналу: `commentary to=python code`, `to=functions.name`, `final json`, ...
    - Самостійні службові слова: `assistant`, `channel`, `constrain`, `commentary`, `final`.
    """
    if not text:
        return ""
    # 1. Прибрати токени <|...|>
    cleaned = re.sub(r'<\|[^|]*\|>', '', text)
    # 2. Прибрати метадані каналу типу `to=python code`, `to=functions.foo`
    cleaned = re.sub(r'to\s*=\s*[\w.]+(\s+\w+)?', '', cleaned)
    # 3. Прибрати службові слова поряд із токенами
    cleaned = re.sub(
        r'\b(assistant|channel|commentary|constrain|message|final)\b',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )
    # 4. Нормалізувати пробіли
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    return cleaned.strip()


def extract_json_from_text(text):
    """Витягти JSON з тексту (з очисткою службових токенів LLM)."""
    clean_text = clean_llm_tokens(text)

    # Якщо це JSON в блоках ```json ... ``` (або ```...```)
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_text, re.DOTALL | re.IGNORECASE)
    if json_match:
        return json_match.group(1).strip()

    # Якщо є JSON-масив [...]
    if '[' in clean_text and ']' in clean_text:
        start = clean_text.find('[')
        end = clean_text.rfind(']')
        if end > start:
            candidate = clean_text[start : end + 1]
            # Перевіримо валідність
            try:
                safe_json_loads(candidate)
                return candidate
            except Exception:
                pass

    # Якщо є JSON-об'єкт {...} (беремо від першого '{' до останнього '}')
    if '{' in clean_text and '}' in clean_text:
        start = clean_text.find('{')
        end = clean_text.rfind('}')
        if end > start:
            candidate = clean_text[start : end + 1]
            try:
                safe_json_loads(candidate)
                return candidate
            except Exception:
                # Може бути частковий JSON — повертаємо як є, парсер спробує sanitize
                return candidate

    # Нічого не знайдено — повертаємо ОЧИЩЕНИЙ текст як response
    return json.dumps({"response": clean_text}, ensure_ascii=False)

def ask_llm(user_message, conversation_history, system_prompt):
    """Відправити запит до LM Studio"""
    try:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        # Уникнути дублювання: якщо останнє повідомлення вже == user_message, не додаємо ще раз
        last = conversation_history[-1] if conversation_history else None
        if not (last and last.get("role") == "user" and last.get("content") == user_message):
            messages.append({"role": "user", "content": user_message})
        
        response = requests.post(LM_STUDIO_URL, 
            json={
                "model": "local-model",
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 1024,
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            error_text = response.text
            error_msg = f"Помилка API {response.status_code}: {error_text}"
            print(f"{Fore.RED}{error_msg}")

            # Детекція специфічних помилок з корисними порадами
            error_lower = error_text.lower()

            if "no models loaded" in error_lower or "invalid_request_error" in error_lower:
                user_msg = (
                    "❌ **Модель не завантажена в LM Studio**\n\n"
                    "Будь ласка:\n"
                    "1. Відкрийте LM Studio\n"
                    "2. Перейдіть на вкладку 'Developer'\n"
                    "3. Завантажте модель (наприклад, через 'Load Model')\n"
                    "4. Або виконайте в консолі: `lms load <model_name>`\n\n"
                    "Потім спробуйте знову."
                )
                return user_msg

            if "connection" in error_lower or "refused" in error_lower:
                return (
                    "❌ **Не вдається підключитися до LM Studio**\n\n"
                    "Перевірте:\n"
                    "1. Чи запущено LM Studio?\n"
                    "2. Чи ввімкнено 'API Server' в налаштуваннях LM Studio?\n"
                    "3. Чи правильний URL в Налаштуваннях агента?\n\n"
                    f"Поточний URL: {LM_STUDIO_URL}"
                )

            return f"Помилка: {response.status_code} - {error_text[:200]}"

    except requests.exceptions.ConnectionError:
        return (
            "❌ **LM Studio не відповідає**\n\n"
            "Перевірте:\n"
            "1. Чи запущено LM Studio?\n"
            "2. Чи ввімкнено API Server (порт 1234)?\n\n"
            f"URL: {LM_STUDIO_URL}"
        )

    except Exception as e:
        return f"{Fore.RED}❌ Помилка з'єднання: {str(e)}"

def process_llm_response(response_text, registry):
    """Обробити відповідь LLM і виконати функції"""
    # Спершу спробувати отримати чистий JSON
    json_text = extract_json_from_text(response_text)
    
    print(f"{Fore.LIGHTBLACK_EX}📦 [Спроба парсингу]: {json_text[:200]}...")
    
    try:
        response_json = safe_json_loads(json_text)
        
        # Якщо це відповідь
        if "response" in response_json and "action" not in response_json:
            return response_json["response"]

        # Прості обчислення: {"result": 4} → повертаємо як текст
        if "result" in response_json and "action" not in response_json and "actions" not in response_json:
            return str(response_json["result"])

        # Множинні дії: {"actions": [...]} → виконати по черзі
        if "actions" in response_json and isinstance(response_json["actions"], list):
            results = []
            action_map = {
                "execute_python": "execute_python",
                "execute_python_code": "execute_python",
                "run_python": "execute_python",
                "debug_python_code": "debug_python_code",
                "open_program": "open_program",
                "close_program": "close_program",
            }
            for act_obj in response_json["actions"]:
                if not isinstance(act_obj, dict):
                    continue
                act_copy = dict(act_obj)
                act = act_copy.pop("action", None)
                if not act:
                    continue
                fn = action_map.get(act, act)
                # Підтримати вкладені args
                if "args" in act_copy and isinstance(act_copy["args"], dict):
                    params = act_copy["args"]
                else:
                    params = act_copy
                print(f"{Fore.MAGENTA}⚡ [Дія {fn}]: {params}")
                try:
                    r = registry.execute_function(fn, params)
                    results.append(f"• {fn}: {r}")
                except Exception as e:
                    results.append(f"• {fn}: ❌ {e}")
            return "\n".join(results) if results else "❌ Порожній список дій"

        # 🔥 ВИПРАВЛЕННЯ: Додано execute_python
        if "action" in response_json:
            action = response_json.pop("action")
            
            # Мапінг action → function_name
            action_map = {
                "execute_python": "execute_python",
                "execute_python_code": "execute_python",
                "run_python": "execute_python",
                "debug_python_code": "debug_python_code",
                "list_sandbox_scripts": "list_sandbox_scripts",
                "execute_python_file": "execute_python_file",
                "open_program": "open_program",
                "close_program": "close_program",
            }
            
            # Перетворити action
            function_name = action_map.get(action, action)
            
            # Логування
            print(f"{Fore.MAGENTA}⚡ [Виконую]: {function_name} з параметрами {response_json}")
            
            # Виконати
            result = registry.execute_function(function_name, response_json)
            return result
        
        # Якщо немає action, але є code (прямий код)
        if "code" in response_json and "action" not in response_json:
            print(f"{Fore.MAGENTA}⚡ [Виконую execute_python з прямим code]")
            result = registry.execute_function("execute_python", response_json)
            return result
        
        # Якщо є program_name, то це відкриття програми
        if "program_name" in response_json:
            print(f"{Fore.MAGENTA}⚡ [Виконую open_program]")
            result = registry.execute_function("open_program", response_json)
            return result
        
        # Якщо невідомий формат
        return f"❌ Невідомий формат команди: {response_json}"
        
    except json.JSONDecodeError as e:
        print(f"{Fore.YELLOW}⚠️ [JSON помилка]: {e}")
        print(f"{Fore.YELLOW}⚠️ [Оригінал]: {response_text}")
        
        # Якщо не вдалося розпарсити, спробуємо витягти JSON з токенів
        if "to=functions.open_program" in response_text:
            json_match = re.search(r'<\|message\|>(\{.*?\})', response_text)
            if json_match:
                try:
                    json_str = json_match.group(1)
                    response_json = safe_json_loads(json_str)
                    if "program_name" in response_json:
                        print(f"{Fore.MAGENTA}⚡ [Знайдено через токени]: open_program")
                        result = registry.execute_function("open_program", response_json)
                        return result
                except:
                    pass
        
        return response_text
    except Exception as e:
        return f"{Fore.RED}❌ Помилка обробки: {str(e)}"
