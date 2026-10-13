import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app.models.rag_document import RAGDocument
from app.schemas.schemas import SourceCitation

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_base"

class RAGService:
    @staticmethod
    def ingest_document(doc_data: Dict[str, Any]) -> bool:
        """
        Ingests a single document into the database.
        - Persists to RAGDocument table (supported across PostgreSQL & SQLite).
        - If running SQLite, also syncs to SQLite FTS5 table for BM25 ranking.
        """
        doc_id = doc_data.get("id", "")
        if not doc_id:
            return False

        try:
            # 1. Store in standard SQLAlchemy table
            with SessionLocal() as db:
                doc = db.query(RAGDocument).filter(RAGDocument.id == doc_id).first()
                if not doc:
                    doc = RAGDocument(id=doc_id)
                    db.add(doc)
                doc.title = doc_data.get("title", "")
                doc.crop = doc_data.get("crop", "")
                doc.topic = doc_data.get("topic", "")
                doc.region = doc_data.get("region", "")
                doc.language = doc_data.get("language", "English")
                doc.source_name = doc_data.get("source_name", "")
                doc.source_url = doc_data.get("source_url", "")
                doc.publication_date = doc_data.get("publication_date", "")
                doc.summary = doc_data.get("summary", "")
                doc.content = doc_data.get("content", "")
                db.commit()

            # 2. If SQLite, also update SQLite FTS5 table
            if engine.dialect.name == "sqlite":
                try:
                    raw_conn = engine.raw_connection()
                    cursor = raw_conn.cursor()
                    cursor.execute("DELETE FROM rag_documents_fts WHERE doc_id = ?", (doc_id,))
                    cursor.execute("""
                        INSERT INTO rag_documents_fts (
                            doc_id, title, crop, topic, region, language,
                            source_name, source_url, publication_date, summary, content
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        doc_id,
                        doc_data.get("title", ""),
                        doc_data.get("crop", ""),
                        doc_data.get("topic", ""),
                        doc_data.get("region", ""),
                        doc_data.get("language", ""),
                        doc_data.get("source_name", ""),
                        doc_data.get("source_url", ""),
                        doc_data.get("publication_date", ""),
                        doc_data.get("summary", ""),
                        doc_data.get("content", "")
                    ))
                    raw_conn.commit()
                    raw_conn.close()
                except Exception as fts_err:
                    logger.warning(f"SQLite FTS5 sync warning for {doc_id}: {fts_err}")

            return True
        except Exception as e:
            logger.error(f"Failed to ingest document {doc_id}: {e}")
            return False

    @staticmethod
    def sync_knowledge_base() -> int:
        """Ensure all local JSON documents in data/knowledge_base are indexed."""
        if not KB_DIR.exists():
            return 0
        count = 0
        for file in sorted(KB_DIR.glob("*.json")):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if RAGService.ingest_document(data):
                        count += 1
            except Exception as e:
                logger.error(f"Error reading KB file {file}: {e}")
        return count

    @staticmethod
    def get_document_count(db_session: Optional[Session] = None) -> int:
        """Returns the total number of indexed knowledge base documents."""
        try:
            if db_session:
                count = db_session.query(RAGDocument).count()
                if count > 0:
                    return count
            with SessionLocal() as db:
                count = db.query(RAGDocument).count()
                if count > 0:
                    return count

            # Fallback for SQLite FTS5 if table count is 0
            if engine.dialect.name == "sqlite":
                raw_conn = engine.raw_connection()
                cursor = raw_conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM rag_documents_fts")
                count = cursor.fetchone()[0]
                raw_conn.close()
                return count
        except Exception as e:
            logger.warning(f"Error checking document count: {e}")
        return 0

    @staticmethod
    def search(
        query: str,
        crop: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base documents using best available strategy:
        - SQLite FTS5 BM25 ranking when running on SQLite.
        - PostgreSQL / SQLAlchemy multi-field relevance scoring when running on PostgreSQL.
        """
        # Ensure knowledge base is populated
        if RAGService.get_document_count() == 0:
            RAGService.sync_knowledge_base()

        # Stop words filter common conversational fillers
        STOP_WORDS = {
            "the", "and", "for", "with", "from", "that", "this", "what", "how", "when",
            "where", "which", "does", "give", "tell", "please", "about", "have", "been",
            "will", "some", "need", "help", "problem", "solution", "spray", "water",
            "maharashtra", "state", "farmer", "field", "farm", "district", "india",
            "काय", "करावे", "आहे", "कसे", "करा", "पाहिजे", "माहिती", "द्या", "सांगा",
            "आम्ही", "माझ्या", "माझे", "होते", "होत", "आहेत", "नाही", "होय", "पिक",
            "क्या", "करें", "है", "कैसे", "करना", "चाहिए", "जानकारी", "दें", "बताएं",
            "हम", "मेरे", "मेरा", "होता", "होती", "हैं", "नहीं", "फसल"
        }

        raw_tokens = [t.strip().lower() for t in query.replace('"', ' ').replace("'", ' ').split() if len(t.strip()) > 2]
        tokens = [t for t in raw_tokens if t not in STOP_WORDS]
        if not tokens and crop:
            tokens = [crop.lower()]
        if not tokens:
            return []

        safe_tokens = [re.sub(r'[^a-zA-Z0-9\u0900-\u097F]', '', t) for t in tokens if len(t) > 2]
        safe_tokens = [t for t in safe_tokens if t and t not in STOP_WORDS]
        if not safe_tokens:
            return []

        # 1. If SQLite, use FTS5 BM25 search
        if engine.dialect.name == "sqlite":
            return RAGService._search_sqlite_fts(safe_tokens, crop, limit)

        # 2. For PostgreSQL (and other dialects), use SQLAlchemy relevance scoring
        return RAGService._search_sqlalchemy(safe_tokens, crop, limit)

    @staticmethod
    def _search_sqlite_fts(safe_tokens: List[str], crop: Optional[str], limit: int) -> List[Dict[str, Any]]:
        results = []
        raw_conn = engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            clean_fts_query = " OR ".join(f'"{token}"*' for token in safe_tokens[:6])
            if crop:
                clean_fts_query = f'("{crop}") AND ({clean_fts_query})'

            rows = []
            try:
                cursor.execute("""
                    SELECT doc_id, title, crop, topic, region, language,
                           source_name, source_url, publication_date, summary, content,
                           bm25(rag_documents_fts) as rank
                    FROM rag_documents_fts
                    WHERE rag_documents_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?
                """, (clean_fts_query, limit))
                rows = cursor.fetchall()
            except Exception as fts_err:
                logger.warning(f"FTS match warning for query '{clean_fts_query}': {fts_err}. Using targeted LIKE search.")
                like_clauses = []
                params = []
                if crop:
                    like_clauses.append("crop LIKE ?")
                    params.append(f"%{crop}%")
                if safe_tokens:
                    token_conditions = " OR ".join(["(title LIKE ? OR summary LIKE ?)"] * len(safe_tokens[:3]))
                    for st in safe_tokens[:3]:
                        params.extend([f"%{st}%", f"%{st}%"])
                    like_clauses.append(f"({token_conditions})")

                if like_clauses:
                    where_sql = " AND ".join(like_clauses)
                    params.append(limit)
                    cursor.execute(f"""
                        SELECT doc_id, title, crop, topic, region, language,
                               source_name, source_url, publication_date, summary, content, 0 as rank
                        FROM rag_documents_fts
                        WHERE {where_sql}
                        LIMIT ?
                    """, tuple(params))
                    rows = cursor.fetchall()

            for row in rows:
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "crop": row[2],
                    "topic": row[3],
                    "region": row[4],
                    "language": row[5],
                    "source_name": row[6],
                    "source_url": row[7],
                    "publication_date": row[8],
                    "summary": row[9],
                    "content": row[10],
                    "score": row[11]
                })
        except Exception as e:
            logger.error(f"Error querying SQLite RAG index: {e}")
        finally:
            raw_conn.close()

        return results

    @staticmethod
    def _search_sqlalchemy(safe_tokens: List[str], crop: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """PostgreSQL & generic SQL search with agronomic scoring."""
        results = []
        try:
            with SessionLocal() as db:
                all_docs = db.query(RAGDocument).all()
                scored_docs = []

                crop_lower = crop.lower() if crop else None

                for doc in all_docs:
                    score = 0
                    doc_crop = (doc.crop or "").lower()
                    doc_title = (doc.title or "").lower()
                    doc_summary = (doc.summary or "").lower()
                    doc_content = (doc.content or "").lower()
                    doc_topic = (doc.topic or "").lower()

                    # Crop match weight
                    if crop_lower and (crop_lower in doc_crop or crop_lower in doc_title):
                        score += 20

                    # Token matches
                    matched_tokens = 0
                    for token in safe_tokens[:6]:
                        t = token.lower()
                        if t in doc_title:
                            score += 8
                            matched_tokens += 1
                        if t in doc_summary:
                            score += 5
                            matched_tokens += 1
                        if t in doc_topic:
                            score += 4
                            matched_tokens += 1
                        if t in doc_content:
                            score += 2
                            matched_tokens += 1

                    if matched_tokens > 0 or (crop_lower and crop_lower in doc_crop):
                        scored_docs.append((score, doc))

                # Sort by highest score first
                scored_docs.sort(key=lambda x: x[0], reverse=True)

                for score, doc in scored_docs[:limit]:
                    results.append({
                        "id": doc.id,
                        "title": doc.title,
                        "crop": doc.crop,
                        "topic": doc.topic,
                        "region": doc.region,
                        "language": doc.language,
                        "source_name": doc.source_name,
                        "source_url": doc.source_url,
                        "publication_date": doc.publication_date,
                        "summary": doc.summary,
                        "content": doc.content,
                        "score": score
                    })
        except Exception as e:
            logger.error(f"Error querying PostgreSQL RAG documents: {e}")

        return results

    @staticmethod
    def format_citations(rag_docs: List[Dict[str, Any]]) -> List[SourceCitation]:
        citations = []
        for doc in rag_docs:
            citations.append(SourceCitation(
                title=doc.get("title", ""),
                source_name=doc.get("source_name", "Official Agricultural Advisory"),
                source_url=doc.get("source_url"),
                publication_date=doc.get("publication_date"),
                relevance_summary=doc.get("summary")
            ))
        return citations
