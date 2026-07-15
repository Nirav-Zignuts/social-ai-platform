"""Single source of truth for onboarding chat profile fields."""

REQUIRED_PROFILE_FIELDS = {
    "business_name": "The business's name",
    "industry": "What category/industry the business is in",
    "description": "What the business does, in enough detail to write good social content about it",
    "target_audience": "Who the business's customers typically are",
    "brand_voice": "How the business wants to sound in its content (tone, personality)",
}

OPTIONAL_PROFILE_FIELDS = {
    "prohibited_words": "Words or phrases the business never wants used",
    "required_keywords": "Words/phrases that should always appear",
}

# Hard guardrail: after this many user messages, force synthesis without another LLM turn.
MAX_ONBOARDING_TURNS = 20

ALL_PROFILE_FIELD_KEYS = tuple(REQUIRED_PROFILE_FIELDS) + tuple(OPTIONAL_PROFILE_FIELDS)
