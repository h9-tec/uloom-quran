"""
Qiraat Views - Frontend route handlers for Qiraat pages
القراءات العشر - صفحات العرض
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from ..api.database import get_db, dict_from_row

# Get paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Setup templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Create router
router = APIRouter(tags=["Qiraat Views"])


@router.get("/qiraat", response_class=HTMLResponse)
async def qiraat_main_page(request: Request):
    """
    Main Qiraat comparison page - صفحة مقارنة القراءات الرئيسية

    Displays the main interface for comparing different Quranic readings (Qiraat),
    showing all 8 riwayat with selection controls for surah and verse comparison.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surahs
        cursor.execute("SELECT id, name_arabic FROM surahs ORDER BY id")
        surahs = [dict_from_row(row) for row in cursor.fetchall()]

        # Get qurra (the ten readers)
        cursor.execute("""
            SELECT id, name_arabic, city, death_year_hijri
            FROM qurra ORDER BY rank_order
        """)
        qurra = [dict_from_row(row) for row in cursor.fetchall()]

    return templates.TemplateResponse("qiraat.html", {
        "request": request,
        "surahs": surahs,
        "qurra": qurra
    })


@router.get("/qiraat/learn", response_class=HTMLResponse)
async def qiraat_learn_page(request: Request):
    """
    Learning resources page - صفحة مصادر التعلم

    Provides educational content about Qiraat including:
    - History and importance of Qiraat
    - The ten canonical readers (القراء العشرة)
    - Their transmitters (الرواة)
    - Learning methodology
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get qurra with their ruwat
        cursor.execute("""
            SELECT q.id, q.name_arabic, q.name_english, q.death_year_hijri,
                   q.city, q.region, q.rank_order
            FROM qurra q
            ORDER BY q.rank_order
        """)
        qurra = []
        for row in cursor.fetchall():
            qari = dict_from_row(row)
            # Get ruwat for this qari
            cursor.execute("""
                SELECT id, name_arabic, name_english, death_year_hijri
                FROM ruwat WHERE qari_id = ?
            """, (qari['id'],))
            qari['ruwat'] = [dict_from_row(r) for r in cursor.fetchall()]
            qurra.append(qari)

        # Get riwayat info
        cursor.execute("""
            SELECT id, code, name_arabic, name_english, description
            FROM riwayat
            ORDER BY id
        """)
        riwayat = [dict_from_row(row) for row in cursor.fetchall()]

    return templates.TemplateResponse("qiraat_learn.html", {
        "request": request,
        "qurra": qurra,
        "riwayat": riwayat
    })


@router.get("/qiraat/glossary", response_class=HTMLResponse)
async def qiraat_glossary_page(request: Request):
    """
    Terminology glossary page - صفحة مصطلحات القراءات

    Provides definitions and explanations for key Qiraat terminology:
    - القراءة (Qira'a) - Reading
    - الرواية (Riwaya) - Transmission
    - الطريق (Tareeq) - Chain
    - الأصول (Usool) - Principles
    - الفرش (Farsh) - Individual word differences
    """
    # Glossary terms data
    glossary_terms = [
        {
            "term_arabic": "القراءة",
            "term_english": "Qira'a (Reading)",
            "definition": "طريقة أداء كلمات القرآن الكريم كما نقلها القارئ عن شيوخه بسند متصل إلى رسول الله صلى الله عليه وسلم",
            "category": "أساسيات"
        },
        {
            "term_arabic": "الرواية",
            "term_english": "Riwaya (Transmission)",
            "definition": "ما نسب إلى الراوي الذي روى القراءة عن الإمام القارئ",
            "category": "أساسيات"
        },
        {
            "term_arabic": "الطريق",
            "term_english": "Tareeq (Chain)",
            "definition": "ما نسب إلى من روى عن الراوي ولو بواسطة",
            "category": "أساسيات"
        },
        {
            "term_arabic": "الأصول",
            "term_english": "Usool (Principles)",
            "definition": "القواعد العامة المطردة التي تتكرر في مواضع كثيرة من القرآن الكريم",
            "category": "قواعد"
        },
        {
            "term_arabic": "الفرش",
            "term_english": "Farsh (Individual Differences)",
            "definition": "الكلمات القرآنية التي اختلف القراء في قراءتها ولا تندرج تحت قاعدة عامة",
            "category": "قواعد"
        },
        {
            "term_arabic": "المد",
            "term_english": "Madd (Elongation)",
            "definition": "إطالة الصوت بحرف من حروف المد الثلاثة: الألف والواو والياء",
            "category": "أحكام التجويد"
        },
        {
            "term_arabic": "الإمالة",
            "term_english": "Imala (Inclination)",
            "definition": "أن تنحو بالفتحة نحو الكسرة وبالألف نحو الياء",
            "category": "أحكام التجويد"
        },
        {
            "term_arabic": "الإدغام",
            "term_english": "Idgham (Merging)",
            "definition": "إدخال حرف ساكن في حرف متحرك بحيث يصيران حرفا واحدا مشددا",
            "category": "أحكام التجويد"
        },
        {
            "term_arabic": "الإظهار",
            "term_english": "Izhar (Manifestation)",
            "definition": "إخراج كل حرف من مخرجه من غير غنة في الحرف المظهر",
            "category": "أحكام التجويد"
        },
        {
            "term_arabic": "السكت",
            "term_english": "Sakt (Pause)",
            "definition": "قطع الصوت زمنا دون زمن الوقف من غير تنفس",
            "category": "أحكام التجويد"
        },
        {
            "term_arabic": "القارئ",
            "term_english": "Qari (Reader)",
            "definition": "الإمام الذي اشتهر بقراءته ونسبت إليه وتلقاها الناس عنه بالقبول",
            "category": "أعلام"
        },
        {
            "term_arabic": "الراوي",
            "term_english": "Rawi (Transmitter)",
            "definition": "من روى القراءة عن القارئ وحفظها ونقلها إلى من بعده",
            "category": "أعلام"
        }
    ]

    # Group by category
    categories = {}
    for term in glossary_terms:
        cat = term['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(term)

    return templates.TemplateResponse("qiraat_glossary.html", {
        "request": request,
        "glossary_terms": glossary_terms,
        "categories": categories
    })


@router.get("/qiraat/stats", response_class=HTMLResponse)
async def qiraat_stats_page(request: Request):
    """
    Statistics page - صفحة إحصائيات القراءات

    Displays comprehensive statistics about Qiraat data:
    - Total variants and readings
    - Distribution by surah
    - Distribution by type
    - Coverage by reader
    """
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {}

        # Total variants (from qiraat_variants)
        cursor.execute("SELECT COUNT(*) FROM qiraat_variants")
        stats['total_variants'] = cursor.fetchone()[0]

        # Total readings (from qiraat_readings)
        cursor.execute("SELECT COUNT(*) FROM qiraat_readings")
        stats['total_readings'] = cursor.fetchone()[0]

        # Total differences (from qiraat_differences)
        try:
            cursor.execute("SELECT COUNT(*) FROM qiraat_differences")
            stats['total_differences'] = cursor.fetchone()[0]
        except:
            stats['total_differences'] = 0

        # Variants by type
        cursor.execute("""
            SELECT variant_type, COUNT(*) as count
            FROM qiraat_variants
            GROUP BY variant_type
            ORDER BY count DESC
        """)
        stats['by_type'] = [
            {"type": row[0] or 'غير محدد', "count": row[1]}
            for row in cursor.fetchall()
        ]

        # Readings by qari
        cursor.execute("""
            SELECT q.name_arabic, COUNT(*) as count
            FROM qiraat_readings qr
            JOIN qurra q ON qr.qari_id = q.id
            GROUP BY qr.qari_id
            ORDER BY q.rank_order
        """)
        stats['by_qari'] = [
            {"name": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]

        # Surahs with most differences
        cursor.execute("""
            SELECT s.id, s.name_arabic, COUNT(qv.id) as count
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
            JOIN surahs s ON v.surah_id = s.id
            GROUP BY s.id
            ORDER BY count DESC
            LIMIT 10
        """)
        stats['top_surahs'] = [
            {"id": row[0], "name": row[1], "count": row[2]}
            for row in cursor.fetchall()
        ]

        # Get all surahs with variant counts
        cursor.execute("""
            SELECT s.id, s.name_arabic, s.ayah_count,
                   COALESCE(variant_counts.count, 0) as variant_count
            FROM surahs s
            LEFT JOIN (
                SELECT v.surah_id, COUNT(qv.id) as count
                FROM qiraat_variants qv
                JOIN verses v ON qv.verse_id = v.id
                GROUP BY v.surah_id
            ) variant_counts ON s.id = variant_counts.surah_id
            ORDER BY s.id
        """)
        stats['all_surahs'] = [
            {"id": row[0], "name": row[1], "ayah_count": row[2], "variant_count": row[3]}
            for row in cursor.fetchall()
        ]

        # Riwayat coverage
        try:
            cursor.execute("""
                SELECT r.id, r.code, r.name_arabic, r.name_english,
                       (SELECT COUNT(*) FROM qiraat_texts WHERE riwaya_id = r.id) as text_count
                FROM riwayat r
                ORDER BY r.id
            """)
            stats['riwayat_coverage'] = [dict_from_row(row) for row in cursor.fetchall()]
        except:
            stats['riwayat_coverage'] = []

    return templates.TemplateResponse("qiraat_stats.html", {
        "request": request,
        "stats": stats
    })


@router.get("/qiraat/verse/{verse_key:path}", response_class=HTMLResponse)
async def qiraat_verse_page(request: Request, verse_key: str):
    """
    Detailed qiraat comparison page for a single verse - صفحة مقارنة القراءات لآية واحدة

    Displays detailed side-by-side comparison of readings for a specific verse.
    """
    # Parse verse key (format: surah:ayah)
    try:
        parts = verse_key.split(":")
        surah_id = int(parts[0])
        ayah_number = int(parts[1])
    except (ValueError, IndexError):
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    with get_db() as conn:
        cursor = conn.cursor()

        # Get verse info
        cursor.execute("""
            SELECT v.id, v.verse_key, v.text_uthmani, s.name_arabic as surah_name,
                   s.name_english as surah_name_english, s.ayah_count
            FROM verses v
            JOIN surahs s ON v.surah_id = s.id
            WHERE v.surah_id = ? AND v.ayah_number = ?
        """, (surah_id, ayah_number))
        verse = cursor.fetchone()

        if not verse:
            return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

        verse_data = dict_from_row(verse)
        total_ayahs = verse_data['ayah_count']

    return templates.TemplateResponse("qiraat_verse.html", {
        "request": request,
        "verse": verse_data,
        "surah_id": surah_id,
        "ayah_number": ayah_number,
        "total_ayahs": total_ayahs
    })


@router.get("/qiraat/surah/{surah_id}", response_class=HTMLResponse)
async def qiraat_surah_page(request: Request, surah_id: int):
    """
    Surah-specific Qiraat view - عرض قراءات سورة محددة

    Displays all Qiraat differences for a specific surah with:
    - Surah information
    - List of all verses with differences
    - Detailed reading variants for each verse
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surah info
        cursor.execute("""
            SELECT id, name_arabic, name_english, ayah_count, revelation_type
            FROM surahs WHERE id = ?
        """, (surah_id,))
        surah = cursor.fetchone()

        if not surah:
            return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

        surah_data = dict_from_row(surah)

    return templates.TemplateResponse("qiraat_surah.html", {
        "request": request,
        "surah": surah_data
    })


@router.get("/qiraat/audio/compare/{verse_key:path}", response_class=HTMLResponse)
async def qiraat_audio_compare_page(request: Request, verse_key: str):
    """
    Audio comparison page for Qiraat - صفحة مقارنة صوتيات القراءات

    Displays an interface for comparing audio recitations of the same verse
    in different qiraat, with features including:
    - Side-by-side audio playback
    - Sequential playback through all readings
    - Synchronized text highlighting showing differences
    - Audio controls for each reading
    """
    # Parse verse key (format: surah:ayah)
    try:
        parts = verse_key.split(":")
        surah_id = int(parts[0])
        ayah_number = int(parts[1])
    except (ValueError, IndexError):
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    with get_db() as conn:
        cursor = conn.cursor()

        # Get verse info
        cursor.execute("""
            SELECT v.id, v.verse_key, v.text_uthmani, s.name_arabic as surah_name,
                   s.name_english as surah_name_english, s.ayah_count
            FROM verses v
            JOIN surahs s ON v.surah_id = s.id
            WHERE v.surah_id = ? AND v.ayah_number = ?
        """, (surah_id, ayah_number))
        verse = cursor.fetchone()

        if not verse:
            return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

        verse_data = dict_from_row(verse)
        total_ayahs = verse_data['ayah_count']

        # Get all surahs for the selector
        cursor.execute("SELECT id, name_arabic FROM surahs ORDER BY id")
        surahs = [dict_from_row(row) for row in cursor.fetchall()]

    return templates.TemplateResponse("qiraat_audio_compare.html", {
        "request": request,
        "verse": verse_data,
        "surah_id": surah_id,
        "ayah_number": ayah_number,
        "total_ayahs": total_ayahs,
        "surahs": surahs
    })
