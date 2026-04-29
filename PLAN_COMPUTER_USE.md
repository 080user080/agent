# ПЛАН: МАРК як повноцінний Computer Use агент + GUI-тестувальник

> Дата: 26.04.2026  
> Автор: Devin (аналіз коду)  
> Мета: Перетворити МАРК з "набору інструментів з планером" на агента, який користується ПК як людина і може тестувати GUI

---

## 0. ДІАГНОЗ: ЩО ЗАРАЗ НЕ ТАК (після аналізу всього коду)

### Головна проблема: ДВА ПАРАЛЕЛЬНИХ СТЕКИ, НЕ З'ЄДНАНИХ МІЖ СОБОЮ

```
LEGACY СТЕК (працює через GUI):
  run_assistant.py → AssistantApp.gui_callback('process_text')
    → AssistantCore.process_text_command()
      → VoiceAssistant.process_command()
        → Planner.create_plan() → список словників [{action, args}]
          → TaskExecutor.execute_plan_async(plan, execute_step)
            → registry.execute_function(action, args)
              → aaa_*.py функції

НОВИЙ СТЕК (Phase 11+, НЕ підключений до GUI):
  TaskRunner.run(plan)
    → Task(kind="run_command|write_file|call_provider|...")
      → PermissionGate.ask() → Decision
      → handler(TaskContext) → result
      → Task.expect → ExpectationResult
    → ExecutionReport → StepReport[]
    → SessionBudget.check() → kill-switch
    → PlanCritic.review(plan) → verdict
```

**Проблема:** Коли користувач натискає "Виконати" в GUI → йде по LEGACY стеку. Новий стек (TaskRunner з PermissionGate, Expectations, SessionBudget, PlanCritic) — мертвий код з точки зору реального використання.

### Конкретні розриви між стеками

| Що | Legacy стек | Новий стек | Розрив |
|----|-------------|------------|--------|
| **Формат плану** | `[{action: "mouse_click", args: {x, y}}]` — список словників | `Plan(tasks=[Task(kind="run_command")])` — типізовані dataclass-и | Різні формати. `core_planner_runner.py` існує як міст, але НЕ підключений до GUI |
| **Перевірка результату** | `planner._validate_step()` — примітивний check | `Task.expect` → `ExpectRegistry` з 17 evaluator-ами | Legacy не використовує expectations |
| **Безпека** | `registry.get_tool_risk()` + `TOOL_POLICIES` | `PermissionGate` з 4-рівневою policy stack | Дублювання, legacy не використовує PermissionGate |
| **Repair** | `planner.propose_repair_step()` — 3 спроби | Repair loop (Phase 12.2) — не реалізований | Legacy має примітивний repair, новий стек — жодного |
| **Звіт** | Відсутній (тільки лог у консоль) | `ExecutionReport` + `ReportGenerator` | Legacy не генерує звіт |
| **Бюджет** | Відсутній | `SessionBudget` з лімітами на час/кроки/токени | Legacy працює без лімітів |
| **GUI progress** | `TaskExecutor` оновлює панель плану | `ExecutionReport` — в пам'яті, без GUI | Новий стек не має UI |

### Що є і працює (реальний код, а не заглушки)

**✅ Повністю реалізовано (код review підтверджує):**
- `tools_mouse_keyboard.py` (436 рядків) — mouse_click, mouse_move, mouse_scroll, mouse_drag, keyboard_type, keyboard_press, keyboard_hotkey, clipboard — **все через pyautogui, реальний код**
- `tools_window_manager.py` (605 рядків) — list_windows, find_window_by_title, activate_window, move/resize/close — **реальний код через win32gui/pygetwindow**
- `tools_screen_capture.py` (608 рядків) — take_screenshot, capture_region, find_image_on_screen, wait_for_image — **реальний код через mss + PIL + OpenCV**
- `tools_ocr.py` (595 рядків) — OCREngine + ScreenOCR, pytesseract + easyocr fallback, find_text_on_screen, click_text — **реальний код**
- `tools_ui_detector.py` (653 рядки) — find_button_by_text, find_input_field, find_checkbox, find_input_near_label — **реальний код через OpenCV + OCR**
- `tools_app_recognizer.py` (573 рядки) — detect_active_application, detect_file_dialog, detect_error_dialog — **реальний код**
- `tools_visual_diff.py` (504 рядки) — capture_baseline, compare_with_baseline, highlight_changes — **реальний код**
- `logic_ui_navigator.py` (860 рядків) — UINavigator: click_element, type_in_field, fill_form, handle_dialog — **реальний код, використовує Phase 1-4**
- `logic_scenario_runner.py` (807 рядків) — ScenarioRunner: run_scenario, built-in scenarios (save/open/find) — **реальний код**
- `logic_context_analyzer.py` (854 рядки) — ContextAnalyzer: analyze_current_context, suggest_next_action, detect_blocker — **реальний код**
- `logic_task_runner.py` (836 рядків) — TaskRunner з handler-реєстром, 10 built-in handlers — **повністю функціональний**
- `logic_permission_gate.py` (387 рядків) — 4-рівнева policy stack — **повністю функціональний**
- `logic_expectations.py` (728 рядків) — 17 evaluator-ів (incl. Phase 13 S10) — **повністю функціональний**
- `logic_execution_report.py` (317 рядків) — StepReport + ExecutionReport — **повністю функціональний**
- `logic_report_generator.py` (404 рядки) — goal-driven markdown report — **повністю функціональний**
- `core_session_budget.py` (215 рядків) — SessionBudget з лімітами — **повністю функціональний**
- `logic_watcher.py` (457 рядків) — Watcher engine з потоками — **повністю функціональний**
- `logic_plan_critic.py` (453 рядки) — PlanCritic (LLM meta-оцінка) — **повністю функціональний**
- `logic_llm_tools.py` (455 рядків) — OpenAI tool-calling — **повністю функціональний**
- `core_planner_runner.py` (448 рядків) — міст legacy→TaskRunner — **повністю функціональний, але НЕ ПІДКЛЮЧЕНИЙ**
- `core_windsurf_watcher.py` (411 рядків) — WindsurfWatcherRunner — **повністю функціональний**
- `core_action_recorder.py` (521 рядків) — ActionRecorder з скріншотами до/після — **реальний код**
- `core_undo_manager.py` (641 рядків) — snapshots + undo — **реальний код**
- `core_gui_guardian.py` (532 рядки) — GUIGuardian risk assessment — **реальний код**

