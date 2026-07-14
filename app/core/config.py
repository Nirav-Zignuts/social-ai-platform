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

    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

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

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        object.__setattr__(self, "DATABASE_URL", _normalize_database_url(self.DATABASE_URL))
        object.__setattr__(self, "RSA_PRIVATE_KEY", _normalize_pem(self.RSA_PRIVATE_KEY) or "")
        object.__setattr__(self, "RSA_PUBLIC_KEY", _normalize_pem(self.RSA_PUBLIC_KEY) or "")


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
