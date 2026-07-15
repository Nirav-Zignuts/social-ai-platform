from langgraph.graph import StateGraph, START, END
from app.services.generation.state import GenerationState
from app.services.generation.debug_log import gen_log
from app.services.generation.nodes import (
    context_builder_node,
    strategy_node,
    writer_node,
    image_node,
    reviewer_node,
    persist_post_node
)

def should_generate_image(state: GenerationState):
    decision = "generate_image" if state.get("needs_image") else "skip_image"
    gen_log(
        "ROUTER → after writer (should_generate_image)",
        needs_image=state.get("needs_image"),
        decision=decision,
        next_node="image" if decision == "generate_image" else "reviewer",
    )
    return decision

def reviewer_router(state: GenerationState):
    if state.get("reviewer_passed"):
        decision = "persist"
    else:
        retry_count = state.get("reviewer_retry_count", 0)
        decision = "retry_writer" if retry_count < 2 else "persist"

    gen_log(
        "ROUTER → after reviewer (reviewer_router)",
        reviewer_passed=state.get("reviewer_passed"),
        reviewer_score=state.get("reviewer_score"),
        retry_count=state.get("reviewer_retry_count", 0),
        decision=decision,
        next_node="persist" if decision == "persist" else "increment_retry → writer",
    )
    return decision

def increment_retry(state: GenerationState):
    new_count = state.get("reviewer_retry_count", 0) + 1
    gen_log(
        "NODE → increment_retry (loop back to writer)",
        previous_retry_count=state.get("reviewer_retry_count", 0),
        new_retry_count=new_count,
        reviewer_notes=state.get("reviewer_notes"),
    )
    return {"reviewer_retry_count": new_count}

def build_generation_graph():
    builder = StateGraph(GenerationState)
    
    # Add Nodes
    builder.add_node("context_builder", context_builder_node)
    builder.add_node("strategy", strategy_node)
    builder.add_node("writer", writer_node)
    builder.add_node("image", image_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("increment_retry", increment_retry)
    builder.add_node("persist", persist_post_node)
    
    # Edges
    builder.add_edge(START, "context_builder")
    builder.add_edge("context_builder", "strategy")
    builder.add_edge("strategy", "writer")
    
    # Conditional image generation
    builder.add_conditional_edges(
        "writer",
        should_generate_image,
        {
            "generate_image": "image",
            "skip_image": "reviewer"
        }
    )
    
    builder.add_edge("image", "reviewer")
    
    # Reviewer router
    builder.add_conditional_edges(
        "reviewer",
        reviewer_router,
        {
            "persist": "persist",
            "retry_writer": "increment_retry"
        }
    )
    
    builder.add_edge("increment_retry", "writer")
    
    # After persist, pause/interrupt
    builder.add_edge("persist", END)
    
    return builder

# Compile it without checkpointer for testing/building. 
# Checkpointer will be injected when we run it.
generation_graph = build_generation_graph().compile(interrupt_before=[]) 
# We interrupt after persist by virtue of reaching END (which pauses if we resume later, or just ends)
# Wait, the instruction says "Pause after persist_post_node using the Postgres checkpointer"
# The canonical way to pause *after* persist is to add an interrupt on END, or just let it finish the thread and we can resume the thread if we append to it later.
# Or interrupt *after* persist. Let's do interrupt_after=["persist"].

def get_compiled_graph(checkpointer=None):
    gen_log(
        "GRAPH compile",
        has_checkpointer=checkpointer is not None,
        interrupt_after=["persist"],
        pipeline=[
            "START → context_builder → strategy → writer",
            "→ (image | skip) → reviewer",
            "→ (persist | increment_retry → writer)",
            "→ interrupt_after persist (human review / regenerate resume)",
        ],
    )
    builder = build_generation_graph()
    if checkpointer:
        return builder.compile(checkpointer=checkpointer, interrupt_after=["persist"])
    return builder.compile(interrupt_after=["persist"])