**🟡 Частково (скелет + базова функціональність):**
- `core_app_profile.py` (280 рядків) — AppProfile dataclass є, built-in профілі є, але learn_from_interaction — заглушка
- `core_macro.py` (293 рядки) — MacroRecorder + MacroPlayer є, але не підключені до GUI

**🔴 Відсутнє (ні коду, ні модулів):**
- `tools_browser.py` — Playwright/CDP для реальної браузерної автоматизації
- `tools_ui_accessibility.py` — UIA (Windows Accessibility API) через pywinauto
- `providers_vision.py` — Vision-LLM (GPT-4V / Claude Vision / LLaVA)
- `logic_step_repair.py` — LLM repair loop на expect_failed (Phase 12.2)
- `logic_agent_loop.py` — головний цикл observe→decide→act→check→repeat
- CI/CD — GitHub Actions, pre-commit config

---

## 1. ДЕТАЛЬНИЙ ПЛАН РЕАЛІЗАЦІЇ

### ЕТАП 1: ГОЛОВНИЙ ЦИКЛ (Phase 12.3 + Agent Loop) — КРИТИЧНИЙ

**Ціль:** з'єднати новий стек з GUI і створити цикл observe→decide→act→check→repeat

#### 1.1 Файл: `functions/logic_agent_loop.py` (НОВИЙ, ~400 рядків)

Це **серце** агента. Один цикл, який замінює весь legacy flow.

```python
class AgentLoop:
    """Головний цикл агента: observe → decide → act → check → repeat.
    
    Замінює legacy flow (Planner → TaskExecutor → registry.execute_function)
    на цикл з повною інтеграцією Phase 11+ стеку.
    """
    
    def __init__(
        self,
        runner: TaskRunner,          # Phase 11 TaskRunner
        gate: PermissionGate,        # Phase 11 PermissionGate
        budget: SessionBudget,       # Phase 8 SessionBudget
        observer: ScreenObserver,    # observe() — screenshot + OCR + UIA
        decider: ActionDecider,      # decide() — LLM tool-calling
        report: ExecutionReport,     # Phase 11 ExecutionReport
        on_step_update: Callable,    # callback для GUI
        on_complete: Callable,       # callback для GUI
    ):
        ...
    
    def run(self, goal: str) -> RunResult:
        """Головний цикл."""
        state = AgentState(goal=goal)
        
        while not self._should_stop(state):
            # 1. OBSERVE — подивитись на екран
            observation = self.observer.observe()
            state.update_observation(observation)
            
            # 2. DECIDE — LLM вирішує що робити
            action = self.decider.decide(
                goal=state.goal,
                observation=observation,
                history=state.action_history,
                last_result=state.last_result,
            )
            
            if action.type == "done":
                state.mark_done(action.summary)
                break
            
            # 3. ACT — виконати дію
            result = self._execute_action(action)
            state.record_action(action, result)
            self._notify_gui(state)
            
            # 4. CHECK — перевірити результат
            check_result = self._check_result(action, result, observation)
            state.update_check(check_result)
            
            if not check_result.ok:
                state.increment_failures()
                if state.consecutive_failures >= 3:
                    # Попросити LLM переосмислити підхід
                    action = self.decider.replan(state)
                    
        return self._build_result(state)
```

**Що робить кожен компонент:**

