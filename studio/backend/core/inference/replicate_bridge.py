import json
import httpx
from typing import Any, AsyncGenerator, Optional

async def stream_replicate(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    messages: list[dict[str, Any]],
    model: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    \"\"\"Stream responses natively from Replicate's API, translating to OpenAI SSE format.\"\"\"
    
    # Extract the latest prompt for Replicate's standard input format
    prompt = \"\"
    system_prompt = \"\"
    for msg in messages:
        if msg.get(\"role\") == \"system\":
            system_prompt = msg.get(\"content\", \"\")
        elif msg.get(\"role\") == \"user\":
            prompt = msg.get(\"content\", \"\")
            
    input_data = {
        \"prompt\": prompt,
        \"system_prompt\": system_prompt,
    }
    if temperature is not None:
        input_data[\"temperature\"] = temperature
    if max_tokens is not None:
        input_data[\"max_new_tokens\"] = max_tokens
        
    # Replicate native prediction endpoint
    url = f\"{base_url}/models/{model}/predictions\"
    payload = {\"input\": input_data, \"stream\": True}
    
    async with client.stream(\"POST\", url, headers=headers, json=payload) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line or not line.startswith(\"data: \"):
                continue
            data_str = line[len(\"data: \"):]
            if data_str.strip() == \"[DONE]\":
                yield line + \"\\n\"
                return
            
            try:
                # Translate Replicate's chunk format to OpenAI's chunk format
                chunk = json.loads(data_str)
                # Replicate sends raw strings or objects depending on the model pipeline.
                # Assuming standard text output:
                text = chunk if isinstance(chunk, str) else chunk.get(\"text\", \"\")
                
                oai_chunk = {
                    \"choices\": [{\"delta\": {\"content\": text}}]
                }
                yield f\"data: {json.dumps(oai_chunk)}\\n\\n\"
            except Exception:
                pass
        
        yield \"data: [DONE]\\n\\n\"

