"""
إعراب القرآن API routes - Arabic Grammatical Analysis
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..database import get_db, dict_from_row

router = APIRouter(prefix="/api/earab", tags=["Earab - إعراب القرآن"])


@router.get("/verse/{verse_key}")
def get_verse_earab(verse_key: str):
    """Get إعراب for a specific verse"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get verse
        cursor.execute("""
            SELECT v.id, v.verse_key, v.text_uthmani, s.name_arabic as surah_name
            FROM verses v
            JOIN surahs s ON v.surah_id = s.id
            WHERE v.verse_key = ?
        """, (verse_key,))
        verse = cursor.fetchone()

        if not verse:
            raise HTTPException(status_code=404, detail="Verse not found")

        verse_data = dict_from_row(verse)

        # Get إعراب
        cursor.execute("""
            SELECT id, earab_text, source, book_name
            FROM earab_verses
            WHERE verse_id = ?
        """, (verse_data['id'],))

        earab_row = cursor.fetchone()
        earab = dict_from_row(earab_row) if earab_row else None

        return {
            "verse": verse_data,
            "earab": earab
        }


@router.get("/surah/{surah_id}")
def get_surah_earab(surah_id: int):
    """Get إعراب for all verses in a surah"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify surah
        cursor.execute("SELECT id, name_arabic, name_english FROM surahs WHERE id = ?", (surah_id,))
        surah = cursor.fetchone()
        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        # Get all إعراب for this surah
        cursor.execute("""
            SELECT v.verse_key, v.ayah_number, v.text_uthmani,
                   e.earab_text, e.source, e.book_name
            FROM verses v
            LEFT JOIN earab_verses e ON v.id = e.verse_id
            WHERE v.surah_id = ?
            ORDER BY v.ayah_number
        """, (surah_id,))

        verses = []
        for row in cursor.fetchall():
            data = dict_from_row(row)
            verses.append({
                "verse_key": data['verse_key'],
                "ayah_number": data['ayah_number'],
                "text_uthmani": data['text_uthmani'],
                "earab": {
                    "text": data['earab_text'],
                    "source": data['source'],
                    "book_name": data['book_name']
                } if data['earab_text'] else None
            })

        return {
            "surah": dict_from_row(surah),
            "total_verses": len(verses),
            "verses_with_earab": sum(1 for v in verses if v['earab']),
            "verses": verses
        }


@router.get("/search")
def search_earab(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, le=100)
):
    """Search إعراب by text"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT v.verse_key, v.text_uthmani, s.name_arabic as surah_name,
                   e.earab_text, e.book_name
            FROM earab_verses e
            JOIN verses v ON e.verse_id = v.id
            JOIN surahs s ON v.surah_id = s.id
            WHERE e.earab_text LIKE ?
            LIMIT ?
        """, (f"%{q}%", limit))

        return [dict_from_row(row) for row in cursor.fetchall()]


@router.get("/stats")
def get_earab_stats():
    """Get statistics about إعراب data"""
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {}

        # Total إعراب entries
        cursor.execute("SELECT COUNT(*) FROM earab_verses")
        stats['total_entries'] = cursor.fetchone()[0]

        # Total verses in Quran
        cursor.execute("SELECT COUNT(*) FROM verses")
        stats['total_verses'] = cursor.fetchone()[0]

        # Coverage percentage
        stats['coverage_percent'] = round(
            (stats['total_entries'] / stats['total_verses']) * 100, 2
        ) if stats['total_verses'] > 0 else 0

        # By source
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM earab_verses
            GROUP BY source
        """)
        stats['by_source'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Surahs with most إعراب
        cursor.execute("""
            SELECT s.name_arabic, s.id, COUNT(e.id) as count
            FROM earab_verses e
            JOIN verses v ON e.verse_id = v.id
            JOIN surahs s ON v.surah_id = s.id
            GROUP BY s.id
            ORDER BY count DESC
            LIMIT 10
        """)
        stats['top_surahs'] = [
            {"name": row[0], "id": row[1], "count": row[2]}
            for row in cursor.fetchall()
        ]

        return stats