##### 1.1.1 `ScreenObserver` (в тому ж файлі, ~100 рядків)

```python
class ScreenObserver:
    """Збирає 'картину світу' з екрану."""
    
    def observe(self) -> Observation:
        screenshot = take_screenshot()
        ocr_text = ocr_screen()
        active_app = detect_active_application()
        app_state = detect_application_state()
        elements = self._detect_ui_elements()
        
        return Observation(
            screenshot_path=screenshot,
            text=ocr_text,
            active_app=active_app,
            app_state=app_state,
            elements=elements,
            timestamp=time.time(),
        )
    
    def _detect_ui_elements(self) -> List[UIElement]:
        """Знайти всі видимі UI елементи."""
        buttons = find_button_by_text("*")  # всі кнопки
        inputs = find_input_field()
        checkboxes = find_checkbox()
        # В майбутньому — UIA (Etap 3)
        return buttons + inputs + checkboxes
```

##### 1.1.2 `ActionDecider` (в тому ж файлі, ~150 рядків)

```python
class ActionDecider:
    """LLM вирішує наступну дію на основі observation."""
    
    def __init__(self, llm_caller, tools_schema):
        self.llm = llm_caller
        self.tools = tools_schema  # OpenAI tool-calling schema
    
    def decide(self, goal, observation, history, last_result) -> AgentAction:
        """Один крок рішення через tool-calling."""
        messages = self._build_messages(goal, observation, history, last_result)
        response = ask_llm_with_tools(messages, tools=self.tools)
        
        if response.has_tool_calls:
            tc = response.tool_calls[0]
            return AgentAction(
                type=tc.name,
                params=tc.arguments,
                reasoning=response.content,
            )
        
        # LLM вважає що задача виконана
        return AgentAction(type="done", summary=response.content)
    
    def replan(self, state: AgentState) -> AgentAction:
        """Переосмислити підхід після кількох невдач."""
        prompt = f"""
        Задача: {state.goal}
        Останні 3 невдалі дії: {state.recent_failures}
        Поточний стан екрану: {state.last_observation.text[:500]}
        
        Що спробувати по-іншому?
        """
        return self.decide(prompt, state.last_observation, [], None)
```

##### 1.1.3 `AgentState` (dataclass, ~50 рядків)

```python
@dataclass
class AgentState:
    goal: str
    step: int = 0
    action_history: List[Dict] = field(default_factory=list)
    last_result: Optional[Dict] = None
    last_observation: Optional[Observation] = None
    consecutive_failures: int = 0
    total_failures: int = 0
    is_done: bool = False
    done_summary: str = ""
    
    def record_action(self, action, result):
        self.step += 1
        self.action_history.append({
            "step": self.step,
            "action": action.type,
            "params": action.params,
            "success": result.get("success", False),
        })
        self.last_result = result
        if result.get("success"):
            self.consecutive_failures = 0
        
    def update_check(self, check):
        if not check.ok:
            self.consecutive_failures += 1
            self.total_failures += 1
```

#### 1.2 Файл: `core_gui/main_window.py` — зміни (~50 рядків змін)

Додати кнопку "Виконати (Agent Loop)" або замінити legacy flow:

```python
# В create_widgets():
self.agent_loop_btn = ttk.Button(
    control_frame,
    text="🤖 Агент",
    command=self._start_agent_loop,
    style='Action.TButton'
)

def _start_agent_loop(self):
    """Запустити agent loop замість legacy executor."""
    text = self.text_input.get().strip()
    if text:
        self.assistant_callback('start_agent_loop', text)
```

#### 1.3 Файл: `run_assistant.py` — зміни (~30 рядків)

Додати обробку `start_agent_loop` в `gui_callback`:

```python
elif action == 'start_agent_loop':
    threading.Thread(
        target=self.core.run_agent_loop,
        args=(data,),
        daemon=True
    ).start()
```

#### 1.4 Файл: `main.py` (AssistantCore) — зміни (~60 рядків)

Додати метод `run_agent_loop`:

```python
def run_agent_loop(self, goal_text: str):
    """Запустити новий agent loop."""
    from functions.logic_agent_loop import AgentLoop, ScreenObserver, ActionDecider
    from functions.logic_task_runner import TaskRunner
    from functions.logic_permission_gate import PermissionGate
    from functions.core_session_budget import SessionBudget, SessionLimits
    from functions.logic_execution_report import ExecutionReport
    
    runner = TaskRunner(gate=PermissionGate())
    budget = SessionBudget(limits=SessionLimits())
    observer = ScreenObserver()
    decider = ActionDecider(llm_caller=self.assistant.ask_llm, tools_schema=...)
    report = ExecutionReport(plan_name=goal_text)
    
    loop = AgentLoop(
        runner=runner,
        gate=PermissionGate(),
        budget=budget,
        observer=observer,
        decider=decider,
        report=report,
        on_step_update=lambda state: self.gui_queue.put(('step_update', state)),
        on_complete=lambda result: self.gui_queue.put(('agent_complete', result)),
    )
    
    result = loop.run(goal_text)
    # Згенерувати звіт
    report_md = ReportGenerator().generate(report)
    # Показати в GUI
```

