# functions/aaa_system.py
"""Системні команди асистента (очищення кешу, діагностика тощо)"""
import os
import shutil
from colorama import Fore
from .core_tool_runtime import make_tool_result

def llm_function(name, description, parameters):
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

@llm_function(
    name="clear_cache",
    description="Очистити кеш асистента (TTS аудіо, STT тимчасові файли, LLM сесії)",
    parameters={}
)
def clear_cache():
    """Очистити кеш асистента."""
    try:
        cleared = []
        errors = []

        # 1. TTS кеш
        from .config import TTS_CACHE_DIR
        if os.path.exists(TTS_CACHE_DIR):
            try:
                count = len([f for f in os.listdir(TTS_CACHE_DIR) if f.endswith('.wav')])
                shutil.rmtree(TTS_CACHE_DIR)
                os.makedirs(TTS_CACHE_DIR, exist_ok=True)
                cleared.append(f"TTS аудіо ({count} файлів)")
            except Exception as e:
                errors.append(f"TTS кеш: {e}")

        # 2. STT тимчасові файли (якщо є)
        stt_temp = "temp_stt"
        if os.path.exists(stt_temp):
            try:
                count = len(os.listdir(stt_temp))
                shutil.rmtree(stt_temp)
                cleared.append(f"STT тимчасові ({count} файлів)")
            except Exception as e:
                errors.append(f"STT temp: {e}")

        # 3. LLM сесійні файли (якщо є)
        if os.path.exists("agent_memory.json"):
            try:
                # Резервна копія
                shutil.copy("agent_memory.json", "agent_memory_backup.json")
                cleared.append("LLM сесії (збережено backup)")
            except Exception as e:
                errors.append(f"LLM memory backup: {e}")

        # 4. Кеш команд (cache_data.json)
        import json
        cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_data.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    prev = json.load(f) or {}
                count = len(prev)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False)
                cleared.append(f"Кеш команд ({count} записів)")
            except Exception as e:
                errors.append(f"cache_data.json: {e}")

        # 5. Логи аудіо (якщо є)
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            try:
                count = len([f for f in os.listdir(logs_dir) if f.endswith('.jsonl')])
                # Не видаляємо audit.jsonl - це безпека
                for f in os.listdir(logs_dir):
                    if f.endswith('.jsonl') and f != 'audit.jsonl':
                        os.remove(os.path.join(logs_dir, f))
                cleared.append(f"Логи аудіо (крім audit.jsonl)")
            except Exception as e:
                errors.append(f"Logs cleanup: {e}")

        summary = "✅ Кеш очищено:"
        if cleared:
            summary += " " + ", ".join(cleared)
        if errors:
            summary += f" ⚠️ Помилки: {', '.join(errors)}"

        print(f"{Fore.GREEN}{summary}{Fore.RESET}")
        return make_tool_result(True, summary)

    except Exception as e:
        print(f"{Fore.RED}❌ Помилка очищення кешу: {e}{Fore.RESET}")
        return make_tool_result(False, f"❌ Помилка очищення кешу: {e}", error=str(e), retryable=True)
