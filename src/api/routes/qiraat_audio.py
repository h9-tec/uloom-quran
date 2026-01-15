"""
Qiraat Audio API routes - صوتيات القراءات
API endpoints for Quranic recitations audio by different reciters and riwayat
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from ..database import get_db, dict_from_row

router = APIRouter(prefix="/api/qiraat/audio", tags=["Qiraat Audio"])


# ============================================================================
# Helper Functions
# ============================================================================

def normalize_riwaya_code(code: str) -> str:
    """
    Normalize riwaya codes to match frontend expectations.
    Database uses: shouba, qumbul
    Frontend uses: shuba, qunbul
    """
    code_map = {
        'shouba': 'shuba',
        'qumbul': 'qunbul',
    }
    return code_map.get(code, code)


def build_audio_url(base_url: str, pattern: str, surah_id: int, ayah_number: Optional[int] = None) -> str:
    """
    Build audio URL from base URL and pattern.

    Pattern placeholders supported:
    - {surah}, {surah_id}: Surah number (1-114)
    - {surah_padded}, {surah_number_3digit}, {surah_3digit}: 3-digit padded (001-114)
    - {ayah}, {ayah_number}: Ayah number
    - {ayah_padded}, {ayah_3digit}: 3-digit padded ayah
    """
    # Handle patterns that include base_url placeholder
    if '{audio_base_url}' in pattern:
        url = pattern.replace('{audio_base_url}', base_url.rstrip('/'))
    elif '{download_base}' in pattern:
        # Extract base and path for quranicaudio patterns
        url = pattern.replace('{download_base}', base_url.rstrip('/'))
        url = url.replace('{reciter_path}', '')
        url = url.replace('{reciter_folder}', '')
    else:
        url = f"{base_url.rstrip('/')}/{pattern}"

    # Replace surah placeholders
    surah_3digit = str(surah_id).zfill(3)
    url = url.replace("{surah}", str(surah_id))
    url = url.replace("{surah_id}", str(surah_id))
    url = url.replace("{surah_padded}", surah_3digit)
    url = url.replace("{surah_number_3digit}", surah_3digit)
    url = url.replace("{surah_3digit}", surah_3digit)

    # Replace ayah placeholders if provided
    if ayah_number is not None:
        ayah_3digit = str(ayah_number).zfill(3)
        url = url.replace("{ayah}", str(ayah_number))
        url = url.replace("{ayah_number}", str(ayah_number))
        url = url.replace("{ayah_padded}", ayah_3digit)
        url = url.replace("{ayah_3digit}", ayah_3digit)

    # Clean up double slashes (except after protocol)
    url = url.replace('://', '::PROTOCOL::')
    while '//' in url:
        url = url.replace('//', '/')
    url = url.replace('::PROTOCOL::', '://')

    return url


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/reciters")
def get_all_reciters():
    """
    Get all audio reciters grouped by riwaya (GET /api/qiraat/audio/reciters)

    Returns a list of all available reciters organized by their riwaya (transmission chain).
    Each reciter includes their audio base URL and URL pattern for constructing audio URLs.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get all riwayat with their reciters
        cursor.execute("""
            SELECT r.id, r.code, r.name_arabic, r.name_english
            FROM riwayat r
            WHERE r.code IN ('hafs', 'warsh', 'qaloon', 'shouba', 'doori', 'soosi', 'bazzi', 'qumbul')
            ORDER BY r.id
        """)
        riwayat = [dict_from_row(row) for row in cursor.fetchall()]

        result = []
        for riwaya in riwayat:
            # Get reciters for this riwaya
            cursor.execute("""
                SELECT id, name_arabic, name_english, audio_base_url, url_pattern, has_verse_audio
                FROM qiraat_audio_reciters
                WHERE riwaya_id = ?
                ORDER BY name_english
            """, (riwaya['id'],))

            reciters = [dict_from_row(row) for row in cursor.fetchall()]

            result.append({
                "riwaya": riwaya,
                "reciters": reciters,
                "reciter_count": len(reciters)
            })

        # Calculate totals
        total_reciters = sum(r['reciter_count'] for r in result)

        return {
            "riwayat": result,
            "total_riwayat": len(result),
            "total_reciters": total_reciters
        }


