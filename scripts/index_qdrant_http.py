#!/usr/bin/env python3
"""
Index Quran Data into Qdrant Vector Database using HTTP API directly
"""

import sys
import os
import sqlite3
import logging
import time
import httpx
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai.services.embedding_service import get_embedding_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "uloom_quran.db")
VECTOR_SIZE = 1536  # text-embedding-ada-002 dimensions

# Collection names
COLLECTIONS = {
    "verses": "quran_verses",
    "tafsir": "tafsir_texts",
    "qiraat": "qiraat_differences",
    "asbab": "asbab_nuzul"
}


def qdrant_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make a request to Qdrant REST API."""
    url = f"{QDRANT_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}

    with httpx.Client(timeout=60.0) as client:
        if method == "GET":
            resp = client.get(url, headers=headers)
        elif method == "PUT":
            resp = client.put(url, headers=headers, json=data)
        elif method == "POST":
            resp = client.post(url, headers=headers, json=data)
        elif method == "DELETE":
            resp = client.delete(url, headers=headers)

        if resp.status_code >= 400:
            logger.error(f"Qdrant error: {resp.status_code} - {resp.text}")
            return None
        return resp.json()


def create_collection(name: str):
    """Create a Qdrant collection if it doesn't exist."""
    # Check if exists
    resp = qdrant_request("GET", f"/collections/{name}")
    if resp and resp.get("result"):
        logger.info(f"Collection {name} already exists")
        return True

    # Create collection
    data = {
        "vectors": {
            "size": VECTOR_SIZE,
            "distance": "Cosine"
        }
    }
    resp = qdrant_request("PUT", f"/collections/{name}", data)
    if resp:
        logger.info(f"Created collection: {name}")
        return True
    return False


def upsert_points(collection: str, points: list):
    """Upsert points to a collection."""
    data = {"points": points}
    resp = qdrant_request("PUT", f"/collections/{collection}/points", data)
    return resp is not None


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def index_verses(batch_size: int = 50):
    """Index all Quran verses into Qdrant."""
    logger.info("Starting verse indexing...")

    embedding_service = get_embedding_service()
    collection = COLLECTIONS["verses"]

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) FROM verses")
    total = cursor.fetchone()[0]
    logger.info(f"Total verses to index: {total}")

    # Fetch verses with surah info
    cursor.execute("""
        SELECT v.id, v.surah_id, v.ayah_number, v.verse_key, v.text_uthmani,
               s.name_arabic as surah_name_ar, s.name_english as surah_name_en
        FROM verses v
        JOIN surahs s ON v.surah_id = s.id
        ORDER BY v.surah_id, v.ayah_number
    """)

    verses = cursor.fetchall()
    indexed = 0

    for i in range(0, len(verses), batch_size):
        batch = verses[i:i + batch_size]
        texts = [row[4] for row in batch]  # text_uthmani

        try:
            embeddings = embedding_service.get_embeddings_batch(texts)

            points = []
            for verse, embedding in zip(batch, embeddings):
                if embedding is None:
                    continue

                point = {
                    "id": verse[0],
                    "vector": embedding,
                    "payload": {
                        "surah_id": verse[1],
                        "ayah_number": verse[2],
                        "verse_key": verse[3],
                        "text_ar": verse[4],
                        "surah_name_ar": verse[5],
                        "surah_name_en": verse[6],
                        "type": "verse"
                    }
                }
                points.append(point)

            if points:
                if upsert_points(collection, points):
                    indexed += len(points)

            logger.info(f"Indexed verses: {indexed}/{total}")
            time.sleep(0.3)

        except Exception as e:
            logger.error(f"Error indexing verse batch {i}: {e}")
            continue

    conn.close()
    logger.info(f"Verse indexing complete. Total indexed: {indexed}")
    return indexed


