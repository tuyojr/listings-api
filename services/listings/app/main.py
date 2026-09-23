import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import build_listings_database_url, create_engine_and_session
from app.routers import listings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.ENV)

    database_url = build_listings_database_url()
    logger.info(
        "Database configured: host=%s db=%s user=%s",
        settings.LISTING_DB_HOST,
        settings.LISTING_DB_NAME,
        settings.LISTING_DB_USER,
    )

    app.state.engine, app.state.session_factory = create_engine_and_session(database_url)

    yield

    logger.info("Shutting down %s", settings.APP_NAME)
    await app.state.engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV == "development" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.ENV == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

app.include_router(listings.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness + readiness probe that verifies DB connectivity.

    Registered at both paths: bare /health is what the container's own
    Docker healthcheck and the ALB target group hit directly (bypassing
    the listener's path-based routing); /api/health is reachable
    externally through the ALB, which only forwards /api/*.
    """
    try:
        async with app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        logging.getLogger(__name__).error("Health check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unreachable") from exc
    return {"status": "ok", "service": "listings"}
