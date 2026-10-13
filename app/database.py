import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

def _build_engine(target_url: str):
    """Builds a SQLAlchemy engine configured for the target database dialect."""
    is_sqlite = target_url.startswith("sqlite")
    engine_kwargs = {}
    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Optimized for hosted PostgreSQL (Neon, Supabase, Render, Railway, AWS RDS)
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_recycle"] = 300
    return create_engine(target_url, **engine_kwargs)

def _get_initial_url() -> str:
    """
    Returns initial database URL for module import time.
    Falls back to in-memory SQLite if DATABASE_URL is unset, ensuring
    imports and serverless function packaging never fail at import time.
    """
    url = settings.get_database_url()
    if not url:
        return "sqlite:///:memory:"
    return url

# Global engine and session factory initialized safely at module scope
try:
    engine = _build_engine(_get_initial_url())
except Exception as _init_err:
    logger.warning(f"Initial engine construction deferred: {_init_err}. Using fallback placeholder.")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def refresh_engine_if_needed():
    """
    Ensures engine is bound to the latest DATABASE_URL if it was populated
    after module import time (common in serverless cold starts).
    """
    global engine, SessionLocal
    configured_url = settings.get_database_url()
    current_engine_url = str(engine.url) if engine else ""

    if configured_url and (current_engine_url == "sqlite:///:memory:" or current_engine_url != configured_url):
        logger.info("Configuring database engine for active request session")
        engine = _build_engine(configured_url)
        SessionLocal.configure(bind=engine)
    return engine

def get_db():
    refresh_engine_if_needed()
    is_vercel = settings.is_production_or_vercel()
    db_url = settings.get_database_url()

    if is_vercel:
        if not db_url:
            raise RuntimeError(
                "CRITICAL DATABASE ERROR: The DATABASE_URL environment variable is missing on Vercel. "
                "Please configure a hosted PostgreSQL connection string in your Vercel project environment variables."
            )
        if db_url.startswith("sqlite"):
            raise RuntimeError(
                "CRITICAL DATABASE ERROR: Local SQLite database cannot be used on Vercel. "
                "Vercel serverless functions operate in a read-only filesystem. "
                "Please configure a hosted PostgreSQL database via the DATABASE_URL environment variable."
            )

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_database_connection():
    """
    Validates database configuration and connectivity on startup.
    Provides clear, sanitized diagnostic errors if connection fails.
    """
    refresh_engine_if_needed()
    is_vercel = settings.is_production_or_vercel()
    db_url = settings.get_database_url()

    if is_vercel:
        if not db_url:
            raise RuntimeError(
                "CRITICAL STARTUP ERROR: The DATABASE_URL environment variable is missing on Vercel. "
                "Please configure a hosted PostgreSQL database connection string "
                "(e.g. postgresql://user:password@host:port/dbname) in your Vercel project environment variables."
            )
        if db_url.startswith("sqlite"):
            raise RuntimeError(
                "CRITICAL STARTUP ERROR: SQLite cannot be used as the production database on Vercel. "
                "Vercel serverless functions operate in a read-only filesystem. "
                "Please configure a hosted PostgreSQL database (such as Neon, Supabase, Render, or Railway) "
                "via the DATABASE_URL environment variable."
            )

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Database connection verified successfully (dialect: {engine.dialect.name}).")
    except Exception as e:
        safe_url = engine.url.render_as_string(hide_password=True)
        err_msg = (
            f"CRITICAL STARTUP ERROR: Failed to connect to database at '{safe_url}'. "
            f"Error details: {e}. "
            "Please check that your DATABASE_URL credentials, host, and SSL settings are correct."
        )
        logger.critical(err_msg)
        raise RuntimeError(err_msg) from e

def init_fts5_tables():
    """Initializes SQLite FTS5 table only if running on SQLite."""
    if engine.dialect.name != "sqlite":
        return
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS rag_documents_fts USING fts5(
                doc_id UNINDEXED,
                title,
                crop,
                topic,
                region,
                language,
                source_name,
                source_url UNINDEXED,
                publication_date UNINDEXED,
                summary,
                content,
                tokenize = 'porter unicode61'
            );
        """)
        raw_conn.commit()
    finally:
        raw_conn.close()

def init_db_schema():
    """
    Safely creates all database tables (conversations, messages, farmer_profiles, feedbacks, rag_documents)
    without erasing existing data.
    """
    refresh_engine_if_needed()
    import app.models  # Ensure all SQLAlchemy models are registered
    Base.metadata.create_all(bind=engine)
    init_fts5_tables()
