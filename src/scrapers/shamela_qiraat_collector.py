#!/usr/bin/env python3
"""
Shamela.ws Qiraat Books Collector
Collects metadata and references for قراءات (Qiraat/Readings) books from المكتبة الشاملة

Books covered:
1. متن الشاطبية (حرز الأماني ووجه التهاني)
2. شروح الشاطبية (إبراز المعاني، سراج القارئ)
3. متن الدرة المضية في القراءات الثلاث
4. النشر في القراءات العشر لابن الجزري
5. طيبة النشر في القراءات العشر
6. إتحاف فضلاء البشر في القراءات الأربعة عشر
7. الهادي شرح طيبة النشر

Data sources:
- shamela.ws (main site)
- old.shamela.ws (legacy site with additional metadata)
"""

import sqlite3
import json
import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import requests
from bs4 import BeautifulSoup
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "db" / "uloom_quran.db"
EXPORT_PATH = BASE_DIR / "data" / "exports" / "shamela_qiraat"

# Shamela URLs
SHAMELA_BASE = "https://shamela.ws"
SHAMELA_OLD = "https://old.shamela.ws"
SHAMELA_CATEGORY_QIRAAT = f"{SHAMELA_BASE}/category/5"  # التجويد والقراءات

# Request headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
}


@dataclass
class ShamelaBook:
    """Data class for Shamela book metadata"""
    shamela_id: int
    title_arabic: str
    title_english: Optional[str] = None
    author_arabic: Optional[str] = None
    author_english: Optional[str] = None
    author_death_hijri: Optional[int] = None
    editor: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    year_published: Optional[str] = None
    volume_count: Optional[int] = None
    page_count: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    table_of_contents: Optional[str] = None  # JSON string
    shamela_url: Optional[str] = None
    download_url: Optional[str] = None
    is_qiraat_book: int = 1
    book_type: Optional[str] = None  # matn, sharh, reference
    related_to: Optional[str] = None  # For sharh books - which matn it explains


