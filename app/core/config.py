from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
load_dotenv()
import os

class Settings(BaseSettings):
    APP_NAME: str = "AI Marketing Platform"
    APP_VERSION: str = "1.0.0"

    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str

    SECRET_KEY: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    RSA_PRIVATE_KEY: str = os.getenv("RSA_PRIVATE_KEY")
    RSA_PUBLIC_KEY: str = os.getenv("RSA_PUBLIC_KEY")

    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    EMAIL_FROM: str
    FRONTEND_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()