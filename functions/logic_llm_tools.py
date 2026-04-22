"""OpenAI-compatible tool-calling / JSON mode для legacy LLM-стеку (`logic_llm`).

Це адитивний шар **поверх** існуючого `logic_llm.ask_llm`:

- `ask_llm` лишається незмінним і використовує self-parsed JSON
  (`extract_json_from_text` + `process_llm_response`).
- `ask_llm_with_tools` — новий вхід, який передає OpenAI-compatible
  `tools` / `response_format` прямо в payload і повертає структуровану
  відповідь з `tool_calls` (без regex-парсингу).

Мотивація (F1 з трека F у status.md):
  «Замість самописного JSON-парсингу перейти на OpenAI-compatible
  `tools` параметр (LM Studio ≥ 0.3.x підтримує). Підвищить надійність
  планів на ~10–20%.»

Повністю backward-compatible. Legacy код продовжує працювати без змін.
Новий код може опційно обирати tool-calling path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import requests

# Re-використовуємо endpoint-розвʼязання зі старого модуля.
from .logic_llm import get_primary_endpoint


# --------------------------------------------------------------------------- #
# Структури результату                                                        #
# --------------------------------------------------------------------------- #

@dataclass
class ToolCall:
    """Один виклик інструменту, розпарсений з `choices[].message.tool_calls`."""

    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "arguments": dict(self.arguments), "id": self.id}


@dataclass
class ToolExecutionResult:
    """Результат виконання одного `ToolCall` через `FunctionRegistry`."""

    name: str
    ok: bool
    result: Any = None
    error: str = ""
    call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "result": self.result,
            "error": self.error,
            "call_id": self.call_id,
        }


@dataclass
class ChatToolsResponse:
    """Відповідь `ask_llm_with_tools` у структурованому вигляді."""

    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    model: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    http_status: Optional[int] = None

    @property
    def ok(self) -> bool:
        return not self.error and self.http_status in (None, 200)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "finish_reason": self.finish_reason,
            "model": self.model,
            "usage": dict(self.usage),
            "error": self.error,
            "http_status": self.http_status,
        }


# --------------------------------------------------------------------------- #
# Побудова tool-специфікацій                                                  #
# --------------------------------------------------------------------------- #

def build_tool_spec(
    name: str,
    description: str = "",
    parameters: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Сформувати один запис у форматі OpenAI `tools` param.

    Якщо `parameters` не передано — використовується порожня object-схема.
    """
    schema: Dict[str, Any] = dict(parameters) if parameters else {"type": "object"}
    if "type" not in schema:
        schema = {"type": "object", **schema}
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description or "",
            "parameters": schema,
        },
    }


