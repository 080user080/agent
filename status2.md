# MARK — стратегія v2 (status2.md)

> Робочий документ для ручного мержу у `status.md`. Цей файл **не редагує**
> основний `status.md` і може бути прийнятий частково. Нижче:
> - (§ 1) Чесна ревізія вашої стратегії з урахуванням того, що реально є у репо.
> - (§ 2) Що залишаємо, що виправляємо, що викидаємо.
> - (§ 3) Фазований roadmap (6 тижнів, по одному PR).
> - (§ 4) **Ризики й пастки**, які легко пропустити.
> - (§ 5) Точки конфлікту з існуючим кодом.

---

## 1. Ревізія: що насправді вже є в репозиторії

Перш ніж планувати «треба додати X», я звірився з кодом. Ось таблиця:

| Блок вашої стратегії | Стан у репо | Коментар |
|---|---|---|
| GUI-Automation (CV + миша/клавіатура) | ✅ є | Phase 1-7: `tools_screen_capture`, `tools_ocr`, `tools_ui_detector`, `core_gui_guardian`, `logic_ui_navigator`. |
| API/CLI виклики через LLM | 🟡 частково | `logic_ai_adapter`+`logic_provider_registry`+`providers_openai_compatible` (Phase 9). LM Studio працює. |
| Planner | ✅ є | `core_planner.py` — генерує JSON-план, валідує `TOOL_POLICIES`, має `_repair()`. |
| Planner-Critic | ✅ щойно | PR #15 — `logic_plan_critic.py` (PlanCritic + `review_and_run_plan`). |
| Step-Check (перед виконанням) | ❌ немає | Немає явної перевірки «вікно відкрилось?». Є `PermissionGate`, але він лише про дозвіл, не про стан. |
| Actor-Critic (після виконання) | ❌ немає | `_repair` спрацьовує **лише якщо tool кинув помилку**. Якщо tool повернув «успіх», але реальний ефект не досягнуто — агент цього не помітить. |
| HostAgent | ✅ є | `core_planner` + `core_dispatcher` грають цю роль. |
| AppAgent | 🟡 частково | `functions/core_app_profile.py` є (PR #6) — дата-шар (AppProfile/Workflow/UIElement). Нема `AppAgent` як окремого виконавця (ще не підключений до планера). |
| Safe execute_python | 🟡 слабко | `aaa_execute_python.py` + `safety_sandbox.py` є, але: (1) `SANDBOX_DIR = D:/Python/MARK/sandbox` — **hardcoded Windows-шлях**; (2) `validate_code` має список заборонених патернів, але **майже всі закоментовані**; (3) немає memory-limit на Windows. |
| Playwright / браузер | ❌ немає | `aaa_open_browser.py` — це `webbrowser.open(url)`. Не управляє браузером, просто відкриває. Selenium у репо **немає** — це неіснуюча проблема. |
| TaskRunner / PermissionGate / ExecutionReport | ✅ є | PR #13 — Phase 11 скелет. |
| Watcher / SessionBudget | ✅ є | PR #8. |
| Windows conditions (chat_idle, window_title) | ✅ є | PR #11. |

**Висновок:** вектор стратегії правильний, але кілька пунктів перефразовуються:
- «замінити Selenium на Playwright» → просто **додати Playwright** (Selenium не було).
- «безпечно виконати Python як Open Interpreter» → **підсилити існуючий** `PythonSandbox`, не писати заново.
- «AppAgent» → **підключити існуючий** `core_app_profile` до планера.

---

## 2. Що залишаємо / виправляємо / викидаємо

### ✅ Залишаємо (без змін)

1. **Гібридна універсальність** (GUI + API/CLI) — правильний концепт. Це вже закладено в архітектурі.
2. **3-рівнева критика: Planner-Critic → Step-Check → Actor-Critic** — це найсильніша інвестиція у якість рішень.
3. **Playwright для реальної браузерної автоматизації** — так, це потрібно.
4. **AppProfile-first** — розширювати JSON-профілі замість того, щоб вчити LLM.
5. **Локальність + безкоштовно + LM Studio як primary** — незмінно.

### 🔧 Виправляємо / уточнюємо

1. **RestrictedPython** → краще **subprocess-sandbox з deny-list імпортів + Windows Job Object / resource limits**. RestrictedPython **не є** реальним security boundary (є задокументовані escape-и через `co_consts`, frame walking, `__subclasses__`). Для локального single-user-агента підійде як додатковий шар, але не як основний.
2. **AppAgent як окремий LLM-виклик** → у 80% випадків **вистачить одного LLM з AppProfile, вкладеним у prompt**. Окремий `AppAgent` = 2× токени + 2× latency + узгодження контексту. Робимо окремий `AppAgent` **тільки якщо** app-specific workflow не вміщується в 8k-ший prompt (Photoshop / Blender).
3. **Крок «Open Interpreter-like execution»** → це не фіча, а пачка з трьох: (a) pinned sandbox dir (cross-platform), (b) deny-list у `validate_code`, (c) resource limits через subprocess flags. Робимо як один PR.
4. **Playwright + existing Chrome profile** — небезпечно (конфлікт з активною сесією юзера, закриває його вкладки). Краще окремий `user-data-dir` у `~/.mark/chrome-profile/`, одноразовий login, потім reuse.

### ❌ Викидаємо / відкладаємо

1. **«AppAgent для 1000 програм»** — нереалістично. Робимо для **3 програм**: Chrome (через Playwright), File Explorer, один Office-app (Excel або PowerPoint). Решта — через generic GUI-Automation fallback.
2. **«Блокування детекту через Playwright»** (stealth-патерни) — виходить за межі «безпечного особистого агента». Якщо сайт блокує автоматизацію — це валідний сигнал, а не задача обходу.
3. **Спроби повного ізоляту через RestrictedPython** — як описано вище.

---

## 3. Roadmap — 6 тижнів, по одному PR за крок

Розмір PR підібрано так, щоб кожен був **self-contained, проходив CI, не ламав існуюче**.

### Phase 12 — Багаторівнева критика (тиждень 1-2)

| PR | Назва | Що | Залежить |
|----|-------|-----|-----|
| 12.1 | Step-Check | Додати `Task.expect: Optional[ExpectSpec]` — список перевірок (`file_exists`, `window_title_contains`, `stdout_contains`, `process_running`). `TaskRunner` автоматично перевіряє `expect` **перед** запуском тієї ж задачі (sanity: чи стан світу ще підходить) **і після** (Actor-Critic). Кидає `ExpectationFailed` → `on_error` logic. | PR #13 |
| 12.2 | Actor-Critic loop | Якщо `expect` після виконання не спрацював, викликати `repair_fn(task, before, after, expected)` через `ProviderRegistry`. LLM-repair отримує контекст і видає новий `Task`. Макс 2 спроби (config). | 12.1 |
| 12.3 | PlanCritic integration | Підключити `PlanCritic` з PR #15 у `core_planner` опційно (`enable_plan_critic: bool`). Зберігати критичні вердикти у `logs/critiques/*.json`. | PR #15 |

### Phase 13 — Безпечне виконання (тиждень 3)

| PR | Назва | Що |
|----|-------|-----|
| 13.1 | Sandbox hardening | (a) `SANDBOX_DIR` → `Path.home() / ".mark" / "sandbox"` (cross-platform); (b) увімкнути deny-list у `validate_code` (ast-based, не substring — `ast.walk` для `Import`/`Call`); (c) Windows Job Object через `pywin32` для memory/time limits; (d) subprocess stdlib-only, без мережі (env `NO_PROXY=*`, `https_proxy=`). |
| 13.2 | Sandbox optional RestrictedPython | Додати як **опційний** secondary layer (feature-flag `use_restricted_python=False` by default). Чесно задокументувати, що це не security boundary. |

### Phase 14 — Playwright-браузер (тиждень 4)

| PR | Назва | Що |
|----|-------|-----|
| 14.1 | `BrowserController` | Новий `functions/logic_browser_controller.py` з Playwright. API: `.open(url)`, `.click(selector)`, `.type(selector, text)`, `.screenshot()`, `.eval(js)`, `.text(selector)`. Persistent context у `~/.mark/chrome-profile/`. |
| 14.2 | `browser_*` handler-и для TaskRunner | `browser_open`, `browser_click`, `browser_type`, `browser_extract` — реєструються як handlers. Проходять через `PermissionGate` (domain-whitelist). |
| 14.3 | `GeminiProvider` / `WindsurfProvider` | AIProvider на базі BrowserController. Це реалізація J4 з попередніх обговорень, але вже на Playwright. |

### Phase 15 — AppAgent + розширені профілі (тиждень 5)

| PR | Назва | Що |
|----|-------|-----|
| 15.1 | Extended AppProfile schema | Додати до `core_app_profile.py`: `common_actions: Dict[str, ActionRecipe]` (з `gui_sequence` / `fallback_api` як у вашому прикладі), `ui_anchors: Dict[str, ImageAnchor]` (шлях до PNG + confidence), `wait_for: Dict[str, ExpectSpec]`. |
| 15.2 | AppAgent (single-LLM + profile injection) | `functions/logic_app_agent.py`. При виклику `plan_for_app(app_name, task)` — зчитує AppProfile, вкладає у prompt, викликає ProviderRegistry. Повертає `Plan`. Без окремих LLM-викликів за app. |
| 15.3 | Seed profiles | `chrome.json`, `explorer.json`, `powerpoint.json` — 3 базові профілі у `data/app_profiles/`. |

### Phase 16 — Інтеграція в GUI (тиждень 6)

| PR | Назва | Що |
|----|-------|-----|
| 16.1 | «Виконати план» UI | Кнопка в `core_gui`, яка викликає `review_and_run_plan(plan, critic, runner)`. Live-прогрес через `ExecutionReport`. |
| 16.2 | Manual review UI | Вкладка з історією `CritiqueResult` — показує вердикти, зауваження, таймінги. |

---

## 4. Ризики й пастки (читайте уважно)

### 4.1. `RestrictedPython` — НЕ security boundary

> Це спростиме те, що ви написали у стратегії. Не треба на нього розраховувати.

Відомі escape-и (публічні, з 2010-х):
- `().__class__.__base__.__subclasses__()` — доступ до всіх класів Python;
- інспекція `co_consts` скомпільованого коду;
- walk frame stack через `sys._getframe`;
- через `inspect` (якщо не заборонений) — доступ до чого завгодно.

Реальна ізоляція потребує **OS-level sandbox**: на Windows — Job Object + AppContainer, на Linux — `seccomp` + `nsenter`, або WASM (Pyodide). Subprocess з deny-list імпортів — **адекватний компроміс** для локального single-user-агента, але не для коду з інтернету.

**Рекомендація:** у PR 13.1 не використовувати `RestrictedPython` взагалі. Якщо дуже хочеться — у 13.2 як опційний secondary layer зі зрозумілим disclaim-ом у докстрингу.

### 4.2. Actor-Critic → нескінченний цикл

Класична помилка: repair-LLM видає план, який знову не проходить Actor-Critic → викликається repair → і т.д. Захист:
- жорсткий `max_repairs = 2` (default);
- `SessionBudget` як hard kill;
- після 2 невдалих repair — **підняти задачу до юзера** (через `ask_fn` у `PermissionGate`), не продовжувати автономно.

### 4.3. Playwright + user's Chrome profile

Якщо запустити Playwright на **активний** Chrome-профіль юзера:
- закриються всі його вкладки;
- потечуть cookies у логах автоматизації;
- можливий конфлікт з розширеннями юзера.

**Рекомендація:** окремий `~/.mark/chrome-profile/`. Юзер один раз логіниться у Gemini/ChatGPT там — далі агент reuse-ить його.

### 4.4. AppProfile як JSON — ризик desync

Якщо UI програми змінюється (Office update), `ui_anchors` стають невалідними → автоматизація мовчки ламається. Mitigation:
- перевіряти `image_match.confidence` проти порогу → якщо низька, піднімати `ExpectationFailed`;
- мати generic fallback (OCR по видимому тексту), якщо anchor не спрацював;
- у profile додати `version` + `last_verified_at` + warning у report якщо «застарілий» (>30 днів).

### 4.5. `Task.expect` — експресивність vs складність

Якщо `expect` занадто слабкий (`status_code==0`) — дає false positives. Занадто потужний (повний DSL) — важко генерувати LLM-ом.

**Рекомендація:** закритий список з 6-8 типів:
```
expect:
  - kind: file_exists       path: ./output/report.xlsx
  - kind: stdout_contains   value: "Saved"
  - kind: window_title_contains  value: "PowerPoint"
  - kind: process_running   name: "POWERPNT.EXE"
  - kind: http_status       url: http://localhost:1234  code: 200
  - kind: image_match       path: anchors/save_btn.png  confidence: 0.85
  - kind: counter_at_least  name: files_created  value: 3
  - kind: no_error_in_report
```

Все інше — через custom handler, але з гейтом на review.

### 4.6. LM Studio і function-calling

Не всі локальні моделі добре вміють function-calling. Qwen 2.5 Coder — так. Llama 3.1 — так. Phi — слабко. Якщо критик/planner нестабільний — проблема **моделі**, не архітектури.

**Mitigation:** у `ProviderRegistry` можна задати primary=LM Studio для дешевих задач, fallback=OpenAI-compatible cloud API для критичних (критика, repair). Це вже працює у PR #10.

---

## 5. Конфлікти з існуючим кодом

Що **обовʼязково** доведеться зачепити при реалізації roadmap:

| Новий модуль | Який існуючий чіпає | Як саме |
|----|----|----|
| Step-Check (12.1) | `functions/logic_task_runner.py` | Додаємо поле `Task.expect`. Міграція старих планів — `expect` optional, default []. Тести на зворотну сумісність. |
| Actor-Critic (12.2) | `functions/core_planner.py` | Існуючий `_repair()` конфліктує з новим `repair_fn` у TaskRunner. Пропозиція: залишити обидва — `_repair` для старого планера, `repair_fn` для нового пайплайну. Не зливати примусово. |
| Sandbox hardening (13.1) | `functions/aaa_execute_python.py`, `functions/safety_sandbox.py`, `functions/core_safety_sandbox.py` | У репо **три** sandbox-модулі. Перед рефактором потрібна консолідація — залишити один, два задепрекати. Великий диф. |
| BrowserController (14.1) | `functions/aaa_open_browser.py` | Поточний `open_browser` через `webbrowser` — залишити для simple-use. Playwright — окремий набір tools з префіксом `browser_*`. Без взаємного конфлікту. |
| Extended AppProfile (15.1) | `functions/core_app_profile.py` | Міграція старого `workflows` → `common_actions`. Простий, але ламає стару серіалізацію. Потрібен `schema_version` + upgrade-функція. |
| AppAgent (15.2) | `functions/core_planner.py` | Планер має вміти делегувати частину плану до AppAgent. Чистий додаток — не ламає нічого. |
| GUI-integration (16.1) | `core_gui/*` | Це найбільший ризик конфліктів — UI-модулі активно використовуються. Робити на окремій гілці з live-перевіркою на Windows. |

**Порядок мержу** з точки зору найменшого ризику:
```
12.1 → 12.2 → 12.3 (всі поверх PR #13+#15)
   ↓
13.1 (окремо — консолідація sandbox)
   ↓
14.1 → 14.2 → 14.3 (Playwright трек)
   ↓
15.1 → 15.2 → 15.3 (AppAgent трек)
   ↓
16.1 → 16.2 (GUI integration)
```

---

## 6. Приклад з вашого повідомлення — як він пройде через нову архітектуру

> «Поговори з Gemini про погоду, збери дані, зроби презентацію»

```
1. USER prompt → core_planner → generates Plan:
    t1 browser_open        url=https://gemini.google.com       expect: window_title_contains="Gemini"
    t2 browser_type        selector=textarea  text="weather ..."  expect: element_visible="response"
    t3 browser_extract     selector=table  save_to=./weather.html   expect: file_exists=./weather.html
    t4 execute_python      code="parse_html('./weather.html', ...)" expect: file_exists=./weather.xlsx
    t5 app_delegate        app=PowerPoint  action=create_chart_slides
                           params={xlsx: ./weather.xlsx}
                           expect: file_exists=./output/weather.pptx

2. PlanCritic.review(plan) → verdict=approve
     (якщо concerns → попередження в звіті; якщо redo → _repair)

3. TaskRunner.run:
     for each t:
        PermissionGate.check   (13.1 whitelist)
        [pre] Step-Check: чи actual state match expect.preconditions (якщо задано)
        handler(t)
        [post] Actor-Critic: чи expect спрацював
           └─ ні → repair_fn → max 2 retry → якщо все одно ні → stop + report

4. ExecutionReport.to_markdown()  — тезисний звіт з таймінгами
   (те, що ви просили у попередньому повідомленні про рефакторинг × 3)
```

Без Actor-Critic крок t5 (PowerPoint) міг би мовчки створити порожню презентацію — `subprocess.returncode=0`, ExecutionReport сказав би «OK», але реальний `.pptx` — некоректний. З Actor-Critic — автоматичне виявлення + repair.

---

## 7. Що рекомендую як **наступний PR**

**Phase 12.1 — Step-Check + `Task.expect`.** Це:
- найменший обсяг коду (~300 LoC) серед фаз;
- **не ламає** нічого (поле optional);
- одразу дає 40% користі від повного Actor-Critic (бо LLM сам починає генерувати очікувані стани — це покращує якість plan-у);
- розблоковує всі наступні фази (Actor-Critic, AppAgent build on top).

Якщо погоджуєтесь — беру цю фазу наступною.

---

*Документ live. Правки — у окремому PR або напряму в `status.md` після мержу.*
