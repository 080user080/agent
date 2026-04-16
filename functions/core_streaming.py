import requests
import json
from colorama import Fore

class StreamingHandler:
    """Обробник стрімінгу відповідей від LLM"""
    
    def __init__(self, api_url):
        self.api_url = api_url
    
    def stream_response(self, messages):
        """Отримати відповідь у стрімінг режимі"""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 8000,
                    "stream": True
                },
                stream=True,
                timeout=60
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
                            delta = json_data['choices'][0]['delta']
                            if 'content' in delta:
                                content = delta['content']
                                print(content, end="", flush=True)
                                full_text += content
                        except:
                            pass
            
            print()  # Новий рядок після стрімінгу
            return full_text
            
        except Exception as e:
            return f"❌ Помилка стрімінгу: {str(e)}"

    def stream_response_with_callback(self, messages, callback):
        """Стрімить відповідь і викликає callback(chunk_text) для кожного фрагмента."""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 8000,
                    "stream": True
                },
                stream=True,
                timeout=60
            )
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            json_data = json.loads(data)
                            delta = json_data['choices'][0]['delta']
                            if 'content' in delta:
                                callback(delta['content'])
                        except:
                            pass
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка стрімінгу: {e}")
            raise

def init():
    """Ініціалізація модуля"""
    pass