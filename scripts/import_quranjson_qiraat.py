#!/usr/bin/env python3
"""
Import قراءات data from QuranJSON repository

This script imports Quran text for multiple qiraat/riwayat from the QuranJSON project:
- Hafs, Warsh, Qaloun, Shuba, Sousi, Douri

The data comes from plain text files that need to be parsed.
"""

import sqlite3
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw', 'QuranJSON', 'data')
DB_PATH = os.path.join(BASE_DIR, 'db', 'uloom_quran.db')

# Available qiraat in QuranJSON
QIRAAT_FILES = {
    'hafs_qj': ('Hafs.txt', 'حفص عن عاصم (QuranJSON)', 'Hafs from Asim (QuranJSON)'),
    'warsh_qj': ('Warsh.txt', 'ورش عن نافع (QuranJSON)', 'Warsh from Nafi (QuranJSON)'),
    'qaloun_qj': ('Qaloun.txt', 'قالون عن نافع (QuranJSON)', 'Qaloon from Nafi (QuranJSON)'),
    'shuba_qj': ('Shuba.txt', 'شعبة عن عاصم (QuranJSON)', 'Shuba from Asim (QuranJSON)'),
    'sousi_qj': ('Sousi.txt', 'السوسي عن أبي عمرو (QuranJSON)', 'Al-Soosi from Abu Amr (QuranJSON)'),
    'douri_qj': ('Douri.txt', 'الدوري عن أبي عمرو (QuranJSON)', 'Al-Douri from Abu Amr (QuranJSON)'),
}

# Surah names for mapping
SURAH_NAMES = [
    "الفَاتِحَةِ", "البَقَرَةِ", "آلِ عِمۡرَانَ", "النِّسَاءِ", "المَائِدَةِ",
    "الأَنۡعَامِ", "الأَعۡرَافِ", "الأَنفَالِ", "التَّوۡبَةِ", "يُونُسَ",
    "هُودٍ", "يُوسُفَ", "الرَّعۡدِ", "إِبۡرَاهِيمَ", "الحِجۡرِ",
    "النَّحۡلِ", "الإِسۡرَاءِ", "الكَهۡفِ", "مَرۡيَمَ", "طَهَ",
    "الأَنۡبِيَاءِ", "الحَجِّ", "المُؤۡمِنُونَ", "النُّورِ", "الفُرۡقَانِ",
    "الشُّعَرَاءِ", "النَّمۡلِ", "القَصَصِ", "العَنكَبُوتِ", "الرُّومِ",
    "لُقۡمَانَ", "السَّجۡدَةِ", "الأَحۡزَابِ", "سَبَإٍ", "فَاطِرٍ",
    "يَسٓ", "الصَّافَّاتِ", "صٓ", "الزُّمَرِ", "غَافِرٍ",
    "فُصِّلَتۡ", "الشُّورَىٰ", "الزُّخۡرُفِ", "الدُّخَانِ", "الجَاثِيَةِ",
    "الأَحۡقَافِ", "مُحَمَّدٍ", "الفَتۡحِ", "الحُجُرَاتِ", "قٓ",
    "الذَّارِيَاتِ", "الطُّورِ", "النَّجۡمِ", "القَمَرِ", "الرَّحۡمَٰنِ",
    "الوَاقِعَةِ", "الحَدِيدِ", "المُجَادِلَةِ", "الحَشۡرِ", "المُمۡتَحَنَةِ",
    "الصَّفِّ", "الجُمُعَةِ", "المُنَافِقُونَ", "التَّغَابُنِ", "الطَّلاقِ",
    "التَّحۡرِيمِ", "المُلۡكِ", "القَلَمِ", "الحَاقَّةِ", "المَعَارِجِ",
    "نُوحٍ", "الجِنِّ", "المُزَّمِّلِ", "المُدَّثِّرِ", "القِيَامَةِ",
    "الإِنسَانِ", "المُرۡسَلاتِ", "النَّبَإِ", "النَّازِعَاتِ", "عَبَسَ",
    "التَّكۡوِيرِ", "الانفِطَارِ", "المُطَفِّفِينَ", "الانشِقَاقِ", "البُرُوجِ",
    "الطَّارِقِ", "الأَعۡلَىٰ", "الغَاشِيَةِ", "الفَجۡرِ", "البَلَدِ",
    "الشَّمۡسِ", "اللَّيۡلِ", "الضُّحَىٰ", "الشَّرۡحِ", "التِّينِ",
    "العَلَقِ", "القَدۡرِ", "البَيِّنَةِ", "الزَّلۡزَلَةِ", "العَادِيَاتِ",
    "القَارِعَةِ", "التَّكَاثُرِ", "العَصۡرِ", "الهُمَزَةِ", "الفِيلِ",
    "قُرَيۡشٍ", "المَاعُونِ", "الكَوۡثَرِ", "الكَافِرُونَ", "النَّصۡرِ",
    "المَسَدِ", "الإِخۡلاصِ", "الفَلَقِ", "النَّاسِ"
]


