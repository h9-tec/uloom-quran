#!/usr/bin/env python3
"""
Import قراءات data from quran-meta repository

This script imports validated Quran text data for multiple riwayat from quran-meta:
- Hafs (v2.0), Warsh (v2.1), Qaloon (v2.1), Doori (v2.0), Soosi (v2.0), Shuba (v2.0)

The data has been validated against multiple authoritative sources:
- KFGQPC Uthmanic fonts
- AlQuran Cloud API
- Tanzil.net
- Quran API

Source: https://github.com/quran-center/quran-meta
"""

import json
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw', 'quran-meta', 'examples', 'data-check', 'data')
DB_PATH = os.path.join(BASE_DIR, 'db', 'uloom_quran.db')

# Available riwayat in quran-meta data-check examples
RIWAYAT_FILES = {
    'hafs_v2': ('hafsData_v2-0.json', 'حفص عن عاصم (v2.0)', 'Hafs from Asim (v2.0)'),
    'hafs_smart': ('hafs_smart_v8.json', 'حفص (Smart v8)', 'Hafs Smart (v8)'),
    'warsh_v2': ('warshData_v2-1.json', 'ورش عن نافع (v2.1)', 'Warsh from Nafi (v2.1)'),
    'qaloon_v2': ('QalounData_v2-1.json', 'قالون عن نافع (v2.1)', 'Qaloon from Nafi (v2.1)'),
    'doori_v2': ('DouriData_v2-0.json', 'الدوري عن أبي عمرو (v2.0)', 'Al-Douri from Abu Amr (v2.0)'),
    'soosi_v2': ('SousiData_v2-0.json', 'السوسي عن أبي عمرو (v2.0)', 'Al-Soosi from Abu Amr (v2.0)'),
    'shuba_v2': ('shubaData_v2-0.json', 'شعبة عن عاصم (v2.0)', 'Shuba from Asim (v2.0)'),
}


def setup_database():
    """Ensure tables exist for qiraat texts"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for riwayat (if not exists)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riwayat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name_arabic TEXT NOT NULL,
            name_english TEXT NOT NULL,
            qari_id INTEGER,
            source TEXT,
            version TEXT,
            description TEXT,
            FOREIGN KEY (qari_id) REFERENCES qurra(id)
        )
    """)

    # Add source column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE riwayat ADD COLUMN source TEXT")
    except:
        pass  # Column already exists

    # Ensure qiraat_texts table has source column
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
            line_start INTEGER,
            line_end INTEGER,
            source TEXT,
            FOREIGN KEY (riwaya_id) REFERENCES riwayat(id),
            FOREIGN KEY (surah_id) REFERENCES surahs(id),
            UNIQUE(riwaya_id, surah_id, ayah_number)
        )
    """)

    conn.commit()
    conn.close()
    print("Database tables verified")


def load_json_data(file_path):
    """Load JSON data from file"""
    full_path = os.path.join(DATA_DIR, file_path)
    if not os.path.exists(full_path):
        print(f"  File not found: {full_path}")
        return None

    with open(full_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def import_riwayat():
    """Import riwayat metadata"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for code, (file_path, name_ar, name_en) in RIWAYAT_FILES.items():
        cursor.execute("""
            INSERT OR REPLACE INTO riwayat (code, name_arabic, name_english, source)
            VALUES (?, ?, ?, 'quran-meta')
        """, (code, name_ar, name_en))

    conn.commit()
    conn.close()
    print(f"Imported {len(RIWAYAT_FILES)} riwayat from quran-meta")


def import_qiraat_texts():
    """Import Quran text for each riwaya"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_imported = 0

    for code, (file_name, name_ar, name_en) in RIWAYAT_FILES.items():
        print(f"\nImporting {name_ar} ({code})...")

        # Get riwaya_id
        cursor.execute("SELECT id FROM riwayat WHERE code = ?", (code,))
        riwaya_row = cursor.fetchone()
        if not riwaya_row:
            print(f"  Riwaya not found: {code}")
            continue
        riwaya_id = riwaya_row[0]

        # Load data
        data = load_json_data(file_name)
        if not data:
            continue

        # Import verses
        count = 0
        for verse in data:
            # Handle different field names
            surah_id = verse.get('sura_no') or verse.get('sora')
            ayah_no = verse.get('aya_no')
            text_uthmani = verse.get('aya_text', '')
            text_simple = verse.get('aya_text_emlaey', '')
            juz = verse.get('jozz')
            page = verse.get('page')
            line_start = verse.get('line_start')
            line_end = verse.get('line_end')

            if not surah_id or not ayah_no:
                continue

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO qiraat_texts
                    (riwaya_id, surah_id, ayah_number, text_uthmani, text_simple, juz, page, line_start, line_end, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'quran-meta')
                """, (riwaya_id, surah_id, ayah_no, text_uthmani, text_simple, juz, page, line_start, line_end))
                count += 1
            except Exception as e:
                print(f"  Error importing {surah_id}:{ayah_no}: {e}")

        print(f"  Imported {count} verses")
        total_imported += count

    conn.commit()
    conn.close()
    print(f"\nTotal verses imported from quran-meta: {total_imported}")


def main():
    print("=" * 60)
    print("Importing القراءات from quran-meta")
    print("=" * 60)

    if not os.path.exists(DATA_DIR):
        print(f"Error: Data directory not found: {DATA_DIR}")
        print("Please clone quran-meta repository first:")
        print("  git clone https://github.com/quran-center/quran-meta.git data/raw/quran-meta")
        return

    # Setup
    setup_database()

    # Import riwayat metadata
    import_riwayat()

    # Import texts
    import_qiraat_texts()

    # Print summary
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    cursor.execute("""
        SELECT r.name_arabic, COUNT(qt.id)
        FROM riwayat r
        LEFT JOIN qiraat_texts qt ON qt.riwaya_id = r.id
        WHERE r.source = 'quran-meta'
        GROUP BY r.id
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} verses")

    conn.close()
    print("\n" + "=" * 60)
    print("Import complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
