#!/usr/bin/env python3
"""
nquran.com Scraper for القراءات العشر (Ten Readings)
Scrapes differences between the ten Quranic readings

Website: https://www.nquran.com/ar/
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.nquran.com/ar"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en;q=0.9',
}

# Surah info
SURAH_COUNT = 114
SURAH_AYAH_COUNT = {
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

# The ten readers and their transmitters
QURRA = {
    'نافع': {'id': 1, 'ruwat': ['قالون', 'ورش']},
    'ابن كثير': {'id': 2, 'ruwat': ['البزي', 'قنبل']},
    'أبو عمرو': {'id': 3, 'ruwat': ['الدوري', 'السوسي']},
    'ابن عامر': {'id': 4, 'ruwat': ['هشام', 'ابن ذكوان']},
    'عاصم': {'id': 5, 'ruwat': ['شعبة', 'حفص']},
    'حمزة': {'id': 6, 'ruwat': ['خلف', 'خلاد']},
    'الكسائي': {'id': 7, 'ruwat': ['أبو الحارث', 'الدوري']},
    'أبو جعفر': {'id': 8, 'ruwat': ['ابن وردان', 'ابن جماز']},
    'يعقوب': {'id': 9, 'ruwat': ['رويس', 'روح']},
    'خلف العاشر': {'id': 10, 'ruwat': ['إسحاق', 'إدريس']},
}

# Arabic diacritics pattern for removal (to match names regardless of tashkeel)
import unicodedata

def remove_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel) from text"""
    # Arabic diacritic marks Unicode range
    diacritics = (
        '\u064B', '\u064C', '\u064D', '\u064E', '\u064F', '\u0650',
        '\u0651', '\u0652', '\u0653', '\u0654', '\u0655', '\u0656',
        '\u0657', '\u0658', '\u0659', '\u065A', '\u065B', '\u065C',
        '\u065D', '\u065E', '\u065F', '\u0670'
    )
    return ''.join(c for c in text if c not in diacritics)


@dataclass
class QiraatVariant:
    """Represents a single reading variant"""
    surah: int
    ayah: int
    word: str
    word_position: Optional[int]
    variant_type: str  # 'أصول' or 'فرش'
    readings: Dict[str, str]  # qari_name -> reading text
    notes: Optional[str] = None


class NQuranScraper:
    """Scraper for nquran.com القراءات العشر data"""

    def __init__(self, output_dir: str = "data/processed/qiraat"):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.variants: List[QiraatVariant] = []

    def get_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with retries"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return BeautifulSoup(response.text, 'html.parser')
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                time.sleep(2 ** attempt)
        return None

    def scrape_verse_variants(self, surah: int, ayah: int) -> List[QiraatVariant]:
        """Scrape qiraat variants for a specific verse"""
        # Correct URL pattern: aya_no for verse, sorano for surah
        url = f"{BASE_URL}/index.php?group=tb1&tpath=1&aya_no={ayah}&sorano={surah}"

        soup = self.get_page(url)
        if not soup:
            logger.error(f"Failed to fetch {surah}:{ayah}")
            return []

        variants = []

        try:
            # Find blockrwaya - contains the actual difference data
            blockrwaya = soup.find('div', class_='blockrwaya')
            if not blockrwaya:
                return []

            # Check if there's no difference
            block_text = blockrwaya.get_text(strip=True)
            if 'لا خلاف بين القراء' in block_text:
                return []

            # Find all h2 elements - each represents a word with differences
            h2_elements = blockrwaya.find_all('h2')

            for h2 in h2_elements:
                # Extract the word from {word} in strong tag
                strong = h2.find('strong')
                if not strong:
                    continue

                word_text = strong.get_text(strip=True)
                # Clean up the word (remove braces if present)
                word = word_text.replace('{', '').replace('}', '').strip()
                if not word:
                    continue

                # Find quran-page divs that contain reader info
                quran_pages = h2.find_all('div', class_='quran-page')
                readings = {}

                for qp in quran_pages:
                    qp_text = qp.get_text(strip=True)
                    qp_text_clean = remove_diacritics(qp_text)

                    # Parse pattern: "ReaderNames قرأ (reading) description"
                    # or "باقي الرواة قرؤوا (reading) description"
                    if 'قرأ' in qp_text_clean or 'قرؤوا' in qp_text_clean:
                        # Extract the reading in parentheses (keep original with diacritics)
                        read_match = re.search(r'قرأ[وا]?\s*\(([^)]+)\)\s*(.+)', qp_text)
                        if read_match:
                            reading = read_match.group(1).strip()
                            description = read_match.group(2).strip()

                            # Extract reader names (text before قرأ) - use clean version for matching
                            readers_part = qp_text_clean.split('قرأ')[0].strip()

                            if 'باقي الرواة' in readers_part or readers_part == '':
                                readings['باقي الرواة'] = f"{reading} - {description}"
                            else:
                                # Map individual readers (compare without diacritics)
                                for qari in QURRA.keys():
                                    if remove_diacritics(qari) in readers_part:
                                        readings[qari] = f"{reading} - {description}"

                                # Also check for ruwat names
                                for qari_data in QURRA.values():
                                    for rawi in qari_data['ruwat']:
                                        if remove_diacritics(rawi) in readers_part:
                                            readings[rawi] = f"{reading} - {description}"

                if readings:
                    variant = QiraatVariant(
                        surah=surah,
                        ayah=ayah,
                        word=word,
                        word_position=None,
                        variant_type='فرش',
                        readings=readings
                    )
                    variants.append(variant)

        except Exception as e:
            logger.error(f"Error parsing {surah}:{ayah}: {e}")

        return variants

    def scrape_surah(self, surah: int) -> List[QiraatVariant]:
        """Scrape all variants for a surah"""
        logger.info(f"Scraping Surah {surah}...")
        ayah_count = SURAH_AYAH_COUNT.get(surah, 0)
        surah_variants = []

        for ayah in range(1, ayah_count + 1):
            variants = self.scrape_verse_variants(surah, ayah)
            surah_variants.extend(variants)
            time.sleep(0.5)  # Rate limiting

            if ayah % 50 == 0:
                logger.info(f"  Surah {surah}: {ayah}/{ayah_count} verses processed")

        return surah_variants

    def scrape_all(self, start_surah: int = 1, end_surah: int = 114):
        """Scrape all surahs"""
        logger.info(f"Starting full scrape from Surah {start_surah} to {end_surah}")

        all_variants = []

        for surah in range(start_surah, end_surah + 1):
            surah_variants = self.scrape_surah(surah)
            all_variants.extend(surah_variants)

            # Save progress after each surah
            self.save_surah_data(surah, surah_variants)

            logger.info(f"Surah {surah} complete: {len(surah_variants)} variants found")
            time.sleep(1)  # Be nice to the server

        self.variants = all_variants
        self.save_all_data()

        return all_variants

    def scrape_usul(self) -> Dict:
        """Scrape أصول (general rules) for each reader"""
        url = f"{BASE_URL}/index.php?group=tb2"
        soup = self.get_page(url)

        if not soup:
            return {}

        usul = {}
        # Parse usul tables...
        # This needs to be customized based on the actual page structure

        return usul

    def save_surah_data(self, surah: int, variants: List[QiraatVariant]):
        """Save surah data to JSON file"""
        filepath = os.path.join(self.output_dir, f"surah_{surah:03d}.json")
        data = {
            "surah": surah,
            "variants_count": len(variants),
            "variants": [asdict(v) for v in variants]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_all_data(self):
        """Save all data to a single JSON file"""
        filepath = os.path.join(self.output_dir, "all_qiraat.json")

        data = {
            "total_variants": len(self.variants),
            "qurra": QURRA,
            "variants": [asdict(v) for v in self.variants]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self.variants)} variants to {filepath}")


