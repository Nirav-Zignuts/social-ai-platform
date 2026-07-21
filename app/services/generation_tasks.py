import uuid
from datetime import datetime
import asyncio
import logging
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings
from app.services.generation.graph import get_compiled_graph
from app.services.generation.state import GenerationState

logger = logging.getLogger(__name__)


async def _run_graph_async(workspace_id: str, generation_cycle_id: str):
    db_url = (
        settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql")
        .replace("postgresql+asyncpg", "postgresql")
        .replace("postgresql+psycopg", "postgresql")
    )

    async with AsyncConnectionPool(
        conninfo=db_url, max_size=5, kwargs={"autocommit": True}
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
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
            "force_regenerate_image": False,
            "is_human_regeneration": False,
            "reviewer_passed": None,
            "reviewer_score": None,
            "reviewer_notes": None,
            "reviewer_retry_count": 0,
            "total_regenerate_count": 0,
            "post_id": None,
        }

        config = {"configurable": {"thread_id": generation_cycle_id}}
        result = await graph.ainvoke(state, config=config)
        return result


def run_generation_cycle(workspace_id: str) -> dict:
    """Run one generation cycle for a workspace (sync entry for BackgroundTasks)."""
    generation_cycle_id = str(uuid.uuid4())
    logger.info(
        "Starting generation cycle %s for workspace %s",
        generation_cycle_id,
        workspace_id,
    )

    try:
        asyncio.run(_run_graph_async(workspace_id, generation_cycle_id))
        logger.info("Generation cycle %s complete.", generation_cycle_id)
        return {
            "status": "completed",
            "generation_cycle_id": generation_cycle_id,
            "workspace_id": workspace_id,
        }
    except Exception as e:
        logger.error(
            "Generation cycle %s failed: %s",
            generation_cycle_id,
            e,
            exc_info=True,
        )   
        return {
            "status": "failed",
            "generation_cycle_id": generation_cycle_id,
            "workspace_id": workspace_id,
            "error": str(e),
        }
