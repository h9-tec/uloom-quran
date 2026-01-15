#!/usr/bin/env python3
"""
Import all existing qiraat audio data into the database.

Sources:
1. /home/hesham-haroun/Quran/data/processed/qiraat_audio_sources.json
   - QuranicAudio.com sources for Warsh, Qaloon, Doori, Shubah

2. /home/hesham-haroun/Quran/data/raw/Quran-Data/data/json/audio/
   - 114 surah files with multiple reciters from various riwayat
"""

import json
import sqlite3
import os
from pathlib import Path
from collections import defaultdict

DB_PATH = '/home/hesham-haroun/Quran/db/uloom_quran.db'
PROCESSED_SOURCE = '/home/hesham-haroun/Quran/data/processed/qiraat_audio_sources.json'
RAW_AUDIO_DIR = '/home/hesham-haroun/Quran/data/raw/Quran-Data/data/json/audio/'

# Mapping of riwaya names (Arabic) to their codes in the riwayat table
RIWAYA_MAPPING = {
    # Hafs variations
    'حفص عن عاصم': 'hafs',

    # Warsh variations
    'ورش عن نافع': 'warsh',
    'warsh': 'warsh',

    # Qaloon variations
    'قالون عن نافع': 'qaloon',
    'qaloon': 'qaloon',

    # Shubah variations
    'شعبة عن عاصم': 'shouba',
    'shubah': 'shouba',

    # Doori (Abu Amr) variations
    'الدوري عن أبي عمرو': 'doori',
    'doori': 'doori',

    # Soosi variations
    'السوسي عن أبي عمرو': 'soosi',

    # Bazzi variations
    'البزي عن ابن كثير': 'bazzi',
    'البزي وقنبل عن ابن كثير': 'bazzi',  # Combined - map to bazzi

    # Qunbul variations
    'قنبل عن ابن كثير': 'qumbul',

    # Additional riwayat that may need to be added
    'ابن ذكوان عن ابن عامر': None,  # Ibn Dhakwan - not in current riwayat table
    'الدوري عن الكسائي': None,  # Al-Douri from Al-Kisai - different from Abu Amr
    'خلف عن حمزة': None,  # Khalaf from Hamza
    'روايتي رويس وروح': None,  # Ruways and Rawh
}


def get_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def get_riwaya_id_map(conn):
    """Get mapping of riwaya code to ID."""
    cursor = conn.cursor()
    cursor.execute('SELECT id, code FROM riwayat')
    return {row[1]: row[0] for row in cursor.fetchall()}


def ensure_riwayat_exist(conn):
    """Ensure all needed riwayat exist in the database."""
    cursor = conn.cursor()

    # New riwayat to add if they don't exist
    new_riwayat = [
        ('ibn_dhakwan', 'ابن ذكوان عن ابن عامر', 'Ibn Dhakwan from Ibn Amir'),
        ('doori_kisai', 'الدوري عن الكسائي', 'Al-Douri from Al-Kisai'),
        ('khalaf', 'خلف عن حمزة', 'Khalaf from Hamza'),
        ('ruways', 'رويس عن يعقوب', 'Ruways from Yaqub'),
        ('rawh', 'روح عن يعقوب', 'Rawh from Yaqub'),
    ]

    for code, name_ar, name_en in new_riwayat:
        cursor.execute(
            '''INSERT OR IGNORE INTO riwayat (code, name_arabic, name_english)
               VALUES (?, ?, ?)''',
            (code, name_ar, name_en)
        )

    conn.commit()

    # Update mapping
    RIWAYA_MAPPING['ابن ذكوان عن ابن عامر'] = 'ibn_dhakwan'
    RIWAYA_MAPPING['الدوري عن الكسائي'] = 'doori_kisai'
    RIWAYA_MAPPING['خلف عن حمزة'] = 'khalaf'
    RIWAYA_MAPPING['روايتي رويس وروح'] = 'ruways'  # Map to ruways as primary


def normalize_riwaya(riwaya_ar, riwaya_en=None):
    """Normalize riwaya name to code."""
    # Try Arabic first
    if riwaya_ar in RIWAYA_MAPPING:
        return RIWAYA_MAPPING[riwaya_ar]

    # Try lowercase English
    if riwaya_en:
        riwaya_lower = riwaya_en.lower()
        for key in RIWAYA_MAPPING:
            if key.lower() in riwaya_lower:
                return RIWAYA_MAPPING[key]

    return None


def import_from_processed_source(conn, stats):
    """Import reciters from qiraat_audio_sources.json (QuranicAudio.com)."""
    if not os.path.exists(PROCESSED_SOURCE):
        print(f"Warning: {PROCESSED_SOURCE} not found")
        return

    with open(PROCESSED_SOURCE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cursor = conn.cursor()
    riwaya_id_map = get_riwaya_id_map(conn)

    for source in data.get('sources', []):
        source_name = source.get('name', '')

        for recitation in source.get('recitations', []):
            riwaya_code = recitation.get('riwaya', '').lower()
            reciter = recitation.get('reciter')
            audio_base_url = recitation.get('audio_base_url')

            if not reciter or not audio_base_url:
                continue

            # Map riwaya code
            if riwaya_code == 'doori':
                riwaya_code = 'doori'
            elif riwaya_code == 'shubah':
                riwaya_code = 'shouba'

            riwaya_id = riwaya_id_map.get(riwaya_code)

            if not riwaya_id:
                print(f"  Warning: Unknown riwaya '{riwaya_code}' for {reciter}")
                continue

            # Check for url pattern
            url_pattern = source.get('url_pattern', '{download_base}/{reciter_path}/{surah_number_3digit}.mp3')

            # Insert reciter
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO qiraat_audio_reciters
                    (riwaya_id, name_arabic, name_english, audio_base_url, url_pattern, has_verse_audio)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    riwaya_id,
                    reciter,  # Use English name for both if no Arabic
                    reciter,
                    audio_base_url,
                    url_pattern,
                    1 if 'everyayah' in source_name.lower() else 0
                ))
                stats[riwaya_code] += 1
            except sqlite3.IntegrityError as e:
                print(f"  Duplicate: {reciter} for {riwaya_code}")

    conn.commit()


