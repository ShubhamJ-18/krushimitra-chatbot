#!/usr/bin/env python3
"""
KrushiMitra AI — Knowledge Base Ingestion Script
Indexes verified agricultural documents (ICAR, KVKs, Agri Universities) into SQLite FTS5.
"""

import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database import engine, init_db_schema
from app.services.rag_service import RAGService

def main():
    print("=" * 65)
    print(f"[*] KrushiMitra AI - Knowledge Base Ingestion ({engine.dialect.name})")
    print("=" * 65)

    # 1. Ensure DB tables exist
    print("Checking database tables...")
    init_db_schema()

    # 2. Ingest documents
    kb_path = ROOT_DIR / "data" / "knowledge_base"
    print(f"Reading approved agricultural documents from: {kb_path}")
    
    files = list(kb_path.glob("*.json"))
    if not files:
        print("[!] No .json knowledge documents found in directory.")
        return

    count = 0
    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                doc = json.load(f)
                success = RAGService.ingest_document(doc)
                if success:
                    count += 1
                    print(f"  [+] Indexed [{doc.get('id', 'N/A')}]: {doc.get('title')}")
                    print(f"      Source: {doc.get('source_name')} | Date: {doc.get('publication_date')}")
                else:
                    print(f"  [-] Failed to index: {file.name}")
        except Exception as e:
            print(f"  [-] Error processing {file.name}: {e}")

    print("-" * 65)
    print(f"[+] Ingestion complete: {count}/{len(files)} documents indexed into RAG FTS5.")
    print("=" * 65)

if __name__ == "__main__":
    main()
