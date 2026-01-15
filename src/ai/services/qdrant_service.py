"""
Qdrant Vector Database Service
Manages collections and search operations for Quranic data
"""

import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
    SearchRequest
)
from ..config import qdrant_config, azure_config

logger = logging.getLogger(__name__)


class QdrantService:
    """
    Service for managing Qdrant vector database operations.
    Handles collections for Quran verses, tafsir, qiraat, and asbab al-nuzul.
    Supports both local (host/port) and remote (URL) connections for GKE deployment.
    """

    def __init__(self, host: str = None, port: int = None, url: str = None):
        # Support URL-based connection for GKE/cloud deployment
        qdrant_url = url or qdrant_config.url
        qdrant_api_key = qdrant_config.api_key

        if qdrant_url:
            # Use URL-based connection (for GKE/cloud)
            logger.info(f"Connecting to Qdrant via URL: {qdrant_url}")
            self.client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key if qdrant_api_key else None,
                timeout=30,
                prefer_grpc=False  # Use REST API for Cloud Run compatibility
            )
            self.host = qdrant_url
            self.port = None
        else:
            # Use host/port connection (for local development)
            self.host = host or qdrant_config.host
            self.port = port or qdrant_config.port
            logger.info(f"Connecting to Qdrant via host: {self.host}:{self.port}")
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                check_compatibility=False
            )

        self.vector_size = azure_config.embedding_dimensions

    def initialize_collections(self):
        """
        Initialize all required collections for the platform.
        Creates collections if they don't exist.
        """
        collections = [
            {
                "name": qdrant_config.verses_collection,
                "description": "Quran verses with embeddings"
            },
            {
                "name": qdrant_config.tafsir_collection,
                "description": "Tafsir texts with embeddings"
            },
            {
                "name": qdrant_config.qiraat_collection,
                "description": "Qiraat differences with embeddings"
            },
            {
                "name": qdrant_config.asbab_collection,
                "description": "Asbab al-Nuzul with embeddings"
            }
        ]

        for col in collections:
            self._create_collection_if_not_exists(col["name"])
            logger.info(f"Collection '{col['name']}' ready")

    def _create_collection_if_not_exists(self, collection_name: str):
        """Create a collection if it doesn't exist."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)

            if not exists:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {collection_name}")
            else:
                logger.info(f"Collection already exists: {collection_name}")

        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}")
            raise

    def upsert_points(
        self,
        collection_name: str,
        points: List[Dict[str, Any]]
    ) -> bool:
        """
        Insert or update points in a collection.

        Args:
            collection_name: Name of the collection
            points: List of dicts with 'id', 'vector', and 'payload'

        Returns:
            True if successful
        """
        try:
            point_structs = [
                PointStruct(
                    id=p['id'],
                    vector=p['vector'],
                    payload=p['payload']
                )
                for p in points
            ]

            self.client.upsert(
                collection_name=collection_name,
                points=point_structs
            )
            return True

        except Exception as e:
            logger.error(f"Error upserting points: {e}")
            raise

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = None,
        score_threshold: float = None,
        filter_conditions: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in a collection.

        Args:
            collection_name: Name of the collection to search
            query_vector: Query embedding vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Optional filter conditions

        Returns:
            List of search results with scores and payloads
        """
        limit = limit or qdrant_config.default_limit
        score_threshold = score_threshold or qdrant_config.score_threshold

        # Build filter if conditions provided
        search_filter = None
        if filter_conditions:
            search_filter = self._build_filter(filter_conditions)

        try:
            # Use HTTP API directly for Cloud Run compatibility
            import httpx
            qdrant_url = self.host if self.host.startswith('http') else f"http://{self.host}:{self.port}"

            search_body = {
                "vector": query_vector,
                "limit": limit,
                "with_payload": True
            }
            if score_threshold:
                search_body["score_threshold"] = score_threshold

            with httpx.Client(timeout=30.0) as http_client:
                resp = http_client.post(
                    f"{qdrant_url}/collections/{collection_name}/points/search",
                    json=search_body
                )
                if resp.status_code != 200:
                    logger.error(f"Qdrant search error: {resp.status_code} - {resp.text}")
                    return []

                data = resp.json()
                return [
                    {
                        "id": r["id"],
                        "score": r["score"],
                        "payload": r.get("payload", {})
                    }
                    for r in data.get("result", [])
                ]

        except Exception as e:
            logger.error(f"Error searching collection {collection_name}: {e}")
            raise

    def search_verses(
        self,
        query_vector: List[float],
        limit: int = 10,
        surah_id: int = None,
        riwaya_code: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar Quran verses.

        Args:
            query_vector: Query embedding
            limit: Max results
            surah_id: Filter by surah
            riwaya_code: Filter by qiraat/riwaya

        Returns:
            List of matching verses with scores
        """
        filter_conditions = {}
        if surah_id:
            filter_conditions['surah_id'] = surah_id
        if riwaya_code:
            filter_conditions['riwaya_code'] = riwaya_code

        return self.search(
            collection_name=qdrant_config.verses_collection,
            query_vector=query_vector,
            limit=limit,
            filter_conditions=filter_conditions if filter_conditions else None
        )

    def search_tafsir(
        self,
        query_vector: List[float],
        limit: int = 5,
        tafsir_id: int = None,
        verse_key: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant tafsir content.

        Args:
            query_vector: Query embedding
            limit: Max results
            tafsir_id: Filter by specific tafsir
            verse_key: Filter by verse (e.g., "1:1")

        Returns:
            List of matching tafsir content
        """
        filter_conditions = {}
        if tafsir_id:
            filter_conditions['tafsir_id'] = tafsir_id
        if verse_key:
            filter_conditions['verse_key'] = verse_key

        return self.search(
            collection_name=qdrant_config.tafsir_collection,
            query_vector=query_vector,
            limit=limit,
            filter_conditions=filter_conditions if filter_conditions else None
        )

    def search_qiraat(
        self,
        query_vector: List[float],
        limit: int = 10,
        surah_id: int = None
    ) -> List[Dict[str, Any]]:
        """Search for qiraat differences."""
        filter_conditions = {}
        if surah_id:
            filter_conditions['surah_id'] = surah_id

        return self.search(
            collection_name=qdrant_config.qiraat_collection,
            query_vector=query_vector,
            limit=limit,
            filter_conditions=filter_conditions if filter_conditions else None
        )

    def search_asbab(
        self,
        query_vector: List[float],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for asbab al-nuzul."""
        return self.search(
            collection_name=qdrant_config.asbab_collection,
            query_vector=query_vector,
            limit=limit
        )

    def _build_filter(self, conditions: Dict[str, Any]) -> Filter:
        """Build Qdrant filter from conditions dictionary."""
        must_conditions = []

        for key, value in conditions.items():
            if isinstance(value, (int, str, bool)):
                must_conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            elif isinstance(value, dict) and 'range' in value:
                must_conditions.append(
                    FieldCondition(
                        key=key,
                        range=Range(**value['range'])
                    )
                )

        return Filter(must=must_conditions) if must_conditions else None

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection."""
        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "points_count": getattr(info, 'points_count', 0) or 0,
                "vectors_count": getattr(info, 'vectors_count', getattr(info, 'points_count', 0)) or 0,
                "status": str(getattr(info, 'status', 'unknown'))
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {"error": str(e)}

    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False

    def get_all_collections_stats(self) -> Dict[str, Any]:
        """Get stats for all collections."""
        stats = {}
        for col_name in [
            qdrant_config.verses_collection,
            qdrant_config.tafsir_collection,
            qdrant_config.qiraat_collection,
            qdrant_config.asbab_collection
        ]:
            stats[col_name] = self.get_collection_info(col_name)
        return stats


# Singleton instance
_qdrant_service: Optional[QdrantService] = None


def get_qdrant_service() -> QdrantService:
    """Get or create singleton QdrantService instance."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service