def functions_to_tools(
    functions_map: Mapping[str, Mapping[str, Any]],
    *,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Сконвертувати `{name: {name, description, parameters}}` → OpenAI tools list.

    Приймає структуру, аналогічну `FunctionRegistry.functions`.
    Фільтрує за `include` / `exclude` (якщо задані).
    Пропускає записи без `name`.
    """
    include_set = set(include) if include is not None else None
    exclude_set = set(exclude) if exclude is not None else set()

    tools: List[Dict[str, Any]] = []
    for key, info in (functions_map or {}).items():
        if not isinstance(info, Mapping):
            continue
        name = info.get("name") or key
        if not name:
            continue
        if include_set is not None and name not in include_set:
            continue
        if name in exclude_set:
            continue
        tools.append(
            build_tool_spec(
                name=name,
                description=str(info.get("description") or ""),
                parameters=info.get("parameters") or {},
            )
        )
    return tools


def registry_to_tools(
    registry: Any,
    *,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Convenience-обгортка: дістати `.functions` з `FunctionRegistry` й конвертувати."""
    functions_map = getattr(registry, "functions", None) or {}
    return functions_to_tools(functions_map, include=include, exclude=exclude)


# --------------------------------------------------------------------------- #
# Парсинг відповіді                                                           #
# --------------------------------------------------------------------------- #

def _parse_arguments(raw: Any) -> Dict[str, Any]:
    """OpenAI спек каже що `arguments` — це JSON-рядок. Але деякі LLM
    (LM Studio, Ollama) повертають вже розпарсений об'єкт. Підтримуємо обидва.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        try:
            decoded = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {"_raw": raw}
        if isinstance(decoded, dict):
            return decoded
        return {"_value": decoded}
    return {"_raw": str(raw)}


def parse_tool_calls_from_body(body: Mapping[str, Any]) -> List[ToolCall]:
    """Витягти список `ToolCall` з OpenAI-compatible response body.

    Стійкий до відсутніх полів. Повертає `[]` якщо tool_calls немає.
    """
    if not isinstance(body, Mapping):
        return []
    choices = body.get("choices") or []
    if not isinstance(choices, list) or not choices:
        return []
    first = choices[0] if isinstance(choices[0], Mapping) else {}
    message = first.get("message") or {}
    if not isinstance(message, Mapping):
        return []

    out: List[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        if not isinstance(tc, Mapping):
            continue
        fn = tc.get("function") or {}
        if not isinstance(fn, Mapping):
            fn = {}
        name = str(fn.get("name") or tc.get("name") or "").strip()
        if not name:
            continue
        args = _parse_arguments(fn.get("arguments", tc.get("arguments")))
        out.append(ToolCall(name=name, arguments=args, id=tc.get("id")))
    return out


# --------------------------------------------------------------------------- #
# Головна функція запиту                                                      #
# --------------------------------------------------------------------------- #

def ask_llm_with_tools(
    messages: Sequence[Mapping[str, Any]],
    tools: Optional[Sequence[Mapping[str, Any]]] = None,
    *,
    tool_choice: Optional[Any] = None,
    response_format: Optional[Any] = None,
    endpoint: Optional[Mapping[str, Any]] = None,
    extra_payload: Optional[Mapping[str, Any]] = None,
    request_fn: Callable[..., Any] = requests.post,
) -> ChatToolsResponse:
    """Відправити запит до LLM endpoint з OpenAI-compatible `tools` / `response_format`.

    На відміну від `logic_llm.ask_llm`:
    - не склеює system-prompt + history — приймає готовий `messages`;
    - не робить regex-парсинг — повертає структуровані `tool_calls`;
    - не форматує user-facing помилки — залишає `error` як машиночитний рядок.

    Args:
      messages: список `{"role": ..., "content": ...}` (система/користувач/асистент/tool).
      tools: список OpenAI-format tool-описів (див. `build_tool_spec`).
      tool_choice: `"auto" | "none" | {"type": "function", "function": {"name": "..."}}`.
      response_format: `{"type": "json_object"}` або `{"type": "json_schema", "json_schema": {...}}`.
      endpoint: кастомний endpoint-dict; якщо None — `get_primary_endpoint()`.
      extra_payload: будь-які додаткові поля для payload (напр. `top_p`, `seed`).
      request_fn: для тестів — мокаємо без мережі.
    """
    ep = dict(endpoint) if endpoint else get_primary_endpoint()

    payload: Dict[str, Any] = {
        "model": ep.get("model", "local-model"),
        "messages": [dict(m) for m in messages],
        "temperature": ep.get("temperature", 0.1),
        "max_tokens": ep.get("max_tokens", 1024),
        "stream": False,
    }
    if tools:
        payload["tools"] = [dict(t) for t in tools]
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if response_format is not None:
        payload["response_format"] = response_format
    if extra_payload:
        for k, v in extra_payload.items():
            payload.setdefault(k, v)

    headers = {"Content-Type": "application/json"}
    api_key = ep.get("api_key") or ""
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = request_fn(
            ep.get("url"),
            headers=headers,
            json=payload,
            timeout=ep.get("timeout", 60),
        )
    except requests.exceptions.RequestException as exc:
        return ChatToolsResponse(error=f"network: {exc}", raw={})
    except Exception as exc:  # noqa: BLE001
        return ChatToolsResponse(error=f"unexpected: {exc}", raw={})

    status = getattr(response, "status_code", None)
    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001
        return ChatToolsResponse(
            http_status=status,
            error=f"bad json body: {exc}",
            raw={"text": getattr(response, "text", "")[:500]},
        )

    if status != 200:
        err_msg = ""
        if isinstance(body, Mapping):
            err_block = body.get("error")
            if isinstance(err_block, Mapping):
                err_msg = str(err_block.get("message") or err_block.get("type") or "")
            elif isinstance(err_block, str):
                err_msg = err_block
        return ChatToolsResponse(
            http_status=status,
            error=f"http {status}{': ' + err_msg if err_msg else ''}",
            raw=body if isinstance(body, dict) else {},
        )

    if not isinstance(body, Mapping):
        return ChatToolsResponse(
            http_status=status,
            error=f"bad payload shape: {type(body).__name__}",
            raw={},
        )

    choices = body.get("choices") or []
    if not choices:
        return ChatToolsResponse(
            http_status=status,
            error="no choices in response",
            raw=dict(body),
        )

    first = choices[0] if isinstance(choices[0], Mapping) else {}
    message = first.get("message") or {}
    content = ""
    if isinstance(message, Mapping):
        maybe_content = message.get("content")
        content = str(maybe_content) if maybe_content is not None else ""
    finish_reason = str(first.get("finish_reason") or "")
    tool_calls = parse_tool_calls_from_body(body)
    usage = dict(body.get("usage") or {}) if isinstance(body.get("usage"), Mapping) else {}
    model = str(body.get("model") or payload["model"])

    return ChatToolsResponse(
        content=content,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        model=model,
        usage=usage,
        raw=dict(body),
        http_status=status,
    )


# --------------------------------------------------------------------------- #
# Виконання tool_calls                                                        #
# --------------------------------------------------------------------------- #

def execute_tool_calls(
    tool_calls: Sequence[ToolCall],
    registry: Any,
    *,
    name_alias: Optional[Mapping[str, str]] = None,
) -> List[ToolExecutionResult]:
    """Виконати список `ToolCall` через `registry.execute_function(name, params)`.

    Стійкий до помилок окремих викликів — кожен інкапсульований у try/except.
    `name_alias` дозволяє мапити alias → реальне ім'я (напр. `execute_python_code → execute_python`).
    """
    alias = dict(name_alias or {})
    results: List[ToolExecutionResult] = []
    for tc in tool_calls:
        real_name = alias.get(tc.name, tc.name)
        try:
            fn_result = registry.execute_function(real_name, dict(tc.arguments))
            results.append(
                ToolExecutionResult(
                    name=real_name,
                    ok=True,
                    result=fn_result,
                    call_id=tc.id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                ToolExecutionResult(
                    name=real_name,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                    call_id=tc.id,
                )
            )
    return results


def tool_results_to_messages(
    tool_calls: Sequence[ToolCall],
    results: Sequence[ToolExecutionResult],
) -> List[Dict[str, Any]]:
    """Сформувати `role="tool"` повідомлення для наступного turn-а LLM.

    Згідно з OpenAI-спеком: кожне `tool`-повідомлення має `tool_call_id`
    й `name`. `content` — серіалізований результат виклику (str або JSON).
    """
    # Індексуємо результати за call_id для точного матчингу (fallback — за порядком).
    by_id: Dict[str, ToolExecutionResult] = {
        r.call_id: r for r in results if r.call_id
    }
    out: List[Dict[str, Any]] = []
    for idx, tc in enumerate(tool_calls):
        result = by_id.get(tc.id) if tc.id else None
        if result is None and idx < len(results):
            result = results[idx]
        if result is None:
            continue
        if result.ok:
            content = _serialize_tool_result(result.result)
        else:
            content = json.dumps(
                {"error": result.error, "ok": False}, ensure_ascii=False
            )
        out.append(
            {
                "role": "tool",
                "tool_call_id": tc.id or f"call_{idx}",
                "name": result.name,
                "content": content,
            }
        )
    return out


def _serialize_tool_result(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return str(value)


__all__ = [
    "ChatToolsResponse",
    "ToolCall",
    "ToolExecutionResult",
    "ask_llm_with_tools",
    "build_tool_spec",
    "execute_tool_calls",
    "functions_to_tools",
    "parse_tool_calls_from_body",
    "registry_to_tools",
    "tool_results_to_messages",
]
