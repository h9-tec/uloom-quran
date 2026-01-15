#!/usr/bin/env python3
"""
Import Qiraat Audio Data into Database

This script imports qiraat audio reciters and audio sources from JSON files
into the uloom_quran database.

Tables created:
- qiraat_reciters: Contemporary reciters with their riwaya association
- qiraat_audio_sources: Audio source configurations for each reciter
"""

import json
import sqlite3
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "db" / "uloom_quran.db"
AUDIO_DATA_DIR = BASE_DIR / "data" / "processed" / "audio"


class QiraatAudioImporter:
    """Import Qiraat audio data into the database"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.riwayat_map: Dict[str, int] = {}

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

    def create_tables(self):
        """Create audio tables if they don't exist"""
        logger.info("Creating audio tables...")

        # Table for qiraat reciters (contemporary reciters)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS qiraat_reciters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                riwaya_id INTEGER,
                name_arabic TEXT NOT NULL,
                name_english TEXT NOT NULL,
                country TEXT,
                style TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (riwaya_id) REFERENCES riwayat(id)
            )
        """)

        # Table for audio sources (where to find audio files)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS qiraat_audio_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reciter_id INTEGER NOT NULL,
                source_name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                surah_pattern TEXT,
                verse_pattern TEXT,
                quality TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reciter_id) REFERENCES qiraat_reciters(id)
            )
        """)

        # Create indexes for better query performance
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_qiraat_reciters_riwaya
            ON qiraat_reciters(riwaya_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_qiraat_audio_sources_reciter
            ON qiraat_audio_sources(reciter_id)
        """)

        self.conn.commit()
        logger.info("Audio tables created successfully")

    def load_riwayat_mapping(self):
        """Load mapping of riwaya codes to IDs from the database"""
        logger.info("Loading riwayat mapping...")

        self.cursor.execute("SELECT id, code FROM riwayat")
        rows = self.cursor.fetchall()

        for row in rows:
            self.riwayat_map[row['code']] = row['id']

        logger.info(f"Loaded {len(self.riwayat_map)} riwayat mappings")

        if self.riwayat_map:
            logger.info(f"Available riwayat codes: {list(self.riwayat_map.keys())}")

    def get_riwaya_id(self, riwaya_code: str) -> Optional[int]:
        """Get riwaya_id from code, handling variations"""
        if not riwaya_code:
            return None

        # Direct match
        if riwaya_code in self.riwayat_map:
            return self.riwayat_map[riwaya_code]

        # Try lowercase
        code_lower = riwaya_code.lower()
        if code_lower in self.riwayat_map:
            return self.riwayat_map[code_lower]

        # Try common variations
        variations = {
            'douri': 'doori',
            'doury': 'doori',
            'shubah': 'shouba',
            'shuba': 'shouba',
            'shu\'bah': 'shouba',
        }

        if code_lower in variations:
            mapped = variations[code_lower]
            if mapped in self.riwayat_map:
                return self.riwayat_map[mapped]

        logger.warning(f"No riwaya_id found for code: {riwaya_code}")
        return None

    def load_json_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load a JSON file from the audio data directory"""
        file_path = AUDIO_DATA_DIR / filename

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded: {filename}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON error in {filename}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return None

    def import_reciters(self) -> Dict[int, int]:
        """Import reciters from JSON file and return mapping of JSON ID to DB ID"""
        logger.info("Importing reciters...")

        data = self.load_json_file("reciters.json")
        if not data or 'reciters' not in data:
            logger.warning("No reciters data found")
            return {}

        reciters = data['reciters']
        id_mapping: Dict[int, int] = {}
        imported_count = 0

        for reciter in reciters:
            json_id = reciter.get('id')
            riwaya_code = reciter.get('riwaya_code')
            name_arabic = reciter.get('name_arabic', '')
            name_english = reciter.get('name_english', '')
            country = reciter.get('country')
            style = reciter.get('style')

            if not name_arabic or not name_english:
                logger.warning(f"Skipping reciter with missing name: {reciter}")
                continue

            # Get riwaya_id from code
            riwaya_id = self.get_riwaya_id(riwaya_code)

            try:
                self.cursor.execute("""
                    INSERT INTO qiraat_reciters
                    (riwaya_id, name_arabic, name_english, country, style)
                    VALUES (?, ?, ?, ?, ?)
                """, (riwaya_id, name_arabic, name_english, country, style))

                db_id = self.cursor.lastrowid
                if json_id is not None:
                    id_mapping[json_id] = db_id

                imported_count += 1
                logger.debug(f"Imported reciter: {name_english} ({name_arabic})")

            except sqlite3.IntegrityError as e:
                logger.warning(f"Duplicate reciter skipped: {name_english} - {e}")
            except Exception as e:
                logger.error(f"Error importing reciter {name_english}: {e}")

        self.conn.commit()
        logger.info(f"Imported {imported_count} reciters")
        return id_mapping

    def import_audio_sources(self, reciter_id_mapping: Dict[int, int]):
        """Import audio sources from JSON file"""
        logger.info("Importing audio sources...")

        data = self.load_json_file("sources.json")
        if not data or 'sources' not in data:
            logger.warning("No sources data found")
            return

        sources = data['sources']
        imported_count = 0

        for source in sources:
            json_reciter_id = source.get('reciter_id')
            source_name = source.get('source_name', '')
            base_url = source.get('base_url', '')
            surah_pattern = source.get('surah_pattern')
            verse_pattern = source.get('verse_pattern')
            quality = source.get('quality')

            if not source_name or not base_url:
                logger.warning(f"Skipping source with missing required fields: {source}")
                continue

            # Map JSON reciter_id to database ID
            db_reciter_id = reciter_id_mapping.get(json_reciter_id)

            if db_reciter_id is None:
                # Try to use the JSON ID directly if mapping doesn't exist
                # This handles cases where reciters were already in DB
                self.cursor.execute(
                    "SELECT id FROM qiraat_reciters WHERE id = ?",
                    (json_reciter_id,)
                )
                result = self.cursor.fetchone()
                if result:
                    db_reciter_id = result['id']
                else:
                    logger.warning(f"No reciter found for ID {json_reciter_id}, skipping source")
                    continue

            try:
                self.cursor.execute("""
                    INSERT INTO qiraat_audio_sources
                    (reciter_id, source_name, base_url, surah_pattern, verse_pattern, quality)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (db_reciter_id, source_name, base_url, surah_pattern, verse_pattern, quality))

                imported_count += 1
                logger.debug(f"Imported source: {source_name} for reciter {db_reciter_id}")

            except sqlite3.IntegrityError as e:
                logger.warning(f"Duplicate source skipped: {source_name} - {e}")
            except Exception as e:
                logger.error(f"Error importing source {source_name}: {e}")

        self.conn.commit()
        logger.info(f"Imported {imported_count} audio sources")

    def import_from_main_audio_sources(self):
        """
        Import additional data from the main qiraat_audio_sources.json file
        in the processed directory (if it exists and contains additional data)
        """
        main_file = BASE_DIR / "data" / "processed" / "qiraat_audio_sources.json"

        if not main_file.exists():
            logger.info("Main qiraat_audio_sources.json not found, skipping")
            return

        logger.info("Importing from main qiraat_audio_sources.json...")

        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading main audio sources file: {e}")
            return

        sources = data.get('sources', [])
        imported_reciters = 0
        imported_sources = 0

        for source in sources:
            recitations = source.get('recitations', [])
            source_name = source.get('name', '')

            for recitation in recitations:
                riwaya_code = recitation.get('riwaya', '')
                reciter_name = recitation.get('reciter', '')
                audio_base_url = recitation.get('audio_base_url', '')

                if not reciter_name or not audio_base_url:
                    continue

                riwaya_id = self.get_riwaya_id(riwaya_code)

                # Check if reciter already exists
                self.cursor.execute("""
                    SELECT id FROM qiraat_reciters
                    WHERE name_english = ? AND riwaya_id = ?
                """, (reciter_name, riwaya_id))

                result = self.cursor.fetchone()

                if result:
                    reciter_db_id = result['id']
                else:
                    # Insert new reciter
                    try:
                        self.cursor.execute("""
                            INSERT INTO qiraat_reciters
                            (riwaya_id, name_arabic, name_english, country, style)
                            VALUES (?, ?, ?, NULL, 'murattal')
                        """, (riwaya_id, reciter_name, reciter_name))
                        reciter_db_id = self.cursor.lastrowid
                        imported_reciters += 1
                    except Exception as e:
                        logger.warning(f"Could not insert reciter {reciter_name}: {e}")
                        continue

                # Check if source already exists
                self.cursor.execute("""
                    SELECT id FROM qiraat_audio_sources
                    WHERE reciter_id = ? AND base_url = ?
                """, (reciter_db_id, audio_base_url))

                if not self.cursor.fetchone():
                    # Determine patterns based on source
                    surah_pattern = "{surah:03d}.mp3"
                    verse_pattern = None

                    if 'everyayah' in source_name.lower():
                        surah_pattern = None
                        verse_pattern = "{surah:03d}{ayah:03d}.mp3"

                    quality = recitation.get('bitrate', 'high')

                    try:
                        self.cursor.execute("""
                            INSERT INTO qiraat_audio_sources
                            (reciter_id, source_name, base_url, surah_pattern, verse_pattern, quality)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (reciter_db_id, source_name, audio_base_url,
                              surah_pattern, verse_pattern, quality))
                        imported_sources += 1
                    except Exception as e:
                        logger.warning(f"Could not insert source for {reciter_name}: {e}")

        self.conn.commit()
        logger.info(f"Imported {imported_reciters} additional reciters and {imported_sources} sources from main file")

    def print_summary(self):
        """Print summary of imported data"""
        print("\n" + "=" * 70)
        print("QIRAAT AUDIO IMPORT SUMMARY")
        print("=" * 70)

        # Count reciters
        self.cursor.execute("SELECT COUNT(*) FROM qiraat_reciters")
        reciter_count = self.cursor.fetchone()[0]
        print(f"\nTotal Reciters: {reciter_count}")

        # Count audio sources
        self.cursor.execute("SELECT COUNT(*) FROM qiraat_audio_sources")
        source_count = self.cursor.fetchone()[0]
        print(f"Total Audio Sources: {source_count}")

        # Reciters by riwaya
        print("\nReciters by Riwaya:")
        print("-" * 50)
        self.cursor.execute("""
            SELECT r.name_arabic as riwaya, r.name_english, COUNT(qr.id) as count
            FROM riwayat r
            LEFT JOIN qiraat_reciters qr ON qr.riwaya_id = r.id
            GROUP BY r.id
            HAVING count > 0
            ORDER BY count DESC
        """)
        for row in self.cursor.fetchall():
            print(f"  {row[0]} ({row[1]}): {row[2]} reciter(s)")

        # Reciters without riwaya link
        self.cursor.execute("""
            SELECT COUNT(*) FROM qiraat_reciters WHERE riwaya_id IS NULL
        """)
        unlinked = self.cursor.fetchone()[0]
        if unlinked > 0:
            print(f"\n  [Unlinked to riwaya]: {unlinked} reciter(s)")

        # Sources by provider
        print("\nSources by Provider:")
        print("-" * 50)
        self.cursor.execute("""
            SELECT source_name, COUNT(*) as count
            FROM qiraat_audio_sources
            GROUP BY source_name
            ORDER BY count DESC
        """)
        for row in self.cursor.fetchall():
            print(f"  {row[0]}: {row[1]} source(s)")

        # Sample reciters with their sources
        print("\nSample Reciters with Sources:")
        print("-" * 50)
        self.cursor.execute("""
            SELECT
                qr.name_english,
                qr.name_arabic,
                r.name_english as riwaya,
                GROUP_CONCAT(DISTINCT qs.source_name) as sources
            FROM qiraat_reciters qr
            LEFT JOIN riwayat r ON qr.riwaya_id = r.id
            LEFT JOIN qiraat_audio_sources qs ON qs.reciter_id = qr.id
            GROUP BY qr.id
            LIMIT 5
        """)
        for row in self.cursor.fetchall():
            riwaya = row[2] or "N/A"
            sources = row[3] or "No sources"
            print(f"  {row[0]} ({row[1]})")
            print(f"    Riwaya: {riwaya}")
            print(f"    Sources: {sources}")

        print("\n" + "=" * 70)

    def run_import(self):
        """Run the complete import process"""
        logger.info("Starting Qiraat Audio Import...")

        self.connect()

        try:
            # Step 1: Create tables
            self.create_tables()

            # Step 2: Load riwayat mapping for linking
            self.load_riwayat_mapping()

            # Step 3: Import reciters
            reciter_id_mapping = self.import_reciters()

            # Step 4: Import audio sources
            self.import_audio_sources(reciter_id_mapping)

            # Step 5: Import from main audio sources file
            self.import_from_main_audio_sources()

            # Step 6: Print summary
            self.print_summary()

            logger.info("Qiraat Audio Import completed successfully!")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise
        finally:
            self.close()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Import Qiraat Audio data into the database"
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help="Database path"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 70)
    print("QIRAAT AUDIO IMPORTER")
    print("Importing audio reciters and sources into the database")
    print("=" * 70)

    importer = QiraatAudioImporter(Path(args.db))
    importer.run_import()

    print("\nImport complete!")


if __name__ == "__main__":
    main()
