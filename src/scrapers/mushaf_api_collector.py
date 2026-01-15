#!/usr/bin/env python3
"""
Mushaf API Collector - Data Collection Script for Qiraat Data

Sources:
1. KFGQPC (King Fahd Glorious Quran Printing Complex) - Local JSON data
   - Hafs, Warsh, Shouba, Qaloon, Doori, Soosi, Bazzi, Qumbul
2. AlQuran.cloud API - Various Quran editions and qiraat
3. Tanzil.net - Quran text downloads
4. Quran.com API (via quran.foundation) - Additional editions

This script collects, normalizes, and stores qiraat data in the uloom_quran database.
"""

import requests
import sqlite3
import json
import os
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "db" / "uloom_quran.db"
EXPORT_DIR = BASE_DIR / "data" / "raw" / "qiraat_collected"

# KFGQPC Data paths
KFGQPC_DIR = DATA_DIR / "quran-data-kfgqpc"

# API Endpoints
ALQURAN_CLOUD_API = "https://api.alquran.cloud/v1"
TANZIL_BASE_URL = "https://tanzil.net"

# Qiraat mapping: rawi_name -> riwaya_id in our database (from riwayat table)
# Based on existing riwayat table data
QIRAAT_MAPPING = {
    'hafs': {'riwaya_id': 1, 'name_ar': 'حفص عن عاصم', 'name_en': 'Hafs from Asim'},
    'warsh': {'riwaya_id': 2, 'name_ar': 'ورش عن نافع', 'name_en': 'Warsh from Nafi'},
    'qaloon': {'riwaya_id': 3, 'name_ar': 'قالون عن نافع', 'name_en': 'Qaloon from Nafi'},
    'shouba': {'riwaya_id': 4, 'name_ar': 'شعبة عن عاصم', 'name_en': 'Shuba from Asim'},
    'doori': {'riwaya_id': 5, 'name_ar': 'الدوري عن أبي عمرو', 'name_en': 'Al-Douri from Abu Amr'},
    'soosi': {'riwaya_id': 6, 'name_ar': 'السوسي عن أبي عمرو', 'name_en': 'Al-Soosi from Abu Amr'},
    'bazzi': {'riwaya_id': 7, 'name_ar': 'البزي عن ابن كثير', 'name_en': 'Al-Bazzi from Ibn Kathir'},
    'qumbul': {'riwaya_id': 8, 'name_ar': 'قنبل عن ابن كثير', 'name_en': 'Qunbul from Ibn Kathir'},
}

# AlQuran.cloud edition identifiers for qiraat
ALQURAN_EDITIONS = {
    'quran-uthmani': {'type': 'text', 'qiraa': 'hafs', 'description': 'Uthmani text (Hafs)'},
    'quran-simple': {'type': 'text', 'qiraa': 'hafs', 'description': 'Simple text'},
    'quran-wordbyword': {'type': 'text', 'qiraa': 'hafs', 'description': 'Word by word'},
    # Audio editions with different qiraat
    'ar.alafasy': {'type': 'audio', 'qiraa': 'hafs', 'reciter': 'Mishary Alafasy'},
    'ar.abdulbasitmurattal': {'type': 'audio', 'qiraa': 'hafs', 'reciter': 'Abdul Basit'},
    'ar.husary': {'type': 'audio', 'qiraa': 'hafs', 'reciter': 'Mahmoud Husary'},
    'ar.minshawi': {'type': 'audio', 'qiraa': 'hafs', 'reciter': 'Mohamed Minshawi'},
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    'Accept': 'application/json',
}


