from typing import TypedDict, Optional, List

class GenerationState(TypedDict):
    workspace_id: str
    generation_cycle_id: str
    calendar_date: str                  # today's date, computed at graph invocation time
    
    content_type: Optional[str]         # decided by Content Strategy node
    content_type_rationale: Optional[str]
    
    business_context: str               # from Context Builder's RAG retrieval
    recent_posts_context: str           # from Context Builder's recent-posts query
    ai_config: dict
    
    caption: Optional[str]
    hashtags: Optional[List[str]]
    cta: Optional[str]
    needs_image: Optional[bool]         # decided by the Writer node
    
    image_url: Optional[str]
    force_regenerate_image: Optional[bool]
    is_human_regeneration: Optional[bool]
    
    reviewer_passed: Optional[bool]
    reviewer_score: Optional[int]
    reviewer_notes: Optional[str]
    # Automatic writer retries performed in the current graph run.
    reviewer_retry_count: int
    # Cumulative automatic + human-requested rewrites persisted on the post.
    total_regenerate_count: int
    
    post_id: Optional[str]
