"""
علوم القرآن API - Main Application
FastAPI backend for Quranic Sciences Platform
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os

from .routes import quran_router, tafsir_router, qiraat_router, qiraat_search_router, qiraat_export_router, qiraat_audio_router, asbab_router, earab_router, ai_router, mutashabihat_router
from ..views import qiraat_views_router
from .database import get_db

# Get paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Create app
app = FastAPI(
    title="علوم القرآن API",
    description="""
    Comprehensive API for Quranic Sciences:
    - **القرآن الكريم** - Quran text and search
    - **التفاسير المقارنة** - Comparative Tafsir from 7 Sunni scholars
    - **القراءات العشر** - Ten Qiraat readings and differences
    - **أسباب النزول** - Reasons for revelation
    - **إعراب القرآن** - Arabic grammatical analysis
    - **المتشابهات** - Similar verses with Quranpedia integration
    - **الذكاء الاصطناعي** - AI-powered semantic search and Q&A with GPT-4o
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Mount data directory for audio JSON files
DATA_DIR = os.path.join(BASE_DIR, "data")
if os.path.exists(DATA_DIR):
    app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")

# Include routers
app.include_router(quran_router)
app.include_router(tafsir_router)
app.include_router(qiraat_router)
app.include_router(qiraat_search_router)
app.include_router(qiraat_export_router)
app.include_router(qiraat_audio_router)
app.include_router(asbab_router)
app.include_router(earab_router)
app.include_router(ai_router)
app.include_router(mutashabihat_router)

# Include Qiraat views router (frontend pages)
app.include_router(qiraat_views_router)


# ============================================================================
# Frontend Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get stats
        cursor.execute("SELECT COUNT(*) FROM verses")
        verse_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tafsir_entries")
        tafsir_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM qiraat_variants")
        qiraat_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM asbab_nuzul")
        asbab_count = cursor.fetchone()[0]

        # Get earab count (may not exist yet)
        try:
            cursor.execute("SELECT COUNT(*) FROM earab_verses")
            earab_count = cursor.fetchone()[0]
        except:
            earab_count = 0

    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": {
            "verses": verse_count,
            "tafsirs": tafsir_count,
            "qiraat": qiraat_count,
            "asbab": asbab_count,
            "earab": earab_count
        }
    })


@app.get("/quran", response_class=HTMLResponse)
async def quran_page(request: Request):
    """Quran browser page"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name_arabic, name_english, ayah_count, revelation_type
            FROM surahs ORDER BY id
        """)
        surahs = [dict(zip(['id', 'name_arabic', 'name_english', 'ayah_count', 'revelation_type'], row))
                  for row in cursor.fetchall()]

    return templates.TemplateResponse("quran.html", {
        "request": request,
        "surahs": surahs
    })


@app.get("/surah/{surah_id}", response_class=HTMLResponse)
async def surah_page(request: Request, surah_id: int):
    """Surah detail page"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surah
        cursor.execute("""
            SELECT id, name_arabic, name_english, ayah_count, revelation_type
            FROM surahs WHERE id = ?
        """, (surah_id,))
        surah = cursor.fetchone()

        if not surah:
            return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

        surah_data = dict(zip(['id', 'name_arabic', 'name_english', 'ayah_count', 'revelation_type'], surah))

        # Get verses
        cursor.execute("""
            SELECT ayah_number, verse_key, text_uthmani
            FROM verses WHERE surah_id = ? ORDER BY ayah_number
        """, (surah_id,))
        verses = [dict(zip(['ayah_number', 'verse_key', 'text_uthmani'], row))
                  for row in cursor.fetchall()]

        # Get tafsir books
        cursor.execute("""
            SELECT id, name_arabic, short_name, author_arabic
            FROM tafsir_books WHERE id IN (
                SELECT DISTINCT tafsir_id FROM tafsir_entries
            )
        """)
        tafsir_books = [dict(zip(['id', 'name_arabic', 'short_name', 'author_arabic'], row))
                       for row in cursor.fetchall()]

    return templates.TemplateResponse("surah.html", {
        "request": request,
        "surah": surah_data,
        "verses": verses,
        "tafsir_books": tafsir_books
    })


@app.get("/tafsir", response_class=HTMLResponse)
async def tafsir_page(request: Request):
    """Tafsir comparison page"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surahs
        cursor.execute("SELECT id, name_arabic FROM surahs ORDER BY id")
        surahs = [dict(zip(['id', 'name_arabic'], row)) for row in cursor.fetchall()]

        # Get tafsir books
        cursor.execute("""
            SELECT id, name_arabic, short_name, author_arabic, methodology
            FROM tafsir_books WHERE id IN (
                SELECT DISTINCT tafsir_id FROM tafsir_entries
            )
        """)
        tafsir_books = [dict(zip(['id', 'name_arabic', 'short_name', 'author_arabic', 'methodology'], row))
                       for row in cursor.fetchall()]

    return templates.TemplateResponse("tafsir.html", {
        "request": request,
        "surahs": surahs,
        "tafsir_books": tafsir_books
    })


