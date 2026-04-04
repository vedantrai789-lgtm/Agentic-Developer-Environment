"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging so agent/task logs appear in the console
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

from ade.api.routes import projects, tasks
from ade.api.routes.ws import task_websocket
from ade.api.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle handler."""
    # Startup: warm Redis connection
    from ade.core.redis_client import get_redis

    redis = get_redis()
    await redis.ping()
    yield
    # Shutdown: close Redis, dispose DB engine
    await redis.aclose()
    from ade.core.database import engine

    await engine.dispose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="ADE API",
        description="Agentic Developer Environment API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routes
    app.include_router(projects.router)
    app.include_router(tasks.router)

    # WebSocket route
    app.add_api_websocket_route("/ws/tasks/{task_id}", task_websocket)

    # Health check
    @app.get("/health", response_model=HealthResponse)
    async def health():
        db_ok = False
        redis_ok = False

        try:
            from sqlalchemy import text

            from ade.core.database import async_session_factory

            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            pass

        try:
            from ade.core.redis_client import get_redis

            redis = get_redis()
            await redis.ping()
            redis_ok = True
        except Exception:
            pass

        status = "healthy" if (db_ok and redis_ok) else "degraded"
        return HealthResponse(status=status, database=db_ok, redis=redis_ok)

    return app


app = create_app()
