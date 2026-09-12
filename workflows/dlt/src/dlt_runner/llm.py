"""Shared helper for calling an OpenAI-compatible chat-completions endpoint.

Works against both the LiteLLM gateway and Ollama's OpenAI-compatible API — the
two providers ``dlt_runner.config.llm_settings`` resolves.
"""

from __future__ import annotations

import httpx


def call_llm(
    prompt: str,
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    system_prompt: str | None = None,
    timeout: float = 60,
    response_format: dict | None = None,
) -> str:
    """Send a chat-completion request and return the assistant message content.

    Raises ``httpx.HTTPError`` on network/HTTP failures (including a timeout).
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {"model": model_id, "messages": messages}
    if response_format:
        payload["response_format"] = response_format

    resp = httpx.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
