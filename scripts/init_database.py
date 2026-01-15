#!/usr/bin/env python3
"""
Database Initialization Script
Populates the علوم القرآن database with data from various sources

Sources:
1. Quran-Data: Verses, Surahs, basic metadata
2. tafseer-sqlite-db: 8 Arabic tafsirs
3. Quraan_DB: Additional tafsirs
4. tafsir_api: JSON tafsirs including Asbab al-Nuzul
"""

import sqlite3
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
DB_DIR = BASE_DIR / "db"
OUTPUT_DB = DB_DIR / "uloom_quran.db"

# Source paths
QURAN_DATA_JSON = DATA_DIR / "Quran-Data" / "data" / "mainDataQuran.json"
TAFASEER_DB = DATA_DIR / "tafseer-sqlite-db" / "tafaseer.db"
QURAAN_DB = DATA_DIR / "Quraan_DB" / "Quraan.db"
TAFSIR_API_DIR = DATA_DIR / "tafsir_api" / "tafsir"


class DatabaseInitializer:
    """Initialize and populate the علوم القرآن database"""

    def __init__(self, db_path: Path = OUTPUT_DB):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")
        logger.info(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            logger.info("Database connection closed")

    def init_schema(self):
        """Initialize database schema from SQL file"""
        schema_file = DB_DIR / "schema.sql"

        if not schema_file.exists():
            logger.error(f"Schema file not found: {schema_file}")
            return False

        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        try:
            self.cursor.executescript(schema_sql)
            self.conn.commit()
            logger.info("Database schema initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing schema: {e}")
            return False

    def import_quran_data(self):
        """Import Quran verses and surah data from Quran-Data JSON"""
        if not QURAN_DATA_JSON.exists():
            logger.error(f"Quran data not found: {QURAN_DATA_JSON}")
            return False

        logger.info("Importing Quran base data...")

        with open(QURAN_DATA_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)

        verse_count = 0

        for surah in data:
            # Insert surah
            self.cursor.execute("""
                INSERT OR REPLACE INTO surahs
                (id, name_arabic, name_english, name_transliteration,
                 revelation_type, ayah_count, word_count, letter_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                surah['number'],
                surah['name']['ar'],
                surah['name']['en'],
                surah['name']['transliteration'],
                surah['revelation_place']['ar'],
                surah['verses_count'],
                surah.get('words_count'),
                surah.get('letters_count')
            ))

            # Insert verses
            for verse in surah['verses']:
                verse_key = f"{surah['number']}:{verse['number']}"
                self.cursor.execute("""
                    INSERT OR REPLACE INTO verses
                    (surah_id, ayah_number, verse_key, text_uthmani,
                     page_number, juz_number)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    surah['number'],
                    verse['number'],
                    verse_key,
                    verse['text']['ar'],
                    verse.get('page'),
                    verse.get('juz')
                ))
                verse_count += 1

        self.conn.commit()
        logger.info(f"Imported {len(data)} surahs and {verse_count} verses")
        return True

    def import_tafsirs_from_sqlite(self):
        """Import tafsirs from tafseer-sqlite-db"""
        if not TAFASEER_DB.exists():
            logger.warning(f"Tafseer DB not found: {TAFASEER_DB}")
            return False

        logger.info("Importing tafsirs from tafseer-sqlite-db...")

        # Connect to source database
        src_conn = sqlite3.connect(TAFASEER_DB)
        src_cursor = src_conn.cursor()

        # Get tafsir names mapping
        src_cursor.execute("SELECT ID, Name, NameE FROM TafseerName")
        tafsir_mapping = {}
        for row in src_cursor.fetchall():
            tafsir_mapping[row[0]] = {'name_ar': row[1], 'short_name': row[2]}

        # Map to our tafsir_books table (already populated from schema)
        name_to_id = {
            'tabary': 1,      # الطبري
            'katheer': 2,     # ابن كثير
            'baghawy': 3,     # البغوي
            'qortobi': 4,     # القرطبي
            'saadi': 10,      # السعدي
            'tanweer': 11,    # ابن عاشور
            'eerab': None,    # إعراب - needs separate handling
            'waseet': 15,     # الوسيط
        }

        # Import tafsir entries
        entry_count = 0
        src_cursor.execute("SELECT tafseer, sura, ayah, nass FROM Tafseer")

        for row in src_cursor.fetchall():
            tafseer_id, sura, ayah, text = row

            if tafseer_id not in tafsir_mapping:
                continue

            short_name = tafsir_mapping[tafseer_id]['short_name']
            our_tafsir_id = name_to_id.get(short_name)

            if not our_tafsir_id:
                continue

            # Get verse_id from our database
            self.cursor.execute(
                "SELECT id FROM verses WHERE surah_id = ? AND ayah_number = ?",
                (sura, ayah)
            )
            result = self.cursor.fetchone()

            if result:
                verse_id = result[0]
                try:
                    self.cursor.execute("""
                        INSERT OR REPLACE INTO tafsir_entries
                        (tafsir_id, verse_id, text_arabic, word_count)
                        VALUES (?, ?, ?, ?)
                    """, (
                        our_tafsir_id,
                        verse_id,
                        text,
                        len(text.split()) if text else 0
                    ))
                    entry_count += 1
                except Exception as e:
                    logger.warning(f"Error inserting tafsir {sura}:{ayah}: {e}")

            if entry_count % 10000 == 0:
                logger.info(f"  Imported {entry_count} tafsir entries...")
                self.conn.commit()

        src_conn.close()
        self.conn.commit()
        logger.info(f"Imported {entry_count} tafsir entries")
        return True

    def import_asbab_nuzul_from_api(self):
        """Import Asbab al-Nuzul from tafsir_api"""
        asbab_file = TAFSIR_API_DIR / "en-asbab-al-nuzul-by-al-wahidi"

        if not asbab_file.exists():
            # Try to find the directory
            if TAFSIR_API_DIR.exists():
                for item in TAFSIR_API_DIR.iterdir():
                    if 'asbab' in item.name.lower() or 'wahidi' in item.name.lower():
                        asbab_file = item
                        break

        if not asbab_file.exists():
            logger.warning("Asbab al-Nuzul data not found in tafsir_api")
            return False

        logger.info(f"Importing Asbab al-Nuzul from {asbab_file}...")

        entry_count = 0

        # The tafsir_api stores each surah as a separate JSON file
        for surah_file in sorted(asbab_file.glob("*.json")):
            try:
                with open(surah_file, 'r', encoding='utf-8') as f:
                    surah_data = json.load(f)

                surah_num = int(surah_file.stem)

                # Parse the structure (may vary)
                if isinstance(surah_data, dict):
                    verses_data = surah_data.get('ayahs', surah_data.get('verses', []))
                elif isinstance(surah_data, list):
                    verses_data = surah_data
                else:
                    continue

                for verse_data in verses_data:
                    if isinstance(verse_data, dict):
                        ayah_num = verse_data.get('ayah', verse_data.get('verse'))
                        text = verse_data.get('text', verse_data.get('tafsir', ''))
                    else:
                        continue

                    if not text or not ayah_num:
                        continue

                    # Get verse_id
                    self.cursor.execute(
                        "SELECT id FROM verses WHERE surah_id = ? AND ayah_number = ?",
                        (surah_num, ayah_num)
                    )
                    result = self.cursor.fetchone()

                    if result:
                        verse_id = result[0]
                        self.cursor.execute("""
                            INSERT OR IGNORE INTO asbab_nuzul
                            (verse_id, source_id, sabab_text)
                            VALUES (?, 1, ?)
                        """, (verse_id, text))
                        entry_count += 1

            except Exception as e:
                logger.warning(f"Error processing {surah_file}: {e}")

        self.conn.commit()
        logger.info(f"Imported {entry_count} Asbab al-Nuzul entries")
        return True

    def import_additional_tafsirs(self):
        """Import additional tafsirs from Quraan_DB"""
        tafsir_dir = DATA_DIR / "Quraan_DB" / "Tafseer"

        if not tafsir_dir.exists():
            logger.warning(f"Tafseer directory not found: {tafsir_dir}")
            return False

        logger.info("Importing additional tafsirs from Quraan_DB...")

        # Map file names to tafsir IDs
        file_mapping = {
            'Quraan_AQ.db': 4,   # القرطبي (if not already imported)
            'Quraan_IK.db': 2,   # ابن كثير (if not already imported)
            'Quraan_Ba.db': 3,   # البغوي (if not already imported)
            'Quraan_AS.db': 10,  # السعدي (if not already imported)
        }

        total_imported = 0

        for db_file, tafsir_id in file_mapping.items():
            db_path = tafsir_dir / db_file

            if not db_path.exists():
                continue

            try:
                src_conn = sqlite3.connect(db_path)
                src_cursor = src_conn.cursor()

                # Get table name
                src_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in src_cursor.fetchall()]

                for table in tables:
                    if table in ['android_metadata', 'sqlite_sequence']:
                        continue

                    # Try to get column info
                    src_cursor.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in src_cursor.fetchall()]

                    # Common patterns for tafsir tables
                    sura_col = next((c for c in columns if 'sura' in c.lower()), None)
                    ayah_col = next((c for c in columns if 'ayah' in c.lower() or 'aya' in c.lower()), None)
                    text_col = next((c for c in columns if 'text' in c.lower() or 'nass' in c.lower() or 'tafseer' in c.lower()), None)

                    if not all([sura_col, ayah_col, text_col]):
                        continue

                    query = f"SELECT {sura_col}, {ayah_col}, {text_col} FROM {table}"
                    src_cursor.execute(query)

                    for row in src_cursor.fetchall():
                        sura, ayah, text = row

                        if not text:
                            continue

                        self.cursor.execute(
                            "SELECT id FROM verses WHERE surah_id = ? AND ayah_number = ?",
                            (sura, ayah)
                        )
                        result = self.cursor.fetchone()

                        if result:
                            verse_id = result[0]
                            # Check if already exists
                            self.cursor.execute(
                                "SELECT id FROM tafsir_entries WHERE tafsir_id = ? AND verse_id = ?",
                                (tafsir_id, verse_id)
                            )
                            if not self.cursor.fetchone():
                                self.cursor.execute("""
                                    INSERT INTO tafsir_entries
                                    (tafsir_id, verse_id, text_arabic, word_count)
                                    VALUES (?, ?, ?, ?)
                                """, (
                                    tafsir_id,
                                    verse_id,
                                    text,
                                    len(text.split()) if text else 0
                                ))
                                total_imported += 1

                src_conn.close()

            except Exception as e:
                logger.warning(f"Error importing from {db_file}: {e}")

        self.conn.commit()
        logger.info(f"Imported {total_imported} additional tafsir entries")
        return True

    def create_indexes(self):
        """Create additional indexes for performance"""
        logger.info("Creating performance indexes...")

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_tafsir_verse_tafsir ON tafsir_entries(verse_id, tafsir_id)",
            "CREATE INDEX IF NOT EXISTS idx_asbab_source ON asbab_nuzul(source_id)",
        ]

        for idx in indexes:
            try:
                self.cursor.execute(idx)
            except Exception as e:
                logger.warning(f"Index creation warning: {e}")

        self.conn.commit()

    def generate_stats(self):
        """Generate and display database statistics"""
        logger.info("\n=== Database Statistics ===")

        stats = {}

        # Count surahs
        self.cursor.execute("SELECT COUNT(*) FROM surahs")
        stats['surahs'] = self.cursor.fetchone()[0]

        # Count verses
        self.cursor.execute("SELECT COUNT(*) FROM verses")
        stats['verses'] = self.cursor.fetchone()[0]

        # Count tafsir entries
        self.cursor.execute("SELECT COUNT(*) FROM tafsir_entries")
        stats['tafsir_entries'] = self.cursor.fetchone()[0]

        # Count tafsir entries per book
        self.cursor.execute("""
            SELECT tb.name_arabic, tb.short_name, COUNT(te.id) as count
            FROM tafsir_books tb
            LEFT JOIN tafsir_entries te ON tb.id = te.tafsir_id
            GROUP BY tb.id
            ORDER BY count DESC
        """)
        stats['tafsirs'] = self.cursor.fetchall()

        # Count asbab entries
        self.cursor.execute("SELECT COUNT(*) FROM asbab_nuzul")
        stats['asbab_nuzul'] = self.cursor.fetchone()[0]

        # Count qiraat data
        self.cursor.execute("SELECT COUNT(*) FROM qurra")
        stats['qurra'] = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM ruwat")
        stats['ruwat'] = self.cursor.fetchone()[0]

        # Display stats
        print(f"\nSurahs: {stats['surahs']}")
        print(f"Verses: {stats['verses']}")
        print(f"Tafsir Entries: {stats['tafsir_entries']}")
        print(f"Asbab al-Nuzul Entries: {stats['asbab_nuzul']}")
        print(f"Qurra (Readers): {stats['qurra']}")
        print(f"Ruwat (Transmitters): {stats['ruwat']}")

        print("\nTafsir Books:")
        for tafsir in stats['tafsirs']:
            print(f"  {tafsir[0]} ({tafsir[1]}): {tafsir[2]} entries")

        return stats

    def run_full_import(self):
        """Run the complete import process"""
        logger.info("Starting full database import...")

        self.connect()

        # Initialize schema
        if not self.init_schema():
            logger.error("Failed to initialize schema")
            self.close()
            return False

        # Import in order
        self.import_quran_data()
        self.import_tafsirs_from_sqlite()
        self.import_asbab_nuzul_from_api()
        self.import_additional_tafsirs()

        # Create indexes
        self.create_indexes()

        # Generate stats
        self.generate_stats()

        self.close()
        logger.info("Database import complete!")
        return True


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize علوم القرآن database")
    parser.add_argument("--db", default=str(OUTPUT_DB), help="Database path")
    parser.add_argument("--schema-only", action="store_true", help="Only create schema")
    parser.add_argument("--stats", action="store_true", help="Show stats only")

    args = parser.parse_args()

    initializer = DatabaseInitializer(Path(args.db))

    if args.stats:
        initializer.connect()
        initializer.generate_stats()
        initializer.close()
    elif args.schema_only:
        initializer.connect()
        initializer.init_schema()
        initializer.close()
    else:
        initializer.run_full_import()


if __name__ == "__main__":
    main()
