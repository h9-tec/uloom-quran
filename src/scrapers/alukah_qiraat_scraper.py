#!/usr/bin/env python3
"""
Alukah.net Scraper for Qiraat (القراءات) Resources

This scraper collects scholarly content on Quranic readings from alukah.net,
a major Islamic scholarly network with quality content.

Target Resources:
1. متن الشاطبية - The Shatibiyyah poem (القراءات السبع)
2. متن الدرة المضية - The Durra poem (القراءات الثلاث المتممة للعشر)
3. طيبة النشر - Tayyibat al-Nashr (القراءات العشر)
4. شرح أصول القراءات - Explanations of Qiraat principles
5. الفرش والأصول - Farsh and Usul (specific vs general rules)

Author: Auto-generated
License: For educational purposes only
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import os
import json
import argparse
import re
from urllib.parse import urljoin, quote
from datetime import datetime

# Constants
BASE_URL = "https://www.alukah.net"
LIBRARY_BASE = "https://www.alukah.net/library"
SHARIA_BASE = "https://www.alukah.net/sharia"
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'uloom_quran.db')
EXPORT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed', 'alukah_qiraat')

# Headers for requests (note: removed Accept-Encoding to avoid decompression issues)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
}

# Qiraat resources with their URLs discovered from alukah.net
QIRAAT_RESOURCES = {
    'shatibiyyah': {
        'name_arabic': 'متن الشاطبية',
        'name_english': 'Matn al-Shatibiyyah',
        'description': 'حرز الأماني ووجه التهاني - منظومة في القراءات السبع للإمام الشاطبي',
        'category': 'mutun',
        'urls': [
            'https://www.alukah.net/library/0/101781/',  # مخطوطة الشاطبية
            'https://www.alukah.net/culture/0/140118/',  # الوافي في شرح الشاطبية
            'https://www.alukah.net/sharia/0/117921/',   # ترجمة الإمام الشاطبي
            'https://www.alukah.net/library/0/101663/',  # شرح الشاطبية - سراج القارئ
        ],
        'pdf_urls': [
            'https://www.alukah.net/books/files/book_13121/bookfile/shatbiaa.pdf',
        ]
    },
    'durra': {
        'name_arabic': 'متن الدرة المضية',
        'name_english': 'Matn al-Durra al-Mudiyya',
        'description': 'الدرة المضية في القراءات الثلاث المتممة للعشر - لابن الجزري',
        'category': 'mutun',
        'urls': [
            'https://www.alukah.net/library/0/119437/',  # الغرة البهية في شرح الدرة
            'https://www.alukah.net/sharia/0/52804/',    # مخطوطة الدرة المضية
            'https://www.alukah.net/library/0/81194/',   # مخطوطة الدرة
            'https://www.alukah.net/library/0/101974/',  # الغرة البهية شرح الدرة
        ],
        'pdf_urls': []
    },
    'tayyiba': {
        'name_arabic': 'طيبة النشر',
        'name_english': 'Tayyibat al-Nashr',
        'description': 'طيبة النشر في القراءات العشر - لابن الجزري',
        'category': 'mutun',
        'urls': [
            'https://www.alukah.net/library/0/101859/',  # مخطوطة طيبة النشر (نسخة ثانية)
            'https://www.alukah.net/library/0/72547/',   # تحرير طيبة النشر
            'https://www.alukah.net/sharia/0/85384/',    # الكتب التي جمع منها ابن الجزري
            'https://www.alukah.net/library/0/101857/',  # مخطوطة طيبة النشر
            'https://www.alukah.net/library/0/76139/',   # مخطوطة النشر في القراءات العشر
        ],
        'pdf_urls': []
    },
    'usul_qiraat': {
        'name_arabic': 'شرح أصول القراءات',
        'name_english': 'Sharh Usul al-Qiraat',
        'description': 'شروحات وتوضيحات لأصول القراءات القرآنية',
        'category': 'shuruh',
        'urls': [
            'https://www.alukah.net/sharia/0/125024/',   # أرجوزة فوح العطر في نظم أصول النشر
            'https://www.alukah.net/sharia/0/44534/',    # ثبوت القراءات
            'https://www.alukah.net/sharia/0/68026/',    # قواعد وإشارات في علم القراءات
            'https://www.alukah.net/library/0/69756/',   # نبذة عن علم القراءات
            'https://www.alukah.net/library/0/75517/',   # الكشف عن وجوه القراءات السبع
        ],
        'pdf_urls': []
    },
    'farsh_usul': {
        'name_arabic': 'الفرش والأصول',
        'name_english': 'Al-Farsh wa al-Usul',
        'description': 'الفرش (الكلمات الخاصة بكل سورة) والأصول (القواعد العامة المطردة)',
        'category': 'shuruh',
        'urls': [
            'https://www.alukah.net/sharia/0/26244/',    # مناهج المصنفين في ذكر أوجه القراءات
            'https://www.alukah.net/sharia/0/37/',       # القراءات الشاذة
            'https://www.alukah.net/sharia/0/4313/',     # لمع من علم الصوت في القراءات
        ],
        'pdf_urls': []
    }
}


def setup_database():
    """Create tables for qiraat scholarly content if not exists"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    # Table for qiraat scholarly resources/books
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_scholarly_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_key TEXT UNIQUE NOT NULL,
            name_arabic TEXT NOT NULL,
            name_english TEXT,
            description TEXT,
            category TEXT CHECK(category IN ('mutun', 'shuruh', 'makhtutat', 'articles')),
            author_name TEXT,
            source_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for individual articles/content from alukah
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_scholarly_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            content_type TEXT CHECK(content_type IN ('article', 'manuscript', 'book', 'pdf', 'sharh')),
            author TEXT,
            content_text TEXT,
            summary TEXT,
            has_pdf INTEGER DEFAULT 0,
            pdf_url TEXT,
            source TEXT DEFAULT 'alukah.net',
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resource_id) REFERENCES qiraat_scholarly_resources(id)
        )
    """)

    # Table for extracted qiraat-specific information
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_extracted_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            info_type TEXT CHECK(info_type IN ('qari', 'rawi', 'rule', 'example', 'variant', 'ijma', 'khilaf')),
            info_text TEXT NOT NULL,
            related_verse TEXT,
            related_surah INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES qiraat_scholarly_content(id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_content_resource ON qiraat_scholarly_content(resource_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_content_type ON qiraat_scholarly_content(content_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_info_type ON qiraat_extracted_info(info_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qiraat_info_content ON qiraat_extracted_info(content_id)")

    conn.commit()
    conn.close()
    print("Database tables for qiraat scholarly content ready")


def init_resources():
    """Initialize the qiraat resources in the database"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    for key, resource in QIRAAT_RESOURCES.items():
        cursor.execute("""
            INSERT OR IGNORE INTO qiraat_scholarly_resources
            (resource_key, name_arabic, name_english, description, category)
            VALUES (?, ?, ?, ?, ?)
        """, (
            key,
            resource['name_arabic'],
            resource['name_english'],
            resource['description'],
            resource['category']
        ))

    conn.commit()
    conn.close()
    print("Qiraat resources initialized")


