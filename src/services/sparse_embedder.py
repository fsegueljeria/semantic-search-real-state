"""
Sparse vectorizer for hybrid dense+sparse retrieval.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Dict, List, Tuple

from unidecode import unidecode

from config.settings import settings


class SparseEmbeddingService:
    """Hash-based sparse vectorizer (deterministic, dependency-free)."""

    _es_stopwords = {
        "de", "la", "el", "los", "las", "y", "o", "en", "con", "por", "para",
        "un", "una", "unos", "unas", "al", "del", "que", "se", "es", "a",
    }

    def _normalize(self, text: str) -> List[str]:
        clean = unidecode(str(text or "").lower())
        tokens = re.findall(r"[a-z0-9]+", clean)
        min_len = max(1, int(settings.sparse_min_token_length))
        return [
            token
            for token in tokens
            if ((len(token) >= min_len) or token.isdigit()) and token not in self._es_stopwords
        ]

    @staticmethod
    def _hash_token(token: str, hash_space: int) -> int:
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(digest, 16) % hash_space

    def embed_text(self, text: str) -> Dict[str, List[float]]:
        """
        Return sparse vector in Qdrant-compatible shape:
        {"indices": [...], "values": [...]}
        """
        tokens = self._normalize(text)
        if not tokens:
            return {"indices": [], "values": []}

        hash_space = max(1024, int(settings.sparse_hash_space))
        counts: Dict[int, int] = {}
        for token in tokens:
            idx = self._hash_token(token, hash_space)
            counts[idx] = counts.get(idx, 0) + 1

        length = max(len(tokens), 1)
        # Sublinear TF normalization.
        weighted: List[Tuple[int, float]] = [
            (idx, (1.0 + math.log(freq)) / length)
            for idx, freq in counts.items()
        ]
        weighted.sort(key=lambda item: item[0])
        return {
            "indices": [idx for idx, _ in weighted],
            "values": [val for _, val in weighted],
        }

    def embed_batch(self, texts: List[str]) -> List[Dict[str, List[float]]]:
        return [self.embed_text(text) for text in texts]


sparse_embedder = SparseEmbeddingService()
