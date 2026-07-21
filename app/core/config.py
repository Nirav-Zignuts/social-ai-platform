from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()
import os


def _normalize_database_url(url: str) -> str:
    """Render/Supabase often provide postgres:// or postgresql:// — SQLAlchemy needs +psycopg."""
    if not url:
        return url

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    host = (parsed.hostname or "").lower()
    # Managed Postgres (Supabase/Neon/Render) requires TLS from most PaaS hosts.
    if (
        "supabase.co" in host
        or "neon.tech" in host
        or "render.com" in host
        or "amazonaws.com" in host
    ) and "sslmode" not in query:
        query["sslmode"] = "require"
        parsed = parsed._replace(query=urlencode(query))
        url = urlunparse(parsed)

    return url


def _normalize_pem(value: str | None) -> str | None:
    """Render env vars often store PEM with literal \\n instead of real newlines."""
    if value is None:
        return None
    return value.replace("\\n", "\n").strip()


class Settings(BaseSettings):
    APP_NAME: str = "AI Marketing Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/social_ai_platform",
    )

    SECRET_KEY: str

    # Shared secret for cron-job.org → /internal/* routes (header: X-Cron-Secret).
    CRON_SECRET: str = os.getenv("CRON_SECRET", "")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    RSA_PRIVATE_KEY: str = os.getenv("RSA_PRIVATE_KEY", "")
    RSA_PUBLIC_KEY: str = os.getenv("RSA_PUBLIC_KEY", "")

    # Brevo HTTP API (use this on Render — SMTP ports are blocked on Free)
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    EMAIL_FROM: str = os.getenv(
        "EMAIL_FROM",
        "AI Marketing Platform <noreply@yourdomain.com>",
    )

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # SlowAPI rate limits (per client IP). Use redis://... for multi-worker deploys.
    RATE_LIMIT_STORAGE_URI: str = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
    RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "120/minute")
    RATE_LIMIT_AUTH: str = os.getenv("RATE_LIMIT_AUTH", "3/minute")
    RATE_LIMIT_AUTH_REFRESH: str = os.getenv("RATE_LIMIT_AUTH_REFRESH", "20/minute")
    TRUST_PROXY_HEADERS: bool = os.getenv(
        "TRUST_PROXY_HEADERS",
        "false",
    ).lower() in ("1", "true", "yes", "on")

    # Completely separate admin authentication surface. If the prefix or key is
    # absent, main.py does not register any admin routes (fail closed).
    ADMIN_ROUTE_PREFIX: str = os.getenv("ADMIN_ROUTE_PREFIX", "")
    ADMIN_JWE_SECRET: str = os.getenv("ADMIN_JWE_SECRET", "")
    ADMIN_OTP_PEPPER: str = os.getenv("ADMIN_OTP_PEPPER", "")
    ADMIN_SESSION_EXPIRE_MINUTES: int = int(
        os.getenv("ADMIN_SESSION_EXPIRE_MINUTES", "30")
    )
    ADMIN_OTP_EXPIRE_MINUTES: int = int(
        os.getenv("ADMIN_OTP_EXPIRE_MINUTES", "10")
    )

    META_APP_ID: str = os.getenv("META_APP_ID", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    META_REDIRECT_URI: str = os.getenv(
        "META_REDIRECT_URI",
        "http://localhost:8000/api/v1/instagram/callback",
    )
    META_GRAPH_VERSION: str = os.getenv("META_GRAPH_VERSION", "v21.0")
    META_SCOPES: str = os.getenv(
        "META_SCOPES",
        "instagram_basic,instagram_content_publish,instagram_manage_insights,"
        "pages_show_list,pages_read_engagement",
    )

    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")

    # Pollinations image generation
    # Free tier (default): image.pollinations.ai + model=flux (0 Pollen).
    # Set POLLINATIONS_FREE_TIER=false to force gen.pollinations.ai (needs Pollen for most models).
    POLLINATIONS_API_KEY: str = os.getenv("POLLINATIONS_API_KEY", "")
    POLLINATIONS_BASE_URL: str = os.getenv(
        "POLLINATIONS_BASE_URL",
        "https://gen.pollinations.ai",
    )
    POLLINATIONS_IMAGE_MODEL: str = os.getenv("POLLINATIONS_IMAGE_MODEL", "flux")
    POLLINATIONS_IMAGE_WIDTH: int = int(os.getenv("POLLINATIONS_IMAGE_WIDTH", "1024"))
    POLLINATIONS_IMAGE_HEIGHT: int = int(os.getenv("POLLINATIONS_IMAGE_HEIGHT", "1024"))
    POLLINATIONS_FREE_TIER: bool = os.getenv(
        "POLLINATIONS_FREE_TIER", "true"
    ).lower() in ("1", "true", "yes", "on")

    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/google/callback/",
    )
    GOOGLE_OAUTH_SCOPES: str = os.getenv(
        "GOOGLE_OAUTH_SCOPES",
        "openid email profile",
    )
    GOOGLE_OAUTH_DEFAULT_REDIRECT_URL: str = os.getenv(
        "GOOGLE_OAUTH_DEFAULT_REDIRECT_URL",
        f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/login",
    )
    GOOGLE_OAUTH_ALLOWED_REDIRECT_URLS: str = os.getenv(
        "GOOGLE_OAUTH_ALLOWED_REDIRECT_URLS", ""
    )

    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "storage/chroma")

    # Razorpay (use rzp_test_* until KYC; swap to rzp_live_* with zero code changes)
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        object.__setattr__(self, "DATABASE_URL", _normalize_database_url(self.DATABASE_URL))
        object.__setattr__(self, "RSA_PRIVATE_KEY", _normalize_pem(self.RSA_PRIVATE_KEY) or "")
        object.__setattr__(self, "RSA_PUBLIC_KEY", _normalize_pem(self.RSA_PUBLIC_KEY) or "")
        # Absolute path so uvicorn --reload / cwd changes don't split Chroma across dirs.
        chroma = self.CHROMA_PERSIST_DIR or "storage/chroma"
        if not os.path.isabs(chroma):
            chroma = os.path.abspath(chroma)
        object.__setattr__(self, "CHROMA_PERSIST_DIR", chroma)


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
