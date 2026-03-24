"""
Search pipeline with feature flags for staged rollout.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List

from config.settings import settings
from src.db.client import qdrant
from src.services.embedder import embedder
from src.services.reranker import reranker
from src.services.sparse_embedder import sparse_embedder


@dataclass
class SearchTelemetry:
    parse_ms: float = 0.0
    embed_ms: float = 0.0
    retrieval_ms: float = 0.0
    rerank_ms: float = 0.0
    total_ms: float = 0.0

    def as_dict(self) -> Dict[str, float]:
        return {
            "parse_ms": round(self.parse_ms, 2),
            "embed_ms": round(self.embed_ms, 2),
            "retrieval_ms": round(self.retrieval_ms, 2),
            "rerank_ms": round(self.rerank_ms, 2),
            "total_ms": round(self.total_ms, 2),
        }


class SearchPipeline:
    """Composable search pipeline used by CLI and Streamlit."""

    def _normalize_result(self, hit: Any) -> Dict[str, Any]:
        if hasattr(hit, "score"):
            dense_score = float(hit.score)
            payload = hit.payload if hasattr(hit, "payload") else {}
            return {"dense_score": dense_score, "score": dense_score, "payload": payload or {}}
        dense_score = float(hit.get("score", 0.0))
        return {"dense_score": dense_score, "score": dense_score, "payload": hit.get("payload", hit)}

    def _blend_score(self, dense_score: float, sparse_score: float, rerank_score: float) -> float:
        alpha = float(settings.hybrid_alpha)
        alpha = min(max(alpha, 0.0), 1.0)
        blended = dense_score
        if settings.enable_sparse_dense_hybrid:
            blended = (alpha * dense_score) + ((1.0 - alpha) * sparse_score)
        if settings.enable_cross_encoder_rerank:
            # Keep dense+sparse as anchor and add CE score as a calibrated bonus.
            blended = (0.7 * blended) + (0.3 * rerank_score)
        return blended

    def search(
        self,
        query: str,
        top_k_final: int | None = None,
        top_k_retrieval: int | None = None,
        score_threshold: float | None = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        telemetry = SearchTelemetry()

        parse_started = time.perf_counter()
        # Local import avoids circular dependency with scripts.semantic_search.search().
        from scripts.semantic_search import extract_filters
        query_clean, filters = extract_filters(query)
        telemetry.parse_ms = (time.perf_counter() - parse_started) * 1000

        embed_started = time.perf_counter()
        vector = embedder.embed_text(query_clean if query_clean else query)
        sparse_vector = sparse_embedder.embed_text(query_clean if query_clean else query)
        telemetry.embed_ms = (time.perf_counter() - embed_started) * 1000

        retrieval_limit = top_k_retrieval or settings.top_k_retrieval
        final_limit = top_k_final or settings.top_k_final
        threshold = settings.score_threshold if score_threshold is None else score_threshold

        retrieval_started = time.perf_counter()
        collection_name = qdrant.resolve_collection_name(settings.qdrant_collection_alias)
        if settings.enable_sparse_dense_hybrid:
            normalized = qdrant.search_hybrid(
                collection_name=collection_name,
                dense_query_vector=vector,
                sparse_query_vector=sparse_vector,
                limit=retrieval_limit if settings.enable_two_stage_ranking else final_limit,
                metadata_filter=filters if filters else None,
                alpha=settings.hybrid_alpha,
                score_threshold=threshold if threshold > 0 else None,
            )
        else:
            hits = qdrant.search_similar(
                collection_name=collection_name,
                query_vector=vector,
                limit=retrieval_limit if settings.enable_two_stage_ranking else final_limit,
                metadata_filter=filters if filters else None,
                score_threshold=threshold if threshold > 0 else None,
            )
            normalized = [self._normalize_result(hit) for hit in hits]
        telemetry.retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

        rerank_started = time.perf_counter()
        if settings.enable_two_stage_ranking:
            normalized = reranker.rerank(
                query=query_clean if query_clean else query,
                candidates=normalized,
                use_cross_encoder=settings.enable_cross_encoder_rerank,
                filters=filters,
            )
            for item in normalized:
                dense = float(item.get("dense_score", item.get("score", 0.0)))
                sparse = float(item.get("sparse_score", 0.0))
                ce = float(item.get("rerank_score", 0.0))
                final = self._blend_score(dense, sparse, ce)
                item["final_score"] = final
                item["score"] = final
            normalized = sorted(normalized, key=lambda item: float(item.get("score", 0.0)), reverse=True)
            normalized = normalized[:final_limit]
        telemetry.rerank_ms = (time.perf_counter() - rerank_started) * 1000
        telemetry.total_ms = (time.perf_counter() - started) * 1000

        return {
            "query": query,
            "query_clean": query_clean,
            "filters": filters,
            "results": normalized,
            "telemetry": telemetry.as_dict() if settings.enable_query_telemetry else {},
            "flags": {
                "two_stage": settings.enable_two_stage_ranking,
                "cross_encoder": settings.enable_cross_encoder_rerank,
                "hybrid_sparse_dense": settings.enable_sparse_dense_hybrid,
            },
        }


search_pipeline = SearchPipeline()
