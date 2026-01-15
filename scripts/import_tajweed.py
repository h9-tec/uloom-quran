#!/usr/bin/env python3
"""
Import Tajweed annotations from quran-tajweed repository

This script imports tajweed rules annotations for the Quran (Hafs reading).
Each verse has character-level annotations for various tajweed rules like:
- hamzat_wasl, lam_shamsiyyah, madd_2, madd_246, etc.

Source: https://github.com/cpfair/quran-tajweed
"""

import json
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'raw', 'quran-tajweed', 'output',
                         'tajweed.hafs.uthmani-pause-sajdah.json')
DB_PATH = os.path.join(BASE_DIR, 'db', 'uloom_quran.db')

# Tajweed rule translations
TAJWEED_RULES = {
    'hamzat_wasl': {'ar': 'همزة الوصل', 'en': 'Hamzat al-Wasl', 'color': '#AAAAAA'},
    'lam_shamsiyyah': {'ar': 'اللام الشمسية', 'en': 'Lam Shamsiyyah', 'color': '#FF7E1E'},
    'madd_2': {'ar': 'مد طبيعي', 'en': 'Natural Madd (2)', 'color': '#037FFF'},
    'madd_246': {'ar': 'مد منفصل/متصل', 'en': 'Madd Munfasil/Muttasil (2-4-6)', 'color': '#2144C1'},
    'madd_6': {'ar': 'مد لازم', 'en': 'Madd Lazim (6)', 'color': '#000EAD'},
    'madd_obligatory': {'ar': 'مد واجب', 'en': 'Obligatory Madd', 'color': '#0D47A1'},
    'madd_munfasil': {'ar': 'مد منفصل', 'en': 'Madd Munfasil', 'color': '#2144C1'},
    'madd_muttasil': {'ar': 'مد متصل', 'en': 'Madd Muttasil', 'color': '#1565C0'},
    'qalqalah': {'ar': 'قلقلة', 'en': 'Qalqalah', 'color': '#DD0D0D'},
    'idgham_ghunnah': {'ar': 'إدغام بغنة', 'en': 'Idgham with Ghunnah', 'color': '#169200'},
    'idgham_no_ghunnah': {'ar': 'إدغام بلا غنة', 'en': 'Idgham without Ghunnah', 'color': '#169777'},
    'idgham_mutajanisayn': {'ar': 'إدغام متجانسين', 'en': 'Idgham Mutajanisayn', 'color': '#A1A100'},
    'idgham_mutaqaribayn': {'ar': 'إدغام متقاربين', 'en': 'Idgham Mutaqaribayn', 'color': '#A1A500'},
    'idgham_shafawi': {'ar': 'إدغام شفوي', 'en': 'Idgham Shafawi', 'color': '#169200'},
    'idghaam_ghunnah': {'ar': 'إدغام بغنة', 'en': 'Idgham with Ghunnah', 'color': '#169200'},
    'idghaam_no_ghunnah': {'ar': 'إدغام بلا غنة', 'en': 'Idgham without Ghunnah', 'color': '#169777'},
    'idghaam_mutajanisayn': {'ar': 'إدغام متجانسين', 'en': 'Idgham Mutajanisayn', 'color': '#A1A100'},
    'idghaam_mutaqaribayn': {'ar': 'إدغام متقاربين', 'en': 'Idgham Mutaqaribayn', 'color': '#A1A500'},
    'idghaam_shafawi': {'ar': 'إدغام شفوي', 'en': 'Idgham Shafawi', 'color': '#169200'},
    'ikhfa': {'ar': 'إخفاء', 'en': 'Ikhfa', 'color': '#D500B7'},
    'ikhfa_shafawi': {'ar': 'إخفاء شفوي', 'en': 'Ikhfa Shafawi', 'color': '#D500B7'},
    'iqlab': {'ar': 'إقلاب', 'en': 'Iqlab', 'color': '#26BFFD'},
    'ghunnah': {'ar': 'غنة', 'en': 'Ghunnah', 'color': '#FF7A45'},
    'silent': {'ar': 'حرف ساكن', 'en': 'Silent Letter', 'color': '#808080'},
}


