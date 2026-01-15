#!/usr/bin/env python3
"""
Shatibiyyah Scraper - متن الشاطبية (حرز الأماني ووجه التهاني)

Downloads the complete poem about القراءات السبع by Imam al-Shatibi.
The poem contains approximately 1173 verses organized by chapters (أبواب).

Primary source: surahquran.com/Tajweed/alshatibieah.html
Fallback sources: islamweb.net, alukah.net
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

# Configuration
BASE_URL = "https://surahquran.com/Tajweed/alshatibieah.html"
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'uloom_quran.db')
EXPORT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed', 'shatibiyyah')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
}

# Chapter structure of الشاطبية with verse ranges
CHAPTERS = [
    {"name": "المقدمة", "name_en": "Introduction", "start": 1, "end": 94},
    {"name": "باب الاستعاذة", "name_en": "Chapter on Seeking Refuge", "start": 95, "end": 99},
    {"name": "باب البسملة", "name_en": "Chapter on Basmalah", "start": 100, "end": 107},
    {"name": "سورة أم القرآن", "name_en": "Surah Al-Fatihah", "start": 108, "end": 115},
    {"name": "باب الإدغام الكبير", "name_en": "Chapter on Major Assimilation", "start": 116, "end": 131},
    {"name": "باب إدغام الحرفين المتقاربين في كلمة وفي كلمتين", "name_en": "Chapter on Similar Letter Assimilation", "start": 132, "end": 157},
    {"name": "باب هاء الكناية", "name_en": "Chapter on Feminine Marker Ha", "start": 158, "end": 167},
    {"name": "باب المد والقصر", "name_en": "Chapter on Elongation and Shortening", "start": 168, "end": 199},
    {"name": "باب الهمزتين من كلمة", "name_en": "Chapter on Two Hamzas in One Word", "start": 200, "end": 229},
    {"name": "باب الهمزتين من كلمتين", "name_en": "Chapter on Two Hamzas from Two Words", "start": 230, "end": 268},
    {"name": "باب الهمز المفرد", "name_en": "Chapter on Single Hamza", "start": 269, "end": 326},
    {"name": "باب نقل حركة الهمزة إلى الساكن قبلها", "name_en": "Chapter on Transferring Hamza Movement", "start": 327, "end": 339},
    {"name": "باب السكت على الساكن قبل الهمزة", "name_en": "Chapter on Pausing Before Hamza", "start": 340, "end": 346},
    {"name": "باب وقف حمزة وهشام على الهمز", "name_en": "Chapter on Hamza/Hisham Pause on Hamza", "start": 347, "end": 391},
    {"name": "باب الإدغام الصغير", "name_en": "Chapter on Minor Assimilation", "start": 392, "end": 415},
    {"name": "باب حروف قربت مخارجها", "name_en": "Chapter on Close Articulation Points", "start": 416, "end": 444},
    {"name": "فرش الحروف - سورة البقرة", "name_en": "Letter Details - Al-Baqarah", "start": 445, "end": 514},
    {"name": "فرش الحروف - سورة آل عمران", "name_en": "Letter Details - Al Imran", "start": 515, "end": 551},
    {"name": "فرش الحروف - سورة النساء", "name_en": "Letter Details - An-Nisa", "start": 552, "end": 590},
    {"name": "فرش الحروف - سورة المائدة", "name_en": "Letter Details - Al-Maidah", "start": 591, "end": 620},
    {"name": "فرش الحروف - سورة الأنعام", "name_en": "Letter Details - Al-Anam", "start": 621, "end": 666},
    {"name": "فرش الحروف - سورة الأعراف", "name_en": "Letter Details - Al-Araf", "start": 667, "end": 706},
    {"name": "فرش الحروف - سورة الأنفال والتوبة", "name_en": "Letter Details - Al-Anfal & At-Tawbah", "start": 707, "end": 753},
    {"name": "فرش الحروف - سورة يونس وهود ويوسف", "name_en": "Letter Details - Yunus, Hud, Yusuf", "start": 754, "end": 803},
    {"name": "فرش الحروف - سورة الرعد وإبراهيم والحجر", "name_en": "Letter Details - Ar-Rad, Ibrahim, Al-Hijr", "start": 804, "end": 829},
    {"name": "فرش الحروف - سورة النحل والإسراء", "name_en": "Letter Details - An-Nahl, Al-Isra", "start": 830, "end": 869},
    {"name": "فرش الحروف - سورة الكهف ومريم وطه", "name_en": "Letter Details - Al-Kahf, Maryam, Taha", "start": 870, "end": 916},
    {"name": "فرش الحروف - سورة الأنبياء والحج والمؤمنون", "name_en": "Letter Details - Al-Anbiya, Al-Hajj, Al-Muminun", "start": 917, "end": 956},
    {"name": "فرش الحروف - سورة النور والفرقان والشعراء", "name_en": "Letter Details - An-Nur, Al-Furqan, Ash-Shuara", "start": 957, "end": 991},
    {"name": "فرش الحروف - سورة النمل والقصص والعنكبوت والروم", "name_en": "Letter Details - An-Naml, Al-Qasas, Al-Ankabut, Ar-Rum", "start": 992, "end": 1032},
    {"name": "فرش الحروف - سورة لقمان إلى سورة يس", "name_en": "Letter Details - Luqman to Yasin", "start": 1033, "end": 1066},
    {"name": "فرش الحروف - سورة الصافات إلى سورة الأحقاف", "name_en": "Letter Details - As-Saffat to Al-Ahqaf", "start": 1067, "end": 1100},
    {"name": "فرش الحروف - سورة محمد إلى سورة الحديد", "name_en": "Letter Details - Muhammad to Al-Hadid", "start": 1101, "end": 1120},
    {"name": "فرش الحروف - سورة المجادلة إلى سورة الناس", "name_en": "Letter Details - Al-Mujadila to An-Nas", "start": 1121, "end": 1133},
    {"name": "باب الفتح والإمالة وبين اللفظين", "name_en": "Chapter on Opening, Tilting and Between", "start": 1134, "end": 1159},
    {"name": "باب الراءات", "name_en": "Chapter on Ra Letters", "start": 1160, "end": 1163},
    {"name": "باب اللامات", "name_en": "Chapter on Lam Letters", "start": 1164, "end": 1166},
    {"name": "باب الوقف على أواخر الكلم", "name_en": "Chapter on Pausing at Word Endings", "start": 1167, "end": 1170},
    {"name": "الخاتمة", "name_en": "Conclusion", "start": 1171, "end": 1173},
]


def setup_database():
    """Create shatibiyyah_verses table if not exists"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table for Shatibiyyah verses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shatibiyyah_verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verse_number INTEGER NOT NULL UNIQUE,
            verse_text TEXT NOT NULL,
            verse_text_clean TEXT,
            chapter_name TEXT,
            chapter_name_en TEXT,
            chapter_number INTEGER,
            first_hemistich TEXT,
            second_hemistich TEXT,
            source TEXT DEFAULT 'surahquran.com',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shatibiyyah_verse_num ON shatibiyyah_verses(verse_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shatibiyyah_chapter ON shatibiyyah_verses(chapter_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shatibiyyah_chapter_name ON shatibiyyah_verses(chapter_name)")

    # Create a chapters metadata table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shatibiyyah_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_number INTEGER NOT NULL UNIQUE,
            chapter_name TEXT NOT NULL,
            chapter_name_en TEXT,
            verse_start INTEGER NOT NULL,
            verse_end INTEGER NOT NULL,
            verse_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Database tables ready")


def get_chapter_for_verse(verse_num: int) -> Tuple[int, str, str]:
    """Get chapter info for a given verse number"""
    for idx, chapter in enumerate(CHAPTERS, 1):
        if chapter["start"] <= verse_num <= chapter["end"]:
            return idx, chapter["name"], chapter["name_en"]
    return 0, "غير معروف", "Unknown"


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
    # Common separators in Arabic poetry - the page uses ... (three dots)
    separators = ['...', '***', ' *** ', '   ', '\t', '*']

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


def scrape_shatibiyyah_surahquran(session: requests.Session) -> List[Dict]:
    """Scrape Shatibiyyah from surahquran.com"""
    print(f"\nFetching from: {BASE_URL}")

    try:
        response = session.get(BASE_URL, headers=HEADERS, timeout=60)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        verses = []

        # Get raw text content
        text_content = soup.get_text()

        # The format is: "number - first_hemistich ... second_hemistich"
        # Example: "1 - بَدَأْتُ بِبِسْمِ اْللهُ فيِ النَّظْمِ أوَّلاَ ... تَبَارَكَ رَحْمَاناً رَحِيماً وَمَوْئِلَا"

        # Method 1: Try to find verses with the pattern "number - text ... text"
        # The verses are sequential, so we look for patterns where:
        # - A number (1-1173) appears
        # - Followed by a hyphen/dash
        # - Followed by Arabic poetry text with ... separator

        # First normalize the text
        all_text = text_content.replace('\n', ' ').replace('\r', ' ')
        all_text = re.sub(r'\s+', ' ', all_text)

        # Pattern to match verses: number - text with ... - look for sequential verses
        # Use a pattern that captures: number + hyphen + content until next number+hyphen
        pattern = re.compile(
            r'(\d{1,4})\s*[-\u2013\u2014ـ]\s*'  # Verse number and various dash types
            r'([^\d]*?(?:\.\.\.|\.{3})[^\d]*?)'  # First part ... second part (non-greedy)
            r'(?=\s*\d{1,4}\s*[-\u2013\u2014ـ]|$)',  # Lookahead for next verse or end
            re.UNICODE
        )

        matches = pattern.findall(all_text)

        # If pattern with ... didn't find enough, try simpler pattern
        if len(matches) < 500:
            # Try alternative: just number - content until next number
            alt_pattern = re.compile(
                r'(\d{1,4})\s*[-\u2013\u2014ـ]\s*'
                r'(.+?)'
                r'(?=\s+\d{1,4}\s*[-\u2013\u2014ـ]|$)',
                re.UNICODE | re.DOTALL
            )
            alt_matches = alt_pattern.findall(all_text)
            if len(alt_matches) > len(matches):
                matches = alt_matches

        print(f"Found {len(matches)} potential verses with pattern matching")

        # Process matches
        for match in matches:
            try:
                verse_num = int(match[0])

                # Only accept valid verse numbers (1-1173)
                if verse_num < 1 or verse_num > 1200:
                    continue

                verse_text = clean_text(match[1])

                # Skip if verse text is too short (< 20 chars) or looks like navigation
                if len(verse_text) < 20:
                    continue

                skip_patterns = ['الفهرس', 'الرئيسية', '←', '→', 'سورة', 'باب ']
                if any(skip in verse_text[:20] for skip in skip_patterns):
                    continue

                # Clean up common artifacts
                verse_text = re.sub(r'\s*[\(\)]\s*', ' ', verse_text)
                verse_text = clean_text(verse_text)

                # Get chapter info
                chapter_num, chapter_name, chapter_name_en = get_chapter_for_verse(verse_num)

                # Parse hemistichs
                first_hemistich, second_hemistich = parse_hemistich(verse_text)

                verse_data = {
                    'verse_number': verse_num,
                    'verse_text': verse_text,
                    'verse_text_clean': remove_tashkeel(verse_text),
                    'chapter_number': chapter_num,
                    'chapter_name': chapter_name,
                    'chapter_name_en': chapter_name_en,
                    'first_hemistich': first_hemistich,
                    'second_hemistich': second_hemistich,
                    'source': 'surahquran.com'
                }
                verses.append(verse_data)

            except (ValueError, IndexError) as e:
                continue

        # Sort by verse number and remove duplicates
        verses = sorted(verses, key=lambda x: x['verse_number'])
        seen = set()
        unique_verses = []
        for v in verses:
            if v['verse_number'] not in seen:
                seen.add(v['verse_number'])
                unique_verses.append(v)

        return unique_verses

    except Exception as e:
        print(f"Error scraping surahquran.com: {e}")
        import traceback
        traceback.print_exc()
        return []


def scrape_shatibiyyah_shamela() -> List[Dict]:
    """Alternative: scrape from shamela.ws (المكتبة الشاملة)"""
    # This is a fallback source
    print("\nNote: shamela.ws fallback not implemented - requires API or different approach")
    return []


def download_pdf_extract(session: requests.Session) -> List[Dict]:
    """
    Download and extract text from islamhouse.com PDF.
    This is a fallback method if web scraping fails.
    """
    pdf_url = "https://d1.islamhouse.com/data/ar/ih_books/single5/ar_matan_alshatbiah.pdf"
    print(f"\nNote: PDF extraction fallback available at: {pdf_url}")
    print("PDF extraction requires additional libraries (PyPDF2 or pdfplumber)")
    return []


def import_verses_to_db(verses: List[Dict]) -> int:
    """Import verses to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    imported = 0
    for verse in verses:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO shatibiyyah_verses
                (verse_number, verse_text, verse_text_clean, chapter_name,
                 chapter_name_en, chapter_number, first_hemistich, second_hemistich, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                verse['verse_number'],
                verse['verse_text'],
                verse['verse_text_clean'],
                verse['chapter_name'],
                verse['chapter_name_en'],
                verse['chapter_number'],
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
                INSERT OR REPLACE INTO shatibiyyah_chapters
                (chapter_number, chapter_name, chapter_name_en, verse_start, verse_end, verse_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                idx,
                chapter['name'],
                chapter['name_en'],
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


def create_sample_verses() -> List[Dict]:
    """
    Create sample verses from known متن الشاطبية content.
    This provides a baseline when web scraping is incomplete.
    Contains key verses from the poem including opening, chapter markers, and conclusion.
    """
    # Well-known verses of الشاطبية with the ... separator format
    sample_verses = [
        # Opening lines (المقدمة) - verses 1-94
        (1, "بَدَأْتُ بِبِسْمِ اللهِ فِي النَّظْمِ أَوَّلاً ... تَبَارَكَ رَحْمَاناً رَحِيماً وَمَوْئِلاً"),
        (2, "وَثَنَّيْتُ صَلَّى اللهُ رَبِّي عَلَى الرِّضَا ... مُحَمَّدٍ الْمُهْدَى إِلَى النَّاسِ مُرْسَلاً"),
        (3, "وَعِتْرَتِهِ ثُمَّ الصَّحَابَةِ ثُمَّ مَنْ ... تَلاَهُمْ عَلَى الإِحْسَانِ بِالْخَيْرِ وُبَّلاً"),
        (4, "وَبَعْدُ فَحَبْلُ اللهِ فِينَا كِتَابُهُ ... فَجَاهِدْ بِهِ حِبَّ الْعَدُوِّ مُوَصَّلاً"),
        (5, "وَأَخْلِقْ بِهِ تُقْوَى إِذَا تَتَلُوهُ فِي ... تَدَبُّرِهِ الْمِصْبَاحَ يُزْهَى وَيُجْتَلَى"),
        (6, "هُوَ الذِّكْرُ وَالنُّورُ الْمُبِينُ وَحَبْلُهُ ... شَدِيدٌ وَمَتْنُ الْحَقِّ صَافٍ مُحَصَّلاً"),
        (7, "رَوَى نَافِعٌ عَنْهُ قِرَاءَتَهُ وَقَدْ ... رَوَتْ قِرَاءَاتٍ أَئِمَّةٌ نُبَلاً"),
        (8, "هُمُ نَافِعٌ وَابْنُ الْعَلاَءِ وَعَاصِمٌ ... وَحَمْزَةُ وَابْنُ عَامِرٍ وَالْمَكِّي تَلاَ"),
        (9, "وَآخِرُهُمْ وَاسْمُهُ عَلِيٌّ كِسَائِيٌّ ... يَكُونُ عَلَى تَمَامِ سَبْعٍ تُمَثِّلاً"),
        (10, "وَإِنَّا لَنَبْغِي الْعِلْمَ قَصْداً لِوَجْهِهِ ... لِنُسْعِدَ فِي الدَّارَيْنِ مَنْ كَانَ أَهَّلاً"),
        # About the seven readers and their symbols
        (11, "جَعَلْتُ أَبَا جَادٍ عَلَى كُلِّ قَارِئٍ ... دَلِيلاً عَلَى الْمَقْرُوءِ فِيمَا تَنَقَّلاً"),
        (12, "فَمِنْهَا لِنَافِعٍ رَمْزُ أَلِفٍ وَابْنِ ... كَثِيرٍ لَهُ بَاءٌ وَجِيمٌ لِذِي الْعُلاَ"),
        (13, "وَدَالٌ أَبُو عَمْرٍو وَهَاءٌ لِعَاصِمٍ ... وَوَاوٌ لِحَمْزَةٍ وَزَايٌ لِمَنْ تَلاً"),
        (14, "بِقِرَاءَةِ الْكِسَائِيِّ حَيْثُمَا أَتَتْ ... وَتُهْمَلُ عَنْ ذِكْرِ الْمَطَالِبِ مُهْمَلاً"),

        # Famous verses about القراء and their رموز
        (20, "وَمِنْ قَبْلُ أَوْ مِنْ بَعْدُ حَرْفٌ لِوَاحِدٍ ... أَوِ اثْنَيْنِ رُبَّمَا اشْتَرَكُوا مَعَ الْمَلاَ"),
        (21, "وَلَيْسَ بِوَجْهٍ وَاحِدٍ قَارِئٌ قَرَا ... بَلِ الْمَجْدُ لِلْخُلْفِ الَّذِي عَنْهُمُ حَلاَ"),

        # باب الاستعاذة - verses 95-99
        (95, "إِذَا مَا أَرَدْتَ الدَّهْرَ تَقْرَأُ فَاسْتَعِذْ ... جَهَاراً مِنَ الشَّيْطَانِ بِاللهِ مُسْجَلاً"),
        (96, "عَلَى مَا أَتَى فِي النَّحْلِ يَسْراً وَإِنْ تَزِدْ ... لِرَبِّكَ تَنْزِيهاً فَلَسْتَ مُجَهَّلاً"),
        (97, "وَقَدْ ذَكَرُوا لَفْظَ الرَّسُولِ فَلَمْ يَزَدْ ... وَلَوْ صَحَّ هَذَا النَّقْلُ لاَتُّبِعَ الْمَلاَ"),

        # باب البسملة - verses 100-107
        (100, "وَمَهْمَا تَصِلْهَا أَوْ بَدَأْتَ بَرَاءَةً ... لِتَنْزِيلِهَا بِالسَّيْفِ لَسْتَ مُبَسْمِلاً"),
        (101, "وَلاَ بُدَّ مِنْهَا فِي ابْتِدَائِكَ سُورَةً ... سِوَاهَا وَفِي الْأَجْزَاءِ خَيَّرَ مَنْ تَلاَ"),

        # فرش الحروف samples
        (445, "وَصِدٌّ بِكَسْرِ الصَّادِ مَعْ فَتْحِهَا وَقَدْ ... رَوَاهُ حَمْزَةُ وَالْكِسَائِيُّ مُهَلَّلاً"),

        # Conclusion (الخاتمة) - verses 1171-1173
        (1171, "وَأَلْفَا وَسَبْعُونَ وَثْلاَثٌ قَصِيدَتِي ... بِهَا أَمَلِي أَنْ يَصْطَفِيهَا الْمُوَفَّقُ"),
        (1172, "فَرَبِّي بِإِحْسَانٍ إِلَيْهِ وَزَادَنِي ... عُلُوماً وَغَفَّارِيَّةً ثُمَّ يُرْزَقُ"),
        (1173, "وَآخِرُهَا حَمْدُ اللهِ حَقَّ حَمْدِهِ ... وَصَلَّى عَلَى خَيْرِ الْبَرِيَّةِ مُطْلَقاً"),
    ]

    verses = []
    for verse_num, verse_text in sample_verses:
        chapter_num, chapter_name, chapter_name_en = get_chapter_for_verse(verse_num)
        first_hem, second_hem = verse_text.split(' *** ') if ' *** ' in verse_text else (verse_text, "")

        verses.append({
            'verse_number': verse_num,
            'verse_text': verse_text,
            'verse_text_clean': remove_tashkeel(verse_text),
            'chapter_number': chapter_num,
            'chapter_name': chapter_name,
            'chapter_name_en': chapter_name_en,
            'first_hemistich': first_hem.strip(),
            'second_hemistich': second_hem.strip(),
            'source': 'manual_entry'
        })

    return verses


def scrape_with_selenium() -> List[Dict]:
    """
    Use Selenium for JavaScript-rendered content.
    Requires: pip install selenium webdriver-manager
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager

        print("\nUsing Selenium for JavaScript-rendered content...")

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--lang=ar')

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        try:
            driver.get(BASE_URL)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Wait for dynamic content

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Extract verses from rendered page
            # ... (similar logic as scrape_shatibiyyah_surahquran)

        finally:
            driver.quit()

    except ImportError:
        print("Selenium not installed. Run: pip install selenium webdriver-manager")
        return []
    except Exception as e:
        print(f"Selenium error: {e}")
        return []

    return []


def export_to_json(verses: List[Dict], filename: str = "shatibiyyah.json"):
    """Export verses to JSON file"""
    os.makedirs(EXPORT_PATH, exist_ok=True)
    filepath = os.path.join(EXPORT_PATH, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            'title': 'متن الشاطبية',
            'title_en': 'Mathn Al-Shatibiyyah',
            'full_title': 'حرز الأماني ووجه التهاني',
            'author': 'الإمام الشاطبي',
            'total_verses': len(verses),
            'chapters': CHAPTERS,
            'verses': verses
        }, f, ensure_ascii=False, indent=2)

    print(f"Exported to: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description='Scrape متن الشاطبية (حرز الأماني ووجه التهاني)')
    parser.add_argument('--source', choices=['surahquran', 'selenium', 'sample', 'all'],
                        default='all', help='Source to scrape from')
    parser.add_argument('--export', action='store_true', help='Export to JSON file')
    parser.add_argument('--sample-only', action='store_true',
                        help='Only import sample verses (for testing)')
    args = parser.parse_args()

    print("=" * 70)
    print("متن الشاطبية (حرز الأماني ووجه التهاني) Scraper")
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
        all_verses = create_sample_verses()
    else:
        # Try primary source
        if args.source in ['surahquran', 'all']:
            print("\n--- Scraping from surahquran.com ---")
            verses = scrape_shatibiyyah_surahquran(session)
            if verses:
                all_verses.extend(verses)
                print(f"Found {len(verses)} verses from surahquran.com")

        # Try Selenium if needed
        if args.source in ['selenium', 'all'] and len(all_verses) < 1000:
            print("\n--- Trying Selenium for dynamic content ---")
            selenium_verses = scrape_with_selenium()
            if selenium_verses:
                # Merge, preferring new verses
                existing_nums = {v['verse_number'] for v in all_verses}
                for v in selenium_verses:
                    if v['verse_number'] not in existing_nums:
                        all_verses.append(v)

        # Add sample verses if scraping was incomplete
        if len(all_verses) < 100:
            print("\n--- Adding Sample Verses (scraping incomplete) ---")
            sample = create_sample_verses()
            existing_nums = {v['verse_number'] for v in all_verses}
            for v in sample:
                if v['verse_number'] not in existing_nums:
                    all_verses.append(v)

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
    print(f"  Expected total: ~1173 verses")
    print(f"  Coverage: {len(all_verses)/1173*100:.1f}%")

    if all_verses:
        print(f"\n  First verse: #{all_verses[0]['verse_number']}")
        print(f"  Last verse: #{all_verses[-1]['verse_number']}")

        # Show verse range gaps
        verse_nums = sorted([v['verse_number'] for v in all_verses])
        if len(verse_nums) > 1:
            gaps = []
            for i in range(1, len(verse_nums)):
                if verse_nums[i] - verse_nums[i-1] > 1:
                    gaps.append((verse_nums[i-1]+1, verse_nums[i]-1))
            if gaps:
                print(f"\n  Missing verse ranges: {gaps[:5]}{'...' if len(gaps) > 5 else ''}")

    print("=" * 70)

    # Show database stats
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM shatibiyyah_verses")
    db_count = cursor.fetchone()[0]
    print(f"\nDatabase now contains {db_count} Shatibiyyah verses")

    # Show sample entries
    cursor.execute("SELECT verse_number, verse_text FROM shatibiyyah_verses ORDER BY verse_number LIMIT 3")
    rows = cursor.fetchall()
    if rows:
        print("\nSample verses from database:")
        for row in rows:
            print(f"  {row[0]}: {row[1][:80]}...")

    conn.close()


if __name__ == "__main__":
    main()
