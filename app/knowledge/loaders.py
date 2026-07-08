import os

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader

class EmptyDocumentError(Exception):
    """Exception raised when a document has no extractable text."""
    pass


def load_document_text(file_path: str, file_type: str) -> str:
    """
    Loads text from a document given its path and file type.
    
    Args:
        file_path: Path to the document.
        file_type: Extension of the document (pdf, docx, txt).
        
    Returns:
        The concatenated text of the document.
        
    Raises:
        EmptyDocumentError: If no extractable text is found.
        ValueError: If the file type is unsupported.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_type == "pdf":
        loader = PyPDFLoader(file_path)
    elif file_type == "docx":
        loader = Docx2txtLoader(file_path)
    elif file_type == "txt":
        loader = TextLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    documents = loader.load()
    
    # Concatenate all page content with double newline
    text = "\n\n".join(doc.page_content for doc in documents if doc.page_content)
    text = text.strip()
    
    if not text:
        raise EmptyDocumentError("No extractable text found — document may be a scanned image without OCR.")
        
    return text
