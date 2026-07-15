from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.api.v1.schemas.workspace_schema import BusinessProfileUpsert


class OnboardingChatTurn(BaseModel):
    message: str = Field(
        description="The conversational message to show the user next"
    )
    quick_replies: list[str] = Field(
        description=(
            "ALWAYS provide 3-5 short tappable reply options for the question you are asking. "
            "Never return an empty list unless is_complete=true (final wrap-up). "
            "Even for open-ended fields (business name, description), offer concrete example chips "
            "the user can tap or adapt."
        ),
        min_length=0,
    )
    allow_multiple: bool = Field(
        default=False,
        description=(
            "True when the user should be able to select MORE THAN ONE quick_reply at once "
            "(e.g. target audience facets, brand voice traits, prohibited words, keywords, "
            "description aspects). False for single-answer questions like business name or "
            "primary industry. Always false when is_complete=true."
        ),
    )
    extracted_updates: dict[str, Any] = Field(
        description=(
            "Any fields from REQUIRED_PROFILE_FIELDS/OPTIONAL_PROFILE_FIELDS "
            "this turn's user answer filled in or updated, as key-value pairs. "
            "Empty dict on the very first turn (opening message, no user answer "
            "yet to extract from). If the user selected multiple options, combine them "
            "into one coherent value (or a list for prohibited_words / required_keywords)."
        )
    )
    is_complete: bool = Field(
        description=(
            "True only when all REQUIRED fields have been sufficiently collected "
            "and you're ready to move to final synthesis. False otherwise, even if "
            "the user seems to be wrapping up — only set true when you have "
            "genuinely enough detail on every required field."
        )
    )

    @field_validator("quick_replies", mode="before")
    @classmethod
    def _coerce_quick_replies(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return []


class BusinessProfileDraft(BusinessProfileUpsert):
    """Synthesized draft for FE review — not persisted to business_profiles here."""

    synthesis_notes: Optional[str] = Field(
        default=None,
        description=(
            "Notes about incomplete/placeholder fields when turn-cap forced "
            "early synthesis, or None if everything was solid."
        ),
    )