def get_resource_id(cursor, resource_key):
    """Get resource ID from database"""
    cursor.execute("SELECT id FROM qiraat_scholarly_resources WHERE resource_key = ?", (resource_key,))
    row = cursor.fetchone()
    return row[0] if row else None


def scrape_alukah_page(url, session):
    """Scrape content from an alukah.net page"""
    try:
        response = session.get(url, headers=HEADERS, timeout=30)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            print(f"  HTTP {response.status_code} for {url}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract title
        title = None
        title_elem = soup.find('h1') or soup.find('title')
        if title_elem:
            title = title_elem.get_text(strip=True)
            # Clean title
            title = re.sub(r'\s+', ' ', title)
            title = title.replace(' - شبكة الألوكة', '').strip()

        # Extract author if present
        author = None
        author_elem = soup.find('span', class_='author') or soup.find('a', class_='author')
        if author_elem:
            author = author_elem.get_text(strip=True)

        # Try to find the main content - alukah.net specific selectors
        content = None
        content_selectors = [
            'div.content-data',          # Main content on alukah.net
            'div.content-windowBack',    # Content wrapper
            'div.content-area',          # Content area
            'div.article-content',
            'article',
            'div.entry-content',
            'div.post-content',
            '#content',
            'div.main-content',
        ]

        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                content = elem
                break

        if not content:
            # Fallback: get body content
            body = soup.find('body')
            if body:
                # Remove unwanted elements
                for tag in body.find_all(['nav', 'header', 'footer', 'script', 'style', 'aside', 'form']):
                    tag.decompose()
                content = body

        if not content:
            return None

        # Extract text content
        text = content.get_text(separator='\n', strip=True)

        # Clean up the text
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # Remove navigation and common footer patterns
        skip_patterns = [
            'الفهرس', 'الرئيسية', 'شارك بتعليقك', 'أضف تعليقا',
            'إرسال تعليق', 'التعليقات', 'مواضيع ذات صلة',
            'الشبكات الاجتماعية', 'تويتر', 'فيسبوك', 'واتساب',
            'حقوق النشر', 'جميع الحقوق', 'شبكة الألوكة',
            'سياسة الخصوصية', 'اتصل بنا', 'الأرشيف'
        ]

        filtered_lines = []
        for line in lines:
            if not any(p in line for p in skip_patterns) and len(line) > 5:
                filtered_lines.append(line)

        content_text = '\n'.join(filtered_lines)

        # Check for PDF links
        pdf_url = None
        pdf_link = soup.find('a', href=re.compile(r'\.pdf$', re.I))
        if pdf_link:
            pdf_url = urljoin(url, pdf_link['href'])

        # Generate summary (first 500 chars)
        summary = content_text[:500] + '...' if len(content_text) > 500 else content_text

        return {
            'title': title,
            'author': author,
            'content_text': content_text,
            'summary': summary,
            'has_pdf': 1 if pdf_url else 0,
            'pdf_url': pdf_url
        }

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


def determine_content_type(url):
    """Determine the type of content based on URL patterns"""
    url_lower = url.lower()
    if '/library/' in url_lower and 'مخطوط' in url_lower:
        return 'manuscript'
    elif '.pdf' in url_lower:
        return 'pdf'
    elif '/library/' in url_lower:
        return 'book'
    elif 'شرح' in url_lower:
        return 'sharh'
    else:
        return 'article'


def save_content_to_db(resource_key, url, data, content_type):
    """Save scraped content to database"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    resource_id = get_resource_id(cursor, resource_key)

    try:
        cursor.execute("""
            INSERT OR REPLACE INTO qiraat_scholarly_content
            (resource_id, title, url, content_type, author, content_text, summary, has_pdf, pdf_url, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'alukah.net')
        """, (
            resource_id,
            data['title'],
            url,
            content_type,
            data['author'],
            data['content_text'],
            data['summary'],
            data['has_pdf'],
            data['pdf_url']
        ))
        conn.commit()
        content_id = cursor.lastrowid
        conn.close()
        return content_id
    except Exception as e:
        print(f"  Database error: {e}")
        conn.close()
        return None


def extract_qiraat_info(content_id, content_text):
    """Extract qiraat-specific information from content"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    extracted_count = 0

    # Patterns for extracting qiraat information
    patterns = {
        'qari': [
            r'(نافع|ابن كثير|أبو عمرو|ابن عامر|عاصم|حمزة|الكسائي|أبو جعفر|يعقوب|خلف)',
            r'قرأ\s+(\S+)',
        ],
        'rawi': [
            r'(قالون|ورش|البزي|قنبل|الدوري|السوسي|هشام|ابن ذكوان|شعبة|حفص|خلف|خلاد)',
            r'رواية\s+(\S+)',
        ],
        'rule': [
            r'(الإمالة|الإدغام|المد|القصر|الإظهار|الإخفاء|الإقلاب|الغنة|التسهيل|الإبدال)',
            r'قاعدة[:\s]+(.+?)(?:\.|$)',
        ],
        'variant': [
            r'قرأ.+?بـ?[:\s]*([^،.]+)',
            r'الخلاف في[:\s]+(.+?)(?:\.|$)',
        ]
    }

    for info_type, type_patterns in patterns.items():
        for pattern in type_patterns:
            matches = re.findall(pattern, content_text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if len(match) > 2 and len(match) < 200:  # Reasonable length
                    try:
                        cursor.execute("""
                            INSERT INTO qiraat_extracted_info
                            (content_id, info_type, info_text)
                            VALUES (?, ?, ?)
                        """, (content_id, info_type, match.strip()))
                        extracted_count += 1
                    except:
                        pass  # Skip duplicates

    conn.commit()
    conn.close()
    return extracted_count


def scrape_resource(resource_key, session, export=False):
    """Scrape all URLs for a given resource"""
    if resource_key not in QIRAAT_RESOURCES:
        print(f"Unknown resource: {resource_key}")
        return 0

    resource = QIRAAT_RESOURCES[resource_key]
    print(f"\n{'='*60}")
    print(f"Scraping: {resource['name_arabic']} ({resource['name_english']})")
    print(f"Category: {resource['category']}")
    print(f"URLs to scrape: {len(resource['urls'])}")
    print('='*60)

    scraped_count = 0
    all_data = []

    for url in resource['urls']:
        print(f"\n  Fetching: {url}")
        data = scrape_alukah_page(url, session)

        if data and data['content_text']:
            content_type = determine_content_type(url)
            print(f"  Title: {data['title'][:50]}..." if data['title'] else "  Title: N/A")
            print(f"  Type: {content_type}")
            print(f"  Content length: {len(data['content_text'])} chars")

            # Save to database
            content_id = save_content_to_db(resource_key, url, data, content_type)
            if content_id:
                scraped_count += 1
                print(f"  Saved to database (ID: {content_id})")

                # Extract qiraat information
                info_count = extract_qiraat_info(content_id, data['content_text'])
                print(f"  Extracted {info_count} qiraat info items")

                # Prepare for export
                if export:
                    all_data.append({
                        'url': url,
                        'title': data['title'],
                        'author': data['author'],
                        'content_type': content_type,
                        'summary': data['summary'],
                        'pdf_url': data['pdf_url'],
                        'content_length': len(data['content_text'])
                    })
        else:
            print(f"  No content retrieved")

        time.sleep(1)  # Rate limiting

    # Export to JSON if requested
    if export and all_data:
        os.makedirs(EXPORT_PATH, exist_ok=True)
        export_file = os.path.join(EXPORT_PATH, f'{resource_key}.json')
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump({
                'resource': resource,
                'scraped_at': datetime.now().isoformat(),
                'items': all_data
            }, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported to: {export_file}")

    return scraped_count


def download_pdf(url, output_dir, session):
    """Download a PDF file"""
    try:
        response = session.get(url, headers=HEADERS, timeout=60, stream=True)
        if response.status_code == 200:
            filename = os.path.basename(url)
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return filepath
    except Exception as e:
        print(f"  Error downloading PDF: {e}")
    return None


def get_stats():
    """Get statistics from the database"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM qiraat_scholarly_resources")
    stats['resources'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM qiraat_scholarly_content")
    stats['content_items'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM qiraat_extracted_info")
    stats['extracted_info'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT r.name_arabic, COUNT(c.id) as count
        FROM qiraat_scholarly_resources r
        LEFT JOIN qiraat_scholarly_content c ON r.id = c.resource_id
        GROUP BY r.id
    """)
    stats['by_resource'] = cursor.fetchall()

    cursor.execute("""
        SELECT info_type, COUNT(*) as count
        FROM qiraat_extracted_info
        GROUP BY info_type
    """)
    stats['by_info_type'] = cursor.fetchall()

    conn.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description='Scrape Qiraat resources from alukah.net')
    parser.add_argument('--resource', choices=list(QIRAAT_RESOURCES.keys()) + ['all'], default='all',
                        help='Specific resource to scrape')
    parser.add_argument('--export', action='store_true', help='Export to JSON files')
    parser.add_argument('--download-pdfs', action='store_true', help='Download PDF files')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--init-only', action='store_true', help='Only initialize database without scraping')
    args = parser.parse_args()

    # Setup
    setup_database()
    init_resources()

    if args.init_only:
        print("Database initialized. Exiting.")
        return

    if args.stats:
        stats = get_stats()
        print("\n" + "="*60)
        print("Database Statistics")
        print("="*60)
        print(f"Total resources: {stats['resources']}")
        print(f"Total content items: {stats['content_items']}")
        print(f"Total extracted info: {stats['extracted_info']}")
        print("\nContent by resource:")
        for name, count in stats['by_resource']:
            print(f"  {name}: {count}")
        print("\nExtracted info by type:")
        for info_type, count in stats['by_info_type']:
            print(f"  {info_type}: {count}")
        return

    session = requests.Session()

    print("="*60)
    print("Alukah.net Qiraat Scraper")
    print("="*60)
    print(f"Target: {args.resource}")
    print(f"Export: {'Yes' if args.export else 'No'}")
    print(f"Download PDFs: {'Yes' if args.download_pdfs else 'No'}")

    total_scraped = 0

    if args.resource == 'all':
        resources_to_scrape = list(QIRAAT_RESOURCES.keys())
    else:
        resources_to_scrape = [args.resource]

    for resource_key in resources_to_scrape:
        count = scrape_resource(resource_key, session, export=args.export)
        total_scraped += count

        # Download PDFs if requested
        if args.download_pdfs:
            pdf_dir = os.path.join(EXPORT_PATH, 'pdfs', resource_key)
            os.makedirs(pdf_dir, exist_ok=True)
            for pdf_url in QIRAAT_RESOURCES[resource_key].get('pdf_urls', []):
                print(f"\n  Downloading PDF: {pdf_url}")
                filepath = download_pdf(pdf_url, pdf_dir, session)
                if filepath:
                    print(f"  Saved to: {filepath}")

        time.sleep(2)  # Rate limiting between resources

    print("\n" + "="*60)
    print("Scraping Complete!")
    print("="*60)
    print(f"Total items scraped: {total_scraped}")

    # Show final stats
    stats = get_stats()
    print(f"\nDatabase now contains:")
    print(f"  {stats['content_items']} content items")
    print(f"  {stats['extracted_info']} extracted info items")


if __name__ == "__main__":
    main()
