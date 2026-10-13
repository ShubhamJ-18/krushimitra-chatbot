#!/usr/bin/env python3
"""
KrushiMitra AI — Application Server Runner
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"[*] Starting {settings.APP_NAME} on http://localhost:{settings.PORT}")
    print(f"[*] Interactive API Docs: http://localhost:{settings.PORT}/api/docs")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
