import logging
from datetime import datetime
from uuid import UUID

from app.db.session import SessionLocal
from app.models.knowledge_document import KnowledgeDocument
from app.models.knowledge_chunk import KnowledgeChunk
from app.knowledge.loaders import load_document_text, EmptyDocumentError
from app.knowledge.chunking import chunk_text
from app.knowledge.vectorstore import index_chunks, delete_document_vectors

logger = logging.getLogger(__name__)

MAX_INDEX_ATTEMPTS = 3


def process_knowledge_document(document_id: str) -> None:
    """Index a knowledge document into Chroma (sync entry for BackgroundTasks)."""
    last_error: Exception | None = None

    for attempt in range(1, MAX_INDEX_ATTEMPTS + 1):
        db = SessionLocal()
        try:
            logger.info(
                "Processing document %s (attempt %s/%s)",
                document_id,
                attempt,
                MAX_INDEX_ATTEMPTS,
            )
            doc = (
                db.query(KnowledgeDocument)
                .filter(KnowledgeDocument.id == UUID(document_id))
                .first()
            )
            if not doc:
                logger.error("Document %s not found.", document_id)
                return

            doc.status = "processing"
            db.commit()

            try:
                text = load_document_text(
                    doc.file_path,
                    doc.file_type,
                    cloudinary_public_id=doc.cloudinary_public_id,
                )
            except EmptyDocumentError as e:
                doc.status = "failed"
                doc.error_message = str(e)
                db.commit()
                return

            chunks = chunk_text(text)

            delete_document_vectors(str(doc.workspace_id), document_id)
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.document_id == doc.id
            ).delete()
            db.commit()

            chroma_ids = index_chunks(str(doc.workspace_id), document_id, chunks)

            for chroma_id, chunk in zip(chroma_ids, chunks):
                chunk_record = KnowledgeChunk(
                    document_id=doc.id,
                    workspace_id=doc.workspace_id,
                    chunk_text=chunk,
                    chunk_index=chunks.index(chunk),
                    chroma_id=chroma_id,
                )
                db.add(chunk_record)

            doc.status = "indexed"
            doc.indexed_at = datetime.utcnow()
            doc.error_message = None
            db.commit()
            return
        except Exception as e:
            last_error = e
            logger.exception(
                "Failed to process document %s on attempt %s: %s",
                document_id,
                attempt,
                e,
            )
            try:
                db.rollback()
                doc = (
                    db.query(KnowledgeDocument)
                    .filter(KnowledgeDocument.id == UUID(document_id))
                    .first()
                )
                if doc and attempt >= MAX_INDEX_ATTEMPTS:
                    doc.status = "failed"
                    doc.error_message = str(e)
                    db.commit()
            except Exception:
                logger.exception(
                    "Failed to persist error status for document %s", document_id
                )
        finally:
            db.close()

    if last_error:
        logger.error(
            "Giving up on document %s after %s attempts: %s",
            document_id,
            MAX_INDEX_ATTEMPTS,
            last_error,
        )
