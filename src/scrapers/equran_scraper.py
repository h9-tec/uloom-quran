#!/usr/bin/env python3
"""
e-quran.com Scraper for إعراب القرآن and أسباب النزول

Sources:
- إعراب القرآن: https://e-quran.com/pages/tafseer/eerab/{surah}/{verse}.html
- أسباب النزول: https://e-quran.com/noz{surah}.html
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import os
import json
import argparse
import re

BASE_URL = "https://e-quran.com"
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'uloom_quran.db')
EXPORT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed', 'equran')

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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
}


def setup_database():
    """Create إعراب table if not exists"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create earab_verses table for verse-level grammatical analysis
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earab_verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verse_id INTEGER NOT NULL,
            earab_text TEXT NOT NULL,
            source TEXT DEFAULT 'e-quran.com',
            book_name TEXT DEFAULT 'إعراب القرآن للدعاس',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (verse_id) REFERENCES verses(id),
            UNIQUE(verse_id, source)
        )
    """)

    # Create index for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_earab_verse ON earab_verses(verse_id)")

    conn.commit()
    conn.close()
    print("Database tables ready")


def get_verse_id(cursor, surah_id, ayah_number):
    """Get verse ID from database"""
    verse_key = f"{surah_id}:{ayah_number}"
    cursor.execute("SELECT id FROM verses WHERE verse_key = ?", (verse_key,))
    row = cursor.fetchone()
    return row[0] if row else None


def scrape_earab_verse(surah_id, verse_num, session):
    """Scrape إعراب for a single verse"""
    url = f"{BASE_URL}/pages/tafseer/eerab/{surah_id}/{verse_num}.html"

    try:
        response = session.get(url, headers=HEADERS, timeout=30)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the main content - try different selectors
        content = None

        # Try finding main article/content div
        for selector in ['article', '.content', '#content', 'main', '.main-content', 'div.text']:
            elem = soup.select_one(selector)
            if elem:
                content = elem
                break

        if not content:
            # Get body content, excluding nav/header/footer
            body = soup.find('body')
            if body:
                # Remove navigation elements
                for tag in body.find_all(['nav', 'header', 'footer', 'script', 'style']):
                    tag.decompose()
                content = body

        if content:
            # Get text content, preserving structure
            text = content.get_text(separator='\n', strip=True)

            # Clean up the text
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            # Remove navigation text
            filtered_lines = []
            skip_patterns = ['الفهرس', 'السابق', 'التالي', 'الرئيسية', '←', '→']
            for line in lines:
                if not any(p in line for p in skip_patterns) and len(line) > 3:
                    filtered_lines.append(line)

            return '\n'.join(filtered_lines) if filtered_lines else None

        return None

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


def scrape_earab_surah(surah_id, session):
    """Scrape إعراب for all verses in a surah"""
    verse_count = VERSE_COUNTS.get(surah_id, 0)
    results = []

    for verse_num in range(1, verse_count + 1):
        earab_text = scrape_earab_verse(surah_id, verse_num, session)
        if earab_text:
            results.append({
                'surah': surah_id,
                'verse': verse_num,
                'verse_key': f"{surah_id}:{verse_num}",
                'earab': earab_text
            })
            print(f"    ✓ Verse {verse_num}/{verse_count}")
        else:
            print(f"    ✗ Verse {verse_num}/{verse_count} - no content")

        time.sleep(0.1)  # Rate limiting (faster)

    return results


def scrape_asbab_surah(surah_id, session):
    """Scrape أسباب النزول for a surah"""
    url = f"{BASE_URL}/noz{surah_id}.html"

    try:
        response = session.get(url, headers=HEADERS, timeout=30)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find main content
        content = None
        for selector in ['article', '.content', '#content', 'main', 'div.text']:
            elem = soup.select_one(selector)
            if elem:
                content = elem
                break

        if not content:
            body = soup.find('body')
            if body:
                for tag in body.find_all(['nav', 'header', 'footer', 'script', 'style', 'select']):
                    tag.decompose()
                content = body

        if content:
            text = content.get_text(separator='\n', strip=True)

            # Clean up navigation and index patterns
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            skip_patterns = [
                'الفهرس', 'السابق', 'التالي', 'الرئيسية', '←', '→',
                'فهرس أسباب النزول', 'العودة إلى السورة', 'اختر السورة'
            ]

            # Filter out navigation lines and surah index entries (e.g., "001 سورة الفاتحة")
            import re
            filtered_lines = []
            for line in lines:
                # Skip navigation patterns
                if any(p in line for p in skip_patterns):
                    continue
                # Skip surah index entries like "001 سورة الفاتحة"
                if re.match(r'^\d{3}\s+سورة\s+\S+$', line):
                    continue
                if len(line) > 3:
                    filtered_lines.append(line)

            return '\n'.join(filtered_lines) if filtered_lines else None

        return None

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


def import_earab_to_db(data):
    """Import إعراب data to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    imported = 0
    for item in data:
        verse_id = get_verse_id(cursor, item['surah'], item['verse'])
        if verse_id:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO earab_verses (verse_id, earab_text, source, book_name)
                    VALUES (?, ?, 'e-quran.com', 'إعراب القرآن للدعاس')
                """, (verse_id, item['earab']))
                imported += 1
            except Exception as e:
                print(f"  Error importing {item['verse_key']}: {e}")

    conn.commit()
    conn.close()
    return imported


def import_asbab_to_db(surah_id, asbab_text):
    """Import أسباب النزول data to database (as surah-level entry)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get source_id for e-quran.com source (or create it)
    cursor.execute("SELECT id FROM asbab_sources WHERE name_arabic = ?", ('أسباب النزول - e-quran.com',))
    row = cursor.fetchone()
    if row:
        source_id = row[0]
    else:
        cursor.execute("""
            INSERT INTO asbab_sources (name_arabic, name_english, author_arabic, description)
            VALUES (?, ?, ?, ?)
        """, (
            'أسباب النزول - e-quran.com',
            'Asbab al-Nuzul - e-quran.com',
            'موقع القرآن الإلكتروني',
            'مجموعة أسباب النزول من موقع e-quran.com'
        ))
        source_id = cursor.lastrowid

    # Get first verse of surah
    cursor.execute("SELECT id FROM verses WHERE surah_id = ? AND ayah_number = 1", (surah_id,))
    verse_row = cursor.fetchone()
    if not verse_row:
        conn.close()
        return 0

    verse_id = verse_row[0]

    # Insert or update asbab entry
    cursor.execute("""
        INSERT OR REPLACE INTO asbab_nuzul (verse_id, source_id, sabab_text)
        VALUES (?, ?, ?)
    """, (verse_id, source_id, asbab_text))

    conn.commit()
    conn.close()
    return 1


