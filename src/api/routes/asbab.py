"""
Asbab al-Nuzul API routes - أسباب النزول
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..database import get_db, dict_from_row

router = APIRouter(prefix="/api/asbab", tags=["Asbab al-Nuzul"])


@router.get("/sources")
def get_sources():
    """Get all asbab al-nuzul sources/books"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name_arabic, name_english, author_arabic,
                   death_year_hijri, description
            FROM asbab_sources
            ORDER BY id
        """)
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.get("/verse/{verse_key}")
def get_verse_asbab(verse_key: str):
    """Get asbab al-nuzul for a specific verse"""
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

        # Get asbab - using correct column names
        cursor.execute("""
            SELECT a.id, a.sabab_text as text_arabic, a.isnad,
                   a.authenticity_grade as grading, a.grading_scholar,
                   a.revelation_period as context_period,
                   s.name_arabic as source_name, s.author_arabic
            FROM asbab_nuzul a
            LEFT JOIN asbab_sources s ON a.source_id = s.id
            WHERE a.verse_id = ?
            ORDER BY a.id
        """, (verse_data['id'],))

        asbab = [dict_from_row(row) for row in cursor.fetchall()]

        return {
            "verse": verse_data,
            "asbab": asbab,
            "count": len(asbab)
        }


@router.get("/surah/{surah_id}")
def get_surah_asbab(surah_id: int):
    """Get all asbab al-nuzul for a surah"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify surah
        cursor.execute("SELECT id, name_arabic FROM surahs WHERE id = ?", (surah_id,))
        surah = cursor.fetchone()
        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        # Get all asbab for this surah - using correct column names
        cursor.execute("""
            SELECT v.verse_key, v.ayah_number, v.text_uthmani,
                   a.id, a.sabab_text as text_arabic,
                   a.authenticity_grade as grading,
                   a.revelation_period as context_period,
                   s.name_arabic as source_name
            FROM asbab_nuzul a
            JOIN verses v ON a.verse_id = v.id
            LEFT JOIN asbab_sources s ON a.source_id = s.id
            WHERE v.surah_id = ?
            ORDER BY v.ayah_number
        """, (surah_id,))

        asbab_by_verse = {}
        for row in cursor.fetchall():
            data = dict_from_row(row)
            verse_key = data['verse_key']

            if verse_key not in asbab_by_verse:
                asbab_by_verse[verse_key] = {
                    "verse_key": verse_key,
                    "ayah_number": data['ayah_number'],
                    "text_uthmani": data['text_uthmani'],
                    "asbab": []
                }

            asbab_by_verse[verse_key]['asbab'].append({
                "id": data['id'],
                "text": data['text_arabic'],
                "grading": data['grading'],
                "period": data['context_period'],
                "source": data['source_name']
            })

        return {
            "surah": dict_from_row(surah),
            "total_asbab": sum(len(v['asbab']) for v in asbab_by_verse.values()),
            "verses_with_asbab": list(asbab_by_verse.values())
        }


@router.get("/search")
def search_asbab(
    q: str = Query(..., min_length=2, description="Search query"),
    source_id: Optional[int] = None,
    limit: int = Query(50, le=100)
):
    """Search asbab al-nuzul by text"""
    with get_db() as conn:
        cursor = conn.cursor()

        query = """
            SELECT v.verse_key, v.text_uthmani, s.name_arabic as surah_name,
                   a.sabab_text as text_arabic, a.authenticity_grade as grading,
                   src.name_arabic as source_name
            FROM asbab_nuzul a
            JOIN verses v ON a.verse_id = v.id
            JOIN surahs s ON v.surah_id = s.id
            LEFT JOIN asbab_sources src ON a.source_id = src.id
            WHERE a.sabab_text LIKE ?
        """
        params = [f"%{q}%"]

        if source_id:
            query += " AND a.source_id = ?"
            params.append(source_id)

        query += " LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.get("/stats")
def get_asbab_stats():
    """Get statistics about asbab al-nuzul data"""
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {}

        # Total entries
        cursor.execute("SELECT COUNT(*) FROM asbab_nuzul")
        stats['total_entries'] = cursor.fetchone()[0]

        # By source
        cursor.execute("""
            SELECT s.name_arabic, COUNT(*) as count
            FROM asbab_nuzul a
            LEFT JOIN asbab_sources s ON a.source_id = s.id
            GROUP BY a.source_id
            ORDER BY count DESC
        """)
        stats['by_source'] = {row[0] or 'Unknown': row[1] for row in cursor.fetchall()}

        # By grading
        cursor.execute("""
            SELECT authenticity_grade, COUNT(*) as count
            FROM asbab_nuzul
            WHERE authenticity_grade IS NOT NULL
            GROUP BY authenticity_grade
        """)
        stats['by_grading'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Surahs with most asbab
        cursor.execute("""
            SELECT s.name_arabic, s.id, COUNT(*) as count
            FROM asbab_nuzul a
            JOIN verses v ON a.verse_id = v.id
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
