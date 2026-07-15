# ContractLens — LangGraph workflow graph (sections 6.1–6.4)
# All 13 nodes + interrupt-based HITL + checkpointer integration.

from __future__ import annotations

from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from packages.workflows.nodes.create_job import create_job_node
from packages.workflows.nodes.ingest_contract import ingest_contract_node
from packages.workflows.nodes.extract_pages import extract_pages_node
from packages.workflows.nodes.chunk_contract import chunk_contract_node
from packages.workflows.nodes.route_clauses import route_clauses_node
from packages.workflows.nodes.extract_structured_risks import extract_structured_risks_node
from packages.workflows.nodes.validate_extraction import validate_extraction_node
from packages.workflows.nodes.human_review_interrupt import human_review_node
from packages.workflows.nodes.run_law_engine import run_law_engine_node
from packages.workflows.nodes.score_contract import score_contract_node
from packages.workflows.nodes.persist_results import persist_results_node
from packages.workflows.nodes.create_actions import create_actions_node
from packages.workflows.nodes.export_outputs import export_outputs_node
from packages.workflows.nodes.finalize_job import finalize_job_node


# ──────────────────────────────────────────────
# Section 6.4 — Graph state
# ──────────────────────────────────────────────

class AuditState(TypedDict):
    """Lightweight graph state — stores references, not full contract text.
    
    Section 6.4: Keep state small. Store references, not full contract text.
    Section ADR-005: Keep graph state reference-based to control memory.
    """
    audit_job_id: str
    contract_id: Optional[str]
    contract_ids: list[str]
    current_step: str
    review_required: bool
    review_payload_id: Optional[str]
    provider_attempts: list[dict]
    extraction_result_id: Optional[str]
    findings_ids: list[str]
    action_ids: list[str]
    errors: list[str]


# ──────────────────────────────────────────────
# Conditional edge functions
# ──────────────────────────────────────────────

def needs_review(state: AuditState) -> str:
    """After validate_extraction: route to human_review_interrupt or skip to law engine.
    
    Section 8.1: confidence below threshold never auto-commits as final.
    """
    if state.get("review_required", False):
        return "human_review_interrupt"
    return "run_law_engine"


# ──────────────────────────────────────────────
# Graph construction
# ──────────────────────────────────────────────

def build_audit_graph() -> StateGraph:
    """Build the complete audit workflow graph with all 14 nodes.
    
    Section 6.1 graph nodes:
    1.  create_job
    2.  ingest_contract
    3.  extract_pages
    4.  chunk_contract
    5.  route_clauses
    6.  extract_structured_risks
    7.  validate_extraction
    8.  human_review_interrupt
    9.  run_law_engine
    10. score_contract
    11. persist_results
    12. create_actions
    13. export_outputs
    14. finalize_job
    """
    workflow = StateGraph(AuditState)

    # Register all nodes
    workflow.add_node("create_job", create_job_node)
    workflow.add_node("ingest_contract", ingest_contract_node)
    workflow.add_node("extract_pages", extract_pages_node)
    workflow.add_node("chunk_contract", chunk_contract_node)
    workflow.add_node("route_clauses", route_clauses_node)
    workflow.add_node("extract_structured_risks", extract_structured_risks_node)
    workflow.add_node("validate_extraction", validate_extraction_node)
    workflow.add_node("human_review_interrupt", human_review_node)
    workflow.add_node("run_law_engine", run_law_engine_node)
    workflow.add_node("score_contract", score_contract_node)
    workflow.add_node("persist_results", persist_results_node)
    workflow.add_node("create_actions", create_actions_node)
    workflow.add_node("export_outputs", export_outputs_node)
    workflow.add_node("finalize_job", finalize_job_node)

    # Set entry point
    workflow.set_entry_point("create_job")

    # ── Main linear flow edges ──
    workflow.add_edge("create_job", "ingest_contract")
    workflow.add_edge("ingest_contract", "extract_pages")
    workflow.add_edge("extract_pages", "chunk_contract")
    workflow.add_edge("chunk_contract", "route_clauses")
    workflow.add_edge("route_clauses", "extract_structured_risks")
    workflow.add_edge("extract_structured_risks", "validate_extraction")

    # ── Conditional edge: validation → review or skip ──
    workflow.add_conditional_edges(
        "validate_extraction",
        needs_review,
        {
            "human_review_interrupt": "human_review_interrupt",
            "run_law_engine": "run_law_engine",
        },
    )

    # After human review, proceed to law engine
    workflow.add_edge("human_review_interrupt", "run_law_engine")

    # Remaining linear flow
    workflow.add_edge("run_law_engine", "score_contract")
    workflow.add_edge("score_contract", "persist_results")
    workflow.add_edge("persist_results", "create_actions")
    workflow.add_edge("create_actions", "export_outputs")
    workflow.add_edge("export_outputs", "finalize_job")
    workflow.add_edge("finalize_job", END)

    return workflow


def compile_audit_graph() -> StateGraph:
    """Compile the graph with a checkpointer for interrupt/resume support.
    
    Section 6.2: interrupt() requires a checkpointer. Interrupted nodes
    re-run from the start when resumed, so nodes are designed replay-safe.
    
    Section ADR-001: LangGraph checkpointers fit legal HITL flows better
    than stateless chains.
    """
    workflow = build_audit_graph()
    # MemorySaver is used for local-first (A). In production multi-tenant (B),
    # replace with PostgresSaver or SqliteSaver for durable checkpointing.
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