#### 1.5 Tools Schema для LLM tool-calling

Файл: `functions/logic_agent_tools_schema.py` (НОВИЙ, ~200 рядків)

Описує всі доступні GUI-дії у форматі OpenAI tools:

```python
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "Клікнути мишею в координати",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string", "enum": ["left", "right"]},
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_text",
            "description": "Знайти текст на екрані і клікнути по ньому",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст для пошуку"},
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_type",
            "description": "Ввести текст з клавіатури",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_hotkey",
            "description": "Натиснути комбінацію клавіш (наприклад Ctrl+S)",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Зробити скріншот екрану",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ocr_screen",
            "description": "Прочитати весь текст з екрану",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_program",
            "description": "Відкрити програму за назвою",
            "parameters": {
                "type": "object",
                "properties": {
                    "program_name": {"type": "string"},
                },
                "required": ["program_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fill_form",
            "description": "Заповнити форму (словник поле→значення)",
            "parameters": {
                "type": "object",
                "properties": {
                    "fields": {"type": "object"},
                },
                "required": ["fields"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_text",
            "description": "Чекати поки текст з'явиться на екрані",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "timeout": {"type": "number", "default": 10},
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Задача виконана. Викликати коли ціль досягнута.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Підсумок виконання"},
                },
                "required": ["summary"]
            }
        }
    },
]
```

**Оцінка:** ~800-1000 рядків нового коду + ~150 рядків змін  
**Складність:** Висока  
**Результат:** МАРК зможе виконувати задачі в циклі: observe→decide→act→check→repeat

---

### ЕТАП 2: GUI-ТЕСТУВАННЯ (Test Scenario Runner) — ВИСОКА ЦІННІСТЬ

**Ціль:** МАРК може відкрити програму, протестувати GUI, зробити висновки

#### 2.1 Файл: `functions/logic_gui_tester.py` (НОВИЙ, ~500 рядків)

```python
class GUITester:
    """Тестувальник GUI програм.
    
    Використовує AgentLoop для автоматичного тестування:
    - Відкриває програму
    - Виконує сценарій тестування
    - Перевіряє результати (скріншоти до/після, OCR, visual diff)
    - Генерує звіт з вердиктом
    """
    
    def __init__(self, agent_loop: AgentLoop):
        self.loop = agent_loop
        self.recorder = ActionRecorder()  # скріншоти до/після
        self.differ = VisualDiff()         # порівняння скріншотів
    
    def test_scenario(self, scenario: TestScenario) -> TestReport:
        """Виконати тестовий сценарій."""
        report = TestReport(scenario_name=scenario.name)
        
        for test_case in scenario.test_cases:
            # Скріншот "до"
            before = self.recorder.capture("before")
            
            # Виконати тест через agent loop
            result = self.loop.run(test_case.goal)
            
            # Скріншот "після"
            after = self.recorder.capture("after")
            
            # Перевірити очікування
            checks = self._verify_expectations(test_case, result, before, after)
            
            report.add_result(TestCaseResult(
                name=test_case.name,
                passed=all(c.ok for c in checks),
                checks=checks,
                screenshots={"before": before, "after": after},
                duration_s=result.report.duration_s,
            ))
        
        return report
    
    def test_function(self, app_name: str, function_name: str) -> TestCaseResult:
        """Швидкий тест однієї функції.
        
        Приклад: test_function("Notepad", "Зберегти файл")
        """
        goal = f"Відкрий {app_name}, виконай '{function_name}', перевір що спрацювало"
        result = self.loop.run(goal)
        return self._evaluate_result(result)
    
    def test_changes(self, app_name: str, changes_description: str) -> TestReport:
        """Тестування після змін у коді.
        
        Приклад: test_changes("MyApp", "Додав кнопку 'Експорт' в меню Файл")
        """
        goal = f"""
        Відкрий {app_name}.
        Перевір зміни: {changes_description}
        Зроби скріншоти.
        Перевір що:
        1. Програма запускається без помилок
        2. Зміни відображаються правильно
        3. Функціональність працює
        Дай висновок: все ок чи треба доробити.
        """
        return self.loop.run(goal)
```

#### 2.2 `TestScenario` та `TestCase` dataclasses

```python
@dataclass
class TestCase:
    name: str
    goal: str  # текстовий опис що зробити
    expectations: List[Expectation]  # що перевірити після
    # Приклади expectations:
    # - TextVisible("Збережено успішно")
    # - WindowTitle("Notepad - Untitled")
    # - ElementExists("button", "Save")
    # - NoErrorDialog()
    # - VisualMatch(baseline_name="after_save")

@dataclass  
class TestScenario:
    name: str
    app_name: str
    setup_steps: List[str]  # як підготувати тест
    test_cases: List[TestCase]
    teardown_steps: List[str]  # як прибрати після тесту
```

