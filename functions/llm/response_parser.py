# functions/llm/response_parser.py
"""Response parser for LLM responses."""
import json
import re
import time
from typing import Dict, Any, List, Optional
from colorama import Fore

# Кешування скомпільованих regex патернів для продуктивності
_JSON_CODE_BLOCK_PATTERN = re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.DOTALL | re.IGNORECASE)
_QUOTE_PATTERN = re.compile(r'["\']([^"\']+)["\']')
_WORD_AFTER_PATTERN = re.compile(r'слово\s+([а-яА-ЯіїєІЇЄґҐa-zA-Z]+)', re.IGNORECASE)
_COMMAND_AFTER_PATTERN = re.compile(r'команду\s+([а-яА-ЯіїєІЇЄґҐa-zA-Z]+)', re.IGNORECASE)
_WINDOW_PATTERN = re.compile(r'(?:у вікно|в вікно|в окно|в окно)\s+([а-яА-ЯіїєІЇЄґҐa-zA-Z0-9_]+)', re.IGNORECASE)
_MESSAGE_TOKEN_PATTERN = re.compile(r'<\|message\|>(\{.*?\})')


def sanitize_json_string(text: str) -> str:
    """Екранувати сирі переноси рядка/табуляції всередині JSON string-значень.

    LLM часто генерує JSON з реальними \n всередині полів типу `code`,
    що ламає `json.loads`. Ця функція проходить текст і екранує control-
    символи (\n, \r, \t) тільки всередині лапок.
    
    Args:
        text: Текст JSON з можливими сирими control символами
        
    Returns:
        Санітізований текст з екранованими control символами
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


def safe_json_loads(text: str) -> Any:
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
    
    Args:
        text: Текст відповіді LLM з токенами
        
    Returns:
        Очищений текст без токенів
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


def _find_matching_brace(text: str, open_char: str, close_char: str, start: int) -> int:
    """Знайти індекс парної закриваючої дужки, враховуючи рядки та escape."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if not in_string:
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return i
    return -1


def _try_extract_json(clean_text: str, open_char: str, close_char: str) -> Optional[str]:
    """Спробувати витягти перший валідний JSON об'єкт/масив з тексту."""
    start = clean_text.find(open_char)
    if start == -1:
        return None
    end = _find_matching_brace(clean_text, open_char, close_char, start)
    if end == -1 or end <= start:
        return None
    candidate = clean_text[start:end + 1]
    try:
        safe_json_loads(candidate)
        return candidate
    except Exception:
        return None


def extract_json_from_text(text: str) -> str:
    """Витягти перший валідний JSON з тексту (з очисткою службових токенів LLM)."""
    clean_text = clean_llm_tokens(text)

    # Якщо це JSON в блоках ```json ... ``` (або ```...```)
    code_block = _JSON_CODE_BLOCK_PATTERN.search(clean_text)
    if code_block:
        return code_block.group(1).strip()

    # JSON-масив [...]
    candidate = _try_extract_json(clean_text, '[', ']')
    if candidate:
        return candidate

    # JSON-об'єкт {...} — беремо ТІЛЬКИ перший валідний (за допомогою brace matching)
    candidate = _try_extract_json(clean_text, '{', '}')
    if candidate:
        return candidate

    # Нічого не знайдено — повертаємо ОЧИЩЕНИЙ текст напряму (без JSON обгортки)
    return clean_text


def extract_all_json_actions(text: str) -> List[Dict[str, Any]]:
    """Витягти ВСІ JSON-об'єкти з тексту та повернути список dict для виконання.

    Корисно коли LLM повертає кілька дій підряд:
        {"action": "..."}\n{"action": "..."}
    Також підтримує JSON без action (наприклад {"code": "..."} → execute_python).
    """
    clean_text = clean_llm_tokens(text)
    actions = []
    i = 0
    while True:
        start = clean_text.find('{', i)
        if start == -1:
            break
        end = _find_matching_brace(clean_text, '{', '}', start)
        if end == -1:
            i = start + 1
            continue
        candidate = clean_text[start:end + 1]
        try:
            obj = safe_json_loads(candidate)
            if isinstance(obj, dict):
                # Якщо є action — додаємо як є
                if "action" in obj:
                    actions.append(obj)
                # Якщо є code без action — це execute_python
                elif "code" in obj and "action" not in obj:
                    obj["action"] = "execute_python"
                    actions.append(obj)
                # Якщо є text і action відсутній — може бути keyboard_type
                elif "text" in obj and "action" not in obj:
                    obj["action"] = "keyboard_type"
                    actions.append(obj)
            i = end + 1
        except Exception:
            i = start + 1
    return actions