@app.get("/qiraat", response_class=HTMLResponse)
async def qiraat_page(request: Request):
    """Qiraat differences page"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surahs
        cursor.execute("SELECT id, name_arabic FROM surahs ORDER BY id")
        surahs = [dict(zip(['id', 'name_arabic'], row)) for row in cursor.fetchall()]

        # Get qurra
        cursor.execute("""
            SELECT id, name_arabic, city, death_year_hijri
            FROM qurra ORDER BY rank_order
        """)
        qurra = [dict(zip(['id', 'name_arabic', 'city', 'death_year_hijri'], row))
                 for row in cursor.fetchall()]

    return templates.TemplateResponse("qiraat.html", {
        "request": request,
        "surahs": surahs,
        "qurra": qurra
    })


@app.get("/qiraat/stats", response_class=HTMLResponse)
async def qiraat_stats_page(request: Request):
    """Qiraat statistics dashboard page"""
    return templates.TemplateResponse("qiraat_stats.html", {
        "request": request
    })


@app.get("/qiraat/verse/{verse_key:path}", response_class=HTMLResponse)
async def qiraat_verse_page(request: Request, verse_key: str):
    """Detailed qiraat comparison page for a single verse"""
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

        verse_data = dict(zip(
            ['id', 'verse_key', 'text_uthmani', 'surah_name', 'surah_name_english', 'ayah_count'],
            verse
        ))

        total_ayahs = verse_data['ayah_count']

    return templates.TemplateResponse("qiraat_verse.html", {
        "request": request,
        "verse": verse_data,
        "surah_id": surah_id,
        "ayah_number": ayah_number,
        "total_ayahs": total_ayahs
    })


@app.get("/asbab", response_class=HTMLResponse)
async def asbab_page(request: Request):
    """Asbab al-Nuzul page"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surahs with asbab count
        cursor.execute("""
            SELECT s.id, s.name_arabic, COUNT(a.id) as asbab_count
            FROM surahs s
            LEFT JOIN verses v ON v.surah_id = s.id
            LEFT JOIN asbab_nuzul a ON a.verse_id = v.id
            GROUP BY s.id
            ORDER BY s.id
        """)
        surahs = [dict(zip(['id', 'name_arabic', 'asbab_count'], row))
                  for row in cursor.fetchall()]

    return templates.TemplateResponse("asbab.html", {
        "request": request,
        "surahs": surahs
    })


@app.get("/earab", response_class=HTMLResponse)
async def earab_page(request: Request):
    """إعراب القرآن page"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surahs with earab count
        cursor.execute("""
            SELECT s.id, s.name_arabic, s.ayah_count, COUNT(e.id) as earab_count
            FROM surahs s
            LEFT JOIN verses v ON v.surah_id = s.id
            LEFT JOIN earab_verses e ON e.verse_id = v.id
            GROUP BY s.id
            ORDER BY s.id
        """)
        surahs = [dict(zip(['id', 'name_arabic', 'ayah_count', 'earab_count'], row))
                  for row in cursor.fetchall()]

    return templates.TemplateResponse("earab.html", {
        "request": request,
        "surahs": surahs
    })


@app.get("/ai", response_class=HTMLResponse)
async def ai_page(request: Request):
    """AI Assistant page"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surahs for verse selector
        cursor.execute("SELECT id, name_arabic FROM surahs ORDER BY id")
        surahs = [dict(zip(['id', 'name_arabic'], row)) for row in cursor.fetchall()]

    return templates.TemplateResponse("ai.html", {
        "request": request,
        "surahs": surahs
    })


@app.get("/mutashabihat", response_class=HTMLResponse)
async def mutashabihat_page(request: Request):
    """المتشابهات - Similar Verses page"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surahs for verse selector
        cursor.execute("SELECT id, name_arabic, ayah_count FROM surahs ORDER BY id")
        surahs = [dict(zip(['id', 'name_arabic', 'ayah_count'], row)) for row in cursor.fetchall()]

    return templates.TemplateResponse("mutashabihat.html", {
        "request": request,
        "surahs": surahs
    })


# ============================================================================
# API Info Endpoint
# ============================================================================

@app.get("/api")
def api_info():
    """API information and statistics"""
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {}
        tables = [
            ('surahs', 'سور'),
            ('verses', 'آيات'),
            ('tafsir_entries', 'تفسير'),
            ('qiraat_variants', 'قراءات'),
            ('qiraat_readings', 'روايات'),
            ('asbab_nuzul', 'أسباب النزول'),
        ]

        for table, arabic_name in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[arabic_name] = cursor.fetchone()[0]

    return {
        "name": "علوم القرآن API",
        "version": "1.0.0",
        "statistics": stats,
        "endpoints": {
            "quran": "/api/quran",
            "tafsir": "/api/tafsir",
            "qiraat": "/api/qiraat",
            "qiraat_export": "/api/qiraat/export",
            "asbab": "/api/asbab",
            "mutashabihat": "/api/mutashabihat",
            "ai": "/api/ai",
            "docs": "/api/docs"
        },
        "export_endpoints": {
            "json": "/api/qiraat/export/json?surah=1",
            "csv_differences": "/api/qiraat/export/csv/differences",
            "pdf_comparison": "/api/qiraat/export/comparison?verse=1:4",
            "surah_all_readings": "/api/qiraat/export/surah/{surah_id}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
