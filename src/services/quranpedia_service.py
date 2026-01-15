"""
Quranpedia API Service - تكامل مع واجهة Quranpedia
Provides access to mutashabihat, tafsir, e3rab, asbab, and more
"""

import httpx
import json
import sqlite3
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

BASE_URL = "https://api.quranpedia.net/v1"
CACHE_DURATION_HOURS = 24  # Cache data for 24 hours


class QuranpediaService:
    """
    Service for interacting with Quranpedia API.
    Includes caching to respect rate limits (600 requests/window).
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or "/home/hesham-haroun/Quran/db/uloom_quran.db"
        self._ensure_cache_tables()

    @contextmanager
    def _get_db(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_cache_tables(self):
        """Create cache tables if they don't exist."""
        with self._get_db() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                -- تخزين البيانات من Quranpedia
                CREATE TABLE IF NOT EXISTS quranpedia_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    verse_key TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(verse_key, data_type)
                );

                CREATE INDEX IF NOT EXISTS idx_qp_cache_verse
                ON quranpedia_cache(verse_key);

                CREATE INDEX IF NOT EXISTS idx_qp_cache_type
                ON quranpedia_cache(data_type);

                -- تخزين بيانات السور
                CREATE TABLE IF NOT EXISTS quranpedia_surah_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    surah_id INTEGER NOT NULL UNIQUE,
                    data TEXT NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    def _get_cached(self, verse_key: str, data_type: str) -> Optional[Dict]:
        """Get cached data if not expired."""
        with self._get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data, fetched_at FROM quranpedia_cache
                WHERE verse_key = ? AND data_type = ?
            """, (verse_key, data_type))
            row = cursor.fetchone()

            if row:
                fetched_at = datetime.fromisoformat(row['fetched_at'])
                if datetime.now() - fetched_at < timedelta(hours=CACHE_DURATION_HOURS):
                    return json.loads(row['data'])
        return None

    def _set_cached(self, verse_key: str, data_type: str, data: Dict):
        """Store data in cache."""
        with self._get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO quranpedia_cache
                (verse_key, data_type, data, fetched_at)
                VALUES (?, ?, ?, ?)
            """, (verse_key, data_type, json.dumps(data, ensure_ascii=False),
                  datetime.now().isoformat()))
            conn.commit()

    async def _fetch(self, endpoint: str) -> Dict:
        """Fetch data from Quranpedia API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{BASE_URL}{endpoint}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Quranpedia API error: {e.response.status_code} for {endpoint}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Quranpedia request error: {e}")
                raise

    def _fetch_sync(self, endpoint: str) -> Dict:
        """Synchronous fetch for non-async contexts."""
        try:
            response = httpx.get(f"{BASE_URL}{endpoint}", timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Quranpedia API error: {e.response.status_code} for {endpoint}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Quranpedia request error: {e}")
            raise

    # ==========================================================================
    # المتشابهات (Similar Verses)
    # ==========================================================================

    async def get_similar_verses(self, surah: int, ayah: int) -> Dict:
        """Get similar/mutashabihat verses for a specific ayah."""
        verse_key = f"{surah}:{ayah}"

        # Check cache first
        cached = self._get_cached(verse_key, "similar")
        if cached:
            return cached

        # Fetch from API
        data = await self._fetch(f"/ayah/{surah}/{ayah}/similar")
        self._set_cached(verse_key, "similar", data)
        return data

    def get_similar_verses_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_similar_verses."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "similar")
        if cached:
            return cached

        data = self._fetch_sync(f"/ayah/{surah}/{ayah}/similar")
        self._set_cached(verse_key, "similar", data)
        return data

    # ==========================================================================
    # التفسير (Tafsir)
    # ==========================================================================

    async def get_tafsir(self, surah: int, ayah: int) -> Dict:
        """Get tafsir for a specific ayah."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "tafsir")
        if cached:
            return cached

        data = await self._fetch(f"/ayah/{surah}/{ayah}/tafsir")
        self._set_cached(verse_key, "tafsir", data)
        return data

    def get_tafsir_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_tafsir."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "tafsir")
        if cached:
            return cached

        data = self._fetch_sync(f"/ayah/{surah}/{ayah}/tafsir")
        self._set_cached(verse_key, "tafsir", data)
        return data

    # ==========================================================================
    # الإعراب (Grammar Analysis)
    # ==========================================================================

    async def get_e3rab(self, surah: int, ayah: int) -> Dict:
        """Get grammatical analysis (إعراب) for a specific ayah."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "e3rab")
        if cached:
            return cached

        data = await self._fetch(f"/ayah/{surah}/{ayah}/e3rab")
        self._set_cached(verse_key, "e3rab", data)
        return data

    def get_e3rab_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_e3rab."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "e3rab")
        if cached:
            return cached

        data = self._fetch_sync(f"/ayah/{surah}/{ayah}/e3rab")
        self._set_cached(verse_key, "e3rab", data)
        return data

    # ==========================================================================
    # أسباب النزول (Reasons for Revelation)
    # ==========================================================================

    async def get_asbab(self, surah: int, ayah: int) -> Dict:
        """Get asbab al-nuzul for a specific ayah."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "asbab")
        if cached:
            return cached

        data = await self._fetch(f"/ayah/{surah}/{ayah}/asbab")
        self._set_cached(verse_key, "asbab", data)
        return data

    def get_asbab_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_asbab."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "asbab")
        if cached:
            return cached

        data = self._fetch_sync(f"/ayah/{surah}/{ayah}/asbab")
        self._set_cached(verse_key, "asbab", data)
        return data

    # ==========================================================================
    # الموضوعات (Topics)
    # ==========================================================================

    async def get_topics(self, surah: int, ayah: int) -> Dict:
        """Get thematic topics for a specific ayah."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "topics")
        if cached:
            return cached

        data = await self._fetch(f"/ayah/{surah}/{ayah}/topics")
        self._set_cached(verse_key, "topics", data)
        return data

    def get_topics_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_topics."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "topics")
        if cached:
            return cached

        data = self._fetch_sync(f"/ayah/{surah}/{ayah}/topics")
        self._set_cached(verse_key, "topics", data)
        return data

    # ==========================================================================
    # المعاني (Meanings)
    # ==========================================================================

    async def get_meanings(self, surah: int, ayah: int) -> Dict:
        """Get semantic meanings for a specific ayah."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "meanings")
        if cached:
            return cached

        data = await self._fetch(f"/ayah/{surah}/{ayah}/meanings")
        self._set_cached(verse_key, "meanings", data)
        return data

    def get_meanings_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_meanings."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "meanings")
        if cached:
            return cached

        data = self._fetch_sync(f"/ayah/{surah}/{ayah}/meanings")
        self._set_cached(verse_key, "meanings", data)
        return data

    # ==========================================================================
    # الفتاوى (Fatwas)
    # ==========================================================================

    async def get_fatwa(self, surah: int, ayah: int) -> Dict:
        """Get related fatwas for a specific ayah."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "fatwa")
        if cached:
            return cached

        data = await self._fetch(f"/ayah/{surah}/{ayah}/fatwa")
        self._set_cached(verse_key, "fatwa", data)
        return data

    def get_fatwa_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_fatwa."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "fatwa")
        if cached:
            return cached

        data = self._fetch_sync(f"/ayah/{surah}/{ayah}/fatwa")
        self._set_cached(verse_key, "fatwa", data)
        return data

    # ==========================================================================
    # البيانات الكاملة (Full Data)
    # ==========================================================================

    async def get_full_ayah_data(self, surah: int, ayah: int) -> Dict:
        """Get all available data for a specific ayah by fetching each endpoint."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "full")
        if cached:
            return cached

        # Fetch each type separately and combine
        data = {}
        endpoints = ['similar', 'tafsir', 'e3rab', 'asbab', 'topics', 'meanings', 'notes', 'fatwa']

        for endpoint in endpoints:
            try:
                result = await self._fetch(f"/ayah/{surah}/{ayah}/{endpoint}")
                data[endpoint] = result
            except Exception as e:
                logger.debug(f"No {endpoint} data for {verse_key}: {e}")
                data[endpoint] = None

        self._set_cached(verse_key, "full", data)
        return data

    def get_full_ayah_data_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_full_ayah_data."""
        verse_key = f"{surah}:{ayah}"

        cached = self._get_cached(verse_key, "full")
        if cached:
            return cached

        # Fetch each type separately and combine
        data = {}
        endpoints = ['similar', 'tafsir', 'e3rab', 'asbab', 'topics', 'meanings', 'notes', 'fatwa']

        for endpoint in endpoints:
            try:
                result = self._fetch_sync(f"/ayah/{surah}/{ayah}/{endpoint}")
                data[endpoint] = result
            except Exception as e:
                logger.debug(f"No {endpoint} data for {verse_key}: {e}")
                data[endpoint] = None

        self._set_cached(verse_key, "full", data)
        return data

    # ==========================================================================
    # الترجمات (Translations)
    # ==========================================================================

    async def get_translations(self, surah: int, ayah: int,
                               language: str = "en") -> Dict:
        """Get translations for a specific ayah."""
        verse_key = f"{surah}:{ayah}"
        cache_key = f"translations_{language}"

        cached = self._get_cached(verse_key, cache_key)
        if cached:
            return cached

        data = await self._fetch(f"/translations/{surah}/{ayah}/{language}")
        self._set_cached(verse_key, cache_key, data)
        return data

    def get_translations_sync(self, surah: int, ayah: int,
                              language: str = "en") -> Dict:
        """Synchronous version of get_translations."""
        verse_key = f"{surah}:{ayah}"
        cache_key = f"translations_{language}"

        cached = self._get_cached(verse_key, cache_key)
        if cached:
            return cached

        data = self._fetch_sync(f"/translations/{surah}/{ayah}/{language}")
        self._set_cached(verse_key, cache_key, data)
        return data

    async def get_available_languages(self, surah: int, ayah: int) -> Dict:
        """Get available translation languages for a specific ayah."""
        return await self._fetch(f"/translations/available-languages/{surah}/{ayah}")

    # ==========================================================================
    # معلومات السورة (Surah Information)
    # ==========================================================================

    async def get_surah_info(self, surah: int) -> Dict:
        """Get detailed information about a surah."""
        with self._get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data, fetched_at FROM quranpedia_surah_cache
                WHERE surah_id = ?
            """, (surah,))
            row = cursor.fetchone()

            if row:
                fetched_at = datetime.fromisoformat(row['fetched_at'])
                if datetime.now() - fetched_at < timedelta(hours=CACHE_DURATION_HOURS):
                    return json.loads(row['data'])

        data = await self._fetch(f"/surah/information/{surah}")

        with self._get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO quranpedia_surah_cache
                (surah_id, data, fetched_at)
                VALUES (?, ?, ?)
            """, (surah, json.dumps(data, ensure_ascii=False),
                  datetime.now().isoformat()))
            conn.commit()

        return data

    def get_surah_info_sync(self, surah: int) -> Dict:
        """Synchronous version of get_surah_info."""
        with self._get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data, fetched_at FROM quranpedia_surah_cache
                WHERE surah_id = ?
            """, (surah,))
            row = cursor.fetchone()

            if row:
                fetched_at = datetime.fromisoformat(row['fetched_at'])
                if datetime.now() - fetched_at < timedelta(hours=CACHE_DURATION_HOURS):
                    return json.loads(row['data'])

        data = self._fetch_sync(f"/surah/information/{surah}")

        with self._get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO quranpedia_surah_cache
                (surah_id, data, fetched_at)
                VALUES (?, ?, ?)
            """, (surah, json.dumps(data, ensure_ascii=False),
                  datetime.now().isoformat()))
            conn.commit()

        return data

    # ==========================================================================
    # البحث (Search)
    # ==========================================================================

    async def search(self, query: str, search_type: str = None) -> Dict:
        """Search Quranpedia content."""
        endpoint = f"/search/{query}"
        if search_type:
            endpoint += f"/{search_type}"
        return await self._fetch(endpoint)

    def search_sync(self, query: str, search_type: str = None) -> Dict:
        """Synchronous version of search."""
        endpoint = f"/search/{query}"
        if search_type:
            endpoint += f"/{search_type}"
        return self._fetch_sync(endpoint)

    # ==========================================================================
    # المصاحف والقراء (Mushafs & Reciters)
    # ==========================================================================

    async def get_mushafs(self) -> Dict:
        """Get available mushaf manuscripts."""
        return await self._fetch("/mushafs")

    async def get_reciters(self) -> Dict:
        """Get available reciters."""
        return await self._fetch("/reciters")

    # ==========================================================================
    # الكتب والفتاوى (Books & Fatwas)
    # ==========================================================================

    async def get_book(self, book_id: int = None) -> Dict:
        """Get book details or list all books."""
        endpoint = f"/book/{book_id}" if book_id else "/book"
        return await self._fetch(endpoint)

    def get_book_sync(self, book_id: int = None) -> Dict:
        """Synchronous version of get_book."""
        endpoint = f"/book/{book_id}" if book_id else "/book"
        return self._fetch_sync(endpoint)

    async def get_related_books(self, book_id: int = None) -> Dict:
        """Get related books."""
        endpoint = f"/related-books/{book_id}" if book_id else "/related-books"
        return await self._fetch(endpoint)

    def get_related_books_sync(self, book_id: int = None) -> Dict:
        """Synchronous version of get_related_books."""
        endpoint = f"/related-books/{book_id}" if book_id else "/related-books"
        return self._fetch_sync(endpoint)

    async def get_fatwa_detail(self, fatwa_id: int = None) -> Dict:
        """Get fatwa details or list all fatwas."""
        endpoint = f"/fatwa/{fatwa_id}" if fatwa_id else "/fatwa"
        return await self._fetch(endpoint)

    def get_fatwa_detail_sync(self, fatwa_id: int = None) -> Dict:
        """Synchronous version of get_fatwa_detail."""
        endpoint = f"/fatwa/{fatwa_id}" if fatwa_id else "/fatwa"
        return self._fetch_sync(endpoint)

    async def get_note(self, note_id: int = None) -> Dict:
        """Get note details or list all notes."""
        endpoint = f"/note/{note_id}" if note_id else "/note"
        return await self._fetch(endpoint)

    def get_note_sync(self, note_id: int = None) -> Dict:
        """Synchronous version of get_note."""
        endpoint = f"/note/{note_id}" if note_id else "/note"
        return self._fetch_sync(endpoint)

    async def get_all_topics(self) -> Dict:
        """Get full topic hierarchy."""
        return await self._fetch("/topics")

    def get_all_topics_sync(self) -> Dict:
        """Synchronous version of get_all_topics."""
        return self._fetch_sync("/topics")

    # ==========================================================================
    # التصنيفات (Categories)
    # ==========================================================================

    async def get_categories(self, category_type: str = None) -> Dict:
        """Get categories (books, fatwas, notes)."""
        endpoint = f"/categories/{category_type}" if category_type else "/categories"
        return await self._fetch(endpoint)

    def get_categories_sync(self, category_type: str = None) -> Dict:
        """Synchronous version of get_categories."""
        endpoint = f"/categories/{category_type}" if category_type else "/categories"
        return self._fetch_sync(endpoint)

    async def get_category_items(self, category: str, item_type: str) -> Dict:
        """Get items within a category."""
        return await self._fetch(f"/category/{category}/{item_type}")

    def get_category_items_sync(self, category: str, item_type: str) -> Dict:
        """Synchronous version of get_category_items."""
        return self._fetch_sync(f"/category/{category}/{item_type}")

    # ==========================================================================
    # المصاحف (Mushafs)
    # ==========================================================================

    async def get_mushaf(self, mushaf_id: int) -> Dict:
        """Get single mushaf details."""
        return await self._fetch(f"/mushafs/{mushaf_id}")

    def get_mushaf_sync(self, mushaf_id: int) -> Dict:
        """Synchronous version of get_mushaf."""
        return self._fetch_sync(f"/mushafs/{mushaf_id}")

    def get_mushafs_sync(self) -> Dict:
        """Synchronous version of get_mushafs."""
        return self._fetch_sync("/mushafs")

    async def get_mushaf_verse(self, mushaf_id: int, surah: int, ayah: int = None) -> Dict:
        """Get verse(s) from a specific mushaf."""
        endpoint = f"/mushafs/{mushaf_id}/{surah}"
        if ayah:
            endpoint += f"/{ayah}"
        return await self._fetch(endpoint)

    def get_mushaf_verse_sync(self, mushaf_id: int, surah: int, ayah: int = None) -> Dict:
        """Synchronous version of get_mushaf_verse."""
        endpoint = f"/mushafs/{mushaf_id}/{surah}"
        if ayah:
            endpoint += f"/{ayah}"
        return self._fetch_sync(endpoint)

    def get_reciters_sync(self) -> Dict:
        """Synchronous version of get_reciters."""
        return self._fetch_sync("/reciters")

    # ==========================================================================
    # بيانات السورة الإضافية (Additional Surah Data)
    # ==========================================================================

    async def get_surah_books(self, surah: int) -> Dict:
        """Get books related to a surah."""
        return await self._fetch(f"/surah/books/{surah}")

    def get_surah_books_sync(self, surah: int) -> Dict:
        """Synchronous version of get_surah_books."""
        return self._fetch_sync(f"/surah/books/{surah}")

    async def get_surah_fatwas(self, surah: int) -> Dict:
        """Get fatwas related to a surah."""
        return await self._fetch(f"/surah/fatwas/{surah}")

    def get_surah_fatwas_sync(self, surah: int) -> Dict:
        """Synchronous version of get_surah_fatwas."""
        return self._fetch_sync(f"/surah/fatwas/{surah}")

    async def get_surah_tafsirs(self, surah: int) -> Dict:
        """Get available tafsirs for a surah."""
        return await self._fetch(f"/surah/tafsirs/{surah}")

    def get_surah_tafsirs_sync(self, surah: int) -> Dict:
        """Synchronous version of get_surah_tafsirs."""
        return self._fetch_sync(f"/surah/tafsirs/{surah}")

    # ==========================================================================
    # الترجمات الإضافية (Additional Translations)
    # ==========================================================================

    async def get_translation_books(self, language_code: str = None) -> Dict:
        """Get translation books, optionally filtered by language."""
        endpoint = f"/translation/books/{language_code}" if language_code else "/translation/books"
        return await self._fetch(endpoint)

    def get_translation_books_sync(self, language_code: str = None) -> Dict:
        """Synchronous version of get_translation_books."""
        endpoint = f"/translation/books/{language_code}" if language_code else "/translation/books"
        return self._fetch_sync(endpoint)

    async def get_translation_from_book(self, book_id: int, surah: int, ayah: int = None) -> Dict:
        """Get translation from a specific book."""
        endpoint = f"/translation/{book_id}/{surah}"
        if ayah:
            endpoint += f"/{ayah}"
        return await self._fetch(endpoint)

    def get_translation_from_book_sync(self, book_id: int, surah: int, ayah: int = None) -> Dict:
        """Synchronous version of get_translation_from_book."""
        endpoint = f"/translation/{book_id}/{surah}"
        if ayah:
            endpoint += f"/{ayah}"
        return self._fetch_sync(endpoint)

    async def get_verse_in_book(self, surah: int, ayah: int, book_id: int) -> Dict:
        """Get verse content from a particular book."""
        return await self._fetch(f"/ayah/{surah}/{ayah}/book/{book_id}")

    def get_verse_in_book_sync(self, surah: int, ayah: int, book_id: int) -> Dict:
        """Synchronous version of get_verse_in_book."""
        return self._fetch_sync(f"/ayah/{surah}/{ayah}/book/{book_id}")

    def get_available_languages_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_available_languages."""
        return self._fetch_sync(f"/translations/available-languages/{surah}/{ayah}")

    # ==========================================================================
    # الملاحظات للآية (Notes for Verse)
    # ==========================================================================

    async def get_ayah_notes(self, surah: int, ayah: int) -> Dict:
        """Get scholarly notes for a specific ayah."""
        return await self._fetch(f"/ayah/{surah}/{ayah}/notes")

    def get_ayah_notes_sync(self, surah: int, ayah: int) -> Dict:
        """Synchronous version of get_ayah_notes."""
        return self._fetch_sync(f"/ayah/{surah}/{ayah}/notes")

    # ==========================================================================
    # Cache Management
    # ==========================================================================

    def clear_cache(self, verse_key: str = None, data_type: str = None):
        """Clear cached data."""
        with self._get_db() as conn:
            cursor = conn.cursor()
            if verse_key and data_type:
                cursor.execute("""
                    DELETE FROM quranpedia_cache
                    WHERE verse_key = ? AND data_type = ?
                """, (verse_key, data_type))
            elif verse_key:
                cursor.execute("""
                    DELETE FROM quranpedia_cache WHERE verse_key = ?
                """, (verse_key,))
            elif data_type:
                cursor.execute("""
                    DELETE FROM quranpedia_cache WHERE data_type = ?
                """, (data_type,))
            else:
                cursor.execute("DELETE FROM quranpedia_cache")
                cursor.execute("DELETE FROM quranpedia_surah_cache")
            conn.commit()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        with self._get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM quranpedia_cache")
            total_entries = cursor.fetchone()[0]

            cursor.execute("""
                SELECT data_type, COUNT(*) as count
                FROM quranpedia_cache
                GROUP BY data_type
            """)
            by_type = {row['data_type']: row['count'] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM quranpedia_surah_cache")
            surah_entries = cursor.fetchone()[0]

            return {
                "total_cached_verses": total_entries,
                "by_type": by_type,
                "cached_surahs": surah_entries
            }


# Singleton instance
_quranpedia_service: Optional[QuranpediaService] = None


def get_quranpedia_service() -> QuranpediaService:
    """Get or create singleton QuranpediaService instance."""
    global _quranpedia_service
    if _quranpedia_service is None:
        _quranpedia_service = QuranpediaService()
    return _quranpedia_service
