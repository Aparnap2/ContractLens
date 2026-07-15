# ContractLens — Groq provider (section 5.1, 5.2)
# Calls https://api.groq.com/openai/v1 with OpenAI-compatible API.

from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import BaseModel

from packages.domain.schemas import ProviderCredentials


GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider:
    """Provider using Groq's OpenAI-compatible API."""

    def __init__(self, credentials: ProviderCredentials | None = None):
        self._api_key = (
            credentials.groq_api_key
            if credentials and credentials.groq_api_key
            else os.environ.get("GROQ_API_KEY", "")
        )
        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def name(self) -> str:
        return "groq"

    async def structured_extract(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        timeout_s: int,
    ) -> BaseModel:
        """Call Groq chat completions endpoint with JSON mode.
        
        Uses the OpenAI-compatible /chat/completions endpoint.
        Response is parsed through the provided Pydantic schema.
        """
        url = f"{GROQ_BASE_URL}/chat/completions"
        schema_json = response_schema.model_json_schema()

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.01,  # section 5.4 — near zero
            "response_format": {"type": "json_object"},
            "max_tokens": 4096,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with self._client as client:
            resp = await client.post(
                url, json=body, headers=headers, timeout=timeout_s
            )
            resp.raise_for_status()
            data = resp.json()

        raw_content = data["choices"][0]["message"]["content"]
        # Parse JSON string into dict, then validate through schema
        import json
        parsed = json.loads(raw_content)
        return response_schema.model_validate(parsed)