#### 2.3 Приклади сценаріїв (JSON файли)

```json
{
  "name": "Тест Notepad — базові функції",
  "app_name": "notepad.exe",
  "setup_steps": ["Відкрий Notepad"],
  "test_cases": [
    {
      "name": "Введення тексту",
      "goal": "Введи 'Hello World' в Notepad",
      "expectations": [
        {"type": "text_visible", "text": "Hello World"}
      ]
    },
    {
      "name": "Збереження файлу",
      "goal": "Збережи файл як test_output.txt на Desktop",
      "expectations": [
        {"type": "file_exists", "path": "~/Desktop/test_output.txt"},
        {"type": "window_title_contains", "text": "test_output"}
      ]
    },
    {
      "name": "Undo",
      "goal": "Натисни Ctrl+Z щоб відмінити останню дію",
      "expectations": [
        {"type": "text_not_visible", "text": "Hello World"}
      ]
    }
  ],
  "teardown_steps": ["Закрий Notepad без збереження"]
}
```

#### 2.4 Звіт тестування

```python
class TestReportGenerator:
    """Генерує markdown-звіт тестування."""
    
    def generate(self, report: TestReport) -> str:
        lines = [
            f"# Звіт тестування: {report.scenario_name}",
            f"Дата: {report.timestamp}",
            f"Тривалість: {report.total_duration_s:.1f}с",
            f"",
            f"## Результат: {'✅ ВСЕ OK' if report.all_passed else '❌ Є помилки'}",
            f"",
            f"| Тест | Статус | Час | Деталі |",
            f"|------|--------|-----|--------|",
        ]
        for r in report.results:
            status = "✅" if r.passed else "❌"
            lines.append(f"| {r.name} | {status} | {r.duration_s:.1f}с | {r.summary} |")
        
        if report.failed_results:
            lines.append(f"\n## ❌ Невдалі тести\n")
            for r in report.failed_results:
                lines.append(f"### {r.name}")
                lines.append(f"- **Очікувалось:** {r.expected}")
                lines.append(f"- **Отримано:** {r.actual}")
                lines.append(f"- **Скріншот:** ![before]({r.screenshots['before']})")
                lines.append(f"- **Скріншот:** ![after]({r.screenshots['after']})")
        
        lines.append(f"\n## Висновок")
        if report.all_passed:
            lines.append("Всі тести пройшли. Код працює коректно.")
        else:
            lines.append(f"Не пройшло {len(report.failed_results)} з {len(report.results)} тестів.")
            lines.append("Рекомендація: доробити виявлені проблеми.")
        
        return "\n".join(lines)
```

**Оцінка:** ~500-700 рядків нового коду  
**Складність:** Середня (використовує AgentLoop з Етапу 1)  
**Результат:** МАРК може тестувати GUI як QA-інженер

---

### ЕТАП 3: ACCESSIBILITY API (UIA) — СТАБІЛЬНІСТЬ

**Ціль:** Замінити крихкий OCR + template matching на структурне дерево UI

#### 3.1 Файл: `functions/tools_ui_accessibility.py` (НОВИЙ, ~500 рядків)

```python
"""Windows UI Automation через pywinauto.

Дає агенту доступ до структурного дерева UI елементів замість
пошуку по пікселях. Це робить GUI-автоматизацію:
- Стійкою до DPI/тем/локалізації
- Швидшою (не потрібен OCR + template matching)
- Точнішою (знає точні координати і стан елементів)
"""

try:
    from pywinauto import Desktop, Application
    from pywinauto.controls.uiawrapper import UIAWrapper
    HAS_PYWINAUTO = True
except ImportError:
    HAS_PYWINAUTO = False


class UIAccessibility:
    """Доступ до UI через Windows Accessibility API."""
    
    def get_ui_tree(self, hwnd=None, depth=3) -> Dict:
        """Отримати дерево UI елементів активного вікна.
        
        Returns:
            {
                "window_title": "Notepad",
                "elements": [
                    {"role": "Button", "name": "Save", "enabled": True, 
                     "bounds": {"x": 10, "y": 20, "w": 80, "h": 30}},
                    {"role": "Edit", "name": "Text Editor", "value": "Hello",
                     "bounds": {"x": 0, "y": 50, "w": 500, "h": 300}},
                    ...
                ]
            }
        """
    
    def find_element(self, role=None, name=None, automationid=None) -> Optional[UIElement]:
        """Знайти елемент за role/name/automationid."""
    
    def click_element_by_name(self, name: str) -> Dict:
        """Клікнути по елементу за його name (через UIA, не координати)."""
    
    def type_in_element(self, name: str, text: str) -> Dict:
        """Ввести текст в елемент за його name."""
    
    def get_element_value(self, name: str) -> Optional[str]:
        """Отримати значення елементу (текст в полі вводу)."""
    
    def list_all_buttons(self) -> List[Dict]:
        """Список всіх кнопок у активному вікні."""
    
    def list_all_inputs(self) -> List[Dict]:
        """Список всіх полів вводу."""
    
    def wait_for_element(self, name: str, timeout: float = 10) -> bool:
        """Чекати появи елементу."""
```

