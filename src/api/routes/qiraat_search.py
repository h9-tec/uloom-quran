"""
Qiraat Search API routes - البحث في اختلافات القراءات
Advanced search functionality for Quranic reading differences
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from ..database import get_db, dict_from_row

router = APIRouter(prefix="/api/qiraat", tags=["Qiraat Search"])


# ============================================================================
# Search by Word - البحث بالكلمة
# ============================================================================

@router.get("/search")
def search_qiraat_differences(
    word: Optional[str] = Query(None, min_length=1, description="كلمة للبحث عنها في الفروق"),
    type: Optional[str] = Query(None, description="نوع الفرق (همزة، مد، إدغام، إمالة، etc.)"),
    surah_id: Optional[int] = Query(None, description="تحديد السورة"),
    limit: int = Query(50, ge=1, le=200, description="عدد النتائج"),
    offset: int = Query(0, ge=0, description="تجاوز النتائج الأولى")
):
    """
    Search for qiraat differences by word and/or type

    Examples:
    - GET /api/qiraat/search?word=مالك - Find all verses where "مالك" differs between readings
    - GET /api/qiraat/search?type=همزة - Find all hamza-related differences
    - GET /api/qiraat/search?word=صراط&type=إشمام - Combined search

    Returns verses where the specified word has different readings across qiraat,
    along with the specific readings from each qari/rawi.
    """
    if not word and not type:
        raise HTTPException(
            status_code=400,
            detail="يجب تحديد كلمة البحث (word) أو نوع الفرق (type) على الأقل"
        )

    with get_db() as conn:
        cursor = conn.cursor()

        results = []

        # Search in qiraat_variants table (has detailed phonetic descriptions)
        query_variants = """
            SELECT DISTINCT
                qv.id as variant_id,
                v.verse_key,
                v.surah_id,
                s.name_arabic as surah_name,
                v.ayah_number,
                v.text_uthmani as verse_text,
                qv.word_text,
                qv.variant_type,
                qv.category
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
            JOIN surahs s ON v.surah_id = s.id
            WHERE 1=1
        """
        params_variants = []

        if word:
            query_variants += " AND qv.word_text LIKE ?"
            params_variants.append(f"%{word}%")

        if type:
            # Search in reading_text for type-related terms (phonetic descriptions)
            query_variants += """
                AND EXISTS (
                    SELECT 1 FROM qiraat_readings qr
                    WHERE qr.variant_id = qv.id
                    AND (qr.reading_text LIKE ? OR qr.phonetic_description LIKE ? OR qr.tajweed_rule LIKE ?)
                )
            """
            params_variants.extend([f"%{type}%", f"%{type}%", f"%{type}%"])

        if surah_id:
            query_variants += " AND v.surah_id = ?"
            params_variants.append(surah_id)

        query_variants += " ORDER BY v.surah_id, v.ayah_number LIMIT ? OFFSET ?"
        params_variants.extend([limit, offset])

        cursor.execute(query_variants, params_variants)

        for row in cursor.fetchall():
            variant = dict_from_row(row)

            # Get readings for this variant
            cursor.execute("""
                SELECT
                    qr.id,
                    qr.reading_text,
                    qr.phonetic_description,
                    qr.tajweed_rule,
                    qr.is_default,
                    q.id as qari_id,
                    q.name_arabic as qari_name,
                    q.name_english as qari_name_english,
                    r.id as rawi_id,
                    r.name_arabic as rawi_name,
                    r.name_english as rawi_name_english
                FROM qiraat_readings qr
                JOIN qurra q ON qr.qari_id = q.id
                LEFT JOIN ruwat r ON qr.rawi_id = r.id
                WHERE qr.variant_id = ?
                ORDER BY q.rank_order, qr.is_default DESC
            """, (variant['variant_id'],))

            variant['readings'] = [dict_from_row(r) for r in cursor.fetchall()]

            # Group readings by unique text
            unique_readings = {}
            for reading in variant['readings']:
                text = reading['reading_text']
                if text not in unique_readings:
                    unique_readings[text] = {
                        'reading_text': text,
                        'phonetic_description': reading['phonetic_description'],
                        'qurra': []
                    }
                unique_readings[text]['qurra'].append({
                    'qari_name': reading['qari_name'],
                    'rawi_name': reading['rawi_name'],
                    'is_default': reading['is_default']
                })

            variant['grouped_readings'] = list(unique_readings.values())
            results.append(variant)

        # Also search in qiraat_differences table (newer table with different structure)
        query_diff = """
            SELECT DISTINCT
                qd.id as difference_id,
                qd.surah_id,
                qd.ayah_number,
                s.name_arabic as surah_name,
                qd.word_text,
                qd.word_position,
                qd.difference_type,
                qd.description
            FROM qiraat_differences qd
            JOIN surahs s ON qd.surah_id = s.id
            WHERE 1=1
        """
        params_diff = []

        if word:
            query_diff += " AND qd.word_text LIKE ?"
            params_diff.append(f"%{word}%")

        if type:
            query_diff += " AND (qd.difference_type LIKE ? OR qd.description LIKE ?)"
            params_diff.extend([f"%{type}%", f"%{type}%"])

        if surah_id:
            query_diff += " AND qd.surah_id = ?"
            params_diff.append(surah_id)

        query_diff += " ORDER BY qd.surah_id, qd.ayah_number LIMIT ? OFFSET ?"
        params_diff.extend([limit, offset])

        cursor.execute(query_diff, params_diff)

        diff_results = []
        for row in cursor.fetchall():
            diff = dict_from_row(row)
            diff['verse_key'] = f"{diff['surah_id']}:{diff['ayah_number']}"

            # Get readings for this difference
            cursor.execute("""
                SELECT
                    qdr.reading_text,
                    r.id as riwaya_id,
                    r.code as riwaya_code,
                    r.name_arabic as riwaya_name,
                    r.name_english as riwaya_name_english
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
                ORDER BY r.id
            """, (diff['difference_id'],))

            diff['riwayat_readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            diff_results.append(diff)

        # Get total count for pagination
        count_query = """
            SELECT COUNT(DISTINCT qv.id)
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
            WHERE 1=1
        """
        count_params = []

        if word:
            count_query += " AND qv.word_text LIKE ?"
            count_params.append(f"%{word}%")

        if type:
            count_query += """
                AND EXISTS (
                    SELECT 1 FROM qiraat_readings qr
                    WHERE qr.variant_id = qv.id
                    AND (qr.reading_text LIKE ? OR qr.phonetic_description LIKE ?)
                )
            """
            count_params.extend([f"%{type}%", f"%{type}%"])

        if surah_id:
            count_query += " AND v.surah_id = ?"
            count_params.append(surah_id)

        cursor.execute(count_query, count_params)
        total_variants = cursor.fetchone()[0]

        return {
            "search_params": {
                "word": word,
                "type": type,
                "surah_id": surah_id
            },
            "total_results": total_variants + len(diff_results),
            "variants_results": results,
            "differences_results": diff_results,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_variants
            }
        }


# ============================================================================
# Search by Difference Type - البحث بنوع الفرق
# ============================================================================

@router.get("/search/types")
def get_difference_types():
    """
    Get all available difference types for filtering

    Returns a list of all unique difference types found in the qiraat data,
    including categories from qiraat_variants and types from qiraat_differences.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        types = {
            "variant_types": [],
            "categories": [],
            "difference_types": [],
            "common_tajweed_terms": [
                "همزة",
                "مد",
                "إدغام",
                "إمالة",
                "إشمام",
                "صلة",
                "سكت",
                "روم",
                "تسهيل",
                "إبدال",
                "حذف",
                "إثبات",
                "فتح",
                "كسر",
                "ضم",
                "تحقيق",
                "تخفيف"
            ]
        }

        # Get variant types from qiraat_variants
        cursor.execute("""
            SELECT DISTINCT variant_type, COUNT(*) as count
            FROM qiraat_variants
            WHERE variant_type IS NOT NULL
            GROUP BY variant_type
            ORDER BY count DESC
        """)
        types["variant_types"] = [
            {"type": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]

        # Get categories from qiraat_variants
        cursor.execute("""
            SELECT DISTINCT category, COUNT(*) as count
            FROM qiraat_variants
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)
        types["categories"] = [
            {"category": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]

        # Get difference types from qiraat_differences
        cursor.execute("""
            SELECT DISTINCT difference_type, COUNT(*) as count
            FROM qiraat_differences
            WHERE difference_type IS NOT NULL
            GROUP BY difference_type
            ORDER BY count DESC
        """)
        types["difference_types"] = [
            {"type": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]

        return types


# ============================================================================
# Compare Two Riwayat - مقارنة بين روايتين
# ============================================================================

@router.get("/compare/{riwaya1}/{riwaya2}")
def compare_two_riwayat(
    riwaya1: str,
    riwaya2: str,
    surah_id: Optional[int] = Query(None, description="تحديد سورة معينة"),
    limit: int = Query(100, ge=1, le=500, description="عدد النتائج"),
    offset: int = Query(0, ge=0, description="تجاوز النتائج")
):
    """
    Find all differences between two specific riwayat (e.g., Hafs vs Warsh)

    Examples:
    - GET /api/qiraat/compare/hafs/warsh - All differences between Hafs and Warsh
    - GET /api/qiraat/compare/hafs/warsh?surah_id=2 - Differences in Al-Baqarah only

    Valid riwaya codes: hafs, warsh, qaloon, shouba, doori, soosi, bazzi, qumbul

    Returns a list of verses where the two riwayat differ, showing both readings
    side by side for easy comparison.
    """
    valid_codes = ['hafs', 'warsh', 'qaloon', 'shouba', 'doori', 'soosi', 'bazzi', 'qumbul']

    if riwaya1.lower() not in valid_codes:
        raise HTTPException(
            status_code=400,
            detail=f"الرواية الأولى '{riwaya1}' غير صالحة. الروايات المتاحة: {', '.join(valid_codes)}"
        )

    if riwaya2.lower() not in valid_codes:
        raise HTTPException(
            status_code=400,
            detail=f"الرواية الثانية '{riwaya2}' غير صالحة. الروايات المتاحة: {', '.join(valid_codes)}"
        )

    if riwaya1.lower() == riwaya2.lower():
        raise HTTPException(
            status_code=400,
            detail="يجب اختيار روايتين مختلفتين للمقارنة"
        )

    with get_db() as conn:
        cursor = conn.cursor()

        # Get riwaya info
        cursor.execute("""
            SELECT id, code, name_arabic, name_english, description
            FROM riwayat WHERE code IN (?, ?)
        """, (riwaya1.lower(), riwaya2.lower()))

        riwayat_info = {}
        for row in cursor.fetchall():
            riwaya = dict_from_row(row)
            riwayat_info[riwaya['code']] = riwaya

        if len(riwayat_info) < 2:
            raise HTTPException(
                status_code=404,
                detail="لم يتم العثور على إحدى الروايتين في قاعدة البيانات"
            )

        riwaya1_id = riwayat_info[riwaya1.lower()]['id']
        riwaya2_id = riwayat_info[riwaya2.lower()]['id']

        # Find verses where the two riwayat have different texts
        # Use text_uthmani for comparison since text_simple may be empty
        query = """
            SELECT
                qt1.surah_id,
                qt1.ayah_number,
                s.name_arabic as surah_name,
                s.name_english as surah_name_english,
                qt1.text_uthmani as text_riwaya1,
                COALESCE(NULLIF(qt1.text_simple, ''), qt1.text_uthmani) as text_simple_riwaya1,
                qt2.text_uthmani as text_riwaya2,
                COALESCE(NULLIF(qt2.text_simple, ''), qt2.text_uthmani) as text_simple_riwaya2
            FROM qiraat_texts qt1
            JOIN qiraat_texts qt2 ON qt1.surah_id = qt2.surah_id
                AND qt1.ayah_number = qt2.ayah_number
            JOIN surahs s ON qt1.surah_id = s.id
            WHERE qt1.riwaya_id = ? AND qt2.riwaya_id = ?
                AND qt1.text_uthmani != qt2.text_uthmani
        """
        params = [riwaya1_id, riwaya2_id]

        if surah_id:
            query += " AND qt1.surah_id = ?"
            params.append(surah_id)

        query += " ORDER BY qt1.surah_id, qt1.ayah_number LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)

        differences = []
        for row in cursor.fetchall():
            diff = dict_from_row(row)
            diff['verse_key'] = f"{diff['surah_id']}:{diff['ayah_number']}"
            diff['riwaya1'] = {
                'code': riwaya1.lower(),
                'name_arabic': riwayat_info[riwaya1.lower()]['name_arabic'],
                'text': diff['text_riwaya1'],
                'text_simple': diff['text_simple_riwaya1']
            }
            diff['riwaya2'] = {
                'code': riwaya2.lower(),
                'name_arabic': riwayat_info[riwaya2.lower()]['name_arabic'],
                'text': diff['text_riwaya2'],
                'text_simple': diff['text_simple_riwaya2']
            }
            # Remove duplicate fields
            del diff['text_riwaya1']
            del diff['text_riwaya2']
            del diff['text_simple_riwaya1']
            del diff['text_simple_riwaya2']
            differences.append(diff)

        # Get total count
        count_query = """
            SELECT COUNT(*)
            FROM qiraat_texts qt1
            JOIN qiraat_texts qt2 ON qt1.surah_id = qt2.surah_id
                AND qt1.ayah_number = qt2.ayah_number
            WHERE qt1.riwaya_id = ? AND qt2.riwaya_id = ?
                AND qt1.text_uthmani != qt2.text_uthmani
        """
        count_params = [riwaya1_id, riwaya2_id]

        if surah_id:
            count_query += " AND qt1.surah_id = ?"
            count_params.append(surah_id)

        cursor.execute(count_query, count_params)
        total_differences = cursor.fetchone()[0]

        # Also get differences from qiraat_difference_readings
        diff_readings_query = """
            SELECT
                qd.id,
                qd.surah_id,
                qd.ayah_number,
                s.name_arabic as surah_name,
                qd.word_text,
                qd.word_position,
                qd.difference_type,
                qd.description,
                qdr1.reading_text as reading1,
                qdr2.reading_text as reading2
            FROM qiraat_differences qd
            JOIN surahs s ON qd.surah_id = s.id
            LEFT JOIN qiraat_difference_readings qdr1 ON qd.id = qdr1.difference_id AND qdr1.riwaya_id = ?
            LEFT JOIN qiraat_difference_readings qdr2 ON qd.id = qdr2.difference_id AND qdr2.riwaya_id = ?
            WHERE (qdr1.reading_text IS NOT NULL OR qdr2.reading_text IS NOT NULL)
                AND (qdr1.reading_text != qdr2.reading_text OR qdr1.reading_text IS NULL OR qdr2.reading_text IS NULL)
        """
        diff_params = [riwaya1_id, riwaya2_id]

        if surah_id:
            diff_readings_query += " AND qd.surah_id = ?"
            diff_params.append(surah_id)

        diff_readings_query += " ORDER BY qd.surah_id, qd.ayah_number LIMIT ?"
        diff_params.append(limit)

        cursor.execute(diff_readings_query, diff_params)

        word_differences = []
        for row in cursor.fetchall():
            word_diff = dict_from_row(row)
            word_diff['verse_key'] = f"{word_diff['surah_id']}:{word_diff['ayah_number']}"
            word_diff['readings'] = {
                riwaya1.lower(): word_diff.get('reading1'),
                riwaya2.lower(): word_diff.get('reading2')
            }
            del word_diff['reading1']
            del word_diff['reading2']
            word_differences.append(word_diff)

        return {
            "comparison": {
                "riwaya1": riwayat_info[riwaya1.lower()],
                "riwaya2": riwayat_info[riwaya2.lower()]
            },
            "filter": {
                "surah_id": surah_id
            },
            "total_verse_differences": total_differences,
            "verse_differences": differences,
            "word_level_differences": word_differences,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_differences
            }
        }


# ============================================================================
# Advanced Search - بحث متقدم
# ============================================================================

@router.get("/search/advanced")
def advanced_qiraat_search(
    word: Optional[str] = Query(None, description="كلمة للبحث"),
    qari_id: Optional[int] = Query(None, description="معرف القارئ"),
    rawi_id: Optional[int] = Query(None, description="معرف الراوي"),
    variant_type: Optional[str] = Query(None, description="نوع الفرق: أصول أو فرش"),
    surah_id: Optional[int] = Query(None, description="رقم السورة"),
    has_meaning_difference: Optional[bool] = Query(None, description="فقط الفروق ذات الأثر في المعنى"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Advanced search with multiple filters

    Allows searching qiraat differences by:
    - Word text
    - Specific qari (reader)
    - Specific rawi (transmitter)
    - Variant type (usul/farsh)
    - Surah
    - Semantic impact (meaning differences)
    """
    with get_db() as conn:
        cursor = conn.cursor()

        query = """
            SELECT DISTINCT
                qv.id as variant_id,
                v.verse_key,
                v.surah_id,
                s.name_arabic as surah_name,
                v.ayah_number,
                v.text_uthmani as verse_text,
                qv.word_text,
                qv.variant_type,
                qv.category,
                qsi.has_meaning_difference,
                qsi.meaning_explanation,
                qsi.fiqhi_implication
            FROM qiraat_variants qv
            JOIN verses v ON qv.verse_id = v.id
            JOIN surahs s ON v.surah_id = s.id
            LEFT JOIN qiraat_semantic_impact qsi ON qv.id = qsi.variant_id
            WHERE 1=1
        """
        params = []

        if word:
            query += " AND qv.word_text LIKE ?"
            params.append(f"%{word}%")

        if qari_id:
            query += """
                AND EXISTS (
                    SELECT 1 FROM qiraat_readings qr
                    WHERE qr.variant_id = qv.id AND qr.qari_id = ?
                )
            """
            params.append(qari_id)

        if rawi_id:
            query += """
                AND EXISTS (
                    SELECT 1 FROM qiraat_readings qr
                    WHERE qr.variant_id = qv.id AND qr.rawi_id = ?
                )
            """
            params.append(rawi_id)

        if variant_type:
            query += " AND qv.variant_type = ?"
            params.append(variant_type)

        if surah_id:
            query += " AND v.surah_id = ?"
            params.append(surah_id)

        if has_meaning_difference is not None:
            if has_meaning_difference:
                query += " AND qsi.has_meaning_difference = 1"
            else:
                query += " AND (qsi.has_meaning_difference = 0 OR qsi.has_meaning_difference IS NULL)"

        query += " ORDER BY v.surah_id, v.ayah_number LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)

        results = []
        for row in cursor.fetchall():
            variant = dict_from_row(row)

            # Get all readings for this variant
            cursor.execute("""
                SELECT
                    qr.reading_text,
                    qr.phonetic_description,
                    qr.is_default,
                    q.id as qari_id,
                    q.name_arabic as qari_name,
                    r.id as rawi_id,
                    r.name_arabic as rawi_name
                FROM qiraat_readings qr
                JOIN qurra q ON qr.qari_id = q.id
                LEFT JOIN ruwat r ON qr.rawi_id = r.id
                WHERE qr.variant_id = ?
            """, (variant['variant_id'],))

            variant['readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            results.append(variant)

        return {
            "search_params": {
                "word": word,
                "qari_id": qari_id,
                "rawi_id": rawi_id,
                "variant_type": variant_type,
                "surah_id": surah_id,
                "has_meaning_difference": has_meaning_difference
            },
            "results": results,
            "count": len(results),
            "pagination": {
                "limit": limit,
                "offset": offset
            }
        }


# ============================================================================
# Get Qurra and Ruwat for Search Filters
# ============================================================================

@router.get("/search/filters")
def get_search_filters():
    """
    Get all available filter options for search

    Returns lists of:
    - All qurra (readers) with their IDs
    - All ruwat (transmitters) with their IDs
    - All riwayat (transmission chains) with their codes
    - All variant types
    - All surahs with qiraat differences
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get qurra
        cursor.execute("""
            SELECT id, name_arabic, name_english, city, region
            FROM qurra ORDER BY rank_order
        """)
        qurra = [dict_from_row(row) for row in cursor.fetchall()]

        # Get ruwat
        cursor.execute("""
            SELECT r.id, r.name_arabic, r.name_english,
                   q.name_arabic as qari_name, q.id as qari_id
            FROM ruwat r
            JOIN qurra q ON r.qari_id = q.id
            ORDER BY r.qari_id, r.id
        """)
        ruwat = [dict_from_row(row) for row in cursor.fetchall()]

        # Get riwayat
        cursor.execute("""
            SELECT id, code, name_arabic, name_english
            FROM riwayat ORDER BY id
        """)
        riwayat = [dict_from_row(row) for row in cursor.fetchall()]

        # Get variant types
        cursor.execute("""
            SELECT DISTINCT variant_type FROM qiraat_variants
            WHERE variant_type IS NOT NULL
        """)
        variant_types = [row[0] for row in cursor.fetchall()]

        # Get surahs with differences
        cursor.execute("""
            SELECT DISTINCT s.id, s.name_arabic, s.name_english,
                   COUNT(qv.id) as difference_count
            FROM surahs s
            JOIN verses v ON s.id = v.surah_id
            JOIN qiraat_variants qv ON v.id = qv.verse_id
            GROUP BY s.id
            ORDER BY s.id
        """)
        surahs = [dict_from_row(row) for row in cursor.fetchall()]

        return {
            "qurra": qurra,
            "ruwat": ruwat,
            "riwayat": riwayat,
            "variant_types": variant_types,
            "surahs_with_differences": surahs
        }
