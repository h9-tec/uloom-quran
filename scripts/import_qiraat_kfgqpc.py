#!/usr/bin/env python3
"""
Import القراءات العشر (Ten Qiraat) data from KFGQPC repository

This script imports 8 different qiraat readings and creates a comparison table
showing differences between the readings.
"""

import json
import sqlite3
import os
import re
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw', 'quran-data-kfgqpc')
DB_PATH = os.path.join(BASE_DIR, 'db', 'uloom_quran.db')

# Qiraat readings available in KFGQPC
QIRAAT_FILES = {
    'hafs': ('hafs/data/hafsData_v18.json', 'حفص عن عاصم', 'Hafs from Asim'),
    'warsh': ('warsh/data/warshData_v10.json', 'ورش عن نافع', 'Warsh from Nafi'),
    'qaloon': ('qaloon/data/QaloonData_v10.json', 'قالون عن نافع', 'Qaloon from Nafi'),
    'shouba': ('shouba/data/ShoubaData08.json', 'شعبة عن عاصم', 'Shuba from Asim'),
    'doori': ('doori/data/DooriData_v09.json', 'الدوري عن أبي عمرو', 'Al-Douri from Abu Amr'),
    'soosi': ('soosi/data/SoosiData09.json', 'السوسي عن أبي عمرو', 'Al-Soosi from Abu Amr'),
    'bazzi': ('bazzi/data/BazziData_v07.json', 'البزي عن ابن كثير', 'Al-Bazzi from Ibn Kathir'),
    'qumbul': ('qumbul/data/QumbulData_v07.json', 'قنبل عن ابن كثير', 'Qunbul from Ibn Kathir'),
}

