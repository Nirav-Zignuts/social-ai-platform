import os

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader

from app.utils.cloudinary_service import CloudinaryService


class EmptyDocumentError(Exception):
    """Exception raised when a document has no extractable text."""
    pass


def load_document_text(
    file_path: str,
    file_type: str,
    *,
    cloudinary_public_id: str | None = None,
) -> str:
    """
    Load text from a local path or a Cloudinary URL.

    Args:
        file_path: Local filesystem path or Cloudinary secure URL.
        file_type: Extension of the document (pdf, docx, txt).
        cloudinary_public_id: Cloudinary public_id for signed server-side download.

    Returns:
        The concatenated text of the document.

    Raises:
        EmptyDocumentError: If no extractable text is found.
        ValueError: If the file type is unsupported.
    """
    cloudinary = CloudinaryService()
    temp_path: str | None = None
    local_path = file_path

    try:
        if cloudinary.is_remote_url(file_path):
            temp_path = cloudinary.download_to_tempfile(
                secure_url=file_path,
                cloudinary_public_id=cloudinary_public_id,
                suffix=f".{file_type}",
                resource_type="raw",
                file_format=file_type,
            )
            local_path = temp_path
        elif not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_type == "pdf":
            loader = PyPDFLoader(local_path)
        elif file_type == "docx":
            loader = Docx2txtLoader(local_path)
        elif file_type == "txt":
            loader = TextLoader(local_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        documents = loader.load()
        text = "\n\n".join(doc.page_content for doc in documents if doc.page_content)
        text = text.strip()

        if not text:
            raise EmptyDocumentError(
                "No extractable text found — document may be a scanned image without OCR."
            )

        return text
    finally:
        cloudinary.cleanup_tempfile(temp_path)
