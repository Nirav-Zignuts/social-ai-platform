import io
import logging
import os
import re
import tempfile
import time
from typing import BinaryIO

import cloudinary
import cloudinary.uploader
import cloudinary.utils
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudinaryConfigurationError(Exception):
    """Raised when Cloudinary credentials are missing."""


class CloudinaryUploadResult:
    def __init__(self, secure_url: str, public_id: str, resource_type: str):
        self.secure_url = secure_url
        self.public_id = public_id
        self.resource_type = resource_type


class CloudinaryService:
    """Upload and manage media/documents on Cloudinary."""

    _configured = False

    @classmethod
    def _configure(cls) -> None:
        if cls._configured:
            return

        if not all(
            [
                settings.CLOUDINARY_CLOUD_NAME,
                settings.CLOUDINARY_API_KEY,
                settings.CLOUDINARY_API_SECRET,
            ]
        ):
            raise CloudinaryConfigurationError(
                "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, "
                "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."
            )

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
        cls._configured = True

    @staticmethod
    def is_remote_url(path_or_url: str) -> bool:
        return path_or_url.startswith("http://") or path_or_url.startswith("https://")

    @staticmethod
    def is_cloudinary_url(url: str) -> bool:
        return "res.cloudinary.com" in url

    def upload_image(
        self,
        file_data: bytes | BinaryIO,
        *,
        folder: str,
        public_id: str,
    ) -> str:
        """Upload an image and return its secure URL."""
        result = self._upload(
            file_data,
            folder=folder,
            public_id=public_id,
            resource_type="image",
        )
        return result.secure_url

    def upload_document(
        self,
        file_data: bytes,
        *,
        folder: str,
        public_id: str,
    ) -> CloudinaryUploadResult:
        """Upload a knowledge-base document (pdf/docx/txt) as a raw resource."""
        return self._upload(
            file_data,
            folder=folder,
            public_id=public_id,
            resource_type="raw",
        )

    def _upload(
        self,
        file_data: bytes | BinaryIO,
        *,
        folder: str,
        public_id: str,
        resource_type: str,
    ) -> CloudinaryUploadResult:
        self._configure()
        payload = io.BytesIO(file_data) if isinstance(file_data, bytes) else file_data

        result = cloudinary.uploader.upload(
            payload,
            folder=folder,
            public_id=public_id,
            resource_type=resource_type,
            overwrite=True,
            access_mode="public",
        )
        return CloudinaryUploadResult(
            secure_url=result["secure_url"],
            public_id=result["public_id"],
            resource_type=resource_type,
        )

    def delete_resource(self, public_id: str, *, resource_type: str) -> None:
        """Delete a resource from Cloudinary by public_id."""
        self._configure()
        try:
            cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        except Exception:
            logger.exception("Failed to delete Cloudinary resource %s", public_id)

    @staticmethod
    def parse_cloudinary_url(url: str) -> tuple[str, str] | None:
        """Extract public_id (with extension for raw files) and format from a delivery URL."""
        match = re.search(r"/upload/v\d+/(.+)$", url)
        if not match:
            return None

        public_id = match.group(1)
        if "." in public_id.rsplit("/", 1)[-1]:
            file_format = public_id.rsplit(".", 1)[-1]
            return public_id, file_format
        return public_id, ""

    def resolve_public_id(
        self,
        *,
        secure_url: str | None = None,
        cloudinary_public_id: str | None = None,
    ) -> str | None:
        if cloudinary_public_id:
            return cloudinary_public_id
        if secure_url and self.is_cloudinary_url(secure_url):
            parsed = self.parse_cloudinary_url(secure_url)
            return parsed[0] if parsed else None
        return None

    def resolve_file_format(
        self,
        *,
        secure_url: str | None = None,
        file_format: str | None = None,
    ) -> str:
        if file_format:
            return file_format
        if secure_url and self.is_cloudinary_url(secure_url):
            parsed = self.parse_cloudinary_url(secure_url)
            if parsed and parsed[1]:
                return parsed[1]
        raise ValueError("Unable to determine Cloudinary file format.")

    def build_signed_download_url(
        self,
        public_id: str,
        *,
        resource_type: str,
        file_format: str = "",
    ) -> str:
        """Build a time-limited signed URL for server-side download."""
        self._configure()
        download_format = file_format
        if "." in public_id.rsplit("/", 1)[-1]:
            download_format = ""

        return cloudinary.utils.private_download_url(
            public_id,
            download_format,
            resource_type=resource_type,
            type="upload",
            expires_at=int(time.time()) + 3600,
        )

    def download_to_tempfile(
        self,
        *,
        suffix: str,
        secure_url: str | None = None,
        cloudinary_public_id: str | None = None,
        resource_type: str = "raw",
        file_format: str | None = None,
    ) -> str:
        """Download a Cloudinary (or plain HTTP) resource to a temp file."""
        fmt = self.resolve_file_format(secure_url=secure_url, file_format=file_format)
        public_id = self.resolve_public_id(
            secure_url=secure_url,
            cloudinary_public_id=cloudinary_public_id,
        )

        if public_id:
            download_url = self.build_signed_download_url(
                public_id,
                resource_type=resource_type,
                file_format=fmt,
            )
        elif secure_url:
            download_url = secure_url
        else:
            raise ValueError("Either secure_url or cloudinary_public_id is required.")

        response = httpx.get(download_url, timeout=60.0, follow_redirects=True)
        response.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(response.content)
            tmp.flush()
            return tmp.name
        finally:
            tmp.close()

    @staticmethod
    def cleanup_tempfile(path: str | None) -> None:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                logger.warning("Failed to remove temp file %s", path)
