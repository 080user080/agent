# functions/llm/__init__.py
"""LLM layer package — забезпечує зворотну сумісність через адаптер helpers."""

from functions.llm.helpers import ask_llm
from functions.llm.response_parser import process_llm_response
from functions.llm.endpoint_client import get_primary_endpoint, call_endpoint
from functions.llm.streaming_buffer import StreamingBuffer
