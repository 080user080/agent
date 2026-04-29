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
        """Стрімить відповідь і викликає callback(chunk_text) для кожного фрагмента."""
        print(f"[DEBUG] stream_response_with_callback called")
        try:
            ep = self._get_endpoint()
            print(f"[DEBUG] Endpoint: {ep.get('url')}")
            print(f"{Fore.LIGHTBLACK_EX}[DEBUG] Streaming with callback to endpoint: {ep.get('url')}{Fore.RESET}")
            
            # Groq підтримує OpenAI-compatible API - використовуємо стандартний стрімінг
            headers = {"Content-Type": "application/json"}
            if ep["api_key"]:
                headers["Authorization"] = f"Bearer {ep['api_key']}"
            
            print(f"[DEBUG] Sending request with {len(messages)} messages")
            
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
            
            print(f"[DEBUG] Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[DEBUG] Response error: {response.text[:500]}")
                raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
            
            chunk_count = 0
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            print(f"[DEBUG] Stream DONE, total chunks: {chunk_count}")
                            break
                        try:
                            json_data = json.loads(data)
                            delta = json_data['choices'][0]['delta']
                            if 'content' in delta:
                                chunk_count += 1
                                callback(delta['content'])
                        except Exception as e:
                            print(f"[DEBUG] Parse error: {e}, line: {line[:100]}")
                            pass
            
            print(f"[DEBUG] Streaming completed, chunks: {chunk_count}")
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка стрімінгу: {e}")
            raise

def init():
    """Ініціалізація модуля"""
    pass