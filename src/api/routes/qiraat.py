"""
Qiraat API routes - القراءات العشر
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..database import get_db, dict_from_row

router = APIRouter(prefix="/api/qiraat", tags=["Qiraat"])


# ============================================================================
# Riwayat Endpoints (New - using riwayat, qiraat_texts, qiraat_differences tables)
# ============================================================================

@router.get("/riwayat")
def get_riwayat():
    """
    Get all 8 riwayat (الروايات الثمان)

    Returns the list of the 8 canonical Quranic transmission chains (riwayat),
    including both Arabic and English names along with their unique codes.
    Filters out versioned duplicates (codes containing '_v2', '_smart', '-smart').
    """
    # The canonical 8 riwayat codes
    canonical_codes = ['hafs', 'warsh', 'qaloon', 'shouba', 'doori', 'soosi', 'bazzi', 'qumbul']

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, name_arabic, name_english, qari_id, description
            FROM riwayat
            WHERE code IN (?, ?, ?, ?, ?, ?, ?, ?)
            ORDER BY id
        """, canonical_codes)
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.get("/verse/{verse_key}")
def get_verse_readings(verse_key: str):
    """
    Get all readings for a specific verse (e.g., "1:4")

    Returns the verse text in all available riwayat along with any
    documented differences for that verse.
    """
    # Parse verse key
    try:
        parts = verse_key.split(":")
        surah_id = int(parts[0])
        ayah_number = int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=400,
            detail="Invalid verse key format. Use format 'surah:ayah' (e.g., '1:4')"
        )

    with get_db() as conn:
        cursor = conn.cursor()

        # Get verse info from verses table
        cursor.execute("""
            SELECT v.id, v.verse_key, v.text_uthmani, s.name_arabic as surah_name,
                   s.name_english as surah_name_english
            FROM verses v
            JOIN surahs s ON v.surah_id = s.id
            WHERE v.surah_id = ? AND v.ayah_number = ?
        """, (surah_id, ayah_number))
        verse = cursor.fetchone()

        if not verse:
            raise HTTPException(status_code=404, detail="Verse not found")

        verse_data = dict_from_row(verse)

        # Get readings from all riwayat for this verse
        cursor.execute("""
            SELECT qt.id, qt.riwaya_id, r.code, r.name_arabic, r.name_english,
                   qt.text_uthmani, qt.text_simple, qt.juz, qt.page
            FROM qiraat_texts qt
            JOIN riwayat r ON qt.riwaya_id = r.id
            WHERE qt.surah_id = ? AND qt.ayah_number = ?
            ORDER BY r.id
        """, (surah_id, ayah_number))
        readings = [dict_from_row(row) for row in cursor.fetchall()]

        # Get differences for this verse
        cursor.execute("""
            SELECT qd.id, qd.word_position, qd.word_text, qd.difference_type, qd.description
            FROM qiraat_differences qd
            WHERE qd.surah_id = ? AND qd.ayah_number = ?
        """, (surah_id, ayah_number))
        differences = []
        for diff_row in cursor.fetchall():
            diff = dict_from_row(diff_row)

            # Get the specific readings for this difference
            cursor.execute("""
                SELECT qdr.id, qdr.riwaya_id, r.code, r.name_arabic, r.name_english,
                       qdr.reading_text
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
                ORDER BY r.id
            """, (diff['id'],))
            diff['readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            differences.append(diff)

        return {
            "verse": verse_data,
            "riwayat_texts": readings,
            "differences": differences,
            "total_riwayat": len(readings),
            "has_differences": len(differences) > 0
        }


@router.get("/verse/{verse_key}/compare")
def compare_verse_readings(verse_key: str):
    """
    Compare all readings for a verse side-by-side

    Returns a structured comparison showing how each riwaya reads the verse,
    highlighting any textual differences between them.
    """
    # Parse verse key
    try:
        parts = verse_key.split(":")
        surah_id = int(parts[0])
        ayah_number = int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=400,
            detail="Invalid verse key format. Use format 'surah:ayah' (e.g., '1:4')"
        )

    with get_db() as conn:
        cursor = conn.cursor()

        # Get verse info
        cursor.execute("""
            SELECT v.id, v.verse_key, v.text_uthmani, s.name_arabic as surah_name,
                   s.name_english as surah_name_english
            FROM verses v
            JOIN surahs s ON v.surah_id = s.id
            WHERE v.surah_id = ? AND v.ayah_number = ?
        """, (surah_id, ayah_number))
        verse = cursor.fetchone()

        if not verse:
            raise HTTPException(status_code=404, detail="Verse not found")

        verse_data = dict_from_row(verse)

        # Get all riwayat texts for comparison
        cursor.execute("""
            SELECT r.id, r.code, r.name_arabic, r.name_english,
                   qt.text_uthmani, qt.text_simple
            FROM riwayat r
            LEFT JOIN qiraat_texts qt ON r.id = qt.riwaya_id
                AND qt.surah_id = ? AND qt.ayah_number = ?
            ORDER BY r.id
        """, (surah_id, ayah_number))

        comparisons = []
        unique_texts = set()
        for row in cursor.fetchall():
            reading = dict_from_row(row)
            if reading['text_uthmani']:
                unique_texts.add(reading['text_simple'] or reading['text_uthmani'])
            comparisons.append(reading)

        # Check if there are actual differences
        has_variant = len(unique_texts) > 1

        return {
            "verse": verse_data,
            "comparison": comparisons,
            "has_variant": has_variant,
            "unique_reading_count": len(unique_texts)
        }


