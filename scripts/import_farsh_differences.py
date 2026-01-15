#!/usr/bin/env python3
"""
Import Farsh Differences into the uloom_quran database
Imports data from farsh_differences.json into qiraat_variants and qiraat_readings tables
"""

import sqlite3
import json
import os
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_FILE = BASE_DIR / "data" / "processed" / "farsh_differences.json"
DB_PATH = BASE_DIR / "db" / "uloom_quran.db"


# Mapping of reading names to qari IDs
QARI_MAPPING = {
    'hafs': 5,           # Asim (Hafs is his rawi)
    'warsh': 1,          # Nafi (Warsh is his rawi)
    'qalun': 1,          # Nafi (Qalun is his rawi)
    'ibn_kathir': 2,
    'qunbul': 2,         # Ibn Kathir
    'abu_amr': 3,
    'ibn_amir': 4,
    'shubah': 5,         # Asim (Shubah is his rawi)
    'hamza': 6,
    'khallad': 6,        # Hamza
    'khalaf': 6,         # Hamza (as rawi, but also separate qari as 10th)
    'al_kisai': 7,
    'abu_jafar': 8,
    'yaqub': 9,
    'khalaf_al_ashir': 10,
    'ishaq': 10,         # Khalaf Al-Ashir
    'idris': 10,         # Khalaf Al-Ashir
}

# Mapping of rawi names to rawi IDs (from the ruwat table)
RAWI_MAPPING = {
    'hafs': 12,          # حفص
    'warsh': 2,          # ورش
    'qalun': 1,          # قالون
    'shubah': 11,        # شعبة
    'khallad': 14,       # خلاد
    'khalaf': 13,        # خلف (as Hamza's rawi)
    'qunbul': 4,         # قنبل
    'ishaq': 19,         # إسحاق
    'idris': 20,         # إدريس
    'ruways': 17,        # رويس
    'rawh': 18,          # روح
}


