import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Any

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "KrushiMitra AI"
    APP_VERSION: str = "2.1.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # LLM Providers
    DEFAULT_AI_PROVIDER: str = "groq"
    GROQ_API_KEY: Optional[str] = None
    GROQ_TEXT_MODEL: str = "openai/gpt-oss-120b"
    GROQ_FALLBACK_MODELS: str = "qwen/qwen3.8-27b,openai/gpt-oss-20b,llama-3.3-70b-versatile"
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # Database
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_db_url(cls, v: Any) -> Any:
        if not v:
            return v
        v_str = str(v).strip()
        # Handle postgres:// connection strings from providers like Supabase, Render, Neon
        if v_str.startswith("postgres://"):
            return "postgresql://" + v_str[len("postgres://"):]
        return v_str

    def model_post_init(self, __context: Any) -> None:
        is_vercel = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))
        is_prod = self.ENVIRONMENT.lower() == "production" or is_vercel
        # In local development without an explicit DATABASE_URL, default to SQLite
        if not self.DATABASE_URL and not is_prod:
            self.DATABASE_URL = f"sqlite:///{BASE_DIR}/data/krushimitra.db"

    # Weather & Mandi
    WEATHER_API_PROVIDER: str = "open-meteo"
    WEATHER_CACHE_MINUTES: int = 30
    MANDI_CACHE_HOURS: int = 6

    # Defaults
    DEFAULT_REGION: str = "Maharashtra"
    DEFAULT_LANGUAGE: str = "English"

    def get_database_url(self) -> str:
        """
        Returns the effective normalized database URL.
        Converts postgres:// to postgresql:// for SQLAlchemy.
        """
        raw_url = (self.DATABASE_URL or "").strip()
        if raw_url.startswith("postgres://"):
            raw_url = "postgresql://" + raw_url[len("postgres://"):]
        return raw_url

    def is_production_or_vercel(self) -> bool:
        return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or self.ENVIRONMENT.lower() == "production")

    def get_groq_models(self) -> List[str]:
        models = [self.GROQ_TEXT_MODEL]
        if self.GROQ_FALLBACK_MODELS:
            for m in self.GROQ_FALLBACK_MODELS.split(","):
                m_clean = m.strip()
                if m_clean and m_clean not in models:
                    models.append(m_clean)
        return models

settings = Settings()