@router.get("/riwaya/{code}")
def get_reciters_by_riwaya(code: str):
    """
    Get reciters for a specific riwaya (GET /api/qiraat/audio/riwaya/{code})

    Returns all audio reciters available for a specific riwaya identified by its code.
    Valid codes: hafs, warsh, qaloon, shouba, doori, soosi, bazzi, qumbul

    Parameters:
    - code: The riwaya code (e.g., 'hafs', 'warsh')
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get riwaya info
        cursor.execute("""
            SELECT id, code, name_arabic, name_english, description
            FROM riwayat
            WHERE code = ?
        """, (code,))
        riwaya = cursor.fetchone()

        if not riwaya:
            valid_codes = ['hafs', 'warsh', 'qaloon', 'shouba', 'doori', 'soosi', 'bazzi', 'qumbul']
            raise HTTPException(
                status_code=404,
                detail=f"Riwaya '{code}' not found. Valid codes: {', '.join(valid_codes)}"
            )

        riwaya_data = dict_from_row(riwaya)

        # Get reciters for this riwaya
        cursor.execute("""
            SELECT id, name_arabic, name_english, audio_base_url, url_pattern, has_verse_audio
            FROM qiraat_audio_reciters
            WHERE riwaya_id = ?
            ORDER BY name_english
        """, (riwaya_data['id'],))

        reciters = [dict_from_row(row) for row in cursor.fetchall()]

        return {
            "riwaya": riwaya_data,
            "reciters": reciters,
            "reciter_count": len(reciters)
        }


@router.get("/surah/{surah_id}")
def get_surah_audio(surah_id: int):
    """
    Get audio URLs for a surah from all available riwayat (GET /api/qiraat/audio/surah/{surah_id})

    Returns audio URLs for the specified surah from all available reciters across different riwayat.

    Parameters:
    - surah_id: Surah number (1-114)
    """
    if surah_id < 1 or surah_id > 114:
        raise HTTPException(
            status_code=400,
            detail="Invalid surah_id. Must be between 1 and 114."
        )

    with get_db() as conn:
        cursor = conn.cursor()

        # Get surah info
        cursor.execute("""
            SELECT id, name_arabic, name_english, ayah_count, revelation_type
            FROM surahs
            WHERE id = ?
        """, (surah_id,))
        surah = cursor.fetchone()

        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        surah_data = dict_from_row(surah)

        # Get all reciters with their riwayat
        cursor.execute("""
            SELECT qar.id, qar.name_arabic, qar.name_english,
                   qar.audio_base_url, qar.url_pattern, qar.has_verse_audio,
                   r.id as riwaya_id, r.code as riwaya_code,
                   r.name_arabic as riwaya_name_arabic, r.name_english as riwaya_name_english
            FROM qiraat_audio_reciters qar
            JOIN riwayat r ON qar.riwaya_id = r.id
            ORDER BY r.id, qar.name_english
        """)

        audio_sources = []
        for row in cursor.fetchall():
            reciter = dict_from_row(row)

            # Build the audio URL for this surah
            audio_url = build_audio_url(
                reciter['audio_base_url'],
                reciter['url_pattern'],
                surah_id
            )

            audio_sources.append({
                "reciter": {
                    "id": reciter['id'],
                    "name_arabic": reciter['name_arabic'],
                    "name_english": reciter['name_english'],
                    "has_verse_audio": bool(reciter['has_verse_audio'])
                },
                "riwaya": {
                    "id": reciter['riwaya_id'],
                    "code": normalize_riwaya_code(reciter['riwaya_code']),
                    "name_arabic": reciter['riwaya_name_arabic'],
                    "name_english": reciter['riwaya_name_english']
                },
                "audio_url": audio_url
            })

        return {
            "surah": surah_data,
            "audio_sources": audio_sources,
            "total_sources": len(audio_sources)
        }


@router.get("/verse/{verse_key}")
def get_verse_audio(verse_key: str):
    """
    Get verse-level audio if available (GET /api/qiraat/audio/verse/{verse_key})

    Returns audio URLs for a specific verse from reciters that support verse-level audio.

    Parameters:
    - verse_key: Verse key in format 'surah:ayah' (e.g., '1:4', '2:255')
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

        # Verify verse exists
        cursor.execute("""
            SELECT v.id, v.verse_key, v.text_uthmani, v.surah_id, v.ayah_number,
                   s.name_arabic as surah_name, s.name_english as surah_name_english
            FROM verses v
            JOIN surahs s ON v.surah_id = s.id
            WHERE v.surah_id = ? AND v.ayah_number = ?
        """, (surah_id, ayah_number))
        verse = cursor.fetchone()

        if not verse:
            raise HTTPException(status_code=404, detail="Verse not found")

        verse_data = dict_from_row(verse)

        # Get reciters that support verse-level audio
        cursor.execute("""
            SELECT qar.id, qar.name_arabic, qar.name_english,
                   qar.audio_base_url, qar.url_pattern,
                   r.id as riwaya_id, r.code as riwaya_code,
                   r.name_arabic as riwaya_name_arabic, r.name_english as riwaya_name_english
            FROM qiraat_audio_reciters qar
            JOIN riwayat r ON qar.riwaya_id = r.id
            WHERE qar.has_verse_audio = 1
            ORDER BY r.id, qar.name_english
        """)

        audio_sources = []
        for row in cursor.fetchall():
            reciter = dict_from_row(row)

            # Build the audio URL for this verse
            audio_url = build_audio_url(
                reciter['audio_base_url'],
                reciter['url_pattern'],
                surah_id,
                ayah_number
            )

            audio_sources.append({
                "reciter": {
                    "id": reciter['id'],
                    "name_arabic": reciter['name_arabic'],
                    "name_english": reciter['name_english']
                },
                "riwaya": {
                    "id": reciter['riwaya_id'],
                    "code": normalize_riwaya_code(reciter['riwaya_code']),
                    "name_arabic": reciter['riwaya_name_arabic'],
                    "name_english": reciter['riwaya_name_english']
                },
                "audio_url": audio_url
            })

        # Also check the qiraat_audio table for pre-stored verse audio
        cursor.execute("""
            SELECT qa.id, qa.audio_url, qa.reciter_name, qa.duration_seconds, qa.source,
                   q.name_arabic as qari_name, r.name_arabic as rawi_name
            FROM qiraat_audio qa
            LEFT JOIN qurra q ON qa.qari_id = q.id
            LEFT JOIN ruwat r ON qa.rawi_id = r.id
            WHERE qa.verse_id = ?
        """, (verse_data['id'],))

        stored_audio = [dict_from_row(row) for row in cursor.fetchall()]

        return {
            "verse": verse_data,
            "audio_sources": audio_sources,
            "stored_audio": stored_audio,
            "total_sources": len(audio_sources),
            "total_stored": len(stored_audio),
            "has_verse_audio": len(audio_sources) > 0 or len(stored_audio) > 0
        }