# Qiraat books to collect (with known Shamela IDs from research)
QIRAAT_BOOKS = [
    # متن الشاطبية وشروحها
    {
        'shamela_id': 7754,
        'title_arabic': 'متن الشاطبية = حرز الأماني ووجه التهاني في القراءات السبع',
        'author_arabic': 'القاسم بن فيره بن خلف بن أحمد الرعيني، أبو محمد الشاطبي',
        'author_death_hijri': 590,
        'book_type': 'matn',
        'category': 'التجويد والقراءات',
        'subcategory': 'القراءات السبع',
    },
    {
        'shamela_id': 5486,
        'title_arabic': 'إبراز المعاني من حرز الأماني (شرح الشاطبية)',
        'author_arabic': 'عبد الرحمن بن إسماعيل بن إبراهيم المقدسي، أبو شامة',
        'author_death_hijri': 665,
        'book_type': 'sharh',
        'related_to': 'متن الشاطبية',
        'category': 'التجويد والقراءات',
        'subcategory': 'شروح الشاطبية',
    },
    {
        'shamela_id': 95577,
        'title_arabic': 'سراج القارئ المبتدي وتذكار المقرئ المنتهي (شرح الشاطبية)',
        'author_arabic': 'علي بن عثمان بن محمد، ابن القاصح العذري',
        'author_death_hijri': 801,
        'book_type': 'sharh',
        'related_to': 'متن الشاطبية',
        'category': 'التجويد والقراءات',
        'subcategory': 'شروح الشاطبية',
    },

    # متن الدرة المضية
    {
        'shamela_id': 7749,
        'title_arabic': 'الدرة المضية في القراءات الثلاث المتتمة للعشر',
        'author_arabic': 'شمس الدين أبو الخير ابن الجزري، محمد بن محمد بن يوسف',
        'author_death_hijri': 833,
        'book_type': 'matn',
        'category': 'التجويد والقراءات',
        'subcategory': 'القراءات الثلاث',
    },

    # النشر في القراءات العشر
    {
        'shamela_id': 22642,
        'title_arabic': 'النشر في القراءات العشر',
        'author_arabic': 'شمس الدين أبو الخير ابن الجزري، محمد بن محمد بن يوسف',
        'author_death_hijri': 833,
        'book_type': 'reference',
        'category': 'التجويد والقراءات',
        'subcategory': 'القراءات العشر',
        'description': 'المرجع الأساسي في القراءات العشر',
    },

    # طيبة النشر
    {
        'shamela_id': 7795,
        'title_arabic': 'متن طيبة النشر في القراءات العشر',
        'author_arabic': 'شمس الدين أبو الخير ابن الجزري، محمد بن محمد بن يوسف',
        'author_death_hijri': 833,
        'book_type': 'matn',
        'category': 'التجويد والقراءات',
        'subcategory': 'القراءات العشر',
    },
    {
        'shamela_id': 8650,
        'title_arabic': 'الهادي شرح طيبة النشر في القراءات العشر',
        'author_arabic': 'محمد محمد محمد سالم محيسن',
        'author_death_hijri': 1422,
        'book_type': 'sharh',
        'related_to': 'طيبة النشر',
        'category': 'التجويد والقراءات',
        'subcategory': 'شروح طيبة النشر',
    },
    {
        'shamela_id': 29596,
        'title_arabic': 'شرح طيبة النشر في القراءات',
        'author_arabic': 'شمس الدين أبو الخير ابن الجزري، محمد بن محمد بن يوسف',
        'author_death_hijri': 833,
        'book_type': 'sharh',
        'related_to': 'طيبة النشر',
        'category': 'التجويد والقراءات',
        'subcategory': 'شروح طيبة النشر',
    },

    # إتحاف فضلاء البشر
    {
        'shamela_id': 10010,
        'title_arabic': 'إتحاف فضلاء البشر في القراءات الأربعة عشر',
        'author_arabic': 'شهاب الدين أحمد بن محمد بن عبد الغني الدمياطي، البناء',
        'author_death_hijri': 1117,
        'book_type': 'reference',
        'category': 'التجويد والقراءات',
        'subcategory': 'القراءات الأربعة عشر',
        'description': 'شرح موسع على الشاطبية والدرة مع زيادة القراءات الأربع الشاذة',
    },

    # كتب تجويد وقراءات إضافية
    {
        'shamela_id': 29915,
        'title_arabic': 'مجموعة مهمة في التجويد والقراءات (15 متناً)',
        'author_arabic': 'جمع وترتيب: محمد عبد الواحد الدسوقى',
        'book_type': 'collection',
        'category': 'التجويد والقراءات',
        'subcategory': 'متون التجويد',
    },
]

# Additional books to search for
ADDITIONAL_SEARCH_TERMS = [
    'غيث النفع في القراءات السبع',
    'تقريب النشر في القراءات العشر',
    'منظومة المقدمة الجزرية',
    'شرح المقدمة الجزرية',
    'الوافي في شرح الشاطبية',
    'كنز المعاني في شرح حرز الأماني',
    'فتح الوصيد في شرح القصيد',
    'التيسير في القراءات السبع',
]


