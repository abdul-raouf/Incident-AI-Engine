import httpx

async def _call_ollama_direct(prompt: str) -> str:
    """Direct Ollama API call — bypasses langchain-ollama quirks with qwen3."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model":  settings.OLLAMA_MODEL,
                "stream": False,
                "options": {"temperature": 0},
                "think":  False,              # ← Ollama native parameter
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


async def classify_text_fast(text: str) -> ClassificationOutput:
    # Build prompt manually
    prompt = CLASSIFICATION_PROMPT_FAST.format_messages(text=text)
    full_prompt = "\n".join([m.content for m in prompt])

    try:
        raw_output = await _call_ollama_direct(full_prompt)
        print("=== RAW OUTPUT ===", repr(raw_output[:300]))
        raw        = _extract_json(raw_output)
        return _parse_raw(raw, text)
    except Exception as e:
        fallback           = _build_fallback()
        fallback.reasoning = f"Parsing error: {str(e)}"
        return fallback