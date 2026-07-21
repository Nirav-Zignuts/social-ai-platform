import logging
from urllib.parse import quote, urlencode

import requests

from app.core.config import settings
from app.utils.cloudinary_service import CloudinaryService

logger = logging.getLogger(__name__)

# Positive phrasing (models often ignore / reverse-interpret long "no text" lists).
IMAGE_VISUAL_GUARDRAILS = (
    "Photorealistic Instagram brand photograph, square 1:1 composition, "
    "natural lighting, sharp detail, magazine-quality. "
    "Pure visual storytelling only: pristine unmarked surfaces, "
    "blank packaging without labels, environment free of signage. "
    "Unlettered scene — no typography, logos, watermarks, banners, "
    "captions, subtitles, posters, stickers, UI, or readable writing of any kind. "
    "HUMAN ANATOMY QUALITY: if any person is visible, render a coherent, "
    "anatomically correct real human body."
)

LEGACY_FREE_BASE = "https://image.pollinations.ai/prompt"
# Retry target when legacy queue is full (Pollinations' recommended gateway).
GEN_BASE_DEFAULT = "https://gen.pollinations.ai"

# Treat these as "try next endpoint" (legacy overload often returns 500 Queue full).
_RETRYABLE_STATUS = frozenset({401, 402, 403, 429, 500, 502, 503, 504})


def assemble_image_prompt(visual_scene: str, caption: str | None = None) -> str:
    """
    Build the final Pollinations prompt.

    Caption is included for theme alignment with the post, but with an explicit
    instruction never to render those words as on-image text.
    """
    scene = (visual_scene or "").strip()
    if not scene:
        scene = (
            "clean lifestyle product photography with soft natural light "
            "and a single clear focal subject"
        )

    parts = [IMAGE_VISUAL_GUARDRAILS]

    caption_clean = (caption or "").strip()
    if caption_clean:
        # Keep alignment with the written post without inviting gibberish overlays.
        parts.append(
            "Generating image for this Instagram post caption "
            "(match subject, mood, and story only — "
            "DO NOT paint, write, carve, or overlay any of these words in the image): "
            f'"{caption_clean[:400]}"'
        )

    parts.append(f"Scene: {scene}")
    return " ".join(parts)


def _build_query(*, free_tier: bool) -> str:
    model = settings.POLLINATIONS_IMAGE_MODEL or "flux"
    width = settings.POLLINATIONS_IMAGE_WIDTH or 1024
    height = settings.POLLINATIONS_IMAGE_HEIGHT or 1024
    params: dict[str, str | int] = {
        "model": model,
        "width": width,
        "height": height,
        "enhance": "false",
    }
    # nologo is a paid feature — only on authenticated gen requests.
    if not free_tier:
        params["nologo"] = "true"
    return urlencode(params)


def _fetch_image(url: str, headers: dict[str, str] | None = None) -> requests.Response:
    return requests.get(url, headers=headers or {}, timeout=90)


def _is_image_body(response: requests.Response) -> bool:
    if not response.ok or not response.content:
        return False
    ctype = (response.headers.get("content-type") or "").lower()
    if "image" in ctype:
        return True
    # Some gateways return octet-stream / jpeg without a clear image/* type.
    return len(response.content) > 1000 and not ctype.startswith("application/json")


def generate_image(prompt: str, workspace_id: str, generation_cycle_id: str) -> str | None:
    """
    Generate via Pollinations free legacy first; on overload/failure retry
    gen.pollinations.ai with API key. If both fail, return None (post can continue without image).
    """
    try:
        final_prompt = prompt.strip()
        encoded_prompt = quote(final_prompt, safe="")
        model = settings.POLLINATIONS_IMAGE_MODEL or "flux"
        api_key = (settings.POLLINATIONS_API_KEY or "").strip()
        free_tier = bool(getattr(settings, "POLLINATIONS_FREE_TIER", True))
        gen_base = (settings.POLLINATIONS_BASE_URL or GEN_BASE_DEFAULT).rstrip("/")

        candidates: list[tuple[str, str, dict[str, str]]] = []

        if free_tier:
            free_url = f"{LEGACY_FREE_BASE}/{encoded_prompt}?{_build_query(free_tier=True)}"
            candidates.append(("free-legacy", free_url, {}))

        # Recommended fallback when legacy says "Queue full" / overloaded.
        if api_key:
            gen_url = f"{gen_base}/image/{encoded_prompt}?{_build_query(free_tier=False)}"
            candidates.append(
                ("gen-api-key", gen_url, {"Authorization": f"Bearer {api_key}"})
            )
        elif not free_tier:
            # No key and free disabled — still attempt legacy once.
            free_url = f"{LEGACY_FREE_BASE}/{encoded_prompt}?{_build_query(free_tier=True)}"
            candidates.append(("free-legacy", free_url, {}))

        if not candidates:
            logger.warning("No Pollinations candidates configured")
            return None

        response: requests.Response | None = None
        used_tier = candidates[0][0]
        last_error_body = ""

        for idx, (tier_name, url, headers) in enumerate(candidates):
            try:
                response = _fetch_image(url, headers)
            except requests.RequestException as exc:
                last_error_body = str(exc)
                logger.warning("Pollinations %s request failed: %s", tier_name, exc)
                response = None
                continue

            if _is_image_body(response):
                used_tier = tier_name
                break

            last_error_body = (response.text or "")[:500]
            logger.warning(
                "Pollinations %s → HTTP %s: %s",
                tier_name,
                response.status_code,
                last_error_body,
            )

            has_next = idx < len(candidates) - 1
            if has_next and response.status_code in _RETRYABLE_STATUS:
                logger.info(
                    "Pollinations %s failed (%s) — trying next endpoint "
                    "(enter.pollinations.ai / gen.pollinations.ai)",
                    tier_name,
                    response.status_code,
                )
                response = None
                continue

            # Non-retryable or last candidate — stop loop.
            response = None
            break

        if response is None or not response.content:
            logger.warning(
                "Pollinations image unavailable after all attempts "
                "(post will continue without image). Last: %s",
                last_error_body,
            )
            return None

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
