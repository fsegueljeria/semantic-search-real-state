# Runbook de migracion y rollout

## 1) Baseline obligatorio

1. Ejecutar baseline del sistema actual:
   - `python scripts/capture_baseline.py --top-k 5`
2. Guardar salida en control de versiones (`scripts/eval_data/baseline_results.json`).

## 2) Reindexado sin downtime

1. Cargar datos a coleccion versionada:
   - `python -m src.etl.main --use-versioned-collection -y`
2. Validar coleccion objetivo (conteo, queries criticas, calidad).
3. Switch de alias cuando valida:
   - `python -m src.etl.main --use-versioned-collection --switch-alias -y`
4. Rollback:
   - apuntar alias al nombre anterior conocido estable usando las utilidades de alias en `src/db/client.py`.

## 3) Rollout por feature flags

Secuencia recomendada:

1. `ENABLE_TWO_STAGE_RANKING=true`
2. `ENABLE_SPARSE_DENSE_HYBRID=true`
3. `ENABLE_CROSS_ENCODER_RERANK=true` (solo tras validar latencia)

## 4) Guardrails operativos

- Mantener `TOP_K_FINAL` fijo para UX estable.
- Ajustar `TOP_K_RETRIEVAL` gradualmente (50 -> 100) monitoreando latencia.
- Ajustar `HYBRID_ALPHA` con evaluación offline antes de mover a productivo.

## 5) Telemetria y monitoreo

Campos minimos por query (expuestos por el pipeline):

- `parse_ms`
- `embed_ms`
- `retrieval_ms`
- `rerank_ms`
- `total_ms`

Alertas sugeridas:

- p95 `total_ms` fuera de SLO.
- alza sostenida de consultas sin resultados.
- caida del NDCG@5 en evaluación offline.

## 6) Evaluación continua

1. `python scripts/eval_relevance.py --top-k 5`
2. Opcional con juez LLM:
   - `python scripts/eval_relevance.py --top-k 5 --use-llm-judge`
3. Gate de promoción:
   - no promover cambios con caída de NDCG@5 o precision@k vs baseline.
