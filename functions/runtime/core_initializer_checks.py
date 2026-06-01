import os
import requests
import subprocess
import time
from colorama import Fore

def get_primary_endpoint():
    """Отримати primary endpoint з налаштувань."""
    try:
        from functions.runtime.core_settings import get_setting
        endpoints = get_setting("LLM_ENDPOINTS", [])
        # Шукаємо endpoint з role="1" або "primary"
        for ep in endpoints:
            role = ep.get("role")
            if role == "1" or role == "primary":
                if (ep.get("enabled") and ep.get("model") and ep.get("url")):
                    return ep
        # Якщо не знайдено, шукаємо enabled endpoint з найменшим цифровим role
        enabled_endpoints = [ep for ep in endpoints if ep.get("enabled") and ep.get("model") and ep.get("url")]
        if enabled_endpoints:
            def get_role_order(ep):
                try:
                    return int(ep.get("role", 999)) if ep.get("role") else 999
                except (ValueError, TypeError):
                    role_map = {"primary": 1, "secondary": 2, "fallback": 3, "alternative": 4}
                    return role_map.get(ep.get("role"), 999)
            enabled_endpoints.sort(key=get_role_order)
            return enabled_endpoints[0]
    except Exception as e:
        print(f"{Fore.RED}⚠️  Помилка отримання endpoint: {e}")
    return None

def is_model_ready(base_url, model_name):
    """Перевірити, чи модель відповідає на запити."""
    try:
        test_response = requests.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
                "temperature": 0
            },
            timeout=5
        )
        if test_response.status_code == 200:
            return True
        error_text = test_response.text.lower()
        return not ("no model loaded" in error_text or "model not found" in error_text)
    except Exception:
        return False

def check_lm_studio_readiness():
    """Перевірка та автозавантаження моделі в LM Studio."""
    LMS_PATH = os.path.expanduser(r"~\.lmstudio\bin\lms.exe")
    BASE_URL = "http://localhost:1234"

    print(f"{Fore.CYAN}🔌 Перевірка primary LLM endpoint...")

    primary_ep = get_primary_endpoint()

    if not primary_ep:
        print(f"{Fore.YELLOW}⚠️  Primary модель не налаштована")
        print(f"{Fore.YELLOW}💡 Налаштуйте модель в GUI: Налаштування → LLM Моделі")
        return False

    DESIRED_MODEL = primary_ep.get("model")
    PRIMARY_URL = primary_ep.get("url", "")
    
    print(f"{Fore.CYAN}   Primary модель: {DESIRED_MODEL}")
    print(f"{Fore.CYAN}   URL: {PRIMARY_URL}")

    if "localhost" not in PRIMARY_URL and "127.0.0.1" not in PRIMARY_URL:
        print(f"{Fore.GREEN}✅ Віддалений API (Gemini/OpenAI/etc) — LM Studio не потрібен")
        return True

    try:
        response = requests.get(f"{BASE_URL}/v1/models", timeout=2)
        if response.status_code == 200:
            data = response.json()
            models = [m['id'] for m in data.get('data', [])]
            if DESIRED_MODEL in models:
                print(f"{Fore.CYAN}   Модель є в списку, перевіряю чи готова до роботи...")
                if is_model_ready(BASE_URL, DESIRED_MODEL):
                    print(f"{Fore.GREEN}✅ Модель завантажена і готова: {DESIRED_MODEL}")
                    return True
                else:
                    print(f"{Fore.YELLOW}⚠️  Модель є в списку, але не завантажена в пам'ять")
    except Exception as e:
        print(f"{Fore.YELLOW}   Не вдалося перевірити список моделей: {e}")

    print(f"{Fore.CYAN}🤖 Завантаження {DESIRED_MODEL}...")

    try:
        process = subprocess.Popen(
            [LMS_PATH, "load", DESIRED_MODEL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )

        print(f"{Fore.CYAN}⏳ Очікування завантаження (до 30с)...")

        for i in range(30):
            time.sleep(1)
            try:
                response = requests.get(f"{BASE_URL}/v1/models", timeout=1)
                if response.status_code == 200:
                    data = response.json()
                    models = [m['id'] for m in data.get('data', [])]
                    if DESIRED_MODEL in models:
                        if is_model_ready(BASE_URL, DESIRED_MODEL):
                            print(f"{Fore.GREEN}✅ Модель завантажена і готова за {i+1}с!")
                            return True
            except:
                pass

            if i % 5 == 0 and i > 0:
                print(f"{Fore.LIGHTBLACK_EX}   {i}с... очікую завантаження в пам'ять")

        if is_model_ready(BASE_URL, DESIRED_MODEL):
            print(f"{Fore.GREEN}✅ Модель завантажена і готова!")
            return True
        else:
            print(f"{Fore.YELLOW}⚠️  Модель завантажена в список, але не відповідає на запити")
            return False

    except Exception as e:
        print(f"{Fore.RED}❌ Помилка автозавантаження: {e}")
        print(f"{Fore.YELLOW}💡 Завантажте модель вручну в LM Studio")
        return False
