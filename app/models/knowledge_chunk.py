from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class KnowledgeChunk(BaseEntity):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chroma_id: Mapped[str] = mapped_column(String(255), nullable=False)

    document = relationship("KnowledgeDocument", back_populates="chunks")
    workspace = relationship("Workspace")
