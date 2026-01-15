#!/usr/bin/env python3
"""
King Fahd Quran Complex (KFGQPC) Scraper and Data Importer
Scrapes and imports القراءات العشر (Ten Readings) data from official Saudi sources.

Sources:
1. Local KFGQPC data files (from github.com/thetruetruth/quran-data-kfgqpc)
2. qurancomplex.gov.sa - Official King Fahd Complex website
3. fonts.qurancomplex.gov.sa - Font and text resources

Data includes:
- Complete Quran text in 8+ riwayat (narrations)
- الفرش والأصول (specific word variants vs general rules)
- Verse-by-verse differences between readings
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import time
import os
import re
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "raw" / "quran-data-kfgqpc"
DB_PATH = BASE_DIR / "db" / "uloom_quran.db"
EXPORT_DIR = BASE_DIR / "data" / "processed" / "qurancomplex"

# URLs for web scraping
QURANCOMPLEX_BASE = "https://qurancomplex.gov.sa"
FONTS_BASE = "https://fonts.qurancomplex.gov.sa"
TECHQURAN_BASE = "https://qurancomplex.gov.sa/en/techquran/dev/"

# HTTP Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
}

# Riwayat (Narrations) Configuration - mapping to database qari/rawi IDs
RIWAYAT_CONFIG = {
    'hafs': {
        'json_file': 'hafs/data/hafsData_v18.json',
        'qari_id': 5,  # عاصم
        'rawi_id': 10,  # حفص
        'name_ar': 'حفص عن عاصم',
        'name_en': 'Hafs from Asim',
        'description': 'Most widely used narration globally',
        'regions': ['Asia', 'Middle East', 'Most Muslim countries'],
    },
    'hafs-smart': {
        'json_file': 'hafs-smart/data/hafs_smart_v8.json',
        'qari_id': 5,
        'rawi_id': 10,
        'name_ar': 'حفص عن عاصم (للأجهزة الذكية)',
        'name_en': 'Hafs from Asim (Smart)',
        'description': 'Optimized for smart devices',
        'is_smart_version': True,
    },
    'warsh': {
        'json_file': 'warsh/data/warshData_v10.json',
        'qari_id': 1,  # نافع
        'rawi_id': 2,  # ورش
        'name_ar': 'ورش عن نافع',
        'name_en': 'Warsh from Nafi',
        'description': 'Used in Maghreb, West/Central Africa, France, Spain',
        'regions': ['Morocco', 'Algeria', 'Tunisia', 'Libya', 'West Africa', 'Central Africa'],
    },
    'qaloon': {
        'json_file': 'qaloon/data/QaloonData_v10.json',
        'qari_id': 1,  # نافع
        'rawi_id': 1,  # قالون
        'name_ar': 'قالون عن نافع',
        'name_en': 'Qalun from Nafi',
        'description': 'Used in Libya, Tunisia, parts of Mauritania',
        'regions': ['Libya', 'Tunisia', 'Mauritania'],
    },
    'shouba': {
        'json_file': 'shouba/data/ShoubaData08.json',
        'qari_id': 5,  # عاصم
        'rawi_id': 9,  # شعبة
        'name_ar': 'شعبة عن عاصم',
        'name_en': 'Shuba from Asim',
        'description': 'Classical narration for specialists',
    },
    'doori': {
        'json_file': 'doori/data/DooriData_v09.json',
        'qari_id': 3,  # أبو عمرو
        'rawi_id': 5,  # الدوري
        'name_ar': 'الدوري عن أبي عمرو',
        'name_en': 'Al-Duri from Abu Amr',
        'description': 'Used in Sudan and East Africa',
        'regions': ['Sudan', 'East Africa'],
    },
    'soosi': {
        'json_file': 'soosi/data/SoosiData09.json',
        'qari_id': 3,  # أبو عمرو
        'rawi_id': 6,  # السوسي
        'name_ar': 'السوسي عن أبي عمرو',
        'name_en': 'Al-Susi from Abu Amr',
        'description': 'Classical narration for specialists',
    },
    'bazzi': {
        'json_file': 'bazzi/data/BazziData_v07.json',
        'qari_id': 2,  # ابن كثير
        'rawi_id': 3,  # البزي
        'name_ar': 'البزي عن ابن كثير',
        'name_en': 'Al-Bazzi from Ibn Kathir',
        'description': 'Classical narration for specialists',
    },
    'qumbul': {
        'json_file': 'qumbul/data/QumbulData_v07.json',
        'qari_id': 2,  # ابن كثير
        'rawi_id': 4,  # قنبل
        'name_ar': 'قنبل عن ابن كثير',
        'name_en': 'Qunbul from Ibn Kathir',
        'description': 'Classical narration for specialists',
    },
}

# Verse counts per surah
SURAH_VERSE_COUNT = {
    1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109,
    11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135,
    21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60,
    31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85,
    41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45,
    51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13,
    61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44,
    71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42,
    81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20,
    91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11,
    101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3,
    111: 5, 112: 4, 113: 5, 114: 6
}


def remove_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel) from text for comparison"""
    if not text:
        return ""
    diacritics = (
        '\u064B', '\u064C', '\u064D', '\u064E', '\u064F', '\u0650',
        '\u0651', '\u0652', '\u0653', '\u0654', '\u0655', '\u0656',
        '\u0657', '\u0658', '\u0659', '\u065A', '\u065B', '\u065C',
        '\u065D', '\u065E', '\u065F', '\u0670', '\u06D6', '\u06D7',
        '\u06D8', '\u06D9', '\u06DA', '\u06DB', '\u06DC', '\u06DD',
        '\u06DE', '\u06DF', '\u06E0', '\u06E1', '\u06E2', '\u06E3',
        '\u06E4', '\u06E5', '\u06E6', '\u06E7', '\u06E8', '\u06EA',
        '\u06EB', '\u06EC', '\u06ED'
    )
    return ''.join(c for c in text if c not in diacritics)


