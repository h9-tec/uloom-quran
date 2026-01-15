"""
Services module for علوم القرآن Platform
External API integrations and shared services
"""

from .quranpedia_service import QuranpediaService, get_quranpedia_service

__all__ = ['QuranpediaService', 'get_quranpedia_service']
