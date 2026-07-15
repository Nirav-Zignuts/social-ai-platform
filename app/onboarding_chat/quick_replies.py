"""Fallback quick-reply chips when the LLM returns too few/none."""

from __future__ import annotations

from typing import Any

from app.onboarding_chat.constants import (
    OPTIONAL_PROFILE_FIELDS,
    REQUIRED_PROFILE_FIELDS,
)

# Order matters: first empty required field drives the fallback set.
_FALLBACK_BY_FIELD: dict[str, list[str]] = {
    "business_name": [
        "It's a cafe / restaurant",
        "It's a shop / store",
        "It's a service business",
        "It's a clinic / studio",
        "It's a personal brand / creator",
    ],
    "industry": [
        "Food & Drink",
        "Retail / Ecommerce",
        "Health & Wellness",
        "Beauty / Personal care",
        "Professional services",
    ],
    "description": [
        "We sell physical products",
        "We offer services / appointments",
        "We teach / coach people",
        "We make food or drinks",
        "We help with local everyday needs",
    ],
    "target_audience": [
        "Local customers nearby",
        "Busy professionals",
        "Families / parents",
        "Young adults / students",
        "Other businesses (B2B)",
    ],
    "brand_voice": [
        "Warm and friendly",
        "Bold and fun",
        "Professional and clear",
        "Calm and reassuring",
        "Simple and direct",
    ],
    "prohibited_words": [
        "No words to avoid",
        "Avoid hype words (guarantee, miracle)",
        "Avoid salesy pressure words",
        "Avoid slang / jokes",
        "I'll type specific words",
    ],
    "required_keywords": [
        "Just use my business name",
        "Mention our city / location",
        "Mention our main product",
        "No special keywords",
        "I'll type specific keywords",
    ],
}

# Fields where picking several chips at once is useful.
_MULTI_SELECT_FIELDS = frozenset(
    {
        "description",
        "target_audience",
        "brand_voice",
        "prohibited_words",
        "required_keywords",
    }
)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def next_missing_field(collected: dict[str, Any] | None) -> str | None:
    collected = collected or {}
    for key in REQUIRED_PROFILE_FIELDS:
        if _is_empty(collected.get(key)):
            return key
    for key in OPTIONAL_PROFILE_FIELDS:
        if key not in collected:
            return key
    return None


def fallback_quick_replies(collected: dict[str, Any] | None) -> list[str]:
    field = next_missing_field(collected) or "brand_voice"
    return list(_FALLBACK_BY_FIELD.get(field, _FALLBACK_BY_FIELD["brand_voice"]))


def default_allow_multiple(collected: dict[str, Any] | None) -> bool:
    field = next_missing_field(collected)
    if field is None:
        return False
    return field in _MULTI_SELECT_FIELDS


def normalize_stored_quick_replies(
    raw: Any,
) -> tuple[list[str], bool]:
    """Decode DB quick_replies (legacy list or {options, allow_multiple})."""
    if raw is None:
        return [], False
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()], False
    if isinstance(raw, dict):
        options = raw.get("options") or raw.get("quick_replies") or []
        if not isinstance(options, list):
            options = []
        return (
            [str(x) for x in options if str(x).strip()],
            bool(raw.get("allow_multiple", False)),
        )
    return [], False


def encode_quick_replies(options: list[str], allow_multiple: bool) -> dict:
    return {
        "options": list(options),
        "allow_multiple": bool(allow_multiple),
    }
