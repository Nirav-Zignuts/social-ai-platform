import os
from celery import Celery
import logging

logger = logging.getLogger(__name__)
# Redis is used as both broker and backend by default for simple setups
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)
logger.info(f"Celery broker URL: {CELERY_BROKER_URL}")
celery_app = Celery(
    "social_ai_platform",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.knowledge.tasks", "app.services.generation_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
