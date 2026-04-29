import ast
import json
import os
import re

import requests
from colorama import Fore

from .config import LM_STUDIO_URL
from .core_tool_runtime import make_tool_result

CODE_TEMPLATE = '''import os
import sys
import subprocess
import time
import ctypes

def llm_function(name, description, parameters):
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

@llm_function(
    name="{FUNC_NAME}",
    description="{FUNC_DESC}",
    parameters={FUNC_PARAMS}
)
def {FUNC_NAME}({FUNC_ARGS}):
    """{FUNC_DESC}"""
    try:
{FUNC_BODY}
        return "✅ Дія виконана успішно"
    except Exception as e:
        return f"❌ Помилка у новій навичці: {{str(e)}}"
'''

FORBIDDEN_IMPORTS = ["torch", "tensorflow", "cuda", "nvidia", "shutil.rmtree"]


def fix_indentation(code_body, spaces=8):
    lines = code_body.strip().split("\n")
    indented_lines = [(" " * spaces) + line for line in lines]
    return "\n".join(indented_lines)


def validate_code(code):
    for bad_word in FORBIDDEN_IMPORTS:
        if bad_word in code:
            return False, f"Заборонено: {bad_word}"
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"Синтаксис: {e}"
    return True, "OK"


def llm_function_reg(name, description, parameters):
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator


@llm_function_reg(
    name="create_skill",
    description="Створити нову навичку Python для Windows",
    parameters={"task_description": "Що має робити код"},
)
def create_skill(task_description):
    print(f"{Fore.MAGENTA}🏗️  Архітектор: Генерую рішення для: {task_description}")

    system_prompt = f"""Write Python code for: {task_description}.
    Return ONLY JSON with these fields:
    "name": "snake_case_name",
    "args": "",
    "params": {{}},
    "body": "python code without indentation. Use ctypes or subprocess."
    """

    try:
        response = requests.post(
            LM_STUDIO_URL,
            json={
                "messages": [{"role": "system", "content": system_prompt}],
                "temperature": 0.1,
            },
            timeout=30,
        )

        raw_content = response.json()["choices"][0]["message"]["content"]
        json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)

        if not json_match:
            return make_tool_result(False, "❌ ЛЛМ не надала JSON формат.", error="invalid_llm_response", retryable=True)

        data = json.loads(json_match.group(0))
        raw_body = data.get("body", "pass")
        formatted_body = fix_indentation(raw_body, spaces=8)

        full_code = CODE_TEMPLATE.format(
            FUNC_NAME=data.get("name", "new_skill"),
            FUNC_DESC=task_description,
            FUNC_PARAMS=json.dumps(data.get("params", {}), ensure_ascii=False),
            FUNC_ARGS=data.get("args", ""),
            FUNC_BODY=formatted_body,
        )

        ok, err = validate_code(full_code)
        if not ok:
            return make_tool_result(False, f"🚫 Безпека: {err}", error=err)

        filename = f"aaa_{data.get('name', 'skill')}.py"
        path = os.path.join(os.path.dirname(__file__), filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(full_code)

        from .logic_core import global_registry
        refreshed = False
        if global_registry:
            global_registry.refresh()
            refreshed = True

        return make_tool_result(
            True,
            f"✅ Навичка {filename} готова! Спробуйте: {data.get('name')}",
            data={"filename": filename, "path": path, "refreshed_registry": refreshed},
        )

    except Exception as e:
        return make_tool_result(False, f"❌ Помилка: {type(e).__name__} - {str(e)}", error=str(e), retryable=True)
