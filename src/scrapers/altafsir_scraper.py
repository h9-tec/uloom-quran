#!/usr/bin/env python3
"""
altafsir.com Scraper for القراءات (Quranic Readings/Qiraat)

Website: https://www.altafsir.com
Sections:
- القراءات العشر (Ten Readings): Recitations.asp
- القراءات الشاذة (Rare/Odd Readings): RecitationsOdd.asp

This scraper handles the dynamic form-based content loading used by altafsir.com.
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import os
import json
import argparse
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from urllib.parse import urljoin

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.altafsir.com"
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'uloom_quran.db')
EXPORT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed', 'altafsir_qiraat')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.altafsir.com/',
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

# Surah names in Arabic
SURAH_NAMES = {
    1: 'الفاتحة', 2: 'البقرة', 3: 'آل عمران', 4: 'النساء', 5: 'المائدة',
    6: 'الأنعام', 7: 'الأعراف', 8: 'الأنفال', 9: 'التوبة', 10: 'يونس',
    11: 'هود', 12: 'يوسف', 13: 'الرعد', 14: 'إبراهيم', 15: 'الحجر',
    16: 'النحل', 17: 'الإسراء', 18: 'الكهف', 19: 'مريم', 20: 'طه',
    21: 'الأنبياء', 22: 'الحج', 23: 'المؤمنون', 24: 'النور', 25: 'الفرقان',
    26: 'الشعراء', 27: 'النمل', 28: 'القصص', 29: 'العنكبوت', 30: 'الروم',
    31: 'لقمان', 32: 'السجدة', 33: 'الأحزاب', 34: 'سبأ', 35: 'فاطر',
    36: 'يس', 37: 'الصافات', 38: 'ص', 39: 'الزمر', 40: 'غافر',
    41: 'فصلت', 42: 'الشورى', 43: 'الزخرف', 44: 'الدخان', 45: 'الجاثية',
    46: 'الأحقاف', 47: 'محمد', 48: 'الفتح', 49: 'الحجرات', 50: 'ق',
    51: 'الذاريات', 52: 'الطور', 53: 'النجم', 54: 'القمر', 55: 'الرحمن',
    56: 'الواقعة', 57: 'الحديد', 58: 'المجادلة', 59: 'الحشر', 60: 'الممتحنة',
    61: 'الصف', 62: 'الجمعة', 63: 'المنافقون', 64: 'التغابن', 65: 'الطلاق',
    66: 'التحريم', 67: 'الملك', 68: 'القلم', 69: 'الحاقة', 70: 'المعارج',
    71: 'نوح', 72: 'الجن', 73: 'المزمل', 74: 'المدثر', 75: 'القيامة',
    76: 'الإنسان', 77: 'المرسلات', 78: 'النبأ', 79: 'النازعات', 80: 'عبس',
    81: 'التكوير', 82: 'الانفطار', 83: 'المطففين', 84: 'الانشقاق', 85: 'البروج',
    86: 'الطارق', 87: 'الأعلى', 88: 'الغاشية', 89: 'الفجر', 90: 'البلد',
    91: 'الشمس', 92: 'الليل', 93: 'الضحى', 94: 'الشرح', 95: 'التين',
    96: 'العلق', 97: 'القدر', 98: 'البينة', 99: 'الزلزلة', 100: 'العاديات',
    101: 'القارعة', 102: 'التكاثر', 103: 'العصر', 104: 'الهمزة', 105: 'الفيل',
    106: 'قريش', 107: 'الماعون', 108: 'الكوثر', 109: 'الكافرون', 110: 'النصر',
    111: 'المسد', 112: 'الإخلاص', 113: 'الفلق', 114: 'الناس'
}

# The ten readers and their transmitters (from database schema)
QURRA_INFO = {
    1: {'name': 'نافع بن عبد الرحمن', 'ruwat': ['قالون', 'ورش']},
    2: {'name': 'عبد الله بن كثير', 'ruwat': ['البزي', 'قنبل']},
    3: {'name': 'أبو عمرو بن العلاء', 'ruwat': ['الدوري', 'السوسي']},
    4: {'name': 'عبد الله بن عامر', 'ruwat': ['هشام', 'ابن ذكوان']},
    5: {'name': 'عاصم بن أبي النجود', 'ruwat': ['شعبة', 'حفص']},
    6: {'name': 'حمزة بن حبيب الزيات', 'ruwat': ['خلف', 'خلاد']},
    7: {'name': 'علي بن حمزة الكسائي', 'ruwat': ['أبو الحارث', 'الدوري']},
    8: {'name': 'أبو جعفر يزيد بن القعقاع', 'ruwat': ['ابن وردان', 'ابن جماز']},
    9: {'name': 'يعقوب بن إسحاق الحضرمي', 'ruwat': ['رويس', 'روح']},
    10: {'name': 'خلف بن هشام البزار', 'ruwat': ['إسحاق', 'إدريس']},
}


@dataclass
class QiraatVariant:
    """Represents a single qiraat variant/difference"""
    surah: int
    ayah: int
    word: str
    word_position: Optional[int] = None
    variant_type: str = 'فرش'  # 'أصول' (general rules) or 'فرش' (specific words)
    readings: Dict[str, str] = field(default_factory=dict)  # reader_name -> reading_text
    description: Optional[str] = None
    notes: Optional[str] = None
    source: str = 'altafsir.com'
    category: Optional[str] = None  # Classification of difference type


@dataclass
class QiraatRule:
    """Represents a general qiraat rule (أصول)"""
    qari_id: int
    qari_name: str
    rule_name: str
    rule_description: str
    examples: List[str] = field(default_factory=list)
    source: str = 'altafsir.com'


class AltafsirScraper:
    """Scraper for altafsir.com القراءات data"""

    def __init__(self, output_dir: str = None):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.output_dir = output_dir or EXPORT_PATH
        os.makedirs(self.output_dir, exist_ok=True)
        self.variants: List[QiraatVariant] = []
        self.rules: List[QiraatRule] = []

    def get_page(self, url: str, method: str = 'GET', data: dict = None,
                 retries: int = 3) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with retries"""
        for attempt in range(retries):
            try:
                if method == 'POST':
                    response = self.session.post(url, data=data, timeout=30)
                else:
                    response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return BeautifulSoup(response.text, 'html.parser')
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                time.sleep(2 ** attempt)
        return None

    def scrape_recitations_page(self, surah: int, ayah: int = None) -> List[QiraatVariant]:
        """Scrape the main recitations page for a surah/ayah"""
        variants = []

        # Try different URL patterns
        urls_to_try = [
            f"{BASE_URL}/Recitations.asp?SoraNo={surah}&LanguageID=1&TypeID=A",
            f"{BASE_URL}/Recitations.asp?SoraName={surah}&LanguageID=1&rDisplay=yes",
        ]

        if ayah:
            urls_to_try.insert(0, f"{BASE_URL}/Recitations.asp?SoraNo={surah}&AyaNo={ayah}&LanguageID=1&TypeID=A")

        for url in urls_to_try:
            soup = self.get_page(url)
            if soup:
                # Try to extract qiraat content
                variants.extend(self._parse_recitations_content(soup, surah, ayah))
                if variants:
                    break

        # Also try POST request with form data (site uses form submission)
        if not variants:
            form_data = {
                'SoraName': surah,
                'Ayat': ayah or '',
                'rDisplay': 'yes',
                'LanguageID': '1',
                'TypeID': 'A',
                'Reader': '',
                'Narrator': '',
                'Rule': '',
            }
            soup = self.get_page(f"{BASE_URL}/Recitations.asp", method='POST', data=form_data)
            if soup:
                variants.extend(self._parse_recitations_content(soup, surah, ayah))

        return variants

    def scrape_odd_recitations(self, surah: int, ayah: int = None) -> List[QiraatVariant]:
        """Scrape القراءات الشاذة (odd/rare readings)"""
        variants = []

        url = f"{BASE_URL}/RecitationsOdd.asp?SoraNo={surah}&LanguageID=1&TypeID=C"
        if ayah:
            url += f"&AyaNo={ayah}"

        soup = self.get_page(url)
        if soup:
            variants.extend(self._parse_odd_recitations(soup, surah, ayah))

        return variants

    def _parse_recitations_content(self, soup: BeautifulSoup, surah: int,
                                    ayah: Optional[int]) -> List[QiraatVariant]:
        """Parse qiraat content from the page"""
        variants = []

        try:
            # Look for qiraat data in various possible containers
            # The site uses tables and divs for displaying content

            # Try finding content tables
            content_tables = soup.find_all('table', {'class': re.compile(r'content|qiraat|reading', re.I)})
            if not content_tables:
                content_tables = soup.find_all('table', {'width': '100%'})

            for table in content_tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # Try to extract word and reading data
                        text_content = ' '.join(cell.get_text(strip=True) for cell in cells)
                        if self._contains_arabic(text_content):
                            variant = self._extract_variant_from_row(cells, surah, ayah)
                            if variant:
                                variants.append(variant)

            # Also try finding divs with qiraat content
            content_divs = soup.find_all('div', {'class': re.compile(r'qiraat|reading|content|text', re.I)})
            for div in content_divs:
                text = div.get_text(strip=True)
                if self._contains_arabic(text) and len(text) > 20:
                    # Parse structured content
                    variant = self._extract_variant_from_text(text, surah, ayah)
                    if variant:
                        variants.append(variant)

            # Look for specific patterns in the page text
            all_text = soup.get_text()
            # Pattern: word followed by reading alternatives
            patterns = [
                r'(\w+)\s*:\s*قرأ\s+([^،]+)،?\s*وقرأ\s+([^\.]+)',  # word: reader1 read X, reader2 read Y
                r'قرأ\s+(\S+)\s+\(([^)]+)\)',  # reader read (word)
                r'(\S+)\s+بـ?\s*([^،]+)،\s*و(\S+)\s+بـ?\s*([^\.]+)',  # reader1 with X, reader2 with Y
            ]

            for pattern in patterns:
                matches = re.finditer(pattern, all_text)
                for match in matches:
                    variant = self._create_variant_from_match(match, surah, ayah)
                    if variant:
                        variants.append(variant)

        except Exception as e:
            logger.error(f"Error parsing recitations for {surah}:{ayah}: {e}")

        return variants

    def _parse_odd_recitations(self, soup: BeautifulSoup, surah: int,
                                ayah: Optional[int]) -> List[QiraatVariant]:
        """Parse odd/rare recitations content"""
        variants = []

        try:
            # Similar parsing to main recitations but marked as شاذ
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        text_content = ' '.join(cell.get_text(strip=True) for cell in cells)
                        if self._contains_arabic(text_content):
                            variant = self._extract_variant_from_row(cells, surah, ayah)
                            if variant:
                                variant.category = 'شاذة'  # Mark as odd/rare reading
                                variants.append(variant)

        except Exception as e:
            logger.error(f"Error parsing odd recitations for {surah}:{ayah}: {e}")

        return variants

    def _contains_arabic(self, text: str) -> bool:
        """Check if text contains Arabic characters"""
        return bool(re.search(r'[\u0600-\u06FF]', text))

    def _extract_variant_from_row(self, cells: list, surah: int,
                                   ayah: Optional[int]) -> Optional[QiraatVariant]:
        """Extract variant data from table row cells"""
        try:
            texts = [cell.get_text(strip=True) for cell in cells if cell.get_text(strip=True)]
            if len(texts) < 2:
                return None

            # Try to identify word and reading
            word = None
            readings = {}

            for i, text in enumerate(texts):
                # Check if this looks like a Quranic word
                if self._is_quranic_word(text):
                    if not word:
                        word = text
                # Check if this contains reader names
                for qari_id, qari_info in QURRA_INFO.items():
                    if qari_info['name'] in text or any(r in text for r in qari_info['ruwat']):
                        # This cell contains reader info
                        reading_text = texts[i+1] if i+1 < len(texts) else text
                        readings[qari_info['name']] = reading_text

            if word and readings:
                return QiraatVariant(
                    surah=surah,
                    ayah=ayah or 1,
                    word=word,
                    readings=readings,
                    source='altafsir.com'
                )

        except Exception as e:
            logger.debug(f"Error extracting variant from row: {e}")

        return None

    def _extract_variant_from_text(self, text: str, surah: int,
                                    ayah: Optional[int]) -> Optional[QiraatVariant]:
        """Extract variant data from text content"""
        try:
            readings = {}
            word = None

            # Look for patterns like "قرأ نافع (كلمة) بكذا"
            pattern = r'قرأ\s+(\S+)\s+[«"\']([\u0600-\u06FF\s]+)[»"\']'
            matches = re.findall(pattern, text)

            for reader, reading in matches:
                # Map reader name to our qurra list
                for qari_id, qari_info in QURRA_INFO.items():
                    if reader in qari_info['name'] or reader in qari_info['ruwat']:
                        readings[qari_info['name']] = reading
                        if not word:
                            word = reading
                        break

            if readings:
                return QiraatVariant(
                    surah=surah,
                    ayah=ayah or 1,
                    word=word or list(readings.values())[0],
                    readings=readings,
                    source='altafsir.com'
                )

        except Exception as e:
            logger.debug(f"Error extracting variant from text: {e}")

        return None

    def _create_variant_from_match(self, match, surah: int,
                                    ayah: Optional[int]) -> Optional[QiraatVariant]:
        """Create variant from regex match"""
        try:
            groups = match.groups()
            if len(groups) >= 2:
                readings = {}
                word = groups[0] if self._contains_arabic(groups[0]) else None

                for group in groups[1:]:
                    if self._contains_arabic(group):
                        # Try to identify reader
                        for qari_id, qari_info in QURRA_INFO.items():
                            if qari_info['name'] in group:
                                readings[qari_info['name']] = group
                                break
                        else:
                            for rawi_list in [q['ruwat'] for q in QURRA_INFO.values()]:
                                for rawi in rawi_list:
                                    if rawi in group:
                                        readings[rawi] = group
                                        break

                if readings and word:
                    return QiraatVariant(
                        surah=surah,
                        ayah=ayah or 1,
                        word=word,
                        readings=readings,
                        source='altafsir.com'
                    )

        except Exception as e:
            logger.debug(f"Error creating variant from match: {e}")

        return None

    def _is_quranic_word(self, text: str) -> bool:
        """Check if text looks like a Quranic word"""
        if not text or len(text) > 30:
            return False
        # Should be mostly Arabic
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        return arabic_chars > len(text) * 0.5

    def scrape_surah(self, surah: int) -> List[QiraatVariant]:
        """Scrape all qiraat variants for a surah"""
        logger.info(f"Scraping Surah {surah} ({SURAH_NAMES.get(surah, '')})...")
        surah_variants = []

        # First try to get surah-level data
        surah_variants.extend(self.scrape_recitations_page(surah))
        surah_variants.extend(self.scrape_odd_recitations(surah))

        # Then try verse-by-verse if we didn't get much
        if len(surah_variants) < 5:
            verse_count = VERSE_COUNTS.get(surah, 0)
            for ayah in range(1, verse_count + 1):
                variants = self.scrape_recitations_page(surah, ayah)
                surah_variants.extend(variants)

                odd_variants = self.scrape_odd_recitations(surah, ayah)
                surah_variants.extend(odd_variants)

                time.sleep(0.3)  # Rate limiting

                if ayah % 50 == 0:
                    logger.info(f"  Surah {surah}: {ayah}/{verse_count} verses processed")

        return surah_variants

    def scrape_all(self, start_surah: int = 1, end_surah: int = 114) -> List[QiraatVariant]:
        """Scrape all surahs"""
        logger.info(f"Starting full scrape from Surah {start_surah} to {end_surah}")
        all_variants = []

        for surah in range(start_surah, end_surah + 1):
            surah_variants = self.scrape_surah(surah)
            all_variants.extend(surah_variants)

            # Save progress after each surah
            self.save_surah_data(surah, surah_variants)

            logger.info(f"Surah {surah} complete: {len(surah_variants)} variants found")
            time.sleep(1)  # Be respectful to the server

        self.variants = all_variants
        self.save_all_data()

        return all_variants

    def save_surah_data(self, surah: int, variants: List[QiraatVariant]):
        """Save surah data to JSON file"""
        filepath = os.path.join(self.output_dir, f"surah_{surah:03d}_qiraat.json")
        data = {
            "surah": surah,
            "surah_name": SURAH_NAMES.get(surah, ''),
            "source": "altafsir.com",
            "variants_count": len(variants),
            "variants": [asdict(v) for v in variants]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Saved {len(variants)} variants to {filepath}")

    def save_all_data(self):
        """Save all data to a single JSON file"""
        filepath = os.path.join(self.output_dir, "all_qiraat_altafsir.json")

        data = {
            "source": "altafsir.com",
            "total_variants": len(self.variants),
            "qurra": {str(k): v for k, v in QURRA_INFO.items()},
            "variants": [asdict(v) for v in self.variants]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self.variants)} variants to {filepath}")


