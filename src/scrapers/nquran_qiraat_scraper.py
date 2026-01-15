#!/usr/bin/env python3
"""
nquran.com Scraper for الفروق بين القراءات (Differences between Qiraat Readings)

This scraper extracts word-level qiraat differences from nquran.com and stores them
in the uloom_quran.db database, linking to the existing riwayat table.

Website: https://www.nquran.com/ar/
Target: الفروق بين القراءات العشر

Database tables used:
- qiraat_differences: Main differences table
- qiraat_difference_readings: Per-riwaya readings for each difference
- riwayat: Links to the existing riwayat table
- ruwat: Links to the existing ruwat (narrators) table
- qurra: Links to the existing qurra (readers) table
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import time
import os
import re
import argparse
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, '..', '..', 'db', 'uloom_quran.db')
EXPORT_PATH = os.path.join(SCRIPT_DIR, '..', '..', 'data', 'processed', 'qiraat_differences')

# Constants
BASE_URL = "https://www.nquran.com/ar"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
}

# Verse counts per surah
VERSE_COUNTS = {
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

# Arabic diacritics for removal (to match names regardless of tashkeel)
ARABIC_DIACRITICS = (
    '\u064B', '\u064C', '\u064D', '\u064E', '\u064F', '\u0650',
    '\u0651', '\u0652', '\u0653', '\u0654', '\u0655', '\u0656',
    '\u0657', '\u0658', '\u0659', '\u065A', '\u065B', '\u065C',
    '\u065D', '\u065E', '\u065F', '\u0670'
)

# Mapping of reader/narrator names to their database codes
# This maps various Arabic name variants to the database riwayat codes
READER_NAME_MAPPING = {
    # Nafi's narrators
    'قالون': 'qaloon',
    'قالون عن نافع': 'qaloon',
    'ورش': 'warsh',
    'ورش عن نافع': 'warsh',

    # Ibn Kathir's narrators
    'البزي': 'bazzi',
    'قنبل': 'qumbul',

    # Abu Amr's narrators
    'الدوري': 'doori',
    'الدوري عن أبي عمرو': 'doori',
    'السوسي': 'soosi',

    # Ibn Amir's narrators
    'هشام': None,  # Not in riwayat table
    'ابن ذكوان': None,

    # Asim's narrators
    'شعبة': 'shouba',
    'حفص': 'hafs',

    # Hamza's narrators
    'خلف': None,
    'خلاد': None,

    # Al-Kisai's narrators
    'أبو الحارث': None,

    # Abu Jafar's narrators
    'ابن وردان': None,
    'ابن جماز': None,

    # Yaqub's narrators
    'رويس': None,
    'روح': None,

    # Khalaf's narrators
    'إسحاق': None,
    'إدريس': None,
}

# Qari (reader) name mapping to database IDs
QARI_NAME_MAPPING = {
    'نافع': 1,
    'نافع بن عبد الرحمن': 1,
    'ابن كثير': 2,
    'عبد الله بن كثير': 2,
    'أبو عمرو': 3,
    'أبو عمرو بن العلاء': 3,
    'ابن عامر': 4,
    'عبد الله بن عامر': 4,
    'عاصم': 5,
    'عاصم بن أبي النجود': 5,
    'حمزة': 6,
    'حمزة بن حبيب': 6,
    'الكسائي': 7,
    'علي الكسائي': 7,
    'أبو جعفر': 8,
    'أبو جعفر المدني': 8,
    'يعقوب': 9,
    'يعقوب الحضرمي': 9,
    'خلف العاشر': 10,
    'خلف بن هشام': 10,
}


def remove_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel) from text"""
    return ''.join(c for c in text if c not in ARABIC_DIACRITICS)


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for comparison"""
    text = remove_diacritics(text)
    # Normalize alef variants
    text = re.sub(r'[أإآا]', 'ا', text)
    # Normalize teh marbuta
    text = text.replace('ة', 'ه')
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text.strip()


@dataclass
class QiraatDifferenceReading:
    """A single reading variant for a qiraat difference"""
    reader_names: List[str]  # List of reader/narrator names
    reading_text: str  # The actual reading variant
    description: str  # Description of the reading
    is_majority: bool = False  # True if this is "باقي الرواة"


@dataclass
class QiraatDifference:
    """Represents a word-level qiraat difference"""
    surah_id: int
    ayah_number: int
    word_text: str  # The word being discussed
    word_position: Optional[int] = None
    difference_type: Optional[str] = None  # Category of difference
    readings: List[QiraatDifferenceReading] = field(default_factory=list)
    source_url: Optional[str] = None
    scraped_at: Optional[str] = None


class NQuranQiraatScraper:
    """Scraper for nquran.com qiraat differences"""

    def __init__(self, db_path: str = DB_PATH):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.db_path = db_path
        self.riwayat_map = {}  # code -> id mapping
        self.ruwat_map = {}  # name -> id mapping
        self.qurra_map = {}  # name -> id mapping
        self._load_mappings()

        # Create export directory
        os.makedirs(EXPORT_PATH, exist_ok=True)

    def _load_mappings(self):
        """Load riwayat, ruwat, and qurra mappings from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Load riwayat mapping
        cursor.execute("SELECT id, code, name_arabic FROM riwayat")
        for row in cursor.fetchall():
            self.riwayat_map[row[1]] = row[0]  # code -> id
            # Also map Arabic name
            name_clean = normalize_arabic(row[2])
            self.riwayat_map[name_clean] = row[0]

        # Load ruwat mapping
        cursor.execute("SELECT id, name_arabic FROM ruwat")
        for row in cursor.fetchall():
            name_clean = normalize_arabic(row[1])
            self.ruwat_map[name_clean] = row[0]
            self.ruwat_map[row[1]] = row[0]

        # Load qurra mapping
        cursor.execute("SELECT id, name_arabic FROM qurra")
        for row in cursor.fetchall():
            name_clean = normalize_arabic(row[1])
            self.qurra_map[name_clean] = row[0]
            self.qurra_map[row[1]] = row[0]

        conn.close()
        logger.info(f"Loaded {len(self.riwayat_map)} riwayat, {len(self.ruwat_map)} ruwat, {len(self.qurra_map)} qurra mappings")

    def get_riwaya_id(self, reader_name: str) -> Optional[int]:
        """Get riwaya_id for a reader name"""
        # First check direct mapping
        if reader_name in READER_NAME_MAPPING:
            code = READER_NAME_MAPPING[reader_name]
            if code and code in self.riwayat_map:
                return self.riwayat_map[code]

        # Try normalized name lookup
        name_clean = normalize_arabic(reader_name)
        if name_clean in self.riwayat_map:
            return self.riwayat_map[name_clean]

        # Try partial match
        for key, value in self.riwayat_map.items():
            if isinstance(key, str) and name_clean in normalize_arabic(key):
                return value

        return None

    def get_rawi_id(self, reader_name: str) -> Optional[int]:
        """Get rawi_id for a reader name"""
        name_clean = normalize_arabic(reader_name)
        if name_clean in self.ruwat_map:
            return self.ruwat_map[name_clean]

        if reader_name in self.ruwat_map:
            return self.ruwat_map[reader_name]

        return None

    def get_qari_id(self, reader_name: str) -> Optional[int]:
        """Get qari_id for a reader name"""
        # Check direct mapping first
        if reader_name in QARI_NAME_MAPPING:
            return QARI_NAME_MAPPING[reader_name]

        name_clean = normalize_arabic(reader_name)
        if name_clean in self.qurra_map:
            return self.qurra_map[name_clean]

        if reader_name in self.qurra_map:
            return self.qurra_map[reader_name]

        # Check mapping dictionary
        for key, qari_id in QARI_NAME_MAPPING.items():
            if normalize_arabic(key) == name_clean:
                return qari_id

        return None

    def fetch_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with retries"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return BeautifulSoup(response.text, 'html.parser')
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return None

    def parse_reading_block(self, text: str) -> Optional[QiraatDifferenceReading]:
        """Parse a reading block text into structured data"""
        if not text or len(text.strip()) < 5:
            return None

        text = text.strip()
        is_majority = 'باقي الرواة' in text or 'باقي القراء' in text

        # Try to extract reading in parentheses
        reading_match = re.search(r'\(([^)]+)\)', text)
        reading_text = reading_match.group(1).strip() if reading_match else ""

        # Try to extract reader names (before قرأ or قرؤوا)
        reader_names = []
        if 'قرأ' in text or 'قرؤوا' in text:
            parts = re.split(r'قرأ|قرؤوا', text)
            if parts:
                readers_part = parts[0].strip()
                # Split by و and commas
                for name in re.split(r'[،,]|\sو\s', readers_part):
                    name = name.strip()
                    if name and name not in ['باقي الرواة', 'باقي القراء', '']:
                        reader_names.append(name)

        if is_majority:
            reader_names = ['باقي الرواة']

        # Get description (everything after the parentheses)
        description = text
        if reading_match:
            description = text[reading_match.end():].strip()
            # Clean up description
            description = re.sub(r'^[،,\s]+', '', description)

        if not reader_names and not reading_text:
            return None

        return QiraatDifferenceReading(
            reader_names=reader_names if reader_names else ['غير محدد'],
            reading_text=reading_text,
            description=description,
            is_majority=is_majority
        )

    def scrape_verse(self, surah_id: int, ayah_number: int) -> List[QiraatDifference]:
        """Scrape qiraat differences for a single verse"""
        url = f"{BASE_URL}/index.php?group=tb1&tpath=1&aya_no={ayah_number}&sorano={surah_id}"

        soup = self.fetch_page(url)
        if not soup:
            logger.error(f"Failed to fetch {surah_id}:{ayah_number}")
            return []

        differences = []

        try:
            # Check for no differences message
            page_text = soup.get_text()
            if 'لا خلاف بين القراء' in page_text or 'لا خلاف بين العلماء' in page_text:
                return []

            # Find the main content area - try multiple selectors
            content = None
            for selector in ['div.blockrwaya', '#detail', '.main-content', 'article']:
                content = soup.select_one(selector)
                if content:
                    break

            if not content:
                content = soup.find('body')

            if not content:
                return []

            # Find all word difference blocks
            # Look for patterns like "في قوله تعالى {word}" or similar headings

            # Method 1: Look for h2/h3 elements with word markers
            headings = content.find_all(['h2', 'h3', 'strong', 'b'])

            current_word = None
            current_readings = []

            for elem in content.descendants:
                if elem.name in ['h2', 'h3']:
                    # Save previous word if exists
                    if current_word and current_readings:
                        diff = QiraatDifference(
                            surah_id=surah_id,
                            ayah_number=ayah_number,
                            word_text=current_word,
                            readings=current_readings,
                            source_url=url,
                            scraped_at=datetime.now().isoformat()
                        )
                        differences.append(diff)

                    # Extract new word
                    text = elem.get_text(strip=True)
                    # Look for word in braces {word} or after في قوله تعالى
                    word_match = re.search(r'\{([^}]+)\}', text)
                    if word_match:
                        current_word = word_match.group(1).strip()
                    else:
                        # Try other patterns
                        word_match = re.search(r'في\s+قوله\s+تعالى\s*[::]?\s*(.+)', text)
                        if word_match:
                            current_word = word_match.group(1).strip()
                        else:
                            current_word = text.strip() if text else None

                    current_readings = []

                elif elem.name == 'div' and 'quran-page' in (elem.get('class') or []):
                    # This is a reading block
                    reading = self.parse_reading_block(elem.get_text())
                    if reading:
                        current_readings.append(reading)

                elif elem.name in ['li', 'p'] and current_word:
                    # Also check list items and paragraphs for readings
                    text = elem.get_text(strip=True)
                    if 'قرأ' in text or 'قرؤوا' in text:
                        reading = self.parse_reading_block(text)
                        if reading:
                            current_readings.append(reading)

            # Save last word
            if current_word and current_readings:
                diff = QiraatDifference(
                    surah_id=surah_id,
                    ayah_number=ayah_number,
                    word_text=current_word,
                    readings=current_readings,
                    source_url=url,
                    scraped_at=datetime.now().isoformat()
                )
                differences.append(diff)

            # Method 2: Alternative parsing - look for all text blocks with readings
            if not differences:
                # Get all text and parse it
                text_blocks = []
                for elem in content.find_all(['div', 'p', 'li']):
                    text = elem.get_text(strip=True)
                    if text and ('قرأ' in text or 'قرؤوا' in text):
                        text_blocks.append(text)

                if text_blocks:
                    # Create a single difference with all readings found
                    readings = []
                    for block in text_blocks:
                        reading = self.parse_reading_block(block)
                        if reading:
                            readings.append(reading)

                    if readings:
                        # Try to extract the word from the page title or content
                        word_text = "كلمة غير محددة"
                        title = soup.find('title')
                        if title:
                            title_match = re.search(r'الآية\s+(\d+)', title.get_text())

                        diff = QiraatDifference(
                            surah_id=surah_id,
                            ayah_number=ayah_number,
                            word_text=word_text,
                            readings=readings,
                            source_url=url,
                            scraped_at=datetime.now().isoformat()
                        )
                        differences.append(diff)

        except Exception as e:
            logger.error(f"Error parsing {surah_id}:{ayah_number}: {e}")

        return differences

    def scrape_surah(self, surah_id: int, delay: float = 0.3) -> List[QiraatDifference]:
        """Scrape all qiraat differences for a surah"""
        verse_count = VERSE_COUNTS.get(surah_id, 0)
        if verse_count == 0:
            logger.warning(f"Unknown verse count for surah {surah_id}")
            return []

        logger.info(f"Scraping Surah {surah_id} ({verse_count} verses)...")

        all_differences = []
        verses_with_diff = 0

        for ayah in range(1, verse_count + 1):
            differences = self.scrape_verse(surah_id, ayah)
            if differences:
                all_differences.extend(differences)
                verses_with_diff += 1

            if ayah % 20 == 0:
                logger.info(f"  Surah {surah_id}: {ayah}/{verse_count} verses processed, {len(all_differences)} differences found")

            time.sleep(delay)

        logger.info(f"Surah {surah_id} complete: {verses_with_diff} verses with differences, {len(all_differences)} total word differences")
        return all_differences

    def save_to_database(self, differences: List[QiraatDifference], clear_existing: bool = False):
        """Save differences to the database"""
        if not differences:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            if clear_existing:
                # Get surah IDs from differences
                surah_ids = set(d.surah_id for d in differences)
                for surah_id in surah_ids:
                    # First delete readings for differences in this surah
                    cursor.execute("""
                        DELETE FROM qiraat_difference_readings
                        WHERE difference_id IN (
                            SELECT id FROM qiraat_differences WHERE surah_id = ?
                        )
                    """, (surah_id,))
                    # Then delete the differences
                    cursor.execute("DELETE FROM qiraat_differences WHERE surah_id = ?", (surah_id,))

            inserted_diffs = 0
            inserted_readings = 0

            for diff in differences:
                # Insert the main difference
                cursor.execute("""
                    INSERT INTO qiraat_differences
                    (surah_id, ayah_number, word_position, word_text, difference_type, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    diff.surah_id,
                    diff.ayah_number,
                    diff.word_position,
                    diff.word_text,
                    diff.difference_type,
                    f"Source: {diff.source_url}"
                ))

                difference_id = cursor.lastrowid
                inserted_diffs += 1

                # Insert each reading
                for reading in diff.readings:
                    # Try to find riwaya_id for each reader
                    for reader_name in reading.reader_names:
                        riwaya_id = self.get_riwaya_id(reader_name)

                        if riwaya_id:
                            cursor.execute("""
                                INSERT INTO qiraat_difference_readings
                                (difference_id, riwaya_id, reading_text)
                                VALUES (?, ?, ?)
                            """, (
                                difference_id,
                                riwaya_id,
                                f"{reading.reading_text} - {reading.description}"
                            ))
                            inserted_readings += 1

            conn.commit()
            logger.info(f"Saved {inserted_diffs} differences and {inserted_readings} readings to database")

        except Exception as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def export_to_json(self, differences: List[QiraatDifference], filename: str):
        """Export differences to JSON file"""
        data = {
            "scraped_at": datetime.now().isoformat(),
            "source": "nquran.com",
            "total_differences": len(differences),
            "differences": [asdict(d) for d in differences]
        }

        filepath = os.path.join(EXPORT_PATH, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(differences)} differences to {filepath}")

    def scrape_range(self, start_surah: int = 1, end_surah: int = 114,
                     delay: float = 0.3, save_to_db: bool = True,
                     export_json: bool = True, clear_existing: bool = False):
        """Scrape a range of surahs"""
        logger.info(f"Starting scrape from Surah {start_surah} to {end_surah}")

        all_differences = []

        for surah_id in range(start_surah, end_surah + 1):
            surah_differences = self.scrape_surah(surah_id, delay=delay)

            if surah_differences:
                all_differences.extend(surah_differences)

                # Save each surah separately
                if save_to_db:
                    self.save_to_database(surah_differences, clear_existing=clear_existing)

                if export_json:
                    self.export_to_json(surah_differences, f"surah_{surah_id:03d}_qiraat.json")

            # Rate limiting between surahs
            time.sleep(1)

        # Export combined file
        if export_json and all_differences:
            self.export_to_json(all_differences, f"qiraat_differences_{start_surah}-{end_surah}.json")

        logger.info(f"Scraping complete. Total differences: {len(all_differences)}")
        return all_differences


def main():
    parser = argparse.ArgumentParser(
        description='Scrape qiraat differences from nquran.com'
    )
    parser.add_argument('--surah', type=int, help='Specific surah to scrape (1-114)')
    parser.add_argument('--start', type=int, default=1, help='Start surah (default: 1)')
    parser.add_argument('--end', type=int, default=114, help='End surah (default: 114)')
    parser.add_argument('--delay', type=float, default=0.3, help='Delay between requests in seconds (default: 0.3)')
    parser.add_argument('--no-db', action='store_true', help='Do not save to database')
    parser.add_argument('--no-json', action='store_true', help='Do not export to JSON')
    parser.add_argument('--clear', action='store_true', help='Clear existing data before inserting')
    parser.add_argument('--db', type=str, default=DB_PATH, help='Database path')

    args = parser.parse_args()

    # Validate arguments
    if args.surah:
        if args.surah < 1 or args.surah > 114:
            print("Error: Surah must be between 1 and 114")
            return 1
        args.start = args.surah
        args.end = args.surah

    if args.start < 1 or args.start > 114 or args.end < 1 or args.end > 114:
        print("Error: Start and end must be between 1 and 114")
        return 1

    if args.start > args.end:
        print("Error: Start surah must be <= end surah")
        return 1

    print("=" * 60)
    print("nquran.com Qiraat Differences Scraper")
    print("=" * 60)
    print(f"Surahs: {args.start} to {args.end}")
    print(f"Database: {args.db}")
    print(f"Save to DB: {not args.no_db}")
    print(f"Export JSON: {not args.no_json}")
    print(f"Delay: {args.delay}s")
    print("=" * 60)

    scraper = NQuranQiraatScraper(db_path=args.db)

    differences = scraper.scrape_range(
        start_surah=args.start,
        end_surah=args.end,
        delay=args.delay,
        save_to_db=not args.no_db,
        export_json=not args.no_json,
        clear_existing=args.clear
    )

    print("\n" + "=" * 60)
    print(f"Scraping complete!")
    print(f"Total differences found: {len(differences)}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
