import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.config import settings
from app.database import check_database_connection, init_db_schema
from app.services.rag_service import RAGService
from app.api.chat import router as chat_router
from app.api.crop_analysis import router as crop_analysis_router
from app.api.weather import router as weather_router
from app.api.market_prices import router as market_prices_router
from app.api.schemes import router as schemes_router
from app.api.feedback import router as feedback_router
from app.api.profile import router as profile_router
from app.api.health import router as health_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class VercelPathRewriteMiddleware:
    """
    ASGI middleware ensuring reliable request routing when running behind Vercel serverless rewrites.
    When vercel.json rewrites traffic to /main.py, Vercel sets ASGI scope['path'] to '/main.py'
    while passing the original request path in proxy headers (x-matched-path, x-forwarded-uri, etc.).
    This middleware restores the original requested path into scope['path'] so that FastAPI's router
    matches the proper endpoints (/api/..., /static/..., /).
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/main.py" or path.startswith("/main.py/"):
                headers = dict(scope.get("headers", []))
                matched = (
                    headers.get(b"x-matched-path", b"").decode("latin-1")
                    or headers.get(b"x-forwarded-uri", b"").decode("latin-1")
                    or headers.get(b"x-original-url", b"").decode("latin-1")
                    or headers.get(b"x-rewrite-url", b"").decode("latin-1")
                )
                if matched and matched != "/main.py":
                    clean = matched.split("?")[0]
                    scope["path"] = clean
                    scope["raw_path"] = clean.encode("latin-1")
                else:
                    scope["path"] = "/"
                    scope["raw_path"] = b"/"
        await self.app(scope, receive, send)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing KrushiMitra AI database and knowledge base...")
    try:
        check_database_connection()
        init_db_schema()
        indexed = RAGService.sync_knowledge_base()
        logger.info(f"KrushiMitra AI initialized: {indexed} RAG documents ready.")
    except Exception as e:
        logger.critical(f"Startup initialization error: {e}")
        if settings.is_production_or_vercel():
            raise
    yield
    logger.info("KrushiMitra AI shutting down.")

app = FastAPI(
    title=settings.APP_NAME,
    description="KrushiMitra AI — Advanced AI-Powered Multilingual Farmer Assistant & Agricultural Knowledge Engine",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vercel serverless request path normalization middleware
app.add_middleware(VercelPathRewriteMiddleware)

# Include API Routers
app.include_router(chat_router)
app.include_router(crop_analysis_router)
app.include_router(weather_router)
app.include_router(market_prices_router)
app.include_router(schemes_router)
app.include_router(feedback_router)
app.include_router(profile_router)
app.include_router(health_router)

def get_static_dir() -> Path | None:
    """Locate static directory reliably based on source location."""
    candidates = [
        Path(__file__).resolve().parent.parent / "static",
        Path(__file__).resolve().parent / "static",
        Path.cwd() / "static",
    ]
    for p in candidates:
        if p.is_dir():
            return p
    return None

# Mount static assets
STATIC_DIR = get_static_dir()
if STATIC_DIR and STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_cached_html_content: str | None = None

def get_chatbot_html_path() -> Path | None:
    """
    Locate the chatbot HTML file reliably using source-relative paths,
    avoiding reliance on runtime current working directory.
    """
    candidates = [
        Path(__file__).resolve().parent.parent / "Chatbot.html",
        Path(__file__).resolve().parent / "Chatbot.html",
        Path(__file__).resolve().parent.parent / "Chatbot(1).html",
        Path(__file__).resolve().parent / "Chatbot(1).html",
        Path.cwd() / "Chatbot.html",
        Path.cwd() / "Chatbot(1).html",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None

def get_chatbot_html_content() -> str | None:
    global _cached_html_content
    if _cached_html_content is not None:
        return _cached_html_content
    html_path = get_chatbot_html_path()
    if html_path and html_path.is_file():
        try:
            _cached_html_content = html_path.read_text(encoding="utf-8")
            return _cached_html_content
        except Exception as e:
            logger.error(f"Error caching chatbot HTML file {html_path}: {e}")
            return None
    return None

@app.get("/", include_in_schema=False)
@app.get("/main.py", include_in_schema=False)
async def serve_index():
    content = get_chatbot_html_content()
    if content:
        return HTMLResponse(content=content, media_type="text/html")
    html_path = get_chatbot_html_path()
    if html_path and html_path.is_file():
        return FileResponse(str(html_path), media_type="text/html")
    return JSONResponse(
        status_code=404,
        content={"detail": "KrushiMitra AI chatbot HTML interface not found."}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again or check server logs."}
    )
