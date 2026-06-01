# functions/gui/__init__.py
"""GUI-модулі для PyQt6 інтерфейсу МАРК."""

from .commands_streaming import StreamingBuffer, stream_llm_response
from .commands_audio import (
    set_tts_engine,
    should_speak_response,
    extract_speakable_text,
    filter_code_for_tts,
    speak_response,
    speak_response_async,
    speak_if_possible,
)
from .commands_planner import (
    classify_task,
    execute_direct,
    extract_python_code,
    run_agent_loop,
    run_agent_loop_for_voice,
    run_pending_plan,
    stop_plan_execution,
)
