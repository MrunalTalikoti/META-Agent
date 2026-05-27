from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

_WEAK_SECRETS = frozenset({
    "abc", "secret", "changeme", "password", "123456",
    "your_secret_key", "generate your secret key",
})

_MIN_KEY_LENGTH = 32


class Settings(BaseSettings):
    # App
    app_name: str = "MetaAgent"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: str

    # Cache
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if v.strip().lower() in _WEAK_SECRETS:
            raise ValueError(
                "SECRET_KEY is a known weak value. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if len(v) < _MIN_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_KEY_LENGTH} characters "
                f"(got {len(v)}). "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()