def _extract_text_to_type(command_text: str) -> Optional[str]:
    """Витягти текст для введення з команди."""
    # Спроба 1: слово в лапках
    text_match = _QUOTE_PATTERN.search(command_text)
    if text_match:
        return text_match.group(1)
    
    # Спроба 2: слово після "слово"
    text_match = _WORD_AFTER_PATTERN.search(command_text)
    if text_match:
        return text_match.group(1)
    
    # Спроба 3: слово після "команду"
    text_match = _COMMAND_AFTER_PATTERN.search(command_text)
    if text_match:
        return text_match.group(1)
    
    # Спроба 4: останнє слово
    words = command_text.split()
    if len(words) > 1:
        return words[-1]
    
    return command_text


def _is_type_command(text: str) -> bool:
    """Перевірити чи це команда для введення тексту."""
    return any(keyword in text.lower() for keyword in ("введе", "введи", "напиши"))


def _execute_single_action(registry, action_dict):
    """Виконати одну дію з dict. Повертає (success: bool, result_str)."""
    # Gemini іноді вертає вкладені параметри: {"parameters": {"title": "..."}}
    if "parameters" in action_dict and isinstance(action_dict["parameters"], dict):
        nested = action_dict.pop("parameters")
        action_dict.update(nested)

    action = action_dict.pop("action", None)
    if not action:
        return False, "Немає action"
    action_map = {
        "execute_python": "execute_python",
        "execute_python_code": "execute_python",
        "run_python": "execute_python",
        "debug_python_code": "debug_python_code",
        "list_sandbox_scripts": "list_sandbox_scripts",
        "execute_python_file": "execute_python_file",
        "open_program": "open_program",
        "close_program": "close_program",
        "activate_window": "activate_window",
        "activate_window_by_title": "activate_window_by_title",
        "find_windsurf_window": "activate_window_by_title",
        "list_windows": "list_windows",
        "keyboard_type": "keyboard_type",
        "press_key": "press_key",
        "open_browser": "open_browser_playwright",
        "playwright_navigate": "playwright_navigate",
        "playwright_click": "playwright_click",
        "playwright_type": "playwright_type",
        "playwright_screenshot": "playwright_screenshot",
        "playwright_get_text": "playwright_get_text",
        "playwright_evaluate": "playwright_evaluate",
        "playwright_close": "playwright_close",
    }
    function_name = action_map.get(action, action)

    # Конвертація параметрів: activate_window з program_name/title -> activate_window_by_title
    if function_name == "activate_window" and ("program_name" in action_dict or "title" in action_dict):
        function_name = "activate_window_by_title"
        if "program_name" in action_dict:
            action_dict["title"] = action_dict.pop("program_name")

    # Дефолтний title для activate_window_by_title (від find_windsurf_window без параметрів)
    if function_name == "activate_window_by_title" and "title" not in action_dict:
        action_dict["title"] = "Windsurf"

    print(f"{Fore.MAGENTA}⚡ [Виконую]: {function_name} з параметрами {action_dict}")
    try:
        result = registry.execute_function(function_name, action_dict)
        # Затримка після активації вікна, щоб воно встигло перейти на передній план і отримати фокус
        if function_name in ("activate_window_by_title", "activate_window"):
            time.sleep(1.0)  # Збільшено з 0.7 до 1.0 для кращого фокусу перед keyboard_type
        # Затримка перед keyboard_type для кращого фокусу
        if function_name == "keyboard_type":
            time.sleep(0.3)
        if result is None or result == "":
            return True, f"✅ Виконано: {function_name}"
        return True, result
    except Exception as e:
        return False, f"❌ {function_name}: {e}"


def _handle_empty_response(original_command: str, registry) -> Optional[str]:
    """Обробити порожню відповідь LLM, спробувавши розпізнати команду з оригінального тексту."""
    print(f"{Fore.LIGHTBLACK_EX}[DEBUG] LLM повернув порожню відповідь, спробуємо розпізнати з команди користувача")
    clean_command = original_command.strip()
    
    if not _is_type_command(clean_command):
        return None
    
    text_to_type = _extract_text_to_type(clean_command)
    print(f"{Fore.LIGHTBLACK_EX}[DEBUG] text_to_type (from command): '{text_to_type}'")
    
    # Перевіряємо чи є вказане вікно для активації
    window_match = _WINDOW_PATTERN.search(clean_command)
    
    actions_performed = []
    
    if window_match:
        window_title = window_match.group(1)
        print(f"{Fore.LIGHTBLACK_EX}[DEBUG] window_title: '{window_title}'")
        try:
            registry.execute_function("activate_window_by_title", {"title": window_title})
            time.sleep(0.7)
            actions_performed.append(f"🔓 Активовано вікно: {window_title}")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Не вдалося активувати вікно: {e}")
            actions_performed.append(f"❌ Не вдалося активувати вікно: {e}")
    
    try:
        result = registry.execute_function("keyboard_type", {"text": text_to_type})
        actions_performed.append(f"⌨️ Введено текст: {text_to_type}")
        return "\n".join(actions_performed) + "\n\n✅ Команду виконано"
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️ Не вдалося виконати keyboard_type: {e}")
        actions_performed.append(f"❌ Не вдалося ввести текст: {e}")
        return "\n".join(actions_performed)


