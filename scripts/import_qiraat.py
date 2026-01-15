#!/usr/bin/env python3
"""
Import scraped Qiraat data into the database
"""

import sqlite3
import json
import os
import glob
from pathlib import Path

# Map reader names to their IDs in the database
QURRA_NAME_MAP = {
    'نافع': 1,
    'ابن كثير': 2,
    'أبو عمرو': 3,
    'ابن عامر': 4,
    'عاصم': 5,
    'حمزة': 6,
    'الكسائي': 7,
    'أبو جعفر': 8,
    'يعقوب': 9,
    'خلف العاشر': 10,
}

# Map ruwat names to their IDs
RUWAT_NAME_MAP = {
    'قالون': 1,
    'ورش': 2,
    'البزي': 3,
    'قنبل': 4,
    'الدوري': 5,  # Note: appears for both أبو عمرو and الكسائي
    'السوسي': 6,
    'هشام': 7,
    'ابن ذكوان': 8,
    'شعبة': 9,
    'حفص': 10,
    'خلف': 11,
    'خلاد': 12,
    'أبو الحارث': 13,
    'ابن وردان': 15,
    'ابن جماز': 16,
    'رويس': 17,
    'روح': 18,
    'إسحاق': 19,
    'إدريس': 20,
}


def get_verse_id(cursor, surah: int, ayah: int) -> int:
    """Get verse ID from database"""
    cursor.execute(
        "SELECT id FROM verses WHERE surah_id = ? AND ayah_number = ?",
        (surah, ayah)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def get_qari_id(reader_name: str) -> int:
    """Map reader name to qari ID"""
    # Try exact match first
    if reader_name in QURRA_NAME_MAP:
        return QURRA_NAME_MAP[reader_name]

    # Try partial match
    for name, qid in QURRA_NAME_MAP.items():
        if name in reader_name or reader_name in name:
            return qid

    return None


def get_rawi_id(reader_name: str) -> int:
    """Map reader name to rawi ID if it's a transmitter"""
    if reader_name in RUWAT_NAME_MAP:
        return RUWAT_NAME_MAP[reader_name]

    # Try partial match
    for name, rid in RUWAT_NAME_MAP.items():
        if name in reader_name:
            return rid

    return None


def import_qiraat_data(db_path: str, data_dir: str):
    """Import all scraped qiraat data into the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find all surah JSON files
    json_files = sorted(glob.glob(os.path.join(data_dir, "surah_*.json")))

    total_variants = 0
    total_readings = 0

    print(f"Found {len(json_files)} surah files to import")

    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        surah_num = data.get('surah', 0)
        variants = data.get('variants', [])

        print(f"  Importing Surah {surah_num}: {len(variants)} variants")

        for variant in variants:
            verse_id = get_verse_id(cursor, variant['surah'], variant['ayah'])
            if not verse_id:
                print(f"    Warning: Verse {variant['surah']}:{variant['ayah']} not found in database")
                continue

            # Insert variant
            cursor.execute("""
                INSERT INTO qiraat_variants (verse_id, word_text, word_position, variant_type)
                VALUES (?, ?, ?, ?)
            """, (
                verse_id,
                variant.get('word', ''),
                variant.get('word_position'),
                variant.get('variant_type', 'فرش')
            ))

            variant_id = cursor.lastrowid
            total_variants += 1

            # Insert readings
            readings = variant.get('readings', {})
            for reader_name, reading_text in readings.items():
                if reader_name == 'باقي الرواة':
                    # Skip "rest of readers" for now, can be handled separately
                    continue

                qari_id = get_qari_id(reader_name)
                rawi_id = get_rawi_id(reader_name)

                if qari_id or rawi_id:
                    cursor.execute("""
                        INSERT INTO qiraat_readings (variant_id, qari_id, rawi_id, reading_text)
                        VALUES (?, ?, ?, ?)
                    """, (
                        variant_id,
                        qari_id or (QURRA_NAME_MAP.get('حفص', 5)),  # Default to Asim if unknown
                        rawi_id,
                        reading_text
                    ))
                    total_readings += 1

    conn.commit()
    conn.close()

    print(f"\nImport complete:")
    print(f"  Total variants imported: {total_variants}")
    print(f"  Total readings imported: {total_readings}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import Qiraat data into database")
    parser.add_argument("--db", default="db/uloom_quran.db", help="Database path")
    parser.add_argument("--data", default="data/processed/qiraat", help="Data directory")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database not found at {args.db}")
        return

    if not os.path.exists(args.data):
        print(f"Error: Data directory not found at {args.data}")
        return

    import_qiraat_data(args.db, args.data)


if __name__ == "__main__":
    main()
