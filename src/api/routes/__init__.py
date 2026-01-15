"""
API Routes
"""
from .quran import router as quran_router
from .tafsir import router as tafsir_router
from .qiraat import router as qiraat_router
from .qiraat_search import router as qiraat_search_router
from .qiraat_export import router as qiraat_export_router
from .qiraat_audio import router as qiraat_audio_router
from .asbab import router as asbab_router
from .earab import router as earab_router
from .ai import router as ai_router
from .mutashabihat import router as mutashabihat_router

__all__ = [
    'quran_router',
    'tafsir_router',
    'qiraat_router',
    'qiraat_search_router',
    'qiraat_export_router',
    'qiraat_audio_router',
    'asbab_router',
    'earab_router',
    'ai_router',
    'mutashabihat_router'
]
