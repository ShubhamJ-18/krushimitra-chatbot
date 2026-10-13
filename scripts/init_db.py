#!/usr/bin/env python3
"""
KrushiMitra AI — Database Initialization & Seeding Script
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database import engine, init_db_schema, SessionLocal
from app.models.conversation import FarmerProfile
from app.services.rag_service import RAGService

def main():
    print("=" * 60)
    print(f"[*] KrushiMitra AI - Database Initialization ({engine.dialect.name})")
    print("=" * 60)

    # 1. Create tables safely
    print(f"1. Creating database schema for {engine.dialect.name}...")
    init_db_schema()
    print("   [+] Schema verified and ready.")

    # 2. Seed default farmer profile if empty
    print("2. Seeding default farmer profile...")
    db = SessionLocal()
    try:
        profile = db.query(FarmerProfile).first()
        if not profile:
            profile = FarmerProfile(
                name="Shetkari Mitra",
                district="Pune",
                state="Maharashtra",
                farm_size_acres="3.5",
                primary_crops="Soybean, Onion, Cotton",
                irrigation_type="Drip & Well",
                preferred_language="Marathi"
            )
            db.add(profile)
            db.commit()
            print("   [+] Default farmer profile created.")
        else:
            print("   [i] Farmer profile already exists.")
    finally:
        db.close()

    # 3. Ingest knowledge base
    print("3. Indexing agricultural knowledge base documents...")
    indexed_count = RAGService.sync_knowledge_base()
    print(f"   [+] Indexed {indexed_count} verified agricultural documents.")

    print("=" * 60)
    print("[*] Initialization successfully finished!")

if __name__ == "__main__":
    main()
