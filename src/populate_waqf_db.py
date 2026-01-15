#!/usr/bin/env python3
"""
Script to populate the uloom_quran.db database with waqf (stopping) and ibtida (starting) data.
This includes verse counting systems, waqf types, and waqf differences between qiraat.
"""

import sqlite3
import json
import os

DB_PATH = "/home/hesham-haroun/Quran/db/uloom_quran.db"
JSON_PATH = "/home/hesham-haroun/Quran/data/processed/qiraat_waqf.json"

def create_waqf_tables(conn):
    """Create tables for waqf and ibtida data."""
    cursor = conn.cursor()

    # Verse Counting Systems table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verse_counting_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id TEXT UNIQUE NOT NULL,
            name_arabic TEXT NOT NULL,
            name_english TEXT,
            total_verses INTEGER NOT NULL,
            narrator TEXT,
            region TEXT,
            associated_qari TEXT,
            associated_rawi TEXT,
            is_most_common INTEGER DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Waqf Types table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waqf_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_id TEXT UNIQUE NOT NULL,
            name_arabic TEXT NOT NULL,
            name_english TEXT,
            symbol TEXT,
            description TEXT,
            other_names TEXT,
            ruling TEXT,
            importance TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Waqf Signs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waqf_signs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            name_arabic TEXT NOT NULL,
            meaning TEXT,
            action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Waqf Lazim (Obligatory Stop) Locations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waqf_lazim_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            surah_number INTEGER NOT NULL,
            surah_name TEXT NOT NULL,
            ayah_number INTEGER NOT NULL,
            verse_key TEXT NOT NULL,
            text_before_stop TEXT,
            text_after TEXT,
            reason TEXT,
            qiraat_difference INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(surah_number, ayah_number)
        )
    """)

    # Qiraat Waqf Differences table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_waqf_differences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verse_key TEXT NOT NULL,
            surah_number INTEGER NOT NULL,
            ayah_number INTEGER NOT NULL,
            verse_text TEXT,
            difference_type TEXT,
            scholarly_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Qiraat Waqf Readings (individual readings per difference)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_waqf_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            difference_id INTEGER NOT NULL,
            qari TEXT,
            waqf_position TEXT,
            waqf_type TEXT,
            meaning TEXT,
            rule TEXT,
            reason TEXT,
            duration TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (difference_id) REFERENCES qiraat_waqf_differences(id)
        )
    """)

    # Qari Waqf Methodology table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qari_waqf_methodology (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qari TEXT NOT NULL,
            methodology TEXT,
            evidence TEXT,
            preference TEXT,
            saktaat_count INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Saktaat (Brief Pauses) Locations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saktaat_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qari TEXT NOT NULL,
            surah_number INTEGER NOT NULL,
            ayah_number INTEGER NOT NULL,
            word TEXT NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Waqf Scholarly Works table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waqf_scholarly_works (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            death_year INTEGER,
            importance TEXT,
            work_type TEXT CHECK(work_type IN ('classical', 'modern')),
            journal TEXT,
            institution TEXT,
            focus TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Surah Verse Count Differences table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS surah_verse_differences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            surah_number INTEGER NOT NULL,
            surah_name TEXT NOT NULL,
            counting_system TEXT NOT NULL,
            verse_count INTEGER NOT NULL,
            reason TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Regional Mushaf Information
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regional_mushafs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mushaf_name TEXT NOT NULL,
            country TEXT NOT NULL,
            qiraa TEXT NOT NULL,
            counting_system TEXT,
            waqf_system TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_waqf_lazim_surah ON waqf_lazim_locations(surah_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_waqf_diff_verse ON qiraat_waqf_differences(verse_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_saktaat_qari ON saktaat_locations(qari)")

    conn.commit()
    print("Tables created successfully.")

def populate_data(conn, data):
    """Populate all waqf-related tables with data from JSON."""
    cursor = conn.cursor()

    # 1. Populate verse counting systems
    print("Populating verse counting systems...")
    for system in data["verse_counting_systems"]["schools"]:
        cursor.execute("""
            INSERT OR REPLACE INTO verse_counting_systems
            (system_id, name_arabic, name_english, total_verses, narrator, region,
             associated_qari, associated_rawi, is_most_common, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            system["id"],
            system["name_arabic"],
            system.get("name_en"),
            system["total_verses"],
            system.get("narrator"),
            system.get("region"),
            system.get("associated_qari"),
            system.get("associated_rawi"),
            1 if system.get("is_most_common") else 0,
            system.get("notes")
        ))

    # 2. Populate waqf types
    print("Populating waqf types...")
    for wtype in data["waqf_types"]["types"]:
        other_names = ", ".join(wtype.get("other_names", [])) if wtype.get("other_names") else None
        cursor.execute("""
            INSERT OR REPLACE INTO waqf_types
            (type_id, name_arabic, name_english, symbol, description, other_names, ruling, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            wtype["id"],
            wtype["name_arabic"],
            wtype.get("name_en"),
            wtype.get("symbol"),
            wtype.get("description"),
            other_names,
            wtype.get("ruling"),
            wtype.get("importance")
        ))

    # 3. Populate waqf signs
    print("Populating waqf signs...")
    for sign in data["waqf_signs"]["signs"]:
        cursor.execute("""
            INSERT OR REPLACE INTO waqf_signs (symbol, name_arabic, meaning, action)
            VALUES (?, ?, ?, ?)
        """, (
            sign["symbol"],
            sign["name"],
            sign["meaning"],
            sign["action"]
        ))

    # 4. Populate waqf lazim locations
    print("Populating waqf lazim locations...")
    for location in data["waqf_lazim_locations"]["locations"]:
        surah_num = location["surah"]
        surah_name = location["surah_name"]
        for verse in location["verses"]:
            verse_key = f"{surah_num}:{verse['ayah']}"
            cursor.execute("""
                INSERT OR REPLACE INTO waqf_lazim_locations
                (surah_number, surah_name, ayah_number, verse_key, text_before_stop,
                 text_after, reason, qiraat_difference)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                surah_num,
                surah_name,
                verse["ayah"],
                verse_key,
                verse.get("text_before_stop"),
                verse.get("text_after"),
                verse.get("reason"),
                1 if verse.get("qiraat_difference") else 0
            ))

    # 5. Populate qiraat waqf differences
    print("Populating qiraat waqf differences...")
    for example in data["qiraat_waqf_differences"]["examples"]:
        cursor.execute("""
            INSERT INTO qiraat_waqf_differences
            (verse_key, surah_number, ayah_number, verse_text, difference_type, scholarly_note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            example["verse_key"],
            example["surah"],
            example["ayah"],
            example.get("text"),
            example.get("difference_type"),
            example.get("scholarly_note")
        ))
        diff_id = cursor.lastrowid

        # Insert individual readings
        for reading in example.get("readings", []):
            cursor.execute("""
                INSERT INTO qiraat_waqf_readings
                (difference_id, qari, waqf_position, waqf_type, meaning, rule, reason, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                diff_id,
                reading.get("qari"),
                reading.get("waqf_position") or reading.get("position"),
                reading.get("waqf_type"),
                reading.get("meaning"),
                reading.get("rule"),
                reading.get("reason"),
                reading.get("duration")
            ))

    # 6. Populate qari waqf methodology
    print("Populating qari waqf methodology...")
    for method in data["qari_waqf_methodology"]["methods"]:
        cursor.execute("""
            INSERT OR REPLACE INTO qari_waqf_methodology
            (qari, methodology, evidence, preference, saktaat_count, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            method["qari"],
            method.get("methodology"),
            method.get("evidence"),
            method.get("preference"),
            method.get("saktaat"),
            method.get("note")
        ))

        # Insert saktaat locations if available
        if "saktaat_locations" in method:
            for saktah in method["saktaat_locations"]:
                cursor.execute("""
                    INSERT OR REPLACE INTO saktaat_locations
                    (qari, surah_number, ayah_number, word, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    method["qari"],
                    saktah["surah"],
                    saktah["ayah"],
                    saktah["word"],
                    None
                ))

    # 7. Populate scholarly works
    print("Populating scholarly works...")
    for work in data["scholarly_works"]["classical_works"]:
        cursor.execute("""
            INSERT OR REPLACE INTO waqf_scholarly_works
            (title, author, death_year, importance, work_type)
            VALUES (?, ?, ?, ?, 'classical')
        """, (
            work["title"],
            work["author"],
            work.get("death_year"),
            work.get("importance")
        ))

    for work in data["scholarly_works"]["modern_studies"]:
        cursor.execute("""
            INSERT OR REPLACE INTO waqf_scholarly_works
            (title, author, importance, work_type, journal, institution, focus)
            VALUES (?, ?, ?, 'modern', ?, ?, ?)
        """, (
            work["title"],
            work.get("author"),
            None,
            work.get("journal"),
            work.get("institution"),
            work.get("focus")
        ))

    # 8. Populate surah verse differences
    print("Populating surah verse differences...")
    for example in data["surah_verse_differences"]["examples"]:
        for diff in example["differences"]:
            for school in diff["schools"]:
                cursor.execute("""
                    INSERT OR REPLACE INTO surah_verse_differences
                    (surah_number, surah_name, counting_system, verse_count, reason, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    example["surah_number"],
                    example["surah_name"],
                    school,
                    diff["verse_count"],
                    diff.get("reason"),
                    diff.get("note")
                ))

    # 9. Populate regional mushafs
    print("Populating regional mushafs...")
    for mushaf in data["regional_mushaf_waqf"]["mushafs"]:
        cursor.execute("""
            INSERT OR REPLACE INTO regional_mushafs
            (mushaf_name, country, qiraa, counting_system, waqf_system)
            VALUES (?, ?, ?, ?, ?)
        """, (
            mushaf["name"],
            mushaf["country"],
            mushaf["qiraa"],
            mushaf.get("counting"),
            mushaf.get("waqf_system")
        ))

    conn.commit()
    print("All data populated successfully.")

def main():
    """Main function to create tables and populate data."""
    # Load JSON data
    print(f"Loading data from {JSON_PATH}...")
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Connect to database
    print(f"Connecting to database {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)

    try:
        # Create tables
        create_waqf_tables(conn)

        # Populate data
        populate_data(conn, data)

        # Show summary
        cursor = conn.cursor()
        tables = [
            "verse_counting_systems",
            "waqf_types",
            "waqf_signs",
            "waqf_lazim_locations",
            "qiraat_waqf_differences",
            "qiraat_waqf_readings",
            "qari_waqf_methodology",
            "saktaat_locations",
            "waqf_scholarly_works",
            "surah_verse_differences",
            "regional_mushafs"
        ]

        print("\n=== Summary ===")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count} records")

    finally:
        conn.close()

    print("\nDatabase population complete!")

if __name__ == "__main__":
    main()
