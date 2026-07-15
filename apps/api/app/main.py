"""ContractLens API — FastAPI application entrypoint.

Spec section 13: RESTful API for M&A due diligence legal AI system.
Async-first with SQLAlchemy + asyncpg. Connection pooling via database.py.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import engine
from app.routers import contracts, health, jobs, reviews


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: manages startup/shutdown lifecycle."""
    # Startup: engine is created at module import time
    yield
    # Shutdown: dispose of connection pool gracefully
    await engine.dispose()


app = FastAPI(
    title="ContractLens API",
    description=(
        "Legal AI for M&A due diligence. Upload contract folders, "
        "extract clause-level risk, generate auditable risk registers."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("CONTRACTLENS_ENV", "development") != "production" else None,
    redoc_url="/redoc" if os.getenv("CONTRACTLENS_ENV", "development") != "production" else None,
)

# ─── CORS ────────────────────────────────────────────────────────────────────
# Allow frontend (Next.js) to access the API. Restrict origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(jobs.router, prefix="/audit-jobs")
app.include_router(contracts.router, prefix="/contracts")
app.include_router(reviews.router, prefix="/human-reviews")


# ─── Global Exception Handlers ───────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler returning structured error response."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": str(exc) if os.getenv("CONTRACTLENS_ENV") != "production" else "An internal error occurred",
            "code": "INTERNAL_ERROR",
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    """Handle 404 responses with structured format."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "detail": f"The requested resource was not found: {request.url.path}",
            "code": "ROUTE_NOT_FOUND",
        },
    )
