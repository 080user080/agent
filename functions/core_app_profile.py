"""AppProfile — профілі програм (Phase 7 фундамент).

Зберігає специфіку окремих Windows-програм (exe, відомі горячі клавіші,
«знайомі» UI-елементи, типові workflow-и), щоб агент міг впевнено
взаємодіяти з ними без повторного розпізнавання з нуля.

Design:
- Один `AppProfile` dataclass = один файл JSON у `profiles_dir`.
- `AppProfileRegistry` = реєстр із lazy-load у пам'яті + збереження на диск.
- Вбудовані seed-профілі (Notepad / Explorer / Chrome / Paint) повертаються,
  навіть якщо файл ще не створено. Після `save()` вони стають звичайними
  файлами у `profiles_dir` і далі можуть редагуватися користувачем.

Модуль свідомо без залежностей від Windows API — це чистий data-layer,
який можна тестувати і запускати на Linux CI.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Dataclass: AppProfile
# ---------------------------------------------------------------------------


@dataclass
class UIElement:
    """Відомий UI-елемент у програмі.

    Attributes:
        name: Логічна назва (`save_button`, `file_menu`, ...).
        description: Опис людською мовою (ua).
        hints: Підказки для розпізнавання — ключові слова OCR, координати,
            приблизне розташування тощо. Словник щоб не плодити поля.
    """

    name: str
    description: str = ""
    hints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    """Іменований сценарій: послідовність кроків-дій.

    Кроки описуються як `{"action": str, "params": {...}}`, щоб можна було
    одразу передавати у `core_executor` / `TaskExecutor`.
    """

    name: str
    description: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AppProfile:
    """Профіль окремої програми."""

    app_name: str
    exe_path: str = ""
    window_title_pattern: str = ""  # regex / substring для пошуку вікна
    common_shortcuts: Dict[str, str] = field(default_factory=dict)
    known_elements: List[UIElement] = field(default_factory=list)
    workflows: List[Workflow] = field(default_factory=list)
    notes: str = ""

    # ----- Serialization --------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppProfile":
        elements = [UIElement(**e) for e in data.get("known_elements", [])]
        workflows = [Workflow(**w) for w in data.get("workflows", [])]
        return cls(
            app_name=data["app_name"],
            exe_path=data.get("exe_path", ""),
            window_title_pattern=data.get("window_title_pattern", ""),
            common_shortcuts=dict(data.get("common_shortcuts", {})),
            known_elements=elements,
            workflows=workflows,
            notes=data.get("notes", ""),
        )

    # ----- Helpers --------------------------------------------------------

    def add_shortcut(self, name: str, keys: str) -> None:
        self.common_shortcuts[name] = keys

    def add_element(self, element: UIElement) -> None:
        # Якщо вже є елемент із такою назвою — оновлюємо, не дублюємо.
        for i, existing in enumerate(self.known_elements):
            if existing.name == element.name:
                self.known_elements[i] = element
                return
        self.known_elements.append(element)

    def add_workflow(self, workflow: Workflow) -> None:
        for i, existing in enumerate(self.workflows):
            if existing.name == workflow.name:
                self.workflows[i] = workflow
                return
        self.workflows.append(workflow)

    def find_element(self, name: str) -> Optional[UIElement]:
        for element in self.known_elements:
            if element.name == name:
                return element
        return None

    def find_workflow(self, name: str) -> Optional[Workflow]:
        for workflow in self.workflows:
            if workflow.name == name:
                return workflow
        return None


# ---------------------------------------------------------------------------
# Built-in seeds
# ---------------------------------------------------------------------------


def _seed_profiles() -> Dict[str, AppProfile]:
    """Повертає вбудовані профілі для найпоширеніших програм.

    Значення свідомо прості — це стартова точка, яку користувач може
    доповнити через `learn_from_interaction()` або вручну.
    """
    return {
        "notepad": AppProfile(
            app_name="notepad",
            exe_path="notepad.exe",
            window_title_pattern=r".*Notepad$",
            common_shortcuts={
                "new_file": "ctrl+n",
                "open_file": "ctrl+o",
                "save_file": "ctrl+s",
                "save_as": "ctrl+shift+s",
                "find": "ctrl+f",
                "select_all": "ctrl+a",
            },
            notes="Стандартний блокнот Windows.",
        ),
        "explorer": AppProfile(
            app_name="explorer",
            exe_path="explorer.exe",
            window_title_pattern=r".*Explorer$",
            common_shortcuts={
                "new_folder": "ctrl+shift+n",
                "address_bar": "ctrl+l",
                "refresh": "f5",
                "delete": "delete",
                "rename": "f2",
            },
            notes="Провідник Windows.",
        ),
        "chrome": AppProfile(
            app_name="chrome",
            exe_path="chrome.exe",
            window_title_pattern=r".*Google Chrome$",
            common_shortcuts={
                "new_tab": "ctrl+t",
                "close_tab": "ctrl+w",
                "reopen_tab": "ctrl+shift+t",
                "address_bar": "ctrl+l",
                "refresh": "f5",
                "find_on_page": "ctrl+f",
                "devtools": "f12",
            },
            notes="Google Chrome / Chromium-базовані браузери.",
        ),
        "paint": AppProfile(
            app_name="paint",
            exe_path="mspaint.exe",
            window_title_pattern=r".*Paint$",
            common_shortcuts={
                "new_canvas": "ctrl+n",
                "save": "ctrl+s",
                "undo": "ctrl+z",
                "redo": "ctrl+y",
                "select_all": "ctrl+a",
            },
            notes="Microsoft Paint (mspaint).",
        ),
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class AppProfileRegistry:
    """Реєстр профілів програм із персистенцією у JSON.

    Працює так:
    - Перший доступ (`get`, `list_profiles`) мержить seeds + диск.
    - `save_profile` пише JSON у `profiles_dir/{name}.json`.
    - `learn_from_interaction` — легка hook-точка для майбутнього
      `logic_task_learner` (поки тільки лог у `notes`).
    """

    def __init__(self, profiles_dir: str | Path = "profiles"):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, AppProfile] = {}
        self._loaded = False

    # ----- Loading --------------------------------------------------------

    def _load_all(self) -> None:
        if self._loaded:
            return
        # 1) seeds (тільки ті, яких немає на диску).
        for name, profile in _seed_profiles().items():
            self._profiles[name] = profile
        # 2) файли з диску перевизначають seeds.
        for path in self.profiles_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile = AppProfile.from_dict(data)
                self._profiles[profile.app_name] = profile
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                print(f"[AppProfileRegistry] Skipping {path}: {exc}")
        self._loaded = True

    # ----- Public API -----------------------------------------------------

    def get(self, app_name: str) -> Optional[AppProfile]:
        self._load_all()
        return self._profiles.get(app_name.lower())

    def list_profiles(self) -> List[AppProfile]:
        self._load_all()
        return list(self._profiles.values())

    def save_profile(self, profile: AppProfile) -> Path:
        self._load_all()
        self._profiles[profile.app_name.lower()] = profile
        path = self.profiles_dir / f"{profile.app_name.lower()}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def delete_profile(self, app_name: str) -> bool:
        self._load_all()
        key = app_name.lower()
        if key not in self._profiles:
            return False
        self._profiles.pop(key, None)
        path = self.profiles_dir / f"{key}.json"
        if path.exists():
            path.unlink()
        return True

    def learn_from_interaction(
        self,
        app_name: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> AppProfile:
        """Легкий hook — додає запис у `notes` профілю (або створює новий).

        Повертає оновлений профіль. Повноцінна pattern-detection логіка
        винесена у `logic_task_learner` (D3 у roadmap).
        """
        self._load_all()
        key = app_name.lower()
        profile = self._profiles.get(key) or AppProfile(app_name=key)
        note_line = f"[{action}] ok={success} params={params or {}}"
        profile.notes = (profile.notes + "\n" + note_line).strip()
        self._profiles[key] = profile
        return profile
