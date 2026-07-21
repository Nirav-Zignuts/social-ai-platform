import logging

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings
from app.services.generation.graph import get_compiled_graph

logger = logging.getLogger(__name__)


class RegenerationCheckpointError(Exception):
    """The stored graph thread cannot safely regenerate the requested post."""


def _db_url() -> str:
    return (
        settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql")
        .replace("postgresql+asyncpg", "postgresql")
        .replace("postgresql+psycopg", "postgresql")
    )


async def _resume_graph_for_regenerate_async(
    generation_cycle_id: str,
    feedback: str,
    regenerate_image: bool = False,
    expected_workspace_id: str | None = None,
    expected_post_id: str | None = None,
    checkpointer=None,
):
    graph = get_compiled_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": generation_cycle_id}}
    human_notes = f"Human reviewer feedback: {feedback}"

    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise RegenerationCheckpointError(
            f"No generation checkpoint found for cycle {generation_cycle_id}"
        )

    checkpoint_cycle_id = str(snapshot.values.get("generation_cycle_id") or "")
    checkpoint_workspace_id = str(snapshot.values.get("workspace_id") or "")
    checkpoint_post_id = str(snapshot.values.get("post_id") or "")
    if checkpoint_cycle_id != generation_cycle_id:
        raise RegenerationCheckpointError(
            "Generation checkpoint does not match the requested cycle."
        )
    if expected_workspace_id and checkpoint_workspace_id != expected_workspace_id:
        raise RegenerationCheckpointError(
            "Generation checkpoint does not match the requested workspace."
        )
    if expected_post_id and checkpoint_post_id != expected_post_id:
        raise RegenerationCheckpointError(
            "Generation checkpoint does not match the requested post."
        )

    previous_total = snapshot.values.get(
        "total_regenerate_count",
        snapshot.values.get("reviewer_retry_count", 0),
    )
    update = {
        "reviewer_notes": human_notes,
        "reviewer_passed": False,
        # A human request starts a fresh reviewer loop while incrementing the
        # cumulative rewrite count used by the API's five-regeneration cap.
        "reviewer_retry_count": 0,
        "total_regenerate_count": previous_total + 1,
        "force_regenerate_image": regenerate_image,
        "is_human_regeneration": True,
    }

    # AsyncPostgresSaver requires aupdate_state (not sync update_state).
    # Mark the update as coming from strategy so LangGraph schedules writer next.
    # Using as_node="writer" skips writer execution and only runs its downstream
    # nodes, which leaves caption/hashtags/CTA unchanged.
    await graph.aupdate_state(
        config,
        update,
        as_node="strategy",
    )

    result = await graph.ainvoke(None, config=config)
    return result


async def resume_generation_for_regenerate(
    generation_cycle_id: str,
    feedback: str,
    regenerate_image: bool = False,
    expected_workspace_id: str | None = None,
    expected_post_id: str | None = None,
):
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
            regenerate_image=regenerate_image,
            expected_workspace_id=expected_workspace_id,
            expected_post_id=expected_post_id,
            checkpointer=checkpointer,
        )
