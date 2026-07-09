import uuid
from datetime import datetime
import asyncio
import logging
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from celery_app import celery_app
from app.db.session import SessionLocal
from app.models.business_profile import BusinessProfile
from app.models.ai_configuration import AIConfiguration
from app.core.config import settings
from app.services.generation.graph import get_compiled_graph
from app.services.generation.state import GenerationState

logger = logging.getLogger(__name__)

# Note: We need a postgres pool for the checkpointer.
# For celery synchronous task environment, we'll wrap the graph execution in asyncio.run


async def _run_graph_async(workspace_id: str, generation_cycle_id: str):
    # Construct checkpointer pool string.
    # Usually we can get it from settings.DATABASE_URL but replacing asyncpg or using psycopg3 format.
    db_url = (
        settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql")
        .replace("postgresql+asyncpg", "postgresql")
        .replace("postgresql+psycopg", "postgresql")
    )

    async with AsyncConnectionPool(
        conninfo=db_url, max_size=5, kwargs={"autocommit": True}
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)

        # Setup tables if they don't exist
        await checkpointer.setup()

        graph = get_compiled_graph(checkpointer=checkpointer)

        today = datetime.now().strftime("%Y-%m-%d")

        state: GenerationState = {
            "workspace_id": workspace_id,
            "generation_cycle_id": generation_cycle_id,
            "calendar_date": today,
            "content_type": None,
            "content_type_rationale": None,
            "business_context": "",
            "recent_posts_context": "",
            "ai_config": {},
            "caption": None,
            "hashtags": None,
            "cta": None,
            "needs_image": None,
            "image_url": None,
            "reviewer_passed": None,
            "reviewer_score": None,
            "reviewer_notes": None,
            "reviewer_retry_count": 0,
            "post_id": None,
        }

        config = {"configurable": {"thread_id": generation_cycle_id}}

        # Invoke graph
        result = await graph.ainvoke(state, config=config)
        return result


@celery_app.task(
    bind=True, max_retries=2, default_retry_delay=5, name="run_generation_cycle"
)
def run_generation_cycle(self, workspace_id: str):
    generation_cycle_id = str(uuid.uuid4())
    logger.info(
        f"Starting generation cycle {generation_cycle_id} for workspace {workspace_id}"
    )

    try:
        asyncio.run(_run_graph_async(workspace_id, generation_cycle_id))
        logger.info(f"Generation cycle {generation_cycle_id} complete (paused at END).")
    except Exception as e:
        logger.error(
            f"Generation cycle {generation_cycle_id} failed: {e}", exc_info=True
        )
