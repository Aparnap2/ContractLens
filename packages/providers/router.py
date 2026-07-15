# ContractLens — Provider router (sections 5.2, 5.3, 5.4, 21.1)
# All LLM calls go through this abstraction. No node may call vendor SDKs directly.

from __future__ import annotations

import json
from typing import Protocol, Any, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

from packages.domain.schemas import (
    ExtractionRequest,
    ExtractionCandidate,
    ProviderPolicy,
    ContractExtraction,
)

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    """Internal interface for all LLM providers (section 5.2).
    
    No node may call vendor SDKs directly. All calls go through ProviderRouter.
    """

    @property
    def name(self) -> str:
        ...

    async def structured_extract(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        timeout_s: int,
    ) -> BaseModel:
        ...


def enforce_anti_hallucination(
    raw: dict[str, Any],
    schema: type[BaseModel],
) -> BaseModel:
    """Section 5.4 anti-hallucination enforcement.
    
    - Reject any field outside the schema.
    - Numbers must be present in source quotes (checked later in validate_extraction).
    - No field may be populated without source_quote and source_page (enforced by schema validation).
    - Absent clause must be null/false, never inferred.
    
    This function acts as a strict parse gate.
    """
    # Reject keys outside schema
    schema_fields = set(schema.model_fields.keys())
    extra_fields = set(raw.keys()) - schema_fields
    if extra_fields:
        raise ValueError(f"Response contains fields outside schema: {extra_fields}")

    # Absent clause: ensure *_present is not set to True without evidence
    # (ContractExtraction model validator covers this)
    # Parse through Pydantic; ValidationError surfaces violations
    return schema.model_validate(raw)


class ProviderRouter:
    """Section 21.1 — Ordered fallback router with retry."""

    def __init__(
        self,
        providers: dict[str, LLMProvider],
        policy: ProviderPolicy,
    ):
        self._providers = providers
        self._policy = policy

    async def structured_extract(
        self,
        request: ExtractionRequest,
        response_schema: type[BaseModel],
    ) -> tuple[BaseModel, ExtractionCandidate]:
        """Try each provider in priority order. Return (result, candidate) on success.
        
        Implements retry/fallback logic from section 5.3:
        1. Poolside direct free model first
        2. Groq for speed
        3. OpenRouter :free fallback
        4. If all fail, raises RuntimeError → human review path
        """
        last_error: Exception | None = None
        candidates = self._get_candidates()

        for candidate in candidates:
            provider = self._providers.get(candidate.provider_name)
            if provider is None:
                continue

            for attempt in range(1, self._policy.max_retries_per_provider + 1):
                try:
                    result = await provider.structured_extract(
                        model=candidate.model,
                        system_prompt=request.system_prompt,
                        user_prompt=request.user_prompt,
                        response_schema=response_schema,
                        timeout_s=request.timeout_s,
                    )
                    # Apply anti-hallucination gate
                    if isinstance(result, BaseModel):
                        raw = result.model_dump()
                    else:
                        raw = result
                    validated = enforce_anti_hallucination(raw, response_schema)
                    return validated, candidate
                except (ValidationError, ValueError, json.JSONDecodeError) as e:
                    last_error = e
                    continue  # retry same provider or fall through
                except Exception as e:
                    last_error = e
                    break  # non-retryable provider error → move to next provider

        raise RuntimeError(
            f"All providers failed after {self._policy.max_retries_per_provider} retries each. "
            f"Last error: {last_error}"
        )

    def _get_candidates(self) -> list[ExtractionCandidate]:
        """Build ordered candidate list from policy priority."""
        # Map provider names to default models
        model_map = {
            "groq": "llama-3.3-70b-versatile",
            "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
            "poolside": "poolside/laguna-m.1",
        }
        candidates: list[ExtractionCandidate] = []
        for provider_name in self._policy.priority:
            model = model_map.get(provider_name, "unknown")
            candidates.append(
                ExtractionCandidate(provider_name=provider_name, model=model)
            )
        return candidates