@dataclass
class QiraatVerse:
    """Data class for a verse in a specific qiraat"""
    surah_id: int
    ayah_number: int
    text: str
    text_simple: Optional[str] = None
    page: Optional[int] = None
    juz: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class KFGQPCCollector:
    """Collector for KFGQPC local data (8 qiraat)"""

    def __init__(self):
        self.data_dir = KFGQPC_DIR
        self.available_qiraat = []
        self._scan_available()

    def _scan_available(self):
        """Scan available qiraat directories"""
        if not self.data_dir.exists():
            logger.warning(f"KFGQPC directory not found: {self.data_dir}")
            return

        for qiraa in QIRAAT_MAPPING.keys():
            json_path = self._get_json_path(qiraa)
            if json_path and json_path.exists():
                self.available_qiraat.append(qiraa)
                logger.info(f"Found KFGQPC data for: {qiraa}")

    def _get_json_path(self, qiraa: str) -> Optional[Path]:
        """Get JSON file path for a qiraat"""
        # Handle special cases
        qiraa_dir = qiraa
        if qiraa == 'shouba':
            qiraa_dir = 'shouba'

        qiraa_path = self.data_dir / qiraa_dir / "data"
        if not qiraa_path.exists():
            return None

        # Find the JSON file
        for f in qiraa_path.glob("*.json"):
            return f
        return None

    def load_qiraat(self, qiraa: str) -> List[QiraatVerse]:
        """Load qiraat data from JSON file"""
        json_path = self._get_json_path(qiraa)
        if not json_path or not json_path.exists():
            logger.warning(f"No JSON data found for qiraat: {qiraa}")
            return []

        logger.info(f"Loading {qiraa} from {json_path}")

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            verses = []
            for item in data:
                # Handle different JSON structures
                surah_id = item.get('sora') or item.get('sura_no')
                ayah_num = item.get('aya_no')
                text = item.get('aya_text', '')
                text_simple = item.get('aya_text_emlaey')

                if surah_id and ayah_num and text:
                    verses.append(QiraatVerse(
                        surah_id=int(surah_id),
                        ayah_number=int(ayah_num),
                        text=text,
                        text_simple=text_simple,
                        page=item.get('page'),
                        juz=item.get('jozz') or item.get('jozz'),
                        line_start=item.get('line_start'),
                        line_end=item.get('line_end')
                    ))

            logger.info(f"Loaded {len(verses)} verses for {qiraa}")
            return verses

        except Exception as e:
            logger.error(f"Error loading {qiraa}: {e}")
            return []

    def load_all(self) -> Dict[str, List[QiraatVerse]]:
        """Load all available qiraat"""
        all_data = {}
        for qiraa in self.available_qiraat:
            all_data[qiraa] = self.load_qiraat(qiraa)
        return all_data


