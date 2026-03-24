from pydantic_settings import BaseSettings
from pathlib import Path


ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    OLLAMA_BASE_URL: str
    OLLAMA_MODEL: str

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    CONFIDENCE_THRESHOLD: float = 0.70

    model_config = {
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8"
    }

settings = Settings()