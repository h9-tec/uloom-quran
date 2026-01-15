#!/usr/bin/env python3
"""
Import Arabic أسباب النزول from Quran-Database into uloom_quran.db

This script imports authentic Arabic أسباب النزول from Al-Wahidi's work
into the main database, replacing the English translation data.
"""

import sqlite3
import os

# Paths
RAW_DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'quran.db')
MAIN_DB = os.path.join(os.path.dirname(__file__), '..', 'db', 'uloom_quran.db')


def get_source_id(cursor, source_name="كتاب أسباب النزول"):
    """Get or create the source entry for Al-Wahidi's book"""
    cursor.execute("SELECT id FROM asbab_sources WHERE name_arabic = ?", (source_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Insert new source for Al-Wahidi
    cursor.execute("""
        INSERT INTO asbab_sources (name_arabic, name_english, author_arabic, death_year_hijri, description)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "كتاب أسباب النزول",
        "Asbab al-Nuzul",
        "أبو الحسن علي بن أحمد الواحدي النيسابوري",
        "468",
        "أول كتاب مستقل في أسباب النزول، ألفه الإمام الواحدي وهو من أهم المصادر في هذا العلم"
    ))
    return cursor.lastrowid


def import_asbab():
    """Import Arabic أسباب النزول from raw database"""

    # Connect to source database
    source_conn = sqlite3.connect(RAW_DB)
    source_cursor = source_conn.cursor()

    # Connect to main database
    main_conn = sqlite3.connect(MAIN_DB)
    main_cursor = main_conn.cursor()

    print("=" * 60)
    print("استيراد أسباب النزول العربية")
    print("Importing Arabic أسباب النزول")
    print("=" * 60)

    # Get or create source
    source_id = get_source_id(main_cursor)
    print(f"\nSource ID: {source_id}")

    # Clear existing asbab data
    main_cursor.execute("DELETE FROM asbab_nuzul")
    print("Cleared existing asbab data")

    # Get all Arabic asbab from source
    source_cursor.execute("""
        SELECT sora, aya_no, sora_name_ar, reasons_of_verses
        FROM quran
        WHERE reasons_of_verses IS NOT NULL AND reasons_of_verses != ''
    """)

    imported = 0
    skipped = 0

    for row in source_cursor.fetchall():
        surah_id, ayah_no, surah_name, sabab_text = row
        verse_key = f"{surah_id}:{ayah_no}"

        # Get verse_id from main database
        main_cursor.execute("SELECT id FROM verses WHERE verse_key = ?", (verse_key,))
        verse_row = main_cursor.fetchone()

        if not verse_row:
            print(f"  Warning: Verse {verse_key} not found in main database")
            skipped += 1
            continue

        verse_id = verse_row[0]

        # Insert asbab entry
        main_cursor.execute("""
            INSERT INTO asbab_nuzul (verse_id, source_id, sabab_text, revelation_period, authenticity_grade)
            VALUES (?, ?, ?, ?, ?)
        """, (
            verse_id,
            source_id,
            sabab_text.strip(),
            None,  # revelation_period
            None   # authenticity_grade (grading can be added later)
        ))

        imported += 1

        if imported % 100 == 0:
            print(f"  Imported {imported} entries...")

    main_conn.commit()

    print()
    print("=" * 60)
    print(f"Import complete!")
    print(f"  - Imported: {imported} entries")
    print(f"  - Skipped: {skipped} entries")
    print("=" * 60)

    # Show statistics by surah
    main_cursor.execute("""
        SELECT s.name_arabic, COUNT(*) as count
        FROM asbab_nuzul a
        JOIN verses v ON a.verse_id = v.id
        JOIN surahs s ON v.surah_id = s.id
        GROUP BY s.id
        ORDER BY count DESC
        LIMIT 10
    """)

    print("\nTop 10 surahs with أسباب النزول:")
    for row in main_cursor.fetchall():
        print(f"  {row[0]}: {row[1]} entries")

    source_conn.close()
    main_conn.close()


if __name__ == "__main__":
    import_asbab()
