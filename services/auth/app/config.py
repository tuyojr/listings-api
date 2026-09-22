from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Auth Service"
    ENV: str = "development"
    DEBUG: bool = False

    AUTH_DB_HOST: str
    AUTH_DB_PORT: int = 5432
    AUTH_DB_NAME: str
    AUTH_DB_USER: str

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 19456
    ARGON2_PARALLELISM: int = 1

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        # Only allow HMAC algorithms
        allowed = {"HS256", "HS384", "HS512"}
        if v not in allowed:
            raise ValueError(f"JWT_ALGORITHM must be one of {allowed}")
        return v


settings = Settings()
