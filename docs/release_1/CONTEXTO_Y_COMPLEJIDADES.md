# Contexto del proyecto y complejidades a resolver

**Documento para consultor externo**  
*Búsqueda semántica de propiedades inmobiliarias — optimización de relevancia y cobertura*

---

## 1. Contexto del proyecto

### 1.1 Objetivo del sistema

Sistema de **búsqueda semántica** sobre propiedades inmobiliarias chilenas. El usuario escribe en lenguaje natural (ej. *"casa en Las Condes de un piso con jardín"*) y el sistema devuelve propiedades relevantes por **similitud de significado**, no solo por coincidencia de palabras.

### 1.2 Stack técnico actual

| Componente | Tecnología |
|------------|------------|
| Base de datos vectorial | **Qdrant** (Docker, puertos 6333/6334) |
| Embeddings | **FastEmbed** con modelo configurable (por defecto en código: `BAAI/bge-large-en-v1.5`; README menciona `BAAI/bge-m3`) |
| Dimensión de vectores | 1024 (configurable en `config/settings.py`) |
| Fuente de datos | CSV (scraper Lyon Balmaceda): propiedades con título, descripción, comuna, barrio, precio UF, m², dormitorios, baños, estacionamiento, bodega, año, piso, gastos comunes, imágenes, etc. |
| Frontend | Streamlit (`scripts/chat_search_frontend.py`) — chat con tarjetas de propiedades |
| Pipeline de datos | ETL en batches: `src/etl/loader.py`, `src/etl/cleaner.py`, `src/etl/main.py` |

### 1.3 Flujo actual de búsqueda

1. **Entrada:** query en lenguaje natural (ej. *"casa en las condes de un piso"*).
2. **Extracción de filtros:** el módulo `extract_filters()` en `scripts/semantic_search.py` parsea la query y genera:
   - **Filtros estructurados** aplicados en Qdrant: tipo de propiedad, comuna, barrio, operación (venta/arriendo), precio UF, m², dormitorios, baños, estacionamiento, bodega, año, piso (número de piso en edificio), gastos comunes, portal.
   - **Query limpia** para el embedding: se eliminan las partes que ya se usaron como filtro, quedando el resto (ej. "un piso") para similitud semántica.
3. **Embedding + búsqueda:** se genera el vector de la query limpia y se llama a Qdrant con `search_similar(..., limit=top_k, metadata_filter=filters)`.
4. **Salida:** los primeros `top_k` resultados (p. ej. 5) ordenados por score de similitud.

### 1.4 Cómo se indexan los datos (ETL)

- **Texto para embedding:** en `DataCleaner.create_semantic_blob()` se construye un blob por propiedad con: título (repetido 2×), comuna, barrio, tipo, operación, dormitorios, baños, m² útiles, “con estacionamiento”/“con bodega” si aplica, y **descripción** (truncada a 1000 caracteres; blob total truncado a 2000).
- **Metadata (payload):** en `prepare_metadata()` se guardan todos los campos estructurados (url, portal, tipo_propiedad, operacion, comuna, barrio, precio_uf, m2_util, m2_total, dormitorios, banios, estacionamiento, bodega, anio, piso, gastos_comunes, titulo, descripcion, images).  
- **Importante:** no existe hoy un campo estructurado para “cantidad de pisos de la casa” (un piso vs dos pisos). El campo `piso` en metadata se refiere al piso del edificio (departamentos), no al número de niveles de una casa.

---

## 2. Problema central observado

Al buscar **"casa en las condes de un piso"**:

- **Filtros aplicados:** `tipo_propiedad = "casa"`, `comuna = "Las Condes"`.
- La condición **"de un piso"** no se traduce a ningún filtro en Qdrant porque no hay atributo indexado para “número de pisos de la casa”.
- Esa condición queda solo en la **query para embedding** (texto residual tipo “un piso”). La similitud semántica no discrimina bien entre casas de un piso y casas de dos o más pisos, porque:
  - La información está solo en el **texto de la descripción** (no en un campo filtrable).
  - Los modelos de embedding no siempre capturan bien estas distinciones numéricas/descriptivas en español.

**Consecuencia:** entre los resultados aparecen casas de más de un piso, lo que el usuario percibe como fallo de relevancia.

Este mismo patrón se repite para **cualquier criterio que viva solo en la descripción**: vista, jardín grande, piscina, quincho, amoblado, estado de la propiedad, etc.

---

## 3. Complejidades a resolver (resumen para el consultor)

### 3.1 Criterios que no están en atributos estructurados

- **Número de pisos de la casa** (un piso vs dos pisos / dos niveles).
- **Amenities o características descriptivas:** piscina, jardín, quincho, vista (mar, cordillera, ciudad), amoblado, “casa nueva”, “remodelada”.
- **Condiciones de texto libre:** “cerca de colegios”, “tranquilo”, “buena conectividad”, etc.

**Pregunta de diseño:** ¿Cómo lograr que la búsqueda sea a la vez **amplia** (no perder resultados válidos) y **precisa** (no mostrar propiedades que no cumplen criterios que el usuario expresó con claridad)?

### 3.2 Enfoque actual: filtros predefinidos + embedding

