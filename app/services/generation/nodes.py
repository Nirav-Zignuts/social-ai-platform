import os
from typing import Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from collections import Counter

from app.db.session import SessionLocal
from app.models.generated_post import GeneratedPost
from app.models.business_profile import BusinessProfile
from app.models.ai_configuration import AIConfiguration
from app.models.workspace import Workspace
from app.knowledge.retrieval import retrieve_context
from app.core.enums import GeneratedPostStatus
from app.core.llm_client import get_chat_model
from app.core.image_client import generate_image
from app.services.generation.state import GenerationState
from app.services.scheduling import calculate_next_scheduled_time
from app.services.notification_service import (
    notify_post_ready_for_review,
    notify_post_auto_approved,
)

# ----------------- Schemas -----------------
class StrategyOutput(BaseModel):
    content_type: str = Field(description="The chosen content type from the fixed set.")
    rationale: str = Field(description="Brief justification for this choice based on recent posts context.")

class WriterOutput(BaseModel):
    caption: str = Field(description="The main caption text for the post.")
    hashtags: List[str] = Field(description="List of hashtags.")
    cta: str = Field(description="Call to action text.")
    needs_image: bool = Field(description="Whether this post needs an accompanying generated image.")

class ReviewerOutput(BaseModel):
    score: int = Field(description="Score from 0 to 100 on how well it fits the brand voice and requirements.")
    notes: str = Field(description="Actionable notes if it failed, or brief/empty if passed.")


CONTENT_TYPES = [
    "educational", "promotional", "behind_the_scenes", 
    "product_highlight", "faq", "testimonial", "seasonal"
]

PASS_THRESHOLD = 70

# ----------------- Nodes -----------------

def context_builder_node(state: GenerationState) -> GenerationState:
    workspace_id = state["workspace_id"]
    
    with SessionLocal() as db:
        bp = db.query(BusinessProfile).filter(BusinessProfile.workspace_id == workspace_id).first()
        ai = db.query(AIConfiguration).filter(AIConfiguration.workspace_id == workspace_id).first()
        
        # Recent Posts
        recent_posts = db.query(GeneratedPost).filter(
            GeneratedPost.workspace_id == workspace_id,
            GeneratedPost.status.in_([GeneratedPostStatus.PUBLISHED.value, GeneratedPostStatus.APPROVED.value, GeneratedPostStatus.PENDING_REVIEW.value])
        ).order_by(GeneratedPost.created_at.desc()).limit(20).all()
        
        if not recent_posts:
            recent_posts_context = "No recent posts found for this workspace. This is the first post."
        else:
            recent_lines = []
            for p in recent_posts:
                first_line = p.caption.split('\n')[0] if p.caption else ""
                ctype = p.content_type or "unknown"
                recent_lines.append(f"- Type: {ctype} | Hook: {first_line[:50]}...")
            recent_posts_context = "Recent Posts Context:\n" + "\n".join(recent_lines)
            
        # AI Config Dict
        ai_config = {
            "content_style": ai.content_style if ai else "",
            "caption_length": ai.caption_length if ai else "medium",
            "hashtag_count": ai.hashtag_count if ai else 5,
            "emoji_usage": ai.emoji_usage if ai else "moderate",
            "cta_style": ai.cta_style if ai else "soft",
            "custom_instructions": ai.custom_instructions if ai else "",
            "brand_voice": bp.brand_voice if bp else "",
            "prohibited_words": bp.prohibited_words if bp else [],
            "required_keywords": bp.required_keywords if bp else [],
        }
        
        # RAG Retrieval
        if bp and bp.business_name and bp.industry:
            query = f"Generate an Instagram post for {bp.business_name}, a {bp.industry} business"
            try:
                retrieved_chunks = retrieve_context(workspace_id, query, k=5)
                if retrieved_chunks:
                    business_context = "Business Context from Knowledge Base:\n"
                    for chunk in retrieved_chunks:
                        business_context += f"- {chunk.get('text', '')}\n"
                else:
                    business_context = f"Business profile for {bp.business_name} ({bp.industry}). No specific knowledge base documents found."
            except Exception:
                business_context = f"Business profile for {bp.business_name} ({bp.industry}). (Knowledge base retrieval failed)."
        else:
            business_context = "No detailed business profile available."
            
    return {
        **state,
        "recent_posts_context": recent_posts_context,
        "business_context": business_context,
        "ai_config": ai_config
    }


def strategy_node(state: GenerationState) -> GenerationState:
    # Do not re-run if already selected (e.g. during retry)
    if state.get("content_type"):
        return state
        
    recent_context = state["recent_posts_context"]
    
    prompt = f"""
    You are a Content Strategist. Your goal is to pick today's content type from the following fixed set:
    {', '.join(CONTENT_TYPES)}
    
    Here is what the brand recently posted:
    {recent_context}
    
    Pick a type that hasn't been used recently, or provides good variety. 
    Explicitly avoid the most recently used types.
    If there are no recent posts, pick any type freely.
    Briefly justify your choice.
    """
    
    model = get_chat_model("strategist")
    structured_llm = model.with_structured_output(StrategyOutput)
    
    try:
        result = structured_llm.invoke(prompt)
        content_type = result.content_type
        rationale = result.rationale
        
        # Validate content_type
        if content_type not in CONTENT_TYPES:
            content_type = CONTENT_TYPES[0]
            
    except Exception as e:
        # Fallback to least used
        import re
        types_found = re.findall(r"Type: (\w+)", recent_context)
        if not types_found:
            content_type = "educational"
        else:
            counts = Counter(types_found)
            # Find least used among the allowed types
            allowed_counts = {t: counts.get(t, 0) for t in CONTENT_TYPES}
            content_type = min(allowed_counts, key=allowed_counts.get)
        rationale = "Fallback deterministic selection due to LLM failure."

    return {
        **state,
        "content_type": content_type,
        "content_type_rationale": rationale
    }


