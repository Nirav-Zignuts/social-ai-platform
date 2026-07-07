from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logger import logger
from app.db.health import check_database_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Social AI Platform...")

    try:
        check_database_connection()
        logger.info("Database connected successfully")
    except Exception:
        logger.exception("Database connection failed")
        raise

    yield

    logger.info("Shutting down Social AI Platform...")