def setup_database():
    """Create tables for qiraat readings"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for riwayat (narrations/readings)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riwayat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name_arabic TEXT NOT NULL,
            name_english TEXT NOT NULL,
            qari_id INTEGER,
            description TEXT,
            FOREIGN KEY (qari_id) REFERENCES qurra(id)
        )
    """)

    # Table for qiraat texts (full Quran text per reading)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_texts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            riwaya_id INTEGER NOT NULL,
            surah_id INTEGER NOT NULL,
            ayah_number INTEGER NOT NULL,
            text_uthmani TEXT NOT NULL,
            text_simple TEXT,
            juz INTEGER,
            page INTEGER,
            FOREIGN KEY (riwaya_id) REFERENCES riwayat(id),
            FOREIGN KEY (surah_id) REFERENCES surahs(id),
            UNIQUE(riwaya_id, surah_id, ayah_number)
        )
    """)

    # Table for qiraat differences (comparison between readings)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_differences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            surah_id INTEGER NOT NULL,
            ayah_number INTEGER NOT NULL,
            word_position INTEGER,
            word_text TEXT,
            difference_type TEXT,
            description TEXT,
            FOREIGN KEY (surah_id) REFERENCES surahs(id)
        )
    """)

    # Table for difference details per riwaya
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_difference_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            difference_id INTEGER NOT NULL,
            riwaya_id INTEGER NOT NULL,
            reading_text TEXT NOT NULL,
            FOREIGN KEY (difference_id) REFERENCES qiraat_differences(id),
            FOREIGN KEY (riwaya_id) REFERENCES riwayat(id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_texts_verse ON qiraat_texts(surah_id, ayah_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_diff_verse ON qiraat_differences(surah_id, ayah_number)")

    conn.commit()
    conn.close()
    print("Database tables created")


def normalize_text(text):
    """Normalize Arabic text for comparison"""
    if not text:
        return ""
    # Remove verse numbers, diacritics for comparison
    text = re.sub(r'[٠-٩0-9]+$', '', text)  # Remove verse numbers at end
    text = re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]', '', text)
    text = text.strip()
    return text


def load_qiraa_data(file_path):
    """Load qiraa JSON data"""
    full_path = os.path.join(DATA_DIR, file_path)
    if not os.path.exists(full_path):
        print(f"  File not found: {full_path}")
        return None

    with open(full_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def import_riwayat():
    """Import riwayat (narrations) metadata"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for code, (file_path, name_ar, name_en) in QIRAAT_FILES.items():
        cursor.execute("""
            INSERT OR REPLACE INTO riwayat (code, name_arabic, name_english)
            VALUES (?, ?, ?)
        """, (code, name_ar, name_en))

    conn.commit()
    conn.close()
    print(f"Imported {len(QIRAAT_FILES)} riwayat")


def import_qiraat_texts():
    """Import full Quran text for each qiraa"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_imported = 0

    for code, (file_path, name_ar, name_en) in QIRAAT_FILES.items():
        print(f"\nImporting {name_ar} ({code})...")

        # Get riwaya_id
        cursor.execute("SELECT id FROM riwayat WHERE code = ?", (code,))
        riwaya_row = cursor.fetchone()
        if not riwaya_row:
            print(f"  Riwaya not found: {code}")
            continue
        riwaya_id = riwaya_row[0]

        # Load data
        data = load_qiraa_data(file_path)
        if not data:
            continue

        # Import verses
        count = 0
        for verse in data:
            # Handle different field names between qiraat files
            surah_id = verse.get('sora') or verse.get('sura_no')
            ayah_no = verse.get('aya_no')
            text_uthmani = verse.get('aya_text', '')
            text_simple = verse.get('aya_text_emlaey', '')
            juz = verse.get('jozz')
            page = verse.get('page')

            if not surah_id or not ayah_no:
                continue

            cursor.execute("""
                INSERT OR REPLACE INTO qiraat_texts
                (riwaya_id, surah_id, ayah_number, text_uthmani, text_simple, juz, page)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (riwaya_id, surah_id, ayah_no, text_uthmani, text_simple, juz, page))
            count += 1

        print(f"  Imported {count} verses")
        total_imported += count

    conn.commit()
    conn.close()
    print(f"\nTotal verses imported: {total_imported}")


def find_differences():
    """Find differences between qiraat readings"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\nFinding differences between qiraat...")

    # Get all riwayat
    cursor.execute("SELECT id, code, name_arabic FROM riwayat")
    riwayat = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    # Clear existing differences
    cursor.execute("DELETE FROM qiraat_difference_readings")
    cursor.execute("DELETE FROM qiraat_differences")

    # Get Hafs riwaya_id as reference
    cursor.execute("SELECT id FROM riwayat WHERE code = 'hafs'")
    hafs_id = cursor.fetchone()[0]

    # For each verse, compare all readings
    cursor.execute("""
        SELECT DISTINCT surah_id, ayah_number
        FROM qiraat_texts
        ORDER BY surah_id, ayah_number
    """)
    verses = cursor.fetchall()

    diff_count = 0

    for surah_id, ayah_no in verses:
        # Get all readings for this verse
        cursor.execute("""
            SELECT riwaya_id, text_uthmani
            FROM qiraat_texts
            WHERE surah_id = ? AND ayah_number = ?
        """, (surah_id, ayah_no))
        readings = cursor.fetchall()

        if len(readings) < 2:
            continue

        # Normalize texts for comparison
        normalized = {}
        original = {}
        for riwaya_id, text in readings:
            normalized[riwaya_id] = normalize_text(text)
            original[riwaya_id] = text

        # Check if there are differences
        unique_readings = set(normalized.values())
        if len(unique_readings) > 1:
            # Found a difference
            cursor.execute("""
                INSERT INTO qiraat_differences (surah_id, ayah_number, difference_type)
                VALUES (?, ?, 'text_variant')
            """, (surah_id, ayah_no))
            diff_id = cursor.lastrowid

            # Insert each reading
            for riwaya_id, text in original.items():
                cursor.execute("""
                    INSERT INTO qiraat_difference_readings (difference_id, riwaya_id, reading_text)
                    VALUES (?, ?, ?)
                """, (diff_id, riwaya_id, text))

            diff_count += 1

    conn.commit()
    conn.close()
    print(f"Found {diff_count} verses with differences between readings")


def main():
    print("=" * 60)
    print("Importing القراءات from KFGQPC")
    print("=" * 60)

    # Setup
    setup_database()

    # Import riwayat metadata
    import_riwayat()

    # Import texts
    import_qiraat_texts()

    # Find differences
    find_differences()

    # Print summary
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    cursor.execute("SELECT name_arabic, (SELECT COUNT(*) FROM qiraat_texts WHERE riwaya_id = r.id) FROM riwayat r")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} verses")

    cursor.execute("SELECT COUNT(*) FROM qiraat_differences")
    print(f"\n  Verses with differences: {cursor.fetchone()[0]}")

    conn.close()
    print("\n" + "=" * 60)
    print("Import complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