def setup_database():
    """Ensure tables exist for qiraat texts"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for riwayat (if not exists)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riwayat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name_arabic TEXT NOT NULL,
            name_english TEXT NOT NULL,
            qari_id INTEGER,
            source TEXT,
            description TEXT,
            FOREIGN KEY (qari_id) REFERENCES qurra(id)
        )
    """)

    # Table for qiraat texts (if not exists)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_texts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            riwaya_id INTEGER NOT NULL,
            surah_id INTEGER NOT NULL,
            ayah_number INTEGER NOT NULL,
            text_uthmani TEXT NOT NULL,
            text_simple TEXT,
            juz INTEGER,
            page INTEGER,
            source TEXT,
            FOREIGN KEY (riwaya_id) REFERENCES riwayat(id),
            FOREIGN KEY (surah_id) REFERENCES surahs(id),
            UNIQUE(riwaya_id, surah_id, ayah_number)
        )
    """)

    conn.commit()
    conn.close()
    print("Database tables verified")


def parse_qiraa_text(file_path):
    """
    Parse QuranJSON text file format.

    Format:
    - Surah headers start with "سُورَةُ"
    - Verses contain Arabic text with verse number markers (Arabic numerals)
    - Multiple verses can be on same line
    """
    if not os.path.exists(file_path):
        print(f"  File not found: {file_path}")
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    verses = []
    current_surah = 0

    # Split into lines
    lines = content.split('\n')

    verse_text_buffer = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for surah header
        if line.startswith('سُورَةُ'):
            current_surah += 1
            verse_text_buffer = ""
            continue

        # Add line to buffer
        verse_text_buffer += " " + line if verse_text_buffer else line

    # Now parse verse_text_buffer to extract individual verses
    # Verse numbers are in Arabic numerals at the end: ١، ٢، ٣، etc.

    # Process content by surah
    current_surah = 0
    surah_content = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('سُورَةُ'):
            if current_surah > 0 and surah_content:
                # Process previous surah
                verses.extend(extract_verses(' '.join(surah_content), current_surah))
            current_surah += 1
            surah_content = []
        else:
            surah_content.append(line)

    # Process last surah
    if current_surah > 0 and surah_content:
        verses.extend(extract_verses(' '.join(surah_content), current_surah))

    return verses


def extract_verses(text, surah_no):
    """Extract individual verses from concatenated text"""
    verses = []

    # Arabic numeral pattern at end of verses: ١٢٣
    # Match text followed by Arabic numbers
    pattern = r'([^٠-٩]+)([\u0660-\u0669]+)'

    matches = re.findall(pattern, text)

    for verse_text, verse_num_ar in matches:
        # Convert Arabic numerals to integer
        ayah_no = arabic_to_int(verse_num_ar)

        if ayah_no > 0:
            verses.append({
                'surah': surah_no,
                'ayah': ayah_no,
                'text': verse_text.strip()
            })

    return verses


def arabic_to_int(arabic_str):
    """Convert Arabic numerals to integer"""
    arabic_numerals = '٠١٢٣٤٥٦٧٨٩'
    result = 0
    for char in arabic_str:
        if char in arabic_numerals:
            result = result * 10 + arabic_numerals.index(char)
    return result


def import_riwayat():
    """Import riwayat metadata"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for code, (file_path, name_ar, name_en) in QIRAAT_FILES.items():
        cursor.execute("""
            INSERT OR REPLACE INTO riwayat (code, name_arabic, name_english, source)
            VALUES (?, ?, ?, 'QuranJSON')
        """, (code, name_ar, name_en))

    conn.commit()
    conn.close()
    print(f"Imported {len(QIRAAT_FILES)} riwayat from QuranJSON")


def import_qiraat_texts():
    """Import Quran text for each qiraa"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_imported = 0

    for code, (file_name, name_ar, name_en) in QIRAAT_FILES.items():
        print(f"\nImporting {name_ar} ({code})...")

        # Get riwaya_id
        cursor.execute("SELECT id FROM riwayat WHERE code = ?", (code,))
        riwaya_row = cursor.fetchone()
        if not riwaya_row:
            print(f"  Riwaya not found: {code}")
            continue
        riwaya_id = riwaya_row[0]

        # Parse data
        file_path = os.path.join(DATA_DIR, file_name)
        verses = parse_qiraa_text(file_path)
        if not verses:
            print(f"  No verses parsed from {file_name}")
            continue

        # Import verses
        count = 0
        for verse in verses:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO qiraat_texts
                    (riwaya_id, surah_id, ayah_number, text_uthmani, source)
                    VALUES (?, ?, ?, ?, 'QuranJSON')
                """, (riwaya_id, verse['surah'], verse['ayah'], verse['text']))
                count += 1
            except Exception as e:
                print(f"  Error importing {verse['surah']}:{verse['ayah']}: {e}")

        print(f"  Imported {count} verses")
        total_imported += count

    conn.commit()
    conn.close()
    print(f"\nTotal verses imported from QuranJSON: {total_imported}")


def main():
    print("=" * 60)
    print("Importing القراءات from QuranJSON")
    print("=" * 60)

    if not os.path.exists(DATA_DIR):
        print(f"Error: Data directory not found: {DATA_DIR}")
        print("Please clone QuranJSON repository first:")
        print("  git clone https://github.com/Ishaksmail/QuranJSON.git data/raw/QuranJSON")
        return

    # Setup
    setup_database()

    # Import riwayat metadata
    import_riwayat()

    # Import texts
    import_qiraat_texts()

    # Print summary
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    cursor.execute("""
        SELECT r.name_arabic, COUNT(qt.id)
        FROM riwayat r
        LEFT JOIN qiraat_texts qt ON qt.riwaya_id = r.id
        WHERE r.source = 'QuranJSON'
        GROUP BY r.id
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} verses")

    conn.close()
    print("\n" + "=" * 60)
    print("Import complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
