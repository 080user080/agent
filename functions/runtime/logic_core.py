# runtime/logic_core.py
"""Ядро асистента - реєстр функцій та VoiceAssistant"""
import os
import sys
import importlib
import inspect
from pathlib import Path
import time
from colorama import Fore, Back, Style
from functions.runtime.core_tool_runtime import get_tool_policy, get_tool_risk, normalize_tool_result, get_audit_log

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
        # Визначаємо корінь проєкту (папка, де лежить main.py)
        project_root = Path(__file__).resolve().parent.parent.parent
        functions_dir = project_root / 'functions'
        
        if not functions_dir.exists():
            print(f"{Fore.YELLOW}⚠️  Папка functions не знайдена")
            return
        
        # Захист від дублікатів: відстежуємо завантажені імена модулів
        _loaded_modules = set()

        # Допоміжна функція для побудови dotted module name
        # Наприклад: functions/runtime/core_cache.py → "functions.runtime.core_cache"
        #            functions/planning/core_planner.py → "functions.planning.core_planner"
        def _module_full_name(file_path: Path) -> str:
            rel_path = file_path.relative_to(functions_dir)
            parts = list(rel_path.parts)
            # Забираємо .py з останньої частини
            parts[-1] = parts[-1].replace(".py", "")
            return "functions." + ".".join(parts)

        # Спочатку завантажити CORE модулі (core_*.py)
        print(f"{Fore.CYAN}📦 Завантаження core модулів...")
        core_files = sorted(functions_dir.rglob("core_*.py"))
        
        for file_path in core_files:
            module_name = file_path.stem
            full_name = _module_full_name(file_path)
            
            # Пропускаємо, якщо модуль з таким іменем вже завантажено
            if full_name in _loaded_modules or full_name in sys.modules:
                print(f"{Fore.YELLOW}⚠️  {module_name} ({file_path.relative_to(functions_dir)}) — пропущено (дублікат)")
                continue
            _loaded_modules.add(full_name)
            
            try:
                # Якщо модуль уже завантажений через `from functions.xxx import ...`
                # (наприклад core_settings з run_assistant.py), використовуємо його.
                if full_name in sys.modules:
                    module = sys.modules[full_name]
                else:
                    # Важливо: ім'я пакета functions.xxx.yyy — інакше relative import (`from .. import config`) падає
                    spec = importlib.util.spec_from_file_location(full_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[full_name] = module
                    spec.loader.exec_module(module)

                self.core_modules[module_name] = module
                print(f"{Fore.MAGENTA}⚡ Core: {Fore.CYAN}{module_name}")

                if hasattr(module, 'init'):
                    module.init()

            except Exception as e:
                print(f"{Fore.RED}❌ Помилка завантаження {module_name}: {e}")
        
        # Завантажити звичайні функції (aaa_*.py)
        print(f"\n{Fore.CYAN}📦 Завантаження функцій...")
        for file_path in sorted(functions_dir.rglob("aaa_*.py")):
            module_name = file_path.stem
            full_name = _module_full_name(file_path)
            
            # Пропускаємо дублікати
            if full_name in _loaded_modules:
                print(f"{Fore.YELLOW}⚠️  {module_name} ({file_path.relative_to(functions_dir)}) — пропущено (дублікат)")
                continue
            _loaded_modules.add(full_name)
            
            try:
                # Використовуємо правильне dotted module name
                spec = importlib.util.spec_from_file_location(full_name, file_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[full_name] = module
                spec.loader.exec_module(module)
                
                for _name, obj in inspect.getmembers(module):
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

        # Завантажити GUI Automation tools (tools_*.py) — функції без декораторів, для прямого виклику
        print(f"\n{Fore.CYAN}📦 Завантаження GUI Automation tools...")
        for file_path in sorted(functions_dir.rglob("tools_*.py")):
            module_name = file_path.stem
            full_name = _module_full_name(file_path)
            
            # Пропускаємо дублікати
            if full_name in _loaded_modules:
                print(f"{Fore.YELLOW}⚠️  {module_name} ({file_path.relative_to(functions_dir)}) — пропущено (дублікат)")
                continue
            _loaded_modules.add(full_name)
            
            try:
                spec = importlib.util.spec_from_file_location(full_name, file_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[full_name] = module
                spec.loader.exec_module(module)

                # Реєструємо всі публічні функції (без підкреслення на початку)
                count = 0
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) and not name.startswith('_') and hasattr(module, name):
                        # Перевіряємо чи це функція з модуля (не імпортована)
                        if obj.__module__ == full_name:
                            self.functions[name] = {
                                'function': obj,
                                'name': name,
                                'description': obj.__doc__ or f"GUI tool: {name}",
                                'parameters': getattr(obj, '_parameters', {})
                            }
                            count += 1

                if count > 0:
                    print(f"{Fore.GREEN}✅ {Fore.CYAN}{module_name} ({count} функцій)")
                else:
                    print(f"{Fore.YELLOW}⚠️  {module_name} (немає публічних функцій)")

            except Exception as e:
                print(f"{Fore.RED}❌ Помилка завантаження {module_name}: {e}")

        # Завантажити skills модулі (skills/*.py)
        print(f"\n{Fore.CYAN}📦 Завантаження skills...")
        skills_dir = functions_dir / "skills"
        if skills_dir.exists():
            for file_path in sorted(skills_dir.glob("*.py")):
                if file_path.name == "__init__.py":
                    continue
                module_name = file_path.stem
                full_name = f"functions.skills.{module_name}"
                try:
                    if full_name in sys.modules:
                        module = sys.modules[full_name]
                    else:
                        spec = importlib.util.spec_from_file_location(full_name, file_path)
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[full_name] = module
                        spec.loader.exec_module(module)

                    # Реєструємо функції з декоратором _is_llm_function
                    count = 0
                    for _name, obj in inspect.getmembers(module):
                        if inspect.isfunction(obj) and hasattr(obj, '_is_llm_function'):
                            func_info = {
                                'function': obj,
                                'name': obj._function_name,
                                'description': obj._description,
                                'parameters': obj._parameters
                            }
                            self.functions[obj._function_name] = func_info
                            count += 1
                        elif inspect.isfunction(obj) and not _name.startswith('_') and hasattr(module, _name):
                            if obj.__module__ == full_name:
                                self.functions[_name] = {
                                    'function': obj,
                                    'name': _name,
                                    'description': obj.__doc__ or f"Skill: {_name}",
                                    'parameters': getattr(obj, '_parameters', {})
                                }
                                count += 1

                    if count > 0:
                        print(f"{Fore.GREEN}✅ {Fore.CYAN}skills/{module_name} ({count} функцій)")
                    else:
                        print(f"{Fore.YELLOW}⚠️  skills/{module_name} (немає публічних функцій)")

                except Exception as e:
                    print(f"{Fore.RED}❌ Помилка завантаження skills/{module_name}: {e}")
        else:
            print(f"{Fore.YELLOW}⚠️  Папка functions/skills не знайдена")

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
        from functions.config import AGENT_MODE
        active_mode = mode or AGENT_MODE
        if active_mode == "coding":
            return self.get_coding_system_prompt()
        return self._get_voice_system_prompt()

    def get_coding_system_prompt(self):
        """System prompt для режиму coding agent.

        Цикл: аналіз задачі -> пошук у коді -> читання -> редагування -> верифікація.
        """
        from functions.config import ASSISTANT_NAME

        base_prompt = """ТИ: Агент-розробник {ASSISTANT_NAME} для роботи з кодом.

МОВА: Українська для спілкування, англійська для коментарів у коді.
РЕЖИМ: Coding Agent - фокус на якісному виконанні задач із кодом.

	АЛГОРИТМ РОБОТИ З КОДОВОЮ БАЗОЮ (виконувати суворо по порядку):
	1. **ОРІЄНТАЦІЯ** — викликати `get_repo_map()` — зрозуміти структуру проєкту
	2. **ПОШУК** — визначити файли які стосуються задачі (за картою або `search_in_code`)
	3. **АНАЛІЗ ЗАЛЕЖНОСТЕЙ** — для кожного файлу який планую змінити:
	   викликати `get_file_dependents(filepath)`
	4. **ЧИТАННЯ** — прочитати тільки потрібні файли через `read_code_file`
	5. **ЗМІНА** — внести зміну (`edit_file` або `create_file`)
	6. **ОНОВЛЕННЯ ІНДЕКСУ** — викликати `update_repo_map(filepath)` для зміненого файлу
	7. **ПЕРЕВІРКА** — переконатись що залежні файли не зламані (`execute_python`)

	⚠️ КРИТИЧНІ ЗАБОРОНИ:
	1. НІКОЛИ не змінюй файл не перевіривши його залежності через `get_file_dependents`
	2. НІКОЛИ не читай весь проєкт файл за файлом — використовуй `get_repo_map`
	3. ЗАВЖДИ читай файл перед редагуванням (`read_code_file`)
	4. Перевіряй результат `execute_python` після змін
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

ДОСТУПНІ BROWSER-TOOLS:
- `open_browser(url)` — відкрити браузер (CDP)
- `browser_open_url(url)` — відкрити URL у браузері
- `browser_click_text(text)` — клікнути на текст на сторінці

ВЗІРЦІ (КОРОТКІ ПРИКЛАДИ):
- "Знайди TODO в коді" → {{"action":"search_in_code","pattern":"TODO","directory":"."}}
- "Покажи git зміни" → {{"action":"git_diff","directory":"."}}
- "Прочитай файл config.py" → {{"action":"read_code_file","filepath":"config.py"}}
- "відкрий браузер" → {{"action":"open_browser","url":"https://google.com"}}
- "Активуй вікно і напиши текст" → ДВА action підряд:
  {{"action":"activate_window_by_title","title":"Notepad"}}
  {{"action":"keyboard_type","text":"Привіт!"}}
- "Напиши Привіт у вікно windsurf" → ДВА action підряд:
  {{"action":"activate_window_by_title","title":"Windsurf"}}
  {{"action":"keyboard_type","text":"Привіт"}}
- "Введе команду Привіт у вікно WinSurf" → ДВА action підряд:
  {{"action":"activate_window_by_title","title":"Windsurf"}}
  {{"action":"keyboard_type","text":"Привіт"}}
- "Введи текст у вікно" → ДВА action підряд:
  {{"action":"activate_window_by_title","title":"[назва вікна]"}}
  {{"action":"keyboard_type","text":"[текст]"}}
- "Напиши слово у вікно" → ДВА action підряд:
  {{"action":"activate_window_by_title","title":"[назва вікна]"}}
  {{"action":"keyboard_type","text":"[слово]"}}

ВАЖЛИВО: Коли потрібно написати текст у вікно — ЗАВЖДИ повертай ДВА action: activate_window_by_title + keyboard_type.
НІКОЛИ не використовуй find_windsurf_window — це внутрішня функція.
Якщо команда не має прямого JSON action — поверни {{"response":"[пояснення чому немає прямої функції]"}}.

ЗАБОРОНЕНІ ФРАЗИ: "Звичайно", "Я допоможу", "Дозвольте", "З радістю".
ДОЗВОЛЕНІ: "Готово", "Виконую", "Знайдено", "Помилка у рядку X".

ФОРМАТ ВІДПОВІДІ (два варіанти):
A) Є конкретна технічна задача з кодом → {{"action":"назва","параметр":"значення"}}
B) Питання, привітання, незрозуміла команда, потрібне уточнення → {{"response":"текст"}}

АЛГОРИТМ ВИБОРУ:
1. Команда містить конкретну дію ("прочитай", "відкрий", "виконай", "знайди", "створи") → action
2. Команда коротка або соціальна ("привіт", "дякую", "як справи", "що робиш") → response  
3. Команда незрозуміла або неповна → response із уточнюючим питанням
4. Команда технічна але неоднозначна → response із питанням перед виконанням
"""

        prompt = base_prompt.format(ASSISTANT_NAME=ASSISTANT_NAME)
        # --- Repo Map: карта проєкту ---
        try:
            from functions.project_indexer import get_repo_map
            repo_map_text = get_repo_map()
        except Exception:
            repo_map_text = None

        if repo_map_text:
            # Груба оцінка токенів: ~4 символи на токен
            ESTIMATED_TOKENS = len(repo_map_text) // 4

            if ESTIMATED_TOKENS > 3000:
                # Стиснутий варіант: тільки список файлів + класи без методів
                condensed_lines = []
                for line in repo_map_text.split("\n"):
                    if not line.strip():
                        continue
                    # line = "path/to/file.py => Class.method(args); func(args)"
                    if " => " in line:
                        filepath, symbols = line.split(" => ", 1)
                        # Видаляємо сигнатури методів, залишаємо тільки назви класів
                        import re
                        symbols_clean = re.sub(r"\.\{[^}]+\}", "", symbols)
                        symbols_clean = re.sub(r"\([^)]*\)", "()", symbols_clean)
                        condensed_lines.append(f"{filepath} => {symbols_clean}")
                    else:
                        condensed_lines.append(line)
                repo_block = "\n".join(condensed_lines)
                prompt += (
                    f"\n\n📋 REPO MAP (condensed, {len(condensed_lines)} files):\n"
                    f"{repo_block}\n"
                )
            else:
                prompt += (
                    f"\n\n📋 REPO MAP (повна карта проєкту):\n"
                    f"{repo_map_text}\n"
                )

        if self.functions:
            prompt += "\n\nДОСТУПНІ ФУНКЦІЇ (перші 15):\n"
            MAX_FUNCTIONS_IN_PROMPT = 15
            count = 0
            for _func_name, func_info in sorted(self.functions.items()):
                if count >= MAX_FUNCTIONS_IN_PROMPT:
                    break
                prompt += f"\n🔧 {func_info['name']}: {func_info['description']}\n"
                if func_info['parameters']:
                    for pname, pdesc in func_info['parameters'].items():
                        prompt += f"   • {pname}: {pdesc}\n"
                count += 1
            if len(self.functions) > MAX_FUNCTIONS_IN_PROMPT:
                prompt += f"\n... та ще {len(self.functions) - MAX_FUNCTIONS_IN_PROMPT} функцій"

        return prompt

    def _get_voice_system_prompt(self):
        """Звичайний Voice-First system prompt."""
        from functions.config import ASSISTANT_NAME, ASSISTANT_MODES, ACTIVE_MODE

        mode = ASSISTANT_MODES[ACTIVE_MODE]

        prompt = f"""ТИ: {ASSISTANT_NAME}, асистент-кодер. Мова: українська.
РЕЖИМ: {ACTIVE_MODE} ({mode['max_words']} слів, {mode['max_sentences']} реч).

ПРАВИЛА ВІДПОВІДІ (ти сам вирішуєш — відповісти текстом чи виконати дію):
1. Привітання, соціальні фрази, питання → {{"response":"текст відповіді"}}
2. Прості дії (відкрити програму, написати текст, створити файл, виконати код) → {{"action":"назва_функції","параметр":"значення"}}
3. СКЛАДНІ задачі (багатокрокові, "створи веб-сайт", "досліди проект", "рефакторинг") → {{"action":"run_agent_loop","task":"опис задачі"}}

ПРИКЛАДИ:
- "привіт" → {{"response":"Привіт! Я {ASSISTANT_NAME}. Чим можу допомогти?"}}
- "дякую" → {{"response":"Будь ласка! Звертайтеся, якщо потрібна допомога."}}
- "що ти вмієш" → {{"response":"Можу виконувати команди, працювати з файлами, кодом, браузером."}}
- "виконай print('hi')" → {{"action":"execute_python","code":"print('hi')"}}
- "відкрий блокнот" → {{"action":"open_program","program_name":"notepad"}}
- "створи файл test.py" → {{"action":"create_file","filename":"test.py","content":"# test"}}
- "створи веб-сайт" → {{"action":"run_agent_loop","task":"створи веб-сайт з HTML, CSS, JS"}}
- "напиши функцію сортування" → {{"action":"run_agent_loop","task":"напиши функцію сортування на Python"}}

ВАЖЛИВО: Ти САМ вирішуєш що робити. Не питай дозволу. Якщо сумніваєшся — зроби.
"""
        
        if not self.functions:
            return prompt + "\n\n⚠️ Функції недоступні."
        
        # Скорочений список функцій (тільки назва + опис, без параметрів)
        # Обмежуємо кількість функцій для зменшення розміру промпта
        MAX_FUNCTIONS_IN_PROMPT = 15
        
        prompt += f"\n\nДОСТУПНІ ФУНКЦІЇ (перші {MAX_FUNCTIONS_IN_PROMPT}):\n"
        
        # Сортуємо: спочатку найважливіші (core + GUI automation)
        priority_funcs = [
            'execute_python', 'debug_python_code', 'open_program', 'close_program',
            'create_file', 'edit_file', 'list_directory',
            'mouse_click', 'keyboard_type', 'take_screenshot', 'ocr_screen',
            'click_text', 'list_windows', 'find_window_by_title', 'activate_window',
            'cdp_ensure_chrome', 'cdp_open_tab', 'cdp_switch_tab', 'cdp_type_text',
            'cdp_get_response', 'cdp_send_to_ai', 'cdp_list_tabs', 'cdp_get_page_text'
        ]
        
        # Додаємо priority функції першими
        added = set()
        for func_name in priority_funcs:
            if func_name in self.functions and len(added) < MAX_FUNCTIONS_IN_PROMPT:
                func_info = self.functions[func_name]
                prompt += f"• {func_info['name']}: {func_info['description'][:50]}...\n"
                added.add(func_name)
        
        # Додаємо решту функцій до ліміту
        for func_name, func_info in self.functions.items():
            if func_name not in added and len(added) < MAX_FUNCTIONS_IN_PROMPT:
                prompt += f"• {func_info['name']}: {func_info['description'][:40]}\n"
                added.add(func_name)
        
        prompt += """

ПРАВИЛА ВИБОРУ ФУНКЦІЇ:
1. "виконай код" → execute_python
2. "відкрий", "закрий" → open_program/close_program
3. "скріншот" → take_screenshot
4. "клікни [текст]" → click_text
5. "вікна" → list_windows
6. "знайди вікно" → find_window_by_title
7. "активуй" → activate_window
8. "клікни [x,y]" → mouse_click
9. "напиши [текст]" → keyboard_type

ЗАВЖДИ ПОВЕРТАЙ JSON З action!
"""
        
        return prompt
    
    def execute_function(self, action, params, auto_create=True):
        """Виконати функцію за назвою з аудитом.

        Якщо функція не знайдена і auto_create=True — спробувати створити її
        через Архітектор (create_skill).
        """
        audit = get_audit_log()
        risk = get_tool_risk(action)

        if action not in self.functions:
            # Автоматичне створення функції через Архітектор
            if auto_create and action != "create_skill" and "create_skill" in self.functions:
                print(f"{Fore.YELLOW}🏗️  Функція '{action}' не знайдена — створюю через Архітектор...")
                try:
                    create_fn = self.functions["create_skill"]["function"]
                    task_desc = f"Функція з назвою '{action}' приймає параметри: {params}"
                    create_fn(task_description=task_desc)
                    # Після refresh() функції перезавантажуються
                    if action in self.functions:
                        print(f"{Fore.GREEN}✅ Функція '{action}' створена, виконую...")
                        return self.execute_function(action, params, auto_create=False)
                    else:
                        print(f"{Fore.YELLOW}⚠️  Архітектор не створив функцію з точною назвою '{action}'")
                except Exception as e:
                    print(f"{Fore.RED}❌ Помилка Архітектора: {e}")

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