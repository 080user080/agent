"""Convert stubs from sys.modules aliasing to direct re-export."""
import os

# Mapping: stub_name -> subpackage
STUBS = {
    "agent_loop": "planning", "core_planner": "planning",
    "core_plan_compiler": "planning", "core_planner_critic": "planning",
    "core_planner_runner": "planning", "logic_task_runner": "planning",
    "logic_expectations": "planning", "task_spec": "planning",
    "core_tool_runtime": "runtime", "core_settings": "runtime",
    "core_memory": "runtime", "core_cache": "runtime",
    "core_session_budget": "runtime", "core_undo_manager": "runtime",
    "core_action_recorder": "runtime",
    "core_gui_guardian": "gui", "tools_screen_capture": "gui",
    "tools_ocr": "gui", "tools_mouse_keyboard": "gui",
    "tools_window_manager": "gui", "tools_ui_detector": "gui",
    "tools_ui_accessibility": "gui", "tools_visual_diff": "gui",
    "voice_tray_icon": "gui",
    "tools_app_recognizer": "tools", "tools_browser_cdp": "tools",
    "tools_comfyui": "tools", "tools_excel": "tools",
    "tools_ffmpeg": "tools", "tools_image_pillow": "tools",
    "tools_notification": "tools", "tools_pdf": "tools",
    "tools_playwright": "tools", "tools_windsurf": "tools",
    "tools_word": "tools",
    "aaa_architect": "tools", "aaa_code_tools": "tools",
    "aaa_confirmation": "tools", "aaa_create_file": "tools",
    "aaa_debug_code": "tools", "aaa_edit_file": "tools",
    "aaa_execute_python": "tools", "aaa_file_operations": "tools",
    "aaa_help": "tools", "aaa_open_browser": "tools",
    "aaa_open_interpreter": "tools", "aaa_programs": "tools",
    "aaa_system": "tools", "aaa_utility_tools": "tools",
    "aaa_voice_input": "tools",
}

base = r'd:\Python\agent\functions'
for name, subpkg in STUBS.items():
    path = os.path.join(base, f'{name}.py')
    # Use import * instead of sys.modules aliasing
    content = (
        f'# Re-export after A2 restructuring\n'
        f'from functions.{subpkg}.{name} import *  # noqa: F401, F403\n'
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Fixed: functions/{name}.py')

print('All stubs fixed')