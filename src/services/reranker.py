"""
Reranking utilities for two-stage retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from loguru import logger

try:
    from sentence_transformers import CrossEncoder  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    CrossEncoder = None


@dataclass
class CandidateScore:
    """Score container used by the search pipeline."""

    dense_score: float
    sparse_score: float
    rerank_score: float
    final_score: float


class SearchReranker:
    """Cross-encoder reranker with safe lexical fallback."""

    def __init__(self, model_name: str = "jinaai/jina-reranker-v2-base-multilingual") -> None:
        self.model_name = model_name
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        if CrossEncoder is None:
            logger.warning("sentence-transformers is not installed; cross-encoder reranking disabled.")
            return
        try:
            self._model = CrossEncoder(self.model_name)
            logger.info(f"Cross-encoder loaded: {self.model_name}")
        except Exception as exc:
            logger.warning(f"Could not load cross-encoder '{self.model_name}': {exc}")
            self._model = None

    @staticmethod
    def _join_candidate_text(payload: Dict[str, Any]) -> str:
        title = str(payload.get("titulo", "")).strip()
        desc = str(payload.get("descripcion", "")).strip()
        comuna = str(payload.get("comuna", "")).strip()
        tipo = str(payload.get("tipo_propiedad", "")).strip()
        text = " ".join([part for part in [title, desc, comuna, tipo] if part])
        return text[:2500]

    @staticmethod
    def _lexical_score(query: str, payload: Dict[str, Any]) -> float:
        """Simple sparse-style score: normalized query-token overlap."""
        q_tokens = {token for token in query.lower().split() if len(token) > 2}
        if not q_tokens:
            return 0.0
        doc_text = SearchReranker._join_candidate_text(payload).lower()
        hits = sum(1 for token in q_tokens if token in doc_text)
        return hits / max(len(q_tokens), 1)

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        use_cross_encoder: bool,
        filters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Add sparse/rerank/final scores and return sorted candidates."""
        if not candidates:
            return []

        ce_scores: List[float] = [0.0] * len(candidates)
        if use_cross_encoder:
            self._ensure_model()
            if self._model is not None:
                pairs = [(query, self._join_candidate_text(item.get("payload", {}))) for item in candidates]
                try:
                    raw_scores = self._model.predict(pairs)
                    ce_scores = [float(score) for score in raw_scores]
                except Exception as exc:
                    logger.warning(f"Cross-encoder scoring failed. Falling back to lexical-only rerank: {exc}")

        enriched: List[Dict[str, Any]] = []
        target_levels = None
        if filters and isinstance(filters.get("niveles_propiedad"), int):
            target_levels = int(filters["niveles_propiedad"])
        for idx, item in enumerate(candidates):
            payload = item.get("payload", {})
            dense_score = float(item.get("dense_score", item.get("score", 0.0)))
            sparse_score = self._lexical_score(query, payload)
            rerank_score = ce_scores[idx] if idx < len(ce_scores) else 0.0
            # Constraint-aware adjustment for "niveles_propiedad".
            if target_levels is not None:
                current_levels = int(payload.get("niveles_propiedad", 0) or 0)
                if current_levels == target_levels:
                    rerank_score += 0.25
                elif current_levels > 0 and current_levels != target_levels:
                    rerank_score -= 0.35
            item["sparse_score"] = sparse_score
            item["rerank_score"] = rerank_score
            enriched.append(item)

        return enriched


reranker = SearchReranker()
