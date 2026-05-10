"""
Інтеграційний тест для Open Interpreter (self-healing executor).

Цей тест перевіряє, чи OI дійсно встановлює відсутні модулі і виконує код.

Вимоги:
1. LM Studio запущений на http://localhost:1234
2. OI_ENABLED=True в налаштуваннях
3. open-interpreter встановлено

Запуск:
    python TEST_OI_INTEGRATION.py
"""
import sys
from pathlib import Path

# Додаємо проект в path
sys.path.insert(0, str(Path(__file__).parent))

from functions.core_settings import set_setting, get_setting
from functions.aaa_execute_python import execute_python


def test_oi_module_not_found():
    """Тест: OI автоматично встановить відсутній модуль."""
    print("=" * 60)
    print("Тест Open Interpreter: ModuleNotFoundError → auto-install")
    print("=" * 60)
    
    # Увімкнути OI
    set_setting("OI_ENABLED", True)
    print(f"\n✓ OI_ENABLED = {get_setting('OI_ENABLED')}")
    
    # Код, який вимагає модуль, якого немає
    # Використаємо рідкісний модуль, щоб не вплинути на систему
    code = """
import colorama
from colorama import Fore, Back, Style
print(f"{Fore.GREEN}✅ colorama успішно імпортовано!")
print(f"Версія: {colorama.__version__ if hasattr(colorama, '__version__') else 'unknown'}")
"""
    
    print("\n📝 Виконую код з import colorama...")
    print("-" * 60)
    
    result = execute_python(code)
    
    print("-" * 60)
    print(f"\n📊 Результат:")
    print(f"  Success: {result.get('ok')}")
    print(f"  Output:\n{result.get('message', 'N/A')}")
    
    if result.get('ok'):
        print("\n✅ ТЕСТ ПРОЙДЕНО: OI успішно встановив модуль і виконав код")
        return True
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕНО:")
        print(f"  Error: {result.get('error', 'N/A')}")
        return False


def test_oi_already_installed():
    """Тест: Код з вже встановленим модулем працює без OI."""
    print("\n" + "=" * 60)
    print("Тест Open Interpreter: вже встановлений модуль")
    print("=" * 60)
    
    # Код з модулем, який точно є
    code = """
import json
data = {"test": "value"}
print(f"JSON: {json.dumps(data)}")
"""
    
    print("\n📝 Виконую код з import json...")
    print("-" * 60)
    
    result = execute_python(code)
    
    print("-" * 60)
    print(f"\n📊 Результат:")
    print(f"  Success: {result.get('ok')}")
    print(f"  Output:\n{result.get('message', 'N/A')}")
    
    if result.get('ok'):
        print("\n✅ ТЕСТ ПРОЙДЕНО: код виконався без проблем")
        return True
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕНО:")
        print(f"  Error: {result.get('error', 'N/A')}")
        return False


def test_oi_disabled():
    """Тест: OI вимкнено - ModuleNotFoundError не виправляється."""
    print("\n" + "=" * 60)
    print("Тест Open Interpreter: OI вимкнено")
    print("=" * 60)
    
    # Вимкнути OI
    set_setting("OI_ENABLED", False)
    print(f"\n✓ OI_ENABLED = {get_setting('OI_ENABLED')}")
    
    # Код з відсутнім модулем
    code = """
import nonexistent_module_xyz
print("This should not execute")
"""
    
    print("\n📝 Виконую код з import nonexistent_module_xyz...")
    print("-" * 60)
    
    result = execute_python(code)
    
    print("-" * 60)
    print(f"\n📊 Результат:")
    print(f"  Success: {result.get('ok')}")
    print(f"  Output:\n{result.get('message', 'N/A')}")
    
    if not result.get('ok'):
        print("\n✅ ТЕСТ ПРОЙДЕНО: код провалився як очікувано (OI вимкнено)")
        return True
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕНО: код не повинен був виконатися")
        return False


def main():
    """Запустити всі тести."""
    print("\n" + "=" * 60)
    print("ІНТЕГРАЦІЙНІ ТЕСТИ ДЛЯ OPEN INTERPRETER")
    print("=" * 60)
    
    # Перевірка передумов
    print("\n🔍 Перевірка передумов...")
    
    try:
        from interpreter import interpreter
        print("✓ open-interpreter встановлено")
    except ImportError:
        print("❌ open-interpreter НЕ встановлено")
        print("Встановіть: pip install open-interpreter")
        return
    
    # Запуск тестів
    results = []
    
    # Тест 1: вже встановлений модуль
    results.append(("Тест 1: вже встановлений модуль", test_oi_already_installed()))
    
    # Тест 2: OI вимкнено
    results.append(("Тест 2: OI вимкнено", test_oi_disabled()))
    
    # Тест 3: OI увімкнено + ModuleNotFoundError
    results.append(("Тест 3: OI auto-install", test_oi_module_not_found()))
    
    # Підсумок
    print("\n" + "=" * 60)
    print("ПІДСУМОК")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nВсього: {passed}/{total} тестів пройдено")
    
    # Відновити налаштування
    set_setting("OI_ENABLED", False)
    print(f"\n✓ OI_ENABLED відновлено на False")


if __name__ == "__main__":
    main()