def writer_node(state: GenerationState) -> GenerationState:
    ai_c = state["ai_config"]
    
    prompt = f"""
    You are an expert Social Media Copywriter .
    
    Today's Date: {state['calendar_date']}
    Content Type: {state['content_type']}
    Strategy Rationale: {state['content_type_rationale']}
    
    AI Configuration Preferences:
    - Style: {ai_c['content_style']}
    - Caption Length: {ai_c['caption_length']}
    - Hashtags: {ai_c['hashtag_count']}
    - Emoji Usage: {ai_c['emoji_usage']}
    - CTA Style: {ai_c['cta_style']}
    - Custom Instructions: {ai_c['custom_instructions']}
    - Brand Voice: {ai_c['brand_voice']}
    - Words you must NEVER use: {', '.join(ai_c['prohibited_words']) or 'none specified'}
    - Keywords that MUST appear at least once: {', '.join(ai_c['required_keywords']) or 'none specified'}
    
    Business Context:
    {state['business_context']}
    
    Recent Posts Context (AVOID repeating hooks, phrasing, or angles used in these):
    {state['recent_posts_context']}
    
    """
    
    if state.get("reviewer_notes"):
        prompt += f"\nNOTE: Your previous attempt was rejected for this reason: {state['reviewer_notes']}. Revise accordingly."
        
    model = get_chat_model("writer")
    structured_llm = model.with_structured_output(WriterOutput)
    
    try:
        result = structured_llm.invoke(prompt)
        caption = result.caption
        hashtags = result.hashtags
        cta = result.cta
        needs_image = result.needs_image
    except Exception as e:
        # Simplistic fallback
        caption = "Default generated caption due to error."
        hashtags = ["#fallback"]
        cta = "Check out our link in bio!"
        needs_image = False
        # logger.error(f"Writer LLM failed for cycle {state['generation_cycle_id']}: {e}")

        
    return {
        **state,
        "caption": caption,
        "hashtags": hashtags,
        "cta": cta,
        "needs_image": needs_image
    }


def image_node(state: GenerationState) -> GenerationState:
    # Only called if needs_image == True, but we can double check
    if not state.get("needs_image"):
        return state
        
    # Skip if we already generated one in a previous pass
    if state.get("image_url"):
        return state

    prompt = f"An engaging social media image representing the theme: {state.get('caption', '')[:100]}"
    image_url = generate_image(prompt, state["workspace_id"], state["generation_cycle_id"])
    
    return {
        **state,
        "image_url": image_url
    }


def reviewer_node(state: GenerationState) -> GenerationState:
    prompt = f"""
    You are a strict Brand Compliance Reviewer. Check this post against EXACT rules, not general quality.
    Review the following proposed post. 
    
    Content Type: {state['content_type']}
    Caption: {state['caption']}
    Hashtags: {state['hashtags']}
    CTA: {state['cta']}
    
    Does this properly fit the requested content type? Is it high quality?
    Provide a score from 0-100.
    """
    
    model = get_chat_model("reviewer")
    structured_llm = model.with_structured_output(ReviewerOutput)
    
    try:
        result = structured_llm.invoke(prompt)
        score = result.score
        notes = result.notes
    except Exception:
        score = 0
        notes = f"Automated review failed to run ({str(e)[:100]}). Manual review required."
        passed = False

        
    passed = score >= PASS_THRESHOLD
    
    return {
        **state,
        "reviewer_score": score,
        "reviewer_passed": passed,
        "reviewer_notes": notes
    }


def persist_post_node(state: GenerationState) -> GenerationState:
    with SessionLocal() as db:
        workspace = db.query(Workspace).filter(
            Workspace.id == state["workspace_id"]
        ).first()

        post = db.query(GeneratedPost).filter(
            GeneratedPost.generation_cycle_id == state["generation_cycle_id"],
            GeneratedPost.workspace_id == state["workspace_id"]
        ).first()

        require_human_approval = (
            workspace.require_human_approval if workspace else True
        )

        if require_human_approval:
            post_status = GeneratedPostStatus.PENDING_REVIEW.value
            scheduled_for = None
        else:
            post_status = GeneratedPostStatus.APPROVED.value
            scheduled_for = (
                calculate_next_scheduled_time(workspace) if workspace else None
            )

        if not post:
            post = GeneratedPost(
                workspace_id=state["workspace_id"],
                generation_cycle_id=state["generation_cycle_id"],
                content_type=state.get("content_type"),
                caption=state.get("caption"),
                hashtags=state.get("hashtags"),
                cta=state.get("cta"),
                image_url=state.get("image_url"),
                status=post_status,
                reviewer_notes=state.get("reviewer_notes"),
                reviewer_score=state.get("reviewer_score"),
                regenerate_count=state.get("reviewer_retry_count", 0),
                scheduled_for=scheduled_for,
            )
            db.add(post)
        else:
            post.content_type = state.get("content_type")
            post.caption = state.get("caption")
            post.hashtags = state.get("hashtags")
            post.cta = state.get("cta")
            post.image_url = state.get("image_url")
            post.status = post_status
            post.reviewer_notes = state.get("reviewer_notes")
            post.reviewer_score = state.get("reviewer_score")
            post.regenerate_count = state.get("reviewer_retry_count", 0)
            if scheduled_for is not None:
                post.scheduled_for = scheduled_for

        db.commit()
        db.refresh(post)
        post_id = str(post.id)

    if require_human_approval:
        notify_post_ready_for_review(post_id)
    else:
        notify_post_auto_approved(post_id)

    return {
        **state,
        "post_id": post_id
    }
