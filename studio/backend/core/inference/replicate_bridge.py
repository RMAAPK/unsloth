import json
import httpx
from typing import Any, AsyncGenerator, Optional
import litellm


async def stream_replicate(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    messages: list[dict[str, Any]],
    model: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[list[dict]] = None,
) -> AsyncGenerator[str, None]:
    auth_header = headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()

    if not model.startswith("replicate/"):
        model = f"replicate/{model}"

    if tools:
        # Replicate's Llama 3 drops native tool schemas, so we must inject them into the system prompt
        tool_docs = []
        for t in tools:
            if t.get("type") == "function":
                f = t["function"]
                tool_docs.append(
                    {
                        "name": f.get("name"),
                        "description": f.get("description"),
                        "parameters": f.get("parameters"),
                    }
                )
            else:
                tool_docs.append(t)

        system_injection = (
            "\n\n[SYSTEM TOOLING ENGINE ENABLED]\n"
            "You have access to the following server-side tools. To execute a tool, YOU MUST output a RAW JSON object representing the call, and NOTHING ELSE in that block.\n"
            'Format: {"name": "tool_name", "parameters": {"arg": "val"}}\n'
            f"Available Tools: {json.dumps(tool_docs)}\n"
        )

        # Inject into system prompt
        for m in messages:
            if m.get("role") == "system":
                m["content"] = str(m.get("content", "")) + system_injection
                break
        else:
            messages.insert(0, {"role": "system", "content": system_injection})

    try:
        kwargs = {"model": model, "messages": messages, "stream": True, "api_key": token}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        # We don't pass kwargs["tools"] = tools to litellm because litellm throws it away for this model anyway,
        # and if it did support it, it might clash with our system prompt injection.

        response = await litellm.acompletion(**kwargs)

        async for chunk in response:
            try:
                chunk_str = chunk.model_dump_json()
            except Exception:
                try:
                    chunk_str = chunk.json()
                except Exception:
                    chunk_str = json.dumps(dict(chunk))
            yield f"data: {chunk_str}"

        yield "data: [DONE]"
    except Exception as e:
        error_msg = f"\\n\\n[LITELLM ERROR: {str(e)}]"
        yield f"data: {json.dumps({'choices': [{'delta': {'content': error_msg}}]})}"
        yield "data: [DONE]"
