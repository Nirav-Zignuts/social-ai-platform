from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AI Marketing Platform"
    APP_VERSION: str = "1.0.0"

    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str

    SECRET_KEY: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()