def _handle_simple_text_command(clean_text: str, registry) -> Optional[str]:
    """Обробити просту текстову команду без JSON."""
    if not _is_type_command(clean_text):
        return None
    
    if '{' in clean_text:
        return None  # Є JSON - використаємо звичайний парсинг
    
    text_to_type = _extract_text_to_type(clean_text)
    print(f"{Fore.LIGHTBLACK_EX}[DEBUG] text_to_type: '{text_to_type}'")
    
    try:
        result = registry.execute_function("keyboard_type", {"text": text_to_type})
        return "✅ Команду виконано"
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️ Не вдалося виконати keyboard_type: {e}")
        return f"❌ Не вдалося ввести текст: {e}"


def _format_action_summary(action: dict) -> str:
    """Сформувати людинозрозумілий опис дії."""
    action_name = action.get("action", "")
    if action_name == "keyboard_type":
        text = action.get("text", "")
        return f"⌨️ Написано у вікно: {text}"
    elif action_name in ("activate_window_by_title", "activate_window"):
        title = action.get("title", "")
        return f"🔓 Активовано вікно: {title}"
    elif action_name == "press_key":
        key = action.get("key", "")
        return f"⌨️ Натиснуто клавішу: {key}"
    else:
        return f"⚡ Виконано: {action_name}"


def _handle_multi_actions(multi_actions: list, registry) -> Optional[str]:
    """Обробити множинні JSON-дії."""
    if len(multi_actions) <= 1:
        return None
    
    summary = []
    for i, act_obj in enumerate(multi_actions):
        act_copy = dict(act_obj)
        summary.append(_format_action_summary(act_copy))
        _execute_single_action(registry, act_copy)
        
        # Затримка та клік між діями якщо наступна дія це keyboard_type
        if i < len(multi_actions) - 1:
            next_action = multi_actions[i + 1].get("action", "")
            if next_action == "keyboard_type":
                time.sleep(1.0)
                try:
                    registry.execute_function("mouse_click", {})
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️ Не вдалося клікнути для фокусу: {e}")
    
    return "\n".join(summary)


def _handle_json_response(response_json: dict, registry, response_text: str) -> str:
    """Обробити JSON відповідь від LLM."""
    # Якщо це відповідь
    if "response" in response_json and "action" not in response_json:
        response_text = response_json["response"]
        
        # Перевіряємо чи response_text є JSON (для моделей які загортають JSON у response)
        try:
            nested_json = safe_json_loads(response_text)
            if isinstance(nested_json, dict):
                # Якщо nested_json має action, використовуємо його замість зовнішнього JSON
                if "action" in nested_json:
                    response_json = nested_json
                elif "actions" in nested_json:
                    response_json = nested_json
                # Якщо nested_json має тільки response, це вже розпакований response - повертаємо як текст
                elif "response" in nested_json:
                    return response_text  # Повертаємо як текст, не парсимо ще раз
        except:
            pass  # Не JSON, використовуємо як текст
        
        if not response_text or response_text.strip() == "":
            full_response = clean_llm_tokens(response_text.strip())
            if full_response and _is_type_command(full_response):
                text_to_type = _extract_text_to_type(full_response)
                try:
                    result = registry.execute_function("keyboard_type", {"text": text_to_type})
                    return "✅ Команду виконано"
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️ Не вдалося виконати keyboard_type: {e}")
                    return f"❌ Не вдалося ввести текст: {e}"
            return "Я не зміг сформувати відповідь. Спробуйте перефразувати питання."
        # Якщо response_text не JSON і не порожній, повертаємо як текст
        if "action" not in response_json:
            return response_text

    # Прості обчислення: {"result": 4}
    if "result" in response_json and "action" not in response_json and "actions" not in response_json:
        return str(response_json["result"])

    # Множинні дії: {"actions": [...]}
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
            if "parameters" in act_copy and isinstance(act_copy["parameters"], dict):
                nested = act_copy.pop("parameters")
                act_copy.update(nested)
            if "args" in act_copy and isinstance(act_copy["args"], dict):
                nested = act_copy.pop("args")
                act_copy.update(nested)
            act = act_copy.pop("action", None)
            if not act:
                continue
            fn = action_map.get(act, act)
            print(f"{Fore.MAGENTA}⚡ [Дія {fn}]: {act_copy}")
            try:
                r = registry.execute_function(fn, act_copy)
                results.append(f"• {fn}: {r}")
            except Exception as e:
                results.append(f"• {fn}: ❌ {e}")
        return "\n".join(results) if results else "❌ Порожній список дій"

    # Одиночна дія
    if "action" in response_json:
        ok, result = _execute_single_action(registry, response_json)
        if ok:
            return result if result else "✅ Команду виконано"
        return result

    # Прямий код без action
    if "code" in response_json and "action" not in response_json:
        print(f"{Fore.MAGENTA}⚡ [Виконую execute_python з прямим code]")
        result = registry.execute_function("execute_python", response_json)
        if result and not isinstance(result, dict):
            return str(result)
        return "✅ Команду виконано"

    # Відкриття програми
    if "program_name" in response_json:
        print(f"{Fore.MAGENTA}⚡ [Виконую open_program]")
        result = registry.execute_function("open_program", response_json)
        return "✅ Команду виконано"

    return f"❌ Невідомий формат команди: {response_json}"


