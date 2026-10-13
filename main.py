import sys
from pathlib import Path

# Ensure project root is in sys.path so 'app' package resolves cleanly in any serverless runtime
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app

__all__ = ["app"]