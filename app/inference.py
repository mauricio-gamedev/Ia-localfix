import httpx


class InferenceUnavailable(RuntimeError):
    pass


async def create_plan(base_url: str, model: str, request: str) -> str:
    system_prompt = (
        "You are the planning engine of Ia-localfix, a local-first software engineering agent. "
        "Create a concrete, staged implementation plan. Identify assumptions, files, dependencies, "
        "risks, and verifiable tests. Be viewpoint-neutral. Do not claim to have executed tools, "
        "changed files, or run tests. Do not propose unrestricted shell execution."
    )
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request},
        ],
        "options": {"temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=3.0)) as client:
            response = await client.post(f"{base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise InferenceUnavailable("Local model runtime is unavailable or returned invalid data.") from exc

    content = data.get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise InferenceUnavailable("Local model returned an empty response.")
    return content.strip()
