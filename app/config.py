from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

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
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/krushimitra.db"

    # Weather & Mandi
    WEATHER_API_PROVIDER: str = "open-meteo"
    WEATHER_CACHE_MINUTES: int = 30
    MANDI_CACHE_HOURS: int = 6

    # Defaults
    DEFAULT_REGION: str = "Maharashtra"
    DEFAULT_LANGUAGE: str = "English"

    def get_groq_models(self) -> List[str]:
        models = [self.GROQ_TEXT_MODEL]
        if self.GROQ_FALLBACK_MODELS:
            for m in self.GROQ_FALLBACK_MODELS.split(","):
                m_clean = m.strip()
                if m_clean and m_clean not in models:
                    models.append(m_clean)
        return models

settings = Settings()
