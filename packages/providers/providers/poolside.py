# ContractLens — Poolside provider stub (section 5.1, 5.3)
# Ready for direct free access when Poolside API is available.

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import BaseModel

from packages.domain.schemas import ProviderCredentials


POOLSIDE_BASE_URL = "https://api.poolside.ai/v1"  # illustrative — adjust per docs


class PoolsideProvider:
    """Provider stub for Poolside direct free access.
    
    Section 5.3 specifies Poolside as the first priority for structured extraction
    when available/configured. This stub is ready for real implementation once
    Poolside's API endpoint and auth scheme are confirmed.
    """

    def __init__(self, credentials: ProviderCredentials | None = None):
        self._api_key = (
            credentials.poolside_api_key
            if credentials and credentials.poolside_api_key
            else os.environ.get("POOLSIDE_API_KEY", "")
        )
        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def name(self) -> str:
        return "poolside"

    async def structured_extract(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        timeout_s: int,
    ) -> BaseModel:
        """Call Poolside's chat completions endpoint.
        
        Implements the same interface as GroqProvider/OpenRouterProvider.
        The exact endpoint path and auth scheme should be updated per Poolside's
        published API documentation when direct free access is configured.
        """
        url = f"{POOLSIDE_BASE_URL}/chat/completions"

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.01,
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
        parsed = json.loads(raw_content)
        return response_schema.model_validate(parsed)
