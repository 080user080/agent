import os
import yaml

CONFIG_FILE = "config.yaml"

DEFAULT_CONFIG = {
    "cdp_port": 9222,
    "chrome_executable_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "chrome_launch_timeout": 45,
    "connect_via_cdp": True,
    "gemini_url": "https://gemini.google.com/",
    "hotkey_new_chat": "ctrl_shift_o",
    "input_folder": "d:\\Python\\TEXT\\translation\\KOD_pereclad\\0",
    "log_formats": ["txt", "json"],
    "manual_tag": "_check",
    "max_retries": 2,
    "merged_filename": "merged_UKR.txt",
    "numeric_prefix_regex": "^\\d+",
    "on_bad_response": "mark_for_manual",
    "on_missing_copy_button": "retry",
    "output_folder": "output",
    "page_load_timeout": 30,
    "response_timeout": 18,
    "template_message": (
        "Зробити адаптивний переклад максимально точний. У відповіді тільки перекладений текст.\n"
        "Відповідь без жодних твоїх питань, побажань чи вставок чи дублювання моїх інструкції.\n"
        "Використовувати лише подвійні прямі лапки \"\". Не використовувати лапки-ялинки «» і виділення жирним шрифтом **.\n"
    ),
    "use_dom_method": [
        "copy_button",
        "js_full",
        "clipboard_via_js",
        "keyboard_copy"
    ],
    "use_numeric_prefix": True,
    "chrome_user_data_dir": "C:\\Temp\\chrome_debug_profile",
    "auto_launch_chrome": True
}

def create_default_config():
    """Створює config.yaml ТІЛЬКИ якщо його немає."""
    if os.path.exists(CONFIG_FILE):
        print("✔ config.yaml вже існує — не переписую.")
        return

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print("✅ Створено новий config.yaml")

if __name__ == "__main__":
    create_default_config()