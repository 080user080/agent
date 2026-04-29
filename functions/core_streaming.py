import requests
import json
from colorama import Fore

def _is_groq_endpoint(ep):
    """Перевірити чи це Groq endpoint."""
    url = ep.get("url", "")
    return "api.groq.com" in url

class StreamingHandler:
    """Обробник стрімінгу відповідей від LLM"""
    
    def __init__(self, api_url):
        # api_url використовується як fallback, якщо налаштування недоступні
        self.api_url = api_url
    
    def _get_endpoint(self):
        """Отримати активний primary endpoint з налаштувань."""
        try:
            from .llm import get_primary_endpoint
            return get_primary_endpoint()
        except Exception:
            return {
                "url": self.api_url,
                "model": "local-model",
                "api_key": "",
                "temperature": 0.1,
                "max_tokens": 8000,
                "timeout": 60,
            }
    
    def stream_response(self, messages):
        """Отримати відповідь у стрімінг режимі"""
        try:
            ep = self._get_endpoint()
            print(f"{Fore.LIGHTBLACK_EX}[DEBUG] Streaming to endpoint: {ep.get('url')}{Fore.RESET}")
            
            # Якщо це Groq endpoint, використовуємо офіційний SDK
            if _is_groq_endpoint(ep):
                print(f"{Fore.LIGHTBLACK_EX}[DEBUG] Using Groq SDK for streaming{Fore.RESET}")
                from .llm.groq_client import stream_groq_sdk
                full_text = ""
                print(f"{Fore.GREEN} [МАРК]: {Fore.WHITE}", end="", flush=True)
                
                def callback(chunk):
                    nonlocal full_text
                    print(chunk, end="", flush=True)
                    full_text += chunk
                
                if stream_groq_sdk(ep, messages, callback):
                    print()  # Новий рядок після стрімінгу
                    return full_text
                else:
                    print()
                    return "❌ Помилка стрімінгу Groq"
            
            # Стандартний OpenAI-compatible стрімінг
            headers = {"Content-Type": "application/json"}
            if ep["api_key"]:
                headers["Authorization"] = f"Bearer {ep['api_key']}"
            response = requests.post(
                ep["url"],
                headers=headers,
                json={
                    "model": ep["model"],
                    "messages": messages,
                    "temperature": ep["temperature"],
                    "max_tokens": ep.get("max_tokens", 8000),
                    "stream": True
                },
                stream=True,
                timeout=ep["timeout"]
            )
            
            full_text = ""
            print(f"{Fore.GREEN} [МАРК]: {Fore.WHITE}", end="", flush=True)
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            json_data = json.loads(data)
                            # Логування для дебагу (тільки перші кілька chunk)
                            if not full_text:
                                print(f"{Fore.LIGHTBLACK_EX}[DEBUG] First SSE chunk: {str(json_data)[:200]}")
                            delta = json_data['choices'][0]['delta']
                            if 'content' in delta:
                                content = delta['content']
                                print(content, end="", flush=True)
                                full_text += content
                        except Exception as e:
                            print(f"{Fore.LIGHTBLACK_EX}[DEBUG] SSE parse error: {e}, line: {line[:100]}")
                            pass
            
            print()  # Новий рядок після стрімінгу
            return full_text
            
        except Exception as e:
            return f"❌ Помилка стрімінгу: {str(e)}"

    def stream_response_with_callback(self, messages, callback):
        """Стрімить відповідь і викликає callback(chunk_text) для кожного фрагмента з fallback."""
        print(f"[DEBUG] stream_response_with_callback called")

        # Отримуємо всі enabled endpoints в порядку цифрового role
        from .core_settings import get_setting
        endpoints = get_setting("LLM_ENDPOINTS", [])

        # Сортуємо endpoints за цифровим role (1, 2, 3, ...)
        def get_role_order(role):
            try:
                return int(role) if role else 999
            except (ValueError, TypeError):
                # Для сумісності зі старими текстовими role
                role_map = {"primary": 1, "secondary": 2, "fallback": 3, "alternative": 4}
                return role_map.get(role, 999)

        enabled_endpoints = [ep for ep in endpoints if ep.get("enabled") and ep.get("model") and ep.get("url")]
        enabled_endpoints.sort(key=lambda ep: get_role_order(ep.get("role")))

        last_error = None

        for ep in enabled_endpoints:
            try:
                from .llm.endpoint_client import _normalize_endpoint
                endpoint = _normalize_endpoint(ep)
                role = ep.get("role", "unknown")
                name = ep.get("name", "LLM")

                print(f"[DEBUG] Endpoint: {endpoint.get('url')} ({name}, порядок {role})")
                print(f"{Fore.LIGHTBLACK_EX}[DEBUG] Streaming with callback to endpoint: {endpoint.get('url')}{Fore.RESET}")

                # Groq підтримує OpenAI-compatible API - використовуємо стандартний стрімінг
                headers = {"Content-Type": "application/json"}
                if endpoint["api_key"]:
                    headers["Authorization"] = f"Bearer {endpoint['api_key']}"

                print(f"[DEBUG] Sending request with {len(messages)} messages")

                response = requests.post(
                    endpoint["url"],
                    headers=headers,
                    json={
                        "model": endpoint["model"],
                        "messages": messages,
                        "temperature": endpoint["temperature"],
                        "max_tokens": endpoint.get("max_tokens", 8000),
                        "stream": True
                    },
                    stream=True,
                    timeout=endpoint["timeout"]
                )

                print(f"[DEBUG] Response status: {response.status_code}")

                if response.status_code != 200:
                    print(f"[DEBUG] Response error: {response.text[:500]}")
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    print(f"{Fore.YELLOW}⚠️ {name} ({role}) не вдалося: {last_error}")
                    continue

                chunk_count = 0
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                print(f"[DEBUG] Stream DONE, total chunks: {chunk_count}")
                                return  # Успішно завершено
                            try:
                                json_data = json.loads(data)
                                delta = json_data['choices'][0]['delta']
                                if 'content' in delta:
                                    chunk_count += 1
                                    callback(delta['content'])
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass

                return  # Успішно завершено

            except Exception as e:
                last_error = str(e)
                print(f"{Fore.YELLOW}⚠️ Помилка при стрімінгу {ep.get('name', 'LLM')}: {e}")

        # Усі спроби провалились - викликаємо callback з помилкою
        error_msg = last_error if last_error else "Немає налаштованих LLM endpoints"
        callback(f"❌ Помилка стрімінгу: {error_msg}")
        return

def init():
    """Ініціалізація модуля"""
    pass