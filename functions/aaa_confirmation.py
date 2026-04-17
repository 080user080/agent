# functions/aaa_confirmation.py
"""Система підтвердження дій"""
import time
import threading
from colorama import Fore
from .core_tool_runtime import make_tool_result
from .core_settings import get_settings

# Глобальна змінна для GUI
_gui_instance = None

def set_gui_instance(gui):
    """Встановити екземпляр GUI"""
    global _gui_instance
    _gui_instance = gui

def llm_function(name, description, parameters):
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

@llm_function(
    name="confirm_action",
    description="Запитати підтвердження дії у користувача",
    parameters={
        "action": "Дія яку потрібно підтвердити",
        "question": "Питання для користувача"
    }
)
def confirm_action(action, question):
    """Система підтвердження через GUI з підтримкою 'Автоматично'."""
    try:
        settings = get_settings()

        # --- Глобальне автопідтвердження ---
        if settings.is_auto_approve_all():
            print(f"{Fore.GREEN}✅ Автопідтвердження для дії: {action}{Fore.RESET}")
            return make_tool_result(
                True,
                f"✅ Дію '{action}' підтверджено автоматично (auto_approve_all).",
                data={"status": "auto_confirmed", "action": action, "confirmed": True},
            )

        global _gui_instance
        if not _gui_instance:
            # Якщо GUI немає, використовуємо консоль
            print(f"{Fore.YELLOW}⚠️  {question}")
            print(f"{Fore.YELLOW}   💡 Скажіть 'так' або 'ні' (10 секунд)...")

            # Імітуємо очікування
            time.sleep(10)
            return make_tool_result(
                False,
                f"⏰ Підтвердження не отримано для дії: {action}",
                data={"status": "timeout", "action": action},
                needs_confirmation=True,
            )

        # Створюємо подію для GUI - відповідь може бути:
        #   True  — ТАК (один раз)
        #   False — НІ
        #   "auto" — АВТОМАТИЧНО (увімкнути auto_approve_all і підтвердити)
        result = {"response": None}
        event = threading.Event()

        def callback(response):
            result["response"] = response
            event.set()

        # Показуємо підтвердження в GUI
        _gui_instance.queue_message('show_confirmation', (question, callback))

        # Чекаємо відповіді
        event.wait(timeout=30)

        response = result["response"]
        if response is None:
            return make_tool_result(
                False,
                f"⏰ Час підтвердження вийшов для дії: {action}",
                data={"status": "timeout", "action": action},
                needs_confirmation=True,
            )

        # Обробка "auto" - увімкнути глобальне автопідтвердження
        if response == "auto":
            settings.enable_auto_approve_all()
            print(f"{Fore.GREEN}✅ Увімкнено автопідтвердження всіх дій (до перезапуску або вимкнення){Fore.RESET}")
            return make_tool_result(
                True,
                "✅ Дію підтверджено. Автопідтвердження увімкнено для наступних дій.",
                data={
                    "status": "auto_enabled",
                    "action": action,
                    "confirmed": True,
                    "auto_approve_all": True,
                },
            )

        confirmed = bool(response)
        return make_tool_result(
            confirmed,
            "✅ Дію підтверджено." if confirmed else "❌ Дію скасовано користувачем.",
            data={
                "status": "confirmed" if confirmed else "cancelled",
                "action": action,
                "confirmed": confirmed,
            },
            error=None if confirmed else "cancelled",
            needs_confirmation=not confirmed,
        )

    except Exception as e:
        return make_tool_result(False, f"❌ Помилка підтвердження: {str(e)}", error=str(e), retryable=True)
