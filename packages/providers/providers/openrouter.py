# ContractLens — OpenRouter provider (section 5.1, 5.2)
# Calls OpenRouter API with :free model suffix for free-tier access.

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import BaseModel

from packages.domain.schemas import ProviderCredentials


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider:
    """Provider using OpenRouter's unified API with :free model suffix."""

    def __init__(self, credentials: ProviderCredentials | None = None):
        self._api_key = (
            credentials.openrouter_api_key
            if credentials and credentials.openrouter_api_key
            else os.environ.get("OPENROUTER_API_KEY", "")
        )
        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def name(self) -> str:
        return "openrouter"

    async def structured_extract(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        timeout_s: int,
    ) -> BaseModel:
        """Call OpenRouter chat completions endpoint.
        
        The model string should include the :free suffix (e.g.
        "meta-llama/llama-3.1-8b-instruct:free") for free-tier access.
        """
        url = f"{OPENROUTER_BASE_URL}/chat/completions"

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.01,  # section 5.4 — near zero
            "max_tokens": 4096,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://contractlens.local",
        }

        async with self._client as client:
            resp = await client.post(
                url, json=body, headers=headers, timeout=timeout_s
            )
            resp.raise_for_status()
            data = resp.json()

        raw_content = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw_content)
        return response_schema.model_validate(parsed)
