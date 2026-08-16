from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
    )

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./mindsforge.db"
    MEDIA_DIR: Path = BACKEND_DIR / "media"
    MINDS_BUILDER_API_KEY: str = ""
    MINDS_AGENT_ID: str = ""
    GROQ_API_KEY: str = ""
    TRANSCRIPTION_PROVIDER: str = "groq"
    WHISPER_MODEL: str = "small"
    HF_TOKEN: str = ""
    FFMPEG_BIN: str = "ffmpeg"
    PROCESS_JOBS_ON_SUBMIT: bool = True
    AB_TEST_INTERVAL_SECONDS: int = 60
    AB_TEST_VIEW_THRESHOLD: int = 1000

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    API_V1_PREFIX: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()