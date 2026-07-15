#!/usr/bin/env python3
"""ContractLens Worker — CLI entrypoint for LangGraph audit workflow.

Spec section 6: LangGraph workflow design.
Spec section 6.4: Graph state with reference-based payloads.

Usage:
    python -m app.worker.worker          # using module path
    python apps/worker/worker.py         # direct invocation

Graceful shutdown on SIGINT/SIGTERM per spec section 17.2 (crash recovery).
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("contractlens.worker")


# ─── Configuration ───────────────────────────────────────────────────────────
# In a full implementation, these would be loaded from tenant_settings / env.
# Spec section 11: All thresholds must be config-driven.
DEFAULT_CONFIG = {
    "poll_interval_seconds": int(os.getenv("WORKER_POLL_INTERVAL", "5")),
    "max_concurrent_contracts": int(os.getenv("WORKER_MAX_CONCURRENT", "3")),
    "database_url": os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/contractlens",
    ),
}


class AuditWorkflow:
    """Stub for the LangGraph audit workflow.

    Spec section 6.1 defines the full node set:
      create_job → ingest_contract → extract_pages → chunk_contract →
      route_clauses → extract_structured_risks → validate_extraction →
      human_review_interrupt → run_law_engine → score_contract →
      persist_results → create_actions → export_outputs → finalize_job

    This will be replaced with a compiled LangGraph graph using
    MemorySaver checkpointer for interrupt/resume support.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self._running = False
        logger.info("AuditWorkflow initialized (db_url=%s)", db_url)

    async def process_next_job(self) -> bool:
        """Poll for the next queued job and process it.

        Returns True if a job was processed, False if no work available.
        """
        # In the full implementation this will:
        # 1. Query for audit_jobs WHERE status = 'queued' ORDER BY created_at
        # 2. Load the compiled LangGraph with checkpoint from DB
        # 3. Execute the graph with interrupt handling
        # 4. Handle HITL interrupts by writing to human_reviews table
        # 5. Update job status on completion or error
        logger.debug("Polling for queued jobs...")
        return False

    async def run_loop(self):
        """Main processing loop — polls for jobs until shutdown signal."""
        self._running = True
        logger.info("Worker processing loop started (poll_interval=%ds)",
                     DEFAULT_CONFIG["poll_interval_seconds"])

        while self._running:
            try:
                processed = await self.process_next_job()
                if not processed:
                    await asyncio.sleep(DEFAULT_CONFIG["poll_interval_seconds"])
            except asyncio.CancelledError:
                logger.info("Processing loop cancelled")
                break
            except Exception:
                logger.exception("Unhandled error in processing loop")
                await asyncio.sleep(DEFAULT_CONFIG["poll_interval_seconds"])

        logger.info("Worker processing loop ended")

    async def shutdown(self):
        """Graceful shutdown — complete current work, then stop."""
        logger.info("Shutting down worker gracefully...")
        self._running = False
        # In full impl: await current_graph.interrupt() to persist state


async def main():
    """Main worker entrypoint.

    Sets up graceful shutdown via SIGINT/SIGTERM, then enters processing loop.
    """
    logger.info("=" * 60)
    logger.info("ContractLens Worker starting")
    logger.info("=" * 60)

    workflow = AuditWorkflow(db_url=DEFAULT_CONFIG["database_url"])

    # ─── Graceful Shutdown ────────────────────────────────────────────────
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler():
        """Handle shutdown signals by scheduling workflow shutdown."""
        if not shutdown_event.is_set():
            logger.info("Received shutdown signal")
            shutdown_event.set()
            asyncio.ensure_future(workflow.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows compatibility fallback
            pass

    try:
        await workflow.run_loop()
    except asyncio.CancelledError:
        pass
    finally:
        await workflow.shutdown()

    logger.info("Worker stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
