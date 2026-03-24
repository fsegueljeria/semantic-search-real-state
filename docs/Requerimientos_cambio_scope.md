# Consultoría Externa: Optimización de Búsqueda Semántica Inmobiliaria

**Objetivo:** Resolver la tensión entre la similitud semántica y las restricciones exactas (hard constraints) en la búsqueda de propiedades, mejorando la relevancia y cobertura del sistema actual.

---

## 1. Arquitectura de Búsqueda: Filtros vs. Semántica Pura

**Recomendación:** Mantener y potenciar la búsqueda híbrida (Filtros estructurados + Semántica).

En dominios transaccionales como el inmobiliario, los usuarios tienen **límites duros**. Si un presupuesto es de 5.000 UF, mostrar una casa de 10.000 UF por mera coincidencia semántica es un fallo crítico de experiencia de usuario.

* **Lo estructurado debe seguir siendo estructurado:** Precio, comuna, operación, dormitorios y baños deben mantenerse como filtros en el payload de Qdrant.
* **Lo descriptivo debe ir a un pipeline de dos etapas (Two-Stage Retrieval):**
    1.  **Etapa 1 (Retrieval):** Qdrant trae un conjunto amplio (ej. `top_k=100`) usando filtros duros y búsqueda vectorial.
    2.  **Etapa 2 (Re-ranking):** Un modelo secundario ordena esos 100 resultados priorizando las características extraídas de la query (ej. "un piso", "piscina").

## 2. Re-ranking: ¿Reglas, LLMs o Híbrido?

**Recomendación:** Implementar un modelo Cross-Encoder y evaluar un filtro BM25.

Evitar las reglas manuales basadas en keywords. El español tiene demasiadas variaciones ("un piso", "1 piso", "una planta", "sin escaleras") y mantener diccionarios de reglas no es escalable.

* **Cross-Encoder:** Es el estándar actual. A diferencia de FastEmbed (Bi-Encoder) que calcula vectores por separado, un Cross-Encoder evalúa la query y el documento simultáneamente, capturando interacciones exactas. Modelos como `jina-reranker-v2-base-multilingual` o versiones multilingües de `MiniLM` son efectivos y rápidos.
* **Búsqueda Híbrida Nativa (Sparse + Dense):** Qdrant soporta Sparse Vectors (BM25). Se puede calcular un score combinado para asegurar que palabras exactas (como "piscina") no se pierdan:
    
    $$score_{final} = \alpha \cdot score_{denso} + (1 - \alpha) \cdot score_{esparso}$$

* **LLM en tiempo real:** Descartado para el flujo en vivo del usuario por alta latencia y costo. Solo es útil para evaluación offline.

## 3. Embeddings e Idioma

**Recomendación:** Migración inmediata a un modelo Multilingüe o nativo en Español.

El uso actual de `BAAI/bge-large-en-v1.5` (inglés) para datos en español diluye los conceptos y perjudica el recall.

* **Candidato ideal (Open Source):** `BAAI/bge-m3`. Soporta múltiples idiomas, ventanas de contexto amplias y genera tanto vectores densos como dispersos.
* **Alternativas:** `intfloat/multilingual-e5-large` o la API `text-embedding-3-small` de OpenAI.
* **Estrategia de Reindexación:** El cambio exige reindexar todo. Se debe crear una nueva colección en Qdrant (ej. `propiedades_v2`), ejecutar el ETL completo y, tras validar, cambiar el alias en producción para evitar *downtime*.

## 4. Enriquecimiento de Metadata en el ETL

**Recomendación:** Mover la complejidad de inferencia al ETL mediante LLMs en batch.

Para filtrar por casas de "un piso", debe existir un campo `niveles_casa` en Qdrant. Como la propiedad no lo trae por defecto, debe inferirse.

* **Atributos a priorizar:**
    * `niveles_propiedad` (Entero: 1, 2, 3)
    * `tiene_piscina`, `tiene_quincho`, `tiene_jardin`, `es_amoblado` (Booleanos)
    * `estado_propiedad` (Categoría: nueva, remodelada, a_remodelar)
* **Método:** Usar un LLM rápido y económico (Gemini Flash o GPT-4o-mini) dentro de `src/etl/cleaner.py`. Se le envía la descripción y se extrae un JSON estricto (*Structured Outputs*). Esto evita los falsos positivos de las expresiones regulares (ej. "ideal para construir piscina"). Se ejecuta una sola vez por propiedad durante la ingesta.

## 5. Evaluación y Métricas

**Recomendación:** Construir un "Golden Dataset" y usar LLM-as-a-Judge.

* **Dataset Mínimo:** Extraer 50 queries reales complejas del frontend.
* **Anotación:** Pidir a un LLM avanzado que actúe como juez y asigne un grado de relevancia (0: Irrelevante, 1: Parcial, 2: Perfecto) a los resultados devueltos por el sistema.
* **Métrica principal:** Utilizar NDCG@5 (Normalized Discounted Cumulative Gain) para penalizar si el resultado perfecto aparece en posiciones bajas.
    
    $$NDCG_{p} = \frac{DCG_{p}}{IDCG_{p}}$$

* **Iteración:** Automatizar este test para medir objetivamente las mejoras al cambiar modelos o ajustar pesos.