def remove_verse_number(text: str) -> str:
    """Remove verse number marker from end of ayah text"""
    # Remove verse number patterns like "١", "١٢٣", etc. at the end
    return re.sub(r'\s*[\u0660-\u0669]+\s*$', '', text).strip()


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for comparison"""
    if not text:
        return ""
    # Remove verse numbers
    text = remove_verse_number(text)
    # Normalize alef variants
    text = re.sub(r'[إأآا]', 'ا', text)
    # Normalize teh marbuta
    text = re.sub(r'ة', 'ه', text)
    # Normalize ya
    text = re.sub(r'ى', 'ي', text)
    # Remove tatweel (kashida)
    text = re.sub(r'ـ', '', text)
    return text


@dataclass
class RiwayaVerse:
    """Represents a verse in a specific riwaya"""
    riwaya: str
    surah: int
    ayah: int
    text: str
    text_simple: Optional[str] = None
    juz: Optional[int] = None
    page: Optional[int] = None


@dataclass
class QiraatDifference:
    """Represents a difference between readings"""
    surah: int
    ayah: int
    word_text: str
    word_position: Optional[int]
    variant_type: str  # 'أصول' or 'فرش'
    readings: Dict[str, str]  # riwaya_name -> reading_text
    category: Optional[str] = None
    notes: Optional[str] = None


class QuranComplexScraper:
    """Scraper and importer for King Fahd Quran Complex data"""

    def __init__(self, db_path: Path = DB_PATH, data_dir: Path = DATA_DIR):
        self.db_path = db_path
        self.data_dir = data_dir
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.conn = None
        self.cursor = None

    def connect_db(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")
        logger.info(f"Connected to database: {self.db_path}")

    def close_db(self):
        """Close database connection"""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            logger.info("Database connection closed")

    def setup_database(self):
        """Setup/verify database tables for KFGQPC data - uses existing schema"""
        logger.info("Setting up database tables for KFGQPC data...")

        # The database already has these tables from schema.sql:
        # - riwayat (code, name_arabic, name_english, qari_id, description)
        # - qiraat_texts (riwaya_id, surah_id, ayah_number, text_uthmani, text_simple, juz, page)
        # - qiraat_differences (surah_id, ayah_number, word_position, word_text, difference_type, description)
        # - qiraat_difference_readings (difference_id, riwaya_id, reading_text)

        # Ensure riwayat entries exist for all our riwayat
        for riwaya_code, config in RIWAYAT_CONFIG.items():
            self.cursor.execute(
                "SELECT id FROM riwayat WHERE code = ?",
                (riwaya_code,)
            )
            if not self.cursor.fetchone():
                self.cursor.execute("""
                    INSERT INTO riwayat (code, name_arabic, name_english, qari_id, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    riwaya_code,
                    config['name_ar'],
                    config['name_en'],
                    config['qari_id'],
                    config.get('description', '')
                ))

        # Create qiraat_difference_readings table if not exists
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS qiraat_difference_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                difference_id INTEGER NOT NULL,
                riwaya_id INTEGER NOT NULL,
                reading_text TEXT NOT NULL,
                is_default INTEGER DEFAULT 0,
                FOREIGN KEY (difference_id) REFERENCES qiraat_differences(id),
                FOREIGN KEY (riwaya_id) REFERENCES riwayat(id)
            )
        """)

        # Create indexes if not exist
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_texts_riwaya ON qiraat_texts(riwaya_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_texts_surah ON qiraat_texts(surah_id, ayah_number)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_diff_surah ON qiraat_differences(surah_id, ayah_number)")

        self.conn.commit()
        logger.info("Database tables verified/created successfully")

    def get_verse_id(self, surah: int, ayah: int) -> Optional[int]:
        """Get verse ID from database"""
        verse_key = f"{surah}:{ayah}"
        self.cursor.execute("SELECT id FROM verses WHERE verse_key = ?", (verse_key,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def load_riwaya_json(self, riwaya_code: str) -> List[Dict]:
        """Load JSON data for a specific riwaya"""
        config = RIWAYAT_CONFIG.get(riwaya_code)
        if not config:
            logger.error(f"Unknown riwaya code: {riwaya_code}")
            return []

        json_path = self.data_dir / config['json_file']
        if not json_path.exists():
            logger.warning(f"JSON file not found: {json_path}")
            return []

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} verses for {riwaya_code}")
            return data
        except Exception as e:
            logger.error(f"Error loading {json_path}: {e}")
            return []

    def get_riwaya_id(self, riwaya_code: str) -> Optional[int]:
        """Get riwaya ID from database"""
        self.cursor.execute("SELECT id FROM riwayat WHERE code = ?", (riwaya_code,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def import_riwaya(self, riwaya_code: str) -> int:
        """Import a single riwaya's data into the database"""
        config = RIWAYAT_CONFIG.get(riwaya_code)
        if not config:
            return 0

        data = self.load_riwaya_json(riwaya_code)
        if not data:
            return 0

        logger.info(f"Importing {riwaya_code} ({config['name_ar']})...")

        # Get riwaya_id
        riwaya_id = self.get_riwaya_id(riwaya_code)
        if not riwaya_id:
            logger.error(f"Riwaya not found in database: {riwaya_code}")
            return 0

        imported = 0

        for verse_data in data:
            # Handle different JSON key formats
            surah = verse_data.get('sora') or verse_data.get('sura_no')
            ayah = verse_data.get('aya_no')
            text = verse_data.get('aya_text', '')
            text_simple = verse_data.get('aya_text_emlaey', '')
            juz = verse_data.get('jozz')
            page = verse_data.get('page')

            if not surah or not ayah or not text:
                continue

            # Convert page to int if string
            if isinstance(page, str):
                try:
                    page = int(page)
                except ValueError:
                    page = None

            # Insert into qiraat_texts table (existing schema)
            try:
                self.cursor.execute("""
                    INSERT OR REPLACE INTO qiraat_texts
                    (riwaya_id, surah_id, ayah_number, text_uthmani, text_simple, juz, page)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (riwaya_id, surah, ayah, text, text_simple, juz, page))

                imported += 1
            except Exception as e:
                logger.warning(f"Error importing {riwaya_code} {surah}:{ayah}: {e}")

        self.conn.commit()
        logger.info(f"Imported {imported} verses for {riwaya_code}")
        return imported

    def import_all_riwayat(self) -> Dict[str, int]:
        """Import all available riwayat"""
        results = {}
        for riwaya_code in RIWAYAT_CONFIG.keys():
            count = self.import_riwaya(riwaya_code)
            results[riwaya_code] = count
        return results

    def compare_riwayat(self, riwaya1: str, riwaya2: str, surah: int = None) -> List[QiraatDifference]:
        """Compare two riwayat and find differences"""
        differences = []

        # Get riwaya IDs
        riwaya1_id = self.get_riwaya_id(riwaya1)
        riwaya2_id = self.get_riwaya_id(riwaya2)

        if not riwaya1_id or not riwaya2_id:
            logger.error(f"Could not find riwaya IDs for {riwaya1} or {riwaya2}")
            return differences

        # Build query using qiraat_texts table
        query = """
            SELECT qt1.surah_id, qt1.ayah_number, qt1.text_uthmani as text1, qt2.text_uthmani as text2
            FROM qiraat_texts qt1
            JOIN qiraat_texts qt2 ON qt1.surah_id = qt2.surah_id AND qt1.ayah_number = qt2.ayah_number
            WHERE qt1.riwaya_id = ? AND qt2.riwaya_id = ?
        """
        params = [riwaya1_id, riwaya2_id]

        if surah:
            query += " AND qt1.surah_id = ?"
            params.append(surah)

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        for row in rows:
            surah_id, ayah_num, text1, text2 = row

            # Remove verse numbers for comparison
            clean1 = remove_verse_number(text1)
            clean2 = remove_verse_number(text2)

            if clean1 != clean2:
                # Find the specific word differences
                words1 = clean1.split()
                words2 = clean2.split()

                for i, (w1, w2) in enumerate(zip(words1, words2)):
                    if w1 != w2:
                        diff = QiraatDifference(
                            surah=surah_id,
                            ayah=ayah_num,
                            word_text=w1,
                            word_position=i + 1,
                            variant_type='فرش',
                            readings={riwaya1: w1, riwaya2: w2}
                        )
                        differences.append(diff)

        return differences

    def find_all_differences(self) -> List[QiraatDifference]:
        """Find all differences across all loaded riwayat using Hafs as baseline"""
        all_differences = []
        baseline = 'hafs'

        other_riwayat = [r for r in RIWAYAT_CONFIG.keys() if r != baseline and r != 'hafs-smart']

        for riwaya in other_riwayat:
            logger.info(f"Comparing {baseline} with {riwaya}...")
            diffs = self.compare_riwayat(baseline, riwaya)
            all_differences.extend(diffs)
            logger.info(f"  Found {len(diffs)} differences")

        return all_differences

    def store_differences(self, differences: List[QiraatDifference]) -> int:
        """Store found differences in the database"""
        stored = 0

        for diff in differences:
            try:
                # Insert the difference using existing schema
                self.cursor.execute("""
                    INSERT INTO qiraat_differences
                    (surah_id, ayah_number, word_position, word_text, difference_type, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    diff.surah, diff.ayah, diff.word_position,
                    diff.word_text, diff.variant_type, diff.notes
                ))
                diff_id = self.cursor.lastrowid

                # Insert readings for each riwaya
                for riwaya_code, reading_text in diff.readings.items():
                    riwaya_id = self.get_riwaya_id(riwaya_code)
                    is_default = 1 if riwaya_code == 'hafs' else 0

                    if riwaya_id:
                        self.cursor.execute("""
                            INSERT INTO qiraat_difference_readings
                            (difference_id, riwaya_id, reading_text, is_default)
                            VALUES (?, ?, ?, ?)
                        """, (diff_id, riwaya_id, reading_text, is_default))

                stored += 1
            except Exception as e:
                logger.warning(f"Error storing difference {diff.surah}:{diff.ayah}: {e}")

        self.conn.commit()
        logger.info(f"Stored {stored} differences")
        return stored

    def scrape_qurancomplex_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page from qurancomplex.gov.sa"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.warning(f"Error fetching {url}: {e}")
            return None

    def scrape_ten_qiraat_info(self) -> List[Dict]:
        """Scrape information about the ten readings from qurancomplex.gov.sa"""
        url = f"{QURANCOMPLEX_BASE}/category/ten-qiraat/"
        soup = self.scrape_qurancomplex_page(url)

        if not soup:
            return []

        qiraat_info = []

        # Find articles about each qiraat
        articles = soup.find_all('article')
        for article in articles:
            title_elem = article.find(['h2', 'h3', 'h4'])
            if title_elem:
                title = title_elem.get_text(strip=True)

                # Get link
                link_elem = title_elem.find('a')
                link = link_elem.get('href') if link_elem else None

                # Get excerpt/description
                excerpt_elem = article.find(['p', 'div'], class_=['excerpt', 'entry-content', 'content'])
                excerpt = excerpt_elem.get_text(strip=True) if excerpt_elem else ""

                qiraat_info.append({
                    'title': title,
                    'link': link,
                    'description': excerpt[:500] if excerpt else ""
                })

        return qiraat_info

    def scrape_fonts_resources(self) -> Dict:
        """Scrape available font/text resources from fonts.qurancomplex.gov.sa"""
        url = f"{FONTS_BASE}/en/ten-readings/"
        soup = self.scrape_qurancomplex_page(url)

        if not soup:
            return {}

        resources = {
            'fonts': [],
            'downloads': [],
            'info': []
        }

        # Find download links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            if '.ttf' in href or '.woff' in href or '.otf' in href:
                resources['fonts'].append({'name': text, 'url': href})
            elif '.zip' in href or '.pdf' in href:
                resources['downloads'].append({'name': text, 'url': href})

        return resources

    def export_differences_json(self, output_path: Path = None) -> str:
        """Export all differences to JSON file"""
        if not output_path:
            output_path = EXPORT_DIR / "qiraat_differences.json"

        os.makedirs(output_path.parent, exist_ok=True)

        self.cursor.execute("""
            SELECT qd.id, qd.surah_id, qd.ayah_number, qd.word_text, qd.word_position,
                   qd.difference_type, qd.description
            FROM qiraat_differences qd
            ORDER BY qd.surah_id, qd.ayah_number, qd.word_position
        """)

        differences = []
        for row in self.cursor.fetchall():
            diff_id, surah_id, ayah_num, word_text, word_pos, diff_type, description = row
            verse_key = f"{surah_id}:{ayah_num}"

            # Get readings for this difference
            self.cursor.execute("""
                SELECT r.name_arabic, qdr.reading_text, qdr.is_default
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
            """, (diff_id,))

            readings = {}
            for qr_row in self.cursor.fetchall():
                riwaya_name, reading, is_default = qr_row
                readings[riwaya_name] = {
                    'text': reading,
                    'is_default': bool(is_default)
                }

            differences.append({
                'verse_key': verse_key,
                'word_text': word_text,
                'word_position': word_pos,
                'difference_type': diff_type,
                'description': description,
                'readings': readings
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'source': 'King Fahd Quran Complex (KFGQPC)',
                'url': 'https://qurancomplex.gov.sa',
                'count': len(differences),
                'differences': differences
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(differences)} differences to {output_path}")
        return str(output_path)

    def generate_statistics(self) -> Dict:
        """Generate statistics about imported qiraat data"""
        stats = {}

        # Count riwayat entries
        self.cursor.execute("SELECT code, name_arabic FROM riwayat")
        stats['riwayat_list'] = [{'code': row[0], 'name': row[1]} for row in self.cursor.fetchall()]

        # Count qiraat_texts entries per riwaya
        self.cursor.execute("""
            SELECT r.name_arabic, COUNT(qt.id)
            FROM qiraat_texts qt
            JOIN riwayat r ON qt.riwaya_id = r.id
            GROUP BY qt.riwaya_id
        """)
        stats['qiraat_texts'] = [
            {'riwaya': row[0], 'count': row[1]}
            for row in self.cursor.fetchall()
        ]

        # Count differences
        self.cursor.execute("SELECT COUNT(*) FROM qiraat_differences")
        stats['total_differences'] = self.cursor.fetchone()[0]

        # Differences by type
        self.cursor.execute("""
            SELECT difference_type, COUNT(*) FROM qiraat_differences
            GROUP BY difference_type
        """)
        stats['differences_by_type'] = dict(self.cursor.fetchall())

        # Surahs with most differences
        self.cursor.execute("""
            SELECT s.name_arabic, COUNT(qd.id) as diff_count
            FROM qiraat_differences qd
            JOIN surahs s ON qd.surah_id = s.id
            GROUP BY qd.surah_id
            ORDER BY diff_count DESC
            LIMIT 10
        """)
        stats['surahs_most_differences'] = [
            {'surah': row[0], 'count': row[1]}
            for row in self.cursor.fetchall()
        ]

        return stats

    def run_full_import(self):
        """Run complete import process"""
        logger.info("=" * 60)
        logger.info("King Fahd Quran Complex (KFGQPC) Data Import")
        logger.info("=" * 60)

        self.connect_db()
        self.setup_database()

        # Import all riwayat
        logger.info("\n--- Importing Riwayat Data ---")
        import_results = self.import_all_riwayat()

        for riwaya, count in import_results.items():
            logger.info(f"  {riwaya}: {count} verses")

        # Find and store differences
        logger.info("\n--- Finding Qiraat Differences ---")
        differences = self.find_all_differences()
        logger.info(f"Total differences found: {len(differences)}")

        if differences:
            stored = self.store_differences(differences)
            logger.info(f"Stored {stored} differences in database")

        # Export to JSON
        logger.info("\n--- Exporting Data ---")
        self.export_differences_json()

        # Generate statistics
        logger.info("\n--- Statistics ---")
        stats = self.generate_statistics()

        print("\n=== Import Summary ===")
        print(f"Riwayat imported: {len(import_results)}")
        for riwaya, count in import_results.items():
            config = RIWAYAT_CONFIG.get(riwaya, {})
            print(f"  - {config.get('name_ar', riwaya)}: {count} verses")

        print(f"\nTotal differences: {stats.get('total_differences', 0)}")
        print("\nDifferences by type:")
        for vtype, count in stats.get('differences_by_type', {}).items():
            print(f"  - {vtype or 'Unspecified'}: {count}")

        print("\nTop 5 surahs with most differences:")
        for item in stats.get('surahs_most_differences', [])[:5]:
            print(f"  - {item['surah']}: {item['count']} differences")

        self.close_db()
        logger.info("\n" + "=" * 60)
        logger.info("Import complete!")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Import and scrape Qiraat data from King Fahd Quran Complex'
    )
    parser.add_argument('--db', type=str, default=str(DB_PATH),
                        help='Database path')
    parser.add_argument('--data-dir', type=str, default=str(DATA_DIR),
                        help='KFGQPC data directory')
    parser.add_argument('--riwaya', type=str, choices=list(RIWAYAT_CONFIG.keys()),
                        help='Import specific riwaya only')
    parser.add_argument('--compare', nargs=2, metavar=('RIWAYA1', 'RIWAYA2'),
                        help='Compare two riwayat')
    parser.add_argument('--surah', type=int, help='Limit to specific surah')
    parser.add_argument('--export', action='store_true',
                        help='Export differences to JSON')
    parser.add_argument('--stats', action='store_true',
                        help='Show statistics only')
    parser.add_argument('--scrape-web', action='store_true',
                        help='Also scrape from qurancomplex.gov.sa website')

    args = parser.parse_args()

    scraper = QuranComplexScraper(
        db_path=Path(args.db),
        data_dir=Path(args.data_dir)
    )

    if args.stats:
        scraper.connect_db()
        stats = scraper.generate_statistics()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        scraper.close_db()

    elif args.compare:
        scraper.connect_db()
        scraper.setup_database()
        diffs = scraper.compare_riwayat(args.compare[0], args.compare[1], args.surah)
        print(f"\nFound {len(diffs)} differences between {args.compare[0]} and {args.compare[1]}")
        for diff in diffs[:20]:  # Show first 20
            print(f"  {diff.surah}:{diff.ayah} - {diff.word_text}")
            for riwaya, reading in diff.readings.items():
                print(f"    {riwaya}: {reading}")
        if len(diffs) > 20:
            print(f"  ... and {len(diffs) - 20} more")
        scraper.close_db()

    elif args.riwaya:
        scraper.connect_db()
        scraper.setup_database()
        count = scraper.import_riwaya(args.riwaya)
        print(f"Imported {count} verses for {args.riwaya}")
        scraper.close_db()

    elif args.export:
        scraper.connect_db()
        path = scraper.export_differences_json()
        print(f"Exported to: {path}")
        scraper.close_db()

    else:
        # Full import
        scraper.run_full_import()


if __name__ == "__main__":
    main()
