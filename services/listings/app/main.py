from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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
async def lifespan(app: FastAPI):
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.ENV)

    database_url = build_listings_database_url()
    logger.info(
        "Database configured: host=%s db=%s user=%s",
        settings.LISTING_DB_HOST,
        settings.LISTING_DB_NAME,
        settings.LISTING_DB_USER,
    )

    app.state.engine, app.state.session_factory = create_engine_and_session(
        database_url
    )

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
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health():
    try:
        async with app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        logging.getLogger(__name__).error("Health check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unreachable")
    return {"status": "ok", "service": "listings"}
