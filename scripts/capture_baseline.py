#!/usr/bin/env python3
"""
Capture baseline search outputs for a fixed query set.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.services.search_pipeline import search_pipeline


def load_queries(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _force_baseline_flags() -> dict:
    backup = {
        "enable_two_stage_ranking": settings.enable_two_stage_ranking,
        "enable_cross_encoder_rerank": settings.enable_cross_encoder_rerank,
        "enable_sparse_dense_hybrid": settings.enable_sparse_dense_hybrid,
    }
    settings.enable_two_stage_ranking = False
    settings.enable_cross_encoder_rerank = False
    settings.enable_sparse_dense_hybrid = False
    return backup


def _restore_flags(backup: dict) -> None:
    settings.enable_two_stage_ranking = backup["enable_two_stage_ranking"]
    settings.enable_cross_encoder_rerank = backup["enable_cross_encoder_rerank"]
    settings.enable_sparse_dense_hybrid = backup["enable_sparse_dense_hybrid"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture baseline outputs for search queries.")
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("scripts/eval_data/golden_queries.json"),
        help="Path to JSON file with evaluation queries.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("scripts/eval_data/baseline_results.json"),
        help="Path to output baseline results JSON.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Final top-k results per query.")
    args = parser.parse_args()

    queries = load_queries(args.queries)
    backup = _force_baseline_flags()
    try:
        rows = []
        for item in queries:
            response = search_pipeline.search(
                query=item["query"],
                top_k_final=args.top_k,
                top_k_retrieval=args.top_k,
                score_threshold=0.0,
            )
            rows.append(
                {
                    "id": item["id"],
                    "query": item["query"],
                    "intent": item.get("intent", ""),
                    "filters": response.get("filters", {}),
                    "results": [
                        {
                            "rank": idx + 1,
                            "score": float(hit.get("score", 0.0)),
                            "dense_score": float(hit.get("dense_score", hit.get("score", 0.0))),
                            "url": hit.get("payload", {}).get("url", ""),
                            "titulo": hit.get("payload", {}).get("titulo", ""),
                            "comuna": hit.get("payload", {}).get("comuna", ""),
                        }
                        for idx, hit in enumerate(response.get("results", []))
                    ],
                    "telemetry": response.get("telemetry", {}),
                }
            )

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "collection_alias": settings.qdrant_collection_alias,
            "embedding_model": settings.embedding_model,
            "top_k": args.top_k,
            "total_queries": len(rows),
            "rows": rows,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)
        print(f"Baseline captured in: {args.out}")
    finally:
        _restore_flags(backup)


if __name__ == "__main__":
    main()
