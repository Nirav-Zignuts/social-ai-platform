from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

def chunk_text(text: str) -> list[str]:
    """
    Splits text into chunks using a recursive character text splitter.
    
    Args:
        text: The text to chunk.
        
    Returns:
        A list of string chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_text(text)