class ShamelaQiraatCollector:
    """Collector for Qiraat books from Shamela.ws"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.collected_books: List[ShamelaBook] = []

    def setup_database(self):
        """Create necessary tables for Shamela books"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create shamela_books table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shamela_books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shamela_id INTEGER UNIQUE NOT NULL,
                title_arabic TEXT NOT NULL,
                title_english TEXT,
                author_arabic TEXT,
                author_english TEXT,
                author_death_hijri INTEGER,
                editor TEXT,
                publisher TEXT,
                edition TEXT,
                year_published TEXT,
                volume_count INTEGER,
                page_count INTEGER,
                category TEXT,
                subcategory TEXT,
                description TEXT,
                table_of_contents TEXT,
                shamela_url TEXT,
                download_url TEXT,
                is_qiraat_book INTEGER DEFAULT 0,
                book_type TEXT,
                related_to TEXT,
                raw_metadata TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create shamela_book_chapters table for table of contents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shamela_book_chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                chapter_number INTEGER,
                chapter_title TEXT NOT NULL,
                parent_chapter_id INTEGER,
                page_start INTEGER,
                shamela_page_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES shamela_books(id),
                FOREIGN KEY (parent_chapter_id) REFERENCES shamela_book_chapters(id)
            )
        """)

        # Create shamela_book_content table for storing book text
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shamela_book_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                chapter_id INTEGER,
                page_number INTEGER,
                shamela_page_id INTEGER,
                content_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES shamela_books(id),
                FOREIGN KEY (chapter_id) REFERENCES shamela_book_chapters(id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shamela_books_category ON shamela_books(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shamela_books_type ON shamela_books(book_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shamela_chapters_book ON shamela_book_chapters(book_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shamela_content_book ON shamela_book_content(book_id)")

        conn.commit()
        conn.close()
        logger.info("Database tables created successfully")

    def fetch_book_page(self, book_id: int) -> Optional[str]:
        """Fetch a book's main page from Shamela"""
        url = f"{SHAMELA_BASE}/book/{book_id}"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 403:
                logger.warning(f"Access forbidden for book {book_id} - Shamela may require browser access")
                return None
            else:
                logger.warning(f"Failed to fetch book {book_id}: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching book {book_id}: {e}")
            return None

    def parse_book_metadata(self, html: str, book_id: int) -> Optional[Dict]:
        """Parse book metadata from Shamela page HTML"""
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        metadata = {'shamela_id': book_id}

        try:
            # Try to extract title
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                title = title_elem.get_text(strip=True)
                # Clean up title
                title = re.sub(r'\s*-\s*المكتبة الشاملة\s*$', '', title)
                metadata['title_arabic'] = title

            # Look for metadata in info boxes or lists
            for dl in soup.find_all(['dl', 'table']):
                for dt in dl.find_all(['dt', 'th']):
                    key = dt.get_text(strip=True)
                    dd = dt.find_next_sibling(['dd', 'td'])
                    if dd:
                        value = dd.get_text(strip=True)

                        if 'المؤلف' in key or 'الكاتب' in key:
                            metadata['author_arabic'] = value
                        elif 'المحقق' in key:
                            metadata['editor'] = value
                        elif 'الناشر' in key:
                            metadata['publisher'] = value
                        elif 'الطبعة' in key:
                            metadata['edition'] = value
                        elif 'عدد الصفحات' in key or 'الصفحات' in key:
                            try:
                                metadata['page_count'] = int(re.search(r'\d+', value).group())
                            except:
                                pass
                        elif 'عدد الأجزاء' in key or 'المجلدات' in key:
                            try:
                                metadata['volume_count'] = int(re.search(r'\d+', value).group())
                            except:
                                pass

            # Extract table of contents links
            toc_links = []
            for link in soup.find_all('a', href=re.compile(r'/book/\d+/\d+')):
                href = link.get('href', '')
                title = link.get_text(strip=True)
                if title and len(title) > 2:
                    toc_links.append({'title': title, 'href': href})

            if toc_links:
                metadata['table_of_contents'] = json.dumps(toc_links, ensure_ascii=False)

            metadata['shamela_url'] = f"{SHAMELA_BASE}/book/{book_id}"

            return metadata

        except Exception as e:
            logger.error(f"Error parsing metadata for book {book_id}: {e}")
            return None

    def collect_predefined_books(self) -> List[ShamelaBook]:
        """Collect all predefined Qiraat books"""
        books = []

        for book_data in QIRAAT_BOOKS:
            logger.info(f"Processing: {book_data['title_arabic']}")

            # Create book object with predefined data
            book = ShamelaBook(
                shamela_id=book_data['shamela_id'],
                title_arabic=book_data['title_arabic'],
                author_arabic=book_data.get('author_arabic'),
                author_death_hijri=book_data.get('author_death_hijri'),
                book_type=book_data.get('book_type'),
                related_to=book_data.get('related_to'),
                category=book_data.get('category'),
                subcategory=book_data.get('subcategory'),
                description=book_data.get('description'),
                shamela_url=f"{SHAMELA_BASE}/book/{book_data['shamela_id']}",
            )

            # Try to fetch additional metadata from Shamela
            html = self.fetch_book_page(book_data['shamela_id'])
            if html:
                parsed = self.parse_book_metadata(html, book_data['shamela_id'])
                if parsed:
                    # Update with parsed data (only if not already set)
                    if not book.editor and parsed.get('editor'):
                        book.editor = parsed['editor']
                    if not book.publisher and parsed.get('publisher'):
                        book.publisher = parsed['publisher']
                    if not book.edition and parsed.get('edition'):
                        book.edition = parsed['edition']
                    if not book.page_count and parsed.get('page_count'):
                        book.page_count = parsed['page_count']
                    if not book.volume_count and parsed.get('volume_count'):
                        book.volume_count = parsed['volume_count']
                    if parsed.get('table_of_contents'):
                        book.table_of_contents = parsed['table_of_contents']

            books.append(book)
            time.sleep(0.5)  # Rate limiting

        self.collected_books = books
        return books

    def save_to_database(self, books: List[ShamelaBook] = None):
        """Save collected books to database"""
        if books is None:
            books = self.collected_books

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        saved_count = 0
        for book in books:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO shamela_books (
                        shamela_id, title_arabic, title_english, author_arabic,
                        author_english, author_death_hijri, editor, publisher,
                        edition, year_published, volume_count, page_count,
                        category, subcategory, description, table_of_contents,
                        shamela_url, download_url, is_qiraat_book, book_type,
                        related_to, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    book.shamela_id, book.title_arabic, book.title_english,
                    book.author_arabic, book.author_english, book.author_death_hijri,
                    book.editor, book.publisher, book.edition, book.year_published,
                    book.volume_count, book.page_count, book.category,
                    book.subcategory, book.description, book.table_of_contents,
                    book.shamela_url, book.download_url, book.is_qiraat_book,
                    book.book_type, book.related_to, datetime.now().isoformat()
                ))
                saved_count += 1
                logger.info(f"Saved: {book.title_arabic}")
            except Exception as e:
                logger.error(f"Error saving book {book.shamela_id}: {e}")

        conn.commit()
        conn.close()

        logger.info(f"Saved {saved_count}/{len(books)} books to database")
        return saved_count

    def export_to_json(self, books: List[ShamelaBook] = None, filepath: Path = None):
        """Export collected books to JSON file"""
        if books is None:
            books = self.collected_books

        if filepath is None:
            os.makedirs(EXPORT_PATH, exist_ok=True)
            filepath = EXPORT_PATH / f"shamela_qiraat_books_{datetime.now().strftime('%Y%m%d')}.json"

        data = {
            'collection_date': datetime.now().isoformat(),
            'source': 'shamela.ws',
            'category': 'التجويد والقراءات',
            'book_count': len(books),
            'books': [asdict(book) for book in books]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(books)} books to {filepath}")
        return filepath

    def get_book_statistics(self) -> Dict:
        """Get statistics about collected qiraat books"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Total qiraat books
        cursor.execute("SELECT COUNT(*) FROM shamela_books WHERE is_qiraat_book = 1")
        stats['total_qiraat_books'] = cursor.fetchone()[0]

        # By book type
        cursor.execute("""
            SELECT book_type, COUNT(*)
            FROM shamela_books
            WHERE is_qiraat_book = 1
            GROUP BY book_type
        """)
        stats['by_type'] = dict(cursor.fetchall())

        # By subcategory
        cursor.execute("""
            SELECT subcategory, COUNT(*)
            FROM shamela_books
            WHERE is_qiraat_book = 1 AND subcategory IS NOT NULL
            GROUP BY subcategory
        """)
        stats['by_subcategory'] = dict(cursor.fetchall())

        # Authors
        cursor.execute("""
            SELECT DISTINCT author_arabic
            FROM shamela_books
            WHERE is_qiraat_book = 1 AND author_arabic IS NOT NULL
        """)
        stats['authors'] = [row[0] for row in cursor.fetchall()]

        conn.close()
        return stats

    def print_collection_summary(self):
        """Print a summary of collected books"""
        stats = self.get_book_statistics()

        print("\n" + "=" * 70)
        print("مجموعة كتب القراءات من المكتبة الشاملة")
        print("Shamela.ws Qiraat Books Collection")
        print("=" * 70)

        print(f"\nإجمالي الكتب: {stats['total_qiraat_books']}")

        if stats.get('by_type'):
            print("\nحسب النوع:")
            type_names = {
                'matn': 'متن',
                'sharh': 'شرح',
                'reference': 'مرجع',
                'collection': 'مجموعة'
            }
            for book_type, count in stats['by_type'].items():
                ar_name = type_names.get(book_type, book_type or 'غير محدد')
                print(f"  {ar_name}: {count}")

        if stats.get('by_subcategory'):
            print("\nحسب التصنيف الفرعي:")
            for subcat, count in stats['by_subcategory'].items():
                print(f"  {subcat}: {count}")

        if stats.get('authors'):
            print(f"\nعدد المؤلفين: {len(stats['authors'])}")

        print("\n" + "=" * 70)


def generate_book_reference_data() -> Dict:
    """
    Generate comprehensive reference data for qiraat books
    This data can be used even if Shamela is not accessible
    """
    return {
        'متن الشاطبية': {
            'full_title': 'حرز الأماني ووجه التهاني في القراءات السبع',
            'author': 'الإمام الشاطبي (أبو القاسم بن فيره)',
            'death_year': 590,
            'verses_count': 1173,
            'description': 'منظومة في القراءات السبع من طريق التيسير',
            'shamela_id': 7754,
            'shamela_url': 'https://shamela.ws/book/7754',
            'qurra_covered': ['نافع', 'ابن كثير', 'أبو عمرو', 'ابن عامر', 'عاصم', 'حمزة', 'الكسائي'],
            'main_shuruh': [
                {'title': 'إبراز المعاني من حرز الأماني', 'author': 'أبو شامة', 'shamela_id': 5486},
                {'title': 'سراج القارئ', 'author': 'ابن القاصح', 'shamela_id': 95577},
            ]
        },
        'الدرة المضية': {
            'full_title': 'الدرة المضية في القراءات الثلاث المتتمة للعشر',
            'author': 'ابن الجزري',
            'death_year': 833,
            'verses_count': 241,
            'description': 'منظومة تكمل الشاطبية بالقراءات الثلاث المتممة للعشر',
            'shamela_id': 7749,
            'shamela_url': 'https://shamela.ws/book/7749',
            'qurra_covered': ['أبو جعفر', 'يعقوب', 'خلف العاشر'],
        },
        'النشر في القراءات العشر': {
            'full_title': 'النشر في القراءات العشر',
            'author': 'ابن الجزري',
            'death_year': 833,
            'volumes': 2,
            'description': 'المرجع الأساسي في القراءات العشر، يجمع طرقاً متعددة',
            'shamela_id': 22642,
            'shamela_url': 'https://shamela.ws/book/22642',
            'editor': 'علي محمد الضباع',
        },
        'طيبة النشر': {
            'full_title': 'طيبة النشر في القراءات العشر',
            'author': 'ابن الجزري',
            'death_year': 833,
            'verses_count': 1014,
            'description': 'منظومة تختصر النشر وتضم 980 طريقاً',
            'shamela_id': 7795,
            'shamela_url': 'https://shamela.ws/book/7795',
            'main_shuruh': [
                {'title': 'الهادي شرح طيبة النشر', 'author': 'محمد سالم محيسن', 'shamela_id': 8650},
                {'title': 'شرح طيبة النشر', 'author': 'ابن الجزري', 'shamela_id': 29596},
            ]
        },
        'إتحاف فضلاء البشر': {
            'full_title': 'إتحاف فضلاء البشر في القراءات الأربعة عشر',
            'author': 'البنا الدمياطي',
            'death_year': 1117,
            'description': 'شرح موسع يجمع القراءات العشر المتواترة مع الأربع الشاذة',
            'shamela_id': 10010,
            'shamela_url': 'https://shamela.ws/book/10010',
            'qurra_covered_extra': ['ابن محيصن', 'الحسن البصري', 'الأعمش', 'اليزيدي'],
        }
    }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Collect Qiraat books metadata from Shamela.ws'
    )
    parser.add_argument('--setup', action='store_true', help='Setup database tables')
    parser.add_argument('--collect', action='store_true', help='Collect book metadata')
    parser.add_argument('--export', action='store_true', help='Export to JSON')
    parser.add_argument('--stats', action='store_true', help='Show collection statistics')
    parser.add_argument('--reference', action='store_true', help='Generate reference data (no web access)')
    parser.add_argument('--all', action='store_true', help='Run all operations')

    args = parser.parse_args()

    collector = ShamelaQiraatCollector()

    if args.setup or args.all:
        print("\n--- Setting up database ---")
        collector.setup_database()

    if args.collect or args.all:
        print("\n--- Collecting Qiraat books ---")
        books = collector.collect_predefined_books()
        collector.save_to_database(books)

    if args.export or args.all:
        print("\n--- Exporting to JSON ---")
        if not collector.collected_books:
            # Load from database if not already collected
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shamela_books WHERE is_qiraat_book = 1")
            rows = cursor.fetchall()
            # Create book objects from database
            columns = [desc[0] for desc in cursor.description]
            for row in rows:
                book_dict = dict(zip(columns, row))
                book = ShamelaBook(
                    shamela_id=book_dict['shamela_id'],
                    title_arabic=book_dict['title_arabic'],
                    title_english=book_dict.get('title_english'),
                    author_arabic=book_dict.get('author_arabic'),
                    author_english=book_dict.get('author_english'),
                    author_death_hijri=book_dict.get('author_death_hijri'),
                    editor=book_dict.get('editor'),
                    publisher=book_dict.get('publisher'),
                    edition=book_dict.get('edition'),
                    year_published=book_dict.get('year_published'),
                    volume_count=book_dict.get('volume_count'),
                    page_count=book_dict.get('page_count'),
                    category=book_dict.get('category'),
                    subcategory=book_dict.get('subcategory'),
                    description=book_dict.get('description'),
                    table_of_contents=book_dict.get('table_of_contents'),
                    shamela_url=book_dict.get('shamela_url'),
                    download_url=book_dict.get('download_url'),
                    is_qiraat_book=book_dict.get('is_qiraat_book', 1),
                    book_type=book_dict.get('book_type'),
                    related_to=book_dict.get('related_to'),
                )
                collector.collected_books.append(book)
            conn.close()
        collector.export_to_json()

    if args.reference:
        print("\n--- Generating reference data ---")
        ref_data = generate_book_reference_data()
        os.makedirs(EXPORT_PATH, exist_ok=True)
        ref_path = EXPORT_PATH / "qiraat_books_reference.json"
        with open(ref_path, 'w', encoding='utf-8') as f:
            json.dump(ref_data, f, ensure_ascii=False, indent=2)
        print(f"Reference data saved to: {ref_path}")

        # Also save to database as structured reference
        collector.setup_database()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for book_name, book_info in ref_data.items():
            cursor.execute("""
                INSERT OR REPLACE INTO shamela_books (
                    shamela_id, title_arabic, author_arabic, author_death_hijri,
                    description, shamela_url, is_qiraat_book, book_type,
                    raw_metadata, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 'reference', ?, ?)
            """, (
                book_info.get('shamela_id'),
                book_info.get('full_title', book_name),
                book_info.get('author'),
                book_info.get('death_year'),
                book_info.get('description'),
                book_info.get('shamela_url'),
                json.dumps(book_info, ensure_ascii=False),
                datetime.now().isoformat()
            ))

        conn.commit()
        conn.close()
        print("Reference data saved to database")

    if args.stats or args.all:
        print("\n--- Collection Statistics ---")
        collector.print_collection_summary()

    if not any([args.setup, args.collect, args.export, args.stats, args.reference, args.all]):
        # Default: run with reference data (works offline)
        print("Running with reference data (no web access required)...")
        collector.setup_database()

        ref_data = generate_book_reference_data()
        os.makedirs(EXPORT_PATH, exist_ok=True)

        # Save reference data
        ref_path = EXPORT_PATH / "qiraat_books_reference.json"
        with open(ref_path, 'w', encoding='utf-8') as f:
            json.dump(ref_data, f, ensure_ascii=False, indent=2)

        # Insert predefined books to database
        for book_data in QIRAAT_BOOKS:
            book = ShamelaBook(
                shamela_id=book_data['shamela_id'],
                title_arabic=book_data['title_arabic'],
                author_arabic=book_data.get('author_arabic'),
                author_death_hijri=book_data.get('author_death_hijri'),
                book_type=book_data.get('book_type'),
                related_to=book_data.get('related_to'),
                category=book_data.get('category'),
                subcategory=book_data.get('subcategory'),
                description=book_data.get('description'),
                shamela_url=f"{SHAMELA_BASE}/book/{book_data['shamela_id']}",
            )
            collector.collected_books.append(book)

        collector.save_to_database()
        collector.export_to_json()
        collector.print_collection_summary()

        print(f"\nReference data: {ref_path}")
        print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
