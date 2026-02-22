from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    # --- Database ---
    DATABASE_URL: str

    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # --- JWT ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Frontend / CORS ---
    FRONTEND_URL: str = "http://localhost"
    CORS_ORIGINS: List[str] = Field(default_factory=list)

    # --- Bot ---
    BOT_SECRET_KEY: str = "change_me_in_env"
    TELEGRAM_BOT_TOKEN: str = "change_me_in_env"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
