from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from app.core.config import settings
from app.core.logger import logger
from app.db.health import check_database_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Social AI Platform (%s)...", settings.ENVIRONMENT)

    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)

    try:
        check_database_connection()
        logger.info("Database connected successfully")
    except Exception:
        logger.exception("Database connection failed")
        raise

    if not (settings.CRON_SECRET or "").strip():
        logger.warning(
            "CRON_SECRET is empty — /api/v1/internal/* cron routes will return 503"
        )

    yield

    logger.info("Shutting down Social AI Platform...")
