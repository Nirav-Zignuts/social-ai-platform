import logging
from urllib.parse import quote

import requests

from app.services.generation.debug_log import gen_log
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
        gen_log(
            "IMAGE → Pollinations request",
            workspace_id=workspace_id,
            generation_cycle_id=generation_cycle_id,
            prompt=prompt,
            url_preview=url[:180] + ("..." if len(url) > 180 else ""),
        )
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        cloudinary = CloudinaryService()
        secure_url = cloudinary.upload_image(
            response.content,
            folder=f"generated_images/{workspace_id}",
            public_id=str(generation_cycle_id),
        )
        gen_log("IMAGE → Cloudinary upload OK", secure_url=secure_url)
        return secure_url
    except Exception:
        logger.exception("Failed to generate or upload image to Cloudinary")
        gen_log(
            "IMAGE → FAILED",
            workspace_id=workspace_id,
            generation_cycle_id=generation_cycle_id,
            prompt=prompt,
        )
        return None
