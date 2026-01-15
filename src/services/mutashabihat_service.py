"""
Local Mutashabihat Service - خدمة المتشابهات المحلية
Uses the Waqar144 dataset for accurate mutashabihat data
"""

import json
import sqlite3
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Data paths
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "mutashabihat"
WAQAR_DATA_PATH = DATA_DIR / "mutashabihat_waqar.json"
DB_PATH = Path(__file__).parent.parent.parent / "db" / "uloom_quran.db"


class MutashabihatService:
    """Service for managing and querying local mutashabihat data."""

    def __init__(self):
        self._data: Optional[Dict] = None
        self._verse_cache: Dict[int, Dict] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load the Waqar144 mutashabihat JSON data."""
        try:
            if WAQAR_DATA_PATH.exists():
                with open(WAQAR_DATA_PATH, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                logger.info(f"Loaded mutashabihat data from {WAQAR_DATA_PATH}")
            else:
                logger.warning(f"Mutashabihat data file not found: {WAQAR_DATA_PATH}")
                self._data = {}
        except Exception as e:
            logger.error(f"Error loading mutashabihat data: {e}")
            self._data = {}

    def _get_verse_by_absolute_id(self, absolute_id: int) -> Optional[Dict]:
        """Get verse details by absolute ID (1-6236)."""
        if absolute_id in self._verse_cache:
            return self._verse_cache[absolute_id]

        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT v.*, s.name_arabic as surah_name_ar,
                       s.name_english as surah_name_en
                FROM verses v
                JOIN surahs s ON v.surah_id = s.id
                WHERE v.id = ?
            """, (absolute_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                verse = dict(row)
                self._verse_cache[absolute_id] = verse
                return verse
            return None
        except Exception as e:
            logger.error(f"Error getting verse by absolute ID {absolute_id}: {e}")
            return None

    def _get_absolute_id_by_verse_key(self, verse_key: str) -> Optional[int]:
        """Convert verse_key (e.g., '2:14') to absolute ID."""
        try:
            parts = verse_key.split(":")
            if len(parts) != 2:
                return None

            surah_id = int(parts[0])
            ayah_number = int(parts[1])

            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id FROM verses WHERE surah_id = ? AND ayah_number = ?
            """, (surah_id, ayah_number))

            row = cursor.fetchone()
            conn.close()

            return row[0] if row else None
        except Exception as e:
            logger.error(f"Error converting verse_key {verse_key} to absolute ID: {e}")
            return None

    def get_mutashabihat(self, verse_key: str) -> Dict[str, Any]:
        """
        Get mutashabihat for a verse using the Waqar144 dataset.

        Args:
            verse_key: Verse key in format 'surah:ayah' (e.g., '2:14')

        Returns:
            Dictionary with source verse and similar verses
        """
        if not self._data:
            return {"success": False, "error": "Mutashabihat data not loaded"}

        try:
            parts = verse_key.split(":")
            if len(parts) != 2:
                return {"success": False, "error": "Invalid verse_key format"}

            surah_id = int(parts[0])
            ayah_number = int(parts[1])

            # Get absolute ID for the source verse
            source_absolute_id = self._get_absolute_id_by_verse_key(verse_key)
            if not source_absolute_id:
                return {"success": False, "error": f"Verse {verse_key} not found"}

            # Get source verse details
            source_verse = self._get_verse_by_absolute_id(source_absolute_id)
            if not source_verse:
                return {"success": False, "error": f"Verse {verse_key} not found in database"}

            # Search for mutashabihat in Waqar data
            # The data is organized by surah number, then by items with src.ayah
            surah_str = str(surah_id)
            similar_verses = []

            if surah_str in self._data:
                surah_mutashabihat = self._data[surah_str]

                for item in surah_mutashabihat:
                    if item.get("src", {}).get("ayah") == source_absolute_id:
                        # Found mutashabihat for this verse
                        for mut in item.get("muts", []):
                            mut_absolute_id = mut.get("ayah")
                            if mut_absolute_id:
                                mut_verse = self._get_verse_by_absolute_id(mut_absolute_id)
                                if mut_verse:
                                    similar_verses.append({
                                        "verse_key": mut_verse.get("verse_key"),
                                        "text_uthmani": mut_verse.get("text_uthmani", ""),
                                        "text_imlaei": mut_verse.get("text_imlaei", ""),
                                        "surah_name_ar": mut_verse.get("surah_name_ar", ""),
                                        "surah_name_en": mut_verse.get("surah_name_en", ""),
                                        "surah_id": mut_verse.get("surah_id"),
                                        "ayah_number": mut_verse.get("ayah_number"),
                                        "page_number": mut_verse.get("page_number"),
                                        "juz_number": mut_verse.get("juz_number")
                                    })
                        break

            # Also check if this verse appears as a mutashabih in other verses
            reverse_similar = self._find_reverse_mutashabihat(source_absolute_id)

            # Merge and deduplicate
            all_similar = similar_verses + reverse_similar
            seen_keys = set()
            unique_similar = []
            for v in all_similar:
                if v["verse_key"] not in seen_keys and v["verse_key"] != verse_key:
                    seen_keys.add(v["verse_key"])
                    unique_similar.append(v)

            return {
                "success": True,
                "verse_key": verse_key,
                "source_verse": {
                    "verse_key": source_verse.get("verse_key"),
                    "text_uthmani": source_verse.get("text_uthmani", ""),
                    "text_imlaei": source_verse.get("text_imlaei", ""),
                    "surah_name_ar": source_verse.get("surah_name_ar", ""),
                    "surah_name_en": source_verse.get("surah_name_en", ""),
                    "surah_id": source_verse.get("surah_id"),
                    "ayah_number": source_verse.get("ayah_number"),
                    "page_number": source_verse.get("page_number"),
                    "juz_number": source_verse.get("juz_number")
                },
                "similar_verses": unique_similar,
                "total_count": len(unique_similar),
                "source": "waqar144"
            }

        except Exception as e:
            logger.error(f"Error getting mutashabihat for {verse_key}: {e}")
            return {"success": False, "error": str(e)}

    def _find_reverse_mutashabihat(self, target_absolute_id: int) -> List[Dict]:
        """Find verses that have this verse as their mutashabih."""
        reverse_similar = []

        if not self._data:
            return reverse_similar

        try:
            for surah_num, surah_items in self._data.items():
                for item in surah_items:
                    # Check if target verse is in the muts list
                    for mut in item.get("muts", []):
                        if mut.get("ayah") == target_absolute_id:
                            # Found! The source of this item is a reverse mutashabih
                            src_absolute_id = item.get("src", {}).get("ayah")
                            if src_absolute_id:
                                src_verse = self._get_verse_by_absolute_id(src_absolute_id)
                                if src_verse:
                                    reverse_similar.append({
                                        "verse_key": src_verse.get("verse_key"),
                                        "text_uthmani": src_verse.get("text_uthmani", ""),
                                        "text_imlaei": src_verse.get("text_imlaei", ""),
                                        "surah_name_ar": src_verse.get("surah_name_ar", ""),
                                        "surah_name_en": src_verse.get("surah_name_en", ""),
                                        "surah_id": src_verse.get("surah_id"),
                                        "ayah_number": src_verse.get("ayah_number"),
                                        "page_number": src_verse.get("page_number"),
                                        "juz_number": src_verse.get("juz_number")
                                    })
                            break
        except Exception as e:
            logger.error(f"Error in reverse mutashabihat search: {e}")

        return reverse_similar

    def get_surah_mutashabihat(self, surah_id: int) -> Dict[str, Any]:
        """
        Get all mutashabihat in a surah.

        Args:
            surah_id: Surah number (1-114)

        Returns:
            Dictionary with all verses in the surah that have mutashabihat
        """
        if not self._data:
            return {"success": False, "error": "Mutashabihat data not loaded"}

        try:
            surah_str = str(surah_id)

            if surah_str not in self._data:
                return {
                    "success": True,
                    "surah_id": surah_id,
                    "verses_with_mutashabihat": [],
                    "total_count": 0,
                    "source": "waqar144"
                }

            surah_mutashabihat = self._data[surah_str]
            verses_with_mutashabihat = []

            for item in surah_mutashabihat:
                src_absolute_id = item.get("src", {}).get("ayah")
                if src_absolute_id:
                    src_verse = self._get_verse_by_absolute_id(src_absolute_id)
                    if src_verse:
                        similar_count = len(item.get("muts", []))
                        similar_verses = []

                        for mut in item.get("muts", []):
                            mut_absolute_id = mut.get("ayah")
                            if mut_absolute_id:
                                mut_verse = self._get_verse_by_absolute_id(mut_absolute_id)
                                if mut_verse:
                                    similar_verses.append({
                                        "verse_key": mut_verse.get("verse_key"),
                                        "text_uthmani": mut_verse.get("text_uthmani", "")[:100] + "..."
                                    })

                        verses_with_mutashabihat.append({
                            "verse_key": src_verse.get("verse_key"),
                            "ayah_number": src_verse.get("ayah_number"),
                            "text_uthmani": src_verse.get("text_uthmani", "")[:100] + "...",
                            "similar_count": similar_count,
                            "similar_verses": similar_verses
                        })

            return {
                "success": True,
                "surah_id": surah_id,
                "verses_with_mutashabihat": verses_with_mutashabihat,
                "total_count": len(verses_with_mutashabihat),
                "source": "waqar144"
            }

        except Exception as e:
            logger.error(f"Error getting surah mutashabihat for {surah_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the mutashabihat data."""
        if not self._data:
            return {"loaded": False, "error": "Data not loaded"}

        total_items = 0
        total_similar_pairs = 0
        surahs_with_data = 0

        for surah_num, items in self._data.items():
            if items:
                surahs_with_data += 1
                total_items += len(items)
                for item in items:
                    total_similar_pairs += len(item.get("muts", []))

        return {
            "loaded": True,
            "surahs_with_data": surahs_with_data,
            "total_verse_groups": total_items,
            "total_similar_pairs": total_similar_pairs,
            "cache_size": len(self._verse_cache),
            "source": "waqar144"
        }

    def clear_cache(self) -> None:
        """Clear the verse cache."""
        self._verse_cache.clear()

    def reload_data(self) -> bool:
        """Reload the mutashabihat data from disk."""
        self._verse_cache.clear()
        self._load_data()
        return bool(self._data)


# Singleton instance
_mutashabihat_service: Optional[MutashabihatService] = None


def get_mutashabihat_service() -> MutashabihatService:
    """Get the singleton mutashabihat service instance."""
    global _mutashabihat_service
    if _mutashabihat_service is None:
        _mutashabihat_service = MutashabihatService()
    return _mutashabihat_service
