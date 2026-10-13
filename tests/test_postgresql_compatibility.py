import os
import pytest
from unittest.mock import patch
from app.config import Settings
from app.database import Base, check_database_connection, engine
from app.models.conversation import Conversation, Message, FarmerProfile, Feedback, RAGDocument
from app.services.rag_service import RAGService

def test_database_url_normalization_postgres_to_postgresql_psycopg2():
    """Verify postgres:// URLs are automatically transformed to postgresql+psycopg2:// for SQLAlchemy."""
    s = Settings(DATABASE_URL="postgres://user:secret123@neon.tech:5432/neondb")
    assert s.DATABASE_URL == "postgresql+psycopg2://user:secret123@neon.tech:5432/neondb"
    assert s.get_database_url() == "postgresql+psycopg2://user:secret123@neon.tech:5432/neondb"

def test_database_url_normalization_standard_postgresql():
    """Verify postgresql:// URLs are normalized to postgresql+psycopg2:// matching psycopg2-binary."""
    url = "postgresql://user:secret123@supabase.co:5432/postgres"
    s = Settings(DATABASE_URL=url)
    assert s.get_database_url() == "postgresql+psycopg2://user:secret123@supabase.co:5432/postgres"

def test_database_url_normalization_psycopg_to_psycopg2():
    """Verify postgresql+psycopg:// URLs are corrected to postgresql+psycopg2://."""
    url = "postgresql+psycopg://user:secret123@supabase.co:5432/postgres"
    s = Settings(DATABASE_URL=url)
    assert s.get_database_url() == "postgresql+psycopg2://user:secret123@supabase.co:5432/postgres"

def test_engine_selects_psycopg2_driver():
    """Verify engine creation uses psycopg2 and does not attempt to import psycopg3."""
    from sqlalchemy import create_engine
    s = Settings(DATABASE_URL="postgresql://user:secret123@localhost/dbname")
    eng = create_engine(s.get_database_url())
    assert eng.dialect.driver == "psycopg2"
    assert "psycopg2" in eng.dialect.__module__

def test_root_main_imports_cleanly_without_database_url():
    """Verify root main.py imports cleanly without raising errors at module import time."""
    with patch.dict(os.environ, {"VERCEL": "1"}):
        with patch.object(Settings, "get_database_url", return_value=""):
            import main
            assert hasattr(main, "app")
            assert main.app is not None

def test_missing_database_url_on_vercel_raises_clear_startup_error():
    """Verify missing DATABASE_URL on Vercel is caught during startup verification."""
    with patch.dict(os.environ, {"VERCEL": "1"}):
        with patch.object(Settings, "get_database_url", return_value=""):
            with pytest.raises(RuntimeError) as exc_info:
                check_database_connection()
            assert "DATABASE_URL environment variable is missing on Vercel" in str(exc_info.value)

def test_sqlite_rejected_in_production_vercel():
    """Verify SQLite database URL raises a clear error on Vercel / production."""
    with patch.dict(os.environ, {"VERCEL": "1"}):
        with patch.object(Settings, "get_database_url", return_value="sqlite:///./data/krushimitra.db"):
            with pytest.raises(RuntimeError) as exc_info:
                check_database_connection()
            assert "SQLite cannot be used as the production database on Vercel" in str(exc_info.value)
            assert "read-only filesystem" in str(exc_info.value)

def test_all_models_registered_in_metadata():
    """Verify all 5 application models are present in SQLAlchemy Base.metadata."""
    tables = Base.metadata.tables.keys()
    assert "conversations" in tables
    assert "messages" in tables
    assert "farmer_profiles" in tables
    assert "feedbacks" in tables
    assert "rag_documents" in tables

def test_rag_sqlalchemy_search():
    """Verify database-agnostic search on RAGDocument works with scoring."""
    RAGService.sync_knowledge_base()
    results = RAGService._search_sqlalchemy(safe_tokens=["bollworm", "cotton"], crop="Cotton", limit=2)
    assert len(results) > 0
    top = results[0]
    assert "id" in top
    assert "title" in top
    assert "crop" in top
    assert "content" in top
    assert "Cotton" in top["crop"] or "Cotton" in top["title"]
    assert top["score"] > 0

def test_vercel_configuration():
    """Verify vercel.json uses modern rewrites without deprecated builds array."""
    import json
    from pathlib import Path
    vercel_path = Path(__file__).resolve().parent.parent / "vercel.json"
    assert vercel_path.exists()
    with open(vercel_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "builds" not in data, "Legacy 'builds' causes Vercel settings warning"
    assert "rewrites" in data
    assert any(r.get("destination") == "/main.py" for r in data["rewrites"])

def test_serve_index_root_returns_html():
    """Verify GET / serves Chatbot.html with text/html content type."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "KrushiMitra" in resp.text
    assert "<!DOCTYPE html>" in resp.text

def test_serve_index_main_py_returns_html():
    """Verify GET /main.py gracefully serves Chatbot.html when Vercel rewrites to entrypoint."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/main.py")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "KrushiMitra" in resp.text

def test_vercel_proxy_header_api_rewrites():
    """Verify ASGI middleware rewrites /main.py with x-matched-path: /api/health to API route."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/main.py", headers={"x-matched-path": "/api/health"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["healthy", "degraded"]

def test_static_asset_serving():
    """Verify static directory assets (images, css, js) are served correctly."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    # Direct static path
    resp_direct = client.get("/static/tomato_sample.jpg")
    assert resp_direct.status_code == 200
    assert resp_direct.headers.get("content-type") == "image/jpeg"
    assert len(resp_direct.content) > 0

    # Rewritten static path via Vercel proxy header
    resp_rewritten = client.get("/main.py", headers={"x-matched-path": "/static/tomato_sample.jpg"})
    assert resp_rewritten.status_code == 200
    assert resp_rewritten.headers.get("content-type") == "image/jpeg"

def test_chat_post_via_vercel_rewrite_returns_200():
    """Verify POST /api/chat rewritten via Vercel __path__ parameter reaches chat handler and returns 200."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.post("/main.py?__path__=/api/chat", json={"message": "What is the recommended fertilizer for wheat?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "conversation_id" in data
    assert "message" in data
    assert len(data["message"]) > 0

def test_chat_post_invalid_payload_returns_422():
    """Verify invalid POST payload returns 422 validation error instead of 405 Method Not Allowed."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.post("/main.py?__path__=/api/chat", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data

def test_chat_post_direct_returns_200():
    """Verify direct POST /api/chat returns 200 for local dev and standard calls."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/chat", json={"message": "Namaste"})
    assert resp.status_code == 200
    assert "conversation_id" in resp.json()

def test_api_weather_via_vercel_rewrite_with_query_params():
    """Verify GET /api/weather preserves query parameters when rewritten by Vercel."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/main.py?__path__=/api/weather&district=Pune")
    assert resp.status_code == 200
    data = resp.json()
    assert "district" in data
    assert data["district"] == "Pune"


