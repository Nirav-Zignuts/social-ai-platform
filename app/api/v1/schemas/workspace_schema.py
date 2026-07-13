from datetime import datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(..., max_length=255)
    timezone: Optional[str] = Field("UTC", max_length=50)
    preferred_post_time: Optional[time] = None
    require_human_approval: Optional[bool] = True


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    timezone: Optional[str] = Field(None, max_length=50)
    preferred_post_time: Optional[time] = None
    require_human_approval: Optional[bool] = None


class WorkspaceResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    slug: str
    timezone: str
    preferred_post_time: Optional[time]
    require_human_approval: bool
    onboarding_status: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessProfileUpsert(BaseModel):
    business_name: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    target_audience: Optional[str] = None
    brand_voice: Optional[str] = None
    prohibited_words: Optional[list[str]] = None
    required_keywords: Optional[list[str]] = None
    website_url: Optional[str] = Field(None, max_length=500)


class BusinessProfileResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    business_name: Optional[str]
    industry: Optional[str]
    description: Optional[str]
    target_audience: Optional[str]
    brand_voice: Optional[str]
    prohibited_words: Optional[list[str]]
    required_keywords: Optional[list[str]]
    website_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    file_name: str
    file_type: str
    file_path: str
    file_size_bytes: Optional[int]
    status: str
    error_message: Optional[str]
    uploaded_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIConfigurationUpsert(BaseModel):
    content_style: Optional[str] = Field(None, max_length=50)
    caption_length: Optional[str] = Field(None, max_length=20)
    hashtag_count: Optional[int] = Field(8, ge=0)
    emoji_usage: Optional[str] = Field("moderate", max_length=20)
    cta_style: Optional[str] = Field(None, max_length=50)
    custom_instructions: Optional[str] = None


class AIConfigurationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    content_style: Optional[str]
    caption_length: Optional[str]
    hashtag_count: int
    emoji_usage: str
    cta_style: Optional[str]
    custom_instructions: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