def main():
    parser = argparse.ArgumentParser(description='Scrape إعراب and أسباب from e-quran.com')
    parser.add_argument('--type', choices=['earab', 'asbab', 'both'], default='both',
                        help='Type of content to scrape')
    parser.add_argument('--surah', type=int, help='Specific surah to scrape (1-114)')
    parser.add_argument('--start', type=int, default=1, help='Start surah')
    parser.add_argument('--end', type=int, default=114, help='End surah')
    parser.add_argument('--export', action='store_true', help='Export to JSON files')
    args = parser.parse_args()

    # Setup
    setup_database()
    os.makedirs(EXPORT_PATH, exist_ok=True)
    session = requests.Session()

    # Determine surah range
    if args.surah:
        start, end = args.surah, args.surah
    else:
        start, end = args.start, args.end

    print("=" * 60)
    print("e-quran.com Scraper")
    print(f"Type: {args.type}")
    print(f"Surahs: {start} to {end}")
    print("=" * 60)

    # Scrape إعراب
    if args.type in ['earab', 'both']:
        print("\n--- Scraping إعراب القرآن ---")
        all_earab = []

        for surah_id in range(start, end + 1):
            print(f"\nSurah {surah_id} ({VERSE_COUNTS.get(surah_id, 0)} verses):")

            earab_data = scrape_earab_surah(surah_id, session)
            if earab_data:
                all_earab.extend(earab_data)
                print(f"  Scraped {len(earab_data)} verses")

                # Import to database
                imported = import_earab_to_db(earab_data)
                print(f"  Imported {imported} verses to database")

                # Export to JSON
                if args.export:
                    export_file = os.path.join(EXPORT_PATH, f'earab_surah_{surah_id}.json')
                    with open(export_file, 'w', encoding='utf-8') as f:
                        json.dump(earab_data, f, ensure_ascii=False, indent=2)

            time.sleep(0.5)  # Rate limiting between surahs

        print(f"\n✓ Total إعراب entries: {len(all_earab)}")

    # Scrape أسباب النزول
    if args.type in ['asbab', 'both']:
        print("\n--- Scraping أسباب النزول ---")
        asbab_count = 0

        for surah_id in range(start, end + 1):
            print(f"\nSurah {surah_id}:", end=" ")

            asbab_text = scrape_asbab_surah(surah_id, session)
            if asbab_text:
                print(f"✓ ({len(asbab_text)} chars)")

                # Import to database
                import_asbab_to_db(surah_id, asbab_text)
                asbab_count += 1

                # Export to JSON
                if args.export:
                    export_file = os.path.join(EXPORT_PATH, f'asbab_surah_{surah_id}.json')
                    with open(export_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'surah': surah_id,
                            'asbab_text': asbab_text
                        }, f, ensure_ascii=False, indent=2)
            else:
                print("✗ no content")

            time.sleep(0.5)

        print(f"\n✓ Total أسباب entries: {asbab_count}")

    print("\n" + "=" * 60)
    print("Scraping complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