def import_from_raw_audio_files(conn, stats):
    """Import reciters from raw audio surah JSON files."""
    if not os.path.exists(RAW_AUDIO_DIR):
        print(f"Warning: {RAW_AUDIO_DIR} not found")
        return

    cursor = conn.cursor()
    riwaya_id_map = get_riwaya_id_map(conn)

    # Read from first surah file (they all have the same reciters)
    audio_file = os.path.join(RAW_AUDIO_DIR, 'audio_surah_1.json')
    if not os.path.exists(audio_file):
        print(f"Warning: {audio_file} not found")
        return

    with open(audio_file, 'r', encoding='utf-8') as f:
        reciters = json.load(f)

    # Track unique reciters by (name_en, server) to avoid duplicates
    seen = set()

    for reciter_data in reciters:
        reciter_ar = reciter_data.get('reciter', {}).get('ar', '')
        reciter_en = reciter_data.get('reciter', {}).get('en', '')
        rewaya_ar = reciter_data.get('rewaya', {}).get('ar', '')
        rewaya_en = reciter_data.get('rewaya', {}).get('en', '')
        server = reciter_data.get('server', '')

        if not reciter_en or not server:
            continue

        # Create unique key
        unique_key = (reciter_en, server)
        if unique_key in seen:
            continue
        seen.add(unique_key)

        # Get riwaya code
        riwaya_code = normalize_riwaya(rewaya_ar, rewaya_en)

        if not riwaya_code:
            print(f"  Warning: Unknown riwaya '{rewaya_ar}' ({rewaya_en}) for {reciter_en}")
            continue

        riwaya_id = riwaya_id_map.get(riwaya_code)

        if not riwaya_id:
            print(f"  Warning: No riwaya_id for code '{riwaya_code}'")
            continue

        # URL pattern for these files is: {server}/{surah_3digit}.mp3
        url_pattern = '{audio_base_url}/{surah_number_3digit}.mp3'

        # Check if already exists
        cursor.execute('''
            SELECT id FROM qiraat_audio_reciters
            WHERE name_english = ? AND audio_base_url = ?
        ''', (reciter_en, server))

        if cursor.fetchone():
            continue  # Skip duplicate

        # Insert reciter
        try:
            cursor.execute('''
                INSERT INTO qiraat_audio_reciters
                (riwaya_id, name_arabic, name_english, audio_base_url, url_pattern, has_verse_audio)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                riwaya_id,
                reciter_ar,
                reciter_en,
                server.rstrip('/'),
                url_pattern,
                0  # Surah-level audio, not verse-level
            ))
            stats[riwaya_code] += 1
        except sqlite3.IntegrityError as e:
            print(f"  Duplicate: {reciter_en} for {riwaya_code}")

    conn.commit()


def main():
    """Main import function."""
    print("=" * 60)
    print("Importing Qiraat Audio Reciters")
    print("=" * 60)

    conn = get_connection()

    # Ensure all riwayat exist
    print("\n1. Ensuring all riwayat exist in database...")
    ensure_riwayat_exist(conn)

    # Stats tracking
    stats = defaultdict(int)

    # Import from processed source (QuranicAudio.com)
    print("\n2. Importing from qiraat_audio_sources.json...")
    import_from_processed_source(conn, stats)

    # Import from raw audio files
    print("\n3. Importing from raw audio JSON files...")
    import_from_raw_audio_files(conn, stats)

    # Print summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)

    # Get full riwaya names for display
    cursor = conn.cursor()
    cursor.execute('SELECT code, name_english FROM riwayat')
    code_to_name = {row[0]: row[1] for row in cursor.fetchall()}

    total = 0
    for riwaya_code in sorted(stats.keys()):
        count = stats[riwaya_code]
        name = code_to_name.get(riwaya_code, riwaya_code)
        print(f"  {name}: {count} reciters")
        total += count

    print("-" * 40)
    print(f"  TOTAL: {total} reciters imported")

    # Verify by querying database
    print("\n" + "=" * 60)
    print("DATABASE VERIFICATION")
    print("=" * 60)

    cursor.execute('''
        SELECT r.name_english, COUNT(ar.id) as count
        FROM riwayat r
        LEFT JOIN qiraat_audio_reciters ar ON r.id = ar.riwaya_id
        GROUP BY r.id
        HAVING count > 0
        ORDER BY count DESC
    ''')

    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} reciters")

    cursor.execute('SELECT COUNT(*) FROM qiraat_audio_reciters')
    print("-" * 40)
    print(f"  TOTAL IN DATABASE: {cursor.fetchone()[0]} reciters")

    conn.close()
    print("\nImport complete!")


if __name__ == '__main__':
    main()
