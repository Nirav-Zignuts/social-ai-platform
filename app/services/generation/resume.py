import asyncio
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

  graph.update_state(
      config,
      {
          "reviewer_notes": f"Human reviewer feedback: {feedback}",
          "reviewer_passed": False,
      },
      as_node="writer",
  )

  result = await graph.ainvoke(None, config=config)
  return result


async def _resume_with_postgres_checkpointer(generation_cycle_id: str, feedback: str):
    async with AsyncConnectionPool(
        conninfo=_db_url(), max_size=5, kwargs={"autocommit": True}
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        return await _resume_graph_for_regenerate_async(
            generation_cycle_id, feedback, checkpointer=checkpointer
        )


def resume_generation_for_regenerate(generation_cycle_id: str, feedback: str):
    """Resume the LangGraph thread for a human-triggered regeneration."""
    logger.info("Resuming generation cycle %s with human feedback", generation_cycle_id)
    return asyncio.run(_resume_with_postgres_checkpointer(generation_cycle_id, feedback))
