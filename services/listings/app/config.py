from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Listings Service"
    ENV: str = "development"
    DEBUG: bool = False

    # Database connection metadata
    LISTING_DB_HOST: str
    LISTING_DB_PORT: int = 5432
    LISTING_DB_NAME: str
    LISTING_DB_USER: str

    # JWT (validation only)
    JWT_ALGORITHM: str = "HS256"

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        allowed = {"HS256", "HS384", "HS512"}
        if v not in allowed:
            raise ValueError(f"JWT_ALGORITHM must be one of {allowed}")
        return v


settings = Settings()
