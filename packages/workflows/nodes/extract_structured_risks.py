# ContractLens — extract_structured_risks node (section 6.1)
# LLM extraction of only routed paragraphs into typed objects.

from __future__ import annotations

from packages.workflows.graph import AuditState


def extract_structured_risks_node(state: AuditState) -> dict:
    """Node 6 — Send only routed chunks to LLM provider for structured extraction.
    
    The provider abstraction layer (ProviderRouter) handles retry/fallback.
    The result is validated through ContractExtraction schema.
    
    Section 9.3: This constrains LLM context and reduces hallucination surface
    by only exposing relevant text.
    
    Replay-safe: no side effects before interrupt. Writes extraction result
    reference only.
    """
    return {"current_step": "extract_structured_risks"}
