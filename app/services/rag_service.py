import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.database import engine
from app.schemas.schemas import SourceCitation

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_base"

class RAGService:
    @staticmethod
    def ingest_document(doc_data: Dict[str, Any]) -> bool:
        """Ingest a single document into the SQLite FTS5 index."""
        raw_conn = engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            # Delete existing if doc_id exists
            cursor.execute("DELETE FROM rag_documents_fts WHERE doc_id = ?", (doc_data.get("id"),))
            cursor.execute("""
                INSERT INTO rag_documents_fts (
                    doc_id, title, crop, topic, region, language,
                    source_name, source_url, publication_date, summary, content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_data.get("id", ""),
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
            return True
        except Exception as e:
            logger.error(f"Failed to ingest document {doc_data.get('id')}: {e}")
            return False
        finally:
            raw_conn.close()

    @staticmethod
    def sync_knowledge_base():
        """Ensure all local JSON documents in data/knowledge_base are indexed."""
        if not KB_DIR.exists():
            return 0
        count = 0
        for file in KB_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if RAGService.ingest_document(data):
                        count += 1
            except Exception as e:
                logger.error(f"Error reading KB file {file}: {e}")
        return count

    @staticmethod
    def search(
        query: str,
        crop: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using SQLite FTS5 BM25 ranking.
        Sanitizes search query to prevent syntax errors with FTS5.
        """
        # Ensure knowledge base is populated
        raw_conn = engine.raw_connection()
        results = []
        try:
            cursor = raw_conn.cursor()
            # Check if index has rows
            cursor.execute("SELECT COUNT(*) FROM rag_documents_fts")
            count = cursor.fetchone()[0]
            if count == 0:
                RAGService.sync_knowledge_base()

            # Filter common conversational stop words that cause false positive citations
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

            # Clean alphanumeric / unicode tokens for FTS5
            safe_tokens = [re.sub(r'[^a-zA-Z0-9\u0900-\u097F]', '', t) for t in tokens if len(t) > 2]
            safe_tokens = [t for t in safe_tokens if t and t not in STOP_WORDS]
            if not safe_tokens:
                return []

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
                logger.warning(f"FTS match warning for query '{clean_fts_query}': {fts_err}. Attempting targeted LIKE search.")
                # Safe targeted fallback: search by crop or key token, NOT unbounded SELECT
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
            logger.error(f"Error querying RAG knowledge base: {e}")
        finally:
            raw_conn.close()

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