#### 3.2 Інтеграція з `ScreenObserver`

```python
# В logic_agent_loop.py → ScreenObserver.observe():
def observe(self) -> Observation:
    # Пріоритет: UIA → OCR fallback
    if HAS_PYWINAUTO:
        ui_tree = self.uia.get_ui_tree()
        elements = ui_tree["elements"]
    else:
        # Fallback на OCR + CV
        elements = self._detect_ui_elements_ocr()
    
    return Observation(elements=elements, ...)
```

#### 3.3 Зміни в `tools_ui_detector.py`

Додати fallback: якщо pywinauto доступний — використовувати UIA, інакше — OCR + CV:

```python
def find_button_by_text(text, region=None, confidence=0.7):
    if HAS_PYWINAUTO:
        elem = uia.find_element(role="Button", name=text)
        if elem:
            return {"x": elem.bounds.x, "y": elem.bounds.y, ...}
    # Fallback на OCR + template matching
    return _find_button_by_text_ocr(text, region, confidence)
```

**Оцінка:** ~500 рядків нового коду + ~100 рядків змін  
**Складність:** Середня  
**Залежність:** `pip install pywinauto` (Windows only; mock для Linux CI)  
**Результат:** GUI-кліки стабільні незалежно від DPI/теми/мови

---

### ЕТАП 4: VISION-LLM — РОЗУМІННЯ ЕКРАНУ

**Ціль:** Агент може подивитись на скріншот і зрозуміти що на ньому

#### 4.1 Файл: `functions/providers_vision.py` (НОВИЙ, ~300 рядків)

```python
"""Vision-LLM провайдери для аналізу скріншотів.

Pluggable: GPT-4V, Claude Vision, LLaVA (Ollama), Qwen-VL.
"""

class VisionProvider(Protocol):
    def describe(self, image_path: str, prompt: str) -> str: ...
    def plan_action(self, image_path: str, goal: str) -> Dict: ...

class OpenAIVisionProvider:
    """GPT-4V / GPT-4o через OpenAI API."""
    def describe(self, image_path, prompt):
        base64_img = encode_image(image_path)
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                ]
            }]
        )
        return response.choices[0].message.content

class OllamaVisionProvider:
    """LLaVA / Qwen-VL через Ollama (локально)."""
    def describe(self, image_path, prompt):
        base64_img = encode_image(image_path)
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "llava",
            "prompt": prompt,
            "images": [base64_img],
        })
        return response.json()["response"]
```

#### 4.2 Інтеграція з `ActionDecider`

```python
# В logic_agent_loop.py → ActionDecider.decide():
def decide(self, goal, observation, history, last_result):
    # Якщо є vision-провайдер — надіслати скріншот
    if self.vision_provider:
        screen_description = self.vision_provider.describe(
            observation.screenshot_path,
            f"Опиши що бачиш на екрані. Задача: {goal}"
        )
        observation.vision_description = screen_description
    
    # LLM вирішує на основі тексту + vision опису
    ...
```

#### 4.3 Нові tools для Vision

```python
VISION_TOOLS = [
    {
        "name": "describe_screen",
        "description": "Подивитись на екран і описати що бачиш",
        "parameters": {"prompt": {"type": "string"}}
    },
    {
        "name": "find_element_by_description",
        "description": "Знайти елемент на екрані за описом (використовує зір)",
        "parameters": {"description": {"type": "string"}}
    },
    {
        "name": "is_screen_correct",
        "description": "Перевірити чи екран виглядає правильно для даної задачі",
        "parameters": {"expected_state": {"type": "string"}}
    },
]
```

**Оцінка:** ~300-400 рядків нового коду  
**Складність:** Середня  
**Залежність:** OpenAI API key або Ollama  
**Результат:** Агент "розуміє" що бачить, може оцінити незнайомий UI

---

### ЕТАП 5: БРАУЗЕРНА АВТОМАТИЗАЦІЯ (Playwright) — ВЕБ-ЗАДАЧІ

**Ціль:** Повноцінна взаємодія з браузером (клік, ввід тексту, витяг даних)

#### 5.1 Файл: `functions/tools_browser.py` (НОВИЙ, ~500 рядків)

