import webbrowser

from .core_tool_runtime import make_tool_result


def llm_function(name, description, parameters):
    """Декоратор для реєстрації функцій"""
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator


@llm_function(
    name="open_browser",
    description="відкрити сайт у браузері",
    parameters={
        "url": "адреса сайту (наприклад: https://google.com або просто google.com)"
    }
)
def open_browser(url):
    """Відкрити URL у браузері"""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        webbrowser.open(url)
        return make_tool_result(True, f"✅ Відкрито: {url}", data={"url": url})
    except Exception as e:
        return make_tool_result(False, f"❌ Помилка відкриття браузера: {str(e)}", error=str(e), retryable=True)
