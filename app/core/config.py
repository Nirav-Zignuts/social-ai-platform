from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
load_dotenv()
import os

class Settings(BaseSettings):
    APP_NAME: str = "AI Marketing Platform"
    APP_VERSION: str = "1.0.0"

    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/social_ai_platform")

    SECRET_KEY: str

    # Shared secret for cron-job.org → /internal/* routes (header: X-Cron-Secret).
    # Separate from JWT SECRET_KEY — do not reuse the signing key in external cron.
    CRON_SECRET: str = os.getenv("CRON_SECRET", "")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    RSA_PRIVATE_KEY: str = os.getenv("RSA_PRIVATE_KEY")
    RSA_PUBLIC_KEY: str = os.getenv("RSA_PUBLIC_KEY")

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

    # Used if serving local media; generated images currently use Cloudinary HTTPS URLs.
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
    GOOGLE_OAUTH_ALLOWED_REDIRECT_URLS: str = os.getenv("GOOGLE_OAUTH_ALLOWED_REDIRECT_URLS", "")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()