from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
from typing import List
import warnings


class Settings(BaseSettings):
    PROJECT_NAME: str = "FoodBridge"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "PRODUCTION_STRENGTH_KEY_REQUIRED_IN_DOT_ENV"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # Database – override all values in .env for production
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "SET_SECURE_PASSWORD_IN_DOT_ENV"
    POSTGRES_DB: str = "foodbridge"

    # CORS – comma-separated origins allowed to call the API
    BACKEND_CORS_ORIGINS: str = (
        "http://localhost,http://localhost:8000,http://localhost:5500"
    )

    @computed_field
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        )

    @computed_field
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",")]

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Production security warning
if settings.SECRET_KEY == "PRODUCTION_STRENGTH_KEY_REQUIRED_IN_DOT_ENV":
    warnings.warn(
        "CRITICAL: Using default dummy SECRET_KEY! "
        "Application will be insecure. Set a strong SECRET_KEY in your .env file.",
        UserWarning,
        stacklevel=2,
    )
