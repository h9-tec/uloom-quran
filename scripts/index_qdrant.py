#!/usr/bin/env python3
"""
Index Quran Data into Qdrant Vector Database
Generates embeddings and stores in Qdrant for semantic search
"""

import sys
import os
import sqlite3
import logging
from typing import List, Dict, Any
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai.services.embedding_service import get_embedding_service
from src.ai.services.qdrant_service import get_qdrant_service
from src.ai.config import qdrant_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "db", "uloom_quran.db"
)


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def index_verses(batch_size: int = 50):
    """Index all Quran verses into Qdrant."""
    logger.info("Starting verse indexing...")

    embedding_service = get_embedding_service()
    qdrant_service = get_qdrant_service()
    collection = qdrant_config.verses_collection

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

        # Prepare texts for embedding
        texts = [row[4] for row in batch]  # text_uthmani

        try:
            # Get embeddings
            embeddings = embedding_service.get_embeddings_batch(texts)

            # Prepare points
            points = []
            for j, (verse, embedding) in enumerate(zip(batch, embeddings)):
                if embedding is None:
                    continue

                point = {
                    "id": verse[0],  # verse id
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

            # Upsert to Qdrant
            if points:
                qdrant_service.upsert_points(collection, points)
                indexed += len(points)

            logger.info(f"Indexed verses: {indexed}/{total}")

            # Rate limiting
            time.sleep(0.5)

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
    qdrant_service = get_qdrant_service()
    collection = qdrant_config.tafsir_collection

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) FROM tafsir_entries")
    total = cursor.fetchone()[0]
    logger.info(f"Total tafsir entries to index: {total}")

    # Fetch tafsir with book info
    cursor.execute("""
        SELECT te.id, te.tafsir_id, te.verse_id, te.text,
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

        # Prepare texts (combine tafsir name with text for better context)
        texts = [f"{row[4]}: {row[3][:2000]}" for row in batch]  # tafsir_name: text

        try:
            embeddings = embedding_service.get_embeddings_batch(texts)

            points = []
            for j, (tafsir, embedding) in enumerate(zip(batch, embeddings)):
                if embedding is None:
                    continue

                point = {
                    "id": tafsir[0],
                    "vector": embedding,
                    "payload": {
                        "tafsir_id": tafsir[1],
                        "verse_id": tafsir[2],
                        "text": tafsir[3][:5000],  # Truncate for storage
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
                qdrant_service.upsert_points(collection, points)
                indexed += len(points)

            logger.info(f"Indexed tafsir: {indexed}/{total}")
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error indexing tafsir batch {i}: {e}")
            continue

    conn.close()
    logger.info(f"Tafsir indexing complete. Total indexed: {indexed}")
    return indexed


def index_qiraat(batch_size: int = 50):
    """Index qiraat differences into Qdrant."""
    logger.info("Starting qiraat indexing...")

    embedding_service = get_embedding_service()
    qdrant_service = get_qdrant_service()
    collection = qdrant_config.qiraat_collection

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get qiraat variants with differences
    cursor.execute("""
        SELECT qv.id, qv.verse_id, qv.qari_id, qv.rawi_id, qv.word_index,
               qv.hafs_word, qv.variant_word, qv.difference_type,
               v.verse_key, v.surah_id, v.ayah_number,
               q.name_arabic as qari_name
        FROM qiraat_variants qv
        JOIN verses v ON qv.verse_id = v.id
        JOIN qurra q ON qv.qari_id = q.id
        WHERE qv.hafs_word != qv.variant_word
        ORDER BY qv.id
    """)

    qiraat = cursor.fetchall()
    total = len(qiraat)
    logger.info(f"Total qiraat differences to index: {total}")

    indexed = 0

    for i in range(0, len(qiraat), batch_size):
        batch = qiraat[i:i + batch_size]

        # Create searchable text combining all relevant info
        texts = []
        for row in batch:
            text = f"قراءة {row[11]} في الآية {row[8]}: {row[5]} يقرأها {row[6]}"
            if row[7]:
                text += f" ({row[7]})"
            texts.append(text)

        try:
            embeddings = embedding_service.get_embeddings_batch(texts)

            points = []
            for j, (qiraa, embedding) in enumerate(zip(batch, embeddings)):
                if embedding is None:
                    continue

                point = {
                    "id": qiraa[0],
                    "vector": embedding,
                    "payload": {
                        "verse_id": qiraa[1],
                        "qari_id": qiraa[2],
                        "rawi_id": qiraa[3],
                        "word_index": qiraa[4],
                        "hafs_word": qiraa[5],
                        "variant_word": qiraa[6],
                        "difference_type": qiraa[7],
                        "verse_key": qiraa[8],
                        "surah_id": qiraa[9],
                        "ayah_number": qiraa[10],
                        "reader_name": qiraa[11],
                        "type": "qiraat"
                    }
                }
                points.append(point)

            if points:
                qdrant_service.upsert_points(collection, points)
                indexed += len(points)

            logger.info(f"Indexed qiraat: {indexed}/{total}")
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error indexing qiraat batch {i}: {e}")
            continue

    conn.close()
    logger.info(f"Qiraat indexing complete. Total indexed: {indexed}")
    return indexed


def index_asbab(batch_size: int = 20):
    """Index asbab al-nuzul into Qdrant."""
    logger.info("Starting asbab al-nuzul indexing...")

    embedding_service = get_embedding_service()
    qdrant_service = get_qdrant_service()
    collection = qdrant_config.asbab_collection

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get asbab entries
    cursor.execute("""
        SELECT a.id, a.verse_id, a.arabic_text, a.source,
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

        texts = [row[2][:3000] for row in batch]  # arabic_text

        try:
            embeddings = embedding_service.get_embeddings_batch(texts)

            points = []
            for j, (entry, embedding) in enumerate(zip(batch, embeddings)):
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
                qdrant_service.upsert_points(collection, points)
                indexed += len(points)

            logger.info(f"Indexed asbab: {indexed}/{total}")
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error indexing asbab batch {i}: {e}")
            continue

    conn.close()
    logger.info(f"Asbab indexing complete. Total indexed: {indexed}")
    return indexed


def initialize_and_index_all():
    """Initialize collections and index all data."""
    logger.info("=" * 60)
    logger.info("Starting full Qdrant indexing process")
    logger.info("=" * 60)

    # Initialize Qdrant service and create collections
    qdrant_service = get_qdrant_service()
    qdrant_service.initialize_collections()

    # Index all content types
    results = {
        "verses": 0,
        "tafsir": 0,
        "qiraat": 0,
        "asbab": 0
    }

    try:
        results["verses"] = index_verses()
    except Exception as e:
        logger.error(f"Failed to index verses: {e}")

    try:
        results["tafsir"] = index_tafsir()
    except Exception as e:
        logger.error(f"Failed to index tafsir: {e}")

    try:
        results["qiraat"] = index_qiraat()
    except Exception as e:
        logger.error(f"Failed to index qiraat: {e}")

    try:
        results["asbab"] = index_asbab()
    except Exception as e:
        logger.error(f"Failed to index asbab: {e}")

    logger.info("=" * 60)
    logger.info("Indexing Summary:")
    logger.info(f"  Verses indexed: {results['verses']}")
    logger.info(f"  Tafsir indexed: {results['tafsir']}")
    logger.info(f"  Qiraat indexed: {results['qiraat']}")
    logger.info(f"  Asbab indexed: {results['asbab']}")
    logger.info(f"  Total vectors: {sum(results.values())}")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Index Quran data into Qdrant")
    parser.add_argument("--type", choices=["all", "verses", "tafsir", "qiraat", "asbab"],
                        default="all", help="Type of content to index")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Batch size for embedding generation")
    args = parser.parse_args()

    if args.type == "all":
        initialize_and_index_all()
    elif args.type == "verses":
        qdrant_service = get_qdrant_service()
        qdrant_service.initialize_collections()
        index_verses(args.batch_size)
    elif args.type == "tafsir":
        qdrant_service = get_qdrant_service()
        qdrant_service.initialize_collections()
        index_tafsir(args.batch_size)
    elif args.type == "qiraat":
        qdrant_service = get_qdrant_service()
        qdrant_service.initialize_collections()
        index_qiraat(args.batch_size)
    elif args.type == "asbab":
        qdrant_service = get_qdrant_service()
        qdrant_service.initialize_collections()
        index_asbab(args.batch_size)
