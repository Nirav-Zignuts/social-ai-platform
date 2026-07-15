import logging
import os
from uuid import UUID

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_cohere import CohereEmbeddings

from app.core.config import settings

load_dotenv()

logger = logging.getLogger(__name__)


def get_chroma_persist_dir() -> str:
    """Absolute Chroma persist path (cwd-independent)."""
    path = settings.CHROMA_PERSIST_DIR
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    os.makedirs(path, exist_ok=True)
    return path


# Backwards-compatible alias used by retrieval.py / tests.
CHROMA_PERSIST_DIR = get_chroma_persist_dir()


def get_retrieval_embeddings() -> CohereEmbeddings:
    """Returns Cohere embeddings (embed_query uses input_type=search_query)."""
    return CohereEmbeddings(
        model="embed-english-v3.0",
        cohere_api_key=os.environ.get("COHERE_API_KEY") or settings.COHERE_API_KEY,
        user_agent="social-ai-platform",
    )


def _get_ingestion_embeddings() -> CohereEmbeddings:
    """Returns Cohere embeddings (embed_documents uses input_type=search_document)."""
    return CohereEmbeddings(
        model="embed-english-v3.0",
        cohere_api_key=os.environ.get("COHERE_API_KEY") or settings.COHERE_API_KEY,
        user_agent="social-ai-platform",
    )


def get_workspace_collection(workspace_id: str) -> Chroma:
    """Returns the Chroma vector store scoped to the given workspace."""
    workspace_id = str(workspace_id)
    persist_directory = get_chroma_persist_dir()
    collection_name = f"workspace_{workspace_id}"

    return Chroma(
        collection_name=collection_name,
        embedding_function=_get_ingestion_embeddings(),
        persist_directory=persist_directory,
    )


def collection_vector_count(workspace_id: str) -> int:
    """Return how many vectors are currently in the workspace Chroma collection."""
    vectorstore = get_workspace_collection(str(workspace_id))
    result = vectorstore.get()
    return len(result.get("ids") or [])


def index_chunks(workspace_id: str, document_id: str, chunks: list[str]) -> list[str]:
    """
    Indexes the chunks into ChromaDB for the given workspace and document.

    Returns:
        List of Chroma-assigned ids for the chunks.
    """
    if not chunks:
        return []

    workspace_id = str(workspace_id)
    document_id = str(document_id)
    vectorstore = get_workspace_collection(workspace_id)

    metadatas = [
        {
            "workspace_id": workspace_id,
            "document_id": document_id,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    chroma_ids = vectorstore.add_texts(texts=chunks, metadatas=metadatas)
    logger.info(
        "Indexed %s chunks into Chroma collection workspace_%s (persist=%s)",
        len(chroma_ids),
        workspace_id,
        get_chroma_persist_dir(),
    )
    return chroma_ids


def delete_document_vectors(workspace_id: str, document_id: str) -> None:
    """Deletes all chunks belonging to a document from its workspace's Chroma collection."""
    workspace_id = str(workspace_id)
    document_id = str(document_id)
    vectorstore = get_workspace_collection(workspace_id)

    result = vectorstore.get(where={"document_id": document_id})
    ids_to_delete = result.get("ids", [])

    if ids_to_delete:
        vectorstore.delete(ids_to_delete)


def rehydrate_workspace_vectors_from_db(workspace_id: str) -> int:
    """
    If Postgres has knowledge_chunks but Chroma is empty for this workspace,
    rebuild the Chroma collection from DB chunk texts.

    Returns number of vectors written (0 if nothing to do / nothing in DB).
    """
    from app.db.session import SessionLocal
    from app.models.knowledge_chunk import KnowledgeChunk

    workspace_id = str(workspace_id)
    existing = collection_vector_count(workspace_id)
    if existing > 0:
        return 0

    with SessionLocal() as db:
        try:
            ws_uuid = UUID(workspace_id)
        except ValueError:
            ws_uuid = workspace_id  # type: ignore[assignment]

        rows = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.workspace_id == ws_uuid)
            .order_by(KnowledgeChunk.document_id, KnowledgeChunk.chunk_index)
            .all()
        )
        if not rows:
            return 0

        # Group by document for metadata + update chroma_ids after add.
        by_doc: dict[str, list] = {}
        for row in rows:
            by_doc.setdefault(str(row.document_id), []).append(row)

        written = 0
        for document_id, doc_rows in by_doc.items():
            texts = [r.chunk_text for r in doc_rows]
            chroma_ids = index_chunks(workspace_id, document_id, texts)
            for row, chroma_id in zip(doc_rows, chroma_ids):
                row.chroma_id = chroma_id
                db.add(row)
            written += len(chroma_ids)

        db.commit()
        logger.warning(
            "Rehydrated %s Chroma vectors for workspace %s from knowledge_chunks "
            "(collection was empty)",
            written,
            workspace_id,
        )
        return written
