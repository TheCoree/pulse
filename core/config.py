from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str

    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    FRONTEND_URL: str = "http://localhost"

    class Config:
        env_file = "../.env"


settings = Settings()