@router.get("/reciter/{reciter_id}/surah/{surah_id}")
def get_reciter_surah_audio(reciter_id: int, surah_id: int):
    """
    Get specific reciter's audio for a surah (GET /api/qiraat/audio/reciter/{reciter_id}/surah/{surah_id})

    Returns the audio URL and detailed information for a specific reciter's recitation of a surah.
    If the reciter supports verse-level audio, individual verse URLs are also provided.

    Parameters:
    - reciter_id: The reciter's ID
    - surah_id: Surah number (1-114)
    """
    if surah_id < 1 or surah_id > 114:
        raise HTTPException(
            status_code=400,
            detail="Invalid surah_id. Must be between 1 and 114."
        )

    with get_db() as conn:
        cursor = conn.cursor()

        # Get reciter info
        cursor.execute("""
            SELECT qar.id, qar.name_arabic, qar.name_english,
                   qar.audio_base_url, qar.url_pattern, qar.has_verse_audio,
                   r.id as riwaya_id, r.code as riwaya_code,
                   r.name_arabic as riwaya_name_arabic, r.name_english as riwaya_name_english,
                   r.description as riwaya_description
            FROM qiraat_audio_reciters qar
            JOIN riwayat r ON qar.riwaya_id = r.id
            WHERE qar.id = ?
        """, (reciter_id,))
        reciter = cursor.fetchone()

        if not reciter:
            raise HTTPException(status_code=404, detail="Reciter not found")

        reciter_data = dict_from_row(reciter)

        # Get surah info
        cursor.execute("""
            SELECT id, name_arabic, name_english, ayah_count, revelation_type
            FROM surahs
            WHERE id = ?
        """, (surah_id,))
        surah = cursor.fetchone()

        if not surah:
            raise HTTPException(status_code=404, detail="Surah not found")

        surah_data = dict_from_row(surah)

        # Build surah audio URL
        surah_audio_url = build_audio_url(
            reciter_data['audio_base_url'],
            reciter_data['url_pattern'],
            surah_id
        )

        result = {
            "reciter": {
                "id": reciter_data['id'],
                "name_arabic": reciter_data['name_arabic'],
                "name_english": reciter_data['name_english'],
                "has_verse_audio": bool(reciter_data['has_verse_audio'])
            },
            "riwaya": {
                "id": reciter_data['riwaya_id'],
                "code": normalize_riwaya_code(reciter_data['riwaya_code']),
                "name_arabic": reciter_data['riwaya_name_arabic'],
                "name_english": reciter_data['riwaya_name_english'],
                "description": reciter_data['riwaya_description']
            },
            "surah": surah_data,
            "surah_audio_url": surah_audio_url
        }

        # If reciter supports verse-level audio, provide individual verse URLs
        if reciter_data['has_verse_audio']:
            verse_urls = []
            for ayah in range(1, surah_data['ayah_count'] + 1):
                verse_url = build_audio_url(
                    reciter_data['audio_base_url'],
                    reciter_data['url_pattern'],
                    surah_id,
                    ayah
                )
                verse_urls.append({
                    "ayah_number": ayah,
                    "verse_key": f"{surah_id}:{ayah}",
                    "audio_url": verse_url
                })
            result["verse_audio_urls"] = verse_urls
            result["total_verses"] = len(verse_urls)

        return result