class DatabaseImporter:
    """Import scraped qiraat data into the database"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def get_verse_id(self, cursor, surah: int, ayah: int) -> Optional[int]:
        """Get verse ID from database"""
        verse_key = f"{surah}:{ayah}"
        cursor.execute("SELECT id FROM verses WHERE verse_key = ?", (verse_key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_qari_id(self, cursor, qari_name: str) -> Optional[int]:
        """Get qari ID from database"""
        cursor.execute("SELECT id FROM qurra WHERE name_arabic LIKE ?", (f'%{qari_name}%',))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_rawi_id(self, cursor, rawi_name: str) -> Optional[int]:
        """Get rawi ID from database"""
        cursor.execute("SELECT id FROM ruwat WHERE name_arabic LIKE ?", (f'%{rawi_name}%',))
        row = cursor.fetchone()
        return row[0] if row else None

    def import_variants(self, variants: List[QiraatVariant]) -> Tuple[int, int]:
        """Import qiraat variants to database"""
        conn = self.get_connection()
        cursor = conn.cursor()

        imported = 0
        skipped = 0

        for variant in variants:
            try:
                verse_id = self.get_verse_id(cursor, variant.surah, variant.ayah)
                if not verse_id:
                    logger.warning(f"Verse not found: {variant.surah}:{variant.ayah}")
                    skipped += 1
                    continue

                # Insert into qiraat_variants
                cursor.execute("""
                    INSERT INTO qiraat_variants
                    (verse_id, word_text, word_position, variant_type, category)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    verse_id,
                    variant.word,
                    variant.word_position,
                    variant.variant_type,
                    variant.category
                ))
                variant_id = cursor.lastrowid

                # Insert readings for each qari
                for reader_name, reading_text in variant.readings.items():
                    qari_id = self.get_qari_id(cursor, reader_name)
                    rawi_id = self.get_rawi_id(cursor, reader_name)

                    if qari_id or rawi_id:
                        cursor.execute("""
                            INSERT INTO qiraat_readings
                            (variant_id, qari_id, rawi_id, reading_text, is_default)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            variant_id,
                            qari_id or 5,  # Default to Asim if not found
                            rawi_id,
                            reading_text,
                            1 if 'حفص' in reader_name else 0
                        ))

                imported += 1

            except sqlite3.IntegrityError as e:
                logger.debug(f"Duplicate entry for {variant.surah}:{variant.ayah}: {e}")
                skipped += 1
            except Exception as e:
                logger.error(f"Error importing variant: {e}")
                skipped += 1

        conn.commit()
        conn.close()

        return imported, skipped

    def import_from_json(self, json_path: str) -> Tuple[int, int]:
        """Import variants from a JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        variants = []
        for v in data.get('variants', []):
            variants.append(QiraatVariant(**v))

        return self.import_variants(variants)


def create_sample_data() -> List[QiraatVariant]:
    """Create sample qiraat data for testing (famous differences)"""
    sample_variants = [
        QiraatVariant(
            surah=1,
            ayah=4,
            word="مَالِكِ",
            word_position=1,
            variant_type="فرش",
            readings={
                "عاصم بن أبي النجود": "مَالِكِ - بالألف",
                "نافع بن عبد الرحمن": "مَلِكِ - بدون ألف",
                "عبد الله بن كثير": "مَلِكِ - بدون ألف",
                "أبو عمرو بن العلاء": "مَلِكِ - بدون ألف",
            },
            description="اختلاف في المعنى: مالك (صاحب الملك) أو ملك (الحاكم)",
            notes="من أشهر الفروق بين القراءات",
            source="altafsir.com"
        ),
        QiraatVariant(
            surah=1,
            ayah=6,
            word="الصِّرَاطَ",
            word_position=2,
            variant_type="أصول",
            readings={
                "عاصم بن أبي النجود": "الصِّرَاطَ - بالصاد",
                "خلف بن هشام البزار": "السِّرَاطَ - بالسين",
                "يعقوب بن إسحاق الحضرمي": "الصِّرَاطَ - بإشمام الزاي",
            },
            description="اختلاف في نطق الصاد: صاد خالصة، سين، أو إشمام",
            source="altafsir.com"
        ),
        QiraatVariant(
            surah=2,
            ayah=85,
            word="تَظَاهَرُونَ",
            word_position=4,
            variant_type="فرش",
            readings={
                "عاصم بن أبي النجود": "تَظَاهَرُونَ - بتخفيف الظاء",
                "عبد الله بن عامر": "تَظَّاهَرُونَ - بتشديد الظاء",
                "عبد الله بن كثير": "تَظَّاهَرُونَ - بتشديد الظاء",
            },
            description="الاختلاف في التشديد والتخفيف",
            source="altafsir.com"
        ),
        QiraatVariant(
            surah=2,
            ayah=184,
            word="فِدْيَةٌ",
            word_position=5,
            variant_type="فرش",
            readings={
                "عاصم بن أبي النجود": "فِدْيَةٌ طَعَامُ - بالتنوين والإضافة",
                "نافع بن عبد الرحمن": "فِدْيَةٌ طَعَامُ - بالتنوين والإضافة",
                "أبو عمرو بن العلاء": "فِدْيَةُ طَعَامِ - بالإضافة",
            },
            description="اختلاف في الإضافة والتنوين",
            source="altafsir.com"
        ),
        QiraatVariant(
            surah=3,
            ayah=146,
            word="قَاتَلَ",
            word_position=3,
            variant_type="فرش",
            readings={
                "عاصم بن أبي النجود": "قَاتَلَ - بألف بعد القاف (فاعَل)",
                "عبد الله بن عامر": "قُتِلَ - بدون ألف (فُعِل)",
                "حمزة بن حبيب الزيات": "قُتِلَ - مبني للمجهول",
            },
            description="الفرق بين المبني للمعلوم والمجهول",
            source="altafsir.com"
        ),
        QiraatVariant(
            surah=18,
            ayah=86,
            word="عَيْنٍ حَمِئَةٍ",
            word_position=7,
            variant_type="فرش",
            readings={
                "عاصم بن أبي النجود": "حَمِئَةٍ - بالهمزة من الحمأ (الطين)",
                "نافع بن عبد الرحمن": "حَامِيَةٍ - بدون همز (حارة)",
                "عبد الله بن كثير": "حَامِيَةٍ - بدون همز (حارة)",
            },
            description="اختلاف المعنى: طينية أو حارة",
            source="altafsir.com"
        ),
    ]

    return sample_variants


def main():
    parser = argparse.ArgumentParser(description='Scrape altafsir.com for Qiraat data')
    parser.add_argument('--surah', type=int, help='Specific surah to scrape (1-114)')
    parser.add_argument('--start', type=int, default=1, help='Start surah')
    parser.add_argument('--end', type=int, default=114, help='End surah')
    parser.add_argument('--output', default=EXPORT_PATH, help='Output directory')
    parser.add_argument('--sample', action='store_true', help='Generate sample data only')
    parser.add_argument('--import-db', action='store_true', help='Import to database')
    parser.add_argument('--import-file', type=str, help='JSON file to import to database')

    args = parser.parse_args()

    print("=" * 60)
    print("altafsir.com Qiraat Scraper")
    print("=" * 60)

    if args.sample:
        # Generate sample data
        sample = create_sample_data()
        os.makedirs(args.output, exist_ok=True)

        filepath = os.path.join(args.output, "sample_altafsir_qiraat.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "source": "altafsir.com",
                "sample": True,
                "description": "Sample famous qiraat differences",
                "variants": [asdict(v) for v in sample]
            }, f, ensure_ascii=False, indent=2)

        print(f"Sample data saved to {filepath}")

        if args.import_db:
            print("\nImporting sample data to database...")
            importer = DatabaseImporter()
            imported, skipped = importer.import_variants(sample)
            print(f"Imported: {imported}, Skipped: {skipped}")

    elif args.import_file:
        # Import from JSON file
        print(f"Importing from {args.import_file}...")
        importer = DatabaseImporter()
        imported, skipped = importer.import_from_json(args.import_file)
        print(f"Imported: {imported}, Skipped: {skipped}")

    else:
        # Scrape website
        scraper = AltafsirScraper(output_dir=args.output)

        if args.surah:
            variants = scraper.scrape_surah(args.surah)
            scraper.save_surah_data(args.surah, variants)
        else:
            variants = scraper.scrape_all(args.start, args.end)

        print(f"\nScraped {len(variants)} variants")

        if args.import_db:
            print("\nImporting to database...")
            importer = DatabaseImporter()
            imported, skipped = importer.import_variants(variants)
            print(f"Imported: {imported}, Skipped: {skipped}")

    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
