import logging
from urllib.parse import quote

import requests

from app.utils.cloudinary_service import CloudinaryService

logger = logging.getLogger(__name__)


def generate_image(prompt: str, workspace_id: str, generation_cycle_id: str) -> str | None:
    """Generate an image via Pollinations and store it on Cloudinary."""
    try:
        encoded_prompt = quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            "?width=1024&height=1024&nologo=true"
        )
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        cloudinary = CloudinaryService()
        secure_url = cloudinary.upload_image(
            response.content,
            folder=f"generated_images/{workspace_id}",
            public_id=str(generation_cycle_id),
        )
        return secure_url
    except Exception:
        logger.exception("Failed to generate or upload image to Cloudinary")
        return None