def _try_extract_from_tokens(response_text: str, registry) -> Optional[str]:
    """Спробувати витягти JSON з токенів."""
    if "to=functions.open_program" not in response_text:
        return None
    
    json_match = _MESSAGE_TOKEN_PATTERN.search(response_text)
    if not json_match:
        return None
    
    try:
        json_str = json_match.group(1)
        response_json = safe_json_loads(json_str)
        if "program_name" in response_json:
            print(f"{Fore.MAGENTA}⚡ [Знайдено через токени]: open_program")
            result = registry.execute_function("open_program", response_json)
            return result
    except Exception:
        pass
    
    return None


def process_llm_response(response_text, registry, original_command=None):
    """Обробити відповідь LLM і виконати функції
    
    Args:
        response_text: Відповідь від LLM
        registry: Реєстр функцій
        original_command: Оригінальна команда користувача (для fallback логіки)
    """
    clean_text = clean_llm_tokens(response_text).strip()
    
    # Логування для відладки
    print(f"{Fore.LIGHTBLACK_EX}[DEBUG] clean_text: '{clean_text}'")
    print(f"{Fore.LIGHTBLACK_EX}[DEBUG] response_text: '{response_text}'")
    if original_command:
        print(f"{Fore.LIGHTBLACK_EX}[DEBUG] original_command: '{original_command}'")
    
    # Fallback: якщо LLM повернув порожню відповідь
    if not clean_text and original_command:
        result = _handle_empty_response(original_command, registry)
        if result:
            return result
    
    # Проста текстова команда без JSON
    if clean_text:
        result = _handle_simple_text_command(clean_text, registry)
        if result:
            return result
    
    # Множинні JSON-дії
    multi_actions = extract_all_json_actions(response_text)
    print(f"{Fore.LIGHTBLACK_EX}🔍 [Action parser]: знайдено {len(multi_actions)} дій")
    for i, a in enumerate(multi_actions):
        print(f"{Fore.LIGHTBLACK_EX}   • Дія {i+1}: {a.get('action', '???')}")
    
    result = _handle_multi_actions(multi_actions, registry)
    if result:
        return result

    # Спробувати отримати чистий JSON
    json_text = extract_json_from_text(response_text)
    print(f"{Fore.LIGHTBLACK_EX}📦 [Спроба парсингу]: {json_text[:200]}...")
    
    try:
        response_json = safe_json_loads(json_text)
        return _handle_json_response(response_json, registry, response_text)
    except json.JSONDecodeError as e:
        print(f"{Fore.YELLOW}⚠️ [JSON помилка]: {e}")
        print(f"{Fore.YELLOW}⚠️ [Оригінал]: {response_text}")

        # Fallback: спробувати витягти кілька JSON-дій окремо
        if len(multi_actions) >= 1:
            results = []
            for act_obj in multi_actions:
                ok, res = _execute_single_action(registry, dict(act_obj))
                results.append(res)
            return "\n".join(results)

        # Спробувати витягти JSON з токенів
        result = _try_extract_from_tokens(response_text, registry)
        if result:
            return result
        
        return response_text
    except Exception as e:
        return f"{Fore.RED}❌ Помилка обробки: {str(e)}"
