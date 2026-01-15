"""
المتشابهات API Routes - Mutashabihat (Similar Verses)
Provides endpoints for finding and analyzing similar verses in the Quran
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
import sqlite3
import logging

from ..database import get_db, dict_from_row

import sys
import os
# Add parent directories to path for services import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.services.quranpedia_service import get_quranpedia_service
from src.services.mutashabihat_service import get_mutashabihat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mutashabihat", tags=["Mutashabihat"])


# =============================================================================
# Local Mutashabihat (Waqar144 Data) - More Accurate
# =============================================================================

# NOTE: Specific routes must come BEFORE parameterized routes to avoid conflicts

@router.get("/local/stats")
async def get_local_stats():
    """
    الحصول على إحصائيات البيانات المحلية للمتشابهات
    Get local mutashabihat data statistics
    """
    try:
        mutashabihat_service = get_mutashabihat_service()
        return mutashabihat_service.get_stats()
    except Exception as e:
        logger.error(f"Error getting local stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local/surah/{surah_id}")
async def get_local_surah_mutashabihat(surah_id: int):
    """
    الحصول على جميع المتشابهات في سورة من البيانات المحلية
    Get all mutashabihat in a surah from local dataset

    Args:
        surah_id: رقم السورة (1-114)
    """
    try:
        if surah_id < 1 or surah_id > 114:
            raise HTTPException(status_code=400, detail="Invalid surah_id. Must be 1-114")

        mutashabihat_service = get_mutashabihat_service()
        result = mutashabihat_service.get_surah_mutashabihat(surah_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting local surah mutashabihat for {surah_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local/{verse_key}")
async def get_local_mutashabihat(verse_key: str):
    """
    الحصول على المتشابهات من البيانات المحلية (Waqar144)
    Get mutashabihat from local dataset (more accurate, curated data)

    Args:
        verse_key: مفتاح الآية (مثل 2:14)
    """
    try:
        mutashabihat_service = get_mutashabihat_service()
        result = mutashabihat_service.get_mutashabihat(verse_key)
        return result
    except Exception as e:
        logger.error(f"Error getting local mutashabihat for {verse_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Combined Mutashabihat (Local + Quranpedia)
# =============================================================================

@router.get("/combined/{verse_key}")
async def get_combined_mutashabihat(verse_key: str):
    """
    الحصول على المتشابهات من كلا المصدرين (المحلي و Quranpedia)
    Get mutashabihat from both local and Quranpedia sources

    Args:
        verse_key: مفتاح الآية (مثل 2:14)
    """
    try:
        parts = verse_key.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid verse_key format. Use surah:ayah (e.g., 2:14)")

        surah = int(parts[0])
        ayah = int(parts[1])

        # Get local data (primary, more accurate)
        mutashabihat_service = get_mutashabihat_service()
        local_result = mutashabihat_service.get_mutashabihat(verse_key)

        # Get Quranpedia data (secondary, may include thematic groupings)
        quranpedia = get_quranpedia_service()
        try:
            quranpedia_data = quranpedia.get_similar_verses_sync(surah, ayah)
        except Exception as e:
            logger.warning(f"Quranpedia API error for {verse_key}: {e}")
            quranpedia_data = None

        # Combine results
        return {
            "success": True,
            "verse_key": verse_key,
            "source_verse": local_result.get("source_verse") if local_result.get("success") else None,
            "local_mutashabihat": {
                "similar_verses": local_result.get("similar_verses", []),
                "total_count": local_result.get("total_count", 0),
                "source": "waqar144"
            },
            "quranpedia_mutashabihat": {
                "data": quranpedia_data,
                "source": "quranpedia"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting combined mutashabihat for {verse_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Helper Functions
# =============================================================================

def get_verse_by_key(cursor, verse_key: str) -> Optional[Dict]:
    """Get verse details by verse_key (e.g., '2:255')."""
    parts = verse_key.split(":")
    if len(parts) != 2:
        return None

    surah_id = int(parts[0])
    ayah_number = int(parts[1])

    cursor.execute("""
        SELECT v.*, s.name_arabic as surah_name_ar,
               s.name_english as surah_name_en,
               s.revelation_type
        FROM verses v
        JOIN surahs s ON v.surah_id = s.id
        WHERE v.surah_id = ? AND v.ayah_number = ?
    """, (surah_id, ayah_number))

    row = cursor.fetchone()
    return dict_from_row(row) if row else None


# =============================================================================
# المتشابهات لآية (Similar Verses for an Ayah)
# =============================================================================

@router.get("/verse/{verse_key}")
async def get_verse_mutashabihat(
    verse_key: str,
    source: str = Query(default="local", description="Data source: local, quranpedia, or combined")
):
    """
    الحصول على الآيات المتشابهة لآية معينة
    Get similar/mutashabihat verses for a specific ayah

    Args:
        verse_key: مفتاح الآية (مثل 2:255)
        source: مصدر البيانات (local للبيانات المحلية الأكثر دقة، quranpedia للـ API الخارجي)
    """
    try:
        parts = verse_key.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid verse_key format. Use surah:ayah (e.g., 2:255)")

        surah = int(parts[0])
        ayah = int(parts[1])

        # Get local verse data for source_verse info
        with get_db() as conn:
            cursor = conn.cursor()
            source_verse = get_verse_by_key(cursor, verse_key)

            if not source_verse:
                raise HTTPException(status_code=404, detail=f"Verse {verse_key} not found")

        # Use local data as primary source (more accurate)
        if source == "local" or source == "combined":
            mutashabihat_service = get_mutashabihat_service()
            local_result = mutashabihat_service.get_mutashabihat(verse_key)
            local_similar = local_result.get("similar_verses", []) if local_result.get("success") else []
        else:
            local_similar = []

        # Get Quranpedia data if requested
        quranpedia_data = None
        if source == "quranpedia" or source == "combined":
            quranpedia = get_quranpedia_service()
            try:
                quranpedia_data = quranpedia.get_similar_verses_sync(surah, ayah)
            except Exception as e:
                logger.warning(f"Quranpedia API error for {verse_key}: {e}")
                quranpedia_data = None

        # Build response based on source
        response = {
            "success": True,
            "verse_key": verse_key,
            "source_verse": {
                "verse_key": source_verse['verse_key'],
                "text_uthmani": source_verse.get('text_uthmani', ''),
                "text_imlaei": source_verse.get('text_imlaei', ''),
                "surah_name_ar": source_verse.get('surah_name_ar', ''),
                "surah_name_en": source_verse.get('surah_name_en', ''),
                "surah_id": source_verse['surah_id'],
                "ayah_number": source_verse['ayah_number'],
                "page_number": source_verse.get('page_number'),
                "juz_number": source_verse.get('juz_number')
            },
            "source": source
        }

        if source == "local":
            response["similar_verses"] = local_similar
            response["total_count"] = len(local_similar)
        elif source == "quranpedia":
            response["similar_verses"] = quranpedia_data
        else:  # combined
            response["local_similar"] = local_similar
            response["local_count"] = len(local_similar)
            response["quranpedia_similar"] = quranpedia_data

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mutashabihat for {verse_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# البيانات الكاملة لآية (Full Ayah Data from Quranpedia)
# =============================================================================

@router.get("/full/{verse_key}")
async def get_full_verse_data(verse_key: str):
    """
    الحصول على جميع البيانات المتاحة لآية من Quranpedia
    Get all available data for a verse (tafsir, similar, topics, e3rab, asbab, etc.)

    Args:
        verse_key: مفتاح الآية (مثل 2:255)
    """
    try:
        parts = verse_key.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid verse_key format")

        surah = int(parts[0])
        ayah = int(parts[1])

        # Get local verse data
        with get_db() as conn:
            cursor = conn.cursor()
            source_verse = get_verse_by_key(cursor, verse_key)

            if not source_verse:
                raise HTTPException(status_code=404, detail=f"Verse {verse_key} not found")

        # Get full data from Quranpedia
        quranpedia = get_quranpedia_service()
        try:
            full_data = quranpedia.get_full_ayah_data_sync(surah, ayah)
        except Exception as e:
            logger.warning(f"Quranpedia API error for {verse_key}: {e}")
            full_data = {}

        return {
            "success": True,
            "verse_key": verse_key,
            "source_verse": {
                "verse_key": source_verse['verse_key'],
                "text_uthmani": source_verse.get('text_uthmani', ''),
                "text_imlaei": source_verse.get('text_imlaei', ''),
                "surah_name_ar": source_verse.get('surah_name_ar', ''),
                "surah_name_en": source_verse.get('surah_name_en', ''),
                "surah_id": source_verse['surah_id'],
                "ayah_number": source_verse['ayah_number']
            },
            "quranpedia_data": full_data,
            "source": "quranpedia"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting full data for {verse_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# المتشابهات لسورة (Mutashabihat in a Surah)
# =============================================================================

@router.get("/surah/{surah_id}")
async def get_surah_mutashabihat(
    surah_id: int,
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    الحصول على الآيات التي لها متشابهات في سورة معينة
    Get verses that have similar verses in a specific surah

    Args:
        surah_id: رقم السورة (1-114)
        limit: الحد الأقصى للنتائج
    """
    try:
        if surah_id < 1 or surah_id > 114:
            raise HTTPException(status_code=400, detail="Invalid surah_id. Must be 1-114")

        with get_db() as conn:
            cursor = conn.cursor()

            # Get surah info
            cursor.execute("""
                SELECT * FROM surahs WHERE id = ?
            """, (surah_id,))
            surah = cursor.fetchone()

            if not surah:
                raise HTTPException(status_code=404, detail=f"Surah {surah_id} not found")

            surah_data = dict_from_row(surah)

            # Get all verses in the surah
            cursor.execute("""
                SELECT verse_key, text_uthmani, ayah_number
                FROM verses
                WHERE surah_id = ?
                ORDER BY ayah_number
            """, (surah_id,))

            verses = [dict_from_row(row) for row in cursor.fetchall()]

        # Get mutashabihat for each verse (limited)
        quranpedia = get_quranpedia_service()
        verses_with_mutashabihat = []

        for verse in verses[:limit]:
            try:
                similar = quranpedia.get_similar_verses_sync(surah_id, verse['ayah_number'])
                if similar:
                    verses_with_mutashabihat.append({
                        "verse_key": verse['verse_key'],
                        "text_uthmani": verse['text_uthmani'],
                        "ayah_number": verse['ayah_number'],
                        "similar_count": len(similar) if isinstance(similar, list) else 0,
                        "similar": similar
                    })
            except Exception as e:
                logger.debug(f"No mutashabihat for {verse['verse_key']}: {e}")
                continue

        return {
            "success": True,
            "surah": {
                "id": surah_data['id'],
                "name_arabic": surah_data.get('name_arabic', ''),
                "name_english": surah_data.get('name_english', ''),
                "ayah_count": surah_data.get('ayah_count', 0)
            },
            "verses_with_mutashabihat": verses_with_mutashabihat,
            "total_checked": min(len(verses), limit),
            "found_count": len(verses_with_mutashabihat)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting surah mutashabihat for {surah_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# معلومات السورة من Quranpedia
# =============================================================================

@router.get("/surah-info/{surah_id}")
async def get_surah_info(surah_id: int):
    """
    الحصول على معلومات تفصيلية عن السورة من Quranpedia
    Get detailed surah information from Quranpedia

    Args:
        surah_id: رقم السورة (1-114)
    """
    try:
        if surah_id < 1 or surah_id > 114:
            raise HTTPException(status_code=400, detail="Invalid surah_id. Must be 1-114")

        quranpedia = get_quranpedia_service()
        try:
            surah_info = quranpedia.get_surah_info_sync(surah_id)
        except Exception as e:
            logger.error(f"Quranpedia API error for surah {surah_id}: {e}")
            raise HTTPException(status_code=503, detail="Quranpedia API unavailable")

        return {
            "success": True,
            "surah_id": surah_id,
            "info": surah_info,
            "source": "quranpedia"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting surah info for {surah_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# البحث في Quranpedia
# =============================================================================

@router.get("/search")
async def search_quranpedia(
    q: str = Query(..., min_length=2, description="استعلام البحث"),
    type: Optional[str] = Query(default=None, description="نوع البحث: notes, fatwas, topics, books")
):
    """
    البحث في محتوى Quranpedia
    Search Quranpedia content

    Args:
        q: نص البحث
        type: نوع المحتوى للبحث فيه
    """
    try:
        quranpedia = get_quranpedia_service()
        try:
            results = quranpedia.search_sync(q, type)
        except Exception as e:
            logger.error(f"Quranpedia search error: {e}")
            raise HTTPException(status_code=503, detail="Quranpedia API unavailable")

        return {
            "success": True,
            "query": q,
            "type": type,
            "results": results,
            "source": "quranpedia"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching Quranpedia: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# الترجمات
# =============================================================================

@router.get("/translations/{verse_key}")
async def get_verse_translations(
    verse_key: str,
    language: str = Query(default="en", description="رمز اللغة")
):
    """
    الحصول على ترجمات آية
    Get translations for a verse

    Args:
        verse_key: مفتاح الآية
        language: رمز اللغة (en, ur, fr, etc.)
    """
    try:
        parts = verse_key.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid verse_key format")

        surah = int(parts[0])
        ayah = int(parts[1])

        quranpedia = get_quranpedia_service()
        try:
            translations = quranpedia.get_translations_sync(surah, ayah, language)
        except Exception as e:
            logger.error(f"Quranpedia translations error: {e}")
            raise HTTPException(status_code=503, detail="Quranpedia API unavailable")

        return {
            "success": True,
            "verse_key": verse_key,
            "language": language,
            "translations": translations,
            "source": "quranpedia"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# الإحصائيات
# =============================================================================

@router.get("/stats")
async def get_mutashabihat_stats():
    """
    الحصول على إحصائيات المتشابهات والتخزين المؤقت
    Get mutashabihat and cache statistics
    """
    try:
        quranpedia = get_quranpedia_service()
        cache_stats = quranpedia.get_cache_stats()

        with get_db() as conn:
            cursor = conn.cursor()

            # Get total verses count
            cursor.execute("SELECT COUNT(*) FROM verses")
            total_verses = cursor.fetchone()[0]

            # Get surahs count
            cursor.execute("SELECT COUNT(*) FROM surahs")
            total_surahs = cursor.fetchone()[0]

        return {
            "success": True,
            "database": {
                "total_verses": total_verses,
                "total_surahs": total_surahs
            },
            "cache": cache_stats,
            "api_source": "quranpedia.net",
            "features": [
                "similar (المتشابهات)",
                "tafsir (التفسير)",
                "e3rab (الإعراب)",
                "asbab (أسباب النزول)",
                "topics (الموضوعات)",
                "meanings (المعاني)",
                "fatwa (الفتاوى)",
                "translations (الترجمات)"
            ]
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# تنظيف التخزين المؤقت
# =============================================================================

@router.delete("/cache")
async def clear_cache(
    verse_key: Optional[str] = Query(default=None),
    data_type: Optional[str] = Query(default=None)
):
    """
    تنظيف التخزين المؤقت
    Clear cache (admin function)

    Args:
        verse_key: مفتاح الآية (اختياري)
        data_type: نوع البيانات (اختياري)
    """
    try:
        quranpedia = get_quranpedia_service()
        quranpedia.clear_cache(verse_key, data_type)

        return {
            "success": True,
            "message": "Cache cleared successfully",
            "cleared": {
                "verse_key": verse_key or "all",
                "data_type": data_type or "all"
            }
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# المصاحف (Mushafs)
# =============================================================================

@router.get("/mushafs")
async def get_mushafs():
    """
    الحصول على قائمة المصاحف المتاحة
    Get list of available mushaf editions
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_mushafs_sync()
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting mushafs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mushafs/{mushaf_id}")
async def get_mushaf(mushaf_id: int):
    """
    الحصول على تفاصيل مصحف معين
    Get details of a specific mushaf edition
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_mushaf_sync(mushaf_id)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting mushaf {mushaf_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mushafs/{mushaf_id}/{surah_id}")
async def get_mushaf_surah(mushaf_id: int, surah_id: int, ayah: Optional[int] = None):
    """
    الحصول على آيات من مصحف معين
    Get verse(s) from a specific mushaf
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_mushaf_verse_sync(mushaf_id, surah_id, ayah)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting mushaf verse: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# القراء (Reciters)
# =============================================================================

@router.get("/reciters")
async def get_reciters():
    """
    الحصول على قائمة القراء
    Get list of reciters
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_reciters_sync()
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting reciters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# الكتب (Books)
# =============================================================================

@router.get("/books")
async def get_books():
    """
    الحصول على قائمة الكتب
    Get list of books
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_book_sync()
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting books: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/books/{book_id}")
async def get_book(book_id: int):
    """
    الحصول على تفاصيل كتاب معين
    Get details of a specific book
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_book_sync(book_id)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting book {book_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/books/{book_id}/related")
async def get_related_books(book_id: int):
    """
    الحصول على الكتب ذات الصلة
    Get related books
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_related_books_sync(book_id)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting related books: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# الموضوعات (Topics)
# =============================================================================

@router.get("/topics")
async def get_all_topics():
    """
    الحصول على جميع الموضوعات
    Get all topic hierarchy
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_all_topics_sync()
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# التصنيفات (Categories)
# =============================================================================

@router.get("/categories")
async def get_categories(type: Optional[str] = None):
    """
    الحصول على التصنيفات
    Get categories (books, fatwas, notes)
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_categories_sync(type)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}/{item_type}")
async def get_category_items(category: str, item_type: str):
    """
    الحصول على عناصر تصنيف معين
    Get items within a category
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_category_items_sync(category, item_type)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting category items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# الفتاوى (Fatwas)
# =============================================================================

@router.get("/fatwas")
async def get_fatwas():
    """
    الحصول على قائمة الفتاوى
    Get list of fatwas
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_fatwa_detail_sync()
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting fatwas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fatwas/{fatwa_id}")
async def get_fatwa(fatwa_id: int):
    """
    الحصول على تفاصيل فتوى معينة
    Get details of a specific fatwa
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_fatwa_detail_sync(fatwa_id)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting fatwa {fatwa_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# الملاحظات (Notes)
# =============================================================================

@router.get("/notes")
async def get_notes():
    """
    الحصول على قائمة الملاحظات العلمية
    Get list of scholarly notes
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_note_sync()
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notes/{note_id}")
async def get_note(note_id: int):
    """
    الحصول على تفاصيل ملاحظة معينة
    Get details of a specific note
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_note_sync(note_id)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting note {note_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# بيانات السورة الإضافية (Additional Surah Data)
# =============================================================================

@router.get("/surah/{surah_id}/books")
async def get_surah_books(surah_id: int):
    """
    الحصول على الكتب المتعلقة بالسورة
    Get books related to a surah
    """
    try:
        if surah_id < 1 or surah_id > 114:
            raise HTTPException(status_code=400, detail="Invalid surah_id")
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_surah_books_sync(surah_id)
        return {"success": True, "surah_id": surah_id, "data": data, "source": "quranpedia"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting surah books: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/surah/{surah_id}/fatwas")
async def get_surah_fatwas(surah_id: int):
    """
    الحصول على الفتاوى المتعلقة بالسورة
    Get fatwas related to a surah
    """
    try:
        if surah_id < 1 or surah_id > 114:
            raise HTTPException(status_code=400, detail="Invalid surah_id")
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_surah_fatwas_sync(surah_id)
        return {"success": True, "surah_id": surah_id, "data": data, "source": "quranpedia"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting surah fatwas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/surah/{surah_id}/tafsirs")
async def get_surah_tafsirs(surah_id: int):
    """
    الحصول على التفاسير المتاحة للسورة
    Get available tafsirs for a surah
    """
    try:
        if surah_id < 1 or surah_id > 114:
            raise HTTPException(status_code=400, detail="Invalid surah_id")
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_surah_tafsirs_sync(surah_id)
        return {"success": True, "surah_id": surah_id, "data": data, "source": "quranpedia"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting surah tafsirs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# كتب الترجمة (Translation Books)
# =============================================================================

@router.get("/translation-books")
async def get_translation_books(language: Optional[str] = None):
    """
    الحصول على كتب الترجمة
    Get translation books, optionally filtered by language
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_translation_books_sync(language)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting translation books: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/translation/{book_id}/{surah_id}")
async def get_translation_from_book(book_id: int, surah_id: int, ayah: Optional[int] = None):
    """
    الحصول على ترجمة من كتاب معين
    Get translation from a specific book
    """
    try:
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_translation_from_book_sync(book_id, surah_id, ayah)
        return {"success": True, "data": data, "source": "quranpedia"}
    except Exception as e:
        logger.error(f"Error getting translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verse/{verse_key}/book/{book_id}")
async def get_verse_in_book(verse_key: str, book_id: int):
    """
    الحصول على الآية من كتاب معين
    Get verse content from a particular book
    """
    try:
        parts = verse_key.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid verse_key format")
        surah = int(parts[0])
        ayah = int(parts[1])
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_verse_in_book_sync(surah, ayah, book_id)
        return {"success": True, "verse_key": verse_key, "book_id": book_id, "data": data, "source": "quranpedia"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting verse in book: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-languages/{verse_key}")
async def get_available_languages(verse_key: str):
    """
    الحصول على اللغات المتاحة للترجمة
    Get available translation languages for a verse
    """
    try:
        parts = verse_key.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid verse_key format")
        surah = int(parts[0])
        ayah = int(parts[1])
        quranpedia = get_quranpedia_service()
        data = quranpedia.get_available_languages_sync(surah, ayah)
        return {"success": True, "verse_key": verse_key, "data": data, "source": "quranpedia"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting available languages: {e}")
        raise HTTPException(status_code=500, detail=str(e))