@router.get("/surah/{surah_id}")
def get_surah_qiraat(surah_id: int):
    """
    Get all qiraat texts for a surah

    Returns all verses with their readings from different riwayat.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify surah exists
        cursor.execute("SELECT id, name_arabic, name_english FROM surahs WHERE id = ?", (surah_id,))
        surah = cursor.fetchone()
        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        surah_data = dict_from_row(surah)

        # Get all riwayat
        cursor.execute("SELECT id, code, name_arabic, name_english FROM riwayat")
        riwayat = [dict_from_row(r) for r in cursor.fetchall()]

        # Get verse count
        cursor.execute("SELECT COUNT(*) FROM verses WHERE surah_id = ?", (surah_id,))
        verse_count = cursor.fetchone()[0]

        # Get all qiraat texts for this surah
        cursor.execute("""
            SELECT qt.ayah_number, qt.text_uthmani, qt.text_simple, r.code, r.name_arabic
            FROM qiraat_texts qt
            JOIN riwayat r ON qt.riwaya_id = r.id
            WHERE qt.surah_id = ?
            ORDER BY qt.ayah_number, r.id
        """, (surah_id,))

        # Group by verse
        verses = {}
        for row in cursor.fetchall():
            ayah = row[0]
            if ayah not in verses:
                verses[ayah] = {"ayah_number": ayah, "readings": {}}
            verses[ayah]["readings"][row[3]] = {
                "text_uthmani": row[1],
                "text_simple": row[2],
                "riwaya_name": row[4]
            }

        # Get differences for this surah
        cursor.execute("""
            SELECT ayah_number FROM qiraat_differences WHERE surah_id = ?
        """, (surah_id,))
        diff_ayahs = set(row[0] for row in cursor.fetchall())

        # Mark verses with differences
        for ayah, data in verses.items():
            data["has_difference"] = ayah in diff_ayahs

        return {
            "surah": surah_data,
            "verse_count": verse_count,
            "riwayat": riwayat,
            "verses": list(verses.values()),
            "differences_count": len(diff_ayahs)
        }


@router.get("/surah/{surah_id}/differences")
def get_surah_differences(
    surah_id: int,
    difference_type: Optional[str] = Query(default=None, description="Filter by difference type")
):
    """
    Get all qiraat differences in a surah

    Returns all documented reading differences for a specific surah,
    optionally filtered by the type of difference.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify surah exists
        cursor.execute("SELECT id, name_arabic, name_english FROM surahs WHERE id = ?", (surah_id,))
        surah = cursor.fetchone()
        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        surah_data = dict_from_row(surah)

        # Build query for differences
        query = """
            SELECT qd.id, qd.surah_id, qd.ayah_number, qd.word_position,
                   qd.word_text, qd.difference_type, qd.description
            FROM qiraat_differences qd
            WHERE qd.surah_id = ?
        """
        params = [surah_id]

        if difference_type:
            query += " AND qd.difference_type = ?"
            params.append(difference_type)

        query += " ORDER BY qd.ayah_number, qd.word_position"

        cursor.execute(query, params)

        differences = []
        for diff_row in cursor.fetchall():
            diff = dict_from_row(diff_row)
            diff['verse_key'] = f"{surah_id}:{diff['ayah_number']}"

            # Get readings for this difference
            cursor.execute("""
                SELECT qdr.riwaya_id, r.code, r.name_arabic, r.name_english,
                       qdr.reading_text
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
                ORDER BY r.id
            """, (diff['id'],))
            diff['readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            differences.append(diff)

        # Group by ayah for better organization
        by_ayah = {}
        for diff in differences:
            ayah = diff['ayah_number']
            if ayah not in by_ayah:
                by_ayah[ayah] = {
                    "verse_key": f"{surah_id}:{ayah}",
                    "ayah_number": ayah,
                    "differences": []
                }
            by_ayah[ayah]['differences'].append(diff)

        return {
            "surah": surah_data,
            "total_differences": len(differences),
            "ayat_with_differences": len(by_ayah),
            "differences_by_ayah": list(by_ayah.values())
        }


@router.get("/differences/count")
def get_differences_stats():
    """
    Get statistics on qiraat differences

    Returns comprehensive statistics about the documented reading differences
    across the entire Quran.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {}

        # Total differences
        cursor.execute("SELECT COUNT(*) FROM qiraat_differences")
        stats['total_differences'] = cursor.fetchone()[0]

        # Total difference readings
        cursor.execute("SELECT COUNT(*) FROM qiraat_difference_readings")
        stats['total_readings'] = cursor.fetchone()[0]

        # Differences by type
        cursor.execute("""
            SELECT difference_type, COUNT(*) as count
            FROM qiraat_differences
            GROUP BY difference_type
            ORDER BY count DESC
        """)
        stats['by_type'] = {
            row[0] or 'unspecified': row[1]
            for row in cursor.fetchall()
        }

        # Differences per surah
        cursor.execute("""
            SELECT s.id, s.name_arabic, s.name_english, COUNT(qd.id) as count
            FROM surahs s
            LEFT JOIN qiraat_differences qd ON s.id = qd.surah_id
            GROUP BY s.id
            ORDER BY s.id
        """)
        stats['by_surah'] = [
            {
                "surah_id": row[0],
                "name_arabic": row[1],
                "name_english": row[2],
                "count": row[3]
            }
            for row in cursor.fetchall()
        ]

        # Top 10 surahs with most differences
        cursor.execute("""
            SELECT s.id, s.name_arabic, s.name_english, COUNT(qd.id) as count
            FROM qiraat_differences qd
            JOIN surahs s ON qd.surah_id = s.id
            GROUP BY s.id
            ORDER BY count DESC
            LIMIT 10
        """)
        stats['top_surahs'] = [
            {
                "surah_id": row[0],
                "name_arabic": row[1],
                "name_english": row[2],
                "count": row[3]
            }
            for row in cursor.fetchall()
        ]

        # Riwayat coverage
        cursor.execute("""
            SELECT r.id, r.code, r.name_arabic, r.name_english,
                   (SELECT COUNT(*) FROM qiraat_texts WHERE riwaya_id = r.id) as text_count,
                   (SELECT COUNT(*) FROM qiraat_difference_readings WHERE riwaya_id = r.id) as reading_count
            FROM riwayat r
            ORDER BY r.id
        """)
        stats['riwayat_coverage'] = [dict_from_row(row) for row in cursor.fetchall()]

        return stats


@router.get("/riwaya/{code}/surah/{surah_id}")
def get_riwaya_surah_text(code: str, surah_id: int):
    """
    Get specific riwaya text for a surah

    Returns the complete text of a surah according to a specific riwaya,
    identified by its code (e.g., 'hafs', 'warsh', etc.)
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify riwaya exists
        cursor.execute("""
            SELECT id, code, name_arabic, name_english, description
            FROM riwayat WHERE code = ?
        """, (code,))
        riwaya = cursor.fetchone()
        if not riwaya:
            raise HTTPException(
                status_code=404,
                detail=f"Riwaya '{code}' not found. Valid codes: hafs, warsh, qaloon, shouba, doori, soosi, bazzi, qumbul"
            )

        riwaya_data = dict_from_row(riwaya)

        # Verify surah exists
        cursor.execute("""
            SELECT id, name_arabic, name_english, ayah_count, revelation_type
            FROM surahs WHERE id = ?
        """, (surah_id,))
        surah = cursor.fetchone()
        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        surah_data = dict_from_row(surah)

        # Get all verses for this riwaya and surah
        cursor.execute("""
            SELECT qt.ayah_number, qt.text_uthmani, qt.text_simple, qt.juz, qt.page
            FROM qiraat_texts qt
            WHERE qt.riwaya_id = ? AND qt.surah_id = ?
            ORDER BY qt.ayah_number
        """, (riwaya_data['id'], surah_id))

        verses = []
        for row in cursor.fetchall():
            verse = dict_from_row(row)
            verse['verse_key'] = f"{surah_id}:{verse['ayah_number']}"
            verses.append(verse)

        return {
            "riwaya": riwaya_data,
            "surah": surah_data,
            "verses": verses,
            "verse_count": len(verses)
        }


# ============================================================================
# Original Qiraat Endpoints (using qurra, ruwat, qiraat_variants tables)
# ============================================================================

@router.get("/qurra")
def get_qurra():
    """Get all ten readers (القراء العشرة)"""
    with get_db() as conn:
        cursor = conn.cursor()
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
        return qurra


@router.get("/ruwat")
def get_ruwat():
    """Get all transmitters (الرواة)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.name_arabic, r.name_english, r.death_year_hijri,
                   r.qari_id, q.name_arabic as qari_name
            FROM ruwat r
            JOIN qurra q ON r.qari_id = q.id
            ORDER BY r.qari_id, r.id
        """)
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.get("/variants/verse/{verse_key}")
def get_verse_variants(verse_key: str):
    """Get all qiraat variants for a verse (using qiraat_variants table)"""
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

        # Get variants
        cursor.execute("""
            SELECT qv.id, qv.word_text, qv.variant_type
            FROM qiraat_variants qv
            WHERE qv.verse_id = ?
        """, (verse_data['id'],))

        variants = []
        for var_row in cursor.fetchall():
            variant = dict_from_row(var_row)

            # Get readings for this variant
            cursor.execute("""
                SELECT qr.id, qr.reading_text, qr.phonetic_description,
                       q.name_arabic as qari_name, q.id as qari_id,
                       r.name_arabic as rawi_name, r.id as rawi_id
                FROM qiraat_readings qr
                JOIN qurra q ON qr.qari_id = q.id
                LEFT JOIN ruwat r ON qr.rawi_id = r.id
                WHERE qr.variant_id = ?
            """, (variant['id'],))
            variant['readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            variants.append(variant)

        return {
            "verse": verse_data,
            "variants": variants,
            "has_differences": len(variants) > 0
        }


@router.get("/variants/surah/{surah_id}")
def get_surah_variants(surah_id: int):
    """Get all qiraat variants for a surah (using qiraat_variants table)"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify surah
        cursor.execute("SELECT id, name_arabic FROM surahs WHERE id = ?", (surah_id,))
        surah = cursor.fetchone()
        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        # Get all variants in this surah
        cursor.execute("""
            SELECT v.verse_key, v.ayah_number, v.text_uthmani,
                   qv.id as variant_id, qv.word_text, qv.variant_type
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
            WHERE v.surah_id = ?
            ORDER BY v.ayah_number
        """, (surah_id,))

        variants_by_verse = {}
        for row in cursor.fetchall():
            data = dict_from_row(row)
            verse_key = data['verse_key']

            if verse_key not in variants_by_verse:
                variants_by_verse[verse_key] = {
                    "verse_key": verse_key,
                    "ayah_number": data['ayah_number'],
                    "text_uthmani": data['text_uthmani'],
                    "variants": []
                }

            # Get readings for this variant
            cursor.execute("""
                SELECT q.name_arabic as qari_name, qr.reading_text
                FROM qiraat_readings qr
                JOIN qurra q ON qr.qari_id = q.id
                WHERE qr.variant_id = ?
            """, (data['variant_id'],))
            readings = [dict_from_row(r) for r in cursor.fetchall()]

            variants_by_verse[verse_key]['variants'].append({
                "word": data['word_text'],
                "type": data['variant_type'],
                "readings": readings
            })

        return {
            "surah": dict_from_row(surah),
            "total_differences": len(variants_by_verse),
            "verses_with_differences": list(variants_by_verse.values())
        }


@router.get("/stats")
def get_qiraat_stats():
    """Get statistics about qiraat data (using qiraat_variants table)"""
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {}

        # Total variants
        cursor.execute("SELECT COUNT(*) FROM qiraat_variants")
        stats['total_variants'] = cursor.fetchone()[0]

        # Total readings
        cursor.execute("SELECT COUNT(*) FROM qiraat_readings")
        stats['total_readings'] = cursor.fetchone()[0]

        # Variants by type
        cursor.execute("""
            SELECT variant_type, COUNT(*) as count
            FROM qiraat_variants
            GROUP BY variant_type
        """)
        stats['by_type'] = {row[0] or 'unspecified': row[1] for row in cursor.fetchall()}

        # Readings by qari
        cursor.execute("""
            SELECT q.name_arabic, COUNT(*) as count
            FROM qiraat_readings qr
            JOIN qurra q ON qr.qari_id = q.id
            GROUP BY qr.qari_id
            ORDER BY count DESC
        """)
        stats['by_qari'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Surahs with most differences
        cursor.execute("""
            SELECT s.name_arabic, s.id, COUNT(*) as count
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
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


@router.get("/stats/dashboard")
def get_qiraat_dashboard_stats():
    """
    Get comprehensive statistics for qiraat dashboard visualization

    Returns detailed statistics including:
    - Total verses with differences
    - Breakdown by surah (all surahs)
    - Breakdown by type of difference
    - Comparison between readers (qurra)
    - Most common difference patterns
    """
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {}

        # ==========================================
        # 1. Overview Statistics
        # ==========================================

        # Total variants (unique words with differences)
        cursor.execute("SELECT COUNT(*) FROM qiraat_variants")
        stats['total_variants'] = cursor.fetchone()[0]

        # Total readings (all individual reading variations)
        cursor.execute("SELECT COUNT(*) FROM qiraat_readings")
        stats['total_readings'] = cursor.fetchone()[0]

        # Count unique verses with differences
        cursor.execute("""
            SELECT COUNT(DISTINCT verse_id) FROM qiraat_variants
        """)
        stats['total_verses_with_differences'] = cursor.fetchone()[0]

        # Total verses in Quran
        cursor.execute("SELECT COUNT(*) FROM verses")
        stats['total_verses'] = cursor.fetchone()[0]

        # Percentage of verses with differences
        if stats['total_verses'] > 0:
            stats['percentage_with_differences'] = round(
                (stats['total_verses_with_differences'] / stats['total_verses']) * 100, 2
            )
        else:
            stats['percentage_with_differences'] = 0

        # Total qurra (readers)
        cursor.execute("SELECT COUNT(*) FROM qurra")
        stats['total_qurra'] = cursor.fetchone()[0]

        # ==========================================
        # 2. Breakdown by Surah (all surahs)
        # ==========================================
        cursor.execute("""
            SELECT s.id, s.name_arabic, s.name_english, s.ayah_count,
                   COUNT(DISTINCT qv.id) as variant_count,
                   COUNT(DISTINCT qv.verse_id) as verses_with_diff
            FROM surahs s
            LEFT JOIN verses v ON v.surah_id = s.id
            LEFT JOIN qiraat_variants qv ON qv.verse_id = v.id
            GROUP BY s.id
            ORDER BY s.id
        """)
        stats['by_surah'] = [
            {
                "id": row[0],
                "name_arabic": row[1],
                "name_english": row[2],
                "ayah_count": row[3],
                "variant_count": row[4],
                "verses_with_diff": row[5],
                "diff_percentage": round((row[5] / row[3]) * 100, 1) if row[3] > 0 else 0
            }
            for row in cursor.fetchall()
        ]

        # Top 10 surahs with most differences
        stats['top_surahs'] = sorted(
            [s for s in stats['by_surah'] if s['variant_count'] > 0],
            key=lambda x: x['variant_count'],
            reverse=True
        )[:10]

        # ==========================================
        # 3. Breakdown by Type of Difference
        # ==========================================
        cursor.execute("""
            SELECT
                COALESCE(variant_type, 'غير محدد') as type,
                COUNT(*) as count
            FROM qiraat_variants
            GROUP BY variant_type
            ORDER BY count DESC
        """)
        stats['by_type'] = [
            {"type": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]

        # Type descriptions (Arabic)
        type_descriptions = {
            'فرش': 'اختلافات في الألفاظ والكلمات',
            'أصول': 'اختلافات في القواعد الكلية',
            'غير محدد': 'نوع غير محدد'
        }
        for t in stats['by_type']:
            t['description'] = type_descriptions.get(t['type'], '')

        # ==========================================
        # 4. Comparison Between Readers (Qurra)
        # ==========================================
        cursor.execute("""
            SELECT q.id, q.name_arabic, q.name_english, q.city, q.death_year_hijri,
                   COUNT(qr.id) as reading_count
            FROM qurra q
            LEFT JOIN qiraat_readings qr ON qr.qari_id = q.id
            GROUP BY q.id
            ORDER BY q.rank_order
        """)
        stats['by_qari'] = [
            {
                "id": row[0],
                "name_arabic": row[1],
                "name_english": row[2],
                "city": row[3],
                "death_year": row[4],
                "reading_count": row[5]
            }
            for row in cursor.fetchall()
        ]

        # Get ruwat (transmitters) for each qari
        for qari in stats['by_qari']:
            cursor.execute("""
                SELECT r.name_arabic, COUNT(qr.id) as count
                FROM ruwat r
                LEFT JOIN qiraat_readings qr ON qr.rawi_id = r.id
                WHERE r.qari_id = ?
                GROUP BY r.id
            """, (qari['id'],))
            qari['ruwat'] = [
                {"name": row[0], "count": row[1]}
                for row in cursor.fetchall()
            ]

        # ==========================================
        # 5. Most Common Difference Patterns
        # ==========================================
        # Group by word patterns (most frequent words with differences)
        cursor.execute("""
            SELECT word_text, COUNT(*) as frequency,
                   GROUP_CONCAT(DISTINCT v.verse_key) as verse_keys
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
            GROUP BY word_text
            ORDER BY frequency DESC
            LIMIT 20
        """)
        stats['common_patterns'] = [
            {
                "word": row[0],
                "frequency": row[1],
                "verses": row[2].split(',')[:5] if row[2] else []  # Limit to 5 verse references
            }
            for row in cursor.fetchall()
        ]

        # ==========================================
        # 6. Distribution Analysis
        # ==========================================
        # Differences by revelation type (Meccan vs Medinan)
        cursor.execute("""
            SELECT s.revelation_type, COUNT(DISTINCT qv.id) as count
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
            JOIN surahs s ON v.surah_id = s.id
            GROUP BY s.revelation_type
        """)
        stats['by_revelation_type'] = {
            row[0] or 'unknown': row[1]
            for row in cursor.fetchall()
        }

        # Differences by juz (approximate - using surah ranges)
        cursor.execute("""
            SELECT
                CASE
                    WHEN v.surah_id = 1 THEN 1
                    WHEN v.surah_id = 2 AND v.ayah_number <= 141 THEN 1
                    WHEN v.surah_id = 2 AND v.ayah_number <= 252 THEN 2
                    WHEN v.surah_id = 2 THEN 3
                    WHEN v.surah_id = 3 AND v.ayah_number <= 92 THEN 3
                    WHEN v.surah_id = 3 THEN 4
                    WHEN v.surah_id <= 4 AND v.ayah_number <= 23 THEN 4
                    ELSE (v.surah_id / 5) + 1
                END as juz_approx,
                COUNT(DISTINCT qv.id) as count
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
            GROUP BY juz_approx
            ORDER BY juz_approx
        """)
        stats['by_juz'] = [
            {"juz": int(row[0]), "count": row[1]}
            for row in cursor.fetchall()
        ]

        # ==========================================
        # 7. Pairwise Reader Comparison Matrix
        # ==========================================
        # Get all qurra pairs that share readings on the same variant
        cursor.execute("""
            SELECT q1.name_arabic as reader1, q2.name_arabic as reader2,
                   COUNT(DISTINCT qr1.variant_id) as shared_variants
            FROM qiraat_readings qr1
            JOIN qiraat_readings qr2 ON qr1.variant_id = qr2.variant_id
                AND qr1.qari_id < qr2.qari_id
            JOIN qurra q1 ON qr1.qari_id = q1.id
            JOIN qurra q2 ON qr2.qari_id = q2.id
            GROUP BY qr1.qari_id, qr2.qari_id
            ORDER BY shared_variants DESC
            LIMIT 20
        """)
        stats['reader_similarities'] = [
            {"reader1": row[0], "reader2": row[1], "shared": row[2]}
            for row in cursor.fetchall()
        ]

        return stats


# ============================================================================
# Audio Comparison Endpoint
# ============================================================================

@router.get("/audio/compare/{verse_key}")
def get_verse_audio_comparison(verse_key: str):
    """
    Get all available audio sources for comparing qiraat of a specific verse.

    Returns:
    - Verse information and text
    - List of differences/variants for that verse
    - Audio availability information for each riwaya
    - Reciter information for each available audio source

    This endpoint is designed to support an audio comparison interface where
    users can listen to the same verse recited in different qiraat side-by-side.
    """
    # Parse verse key
    try:
        parts = verse_key.split(":")
        surah_id = int(parts[0])
        ayah_number = int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=400,
            detail="Invalid verse key format. Use format 'surah:ayah' (e.g., '1:4')"
        )

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
            raise HTTPException(status_code=404, detail="Verse not found")

        verse_data = dict_from_row(verse)

        # Get differences from qiraat_differences table
        differences = []
        cursor.execute("""
            SELECT qd.id, qd.word_position, qd.word_text, qd.difference_type, qd.description
            FROM qiraat_differences qd
            WHERE qd.surah_id = ? AND qd.ayah_number = ?
        """, (surah_id, ayah_number))

        for diff_row in cursor.fetchall():
            diff = dict_from_row(diff_row)

            # Get the specific readings for this difference
            cursor.execute("""
                SELECT qdr.id, qdr.riwaya_id, r.code, r.name_arabic, r.name_english,
                       qdr.reading_text
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
                ORDER BY r.id
            """, (diff['id'],))
            diff['readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            differences.append(diff)

        # Also get variants from qiraat_variants table
        cursor.execute("""
            SELECT qv.id, qv.word_text, qv.variant_type
            FROM qiraat_variants qv
            WHERE qv.verse_id = ?
        """, (verse_data['id'],))

        variants = []
        for var_row in cursor.fetchall():
            variant = dict_from_row(var_row)

            # Get readings for this variant
            cursor.execute("""
                SELECT qr.id, qr.reading_text, qr.phonetic_description,
                       q.name_arabic as qari_name, q.id as qari_id,
                       r.name_arabic as rawi_name, r.id as rawi_id
                FROM qiraat_readings qr
                JOIN qurra q ON qr.qari_id = q.id
                LEFT JOIN ruwat r ON qr.rawi_id = r.id
                WHERE qr.variant_id = ?
            """, (variant['id'],))
            variant['readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            variants.append(variant)

        # Combine differences and variants
        all_differences = differences.copy()
        for variant in variants:
            # Check if not already in differences
            existing = next((d for d in all_differences if d.get('word_text') == variant.get('word_text')), None)
            if not existing:
                all_differences.append({
                    'word_text': variant.get('word_text'),
                    'difference_type': variant.get('variant_type'),
                    'readings': variant.get('readings', [])
                })

        # Get riwayat texts if available
        riwayat_texts = []
        cursor.execute("""
            SELECT qt.id, qt.riwaya_id, r.code, r.name_arabic, r.name_english,
                   qt.text_uthmani, qt.text_simple
            FROM qiraat_texts qt
            JOIN riwayat r ON qt.riwaya_id = r.id
            WHERE qt.surah_id = ? AND qt.ayah_number = ?
            ORDER BY r.id
        """, (surah_id, ayah_number))
        riwayat_texts = [dict_from_row(row) for row in cursor.fetchall()]

        # Define audio sources for each riwaya
        # These are common audio sources from everyayah.com and similar services
        audio_sources = [
            {
                'riwaya_code': 'hafs',
                'riwaya_name': 'حفص',
                'narrator': 'عن عاصم',
                'available': True,
                'reciters': [
                    {'id': 'abdul_basit', 'name': 'عبد الباسط عبد الصمد', 'folder': 'Abdul_Basit_Murattal_64kbps'},
                    {'id': 'mishary', 'name': 'مشاري راشد العفاسي', 'folder': 'Alafasy_64kbps'},
                    {'id': 'husary', 'name': 'محمود خليل الحصري', 'folder': 'Husary_64kbps'},
                    {'id': 'minshawi', 'name': 'محمد صديق المنشاوي', 'folder': 'Minshawy_Murattal_128kbps'},
                    {'id': 'sudais', 'name': 'عبد الرحمن السديس', 'folder': 'Abdurrahmaan_As-Sudais_64kbps'}
                ]
            },
            {
                'riwaya_code': 'warsh',
                'riwaya_name': 'ورش',
                'narrator': 'عن نافع',
                'available': True,
                'reciters': [
                    {'id': 'warsh_dosary', 'name': 'إبراهيم الدوسري (ورش)', 'folder': 'warsh/warsh_ibrahim_aldosary_128kbps'}
                ]
            },
            {
                'riwaya_code': 'qaloon',
                'riwaya_name': 'قالون',
                'narrator': 'عن نافع',
                'available': False,
                'reciters': []
            },
            {
                'riwaya_code': 'shouba',
                'riwaya_name': 'شعبة',
                'narrator': 'عن عاصم',
                'available': False,
                'reciters': []
            },
            {
                'riwaya_code': 'doori',
                'riwaya_name': 'الدوري',
                'narrator': 'عن أبي عمرو',
                'available': False,
                'reciters': []
            },
            {
                'riwaya_code': 'soosi',
                'riwaya_name': 'السوسي',
                'narrator': 'عن أبي عمرو',
                'available': False,
                'reciters': []
            },
            {
                'riwaya_code': 'bazzi',
                'riwaya_name': 'البزي',
                'narrator': 'عن ابن كثير',
                'available': False,
                'reciters': []
            },
            {
                'riwaya_code': 'qumbul',
                'riwaya_name': 'قنبل',
                'narrator': 'عن ابن كثير',
                'available': False,
                'reciters': []
            }
        ]

        # Add text for each riwaya from riwayat_texts if available
        for audio in audio_sources:
            text_entry = next((t for t in riwayat_texts if t.get('code') == audio['riwaya_code']), None)
            if text_entry:
                audio['text_uthmani'] = text_entry.get('text_uthmani')
                audio['text_simple'] = text_entry.get('text_simple')
            else:
                # Use default verse text
                audio['text_uthmani'] = verse_data['text_uthmani']

        return {
            "verse": verse_data,
            "differences": all_differences,
            "riwayat_texts": riwayat_texts,
            "audio": audio_sources,
            "total_differences": len(all_differences),
            "available_audio_count": sum(1 for a in audio_sources if a['available']),
            "audio_base_url": "https://everyayah.com/data"
        }
