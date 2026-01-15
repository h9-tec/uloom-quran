#!/usr/bin/env python3
"""
Comprehensive Import Script for All Qiraat Text Data

This script imports qiraat text data from multiple sources into the database:
1. qiraat_collected/ - Pre-processed JSON files (8 riwayat)
2. quran-data-kfgqpc/ - KFGQPC XML files (8 riwayat)
3. QuranJSON/ - Text files (6 riwayat)

Database: uloom_quran.db
Table: qiraat_texts

Features:
- Reads from multiple data directories
- Parses JSON, XML, and text formats
- Maps to correct riwaya_id in riwayat table
- Handles duplicates gracefully (INSERT OR IGNORE / ON CONFLICT)
- Reports comprehensive coverage statistics after import
"""

import json
import sqlite3
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any


# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'uloom_quran.db')

# Data source directories
DATA_DIRS = {
    'qiraat_collected': os.path.join(BASE_DIR, 'data', 'raw', 'qiraat_collected'),
    'kfgqpc': os.path.join(BASE_DIR, 'data', 'raw', 'quran-data-kfgqpc'),
    'quranjson': os.path.join(BASE_DIR, 'data', 'raw', 'QuranJSON', 'data'),
}

# Riwaya code mappings for different sources
# Format: source_identifier -> riwaya_code in database
RIWAYA_MAPPINGS = {
    # qiraat_collected JSON files (filename without _collected.json)
    'collected': {
        'hafs': 'hafs',
        'warsh': 'warsh',
        'qaloon': 'qaloon',
        'shouba': 'shouba',
        'doori': 'doori',
        'soosi': 'soosi',
        'bazzi': 'bazzi',
        'qumbul': 'qumbul',
    },
    # KFGQPC XML files
    'kfgqpc': {
        'hafs': ('hafs/data/hafsData_v18.xml', 'hafs'),
        'hafs-smart': ('hafs-smart/data/hafs_smart_v8.xml', 'hafs_smart'),
        'warsh': ('warsh/data/warshData_v10.xml', 'warsh'),
        'qaloon': ('qaloon/data/QaloonData_v10.xml', 'qaloon'),
        'shouba': ('shouba/data/ShoubaData08.xml', 'shouba'),
        'doori': ('doori/data/DooriData_v09.xml', 'doori'),
        'soosi': ('soosi/data/SoosiData09.xml', 'soosi'),
        'bazzi': ('bazzi/data/BazziData_v07.xml', 'bazzi'),
        'qumbul': ('qumbul/data/QumbulData_v07.xml', 'qumbul'),
    },
    # QuranJSON text files
    'quranjson': {
        'Hafs.txt': 'hafs',
        'Warsh.txt': 'warsh',
        'Qaloun.txt': 'qaloon',
        'Shuba.txt': 'shouba',
        'Douri.txt': 'doori',
        'Sousi.txt': 'soosi',
    },
}

# Total verses in Quran (expected count)
TOTAL_QURAN_VERSES = 6236  # Most common count (can vary by qiraa)


