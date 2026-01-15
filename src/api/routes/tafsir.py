"""
Tafsir API routes - Comparative Tafsir Engine
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from ..database import get_db, dict_from_row

router = APIRouter(prefix="/api/tafsir", tags=["Tafsir"])


@router.get("/books")
def get_tafsir_books():
    """Get all available tafsir books"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tb.id, tb.name_arabic, tb.name_english, tb.short_name,
                   tb.author_arabic, tb.author_english, tb.methodology,
                   tb.death_year_hijri,
                   (SELECT COUNT(*) FROM tafsir_entries WHERE tafsir_id = tb.id) as entry_count
            FROM tafsir_books tb
            ORDER BY tb.id
        """)
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.get("/verse/{verse_key}")
def get_verse_tafsirs(
    verse_key: str,
    tafsir_ids: Optional[str] = Query(None, description="Comma-separated tafsir IDs")
):
    """Get all tafsirs for a verse"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get verse info
        cursor.execute("""
            SELECT id, verse_key, text_uthmani, surah_id, ayah_number
            FROM verses WHERE verse_key = ?
        """, (verse_key,))
        verse = cursor.fetchone()

        if not verse:
            raise HTTPException(status_code=404, detail="Verse not found")

        verse_data = dict_from_row(verse)

        # Build tafsir query
        query = """
            SELECT te.id, te.tafsir_id, tb.name_arabic as tafsir_name,
                   tb.short_name, tb.author_arabic, tb.methodology,
                   te.text_arabic
            FROM tafsir_entries te
            JOIN tafsir_books tb ON te.tafsir_id = tb.id
            WHERE te.verse_id = ?
        """
        params = [verse_data['id']]

        if tafsir_ids:
            ids = [int(x) for x in tafsir_ids.split(',')]
            placeholders = ','.join('?' * len(ids))
            query += f" AND te.tafsir_id IN ({placeholders})"
            params.extend(ids)

        query += " ORDER BY tb.id"

        cursor.execute(query, params)
        tafsirs = [dict_from_row(row) for row in cursor.fetchall()]

        return {
            "verse": verse_data,
            "tafsirs": tafsirs
        }


@router.get("/compare/{verse_key}")
def compare_tafsirs(
    verse_key: str,
    tafsir_ids: str = Query(..., description="Comma-separated tafsir IDs to compare")
):
    """Compare multiple tafsirs for a verse side by side"""
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

        # Get requested tafsirs
        ids = [int(x) for x in tafsir_ids.split(',')]
        placeholders = ','.join('?' * len(ids))

        cursor.execute(f"""
            SELECT te.tafsir_id, tb.name_arabic as tafsir_name,
                   tb.short_name, tb.author_arabic, tb.methodology,
                   te.text_arabic
            FROM tafsir_entries te
            JOIN tafsir_books tb ON te.tafsir_id = tb.id
            WHERE te.verse_id = ? AND te.tafsir_id IN ({placeholders})
            ORDER BY tb.id
        """, [verse_data['id']] + ids)

        comparisons = [dict_from_row(row) for row in cursor.fetchall()]

        return {
            "verse": verse_data,
            "comparisons": comparisons
        }


@router.get("/surah/{surah_id}/tafsir/{tafsir_id}")
def get_surah_tafsir(surah_id: int, tafsir_id: int):
    """Get complete tafsir for a surah"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify surah exists
        cursor.execute("SELECT name_arabic FROM surahs WHERE id = ?", (surah_id,))
        surah = cursor.fetchone()
        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        # Verify tafsir exists
        cursor.execute("SELECT name_arabic, author_arabic FROM tafsir_books WHERE id = ?", (tafsir_id,))
        tafsir = cursor.fetchone()
        if not tafsir:
            raise HTTPException(status_code=404, detail="Tafsir not found")

        # Get all entries
        cursor.execute("""
            SELECT v.ayah_number, v.verse_key, v.text_uthmani, te.text_arabic
            FROM tafsir_entries te
            JOIN verses v ON te.verse_id = v.id
            WHERE v.surah_id = ? AND te.tafsir_id = ?
            ORDER BY v.ayah_number
        """, (surah_id, tafsir_id))

        entries = [dict_from_row(row) for row in cursor.fetchall()]

        return {
            "surah": {"id": surah_id, "name": surah['name_arabic']},
            "tafsir": {"id": tafsir_id, "name": tafsir['name_arabic'], "author": tafsir['author_arabic']},
            "entries": entries
        }
