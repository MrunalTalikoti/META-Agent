import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db, check_db_connection
from app.utils.logger import logger
from app.utils.cost_monitor import cost_monitor
from app.api import auth, projects, agents, conversations
from app.api import export as export_api


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} in {settings.environment} mode")

    if check_db_connection():
        logger.info("✓ Database connected")
    else:
        logger.error("✗ Database connection failed — check Docker is running")

    # Start daily cost reset scheduler
    cost_monitor.start_scheduler()
    logger.info("✓ Cost monitor scheduler started")

    yield

    cost_monitor.stop_scheduler()
    logger.info(f"Shutting down {settings.app_name}")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    description="AI-powered meta-agent orchestration system",
    version="0.2.0",
    debug=settings.debug,
    lifespan=lifespan,
)


# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Inject X-Request-ID for log correlation."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def content_size_limit_middleware(request: Request, call_next):
    """Reject bodies larger than 1MB."""
    max_size = 1 * 1024 * 1024  # 1 MB
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        return JSONResponse(status_code=413, content={"detail": "Request body too large (max 1MB)"})
    return await call_next(request)


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(auth.router,          prefix="/api/auth",          tags=["Auth"])
app.include_router(projects.router,      prefix="/api/projects",      tags=["Projects"])
app.include_router(agents.router,        prefix="/api/agents",        tags=["Agents"])
app.include_router(conversations.router, prefix="/api/conversations",  tags=["Conversations"])
app.include_router(export_api.router,    prefix="/api",               tags=["Export & Metrics"])


@app.get("/", tags=["Root"])
async def root():
    return {
        "app": settings.app_name,
        "version": "0.2.0",
        "environment": settings.environment,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    db_ok = check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "environment": settings.environment,
        "daily_spend_usd": round(cost_monitor.daily_spend, 4),
    }