class QiraatImporter:
    """Main class for importing qiraat texts from various sources."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.stats = defaultdict(lambda: {
            'inserted': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'total_processed': 0
        })
        self.riwaya_cache = {}  # Cache riwaya_id lookups

    def connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._load_riwaya_cache()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def _load_riwaya_cache(self):
        """Cache all riwaya codes to IDs."""
        self.cursor.execute("SELECT id, code FROM riwayat")
        for row in self.cursor.fetchall():
            self.riwaya_cache[row[1]] = row[0]
        print(f"Loaded {len(self.riwaya_cache)} riwayat into cache")

    def get_riwaya_id(self, code: str) -> Optional[int]:
        """Get riwaya_id from code, creating if needed."""
        if code in self.riwaya_cache:
            return self.riwaya_cache[code]
        return None

    def ensure_riwaya_exists(self, code: str, name_ar: str, name_en: str, source: str) -> int:
        """Ensure a riwaya exists in the database, create if not."""
        if code in self.riwaya_cache:
            return self.riwaya_cache[code]

        self.cursor.execute("""
            INSERT OR IGNORE INTO riwayat (code, name_arabic, name_english, source)
            VALUES (?, ?, ?, ?)
        """, (code, name_ar, name_en, source))
        self.conn.commit()

        self.cursor.execute("SELECT id FROM riwayat WHERE code = ?", (code,))
        row = self.cursor.fetchone()
        if row:
            self.riwaya_cache[code] = row[0]
            return row[0]
        return None

    def insert_verse(self, riwaya_id: int, surah_id: int, ayah_number: int,
                     text_uthmani: str, text_simple: Optional[str] = None,
                     juz: Optional[int] = None, page: Optional[int] = None,
                     source: str = 'unknown') -> str:
        """
        Insert a verse into qiraat_texts table.
        Returns: 'inserted', 'updated', 'skipped', or 'error'
        """
        try:
            # Clean the text
            text_uthmani = text_uthmani.strip() if text_uthmani else ''
            if not text_uthmani:
                return 'skipped'

            # Try insert first (most common case)
            self.cursor.execute("""
                INSERT INTO qiraat_texts
                (riwaya_id, surah_id, ayah_number, text_uthmani, text_simple, juz, page, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(riwaya_id, surah_id, ayah_number) DO UPDATE SET
                    text_uthmani = CASE
                        WHEN excluded.text_uthmani != '' AND length(excluded.text_uthmani) > length(text_uthmani)
                        THEN excluded.text_uthmani
                        ELSE text_uthmani
                    END,
                    text_simple = COALESCE(excluded.text_simple, text_simple),
                    juz = COALESCE(excluded.juz, juz),
                    page = COALESCE(excluded.page, page),
                    source = COALESCE(excluded.source, source)
            """, (riwaya_id, surah_id, ayah_number, text_uthmani, text_simple, juz, page, source))

            if self.cursor.rowcount > 0:
                return 'inserted'
            return 'skipped'

        except sqlite3.IntegrityError:
            return 'skipped'
        except Exception as e:
            print(f"    Error inserting {surah_id}:{ayah_number}: {e}")
            return 'error'

    # =========================================================================
    # JSON Parsing (qiraat_collected)
    # =========================================================================

    def import_from_collected_json(self):
        """Import from qiraat_collected JSON files."""
        print("\n" + "=" * 70)
        print("IMPORTING FROM: qiraat_collected (JSON)")
        print("=" * 70)

        data_dir = DATA_DIRS['qiraat_collected']
        if not os.path.exists(data_dir):
            print(f"  Directory not found: {data_dir}")
            return

        for filename, riwaya_code in RIWAYA_MAPPINGS['collected'].items():
            json_path = os.path.join(data_dir, f"{filename}_collected.json")
            if not os.path.exists(json_path):
                print(f"  File not found: {json_path}")
                continue

            riwaya_id = self.get_riwaya_id(riwaya_code)
            if not riwaya_id:
                print(f"  Riwaya not found in database: {riwaya_code}")
                continue

            print(f"\n  Processing {filename} -> {riwaya_code} (id={riwaya_id})...")

            with open(json_path, 'r', encoding='utf-8') as f:
                verses = json.load(f)

            source_name = f"collected_{filename}"
            for verse in verses:
                result = self.insert_verse(
                    riwaya_id=riwaya_id,
                    surah_id=verse.get('surah'),
                    ayah_number=verse.get('ayah'),
                    text_uthmani=verse.get('text', ''),
                    text_simple=verse.get('text_simple'),
                    juz=verse.get('juz'),
                    page=verse.get('page'),
                    source=verse.get('source', 'qiraat_collected')
                )
                self.stats[source_name][result] += 1
                self.stats[source_name]['total_processed'] += 1

            self.conn.commit()
            stats = self.stats[source_name]
            print(f"    Processed: {stats['total_processed']}, "
                  f"Inserted: {stats['inserted']}, "
                  f"Skipped: {stats['skipped']}")

    # =========================================================================
    # XML Parsing (KFGQPC)
    # =========================================================================

    def _safe_int(self, value: str, default: Optional[int] = None) -> Optional[int]:
        """Safely convert string to int, handling ranges like '85-86'."""
        if not value:
            return default
        # Handle range values like "85-86" by taking the first number
        if '-' in value:
            value = value.split('-')[0]
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def parse_kfgqpc_xml(self, xml_path: str) -> List[Dict[str, Any]]:
        """Parse KFGQPC XML file format."""
        verses = []
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            for row in root.findall('.//ROW'):
                verse = {
                    'surah': None,
                    'ayah': None,
                    'text': '',
                    'text_simple': None,
                    'juz': None,
                    'page': None,
                }

                # Extract fields (handle different field names)
                sora_el = row.find('sora')
                if sora_el is None:
                    sora_el = row.find('sura_no')
                if sora_el is not None and sora_el.text:
                    verse['surah'] = self._safe_int(sora_el.text)

                ayah_el = row.find('aya_no')
                if ayah_el is not None and ayah_el.text:
                    verse['ayah'] = self._safe_int(ayah_el.text)

                text_el = row.find('aya_text')
                if text_el is not None and text_el.text:
                    verse['text'] = text_el.text

                simple_el = row.find('aya_text_emlaey')
                if simple_el is not None and simple_el.text:
                    verse['text_simple'] = simple_el.text

                juz_el = row.find('jozz')
                if juz_el is not None and juz_el.text:
                    verse['juz'] = self._safe_int(juz_el.text)

                page_el = row.find('page')
                if page_el is not None and page_el.text:
                    verse['page'] = self._safe_int(page_el.text)

                if verse['surah'] and verse['ayah']:
                    verses.append(verse)

        except ET.ParseError as e:
            print(f"    XML parse error: {e}")
        except Exception as e:
            print(f"    Error parsing XML: {e}")

        return verses

    def import_from_kfgqpc_xml(self):
        """Import from KFGQPC XML files."""
        print("\n" + "=" * 70)
        print("IMPORTING FROM: quran-data-kfgqpc (XML)")
        print("=" * 70)

        data_dir = DATA_DIRS['kfgqpc']
        if not os.path.exists(data_dir):
            print(f"  Directory not found: {data_dir}")
            return

        for name, (xml_file, riwaya_code) in RIWAYA_MAPPINGS['kfgqpc'].items():
            xml_path = os.path.join(data_dir, xml_file)
            if not os.path.exists(xml_path):
                print(f"  File not found: {xml_path}")
                continue

            riwaya_id = self.get_riwaya_id(riwaya_code)
            if not riwaya_id:
                print(f"  Riwaya not found in database: {riwaya_code}")
                continue

            print(f"\n  Processing {name} -> {riwaya_code} (id={riwaya_id})...")

            verses = self.parse_kfgqpc_xml(xml_path)
            source_name = f"kfgqpc_{name}"

            for verse in verses:
                result = self.insert_verse(
                    riwaya_id=riwaya_id,
                    surah_id=verse['surah'],
                    ayah_number=verse['ayah'],
                    text_uthmani=verse['text'],
                    text_simple=verse.get('text_simple'),
                    juz=verse.get('juz'),
                    page=verse.get('page'),
                    source='KFGQPC'
                )
                self.stats[source_name][result] += 1
                self.stats[source_name]['total_processed'] += 1

            self.conn.commit()
            stats = self.stats[source_name]
            print(f"    Processed: {stats['total_processed']}, "
                  f"Inserted: {stats['inserted']}, "
                  f"Skipped: {stats['skipped']}")

    # =========================================================================
    # Text Parsing (QuranJSON)
    # =========================================================================

    def arabic_to_int(self, arabic_str: str) -> int:
        """Convert Arabic numerals to integer."""
        arabic_numerals = '\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669'
        result = 0
        for char in arabic_str:
            if char in arabic_numerals:
                result = result * 10 + arabic_numerals.index(char)
        return result

    def parse_quranjson_text(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse QuranJSON text file format.

        Format:
        - Surah headers start with "surah_name"
        - Verses contain Arabic text with verse number markers (Arabic numerals)
        """
        verses = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            current_surah = 0
            surah_content = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check for surah header (various patterns)
                if line.startswith('\u0633\u064f\u0648\u0631\u064e\u0629\u064f'):  # surah_name
                    if current_surah > 0 and surah_content:
                        verses.extend(self._extract_verses_from_text(
                            ' '.join(surah_content), current_surah
                        ))
                    current_surah += 1
                    surah_content = []
                else:
                    surah_content.append(line)

            # Process last surah
            if current_surah > 0 and surah_content:
                verses.extend(self._extract_verses_from_text(
                    ' '.join(surah_content), current_surah
                ))

        except Exception as e:
            print(f"    Error parsing text file: {e}")

        return verses

    def _extract_verses_from_text(self, text: str, surah_no: int) -> List[Dict[str, Any]]:
        """Extract individual verses from concatenated text."""
        verses = []

        # Pattern: text followed by Arabic numerals
        pattern = r'([^\u0660-\u0669]+)([\u0660-\u0669]+)'
        matches = re.findall(pattern, text)

        for verse_text, verse_num_ar in matches:
            ayah_no = self.arabic_to_int(verse_num_ar)
            if ayah_no > 0:
                verses.append({
                    'surah': surah_no,
                    'ayah': ayah_no,
                    'text': verse_text.strip()
                })

        return verses

    def import_from_quranjson_text(self):
        """Import from QuranJSON text files."""
        print("\n" + "=" * 70)
        print("IMPORTING FROM: QuranJSON (Text)")
        print("=" * 70)

        data_dir = DATA_DIRS['quranjson']
        if not os.path.exists(data_dir):
            print(f"  Directory not found: {data_dir}")
            return

        for filename, riwaya_code in RIWAYA_MAPPINGS['quranjson'].items():
            text_path = os.path.join(data_dir, filename)
            if not os.path.exists(text_path):
                print(f"  File not found: {text_path}")
                continue

            riwaya_id = self.get_riwaya_id(riwaya_code)
            if not riwaya_id:
                print(f"  Riwaya not found in database: {riwaya_code}")
                continue

            print(f"\n  Processing {filename} -> {riwaya_code} (id={riwaya_id})...")

            verses = self.parse_quranjson_text(text_path)
            source_name = f"quranjson_{filename}"

            for verse in verses:
                result = self.insert_verse(
                    riwaya_id=riwaya_id,
                    surah_id=verse['surah'],
                    ayah_number=verse['ayah'],
                    text_uthmani=verse['text'],
                    source='QuranJSON'
                )
                self.stats[source_name][result] += 1
                self.stats[source_name]['total_processed'] += 1

            self.conn.commit()
            stats = self.stats[source_name]
            print(f"    Processed: {stats['total_processed']}, "
                  f"Inserted: {stats['inserted']}, "
                  f"Skipped: {stats['skipped']}")

    # =========================================================================
    # KFGQPC JSON Files (Alternative format)
    # =========================================================================

    def import_from_kfgqpc_json(self):
        """Import from KFGQPC JSON files (if XML conversion exists)."""
        print("\n" + "=" * 70)
        print("IMPORTING FROM: quran-data-kfgqpc (JSON)")
        print("=" * 70)

        data_dir = DATA_DIRS['kfgqpc']
        if not os.path.exists(data_dir):
            print(f"  Directory not found: {data_dir}")
            return

        # Check for JSON versions of the files
        json_mappings = {
            'hafs': 'hafs/data/hafsData_v18.json',
            'warsh': 'warsh/data/warshData_v10.json',
            'qaloon': 'qaloon/data/QaloonData_v10.json',
            'shouba': 'shouba/data/ShoubaData08.json',
            'doori': 'doori/data/DooriData_v09.json',
            'soosi': 'soosi/data/SoosiData09.json',
            'bazzi': 'bazzi/data/BazziData_v07.json',
            'qumbul': 'qumbul/data/QumbulData_v07.json',
        }

        for riwaya_code, json_file in json_mappings.items():
            json_path = os.path.join(data_dir, json_file)
            if not os.path.exists(json_path):
                continue  # Skip if JSON doesn't exist

            riwaya_id = self.get_riwaya_id(riwaya_code)
            if not riwaya_id:
                print(f"  Riwaya not found in database: {riwaya_code}")
                continue

            print(f"\n  Processing {riwaya_code} from JSON (id={riwaya_id})...")

            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                print(f"    Invalid JSON: {json_path}")
                continue

            source_name = f"kfgqpc_json_{riwaya_code}"

            for verse in data:
                surah_id = verse.get('sora') or verse.get('sura_no')
                ayah_no = verse.get('aya_no')

                if not surah_id or not ayah_no:
                    continue

                result = self.insert_verse(
                    riwaya_id=riwaya_id,
                    surah_id=surah_id,
                    ayah_number=ayah_no,
                    text_uthmani=verse.get('aya_text', ''),
                    text_simple=verse.get('aya_text_emlaey'),
                    juz=verse.get('jozz'),
                    page=verse.get('page'),
                    source='KFGQPC'
                )
                self.stats[source_name][result] += 1
                self.stats[source_name]['total_processed'] += 1

            self.conn.commit()
            stats = self.stats[source_name]
            print(f"    Processed: {stats['total_processed']}, "
                  f"Inserted: {stats['inserted']}, "
                  f"Skipped: {stats['skipped']}")

    # =========================================================================
    # Statistics and Reporting
    # =========================================================================

    def print_coverage_statistics(self):
        """Print comprehensive coverage statistics."""
        print("\n" + "=" * 70)
        print("COVERAGE STATISTICS")
        print("=" * 70)

        # Overall statistics
        print("\n--- Import Summary by Source ---")
        total_inserted = 0
        total_skipped = 0
        total_errors = 0

        for source, stats in sorted(self.stats.items()):
            if stats['total_processed'] > 0:
                print(f"  {source}:")
                print(f"    Processed: {stats['total_processed']:,}")
                print(f"    Inserted:  {stats['inserted']:,}")
                print(f"    Skipped:   {stats['skipped']:,}")
                print(f"    Errors:    {stats['errors']:,}")
                total_inserted += stats['inserted']
                total_skipped += stats['skipped']
                total_errors += stats['errors']

        print(f"\n  TOTAL:")
        print(f"    Inserted: {total_inserted:,}")
        print(f"    Skipped:  {total_skipped:,}")
        print(f"    Errors:   {total_errors:,}")

        # Database statistics
        print("\n--- Database Coverage ---")

        self.cursor.execute("""
            SELECT r.code, r.name_arabic, r.name_english, COUNT(qt.id) as verse_count
            FROM riwayat r
            LEFT JOIN qiraat_texts qt ON qt.riwaya_id = r.id
            GROUP BY r.id
            ORDER BY verse_count DESC, r.code
        """)

        print(f"\n  {'Riwaya Code':<20} {'Arabic Name':<30} {'Verses':>10} {'Coverage':>10}")
        print(f"  {'-'*20} {'-'*30} {'-'*10} {'-'*10}")

        total_verses = 0
        riwaya_with_data = 0

        for row in self.cursor.fetchall():
            code, name_ar, name_en, count = row
            coverage = f"{(count / TOTAL_QURAN_VERSES * 100):.1f}%" if count > 0 else "0%"
            print(f"  {code:<20} {name_ar:<30} {count:>10,} {coverage:>10}")
            total_verses += count
            if count > 0:
                riwaya_with_data += 1

        self.cursor.execute("SELECT COUNT(*) FROM riwayat")
        total_riwayat = self.cursor.fetchone()[0]

        print(f"\n  Summary:")
        print(f"    Total riwayat in database: {total_riwayat}")
        print(f"    Riwayat with text data:    {riwaya_with_data}")
        print(f"    Total verse entries:       {total_verses:,}")

        # Surah coverage
        print("\n--- Surah Coverage (across all riwayat) ---")

        self.cursor.execute("""
            SELECT surah_id, COUNT(DISTINCT riwaya_id) as riwaya_count, COUNT(*) as total_entries
            FROM qiraat_texts
            GROUP BY surah_id
            ORDER BY surah_id
        """)

        surah_data = self.cursor.fetchall()
        full_coverage = 0
        partial_coverage = 0

        for surah_id, riwaya_count, total in surah_data:
            if riwaya_count >= riwaya_with_data:
                full_coverage += 1
            else:
                partial_coverage += 1

        print(f"  Surahs with full coverage:    {full_coverage} / 114")
        print(f"  Surahs with partial coverage: {partial_coverage}")

        # Source distribution
        print("\n--- Source Distribution ---")

        self.cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM qiraat_texts
            WHERE source IS NOT NULL
            GROUP BY source
            ORDER BY count DESC
        """)

        for row in self.cursor.fetchall():
            source, count = row
            print(f"  {source or 'Unknown':<30}: {count:>10,} verses")

        print("\n" + "=" * 70)

    def run_all_imports(self):
        """Run all import methods."""
        print("=" * 70)
        print("COMPREHENSIVE QIRAAT TEXT IMPORT")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        self.connect()

        try:
            # Import from all sources
            self.import_from_collected_json()
            self.import_from_kfgqpc_xml()
            self.import_from_kfgqpc_json()
            self.import_from_quranjson_text()

            # Print statistics
            self.print_coverage_statistics()

        finally:
            self.close()

        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)


def main():
    """Main entry point."""
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        print("Please run init_database.py first to create the database.")
        return 1

    # Create importer and run
    importer = QiraatImporter(DB_PATH)
    importer.run_all_imports()

    return 0


if __name__ == "__main__":
    exit(main())
