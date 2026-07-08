import logging
from datetime import datetime
from uuid import UUID

from celery_app import celery_app
from app.db.session import SessionLocal
from app.models.knowledge_document import KnowledgeDocument
from app.models.knowledge_chunk import KnowledgeChunk
from app.knowledge.loaders import load_document_text, EmptyDocumentError
from app.knowledge.chunking import chunk_text
from app.knowledge.vectorstore import index_chunks, delete_document_vectors

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=2, default_retry_delay=5)
def process_knowledge_document(self, document_id: str):
    """Celery task to process a knowledge document."""
    db = SessionLocal()
    try:
        # Fetch the knowledge_documents row
        print("Processing document", document_id)
        logger.info(f"Processing document {document_id}")
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == UUID(document_id)).first()
        if not doc:
            logger.error(f"Document {document_id} not found.")
            return

        # Transition status to processing
        doc.status = "processing"
        db.commit()
        logger.info(f"Document {document_id} status updated to processing.")
        # Load text
        try:
            text = load_document_text(doc.file_path, doc.file_type)
        except EmptyDocumentError as e:
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()
            return
        except Exception as e:
            # Re-raise extraction failures that are not expected EmptyDocumentErrors
            # so the task can retry
            raise

        try:
            # Chunk the text
            chunks = chunk_text(text)

            # Idempotency: delete any existing vectors and chunks
            delete_document_vectors(str(doc.workspace_id), document_id)
            db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete()
            db.commit()

            # Index chunks in Chroma
            chroma_ids = index_chunks(str(doc.workspace_id), document_id, chunks)

            # Insert knowledge_chunks rows
            for chroma_id, chunk in zip(chroma_ids, chunks):
                chunk_record = KnowledgeChunk(
                    document_id=doc.id,
                    workspace_id=doc.workspace_id,
                    chunk_text=chunk,
                    chunk_index=chunks.index(chunk),
                    chroma_id=chroma_id
                )
                db.add(chunk_record)

            # Update document status to indexed
            doc.status = "indexed"
            doc.indexed_at = datetime.utcnow()
            db.commit()

        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()
            raise self.retry(exc=e)

    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {str(e)}")
        # If the exception is outside the inner loop or is the retry itself, ensure we rollback
        db.rollback()
        raise
    finally:
        db.close()
