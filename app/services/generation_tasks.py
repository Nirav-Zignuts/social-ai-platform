import uuid
from datetime import datetime
import asyncio
import logging
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings
from app.services.generation.graph import get_compiled_graph
from app.services.generation.state import GenerationState
from app.services.generation.debug_log import gen_log

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
            "reviewer_passed": None,
            "reviewer_score": None,
            "reviewer_notes": None,
            "reviewer_retry_count": 0,
            "post_id": None,
        }

        config = {"configurable": {"thread_id": generation_cycle_id}}
        gen_log(
            "LIFECYCLE → graph.ainvoke START (fresh cycle)",
            workspace_id=workspace_id,
            generation_cycle_id=generation_cycle_id,
            thread_id=generation_cycle_id,
            initial_state_keys=list(state.keys()),
            calendar_date=today,
        )
        result = await graph.ainvoke(state, config=config)
        gen_log(
            "LIFECYCLE → graph.ainvoke END (interrupted after persist)",
            workspace_id=workspace_id,
            generation_cycle_id=generation_cycle_id,
            post_id=result.get("post_id") if isinstance(result, dict) else None,
            content_type=result.get("content_type") if isinstance(result, dict) else None,
            reviewer_score=result.get("reviewer_score") if isinstance(result, dict) else None,
            caption_preview=(
                (result.get("caption") or "")[:120]
                if isinstance(result, dict)
                else None
            ),
        )
        return result


def run_generation_cycle(workspace_id: str) -> dict:
    """Run one generation cycle for a workspace (sync entry for BackgroundTasks)."""
    generation_cycle_id = str(uuid.uuid4())
    gen_log(
        "LIFECYCLE → run_generation_cycle START",
        workspace_id=workspace_id,
        generation_cycle_id=generation_cycle_id,
    )
    logger.info(
        "Starting generation cycle %s for workspace %s",
        generation_cycle_id,
        workspace_id,
    )

    try:
        asyncio.run(_run_graph_async(workspace_id, generation_cycle_id))
        logger.info("Generation cycle %s complete.", generation_cycle_id)
        gen_log(
            "LIFECYCLE → run_generation_cycle COMPLETE",
            workspace_id=workspace_id,
            generation_cycle_id=generation_cycle_id,
            status="completed",
        )
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
        gen_log(
            "LIFECYCLE → run_generation_cycle FAILED",
            workspace_id=workspace_id,
            generation_cycle_id=generation_cycle_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "generation_cycle_id": generation_cycle_id,
            "workspace_id": workspace_id,
            "error": str(e),
        }
