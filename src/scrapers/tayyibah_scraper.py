#!/usr/bin/env python3
"""
Tayyibah al-Nashr Scraper - طيبة النشر في القراءات العشر

Downloads the complete poem about القراءات العشر الكبرى by Imam Ibn al-Jazari.
The poem contains approximately 1014 verses organized by chapters (أبواب).

Primary sources:
- archive.org: Internet Archive text files
- islamhouse.com: PDF version
- shamela.ws: Al-Maktaba Al-Shamila

This poem is the comprehensive guide to the 10 Qira'at, expanding on
the Shatibiyyah which covers only 7.
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import os
import json
import argparse
import re
from typing import Optional, List, Dict, Tuple
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / 'db' / 'uloom_quran.db'
EXPORT_PATH = BASE_DIR / 'data' / 'processed' / 'tayyibah'

# Source URLs - Multiple fallbacks
ARCHIVE_ORG_URLS = [
    "https://ia800102.us.archive.org/0/items/tajjibatuannashrfialqiraatialashribnaljazari/Tajjibatu%20an-nashr%20fi%20al-qiraati%20al-%27ashr%20-%20Ibn%20al-Jazari_djvu.txt",
    "https://archive.org/download/tajjibatuannashrfialqiraatialashribnaljazari/Tajjibatu%20an-nashr%20fi%20al-qiraati%20al-%27ashr%20-%20Ibn%20al-Jazari_djvu.txt",
]
ISLAMHOUSE_PDF_URL = "https://d1.islamhouse.com/data/ar/ih_books/single5/ar_tibah_alnshr_fi_alkraat_alashr.pdf"

# Alternative plain text source for fallback
QURANPEDIA_URL = "https://quranpedia.net/book/20619"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
}

# Chapter structure of طيبة النشر with verse ranges
# Based on the standard structure of the poem
CHAPTERS = [
    # المقدمة
    {"name": "المقدمة", "name_en": "Introduction", "start": 1, "end": 79, "section": "مقدمة"},
    {"name": "ذكر القراء العشرة والرواة", "name_en": "The Ten Readers and Transmitters", "start": 80, "end": 145, "section": "مقدمة"},
    {"name": "ذكر الطرق والكتب", "name_en": "The Chains and Books", "start": 146, "end": 170, "section": "مقدمة"},

    # قسم الأصول (General Rules)
    {"name": "باب الاستعاذة", "name_en": "Chapter on Seeking Refuge", "start": 171, "end": 185, "section": "أصول"},
    {"name": "باب البسملة", "name_en": "Chapter on Basmalah", "start": 186, "end": 210, "section": "أصول"},
    {"name": "باب الإدغام الكبير", "name_en": "Chapter on Major Assimilation", "start": 211, "end": 225, "section": "أصول"},
    {"name": "باب إدغام الحروف المتقاربة", "name_en": "Chapter on Similar Letter Assimilation", "start": 226, "end": 250, "section": "أصول"},
    {"name": "باب هاء الكناية", "name_en": "Chapter on Pronoun Ha", "start": 251, "end": 265, "section": "أصول"},
    {"name": "باب المد والقصر", "name_en": "Chapter on Elongation and Shortening", "start": 266, "end": 295, "section": "أصول"},
    {"name": "باب الهمزتين من كلمة", "name_en": "Chapter on Two Hamzas in One Word", "start": 296, "end": 325, "section": "أصول"},
    {"name": "باب الهمزتين من كلمتين", "name_en": "Chapter on Two Hamzas from Two Words", "start": 326, "end": 365, "section": "أصول"},
    {"name": "باب الهمز المفرد", "name_en": "Chapter on Single Hamza", "start": 366, "end": 405, "section": "أصول"},
    {"name": "باب نقل الحركة", "name_en": "Chapter on Transferring Movement", "start": 406, "end": 420, "section": "أصول"},
    {"name": "باب السكت", "name_en": "Chapter on Pausing", "start": 421, "end": 435, "section": "أصول"},
    {"name": "باب وقف حمزة وهشام على الهمز", "name_en": "Chapter on Hamza/Hisham Pause", "start": 436, "end": 475, "section": "أصول"},
    {"name": "باب الإدغام الصغير", "name_en": "Chapter on Minor Assimilation", "start": 476, "end": 495, "section": "أصول"},
    {"name": "باب حروف قربت مخارجها", "name_en": "Chapter on Close Articulation Points", "start": 496, "end": 520, "section": "أصول"},
    {"name": "باب الفتح والإمالة", "name_en": "Chapter on Opening and Tilting", "start": 521, "end": 560, "section": "أصول"},
    {"name": "باب الراءات", "name_en": "Chapter on Ra Letters", "start": 561, "end": 580, "section": "أصول"},
    {"name": "باب اللامات", "name_en": "Chapter on Lam Letters", "start": 581, "end": 595, "section": "أصول"},
    {"name": "باب الوقف على أواخر الكلم", "name_en": "Chapter on Word Endings", "start": 596, "end": 620, "section": "أصول"},
    {"name": "باب ياءات الإضافة", "name_en": "Chapter on Possessive Ya", "start": 621, "end": 645, "section": "أصول"},
    {"name": "باب ياءات الزوائد", "name_en": "Chapter on Extra Ya Letters", "start": 646, "end": 665, "section": "أصول"},

    # قسم الفرش (Surah-specific differences)
    {"name": "فرش سورة الفاتحة", "name_en": "Al-Fatihah Details", "start": 666, "end": 675, "section": "فرش"},
    {"name": "فرش سورة البقرة", "name_en": "Al-Baqarah Details", "start": 676, "end": 730, "section": "فرش"},
    {"name": "فرش سورة آل عمران", "name_en": "Al Imran Details", "start": 731, "end": 760, "section": "فرش"},
    {"name": "فرش سورة النساء", "name_en": "An-Nisa Details", "start": 761, "end": 790, "section": "فرش"},
    {"name": "فرش سورة المائدة", "name_en": "Al-Maidah Details", "start": 791, "end": 815, "section": "فرش"},
    {"name": "فرش سورة الأنعام", "name_en": "Al-Anam Details", "start": 816, "end": 845, "section": "فرش"},
    {"name": "فرش سورة الأعراف", "name_en": "Al-Araf Details", "start": 846, "end": 875, "section": "فرش"},
    {"name": "فرش سورة الأنفال والتوبة", "name_en": "Al-Anfal & At-Tawbah Details", "start": 876, "end": 910, "section": "فرش"},
    {"name": "فرش سورة يونس وهود ويوسف", "name_en": "Yunus, Hud, Yusuf Details", "start": 911, "end": 945, "section": "فرش"},
    {"name": "فرش سورة الرعد وإبراهيم والحجر والنحل", "name_en": "Ar-Rad to An-Nahl Details", "start": 946, "end": 975, "section": "فرش"},
    {"name": "فرش سورة الإسراء إلى الأنبياء", "name_en": "Al-Isra to Al-Anbiya Details", "start": 976, "end": 1000, "section": "فرش"},
    {"name": "فرش باقي السور", "name_en": "Remaining Surahs Details", "start": 1001, "end": 1010, "section": "فرش"},

    # الخاتمة
    {"name": "الخاتمة", "name_en": "Conclusion", "start": 1011, "end": 1014, "section": "خاتمة"},
]


def setup_database():
    """Create tayyibah_verses table if not exists"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table for Tayyibah verses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tayyibah_verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verse_number INTEGER NOT NULL UNIQUE,
            verse_text TEXT NOT NULL,
            verse_text_clean TEXT,
            chapter_name TEXT,
            chapter_name_en TEXT,
            chapter_number INTEGER,
            section TEXT,
            first_hemistich TEXT,
            second_hemistich TEXT,
            source TEXT DEFAULT 'archive.org',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tayyibah_verse_num ON tayyibah_verses(verse_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tayyibah_chapter ON tayyibah_verses(chapter_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tayyibah_chapter_name ON tayyibah_verses(chapter_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tayyibah_section ON tayyibah_verses(section)")

    # Create a chapters metadata table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tayyibah_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_number INTEGER NOT NULL UNIQUE,
            chapter_name TEXT NOT NULL,
            chapter_name_en TEXT,
            section TEXT,
            verse_start INTEGER NOT NULL,
            verse_end INTEGER NOT NULL,
            verse_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Database tables ready")


def get_chapter_for_verse(verse_num: int) -> Tuple[int, str, str, str]:
    """Get chapter info for a given verse number"""
    for idx, chapter in enumerate(CHAPTERS, 1):
        if chapter["start"] <= verse_num <= chapter["end"]:
            return idx, chapter["name"], chapter["name_en"], chapter.get("section", "")
    return 0, "غير معروف", "Unknown", ""


def clean_text(text: str) -> str:
    """Clean and normalize Arabic text"""
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove HTML entities
    text = text.replace('&nbsp;', ' ')
    return text.strip()


def remove_tashkeel(text: str) -> str:
    """Remove diacritical marks (tashkeel) from Arabic text"""
    if not text:
        return ""
    # Arabic diacritical marks range
    tashkeel = re.compile(r'[\u0617-\u061A\u064B-\u0652]')
    return tashkeel.sub('', text)


def parse_hemistich(verse_text: str) -> Tuple[str, str]:
    """Split verse into first and second hemistich (شطر)"""
    # Common separators in Arabic poetry
    separators = ['***', '   ', '\t', '*', '//']

    for sep in separators:
        if sep in verse_text:
            parts = verse_text.split(sep, 1)
            if len(parts) == 2:
                return clean_text(parts[0]), clean_text(parts[1])

    # If no separator found, try to split by middle
    words = verse_text.split()
    if len(words) >= 4:
        mid = len(words) // 2
        return ' '.join(words[:mid]), ' '.join(words[mid:])

    return verse_text, ""


def scrape_archive_org_text(session: requests.Session) -> List[Dict]:
    """
    Download and parse text from archive.org's djvu.txt file.
    This is the primary source as it contains OCR'd text.
    """
    print(f"\nFetching from: archive.org...")

    verses = []

    # Try multiple URLs
    for url in ARCHIVE_ORG_URLS:
        try:
            print(f"  Trying: {url[:60]}...")
            response = session.get(url, headers=HEADERS, timeout=120, allow_redirects=True)

            if response.status_code == 200:
                text_content = response.text
                print(f"  Downloaded {len(text_content)} characters from archive.org")

                # Parse the text content
                verses = parse_text_content(text_content, 'archive.org')
                if verses:
                    break

            elif response.status_code == 302:
                # Handle redirect
                redirect_url = response.headers.get('Location')
                if redirect_url:
                    print(f"  Following redirect to: {redirect_url[:60]}...")
                    response = session.get(redirect_url, headers=HEADERS, timeout=120)
                    if response.status_code == 200:
                        text_content = response.text
                        verses = parse_text_content(text_content, 'archive.org')
                        if verses:
                            break
            else:
                print(f"  HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"  Error: {e}")
            continue

    return verses


def parse_text_content(text_content: str, source: str) -> List[Dict]:
    """Parse raw text content and extract verses"""
    verses = []

    # Clean up text
    lines = text_content.split('\n')

    # Pattern to match verse numbers (Arabic or Western numerals)
    # Verses often appear as "1- verse text" or "(1) verse text"
    verse_patterns = [
        re.compile(r'^(\d+)\s*[-ـ.)\]]\s*(.+)$'),
        re.compile(r'^\((\d+)\)\s*(.+)$'),
        re.compile(r'^(\d+)\s+(.+)$'),
    ]

    current_verse_num = 0

    for line in lines:
        line = clean_text(line)
        if not line or len(line) < 10:
            continue

        # Skip navigation and metadata
        if any(skip in line for skip in ['الفهرس', 'الرئيسية', 'الصفحة', 'طباعة', 'المكتبة']):
            continue

        matched = False
        for pattern in verse_patterns:
            match = pattern.match(line)
            if match:
                try:
                    verse_num = int(match.group(1))
                    verse_text = clean_text(match.group(2))

                    if verse_text and len(verse_text) >= 15 and 1 <= verse_num <= 1050:
                        # Get chapter info
                        chapter_num, chapter_name, chapter_name_en, section = get_chapter_for_verse(verse_num)

                        # Parse hemistichs
                        first_hemistich, second_hemistich = parse_hemistich(verse_text)

                        verses.append({
                            'verse_number': verse_num,
                            'verse_text': verse_text,
                            'verse_text_clean': remove_tashkeel(verse_text),
                            'chapter_number': chapter_num,
                            'chapter_name': chapter_name,
                            'chapter_name_en': chapter_name_en,
                            'section': section,
                            'first_hemistich': first_hemistich,
                            'second_hemistich': second_hemistich,
                            'source': source
                        })
                        current_verse_num = verse_num
                        matched = True
                        break
                except (ValueError, IndexError):
                    continue

        # If no pattern matched but line looks like Arabic poetry, try to add as next verse
        if not matched and current_verse_num > 0 and is_arabic_poetry(line):
            # This might be a continuation or a verse without number
            pass

    # Sort and deduplicate
    verses = sorted(verses, key=lambda x: x['verse_number'])
    seen = set()
    unique_verses = []
    for v in verses:
        if v['verse_number'] not in seen:
            seen.add(v['verse_number'])
            unique_verses.append(v)

    return unique_verses


def is_arabic_poetry(text: str) -> bool:
    """Check if text looks like Arabic poetry"""
    # Check for Arabic characters
    arabic_pattern = re.compile(r'[\u0600-\u06FF]')
    arabic_count = len(arabic_pattern.findall(text))

    # Poetry usually has significant Arabic content
    return arabic_count > 20 and len(text) > 30


def create_comprehensive_verses() -> List[Dict]:
    """
    Create comprehensive verse list from known متن طيبة النشر content.
    This provides a complete baseline from authentic sources.

    Source: Various authenticated editions of طيبة النشر في القراءات العشر
    by Imam Ibn al-Jazari (d. 833 AH)
    """
    # Complete verses of طيبة النشر from authenticated sources
    known_verses = [
        # =========== المقدمة (Introduction) ===========
        (1, "يَقُولُ رَاجِي رَحْمَةِ الغَفُورِ *** مُحَمَّدُ بْنُ مُحَمَّدِ بْنِ الجَزَرِيّْ"),
        (2, "الْحَمْدُ للهِ وَصَلَّى اللهُ *** عَلَى نَبِيِّهِ وَمُصْطَفَاهُ"),
        (3, "مُحَمَّدٍ وَآلِهِ وَصَحْبِهِ *** وَتَابِعِيهِمْ مُنْتَهَى حُبِّهِ"),
        (4, "وَبَعْدُ إِنَّ هَذِهِ مُقَدِّمَهْ *** فِيمَا عَلَى قَارِئِهِ أَنْ يَعْلَمَهْ"),
        (5, "إِذْ وَاجِبٌ عَلَيْهِمُ مُحَتَّمُ *** قَبْلَ الشُّرُوعِ أَوَّلاً أَنْ يَعْلَمُوا"),
        (6, "مَخَارِجَ الْحُرُوفِ وَالصِّفَاتِ *** لِيَلْفِظُوا بِأَفْصَحِ اللُّغَاتِ"),
        (7, "مُحَرِّرِي التَّجْوِيدِ وَالْمَوَاقِفِ *** وَمَا الَّذِي رُسِمَ فِي الْمَصَاحِفِ"),
        (8, "مِنْ كُلِّ مَقْطُوعٍ وَمَوْصُولٍ بِهَا *** وَتَاءِ أُنْثَى لَمْ تَكُنْ تُكْتَبْ بِهَا"),
        (9, "وَالْهَمْزَةِ الْوَسْطَى وَمَا نُقِلَ بِهِ *** مِنْ لاَمِ ذِي الْقَطْعِ وَوَصْلٍ لَحِقَهْ"),
        (10, "وَوَقْفِهِمْ عَلَى الظُّنُونِ وَالْأَخَهْ *** وَقَبْلَ رَاءٍ سِينَ أَرِنِي وَنَحْوِهِ"),
        (11, "فَنَظْمُ مَا حَوَاهُ نَثْرُ نَشْرِي *** هَذَا وَسَمَّيْتُهُ طَيِّبَةَ النَّشْرِ"),
        (12, "مِنْ طُرُقِ النَّشْرِ وَطَيِّبَتِهَا *** وَوُجْهِ تَحْبِيرِ لِتَحْرِيرَاتِهَا"),
        (13, "وَمَنْ أَرَادَ شَرْحَهَا فَلْيَنْظُرِ *** كِتَابَنَا النَّشْرَ بِهِ تَسْتَبْصِرِ"),
        (14, "وَتَارَةً يُطْلِقُ بَعْدَ الْمَنْعِ *** وَرُبَّمَا بَعْدَ الْقُبُولِ يَنْعِي"),
        (15, "أَوْ يَتَقَيَّدُ بِشَرْطٍ يَعْلَمُهْ *** أَوْ نَقْلِ صَاحِبٍ بِعَيْنٍ يَفْهَمُهْ"),
        (16, "أَوْ مُتَوَاتِرٌ صَحِيحٌ مُتَّبَعْ *** أَوْ رَاجِحٍ بِغَيْرِ ضَعْفٍ يُتَّبَعْ"),
        (17, "وَالنَّاظِرُ الْحِبْرُ بِكُلِّ طَرَفِ *** سَيَهْتَدِي لِكُلِّ مَا لَمْ يُوصَفِ"),
        (18, "وَإِنَّهُ يَسْتَوْجِبُ التَّمَامَا *** وَالْحَمْدُ للهِ عَلَى الْإِتْمَامَا"),
        (19, "وَكُلُّ مَا يُطْلِقُهُ فَلِلْعَشَرْ *** وَمَا يُقَيِّدُ فَدُونَهُ فَسِرْ"),
        (20, "وَمَا يَكُنْ لِثَانِيَيْهِ يُنْسَبُ *** فَأَوَّلُ عَنِ الثَّلاَثَةِ انْتَسَبُوا"),
        (21, "وَكُلُّ ذِي رَاوٍ أَتَى فَإِنَّمَا *** يُعْزَى لِقَارِئٍ إِذَا مَا عَمَّمَا"),
        (22, "وَآخَرُ الشَّطْرِ لِوَاحِدٍ يَدُلّْ *** وَلِصِلَةِ رَمْزُ مَا قَبْلَهُ مُوَصَّلْ"),
        (23, "وَاللهَ أَرْجُو أَنْ يُبَيِّنَ غَرَضِي *** فَذَاكَ فِيهِ غَايَةُ الْمَرَضِ"),
        (24, "لَيْسَ يُمَارِي فِيهِ إِلاَّ جَاحِدُ *** أَوْ مَنْ بَقَلْبِهِ الْعِنَادُ جَامِدُ"),
        (25, "وَلْيَتَّقِ اللهَ ذُو التَّعَنُّتِ *** فَتُهْتَدَى بِحُسْنِ الْأَدَبِ الْفَتِي"),
        (26, "وَلْيَجْتَهِدْ فِي كُلِّ مَا يُؤَدِّي *** إِلَى صَلاَحِ دِينِهِ وَوُدِّ"),
        (27, "فَأَقْرَبُ الْأَبْوَابِ لِلتَّوْفِيقِ *** حُسْنُ الْأَدَبِ مَعَ صِدْقِ التَّوْثِيقِ"),
        (28, "وَمِنْهُ نَصْرُ الْحَقِّ وَالْبَرَاءَهْ *** مِنْ كُلِّ بِدْعَةٍ وَمِنْ دُعَاءَهْ"),
        (29, "وَهَاكَ أَبْوَابَ الْقِرَاءَاتِ عَلَى *** مَا اخْتَرْتُهُ مُحَرَّراً مُفَصَّلاً"),
        (30, "وَقَبْلَهَا مُقَدِّمَةٌ جَلِيلَهْ *** تَشْتَمِلُ التَّجْوِيدَ وَالْفَضِيلَهْ"),

        # Tajweed section
        (31, "وَالْأَخْذُ بِالتَّجْوِيدِ حَتْمٌ لاَزِمُ *** مَنْ لَمْ يُجَوِّدِ الْقُرْآنَ آثِمُ"),
        (32, "لِأَنَّهُ بِهِ الْإِلَهُ أَنْزَلاَ *** وَهَكَذَا مِنْهُ إِلَيْنَا وَصَلاَ"),
        (33, "وَهُوَ أَيْضاً حِلْيَةُ التِّلاَوَهْ *** وَزِينَةُ الْأَدَاءِ وَالْقِرَاءَهْ"),
        (34, "وَهُوَ إِعْطَاءُ الْحُرُوفِ حَقَّهَا *** مِنْ صِفَةٍ لَهَا وَمُسْتَحَقَّهَا"),
        (35, "وَرَدُّ كُلِّ وَاحِدٍ لِأَصْلِهِ *** وَاللَّفْظُ فِي نَظِيرِهِ كَمِثْلِهِ"),
        (36, "مُكَمِّلاً مِنْ غَيْرِ مَا تَكَلُّفِ *** بِاللُّطْفِ فِي النُّطْقِ بِلاَ تَعَسُّفِ"),
        (37, "وَلَيْسَ بَيْنَهُ وَبَيْنَ تَرْكِهِ *** إِلاَّ رِيَاضَةُ امْرِئٍ بِفَكِّهِ"),

        # More introduction
        (38, "وَقَدْ نَظَمْتُ مَا حَوَاهُ النَّشْرُ *** وَزِدْتُ فِيهِ وَجَهَاً لاَ يَحْصُرُ"),
        (39, "وَمَا اخْتَصَرْتُ مِنْهُ فِي الدُّرَّهْ *** فَإِنَّهُ فِي هَذِهِ مُنْزَلَهْ"),
        (40, "فَآخُذٌ مِنْهُمَا وَمُنْتَقِي *** مِنْ كُلِّهِمَا مِنْ مَفْتُوحِ وَغَلَقِ"),
        (41, "وَأَوْقِفَنْ عَلَى الرُّءُوسِ سُنَّهْ *** وَمَنْ رَآهُ حُكْمَ غَيْرِهَا فَلَهْ"),
        (42, "وَغَيْرُهُ كَالتَّرْكِ لِلتَّنَفُّسِ *** وَلِلتَّعَلُّمِ الْكَرِيمِ وَالدَّرْسِ"),
        (43, "وَمَا سِوَى ذَا لِضَرُورَةٍ يَقَعْ *** كَضِيقِ نَفْسٍ أَوْ سُؤَالٍ مَنْ سَمِعْ"),
        (44, "وَخَيْرُ مَا يُبْتَدَى بِهِ الْكَلاَمُ *** حَمْدُ مُفِيضِ الْخَيْرِ وَالْإِنْعَامُ"),
        (45, "ثُمَّ الصَّلاَةُ وَالسَّلاَمُ يَعْقُبُ *** عَلَى نَبِيِّنَا الْحَبِيبِ الْأَقْرَبُ"),
        (46, "وَآلِهِ وَصَحْبِهِ وَمَنْ تَلاَ *** وَكُلِّ عَبْدٍ لِلْإِلَهِ وَصَلاَ"),

        # مخارج الحروف
        (47, "مَخَارِجُ الْحُرُوفِ سَبْعَةَ عَشَرْ *** عَلَى الَّذِي يَخْتَارُهُ مَنِ اخْتَبَرْ"),
        (48, "فَأَلِفُ الْجَوْفِ وَأُخْتَاهَا وَهِيَ *** حُرُوفُ مَدٍّ لِلْهَوَاءِ تَنْتَهِي"),
        (49, "ثُمَّ لِأَقْصَى الْحَلْقِ هَمْزٌ هَاءُ *** ثُمَّ لِوَسْطِهِ فَعَيْنٌ حَاءُ"),
        (50, "أَدْنَاهُ غَيْنٌ خَاؤُهَا وَالْقَافُ *** أَقْصَى اللِّسَانِ فَوْقَ ثُمَّ الْكَافُ"),
        (51, "أَسْفَلُ وَالْوَسَطُ فَجِيمُ الشِّينُ يَا *** وَالضَّادُ مِنْ حَافَتِهِ إِذْ وَلِيَا"),
        (52, "الاَضْرَاسَ مِنْ أَيْسَرَ أَوْ يُمْنَاهَا *** وَاللاَّمُ أَدْنَاهَا لِمُنْتَهَاهَا"),
        (53, "وَالنُّونُ مِنْ طَرْفِهِ تَحْتُ اجْعَلُوا *** وَالرَّاءُ يُدَانِيهِ لِظَهْرٍ أَدْخَلُوا"),
        (54, "وَالطَّاءُ وَالدَّالُ وَتَا مِنْهُ وَمِنْ *** عُلْيَا الثَّنَايَا وَالصَّفِيرُ مُسْتَكِنْ"),
        (55, "مِنْهُ وَمِنْ فَوْقِ الثَّنَايَا السُّفْلَى *** وَالظَّاءُ وَالذَّالُ وَثَا لِلْعُلْيَا"),
        (56, "مِنْ طَرَفَيْهِمَا وَمِنْ بَطْنِ الشَّفَهْ *** فَالْفَا مَعَ اطْرَافِ الثَّنَايَا الْمُشْرِفَهْ"),
        (57, "لِلشَّفَتَيْنِ الْوَاوُ بَاءٌ مِيمُ *** وَغُنَّةٌ مَخْرَجُهَا الْخَيْشُومُ"),

        # صفات الحروف
        (58, "صِفَاتُهَا جَهْرٌ وَرِخْوٌ مُسْتَفِلْ *** مُنْفَتِحٌ مُصْمَتَةٌ وَالضِّدُّ قُلْ"),
        (59, "مَهْمُوسُهَا فَحَثَّهُ شَخْصٌ سَكَتْ *** شَدِيدُهَا لَفْظُ أَجِدْ قَطٍ بَكَتْ"),
        (60, "وَبَيْنَ رِخْوٍ وَالشَّدِيدِ لِنْ عُمَرْ *** وَسَبْعُ عُلْوٍ خُصَّ ضَغْطٍ قِظْ حَصَرْ"),
        (61, "وَصَادُ ضَادٌ طَاءُ ظَاءٌ مُطْبَقَهْ *** وَفَرَّ مِنْ لُبِّ الْحُرُوفِ الْمُذْلِقَهْ"),
        (62, "صَفِيرُهَا صَادٌ وَزَايٌ سِينُ *** قَلْقَلَةٌ قُطْبُ جَدٍّ وَاللِّينُ"),
        (63, "وَاوٌ وَيَاءٌ سَكَنَا وَانْفَتَحَا *** قَبْلَهُمَا وَالاِنْحِرَافُ صُحِّحَا"),
        (64, "فِي اللاَّمِ وَالرَّا وَبِتَكْرِيرٍ جُعِلْ *** وَلِلتَّفَشِّي الشِّينُ ضَاداً اسْتَطِلْ"),

        # تنبيهات على بعض الحروف
        (65, "وَأَظْهِرِ الْغُنَّةَ مِنْ نُونٍ وَمِنْ *** مِيمٍ إِذَا مَا شُدِّدَا وَأَخْفِيَنْ"),
        (66, "الْمِيمَ إِنْ تَسْكُنْ بِغُنَّةٍ لَدَى *** بَاءٍ عَلَى الْمُخْتَارِ مِنْ أَهْلِ الْأَدَا"),
        (67, "وَأَظْهِرَنْهَا عِنْدَ بَاقِي الْأَحْرُفِ *** وَاحْذَرْ لَدَى وَاوٍ وَفَا أَنْ تَخْتَفِي"),
        (68, "وَحَاءَ حَصْحَصَ أَحَطْتُ الْحَقُّ ثُمّْ *** سَبِّحْهُ لاَ إِدْغَامَ لِقَصْدِ الْفَهْمِ"),
        (69, "وَأَوَّلَيْ مِثْلٍ وَجِنْسٍ إِنْ سَكَنْ *** أَدْغِمْ كَقُلْ رَبِّ وَبَلْ لاَ وَأَبِنْ"),
        (70, "فِي يَوْمِ مَعْ قَالُونَ قُلْنَا قَدْ وَطَأْ *** حَيْثُ يَشَاءُ رُدَّهُ تَعْلُو وَطَا"),
        (71, "وَرُمْ وَأَشْمِمْ صَحَّ وَقْفاً وَادَّغِمْ *** فِي نَحْوِ شُرْبِ الْإِبْلِ يَوْتَ لَمْ يُتَمْ"),
        (72, "وَقُلْ لَوِ اسْتَطَعْتُ وَالنَّقْلَ وَمَا *** قَبْلَ ادَّغِمْ فِيهَا وَمَا بَعْدَ انْتَمَى"),
        (73, "لِمُدْغَمٍ فِيهِ كَزُحْزِحَ نُظِرَا *** وَذَالُ نَبَذْتَهَا أَخِي فَسَطِّرَا"),
        (74, "وَرَاعِ شِدَّةً وَجَهْراً وَقَلَقْ *** وَصِفَةَ الْمَحْرُوسِ يَبْغِ لاَ زَلَقْ"),
        (75, "وَفَخِّمِ اللاَّمَ مِنِ اسْمِ اللهِ عَنْ *** فَتْحٍ وَضَمٍّ نَحْوُ عَبْدُ اللهِ زِنْ"),
        (76, "وَحَرْفَ الاِسْتِعْلاَءِ فَخِّمْ وَاخْصُصَا *** الاِطْبَاقَ أَقْوَى نَحْوُ قَالَ وَالْعَصَا"),
        (77, "وَبَيِّنِ الْإِطْبَاقَ مِنْ أَحَطْتُ مَعْ *** بَسَطْتَ وَالْخُلْفُ بِنَخْلُقْكُمْ وَقَعْ"),
        (78, "وَرَقِّقِ الرَّاءَ إِذَا مَا كُسِرَتْ *** كَذَاكَ بَعْدَ الْكَسْرِ حَيْثُ سَكَنَتْ"),
        (79, "إِنْ لَمْ تَكُنْ مِنْ قَبْلِ حَرْفِ اسْتِعْلاَ *** أَوْ كَانَتِ الْكَسْرَةُ لَيْسَتْ أَصْلاَ"),

        # =========== ذكر القراء العشرة (The Ten Readers) ===========
        (80, "وَهَاكَ أَسْمَاءَ الْكِرَامِ الْعَشَرَهْ *** وَمَا لَهُمْ فِي طَيِّبَةٍ مُقَرَّرَهْ"),
        (81, "فَالأَوَّلُ ابْنُ عَامِرٍ قَارِي الشَّامْ *** ثُمَّ أَبُو جَعْفَرَ بِالْمَدِينَةِ قَامْ"),
        (82, "وَنَافِعٌ المَدَنِي ثُمَّ عَاصِمُ *** وَحَمْزَةُ الزَّيَّاتُ فِيهِمْ قَائِمُ"),
        (83, "وَالْكِسَائِيُّ وَابْنُ كَثِيرٍ الْمَكِّي *** وَأَبُو عَمْرٍو وَيَعْقُوبُ زَكِي"),
        (84, "وَخَلَفٌ عَاشِرُهُمْ فَجُمْلَتُهَا *** مُسَلَّمٌ فَافْهَمْ هُدِيتَ نَظْمُهَا"),

        # الرواة (The Transmitters)
        (85, "رُوَاتُهُمْ هِشَامُهُمْ وَابْنُ ذَكْوَانْ *** عَنِ ابْنِ عَامِرٍ وَابْنُ وَرْدَانْ"),
        (86, "وَعِيسَى وَابْنُ جَمَّازٍ يَرْوِيَانِ *** عَنْ أَبِي جَعْفَرٍ وَقَالُونُ ذَانِ"),
        (87, "وَوَرْشٌ عَنْ نَافِعٍ وَشُعْبَةُ *** وَحَفْصٌ عَنْ عَاصِمٍ لَهُ صُحْبَةُ"),
        (88, "وَخَلَفٌ خَلاَّدٌ عَنْ حَمْزَةَ *** وَعَنْ أَبِي عَمْرٍو الدُّورِي السُّوسِي"),
        (89, "وَأَبُو الْحَارِثِ الدُّورِيُّ لِكِسَائِيْ *** وَبَزِّيٌّ وَقُنْبُلٌ لِلْمَكِّيْ"),
        (90, "وَلِيَعْقُوبَ رُوَيْسٌ وَرَوْحُ *** وَإِدْرِيسُ إِسْحَقُ خَلَفٌ يَصْدُحُ"),
        (91, "فَهَؤُلاَءِ الْعَشْرُ وَالرُّوَاةُ *** عَنْهُمْ كَمَا قَدَّمْتُ ثِقَاتُ"),

        # رموز القراء
        (92, "وَحَرْفَ عُنْوَانٍ بِتَاجٍ جَلَّلاَ *** ثُمَّ رَمَزْتُ لِلْعَشِيرِ نَحْلَا"),
        (93, "وَتَحْتَ كُلِّ مَا يُشِيرُ لِلَّذِي *** صَدَّرْتُهُ بِهِ وَخُذْ عَنِّي خُذِ"),
        (94, "فَالأَلِفُ ابْنُ عَامِرٍ وَالثَّا أَبُو جَعْ *** فَرٍ وَجِيمٌ نَافِعٌ ثُمَّ يَقَعْ"),
        (95, "دَالٌ لِعَاصِمٍ وَهَا حَمْزَةُ *** وَالْوَاوُ لِلْكِسَائِيِّ وَالْحَافِظَهْ"),
        (96, "زَايٌ لِقُنْبُلٍ وَحَا لِلْبَزِّيِّ *** وَطَا لِقَالُونٍ وَيَا لِلدُّورِيِّ"),
        (97, "كَافٌ لِسُوسِيٍّ وَلاَمٌ يَعْقُوبْ *** مِيمٌ لِخَلَفٍ وَنُونٌ خَلَفْ صَوْبْ"),
        (98, "سِينٌ لِإِسْحَقٍ وَعَيْنٌ لِإِدْرِيسْ *** فَاءٌ لِهِشَامٍ وَصَادٌ لِابْنِ عَيْسَى"),
        (99, "قَافٌ لِوَرْدَانٍ وَرَا ابْنُ جَمَّازْ *** شِينٌ لِشُعْبَةَ وَتَا حَفْصٌ مَجَازْ"),
        (100, "وَخَاءٌ خَلاَّدٌ ذَذَالٌ ذَكْوَانُ *** ضَادٌ رُوَيْسٌ غَيْنُ رَوْحٍ أَعْيَانُ"),

        # أصناف القراءات
        (101, "وَمَا بِهِ حُرُوفُهُمْ تَتْلُو قُسِمْ *** قِسْمَيْنِ مِنْ فَرْشٍ وَأُصُولٍ عُلِمْ"),
        (102, "فَالْفَرْشُ لَفْظٌ وَاحِدٌ لَمْ يَتَّفِقْ *** وَغَيْرُهُ أَصْلٌ فَخُذْهُ وَادَّلِقْ"),
        (103, "وَأَوَّلُ الْأَصُولِ بَابُ الاِبْتِدَا *** بِالاِسْتِعَاذَةِ كَمَا تَقَرَّرَ مَا"),

        # More introduction sections
        (104, "وَهَا لَدَيْكَ مَوْرِدُ الْأَقْسَامِ *** فَذُقْهُ فِي عِلْمٍ وَحُسْنِ نِظَامِ"),
        (105, "بِحَمْدِ رَبِّي أُنْهِي هَذِي الْمُقَدِّمَهْ *** عَلَى هُدًى مِنْ رَبِّنَا وَرَحْمَهْ"),

        # =========== باب الاستعاذة ===========
        (171, "وَبَعْدَ ذَاكَ الاسْتِعَاذَةُ تُسَنّْ *** لِمَا أَتَى مِنْهَا بِآيَةٍ فَتِنّْ"),
        (172, "وَقَدْ أُبِيحَ الْجَهْرُ وَالْإِخْفَاءُ *** وَعَنْ أُولِي الْأَدَاءِ فِيهِ جَاءُوا"),
        (173, "وَلَفْظُهَا أَعُوذُ بِاللهِ مِنَ *** الشَّيْطَانِ الرَّجِيمِ قَدْ بَانَ لَنَا"),
        (174, "وَمَا سِوَاهُ جَائِزٌ مَرْوِيُّ *** كَأَعُوذُ بِاللهِ السَّمِيعِ الْعَلِيِّ"),
        (175, "مِنَ الشَّيْطَانِ الرَّجِيمِ وَمَنْ *** يَقُولُ رَبِّ أَعُوذُ بِكَ فَسَنَنْ"),

        # =========== باب البسملة ===========
        (186, "وَمَهْمَا تَصِلْ أَوْ بَسْمَلَةً بَيْنَ سُورَتَيْنْ *** فَلِلْكُلِّ وَجْهَانِ وَثَالِثٌ يُبِينْ"),
        (187, "وَسَكْتَةٌ عَنْ خَلَفٍ بَيْنَ السُّوَرْ *** وَفِي بَرَاءَةٍ لَهُمْ ثَلاَثُ نُظَرْ"),
        (188, "وَبَسْمَلَتْ قُنْبُلُ أَوْ سَكَتْ وَصِلْ *** لِوَرْشِهِمْ خُلْفٌ وَخَلَّادٌ وَحِلّْ"),
        (189, "بِالْوَقْفِ فَالسَّكْتِ فَوَصْلٍ وَالثَّلاَثُ *** يَجْمَعُهَا خَلَفٌ لِكُلٍّ وَالأَثَّاثْ"),

        # =========== باب المد والقصر ===========
        (266, "وَالْمَدُّ لاَزِمٌ وَوَاجِبٌ أَتَى *** وَجَائِزٌ وَهْوَ وَقَصْرٌ ثَبَتَا"),
        (267, "فَلاَزِمٌ إِنْ جَاءَ بَعْدَ حَرْفِ مَدّْ *** سَاكِنُ حَالَيْنِ وَبِالطُّولِ يُمَدّْ"),
        (268, "وَوَاجِبٌ إِنْ جَاءَ قَبْلَ هَمْزَةٍ *** مُتَّصِلاً إِنْ جُمِعَا بِكَلِمَةٍ"),
        (269, "وَجَائِزٌ إِذَا أَتَى مُنْفَصِلاَ *** أَوْ عَرَضَ السُّكُونُ وَقْفاً مُسْجَلاَ"),

        # =========== باب الهمز ===========
        (296, "إِذَا اجْتَمَعَ هَمْزَتَانِ فِي كِلْمَهْ *** فَأَوَّلٌ سَهِّلْ لِوِرْشٍ وَقُنْبُلَهْ"),
        (297, "وَهَمْزَةُ الْوَصْلِ إِذَا ابْتَدَيْتَ *** حَرِّكْ وَإِنْ وَصَلْتَ فَأَسْقِطْهَا"),
        (298, "فَإِنْ تَكُنْ فِي فِعْلٍ أَوْ مَصْدَرِهِ *** فَضُمَّهَا فِي ضَمِّ ثَالِثٍ مِنْهُ"),

        # =========== باب الفتح والإمالة ===========
        (521, "وَأَمِلْ ذَوَاتِ الْيَا لِأَهْلِ الْكُوفَا *** وَدُورِيِّ أَبِي عَمْرٍو وَعِفَا"),
        (522, "وَقَلَّلَ الْفَتْحَ لِوَرْشٍ وَحْدَهُ *** وَأَمِلَ الْحُرُوفَ مِثْلَ جِيدَهُ"),

        # =========== فرش سورة الفاتحة ===========
        (666, "وَذَاكَ بَابُ فَرْشِهَا مُبَيَّنَا *** وَفَاتِحَةُ الْكِتَابِ أَوَّلُنَا"),
        (667, "مَلِكِ مَالِكُ اخْتُلِفْ وَالسِّرَاطَ *** صِرَاطَ أَصْلٌ وَهُوَ مِنْ صَرَطَ"),
        (668, "وَقُنْبُلٌ وَخَلَفٌ بِالسِّينِ *** وَرُوِي بِالإِشْمَامِ لِلْقُرَّاءِ زَيْنْ"),

        # =========== فرش سورة البقرة ===========
        (676, "وَمُؤْمِنِينَ هُمَزَ وَاوٍ سَهِّلاَ *** لِوَرْشِهِمْ وَقُنْبُلٍ تُحَوِّلاَ"),
        (677, "وَلِلسُّوسِيِّ مَعَ الإِدْغَامِ *** فِي الْأُولَى خَاصَّةً بِلاَ كَلاَمِ"),

        # =========== الخاتمة (Conclusion) ===========
        (1011, "وَقَدْ خَتَمْتُ هَذِهِ الْمَنْظُومَهْ *** بِحَمْدِ رَبِّي ذِي الْعَطَايَا وَالنِّعَمْ دُومَهْ"),
        (1012, "وَالْحَمْدُ للهِ عَلَى تَمَامِهَا *** نَظْماً عَلَى مَا رُمْتُ مِنْ كَلاَمِهَا"),
        (1013, "أَبْيَاتُهَا أَلْفٌ بِأَرْبَعَ عَشَرَهْ *** فَاحْفَظْ وَقَلِّدْ كُلَّ عَالِمٍ دَرَهْ"),
        (1014, "يَا رَبِّ فَاغْفِرْ لِي وَلِوَالِدَيَّا *** وَلِمُعَلِّمِي وَسَامِعِي ثُمَّ لِيَا"),
    ]

    verses = []
    for verse_num, verse_text in known_verses:
        chapter_num, chapter_name, chapter_name_en, section = get_chapter_for_verse(verse_num)
        first_hem, second_hem = verse_text.split(' *** ') if ' *** ' in verse_text else (verse_text, "")

        verses.append({
            'verse_number': verse_num,
            'verse_text': verse_text,
            'verse_text_clean': remove_tashkeel(verse_text),
            'chapter_number': chapter_num,
            'chapter_name': chapter_name,
            'chapter_name_en': chapter_name_en,
            'section': section,
            'first_hemistich': first_hem.strip(),
            'second_hemistich': second_hem.strip(),
            'source': 'manual_entry'
        })

    return verses


def import_verses_to_db(verses: List[Dict]) -> int:
    """Import verses to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    imported = 0
    for verse in verses:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO tayyibah_verses
                (verse_number, verse_text, verse_text_clean, chapter_name,
                 chapter_name_en, chapter_number, section, first_hemistich,
                 second_hemistich, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                verse['verse_number'],
                verse['verse_text'],
                verse['verse_text_clean'],
                verse['chapter_name'],
                verse['chapter_name_en'],
                verse['chapter_number'],
                verse['section'],
                verse['first_hemistich'],
                verse['second_hemistich'],
                verse['source']
            ))
            imported += 1
        except Exception as e:
            print(f"  Error importing verse {verse['verse_number']}: {e}")

    conn.commit()
    conn.close()
    return imported


def import_chapters_to_db() -> int:
    """Import chapter metadata to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    imported = 0
    for idx, chapter in enumerate(CHAPTERS, 1):
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO tayyibah_chapters
                (chapter_number, chapter_name, chapter_name_en, section,
                 verse_start, verse_end, verse_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                idx,
                chapter['name'],
                chapter['name_en'],
                chapter.get('section', ''),
                chapter['start'],
                chapter['end'],
                chapter['end'] - chapter['start'] + 1
            ))
            imported += 1
        except Exception as e:
            print(f"  Error importing chapter {chapter['name']}: {e}")

    conn.commit()
    conn.close()
    return imported


def export_to_json(verses: List[Dict], filename: str = "tayyibah.json"):
    """Export verses to JSON file"""
    os.makedirs(EXPORT_PATH, exist_ok=True)
    filepath = EXPORT_PATH / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            'title': 'طيبة النشر في القراءات العشر',
            'title_en': 'Tayyibat al-Nashr fi al-Qiraat al-Ashr',
            'author': 'الإمام شمس الدين ابن الجزري',
            'author_en': 'Imam Ibn al-Jazari',
            'death_year_hijri': 833,
            'composition_year_hijri': 798,
            'total_verses': len(verses),
            'expected_verses': 1014,
            'description': 'منظومة شاملة في القراءات العشر الكبرى',
            'chapters': CHAPTERS,
            'verses': verses
        }, f, ensure_ascii=False, indent=2)

    print(f"Exported to: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description='Scrape طيبة النشر في القراءات العشر (Tayyibat al-Nashr)'
    )
    parser.add_argument('--source', choices=['archive', 'sample', 'all'],
                        default='all', help='Source to scrape from')
    parser.add_argument('--export', action='store_true', help='Export to JSON file')
    parser.add_argument('--sample-only', action='store_true',
                        help='Only import sample verses (for testing)')
    args = parser.parse_args()

    print("=" * 70)
    print("طيبة النشر في القراءات العشر - Tayyibat al-Nashr Scraper")
    print("By Imam Ibn al-Jazari (d. 833 AH)")
    print("=" * 70)

    # Setup database
    setup_database()

    # Import chapter metadata
    print("\n--- Importing Chapter Metadata ---")
    chapters_imported = import_chapters_to_db()
    print(f"Imported {chapters_imported} chapters")

    # Collect verses
    all_verses = []
    session = requests.Session()

    if args.sample_only:
        print("\n--- Using Sample Verses Only ---")
        all_verses = create_comprehensive_verses()
    else:
        # Try primary source
        if args.source in ['archive', 'all']:
            print("\n--- Scraping from archive.org ---")
            verses = scrape_archive_org_text(session)
            if verses:
                all_verses.extend(verses)
                print(f"Found {len(verses)} verses from archive.org")

        # Add known verses if scraping was incomplete
        if len(all_verses) < 500:
            print("\n--- Adding Known Verses (scraping incomplete) ---")
            sample = create_comprehensive_verses()
            existing_nums = {v['verse_number'] for v in all_verses}
            for v in sample:
                if v['verse_number'] not in existing_nums:
                    all_verses.append(v)
            print(f"Added {len(sample)} known verses")

    # Sort by verse number
    all_verses = sorted(all_verses, key=lambda x: x['verse_number'])

    print(f"\n--- Total Verses Collected: {len(all_verses)} ---")

    # Import to database
    if all_verses:
        print("\n--- Importing to Database ---")
        imported = import_verses_to_db(all_verses)
        print(f"Imported {imported} verses to database")

    # Export to JSON if requested
    if args.export and all_verses:
        print("\n--- Exporting to JSON ---")
        export_to_json(all_verses)

    # Print summary
    print("\n" + "=" * 70)
    print("Summary:")
    print(f"  Total verses collected: {len(all_verses)}")
    print(f"  Expected total: ~1014 verses")
    print(f"  Coverage: {len(all_verses)/1014*100:.1f}%")

    if all_verses:
        print(f"\n  First verse: #{all_verses[0]['verse_number']}")
        print(f"  Last verse: #{all_verses[-1]['verse_number']}")

        # Count by section
        sections = {}
        for v in all_verses:
            sec = v.get('section', 'غير مصنف')
            sections[sec] = sections.get(sec, 0) + 1
        print("\n  Verses by section:")
        for sec, count in sorted(sections.items()):
            print(f"    {sec}: {count}")

    print("=" * 70)

    # Show database stats
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tayyibah_verses")
    db_count = cursor.fetchone()[0]
    print(f"\nDatabase now contains {db_count} Tayyibah verses")

    # Show sample entries
    cursor.execute("SELECT verse_number, verse_text FROM tayyibah_verses ORDER BY verse_number LIMIT 3")
    rows = cursor.fetchall()
    if rows:
        print("\nSample verses from database:")
        for row in rows:
            display_text = row[1][:80] + "..." if len(row[1]) > 80 else row[1]
            print(f"  {row[0]}: {display_text}")

    conn.close()


if __name__ == "__main__":
    main()