def get_verse_id(cursor, surah_id, verse_number):
    """Get verse ID from surah and verse number"""
    cursor.execute(
        "SELECT id FROM verses WHERE surah_id = ? AND ayah_number = ?",
        (surah_id, verse_number)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def import_farsh_differences():
    """Import farsh differences from JSON file into database"""

    if not DATA_FILE.exists():
        logger.error(f"Data file not found: {DATA_FILE}")
        return False

    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        return False

    # Load JSON data
    logger.info(f"Loading data from {DATA_FILE}")
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    differences = data.get('differences', [])
    logger.info(f"Found {len(differences)} farsh differences to import")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    # Track statistics
    variants_added = 0
    readings_added = 0
    errors = 0

    for diff in differences:
        try:
            surah_id = diff['surah_id']
            verse_number = diff['verse_number']
            word = diff['word']
            readings = diff.get('readings', {})
            explanation = diff.get('explanation', '')
            explanation_ar = diff.get('explanation_ar', '')

            # Get verse ID
            verse_id = get_verse_id(cursor, surah_id, verse_number)

            if not verse_id:
                logger.warning(f"Verse not found: {surah_id}:{verse_number}")
                errors += 1
                continue

            # Check if variant already exists
            cursor.execute("""
                SELECT id FROM qiraat_variants
                WHERE verse_id = ? AND word_text = ? AND variant_type = 'فرش'
            """, (verse_id, word))
            existing = cursor.fetchone()

            if existing:
                variant_id = existing[0]
            else:
                # Insert into qiraat_variants
                cursor.execute("""
                    INSERT INTO qiraat_variants
                    (verse_id, word_text, variant_type, category)
                    VALUES (?, ?, 'فرش', ?)
                """, (verse_id, word, explanation_ar or explanation))
                variant_id = cursor.lastrowid
                variants_added += 1

            # Insert readings for each qari
            for reader_key, reading_text in readings.items():
                reader_key_lower = reader_key.lower().replace(' ', '_').replace("'", '')

                # Get qari ID
                qari_id = QARI_MAPPING.get(reader_key_lower)
                if not qari_id:
                    # Try to match by Arabic name
                    continue

                # Get rawi ID if applicable
                rawi_id = RAWI_MAPPING.get(reader_key_lower)

                # Check if this reading already exists
                cursor.execute("""
                    SELECT id FROM qiraat_readings
                    WHERE variant_id = ? AND qari_id = ?
                """, (variant_id, qari_id))

                if cursor.fetchone():
                    continue

                # Determine if this is default Hafs reading
                is_default = 1 if reader_key_lower == 'hafs' else 0

                # Insert reading
                cursor.execute("""
                    INSERT INTO qiraat_readings
                    (variant_id, qari_id, rawi_id, reading_text, is_default, phonetic_description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    variant_id,
                    qari_id,
                    rawi_id,
                    reading_text,
                    is_default,
                    explanation_ar if reader_key_lower == 'hafs' else None
                ))
                readings_added += 1

            # Commit every 50 variants
            if variants_added % 50 == 0:
                conn.commit()
                logger.info(f"Progress: {variants_added} variants, {readings_added} readings")

        except Exception as e:
            logger.error(f"Error processing difference {diff.get('id', 'unknown')}: {e}")
            errors += 1

    # Final commit
    conn.commit()

    # Also add semantic impact for differences with meaning changes
    logger.info("Adding semantic impact entries...")
    semantic_count = 0

    for diff in differences:
        if diff.get('meaning_difference'):
            verse_id = get_verse_id(cursor, diff['surah_id'], diff['verse_number'])
            if not verse_id:
                continue

            # Get variant ID
            cursor.execute("""
                SELECT id FROM qiraat_variants
                WHERE verse_id = ? AND word_text = ? AND variant_type = 'فرش'
            """, (verse_id, diff['word']))
            variant_row = cursor.fetchone()

            if variant_row:
                variant_id = variant_row[0]
                # Check if semantic impact already exists
                cursor.execute("""
                    SELECT id FROM qiraat_semantic_impact WHERE variant_id = ?
                """, (variant_id,))

                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO qiraat_semantic_impact
                        (variant_id, has_meaning_difference, meaning_explanation)
                        VALUES (?, 1, ?)
                    """, (variant_id, diff['meaning_difference']))
                    semantic_count += 1

    conn.commit()
    conn.close()

    # Report results
    logger.info("\n=== Import Complete ===")
    logger.info(f"Variants added: {variants_added}")
    logger.info(f"Readings added: {readings_added}")
    logger.info(f"Semantic impacts added: {semantic_count}")
    logger.info(f"Errors: {errors}")

    return True


def verify_import():
    """Verify the import by showing statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Count farsh variants
    cursor.execute("SELECT COUNT(*) FROM qiraat_variants WHERE variant_type = 'فرش'")
    variant_count = cursor.fetchone()[0]

    # Count readings
    cursor.execute("""
        SELECT COUNT(*) FROM qiraat_readings qr
        JOIN qiraat_variants qv ON qr.variant_id = qv.id
        WHERE qv.variant_type = 'فرش'
    """)
    reading_count = cursor.fetchone()[0]

    # Show sample data
    cursor.execute("""
        SELECT v.verse_key, qv.word_text, q.name_arabic, qr.reading_text
        FROM qiraat_variants qv
        JOIN verses v ON qv.verse_id = v.id
        JOIN qiraat_readings qr ON qr.variant_id = qv.id
        JOIN qurra q ON qr.qari_id = q.id
        WHERE qv.variant_type = 'فرش'
        LIMIT 10
    """)

    print("\n=== Verification Results ===")
    print(f"Total Farsh Variants: {variant_count}")
    print(f"Total Readings: {reading_count}")
    print("\nSample Data:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} - {row[2]}: {row[3][:50]}...")

    conn.close()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Import Farsh Differences into database")
    parser.add_argument("--verify", action="store_true", help="Only verify existing data")

    args = parser.parse_args()

    if args.verify:
        verify_import()
    else:
        success = import_farsh_differences()
        if success:
            verify_import()


if __name__ == "__main__":
    main()
