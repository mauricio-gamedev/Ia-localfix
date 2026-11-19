import json

import httpx


class InferenceUnavailable(RuntimeError):
    pass


PROJECT_FILES_SCHEMA = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["files"],
    "additionalProperties": False,
}


async def _ollama_chat(base_url: str, model: str, messages: list[dict], output_format=None) -> str:
    payload = {"model": model, "stream": False, "messages": messages}
    if output_format is not None:
        payload["format"] = output_format
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=3.0)) as client:
            response = await client.post(f"{base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise InferenceUnavailable(
            "Local model runtime is unavailable or returned invalid data."
        ) from exc

    content = data.get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise InferenceUnavailable("Local model returned an empty response.")
    return content.strip()


async def create_plan(base_url: str, model: str, request: str) -> str:
    system_prompt = (
        "You are the planning engine of Ia-localfix, a local-first software engineering agent. "
        "Create a concrete, staged implementation plan. Identify assumptions, files, dependencies, "
        "risks, and verifiable tests. Be viewpoint-neutral. Do not claim to have executed tools, "
        "changed files, or run tests. Do not propose unrestricted shell execution."
    )
    return await _ollama_chat(
        base_url,
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request},
        ],
    )


async def generate_project_files(base_url: str, model: str, request: str) -> list[dict]:
    system_prompt = (
        "You are a senior software project generator. Generate a coherent initial project "
        "from the user's requirements. Return only JSON matching the supplied schema. Each file "
        "must have a relative POSIX path and complete UTF-8 text content. Include essential "
        "source, configuration, and tests when appropriate. Do not include absolute paths, "
        "parent-directory traversal, secrets, or instructions to run arbitrary shell commands. "
        "Do not claim that files were built or tested."
    )
    raw = await _ollama_chat(
        base_url,
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request},
        ],
        output_format=PROJECT_FILES_SCHEMA,
    )
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InferenceUnavailable("Local model did not return valid structured project files.") from exc
    files = result.get("files") if isinstance(result, dict) else None
    if not isinstance(files, list):
        raise InferenceUnavailable("Local model response is missing the files array.")
    return files