# ============================================================================
# Admin/Management Endpoints
# ============================================================================

@router.get("/reciters/list")
def list_all_reciters(
    riwaya_code: Optional[str] = Query(default=None, description="Filter by riwaya code"),
    has_verse_audio: Optional[bool] = Query(default=None, description="Filter by verse audio support")
):
    """
    List all reciters with optional filters (GET /api/qiraat/audio/reciters/list)

    Returns a flat list of all reciters with optional filtering.

    Parameters:
    - riwaya_code: Filter by riwaya code (e.g., 'hafs', 'warsh')
    - has_verse_audio: Filter by verse audio support (true/false)
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT qar.id, qar.name_arabic, qar.name_english,
                   qar.audio_base_url, qar.url_pattern, qar.has_verse_audio,
                   r.id as riwaya_id, r.code as riwaya_code,
                   r.name_arabic as riwaya_name_arabic, r.name_english as riwaya_name_english
            FROM qiraat_audio_reciters qar
            JOIN riwayat r ON qar.riwaya_id = r.id
            WHERE 1=1
        """
        params = []

        if riwaya_code:
            query += " AND r.code = ?"
            params.append(riwaya_code)

        if has_verse_audio is not None:
            query += " AND qar.has_verse_audio = ?"
            params.append(1 if has_verse_audio else 0)

        query += " ORDER BY r.id, qar.name_english"

        cursor.execute(query, params)

        reciters = []
        for row in cursor.fetchall():
            reciter = dict_from_row(row)
            reciter['has_verse_audio'] = bool(reciter['has_verse_audio'])
            reciters.append(reciter)

        return {
            "reciters": reciters,
            "total": len(reciters),
            "filters": {
                "riwaya_code": riwaya_code,
                "has_verse_audio": has_verse_audio
            }
        }


@router.get("/stats")
def get_audio_stats():
    """
    Get statistics about available audio content (GET /api/qiraat/audio/stats)

    Returns statistics about the audio reciters and available content.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {}

        # Total reciters
        cursor.execute("SELECT COUNT(*) FROM qiraat_audio_reciters")
        stats['total_reciters'] = cursor.fetchone()[0]

        # Reciters with verse audio
        cursor.execute("SELECT COUNT(*) FROM qiraat_audio_reciters WHERE has_verse_audio = 1")
        stats['reciters_with_verse_audio'] = cursor.fetchone()[0]

        # Reciters by riwaya
        cursor.execute("""
            SELECT r.code, r.name_arabic, r.name_english, COUNT(qar.id) as reciter_count
            FROM riwayat r
            LEFT JOIN qiraat_audio_reciters qar ON r.id = qar.riwaya_id
            WHERE r.code IN ('hafs', 'warsh', 'qaloon', 'shouba', 'doori', 'soosi', 'bazzi', 'qumbul')
            GROUP BY r.id
            ORDER BY r.id
        """)
        stats['by_riwaya'] = [
            {
                "code": row[0],
                "name_arabic": row[1],
                "name_english": row[2],
                "reciter_count": row[3]
            }
            for row in cursor.fetchall()
        ]

        # Stored verse audio count
        cursor.execute("SELECT COUNT(*) FROM qiraat_audio")
        stats['stored_verse_audio_count'] = cursor.fetchone()[0]

        return stats
