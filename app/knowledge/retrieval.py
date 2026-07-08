from typing import Any

from app.knowledge.vectorstore import get_retrieval_embeddings, CHROMA_PERSIST_DIR
from langchain_chroma import Chroma

def retrieve_context(workspace_id: str, query: str, k: int = 5) -> list[dict[str, Any]]:
    """
    Retrieves the most relevant chunks for a given query from a workspace's knowledge base.
    
    Args:
        workspace_id: The ID of the workspace.
        query: The search query.
        k: The number of results to return.
        
    Returns:
        A list of dictionaries containing chunk_text, chunk_index, and document_id.
    """
    collection_name = f"workspace_{workspace_id}"
    
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=get_retrieval_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )
    
    # Run similarity search
    results = vectorstore.similarity_search(query, k=k)
    
    # Format results
    context_chunks = []
    for doc in results:
        context_chunks.append({
            "chunk_text": doc.page_content,
            "chunk_index": doc.metadata.get("chunk_index"),
            "document_id": doc.metadata.get("document_id"),
        })
        
    return context_chunks
