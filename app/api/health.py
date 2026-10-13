from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings
from app.services.rag_service import RAGService

router = APIRouter(prefix="/api", tags=["Health"])

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint reporting backend, database, RAG index, and AI provider statuses.
    """
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    fts_count = 0
    try:
        fts_count = RAGService.get_document_count(db)
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_ok else "error",
        "rag_indexed_documents": fts_count,
        "ai_provider": {
            "configured": bool(settings.GROQ_API_KEY or settings.GEMINI_API_KEY or settings.OPENAI_API_KEY),
            "primary": settings.DEFAULT_AI_PROVIDER,
            "vision_model": settings.GROQ_VISION_MODEL if settings.GROQ_API_KEY else "Not configured",
            "fallback_available": True
        }
    }
