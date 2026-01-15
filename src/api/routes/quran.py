"""
Quran API routes - Surahs and Verses
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from ..database import get_db, dict_from_row

router = APIRouter(prefix="/api/quran", tags=["Quran"])


@router.get("/surahs")
def get_surahs():
    """Get all surahs"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name_arabic, name_english, name_transliteration,
                   revelation_type, revelation_order, ayah_count
            FROM surahs
            ORDER BY id
        """)
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.get("/surahs/{surah_id}")
def get_surah(surah_id: int):
    """Get surah details with verses"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get surah info
        cursor.execute("""
            SELECT id, name_arabic, name_english, name_transliteration,
                   revelation_type, revelation_order, ayah_count
            FROM surahs WHERE id = ?
        """, (surah_id,))
        surah = cursor.fetchone()

        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        # Get verses
        cursor.execute("""
            SELECT id, ayah_number, verse_key, text_uthmani,
                   page_number, juz_number
            FROM verses
            WHERE surah_id = ?
            ORDER BY ayah_number
        """, (surah_id,))
        verses = [dict_from_row(row) for row in cursor.fetchall()]

        result = dict_from_row(surah)
        result['verses'] = verses
        return result


@router.get("/verses/{verse_key}")
def get_verse(verse_key: str):
    """Get single verse by key (e.g., 2:255)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.id, v.surah_id, v.ayah_number, v.verse_key, v.text_uthmani,
                   v.page_number, v.juz_number, s.name_arabic as surah_name
            FROM verses v
            JOIN surahs s ON v.surah_id = s.id
            WHERE v.verse_key = ?
        """, (verse_key,))
        verse = cursor.fetchone()

        if not verse:
            raise HTTPException(status_code=404, detail="Verse not found")

        return dict_from_row(verse)


@router.get("/search")
def search_quran(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, le=100)
):
    """Search verses by text"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.id, v.verse_key, v.text_uthmani, s.name_arabic as surah_name
            FROM verses v
            JOIN surahs s ON v.surah_id = s.id
            WHERE v.text_uthmani LIKE ?
            LIMIT ?
        """, (f"%{q}%", limit))
        return [dict_from_row(row) for row in cursor.fetchall()]
