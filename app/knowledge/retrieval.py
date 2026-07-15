from typing import Any

from app.knowledge.vectorstore import (
    get_retrieval_embeddings,
    get_chroma_persist_dir,
    rehydrate_workspace_vectors_from_db,
)
from langchain_chroma import Chroma


def retrieve_context(workspace_id: str, query: str, k: int = 5) -> list[dict[str, Any]]:
    """
    Retrieves the most relevant chunks for a given query from a workspace's knowledge base.

    Args:
        workspace_id: The ID of the workspace.
        query: The search query.
        k: The number of results to return.

    Returns:
        A list of dictionaries containing text/chunk_text, chunk_index, and document_id.
    """
    workspace_id = str(workspace_id)

    # Heal Postgres↔Chroma desync: indexed docs with empty Chroma collection.
    rehydrate_workspace_vectors_from_db(workspace_id)

    collection_name = f"workspace_{workspace_id}"
    persist_directory = get_chroma_persist_dir()

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=get_retrieval_embeddings(),
        persist_directory=persist_directory,
    )

    results = vectorstore.similarity_search(query, k=k)

    context_chunks = []
    for doc in results:
        text = doc.page_content
        context_chunks.append(
            {
                "text": text,
                "chunk_text": text,
                "chunk_index": doc.metadata.get("chunk_index"),
                "document_id": doc.metadata.get("document_id"),
            }
        )

    return context_chunks
