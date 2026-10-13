import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

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

# Include API Routers
app.include_router(chat_router)
app.include_router(crop_analysis_router)
app.include_router(weather_router)
app.include_router(market_prices_router)
app.include_router(schemes_router)
app.include_router(feedback_router)
app.include_router(profile_router)
app.include_router(health_router)

# Mount static assets
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

ROOT_HTML = Path(__file__).resolve().parent.parent / "Chatbot.html"

@app.get("/", include_in_schema=False)
async def serve_index():
    if ROOT_HTML.exists():
        return FileResponse(str(ROOT_HTML))
    return JSONResponse({"message": "KrushiMitra AI API is online. UI file Chatbot.html not found."})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again or check server logs."}
    )