def setup_database():
    """Create tables for tajweed data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for tajweed rules metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tajweed_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name_arabic TEXT NOT NULL,
            name_english TEXT NOT NULL,
            color TEXT,
            description TEXT,
            category TEXT
        )
    """)

    # Table for tajweed annotations per verse
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tajweed_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verse_id INTEGER,
            surah_id INTEGER NOT NULL,
            ayah_number INTEGER NOT NULL,
            rule_code TEXT NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            FOREIGN KEY (verse_id) REFERENCES verses(id),
            FOREIGN KEY (rule_code) REFERENCES tajweed_rules(code)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tajweed_verse ON tajweed_annotations(surah_id, ayah_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tajweed_rule ON tajweed_annotations(rule_code)")

    conn.commit()
    conn.close()
    print("Database tables created")


def import_tajweed_rules():
    """Import tajweed rule definitions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for code, info in TAJWEED_RULES.items():
        cursor.execute("""
            INSERT OR REPLACE INTO tajweed_rules (code, name_arabic, name_english, color)
            VALUES (?, ?, ?, ?)
        """, (code, info['ar'], info['en'], info.get('color')))

    conn.commit()
    conn.close()
    print(f"Imported {len(TAJWEED_RULES)} tajweed rule definitions")


def get_verse_id(cursor, surah_id, ayah_number):
    """Get verse_id from database"""
    cursor.execute("""
        SELECT id FROM verses WHERE surah_id = ? AND ayah_number = ?
    """, (surah_id, ayah_number))
    result = cursor.fetchone()
    return result[0] if result else None


def import_tajweed_annotations():
    """Import tajweed annotations from JSON file"""
    if not os.path.exists(DATA_FILE):
        print(f"Error: Data file not found: {DATA_FILE}")
        print("Please clone quran-tajweed repository first:")
        print("  git clone https://github.com/cpfair/quran-tajweed.git data/raw/quran-tajweed")
        return

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing annotations
    cursor.execute("DELETE FROM tajweed_annotations")

    total_annotations = 0
    total_verses = 0
    unknown_rules = set()

    for verse_data in data:
        surah = verse_data['surah']
        ayah = verse_data['ayah']
        annotations = verse_data.get('annotations', [])

        # Get verse_id
        verse_id = get_verse_id(cursor, surah, ayah)

        for annotation in annotations:
            rule = annotation['rule']
            start = annotation['start']
            end = annotation['end']

            # Track unknown rules
            if rule not in TAJWEED_RULES:
                unknown_rules.add(rule)

            cursor.execute("""
                INSERT INTO tajweed_annotations
                (verse_id, surah_id, ayah_number, rule_code, char_start, char_end)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (verse_id, surah, ayah, rule, start, end))
            total_annotations += 1

        total_verses += 1

    conn.commit()
    conn.close()

    print(f"\nImported {total_annotations} annotations across {total_verses} verses")

    if unknown_rules:
        print(f"\nNote: Found {len(unknown_rules)} undefined rules:")
        for rule in sorted(unknown_rules):
            print(f"  - {rule}")


def print_summary():
    """Print import summary"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("Tajweed Annotations Summary")
    print("=" * 60)

    # Count annotations by rule
    cursor.execute("""
        SELECT ta.rule_code, tr.name_arabic, COUNT(*)
        FROM tajweed_annotations ta
        LEFT JOIN tajweed_rules tr ON ta.rule_code = tr.code
        GROUP BY ta.rule_code
        ORDER BY COUNT(*) DESC
    """)

    print("\nAnnotations by rule:")
    for row in cursor.fetchall():
        name = row[1] or row[0]
        print(f"  {name}: {row[2]:,}")

    # Count by surah (top 10)
    cursor.execute("""
        SELECT surah_id, COUNT(*) as cnt
        FROM tajweed_annotations
        GROUP BY surah_id
        ORDER BY cnt DESC
        LIMIT 10
    """)

    print("\nTop 10 surahs by annotation count:")
    for row in cursor.fetchall():
        print(f"  Surah {row[0]}: {row[1]:,}")

    conn.close()


def main():
    print("=" * 60)
    print("Importing Tajweed Annotations from quran-tajweed")
    print("=" * 60)

    # Setup
    setup_database()

    # Import rule definitions
    import_tajweed_rules()

    # Import annotations
    import_tajweed_annotations()

    # Print summary
    print_summary()

    print("\n" + "=" * 60)
    print("Import complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