def index_tafsir(batch_size: int = 20):
    """Index tafsir entries into Qdrant."""
    logger.info("Starting tafsir indexing...")

    embedding_service = get_embedding_service()
    collection = COLLECTIONS["tafsir"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tafsir_entries")
    total = cursor.fetchone()[0]
    logger.info(f"Total tafsir entries to index: {total}")

    cursor.execute("""
        SELECT te.id, te.tafsir_id, te.verse_id, te.text_arabic,
               tb.name_arabic as tafsir_name, tb.short_name,
               v.verse_key, v.surah_id, v.ayah_number
        FROM tafsir_entries te
        JOIN tafsir_books tb ON te.tafsir_id = tb.id
        JOIN verses v ON te.verse_id = v.id
        ORDER BY te.id
    """)

    tafsirs = cursor.fetchall()
    indexed = 0

    for i in range(0, len(tafsirs), batch_size):
        batch = tafsirs[i:i + batch_size]
        texts = [f"{row[4]}: {row[3][:2000]}" for row in batch]

        try:
            embeddings = embedding_service.get_embeddings_batch(texts)

            points = []
            for tafsir, embedding in zip(batch, embeddings):
                if embedding is None:
                    continue

                point = {
                    "id": tafsir[0],
                    "vector": embedding,
                    "payload": {
                        "tafsir_id": tafsir[1],
                        "verse_id": tafsir[2],
                        "text": tafsir[3][:5000],
                        "tafsir_name": tafsir[4],
                        "short_name": tafsir[5],
                        "verse_key": tafsir[6],
                        "surah_id": tafsir[7],
                        "ayah_number": tafsir[8],
                        "type": "tafsir"
                    }
                }
                points.append(point)

            if points:
                if upsert_points(collection, points):
                    indexed += len(points)

            logger.info(f"Indexed tafsir: {indexed}/{total}")
            time.sleep(0.3)

        except Exception as e:
            logger.error(f"Error indexing tafsir batch {i}: {e}")
            continue

    conn.close()
    logger.info(f"Tafsir indexing complete. Total indexed: {indexed}")
    return indexed


def index_asbab(batch_size: int = 20):
    """Index asbab al-nuzul into Qdrant."""
    logger.info("Starting asbab al-nuzul indexing...")

    embedding_service = get_embedding_service()
    collection = COLLECTIONS["asbab"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.id, a.verse_id, a.sabab_text, a.source_id,
               v.verse_key, v.surah_id, v.ayah_number
        FROM asbab_nuzul a
        JOIN verses v ON a.verse_id = v.id
        ORDER BY a.id
    """)

    asbab = cursor.fetchall()
    total = len(asbab)
    logger.info(f"Total asbab entries to index: {total}")

    indexed = 0

    for i in range(0, len(asbab), batch_size):
        batch = asbab[i:i + batch_size]
        texts = [row[2][:3000] for row in batch]

        try:
            embeddings = embedding_service.get_embeddings_batch(texts)

            points = []
            for entry, embedding in zip(batch, embeddings):
                if embedding is None:
                    continue

                point = {
                    "id": entry[0],
                    "vector": embedding,
                    "payload": {
                        "verse_id": entry[1],
                        "text": entry[2],
                        "source": entry[3],
                        "verse_key": entry[4],
                        "surah_id": entry[5],
                        "ayah_number": entry[6],
                        "type": "asbab"
                    }
                }
                points.append(point)

            if points:
                if upsert_points(collection, points):
                    indexed += len(points)

            logger.info(f"Indexed asbab: {indexed}/{total}")
            time.sleep(0.3)

        except Exception as e:
            logger.error(f"Error indexing asbab batch {i}: {e}")
            continue

    conn.close()
    logger.info(f"Asbab indexing complete. Total indexed: {indexed}")
    return indexed


def main():
    """Main indexing function."""
    logger.info("=" * 60)
    logger.info("Starting Qdrant indexing (HTTP mode)")
    logger.info(f"Qdrant URL: {QDRANT_URL}")
    logger.info("=" * 60)

    # Test connection
    resp = qdrant_request("GET", "/collections")
    if not resp:
        logger.error("Cannot connect to Qdrant!")
        return
    logger.info(f"Connected to Qdrant. Existing collections: {resp}")

    # Create collections
    for name in COLLECTIONS.values():
        create_collection(name)

    results = {}

    # Index verses first (most important)
    try:
        results["verses"] = index_verses()
    except Exception as e:
        logger.error(f"Failed to index verses: {e}")
        results["verses"] = 0

    # Index asbab (smaller, faster)
    try:
        results["asbab"] = index_asbab()
    except Exception as e:
        logger.error(f"Failed to index asbab: {e}")
        results["asbab"] = 0

    # Index tafsir (largest, slowest)
    try:
        results["tafsir"] = index_tafsir()
    except Exception as e:
        logger.error(f"Failed to index tafsir: {e}")
        results["tafsir"] = 0

    logger.info("=" * 60)
    logger.info("Indexing Summary:")
    for name, count in results.items():
        logger.info(f"  {name}: {count}")
    logger.info(f"  Total: {sum(results.values())}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