class AlQuranCloudCollector:
    """Collector for AlQuran.cloud API"""

    def __init__(self):
        self.base_url = ALQURAN_CLOUD_API
        self.session = requests.Session()
        self.editions = {}

    def get_available_editions(self) -> Dict:
        """Get list of available editions"""
        try:
            response = self.session.get(
                f"{self.base_url}/edition",
                headers=HEADERS,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200:
                    self.editions = {e['identifier']: e for e in data.get('data', [])}
                    return self.editions
        except Exception as e:
            logger.error(f"Error fetching editions: {e}")
        return {}

    def get_quran_edition(self, edition: str = 'quran-uthmani') -> List[QiraatVerse]:
        """Get complete Quran for an edition"""
        try:
            logger.info(f"Fetching Quran edition: {edition}")
            response = self.session.get(
                f"{self.base_url}/quran/{edition}",
                headers=HEADERS,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200:
                    verses = []
                    for surah in data.get('data', {}).get('surahs', []):
                        for ayah in surah.get('ayahs', []):
                            verses.append(QiraatVerse(
                                surah_id=ayah.get('surah'),
                                ayah_number=ayah.get('numberInSurah'),
                                text=ayah.get('text', ''),
                                page=ayah.get('page'),
                                juz=ayah.get('juz')
                            ))
                    logger.info(f"Fetched {len(verses)} verses for {edition}")
                    return verses
        except Exception as e:
            logger.error(f"Error fetching edition {edition}: {e}")
        return []

    def get_surah(self, surah_num: int, edition: str = 'quran-uthmani') -> List[QiraatVerse]:
        """Get a single surah"""
        try:
            response = self.session.get(
                f"{self.base_url}/surah/{surah_num}/{edition}",
                headers=HEADERS,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200:
                    verses = []
                    surah_data = data.get('data', {})
                    for ayah in surah_data.get('ayahs', []):
                        verses.append(QiraatVerse(
                            surah_id=surah_num,
                            ayah_number=ayah.get('numberInSurah'),
                            text=ayah.get('text', ''),
                            page=ayah.get('page'),
                            juz=ayah.get('juz')
                        ))
                    return verses
        except Exception as e:
            logger.error(f"Error fetching surah {surah_num}: {e}")
        return []

    def get_audio_url(self, surah: int, ayah: int, edition: str = 'ar.alafasy') -> Optional[str]:
        """Get audio URL for a verse"""
        try:
            response = self.session.get(
                f"{self.base_url}/ayah/{surah}:{ayah}/{edition}",
                headers=HEADERS,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200:
                    return data.get('data', {}).get('audio')
        except Exception as e:
            logger.error(f"Error fetching audio: {e}")
        return None


class TanzilCollector:
    """Collector for Tanzil.net data"""

    def __init__(self):
        self.data_dir = DATA_DIR / "tanzil"

    def load_local_text(self, text_type: str = 'uthmani') -> List[QiraatVerse]:
        """Load Tanzil text from local files"""
        filename = f"quran-{text_type}.txt"
        filepath = self.data_dir / filename

        if not filepath.exists():
            logger.warning(f"Tanzil file not found: {filepath}")
            return []

        verses = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split('|')
                    if len(parts) >= 3:
                        verses.append(QiraatVerse(
                            surah_id=int(parts[0]),
                            ayah_number=int(parts[1]),
                            text=parts[2]
                        ))

            logger.info(f"Loaded {len(verses)} verses from Tanzil {text_type}")
        except Exception as e:
            logger.error(f"Error loading Tanzil data: {e}")

        return verses


class DatabaseManager:
    """Database operations for qiraat data - uses existing schema with riwayat table"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            logger.info("Database connection closed")

    def ensure_tables_exist(self):
        """Ensure required tables exist with correct schema"""
        cursor = self.conn.cursor()

        # Check if qiraat_texts table exists with correct structure
        cursor.execute("PRAGMA table_info(qiraat_texts)")
        columns = {col[1] for col in cursor.fetchall()}

        required_columns = {'riwaya_id', 'surah_id', 'ayah_number', 'text_uthmani', 'line_start'}

        if not required_columns.issubset(columns):
            # Table doesn't exist or has wrong schema - recreate it
            logger.info("Recreating qiraat_texts table with correct schema...")

            # Drop old table (backup if needed)
            cursor.execute("DROP TABLE IF EXISTS qiraat_texts_backup")
            if columns:  # Table exists but wrong schema
                cursor.execute("ALTER TABLE qiraat_texts RENAME TO qiraat_texts_backup")
            cursor.execute("DROP TABLE IF EXISTS qiraat_texts")

            cursor.execute("""
                CREATE TABLE qiraat_texts (
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
                    source TEXT DEFAULT 'KFGQPC',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (riwaya_id) REFERENCES riwayat(id),
                    UNIQUE(riwaya_id, surah_id, ayah_number)
                )
            """)
            logger.info("Created new qiraat_texts table")

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_qiraat_texts_riwaya
            ON qiraat_texts(riwaya_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_qiraat_texts_surah_ayah
            ON qiraat_texts(surah_id, ayah_number)
        """)

        self.conn.commit()
        logger.info("Database tables ready")

    def insert_qiraat_text(self, riwaya_id: int, surah_id: int, ayah_number: int,
                          text: str, text_simple: str = None,
                          page: int = None, juz: int = None,
                          line_start: int = None, line_end: int = None,
                          source: str = 'KFGQPC'):
        """Insert or update qiraat text using riwaya_id"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO qiraat_texts
                (riwaya_id, surah_id, ayah_number, text_uthmani, text_simple,
                 juz, page, line_start, line_end, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (riwaya_id, surah_id, ayah_number, text, text_simple,
                  juz, page, line_start, line_end, source))
        except Exception as e:
            logger.error(f"Error inserting qiraat text: {e}")

    def get_qiraat_stats(self) -> Dict:
        """Get statistics about stored qiraat data"""
        cursor = self.conn.cursor()
        stats = {}

        # Count by riwaya
        cursor.execute("""
            SELECT r.name_arabic, r.name_english, COUNT(qt.id) as count
            FROM riwayat r
            LEFT JOIN qiraat_texts qt ON r.id = qt.riwaya_id
            GROUP BY r.id
            ORDER BY count DESC
        """)
        stats['by_riwaya'] = cursor.fetchall()

        # Total count
        cursor.execute("SELECT COUNT(*) FROM qiraat_texts")
        stats['total'] = cursor.fetchone()[0]

        return stats


class MushafAPICollector:
    """Main collector class orchestrating all sources"""

    def __init__(self):
        self.kfgqpc = KFGQPCCollector()
        self.alquran = AlQuranCloudCollector()
        self.tanzil = TanzilCollector()
        self.db = DatabaseManager()

    def collect_kfgqpc_data(self, qiraat: List[str] = None):
        """Collect data from KFGQPC local files"""
        logger.info("=" * 60)
        logger.info("Collecting KFGQPC Data")
        logger.info("=" * 60)

        if qiraat is None:
            qiraat = self.kfgqpc.available_qiraat

        self.db.connect()
        self.db.ensure_tables_exist()

        for qiraa in qiraat:
            if qiraa not in QIRAAT_MAPPING:
                logger.warning(f"Unknown qiraat: {qiraa}")
                continue

            mapping = QIRAAT_MAPPING[qiraa]
            verses = self.kfgqpc.load_qiraat(qiraa)

            if not verses:
                continue

            imported = 0
            for verse in verses:
                self.db.insert_qiraat_text(
                    riwaya_id=mapping['riwaya_id'],
                    surah_id=verse.surah_id,
                    ayah_number=verse.ayah_number,
                    text=verse.text,
                    text_simple=verse.text_simple,
                    page=verse.page,
                    juz=verse.juz,
                    line_start=verse.line_start,
                    line_end=verse.line_end,
                    source='KFGQPC'
                )
                imported += 1

            self.db.conn.commit()
            logger.info(f"Imported {imported} verses for {qiraa}")

        self.db.close()

    def collect_alquran_cloud_data(self, editions: List[str] = None):
        """Collect data from AlQuran.cloud API"""
        logger.info("=" * 60)
        logger.info("Collecting AlQuran.cloud Data")
        logger.info("=" * 60)

        if editions is None:
            editions = ['quran-uthmani']

        self.db.connect()
        self.db.ensure_tables_exist()

        for edition in editions:
            verses = self.alquran.get_quran_edition(edition)

            if not verses:
                continue

            # For now, map all AlQuran.cloud text editions to Hafs
            mapping = QIRAAT_MAPPING['hafs']

            imported = 0
            for verse in verses:
                self.db.insert_qiraat_text(
                    riwaya_id=mapping['riwaya_id'],
                    surah_id=verse.surah_id,
                    ayah_number=verse.ayah_number,
                    text=verse.text,
                    page=verse.page,
                    juz=verse.juz,
                    source=f'alquran.cloud:{edition}'
                )
                imported += 1

            self.db.conn.commit()
            logger.info(f"Imported {imported} verses from {edition}")

            time.sleep(1)  # Rate limiting

        self.db.close()

    def export_collected_data(self, output_dir: Path = None):
        """Export collected qiraat data to JSON"""
        if output_dir is None:
            output_dir = EXPORT_DIR

        output_dir.mkdir(parents=True, exist_ok=True)

        self.db.connect()
        cursor = self.db.conn.cursor()

        # Export each qiraat
        for qiraa, mapping in QIRAAT_MAPPING.items():
            cursor.execute("""
                SELECT
                    qt.surah_id, qt.ayah_number,
                    qt.text_uthmani, qt.text_simple, qt.source,
                    qt.page, qt.juz
                FROM qiraat_texts qt
                WHERE qt.riwaya_id = ?
                ORDER BY qt.surah_id, qt.ayah_number
            """, (mapping['riwaya_id'],))

            rows = cursor.fetchall()
            if rows:
                data = [{
                    'surah': r[0],
                    'ayah': r[1],
                    'verse_key': f"{r[0]}:{r[1]}",
                    'text': r[2],
                    'text_simple': r[3],
                    'source': r[4],
                    'page': r[5],
                    'juz': r[6]
                } for r in rows]

                output_file = output_dir / f"{qiraa}_collected.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                logger.info(f"Exported {len(data)} verses to {output_file}")

        self.db.close()

    def get_stats(self):
        """Print statistics about collected data"""
        self.db.connect()
        stats = self.db.get_qiraat_stats()

        print("\n" + "=" * 60)
        print("Qiraat Data Statistics")
        print("=" * 60)
        print(f"\nTotal qiraat text entries: {stats['total']}")
        print("\nBy Riwaya (Transmission):")
        for row in stats['by_riwaya']:
            if row[2] > 0:
                print(f"  {row[0]} ({row[1]}): {row[2]} verses")

        self.db.close()

    def run_full_collection(self):
        """Run complete data collection from all sources"""
        logger.info("Starting full qiraat data collection...")

        # 1. Collect KFGQPC data (local files)
        self.collect_kfgqpc_data()

        # 2. Collect from AlQuran.cloud (API)
        # Uncomment to fetch from API (may take time)
        # self.collect_alquran_cloud_data(['quran-uthmani'])

        # 3. Export collected data
        self.export_collected_data()

        # 4. Print statistics
        self.get_stats()

        logger.info("Data collection complete!")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Collect Qiraat data from various sources'
    )
    parser.add_argument(
        '--source',
        choices=['kfgqpc', 'alquran', 'all'],
        default='all',
        help='Data source to collect from'
    )
    parser.add_argument(
        '--qiraat',
        nargs='+',
        choices=list(QIRAAT_MAPPING.keys()),
        help='Specific qiraat to collect'
    )
    parser.add_argument(
        '--export',
        action='store_true',
        help='Export collected data to JSON'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )
    parser.add_argument(
        '--list-editions',
        action='store_true',
        help='List available AlQuran.cloud editions'
    )

    args = parser.parse_args()

    collector = MushafAPICollector()

    if args.list_editions:
        print("Fetching available editions from AlQuran.cloud...")
        editions = collector.alquran.get_available_editions()
        print(f"\nFound {len(editions)} editions:")
        for eid, info in list(editions.items())[:50]:
            print(f"  {eid}: {info.get('name')} ({info.get('language')})")
        if len(editions) > 50:
            print(f"  ... and {len(editions) - 50} more")
        return

    if args.stats:
        collector.get_stats()
        return

    if args.source == 'kfgqpc':
        collector.collect_kfgqpc_data(args.qiraat)
    elif args.source == 'alquran':
        collector.collect_alquran_cloud_data()
    else:
        collector.run_full_collection()

    if args.export:
        collector.export_collected_data()


if __name__ == "__main__":
    main()
