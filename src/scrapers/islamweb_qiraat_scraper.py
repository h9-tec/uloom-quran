#!/usr/bin/env python3
"""
islamweb.net Qiraat Scraper

Scrapes scholarly qiraat (Quranic readings) content from islamweb.net's library.

Available Books:
- Book 245: الوافي في شرح الشاطبية (Al-Wafi fi Sharh Al-Shaatibiyyah)
  Commentary on the seven canonical qira'at by Abd al-Fattah al-Qadi
  396 pages covering all aspects of the seven readings

Content Types:
- متن الشاطبية (Al-Shaatibiyyah text and commentary)
- أصول القراءات (Usul al-Qiraat - foundational principles)
- فرش الحروف (Farsh al-Huruf - individual letter variants)
- أحكام التجويد (Tajweed rules for each reading)

URL Structure:
- Library: https://www.islamweb.net/ar/library/index.php
- Book contents: ?page=bookcontents&bk_no={book_id}&ID={page_id}
- Book index: ?page=bookindex&bk_no={book_id}
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import os
import json
import argparse
import re
from datetime import datetime
from typing import Optional, Dict, List, Any

# Configuration
BASE_URL = "https://www.islamweb.net"
LIBRARY_URL = f"{BASE_URL}/ar/library/index.php"
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'uloom_quran.db')
EXPORT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed', 'islamweb_qiraat')

# Available Qiraat Books
QIRAAT_BOOKS = {
    245: {
        'name_arabic': 'الوافي في شرح الشاطبية',
        'name_english': 'Al-Wafi fi Sharh Al-Shaatibiyyah',
        'author_arabic': 'عبد الفتاح القاضي',
        'author_english': 'Abd al-Fattah al-Qadi',
        'death_year_hijri': 1403,
        'total_pages': 396,
        'description': 'شرح متوسط على منظومة حرز الأماني ووجه التهاني (الشاطبية) في القراءات السبع',
        'content_type': 'شرح_الشاطبية',
        'covers_qiraat': ['نافع', 'ابن كثير', 'أبو عمرو', 'ابن عامر', 'عاصم', 'حمزة', 'الكسائي']
    }
}

# HTTP Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.islamweb.net/ar/library/',
}


def setup_database():
    """Create qiraat tables if not exists"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create qiraat_books table for book metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER UNIQUE NOT NULL,
            name_arabic TEXT NOT NULL,
            name_english TEXT,
            author_arabic TEXT NOT NULL,
            author_english TEXT,
            death_year_hijri INTEGER,
            total_pages INTEGER,
            description TEXT,
            content_type TEXT,
            source TEXT DEFAULT 'islamweb.net',
            source_url TEXT,
            covers_qiraat TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create qiraat_chapters table for book structure
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_ref_id INTEGER NOT NULL,
            chapter_number INTEGER NOT NULL,
            title_arabic TEXT NOT NULL,
            title_english TEXT,
            parent_chapter_id INTEGER,
            page_start INTEGER,
            page_end INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (book_ref_id) REFERENCES qiraat_books(id),
            FOREIGN KEY (parent_chapter_id) REFERENCES qiraat_chapters(id),
            UNIQUE(book_ref_id, chapter_number)
        )
    """)

    # Create qiraat_content table for page content
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_ref_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            chapter_id INTEGER,
            title TEXT,
            content_text TEXT NOT NULL,
            content_html TEXT,
            has_poetry INTEGER DEFAULT 0,
            has_quran_refs INTEGER DEFAULT 0,
            quran_references TEXT,
            related_qurra TEXT,
            topics TEXT,
            source_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (book_ref_id) REFERENCES qiraat_books(id),
            FOREIGN KEY (chapter_id) REFERENCES qiraat_chapters(id),
            UNIQUE(book_ref_id, page_number)
        )
    """)

    # Create qiraat_rules table for extracted rules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            rule_type TEXT CHECK(rule_type IN ('أصول', 'فرش', 'تجويد', 'رسم', 'ضبط')),
            rule_name TEXT,
            rule_description TEXT NOT NULL,
            applies_to_qurra TEXT,
            quran_examples TEXT,
            source_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES qiraat_content(id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_content_book ON qiraat_content(book_ref_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_content_page ON qiraat_content(page_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_rules_type ON qiraat_rules(rule_type)")

    conn.commit()
    conn.close()
    print("Database tables ready")


def get_or_create_book(cursor, book_id: int) -> int:
    """Get or create book entry, returns internal book reference ID"""
    book_info = QIRAAT_BOOKS.get(book_id)
    if not book_info:
        raise ValueError(f"Unknown book ID: {book_id}")

    cursor.execute("SELECT id FROM qiraat_books WHERE book_id = ?", (book_id,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute("""
        INSERT INTO qiraat_books (
            book_id, name_arabic, name_english, author_arabic, author_english,
            death_year_hijri, total_pages, description, content_type,
            source, source_url, covers_qiraat
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        book_id,
        book_info['name_arabic'],
        book_info['name_english'],
        book_info['author_arabic'],
        book_info['author_english'],
        book_info['death_year_hijri'],
        book_info['total_pages'],
        book_info['description'],
        book_info['content_type'],
        'islamweb.net',
        f"{LIBRARY_URL}?page=bookindex&bk_no={book_id}",
        json.dumps(book_info['covers_qiraat'], ensure_ascii=False)
    ))
    return cursor.lastrowid


def extract_quran_references(text: str) -> List[str]:
    """Extract Quran verse references from text"""
    references = []

    # Pattern for verse references like [البقرة: 255] or (البقرة: 255)
    patterns = [
        r'\[([^\]]+):\s*(\d+)\]',
        r'\(([^)]+):\s*(\d+)\)',
        r'سورة\s+(\S+)\s+آية\s+(\d+)',
        r'(\S+):\s*(\d+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) == 2:
                ref = f"{match[0]}:{match[1]}"
                if ref not in references:
                    references.append(ref)

    return references


def extract_qurra_mentions(text: str) -> List[str]:
    """Extract mentions of qurra (readers) from text"""
    qurra_names = [
        'نافع', 'قالون', 'ورش',
        'ابن كثير', 'البزي', 'قنبل',
        'أبو عمرو', 'الدوري', 'السوسي',
        'ابن عامر', 'هشام', 'ابن ذكوان',
        'عاصم', 'شعبة', 'حفص',
        'حمزة', 'خلف', 'خلاد',
        'الكسائي', 'أبو الحارث',
        'أبو جعفر', 'ابن وردان', 'ابن جماز',
        'يعقوب', 'رويس', 'روح',
        'خلف العاشر', 'إسحاق', 'إدريس'
    ]

    found = []
    for name in qurra_names:
        if name in text:
            found.append(name)
    return found


def has_poetry(text: str) -> bool:
    """Check if text contains poetry verses (from Shaatibiyyah)"""
    # Poetry indicators
    poetry_patterns = [
        r'وقال\s+الشاطبي',
        r'قال\s+الناظم',
        r'ومعنى\s+البيت',
        r'وقوله:',
        r'كقوله:',
        r'\*\*\*',  # Poetry separator
    ]

    for pattern in poetry_patterns:
        if re.search(pattern, text):
            return True
    return False


def clean_content(text: str, include_toc: bool = False) -> str:
    """Clean scraped content by removing navigation and repetitive elements"""
    lines = text.split('\n')

    # Skip table of contents at the beginning
    filtered_lines = []
    in_toc = True
    toc_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect end of TOC
        if in_toc:
            # TOC lines are typically short chapter titles
            if line.startswith('باب ') and len(line) < 100:
                toc_lines.append(line)
                continue
            elif line.startswith('سورة ') and len(line) < 50:
                toc_lines.append(line)
                continue
            elif line.startswith('فهرس الكتاب'):
                toc_lines.append(line)
                continue
            elif line.startswith('المقدمة') and len(line) < 20:
                toc_lines.append(line)
                continue
            elif re.match(r'^الوافي في شرح الشاطبية$', line):
                continue  # Skip book title repetition
            elif re.match(r'^عبد الفتاح القاضي', line):
                continue  # Skip author repetition
            elif 'تم نسخ الرابط' in line:
                continue  # Skip "link copied" text
            else:
                # Found actual content
                in_toc = False

        if not in_toc:
            # Skip navigation and UI elements
            if 'nindex.php' in line and len(line) < 100:
                continue
            if line in ['الوافي في شرح الشاطبية', 'عبد الفتاح القاضي']:
                continue
            if 'تم نسخ الرابط' in line:
                continue
            if re.match(r'^\d+$', line):  # Skip page numbers
                continue
            if len(line) < 4:
                continue

            filtered_lines.append(line)

    result = '\n'.join(filtered_lines)

    # Optionally prepend TOC for first pages
    if include_toc and toc_lines:
        result = '\n'.join(toc_lines) + '\n\n---\n\n' + result

    return result


def scrape_page(session: requests.Session, book_id: int, page_id: int) -> Optional[Dict[str, Any]]:
    """Scrape a single page from a book"""
    url = f"{LIBRARY_URL}?page=bookcontents&bk_no={book_id}&ID={page_id}"

    try:
        response = session.get(url, headers=HEADERS, timeout=30)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract page title
        title = None
        title_elem = soup.select_one('h1, .page-title, .book-title, .section-title')
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Extract main content
        content_elem = None
        for selector in ['.book-content', '.content', '#content', 'article', '.main-content']:
            content_elem = soup.select_one(selector)
            if content_elem:
                break

        if not content_elem:
            # Try to find content by looking for Arabic text blocks
            body = soup.find('body')
            if body:
                # Remove navigation, header, footer
                for tag in body.find_all(['nav', 'header', 'footer', 'script', 'style', 'select', 'option']):
                    tag.decompose()
                content_elem = body

        if not content_elem:
            return None

        # Get HTML content (for preserving structure)
        content_html = str(content_elem)

        # Get text content
        text = content_elem.get_text(separator='\n', strip=True)

        # Clean content using the dedicated function
        content_text = clean_content(text, include_toc=(page_id == 1))

        if not content_text or len(content_text) < 50:
            return None

        # Extract metadata
        quran_refs = extract_quran_references(content_text)
        qurra_mentions = extract_qurra_mentions(content_text)
        contains_poetry = has_poetry(content_text)

        return {
            'book_id': book_id,
            'page_number': page_id,
            'title': title,
            'content_text': content_text,
            'content_html': content_html,
            'has_poetry': contains_poetry,
            'has_quran_refs': len(quran_refs) > 0,
            'quran_references': quran_refs,
            'related_qurra': qurra_mentions,
            'source_url': url
        }

    except Exception as e:
        print(f"  Error scraping page {page_id}: {e}")
        return None


def scrape_book(session: requests.Session, book_id: int, start_page: int = 1,
                end_page: Optional[int] = None) -> List[Dict[str, Any]]:
    """Scrape all pages from a book"""
    book_info = QIRAAT_BOOKS.get(book_id)
    if not book_info:
        raise ValueError(f"Unknown book ID: {book_id}")

    total_pages = book_info['total_pages']
    if end_page is None:
        end_page = total_pages

    results = []

    for page_id in range(start_page, min(end_page + 1, total_pages + 1)):
        print(f"  Scraping page {page_id}/{total_pages}...", end=" ")

        page_data = scrape_page(session, book_id, page_id)
        if page_data:
            results.append(page_data)
            print(f"OK ({len(page_data['content_text'])} chars)")
        else:
            print("SKIP (no content)")

        # Rate limiting
        time.sleep(0.3)

    return results


def import_to_database(data: List[Dict[str, Any]], book_id: int) -> int:
    """Import scraped data to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get or create book entry
    book_ref_id = get_or_create_book(cursor, book_id)

    imported = 0
    for item in data:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO qiraat_content (
                    book_ref_id, page_number, title, content_text, content_html,
                    has_poetry, has_quran_refs, quran_references, related_qurra,
                    source_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                book_ref_id,
                item['page_number'],
                item.get('title'),
                item['content_text'],
                item.get('content_html'),
                1 if item.get('has_poetry') else 0,
                1 if item.get('has_quran_refs') else 0,
                json.dumps(item.get('quran_references', []), ensure_ascii=False),
                json.dumps(item.get('related_qurra', []), ensure_ascii=False),
                item.get('source_url')
            ))
            imported += 1
        except Exception as e:
            print(f"  Error importing page {item['page_number']}: {e}")

    conn.commit()
    conn.close()
    return imported


def export_to_json(data: List[Dict[str, Any]], book_id: int, output_dir: str):
    """Export data to JSON files"""
    os.makedirs(output_dir, exist_ok=True)

    # Export combined file
    combined_file = os.path.join(output_dir, f'book_{book_id}_complete.json')
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump({
            'book_id': book_id,
            'book_info': QIRAAT_BOOKS.get(book_id),
            'scraped_at': datetime.now().isoformat(),
            'pages': data
        }, f, ensure_ascii=False, indent=2)

    print(f"  Exported to {combined_file}")

    # Export individual pages
    pages_dir = os.path.join(output_dir, f'book_{book_id}_pages')
    os.makedirs(pages_dir, exist_ok=True)

    for item in data:
        page_file = os.path.join(pages_dir, f'page_{item["page_number"]:03d}.json')
        with open(page_file, 'w', encoding='utf-8') as f:
            json.dump(item, f, ensure_ascii=False, indent=2)


def get_statistics(book_id: int) -> Dict[str, Any]:
    """Get statistics for scraped content"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total_pages,
            SUM(has_poetry) as pages_with_poetry,
            SUM(has_quran_refs) as pages_with_quran_refs,
            SUM(LENGTH(content_text)) as total_chars
        FROM qiraat_content qc
        JOIN qiraat_books qb ON qc.book_ref_id = qb.id
        WHERE qb.book_id = ?
    """, (book_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'total_pages': row[0] or 0,
            'pages_with_poetry': row[1] or 0,
            'pages_with_quran_refs': row[2] or 0,
            'total_characters': row[3] or 0
        }
    return {}


def main():
    parser = argparse.ArgumentParser(
        description='Scrape Qiraat content from islamweb.net library',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Books:
  245: الوافي في شرح الشاطبية (Al-Wafi fi Sharh Al-Shaatibiyyah)
       Commentary on the seven qira'at - 396 pages

Examples:
  # Scrape first 10 pages of Al-Wafi
  python islamweb_qiraat_scraper.py --book 245 --end 10

  # Scrape entire book with export
  python islamweb_qiraat_scraper.py --book 245 --export

  # Scrape specific page range
  python islamweb_qiraat_scraper.py --book 245 --start 50 --end 100
        """
    )

    parser.add_argument('--book', type=int, default=245,
                        help='Book ID to scrape (default: 245)')
    parser.add_argument('--start', type=int, default=1,
                        help='Start page (default: 1)')
    parser.add_argument('--end', type=int,
                        help='End page (default: all pages)')
    parser.add_argument('--export', action='store_true',
                        help='Export to JSON files')
    parser.add_argument('--stats', action='store_true',
                        help='Show statistics only')
    parser.add_argument('--list-books', action='store_true',
                        help='List available books')

    args = parser.parse_args()

    # List available books
    if args.list_books:
        print("\nAvailable Qiraat Books:")
        print("=" * 60)
        for book_id, info in QIRAAT_BOOKS.items():
            print(f"\nBook ID: {book_id}")
            print(f"  Arabic: {info['name_arabic']}")
            print(f"  English: {info['name_english']}")
            print(f"  Author: {info['author_arabic']}")
            print(f"  Pages: {info['total_pages']}")
            print(f"  Covers: {', '.join(info['covers_qiraat'])}")
        return

    # Setup
    setup_database()
    os.makedirs(EXPORT_PATH, exist_ok=True)

    # Show statistics only
    if args.stats:
        stats = get_statistics(args.book)
        print(f"\nStatistics for Book {args.book}:")
        print("=" * 40)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return

    # Validate book
    if args.book not in QIRAAT_BOOKS:
        print(f"Error: Unknown book ID {args.book}")
        print("Use --list-books to see available books")
        return

    book_info = QIRAAT_BOOKS[args.book]

    print("=" * 60)
    print("islamweb.net Qiraat Scraper")
    print("=" * 60)
    print(f"\nBook: {book_info['name_arabic']}")
    print(f"      ({book_info['name_english']})")
    print(f"Author: {book_info['author_arabic']}")
    print(f"Pages: {args.start} to {args.end or book_info['total_pages']}")
    print("=" * 60)

    # Create session
    session = requests.Session()

    # Scrape book
    print(f"\nScraping book {args.book}...")
    data = scrape_book(session, args.book, args.start, args.end)

    if not data:
        print("\nNo content scraped!")
        return

    print(f"\nScraped {len(data)} pages")

    # Import to database
    print("\nImporting to database...")
    imported = import_to_database(data, args.book)
    print(f"Imported {imported} pages to database")

    # Export to JSON
    if args.export:
        print("\nExporting to JSON...")
        export_to_json(data, args.book, EXPORT_PATH)

    # Show statistics
    stats = get_statistics(args.book)
    print("\nFinal Statistics:")
    print("=" * 40)
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("Scraping complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
