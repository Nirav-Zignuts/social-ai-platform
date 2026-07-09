from langgraph.graph import StateGraph, START, END
from app.services.generation.state import GenerationState
from app.services.generation.nodes import (
    context_builder_node,
    strategy_node,
    writer_node,
    image_node,
    reviewer_node,
    persist_post_node
)

def should_generate_image(state: GenerationState):
    if state.get("needs_image"):
        return "generate_image"
    return "skip_image"

def reviewer_router(state: GenerationState):
    if state.get("reviewer_passed"):
        return "persist"
        
    # Failed. Check retries.
    retry_count = state.get("reviewer_retry_count", 0)
    if retry_count < 2:
        return "retry_writer"
    
    # Cap reached
    return "persist"

def increment_retry(state: GenerationState):
    return {"reviewer_retry_count": state.get("reviewer_retry_count", 0) + 1}

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
    builder = build_generation_graph()
    if checkpointer:
        return builder.compile(checkpointer=checkpointer, interrupt_after=["persist"])
    return builder.compile(interrupt_after=["persist"])