- Ventaja: control y rendimiento para atributos que sí están en metadata (precio, comuna, dormitorios, etc.).
- Limitación: cada nuevo criterio “de descripción” (un piso, piscina, jardín) requiere o bien:
  - **Enriquecer el ETL** (inferir nuevos campos desde la descripción y guardarlos en payload), o
  - **Re-ranking post-Qdrant** (reglas o modelo que reordene/filtre usando título + descripción).

### 3.3 Alternativa explorada: búsqueda “sin filtros predefinidos”

- Se ha valorado usar **solo** similitud semántica (y opcionalmente un **LLM como juez** que, dado query + descripción de cada candidato, decida cumplimiento). Así no se dependen de filtros cableados.
- **Trade-offs:** mayor flexibilidad y menos mantenimiento de reglas, pero menos garantías duras, mayor coste/latencia si se re-rankea con LLM sobre muchos candidatos, y mayor dificultad para depurar resultados incorrectos.

### 3.4 Re-ranking (diseño ya esbozado internamente)

- **Idea:** en lugar de pedir a Qdrant solo `top_k=5`, pedir un **conjunto amplio** (ej. 100 resultados) con los mismos filtros duros. Luego, en aplicación:
  - Calcular un **score textual** por candidato (p. ej. +bonus si en título/descripción aparece “un piso”, −penalización si aparece “dos pisos”).
  - Combinar `score_final = α * score_qdrant + β * score_textual` y reordenar.
  - Devolver los primeros `top_k` tras el re-ranking.
- **Variante avanzada:** que el “score textual” lo calcule un **LLM** (cuánto cumple la propiedad la intención del usuario), en lugar de reglas fijas.

**Pregunta para el consultor:** qué arquitectura de re-ranking (reglas vs. LLM, umbrales, híbrido) recomienda y cómo integrarla de forma óptima con el stack actual.

### 3.5 Modelo de embeddings e idioma

- Configuración actual en código: `BAAI/bge-large-en-v1.5` (modelo en inglés). Datos y consultas son en **español**.
- README menciona `BAAI/bge-m3` (multilingüe). Un modelo multilingüe o en español podría mejorar la captura de matices (“de un piso”, “dos niveles”, “jardín amplio”).
- **Complejidad:** cambiar de modelo implica **nueva dimensión de vectores** y **reindexación completa** de la colección en Qdrant.

### 3.6 Enriquecimiento de metadata en ETL

- Para poder **filtrar** por “casa de un piso” en Qdrant haría falta un campo en payload (ej. `pisos_casa`: 1, 2, …) inferido desde la descripción (regex o modelo ligero).
- Igual para piscina, jardín, vista, etc. (booleanos o categorías).
- **Complejidad:** definir qué campos derivar, cómo inferirlos de forma estable (regex vs. NER/Clasificador) y mantener la calidad sin duplicar lógica entre ETL y re-ranking.

### 3.7 Evaluación y métricas

- No hay hoy un **conjunto de evaluación** (queries de prueba + propiedades “ideales” por query) para medir precisión/recall ni para comparar cambios (modelo, re-ranking, filtros).
- **Complejidad:** definir métricas y proceso de evaluación reproducibles para que el consultor pueda proponer y validar mejoras.

---

## 4. Resumen de preguntas para el consultor

1. **Arquitectura de búsqueda:** ¿Recomienda mantener filtros estructurados para lo que ya está en metadata y añadir re-ranking para criterios “de descripción”, o avanzar hacia un diseño más “solo semántico + LLM” y en qué medida?
2. **Re-ranking:** ¿Reglas basadas en keywords/frases, re-ranking con LLM, o híbrido? ¿Cómo fijar pesos (α, β) y umbrales sin un dataset etiquetado?
3. **Embeddings:** ¿Modelo multilingüe/español concreto recomendado para este dominio (inmobiliario, Chile) y criterios para decidir reindexación?
4. **Enriquecimiento ETL:** ¿Qué atributos derivados (pisos_casa, tiene_piscina, etc.) priorizar y con qué método (regex, modelo pequeño, LLM en batch)?
5. **Evaluación:** ¿Métricas y proceso mínimos (benchmark de queries, relevancia manual o con LLM) para poder iterar con el consultor y medir impacto?

---

## 5. Referencias rápidas en el repositorio

| Qué | Dónde |
|-----|--------|
| Configuración (modelo, dimensión, Qdrant) | `config/settings.py`, `.env` |
| Extracción de filtros desde la query | `scripts/semantic_search.py` → `extract_filters()`, `_extract_*` |
| Búsqueda actual (sin re-ranking) | `scripts/semantic_search.py` → `search()` |
| Construcción del texto indexado (blob) | `src/etl/cleaner.py` → `create_semantic_blob()` |
| Metadata guardada en Qdrant | `src/etl/cleaner.py` → `prepare_metadata()` |
| Cliente Qdrant (search_similar, filtros) | `src/db/client.py` |
| Servicio de embeddings | `src/services/embedder.py` |
| Frontend chat | `scripts/chat_search_frontend.py` |
| Esquema y análisis del CSV fuente | `docs/analisis_csv_lyon_balmaceda.md` |

---

*Documento generado para alinear con el consultor externo en la búsqueda de una solución óptima para relevancia y cobertura de la búsqueda semántica.*
