"""
CURATOR — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, chat, curriculum, graph, health, mimar, pathway
from app.core.config import get_settings
from app.core.logging import logger, setup_logging
from app.graph.client import neo4j_client
from app.services.ingestion import ensure_indexes_ready

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging(debug=settings.app_debug)
    logger.info("curator.starting", env=settings.app_env)

    # Connect Neo4j
    try:
        await neo4j_client.connect()
        await neo4j_client.create_constraints()
    except Exception as exc:
        logger.warning("neo4j.startup_failed", error=str(exc))

    # Load / build FAISS + BM25 indexes
    try:
        await ensure_indexes_ready()
    except Exception as exc:
        logger.warning("indexes.startup_failed", error=str(exc))

    # MİMAR research store (local SQLite) + bootstrap administrator
    try:
        mimar.get_service()
        logger.info("mimar.ready", db=settings.mimar_db_path)
        if settings.app_env == "production" and settings.mimar_admin_token == "dev-admin-token":
            logger.warning("mimar.insecure_admin_token", msg="Set MIMAR_ADMIN_TOKEN in production")
    except Exception as exc:
        logger.warning("mimar.startup_failed", error=str(exc))

    logger.info("curator.ready")
    yield

    # Shutdown
    await neo4j_client.close()
    logger.info("curator.shutdown")


app = FastAPI(
    title="CURATOR API",
    description="KUSOM müfredat sorgu ve analiz servisi",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, tags=["health"])
app.include_router(chat.router,       prefix="/api/v1", tags=["chat"])
app.include_router(curriculum.router, prefix="/api/v1", tags=["curriculum"])
app.include_router(graph.router,      prefix="/api/v1", tags=["graph"])
app.include_router(mimar.router,      prefix="/api/v1")
app.include_router(pathway.router,    prefix="/api/v1")
app.include_router(audit.router,      prefix="/api/v1")
