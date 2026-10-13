import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# SQLite connection args for multi-threaded FastAPI
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_fts5_tables():
    """Initializes SQLite FTS5 table for RAG documents full-text search."""
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
