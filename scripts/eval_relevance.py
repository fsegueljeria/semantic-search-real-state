#!/usr/bin/env python3
"""
Offline evaluation for relevance quality (NDCG@k, Precision@k, hard-filter pass-rate).
"""

from __future__ import annotations

import argparse
import json
import math
import urllib.request
from pathlib import Path
from typing import Any, Dict, List
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.services.search_pipeline import search_pipeline


def dcg_at_k(relevances: List[int], k: int) -> float:
    score = 0.0
    for i, rel in enumerate(relevances[:k], start=1):
        score += (2**rel - 1) / math.log2(i + 1)
    return score


def ndcg_at_k(relevances: List[int], k: int) -> float:
    actual = dcg_at_k(relevances, k)
    ideal = dcg_at_k(sorted(relevances, reverse=True), k)
    return 0.0 if ideal == 0 else actual / ideal


def precision_at_k(relevances: List[int], k: int) -> float:
    if k <= 0:
        return 0.0
    valid = relevances[:k]
    if not valid:
        return 0.0
    return sum(1 for rel in valid if rel >= 1) / len(valid)


def heuristic_judge(query: str, payload: Dict[str, Any]) -> int:
    """Fallback judge: lexical overlap + comuna match as weak relevance proxy."""
    query_tokens = {t for t in query.lower().split() if len(t) > 2}
    text = f"{payload.get('titulo', '')} {payload.get('descripcion', '')}".lower()
    overlap = sum(1 for token in query_tokens if token in text)
    comuna = str(payload.get("comuna", "")).lower()
    has_comuna = comuna and comuna in query.lower()
    if overlap >= 4 or (overlap >= 2 and has_comuna):
        return 2
    if overlap >= 2:
        return 1
    return 0


def llm_judge(query: str, payload: Dict[str, Any]) -> int:
    """Optional LLM-as-a-judge, defaults to heuristic on failure or no key."""
    api_key = settings.llm_enrichment_api_key
    if not api_key:
        return heuristic_judge(query, payload)

    prompt = (
        "Actua como juez de relevancia inmobiliaria. "
        "Devuelve JSON estricto: {\"relevance\":0|1|2}. "
        f"Query: {query}. "
        f"Titulo: {payload.get('titulo','')}. "
        f"Descripcion: {payload.get('descripcion','')}. "
        f"Comuna: {payload.get('comuna','')}. Tipo: {payload.get('tipo_propiedad','')}."
    )
    body = {
        "model": settings.llm_enrichment_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Responde solo JSON valido."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
        content = parsed["choices"][0]["message"]["content"]
        relevance = int(json.loads(content).get("relevance", 0))
        return relevance if relevance in (0, 1, 2) else 0
    except Exception:
        return heuristic_judge(query, payload)


def load_queries(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(queries: list[dict], top_k: int, use_llm_judge: bool) -> Dict[str, Any]:
    rows = []
    hard_filter_success = 0
    for item in queries:
        query = item["query"]
        response = search_pipeline.search(
            query=query,
            top_k_final=top_k,
            top_k_retrieval=settings.top_k_retrieval,
            score_threshold=settings.score_threshold,
        )
        results = response.get("results", [])
        relevances = []
        for hit in results:
            payload = hit.get("payload", {})
            rel = llm_judge(query, payload) if use_llm_judge else heuristic_judge(query, payload)
            relevances.append(rel)

        ndcg = ndcg_at_k(relevances, top_k)
        p_at_k = precision_at_k(relevances, top_k)
        has_filters = bool(response.get("filters"))
        passed_hard = True
        if has_filters and not results:
            passed_hard = False
        hard_filter_success += int(passed_hard)
        rows.append(
            {
                "id": item.get("id", ""),
                "query": query,
                "intent": item.get("intent", ""),
                "filters": response.get("filters", {}),
                "ndcg_at_k": ndcg,
                "precision_at_k": p_at_k,
                "relevances": relevances,
                "telemetry": response.get("telemetry", {}),
            }
        )

    avg_ndcg = sum(r["ndcg_at_k"] for r in rows) / max(len(rows), 1)
    avg_p = sum(r["precision_at_k"] for r in rows) / max(len(rows), 1)
    hard_rate = hard_filter_success / max(len(rows), 1)
    return {
        "queries_evaluated": len(rows),
        "avg_ndcg_at_k": avg_ndcg,
        "avg_precision_at_k": avg_p,
        "hard_filter_pass_rate": hard_rate,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate relevance quality for semantic search.")
    parser.add_argument("--queries", type=Path, default=Path("scripts/eval_data/golden_queries.json"))
    parser.add_argument("--out", type=Path, default=Path("scripts/eval_data/eval_report.json"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--use-llm-judge", action="store_true")
    args = parser.parse_args()

    report = evaluate(load_queries(args.queries), top_k=args.top_k, use_llm_judge=args.use_llm_judge)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=True, indent=2)
    print(f"Evaluation report saved in: {args.out}")


if __name__ == "__main__":
    main()