```python
"""Браузерна автоматизація через Playwright CDP.

Підключається до існуючого Chrome-профілю користувача (залогінений).
"""

from playwright.sync_api import sync_playwright

class BrowserAutomation:
    def __init__(self, cdp_url="http://localhost:9222"):
        self.cdp_url = cdp_url
        self._browser = None
        self._page = None
    
    def connect(self):
        """Підключитись до існуючого Chrome через CDP."""
        pw = sync_playwright().start()
        self._browser = pw.chromium.connect_over_cdp(self.cdp_url)
        self._page = self._browser.contexts[0].pages[0]
    
    def open_url(self, url: str) -> Dict:
        """Відкрити URL."""
        self._page.goto(url)
        return {"success": True, "url": url, "title": self._page.title()}
    
    def click_by_text(self, text: str) -> Dict:
        """Клікнути по елементу з текстом."""
        self._page.get_by_text(text).click()
        return {"success": True}
    
    def click_by_role(self, role: str, name: str) -> Dict:
        """Клікнути по елементу за ролью."""
        self._page.get_by_role(role, name=name).click()
        return {"success": True}
    
    def fill(self, selector_or_label: str, text: str) -> Dict:
        """Заповнити поле."""
        self._page.get_by_label(selector_or_label).fill(text)
        return {"success": True}
    
    def screenshot(self, path: str = None) -> str:
        """Скріншот сторінки."""
        path = path or f"screenshots/browser_{time.time():.0f}.png"
        self._page.screenshot(path=path)
        return path
    
    def extract_text(self) -> str:
        """Витягнути весь текст зі сторінки."""
        return self._page.inner_text("body")
    
    def wait_for(self, text: str, timeout: float = 10) -> bool:
        """Чекати появи тексту."""
        try:
            self._page.wait_for_selector(f"text={text}", timeout=timeout*1000)
            return True
        except:
            return False
    
    def execute_js(self, script: str) -> Any:
        """Виконати JavaScript."""
        return self._page.evaluate(script)
```

#### 5.2 Реєстрація як handler в TaskRunner

```python
# В logic_task_runner.py або окремому модулі:
def _handler_browser(ctx: TaskContext) -> Dict:
    action = ctx.task.params.get("browser_action")
    browser = BrowserAutomation()
    browser.connect()
    
    if action == "open_url":
        return browser.open_url(ctx.task.params["url"])
    elif action == "click_text":
        return browser.click_by_text(ctx.task.params["text"])
    # ...
```

**Оцінка:** ~500 рядків нового коду  
**Складність:** Середня  
**Залежність:** `pip install playwright && playwright install chromium`  
**Результат:** МАРК може працювати з веб-сайтами як людина

---

### ЕТАП 6: LLM REPAIR LOOP (Phase 12.2) — АДАПТИВНІСТЬ

**Ціль:** Коли щось не вийшло — агент адаптує план

#### 6.1 Файл: `functions/logic_step_repair.py` (НОВИЙ, ~250 рядків)

```python
"""LLM repair loop на expect_failed.

Коли Task.expect не пройшов:
1. Збирає контекст: що очікувалось, що отримано, stdout, скріншот
2. Запитує LLM: "що пішло не так і що спробувати"
3. LLM повертає модифікований план
4. TaskRunner виконує новий план
5. Максимум 3 repair-спроби (бюджет)
"""

class StepRepairer:
    def __init__(self, llm_caller, budget_limit=3):
        self.llm = llm_caller
        self.budget_limit = budget_limit
        self.attempts = 0
    
    def repair(self, failed_step: StepReport, plan: Plan, 
               expect_results: List[ExpectationResult]) -> Optional[Plan]:
        """Запропонувати новий план на основі невдачі."""
        if self.attempts >= self.budget_limit:
            return None
        
        self.attempts += 1
        
        prompt = f"""
        Крок "{failed_step.task_name}" не пройшов перевірку.
        
        Очікувалось: {[r.to_dict() for r in expect_results if not r.ok]}
        Отримано: stdout="{failed_step.stdout_tail[:200]}", error="{failed_step.error}"
        
        Попередні кроки: {[s.task_name for s in plan.tasks[:failed_step.index]]}
        
        Що спробувати по-іншому? Поверни JSON з новими кроками.
        """
        
        response = self.llm(prompt)
        return self._parse_new_plan(response)
```

**Оцінка:** ~250 рядків  
**Складність:** Низька  
**Результат:** Агент адаптується коли щось не працює

---

### ЕТАП 7: CHECKPOINT + RESUME (Phase 12.4) — НАДІЙНІСТЬ

**Ціль:** При краші 3-годинної сесії — продовжити з останньої точки

#### 7.1 Зміни в `logic_task_runner.py` (~100 рядків)

