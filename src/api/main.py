from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from redis.exceptions import RedisError

from src.api.auth import require_api_key
from src.api.config import Settings, get_settings
from src.api.observability import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
    metrics_response,
)
from src.api.rate_limit import RateLimitMiddleware
from src.api.schemas import QueryAPIRequest, QueryAPIResponse
from src.api.services import RAGService
from src.vectorstore.retriever import warm_up_embedding_model
from src.vectorstore.postgres_store import PostgresVectorStore
from src.vectorstore.store import LocalVectorStore


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize and release application resources."""
    application.state.settings = get_settings()
    application.state.rag_service = None
    application.state.redis = None
    yield
    if application.state.rag_service is not None:
        application.state.rag_service.close()
    if application.state.redis is not None:
        await application.state.redis.aclose()


settings = get_settings()
configure_logging()
_rag_service_lock = Lock()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)
app.state.rag_service = None
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
    )
if settings.rate_limit_enabled:
    from redis.asyncio import Redis

    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.add_middleware(
        RateLimitMiddleware,
        redis=app.state.redis,
        limit=settings.rate_limit_per_minute,
    )


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    """Report whether the API process is running."""
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Expose Prometheus metrics for internal monitoring."""
    return metrics_response()


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    """Report whether the API and its required dependencies are usable."""
    loaded_settings: Settings = get_settings()
    if loaded_settings.vector_store_backend == "postgres":
        if not loaded_settings.source_sha256:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SOURCE_SHA256 is required for PostgreSQL retrieval.",
            )
        try:
            import psycopg

            database_url = loaded_settings.database_url.replace(
                "postgresql+psycopg://", "postgresql://"
            )
            with psycopg.connect(database_url, connect_timeout=3) as connection:
                connection.execute("SELECT 1")
        except (psycopg.Error, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PostgreSQL is unavailable.",
            ) from error
    elif not (Path(loaded_settings.vector_db_path) / "vectors.npy").exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The vector store is not available.",
        )
    if loaded_settings.rate_limit_enabled:
        redis = Redis.from_url(
            loaded_settings.redis_url,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        try:
            redis.ping()
        except RedisError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis is unavailable.",
            ) from error
        finally:
            redis.close()
    return {
        "status": "ok",
        "environment": loaded_settings.app_environment,
        "version": loaded_settings.app_version,
    }


def _get_rag_service() -> RAGService:
    """Load the local RAG resources on the first query."""
    if app.state.rag_service is not None:
        return app.state.rag_service

    with _rag_service_lock:
        if app.state.rag_service is not None:
            return app.state.rag_service
        warm_up_embedding_model()
        if settings.vector_store_backend == "postgres":
            if not settings.source_sha256:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SOURCE_SHA256 is required for PostgreSQL retrieval.",
                )
            store = PostgresVectorStore(
                settings.database_url,
                settings.source_sha256,
                min_size=settings.database_pool_min_size,
                max_size=settings.database_pool_max_size,
            )
        else:
            vector_db_path = Path(settings.vector_db_path)
            if not (vector_db_path / "vectors.npy").exists():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "The vector store is not available. Run "
                        "'uv run python data_loader.py' first."
                    ),
                )
            store = LocalVectorStore(str(vector_db_path))
        app.state.rag_service = RAGService(store)
    return app.state.rag_service


@app.post(
    "/api/v1/query",
    response_model=QueryAPIResponse,
    status_code=status.HTTP_200_OK,
    tags=["query"],
)
def query(
    request: QueryAPIRequest,
    _: None = Security(require_api_key),
) -> QueryAPIResponse:
    """Answer a question using retrieved constitutional context."""
    try:
        return _get_rag_service().answer(request)
    except HTTPException:
        raise
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
