import logging

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings
from app.services.generation.graph import get_compiled_graph

logger = logging.getLogger(__name__)


def _db_url() -> str:
    return (
        settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql")
        .replace("postgresql+asyncpg", "postgresql")
        .replace("postgresql+psycopg", "postgresql")
    )


async def _resume_graph_for_regenerate_async(
    generation_cycle_id: str,
    feedback: str,
    checkpointer=None,
):
    graph = get_compiled_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": generation_cycle_id}}
    human_notes = f"Human reviewer feedback: {feedback}"

    # AsyncPostgresSaver requires aupdate_state (not sync update_state).
    await graph.aupdate_state(
        config,
        {
            "reviewer_notes": human_notes,
            "reviewer_passed": False,
        },
        as_node="writer",
    )

    result = await graph.ainvoke(None, config=config)
    return result


async def resume_generation_for_regenerate(generation_cycle_id: str, feedback: str):
    """
    Resume the LangGraph thread for a human-triggered regeneration.

    Must be awaited from the FastAPI event loop — do not wrap with asyncio.run()
    (that breaks when called from an already-running async route).
    """
    logger.info("Resuming generation cycle %s with human feedback", generation_cycle_id)
    async with AsyncConnectionPool(
        conninfo=_db_url(), max_size=5, kwargs={"autocommit": True}
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        return await _resume_graph_for_regenerate_async(
            generation_cycle_id,
            feedback,
            checkpointer=checkpointer,
        )