class AlternativeScraper:
    """
    Alternative approach: Scrape from other sources or use existing data
    This can be used if nquran.com is not accessible or has different structure
    """

    @staticmethod
    def parse_bridges_pdf():
        """
        Parse the Bridges Translation PDF for qiraat notes
        The PDF has footnotes marked with 'Q' for qiraat variants
        """
        # This would require PDF parsing library
        pass

    @staticmethod
    def scrape_erquran():
        """
        Scrape from Harvard's Encyclopedia of Quranic Readings
        https://erquran.org/
        """
        pass


def create_sample_data():
    """Create sample qiraat data for testing"""
    sample_variants = [
        QiraatVariant(
            surah=2,
            ayah=184,
            word="فِدْيَةٌ",
            word_position=5,
            variant_type="فرش",
            readings={
                "حفص": "فِدْيَةٌ",
                "ورش": "فِدْيَةٌ",
                "قالون": "فِدْيَةٍ",
            },
            notes="اختلاف في التنوين"
        ),
        QiraatVariant(
            surah=1,
            ayah=4,
            word="مَالِكِ",
            word_position=1,
            variant_type="فرش",
            readings={
                "حفص": "مَالِكِ",
                "عاصم": "مَالِكِ",
                "نافع": "مَلِكِ",
                "ابن كثير": "مَلِكِ",
                "أبو عمرو": "مَلِكِ",
            },
            notes="مالك / ملك - اختلاف في المعنى: صاحب الملك أو الملك"
        ),
        QiraatVariant(
            surah=2,
            ayah=85,
            word="تَظَاهَرُونَ",
            word_position=4,
            variant_type="فرش",
            readings={
                "حفص": "تَظَاهَرُونَ",
                "عاصم": "تَظَاهَرُونَ",
                "ابن عامر": "تَظَّاهَرُونَ",
            },
            notes="بتشديد الظاء أو تخفيفها"
        ),
    ]

    return sample_variants


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape nquran.com for Qiraat data")
    parser.add_argument("--surah", type=int, help="Specific surah to scrape")
    parser.add_argument("--start", type=int, default=1, help="Start surah")
    parser.add_argument("--end", type=int, default=114, help="End surah")
    parser.add_argument("--output", default="../../data/processed/qiraat", help="Output directory")
    parser.add_argument("--sample", action="store_true", help="Generate sample data only")

    args = parser.parse_args()

    if args.sample:
        # Generate sample data
        sample = create_sample_data()
        output_dir = args.output
        os.makedirs(output_dir, exist_ok=True)

        with open(os.path.join(output_dir, "sample_qiraat.json"), 'w', encoding='utf-8') as f:
            json.dump({
                "sample": True,
                "variants": [asdict(v) for v in sample]
            }, f, ensure_ascii=False, indent=2)

        print(f"Sample data saved to {output_dir}/sample_qiraat.json")
    else:
        scraper = NQuranScraper(output_dir=args.output)

        if args.surah:
            variants = scraper.scrape_surah(args.surah)
        else:
            variants = scraper.scrape_all(args.start, args.end)

        print(f"Scraped {len(variants)} variants")