```python
class TaskRunner:
    def __init__(self, ..., checkpoint_path: Optional[str] = None):
        self.checkpoint_path = checkpoint_path
    
    def _checkpoint(self, step: StepReport, remaining_tasks: List[Task]):
        """Зберегти стан після кожного кроку."""
        if self.checkpoint_path:
            state = {
                "completed_steps": [s.to_dict() for s in self.completed_steps],
                "remaining_tasks": [t.to_dict() for t in remaining_tasks],
                "timestamp": time.time(),
            }
            Path(self.checkpoint_path).write_text(json.dumps(state, ensure_ascii=False))
    
    @classmethod
    def resume_from_checkpoint(cls, path: str) -> "TaskRunner":
        """Відновити з checkpoint."""
        state = json.loads(Path(path).read_text())
        # Пропустити виконані кроки, продовжити з remaining
        ...
```

**Оцінка:** ~100-150 рядків  
**Складність:** Низька  
**Результат:** 6-годинні сесії стійкі до крашів

---

### ЕТАП 8: ТЕСТИ + CI — ІНЖЕНЕРНА ЯКІСТЬ

#### 8.1 Нові тест-файли

| Файл | Покриває | Оцінка рядків |
|------|----------|---------------|
| `tests/test_logic_agent_loop.py` | AgentLoop, ScreenObserver, ActionDecider | ~300 |
| `tests/test_logic_gui_tester.py` | GUITester, TestScenario | ~200 |
| `tests/test_tools_ui_accessibility.py` | UIA через pywinauto (моки) | ~200 |
| `tests/test_providers_vision.py` | Vision providers (моки HTTP) | ~150 |
| `tests/test_tools_browser.py` | BrowserAutomation (моки Playwright) | ~200 |
| `tests/test_logic_step_repair.py` | StepRepairer | ~150 |
| `tests/test_tools_screen_capture.py` | Phase 2 (досі відсутній!) | ~200 |
| `tests/test_tools_ui_detector.py` | Phase 4 (досі відсутній!) | ~200 |
| `tests/test_tools_app_recognizer.py` | Phase 4 (досі відсутній!) | ~200 |

#### 8.2 CI конфігурація

Файл: `.github/workflows/ci.yml`

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pip install opencv-python-headless
      - run: python -m ruff check .
      - run: python -m pytest tests/ -q --tb=short
```

Файл: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
```

---

## 2. ПРІОРИТЕТИ ТА ЗАЛЕЖНОСТІ

```
Етап 1 (Agent Loop) ←── КРИТИЧНИЙ, все залежить від нього
  ↓
Етап 2 (GUI Tester) ←── залежить від Етапу 1
  ↓
Етап 3 (UIA) ←── незалежний, підсилює Етап 1
  ↓
Етап 4 (Vision-LLM) ←── незалежний, підсилює Етап 1
  ↓
Етап 5 (Playwright) ←── незалежний
  ↓
Етап 6 (Repair Loop) ←── залежить від Етапу 1
  ↓
Етап 7 (Checkpoint) ←── залежить від Етапу 1
  ↓
Етап 8 (Тести + CI) ←── паралельно з усім
```

## 3. ОЦІНКА ОБ'ЄМУ

| Етап | Нових рядків | Змін | Нових файлів | Час |
|------|-------------|------|--------------|-----|
| 1. Agent Loop | ~1000 | ~240 | 2 | 2-3 дні |
| 2. GUI Tester | ~700 | ~50 | 1 | 1-2 дні |
| 3. UIA | ~600 | ~100 | 1 | 1-2 дні |
| 4. Vision-LLM | ~400 | ~50 | 1 | 1 день |
| 5. Playwright | ~500 | ~50 | 1 | 1-2 дні |
| 6. Repair Loop | ~250 | ~50 | 1 | 1 день |
| 7. Checkpoint | ~150 | ~100 | 0 | 0.5 дня |
| 8. Тести + CI | ~1800 | ~0 | 9+ | 2-3 дні |
| **РАЗОМ** | **~5400** | **~640** | **16** | **~10-15 днів** |

## 4. ДОДАТКОВІ ЗАУВАЖЕННЯ З АУДИТУ КОДУ

### Потрібно виправити зараз (не залежить від плану)

1. **`requirements.txt` неповний** — додати: `pyautogui`, `pywin32`, `psutil`, `mss`, `Pillow`, `opencv-python`, `pytesseract`, `pyperclip`, `pygetwindow`
2. **README.md** — виправити `gui/` → `core_gui/`, `python agent.py` → `python run_assistant.py`
3. **Застарілі файли** — видалити `aaa_kill_process_by_name.py_off`, `aaa_open_program.py_old`
4. **`pyproject.toml`** — додати ruff конфіг:
   ```toml
   [tool.ruff]
   line-length = 120
   target-version = "py311"
   ```

### Архітектурні рішення

1. **НЕ видаляти legacy flow** — залишити як fallback, поступово мігрувати
2. **Agent Loop як opt-in** — спочатку окрема кнопка, потім дефолт
3. **Vision-LLM опційний** — агент працює без нього, але краще з ним
4. **UIA з fallback на OCR** — якщо pywinauto недоступний (Linux), використовувати OCR
5. **Playwright з fallback на webbrowser.open** — якщо Playwright не встановлений
