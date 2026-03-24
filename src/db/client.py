"""
Qdrant Vector Database Client
============================

Singleton client for managing Qdrant connections and collections.
"""

import uuid
import sys
from typing import List, Dict, Any, Optional
from loguru import logger
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CollectionInfo,
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    CreateAliasOperation,
    DeleteAliasOperation,
    ChangeAliasesOperation,
    SparseVector,
)

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings


class QdrantManager:
    """Singleton Qdrant client manager."""
    
    _instance: Optional["QdrantManager"] = None
    _client: Optional[QdrantClient] = None
    
    def __new__(cls) -> "QdrantManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def client(self) -> QdrantClient:
        """Get or create Qdrant client."""
        if self._client is None:
            self._client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                grpc_port=settings.qdrant_grpc_port,
                api_key=settings.qdrant_api_key,
                https=False,  # Use HTTP instead of HTTPS for local instance
                timeout=60,   # Increase timeout for large operations
            )
            logger.info(f"Connected to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}")
        return self._client
    
    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False
    
    def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: Distance = Distance.COSINE,
    ) -> bool:
        """Create a new collection with optimized settings."""
        try:
            if self.collection_exists(collection_name):
                logger.info(f"Collection '{collection_name}' already exists")
                return True
            
            # Hybrid-ready schema: named dense vector + named sparse vector.
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=vector_size,
                        distance=distance,
                    )
                },
                sparse_vectors_config={
                    "sparse": {},
                },
                optimizers_config={
                    "deleted_threshold": 0.2,
                    "vacuum_min_vector_number": 1000,
                    "default_segment_number": 2,
                },
                on_disk_payload=True,
            )
            
            logger.success(f"Created collection '{collection_name}' with {vector_size}D vectors")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            return False
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection (removes all vectors). Use with care."""
        try:
            if not self.collection_exists(collection_name):
                logger.info(f"Collection '{collection_name}' does not exist, nothing to delete")
                return True
            self.client.delete_collection(collection_name)
            logger.success(f"Deleted collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            return False
    
    def upsert_points(
        self,
        collection_name: str,
        points: List[PointStruct],
    ) -> bool:
        """Batch upsert points to collection."""
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info(f"Upserted {len(points)} points to '{collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upsert points to '{collection_name}': {e}")
            return False
    
    def search_similar(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors with optional metadata filtering."""
        try:
            # Build filter if metadata provided
            search_filter = None
            if metadata_filter:
                conditions = []
                for key, value in metadata_filter.items():
                    if isinstance(value, dict):
                        # Handle range queries like {"lt": 5000}
                        for op, val in value.items():
                            if op == "lt":
                                conditions.append(
                                    FieldCondition(key=key, range={"lt": val})
                                )
                            elif op == "gt":
                                conditions.append(
                                    FieldCondition(key=key, range={"gt": val})
                                )
                            elif op == "gte":
                                conditions.append(
                                    FieldCondition(key=key, range={"gte": val})
                                )
                            elif op == "lte":
                                conditions.append(
                                    FieldCondition(key=key, range={"lte": val})
                                )
                    else:
                        # Exact match
                        conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=value))
                        )
                
                if conditions:
                    search_filter = Filter(must=conditions)
            
            # Perform search using query method (new Qdrant API)
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                using="dense",
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
            )
            
            # Format results - query_points returns different structure
            if hasattr(results, 'points'):
                search_results = results.points
            else:
                search_results = results
                
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed in '{collection_name}': {e}")
            return []

    def search_hybrid(
        self,
        collection_name: str,
        dense_query_vector: List[float],
        sparse_query_vector: Dict[str, List[float]],
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
        alpha: float = 0.7,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval by combining dense and sparse searches.
        Uses weighted score fusion:
            final = alpha * dense_score + (1 - alpha) * sparse_score
        """
        try:
            alpha = max(0.0, min(1.0, float(alpha)))
            search_filter = None
            if metadata_filter:
                conditions = []
                for key, value in metadata_filter.items():
                    if isinstance(value, dict):
                        for op, val in value.items():
                            if op == "lt":
                                conditions.append(FieldCondition(key=key, range={"lt": val}))
                            elif op == "gt":
                                conditions.append(FieldCondition(key=key, range={"gt": val}))
                            elif op == "gte":
                                conditions.append(FieldCondition(key=key, range={"gte": val}))
                            elif op == "lte":
                                conditions.append(FieldCondition(key=key, range={"lte": val}))
                    else:
                        conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                if conditions:
                    search_filter = Filter(must=conditions)

            dense_result = self.client.query_points(
                collection_name=collection_name,
                query=dense_query_vector,
                using="dense",
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
            )
            sparse_result = self.client.query_points(
                collection_name=collection_name,
                query=SparseVector(
                    indices=sparse_query_vector.get("indices", []),
                    values=sparse_query_vector.get("values", []),
                ),
                using="sparse",
                query_filter=search_filter,
                limit=limit,
            )

            dense_points = dense_result.points if hasattr(dense_result, "points") else dense_result
            sparse_points = sparse_result.points if hasattr(sparse_result, "points") else sparse_result

            fused: Dict[str, Dict[str, Any]] = {}
            for point in dense_points:
                pid = str(getattr(point, "id", ""))
                if not pid:
                    continue
                fused[pid] = {
                    "id": pid,
                    "payload": getattr(point, "payload", {}) or {},
                    "dense_score": float(getattr(point, "score", 0.0)),
                    "sparse_score": 0.0,
                }
            for point in sparse_points:
                pid = str(getattr(point, "id", ""))
                if not pid:
                    continue
                existing = fused.get(
                    pid,
                    {
                        "id": pid,
                        "payload": getattr(point, "payload", {}) or {},
                        "dense_score": 0.0,
                        "sparse_score": 0.0,
                    },
                )
                existing["sparse_score"] = float(getattr(point, "score", 0.0))
                if not existing.get("payload"):
                    existing["payload"] = getattr(point, "payload", {}) or {}
                fused[pid] = existing

            rows: List[Dict[str, Any]] = []
            for item in fused.values():
                final_score = (alpha * item["dense_score"]) + ((1.0 - alpha) * item["sparse_score"])
                item["score"] = final_score
                rows.append(item)

            rows.sort(key=lambda row: float(row.get("score", 0.0)), reverse=True)
            return rows[:limit]
        except Exception as e:
            logger.error(f"Hybrid search failed in '{collection_name}': {e}")
            return []

    def resolve_collection_name(self, preferred: Optional[str] = None) -> str:
        """Resolve active collection name with alias fallback."""
        candidate = preferred or settings.qdrant_collection_alias
        try:
            self.client.get_collection(candidate)
            return candidate
        except Exception:
            return settings.qdrant_collection_name

    def ensure_alias(self, alias_name: str, collection_name: str) -> bool:
        """Ensure alias points to collection (idempotent)."""
        try:
            self.client.update_collection_aliases(
                change_aliases_operations=[
                    CreateAliasOperation(create_alias={"collection_name": collection_name, "alias_name": alias_name})
                ]
            )
            logger.success(f"Alias '{alias_name}' now points to '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure alias '{alias_name}': {e}")
            return False

    def switch_alias_atomically(self, alias_name: str, new_collection_name: str) -> bool:
        """Switch alias to a new collection atomically."""
        try:
            operations = [
                DeleteAliasOperation(delete_alias={"alias_name": alias_name}),
                CreateAliasOperation(
                    create_alias={"collection_name": new_collection_name, "alias_name": alias_name}
                ),
            ]
            self.client.update_collection_aliases(
                change_aliases_operations=[ChangeAliasesOperation(operations=operations)]
            )
            logger.success(f"Atomically switched alias '{alias_name}' -> '{new_collection_name}'")
            return True
        except Exception as e:
            logger.warning(f"Atomic alias switch failed, trying direct create/update: {e}")
            return self.ensure_alias(alias_name, new_collection_name)

    def build_versioned_collection_name(self, base_name: str, version_suffix: str) -> str:
        """Build deterministic collection version name."""
        return f"{base_name}_{version_suffix}".strip("_")
    
    def get_collection_info(self, collection_name: str) -> Optional[CollectionInfo]:
        """Get collection information."""
        try:
            return self.client.get_collection(collection_name)
        except Exception as e:
            logger.error(f"Failed to get collection info for '{collection_name}': {e}")
            return None

    def get_points_by_payload(
        self,
        collection_name: str,
        payload_filter: Dict[str, Any],
        limit: int = 10,
        with_vectors: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Busca puntos por filtro sobre el payload (ej: url exacto).
        Útil para verificar si una propiedad está en la base y ver sus datos guardados.
        """
        try:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in payload_filter.items()
            ]
            search_filter = Filter(must=conditions)
            results, _ = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=search_filter,
                limit=limit,
                with_payload=True,
                with_vectors=with_vectors,
            )
            return list(results) if results else []
        except Exception as e:
            logger.error(f"Scroll by payload failed in '{collection_name}': {e}")
            return []


# Global instance
qdrant = QdrantManager()