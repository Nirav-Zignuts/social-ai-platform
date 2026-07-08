import os
from langchain_cohere import CohereEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

CHROMA_PERSIST_DIR = "storage/chroma"

def get_retrieval_embeddings() -> CohereEmbeddings:
    """Returns Cohere embeddings configured for search query."""
    return CohereEmbeddings(
        model="embed-english-v3.0",
        cohere_api_key=os.environ.get("COHERE_API_KEY"),
        user_agent="social-ai-platform",
    )

def _get_ingestion_embeddings() -> CohereEmbeddings:
    """Returns Cohere embeddings configured for search document (ingestion)."""
    return CohereEmbeddings(
        model="embed-english-v3.0",
        cohere_api_key=os.environ.get("COHERE_API_KEY"),
        user_agent="social-ai-platform",
    )

def get_workspace_collection(workspace_id: str) -> Chroma:
    """Returns the Chroma vector store scoped to the given workspace."""
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
    collection_name = f"workspace_{workspace_id}"
    
    # We use ingestion embeddings here as LangChain's Chroma uses the embedding function
    # provided at construction time for add_texts (ingestion).
    return Chroma(
        collection_name=collection_name,
        embedding_function=_get_ingestion_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )

def index_chunks(workspace_id: str, document_id: str, chunks: list[str]) -> list[str]:
    """
    Indexes the chunks into ChromaDB for the given workspace and document.
    
    Returns:
        List of Chroma-assigned ids for the chunks.
    """
    if not chunks:
        return []
        
    vectorstore = get_workspace_collection(workspace_id)
    
    metadatas = [
        {
            "workspace_id": workspace_id,
            "document_id": document_id,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]
    
    # add_texts returns a list of assigned IDs
    chroma_ids = vectorstore.add_texts(texts=chunks, metadatas=metadatas)
    return chroma_ids

def delete_document_vectors(workspace_id: str, document_id: str) -> None:
    """Deletes all chunks belonging to a document from its workspace's Chroma collection."""
    vectorstore = get_workspace_collection(workspace_id)
    
    # Get the items matching the document_id
    result = vectorstore.get(where={"document_id": document_id})
    ids_to_delete = result.get("ids", [])
    
    if ids_to_delete:
        vectorstore.delete(ids_to_delete)
