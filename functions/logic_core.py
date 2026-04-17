# functions/logic_core.py
"""Ядро асистента - реєстр функцій та VoiceAssistant"""
import os
import sys
import importlib
import inspect
from pathlib import Path
import time
from colorama import Fore, Back, Style
from .core_tool_runtime import get_tool_policy, get_tool_risk, normalize_tool_result, get_audit_log

# Глобальне посилання на реєстр, щоб aaa_architect міг його оновити
global_registry = None

class FunctionRegistry:
    """Реєстр функцій з автоматичним завантаженням"""
    
    def __init__(self):
        global global_registry
        self.functions = {}
        self.core_modules = {}
        self.last_tool_result = None
        self.load_all_modules()
        global_registry = self  # Зберігаємо посилання на себе
    
    def refresh(self):
        """Перезавантажити всі функції без перезапуску програми"""
        print(f"{Fore.CYAN}♻️  Оновлення реєстру навичок...")
        
        # Очистити поточні функції
        self.functions.clear()
        
        # Примусово очистити кеш модулів aaa_*, щоб Python перечитав файли
        keys_to_remove = [k for k in sys.modules if k.startswith('functions.aaa_')]
        for k in keys_to_remove:
            del sys.modules[k]
            
        # Завантажити заново
        self.load_all_modules()
        print(f"{Fore.GREEN}✅ Реєстр оновлено. Доступно навичок: {len(self.functions)}")

    def load_all_modules(self):
        """Автоматично завантажити всі модулі з папки functions"""
        functions_dir = Path(__file__).parent
        
        if not functions_dir.exists():
            print(f"{Fore.YELLOW}⚠️  Папка functions не знайдена")
            return
        
        # Спочатку завантажити CORE модулі (core_*.py)
        print(f"{Fore.CYAN}📦 Завантаження core модулів...")
        core_files = sorted(functions_dir.glob("core_*.py"))
        
        for file_path in core_files:
            module_name = file_path.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                self.core_modules[module_name] = module
                print(f"{Fore.MAGENTA}⚡ Core: {Fore.CYAN}{module_name}")
                
                if hasattr(module, 'init'):
                    module.init()
                    
            except Exception as e:
                print(f"{Fore.RED}❌ Помилка завантаження {module_name}: {e}")
        
        # Завантажити звичайні функції (aaa_*.py)
        print(f"\n{Fore.CYAN}📦 Завантаження функцій...")
        for file_path in sorted(functions_dir.glob("aaa_*.py")):
            module_name = file_path.stem
            try:
                # Важливо: використовуємо ім'я пакета functions.aaa_... для коректного імпорту
                spec = importlib.util.spec_from_file_location(f"functions.{module_name}", file_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"functions.{module_name}"] = module # Реєструємо в sys.modules
                spec.loader.exec_module(module)
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) and hasattr(obj, '_is_llm_function'):
                        func_info = {
                            'function': obj,
                            'name': obj._function_name,
                            'description': obj._description,
                            'parameters': obj._parameters
                        }
                        self.functions[obj._function_name] = func_info
                        print(f"{Fore.GREEN}✅ {Fore.CYAN}{obj._function_name}")
            
            except Exception as e:
                print(f"{Fore.RED}❌ Помилка завантаження {module_name}: {e}")
    
    def get_core_module(self, name):
        """Отримати core модуль за назвою"""
        for module_name, module in self.core_modules.items():
            if name in module_name:
                return module
        return None

    def get_tool_policy(self, action):
        """Отримати політику інструмента."""
        return get_tool_policy(action)

    def get_tool_risk(self, action):
        """Отримати risk-level інструмента."""
        return get_tool_risk(action)
    
    def get_system_prompt(self, mode: str = None):
        """Згенерувати system prompt залежно від режиму ('voice' або 'coding')."""
        from .config import AGENT_MODE
        active_mode = mode or AGENT_MODE
        if active_mode == "coding":
            return self.get_coding_system_prompt()
        return self._get_voice_system_prompt()

    def get_coding_system_prompt(self):
        """System prompt для режиму coding agent.

        Цикл: аналіз задачі -> пошук у коді -> читання -> редагування -> верифікація.
        """
        from .config import ASSISTANT_NAME

        prompt = f"""ТИ: Агент-розробник {ASSISTANT_NAME} для роботи з кодом.

МОВА: Українська для спілкування, англійська для коментарів у коді.
РЕЖИМ: Coding Agent - фокус на якісному виконанні задач із кодом.

ЦИКЛ РОБОТИ АГЕНТА:
1. **Аналіз** - розбий задачу на кроки
2. **Пошук** - `search_in_code` / `list_directory` для знайомства з проєктом
3. **Читання** - `read_code_file` перед будь-яким редагуванням
4. **Редагування** - `edit_file` або `create_file`
5. **Верифікація** - `execute_python` або `debug_python_code` для перевірки
6. **Git** - `git_status` / `git_diff` після змін

КРИТИЧНІ ПРАВИЛА:
1. ЗАВЖДИ читай файл перед редагуванням (`read_code_file`)
2. НЕ пиши код "навмання" - спочатку подивись, що є в проєкті
3. Перевіряй результат `execute_python` після змін
4. Якщо помилка - використай `debug_python_code`
5. Поверни JSON з action та параметрами
6. На складні задачі — використовуй planner (багатокроковий план)

ДОСТУПНІ CODE-TOOLS:
- `read_code_file(filepath, start_line, max_lines)` — читання файлу
- `search_in_code(pattern, directory, file_pattern)` — regex-пошук
- `list_directory(directory)` — вміст директорії
- `edit_file(filepath, new_content)` — редагування з бекапом
- `create_file(filename, content)` — створення файлу
- `execute_python(code)` — запуск Python у пісочниці
- `debug_python_code(code)` — автовиправлення помилок
- `git_status(directory)` — статус git-репозиторію
- `git_diff(directory, staged)` — показати зміни

ВЗІРЦІ (КОРОТКІ ПРИКЛАДИ):
- "Знайди TODO в коді" → {{"action":"search_in_code","pattern":"TODO","directory":"."}}
- "Покажи git зміни" → {{"action":"git_diff","directory":"."}}
- "Прочитай файл config.py" → {{"action":"read_code_file","filepath":"config.py"}}

ЗАБОРОНЕНІ ФРАЗИ: "Звичайно", "Я допоможу", "Дозвольте", "З радістю".
ДОЗВОЛЕНІ: "Готово", "Виконую", "Знайдено", "Помилка у рядку X".

ЗАВЖДИ ПОВЕРТАЙ JSON З action!
"""
        if self.functions:
            prompt += "\n\nДОСТУПНІ ФУНКЦІЇ:\n"
            for func_name, func_info in sorted(self.functions.items()):
                prompt += f"\n🔧 {func_info['name']}: {func_info['description']}\n"
                if func_info['parameters']:
                    for pname, pdesc in func_info['parameters'].items():
                        prompt += f"   • {pname}: {pdesc}\n"

        return prompt

    def _get_voice_system_prompt(self):
        """Звичайний Voice-First system prompt."""
        from .config import ASSISTANT_NAME, ASSISTANT_MODES, ACTIVE_MODE
        
        mode = ASSISTANT_MODES[ACTIVE_MODE]
        
        prompt = f"""ТИ: Голосовий асистент {ASSISTANT_NAME} для написання коду

МОВА: Українська, розмовна
СТИЛЬ: {mode['style']}
РЕЖИМ: {ACTIVE_MODE} (максимум {mode['max_words']} слів, {mode['max_sentences']} речення)

КРИТИЧНІ ПРАВИЛА:
1. ВИКОНАЙ ДІЮ, не пояснюй її
2. Відповідь = результат, не коментар
3. Повертай JSON з action та параметрами
4. Якщо помилка - скажи "Помилка: [причина]"
5. Якщо не зрозумів - скажи "Не зрозумів. Повторіть?"

🔥 ПРИКЛАДИ КОМАНД (ДУЖЕ ВАЖЛИВО):

**Виконання коду:**
Користувач: "виконай код: print('hello')"
Ти: {{"action":"execute_python","code":"print('hello')"}}

Користувач: "виконай код: result = 2 + 2; print(result)"
Ти: {{"action":"execute_python","code":"result = 2 + 2\\nprint(result)"}}

Користувач: "виконай код: for i in range(5): print(i)"
Ти: {{"action":"execute_python","code":"for i in range(5):\\n    print(i)"}}

**Виправлення коду:**
Користувач: "виправ код: prin('test')"
Ти: {{"action":"debug_python_code","code":"prin('test')"}}

**Список скриптів:**
Користувач: "покажи скрипти в пісочниці"
Ти: {{"action":"list_sandbox_scripts"}}

**Відкриття програм:**
Користувач: "відкрий блокнот"
Ти: {{"action":"open_program","program_name":"notepad"}}

ЗАБОРОНЕНІ ФРАЗИ:
"Звичайно", "Я допоможу", "Дозвольте", "З радістю", 
"Ось ваш код", "Я може допомогти", "Один момент"

ДОЗВОЛЕНІ ФРАЗИ:
"Готово", "Виконано", "Помилка", "Не зрозумів", "Слухаю"
"""
        
        if not self.functions:
            return prompt + "\n\n⚠️ Функції недоступні."
        
        prompt += "\n\nДОСТУПНІ ФУНКЦІЇ:\n"
        
        for func_name, func_info in self.functions.items():
            prompt += f"\n🔧 {func_info['name']}\n"
            prompt += f"   Опис: {func_info['description']}\n"
            
            if func_info['parameters']:
                prompt += "   Параметри:\n"
                for param_name, param_desc in func_info['parameters'].items():
                    prompt += f"   • {param_name}: {param_desc}\n"
        
        prompt += """

ПРАВИЛА ВИБОРУ ФУНКЦІЇ:
1. "виконай код" → execute_python
2. "виправ код" → debug_python_code
3. "покажи скрипти" → list_sandbox_scripts
4. "відкрий", "закрий" → open_program/close_program

ЗАВЖДИ ПОВЕРТАЙ JSON З action!
"""
        
        return prompt
    
    def execute_function(self, action, params):
        """Виконати функцію за назвою з аудитом"""
        audit = get_audit_log()
        risk = get_tool_risk(action)

        if action not in self.functions:
            result = normalize_tool_result(f"{Fore.RED}❌ Функція {action} не знайдена")
            self.last_tool_result = result
            audit.log(action, params, result, risk)
            return result["message"]

        try:
            func = self.functions[action]['function']
            raw_result = func(**params)
            result = normalize_tool_result(raw_result)
            result["action"] = action
            result["params"] = params
            self.last_tool_result = result
            audit.log(action, params, result, risk)
            return result["message"]
        except Exception as e:
            result = normalize_tool_result(f"{Fore.RED}❌ Помилка виконання {action}: {str(e)}")
            result["action"] = action
            result["params"] = params
            self.last_tool_result = result
            audit.log(action, params, result, risk)
            return result["message"]
