# Guía de scripts y puesta en marcha

Este documento es la referencia operativa del proyecto **Semantic Search Real Estate**
(búsqueda semántica de propiedades sobre Qdrant + FastEmbed/`BAAI/bge-m3`, con
frontend en Streamlit y un ETL en Python). Cubre tres bloques:

1. [Uso de los scripts](#1-uso-de-los-scripts) — qué hace cada script, cómo se ejecuta,
   sus flags y sus dependencias.
2. [Instalación paso a paso](#2-instalación-paso-a-paso-desde-cero) — cómo levantar
   todo desde cero (venv, dependencias, Qdrant, ETL, frontend).
3. [Diagrama de conexiones externas](#3-diagrama-de-conexiones-externas) — diagrama
   Mermaid del sistema y sus dependencias externas/locales.

> Convenciones:
> - Todos los comandos asumen que estás en la raíz del repositorio y con el
>   entorno virtual activado (`source .venv/bin/activate`).
> - Los scripts `*.py` se invocan con `python` (o `.venv/bin/python`).
> - El frontend Streamlit **siempre** se ejecuta con `streamlit run …`,
>   nunca con `python …`.

---

## 1. Uso de los scripts

A continuación se documentan los scripts del directorio `scripts/` y los scripts
sueltos en la raíz del repo, agrupados por función.

### 1.1 Búsqueda y demo (CLI)

#### `scripts/semantic_search.py`

| Campo | Detalle |
|---|---|
| Propósito | Búsqueda semántica de propiedades en lenguaje natural, con extracción automática de filtros (operación, tipo, comuna, barrio, precio UF, m², dormitorios, baños, estacionamiento, bodega, año, piso, gastos comunes, portal). Modo single-query o interactivo. |
| Comando | `python scripts/semantic_search.py "casa en Buin con jardín"` (búsqueda única) <br> `python scripts/semantic_search.py` (modo interactivo) |
| Argumentos | No usa `argparse`. Toma toda la línea de comandos (`sys.argv[1:]`) como query. Sin args entra al modo interactivo. |
| Dependencias | Qdrant levantado y poblado (alias `QDRANT_COLLECTION_ALIAS` o colección base), modelo de embeddings descargable, `.env` configurado. |
| Conexiones externas | Qdrant (vía `src/db/client.py`), FastEmbed (modelo local en `./models_cache/`, descarga inicial desde HuggingFace Hub). Si los flags lo permiten también usa el cross-encoder (`jinaai/jina-reranker-v2-base-multilingual`) y el sparse embedder local. |

#### `demo_search.py` (raíz)

| Campo | Detalle |
|---|---|
| Propósito | Demo guiada que ejecuta una lista fija de búsquedas (`apartamento moderno con vista al mar`, `casa familiar con jardín`, etc.) usando directamente `EmbeddingService` + `QdrantManager`. Útil para validar end-to-end con la colección base. |
| Comando | `python demo_search.py` |
| Argumentos | Ninguno. Pide pulsar Enter entre búsquedas. |
| Dependencias | Colección `QDRANT_COLLECTION_NAME` con vectores cargados; modelo de embeddings disponible. |
| Conexiones externas | Qdrant, FastEmbed (con descarga desde HuggingFace en el primer uso). |

---

### 1.2 Frontend de chat (Streamlit)

#### `scripts/chat_search_frontend.py`

| Campo | Detalle |
|---|---|
| Propósito | UI tipo chat con tarjetas de propiedades (foto principal, ubicación, precio UF, dormitorios/baños/m², link al aviso, descripción y carrusel de fotos en un expander). Llama al `search_pipeline` y respeta los feature flags (two-stage, hybrid, cross-encoder). |
| Comando | `streamlit run scripts/chat_search_frontend.py` <br> Alternativa sin venv activado: `.venv/bin/streamlit run scripts/chat_search_frontend.py` <br> En Docker se invoca como: `python -m streamlit run scripts/chat_search_frontend.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true` |
| Argumentos | No define flags propios. Usa los controles de la sidebar: `top_k` (3–15) y umbral mínimo de relevancia (0.0–1.0). |
| Dependencias | `streamlit>=1.36.0`, Qdrant accesible (alias resuelto), modelo de embeddings disponible. |
| Conexiones externas | Navegador del usuario por HTTP (puerto `8501`), Qdrant, FastEmbed, cross-encoder opcional. |

> ⚠️ **Importante:** ejecutar este archivo con `python scripts/chat_search_frontend.py`
> mostrará el aviso de Streamlit *"to view this Streamlit app … run with streamlit
> run …"* y la app no funcionará. Usar siempre `streamlit run`.

---

### 1.3 ETL / mantenimiento de la base vectorial

#### `python -m src.etl.main` (orquestador del ETL)

> Aunque no está en `scripts/`, se documenta acá porque varios scripts dependen de él.

| Campo | Detalle |
|---|---|
| Propósito | Orquesta el pipeline ETL: carga el CSV en chunks, limpia datos, genera embeddings densos + sparse y hace upsert en Qdrant. Soporta colecciones versionadas y switch atómico de alias. |
| Comando | `python -m src.etl.main` (con confirmación interactiva) <br> `python -m src.etl.main -y` (sin confirmar) <br> `python -m src.etl.main --recreate` (borra y recrea la colección) <br> `python -m src.etl.main --use-versioned-collection -y` (carga en `<colección>_<sufijo>`) <br> `python -m src.etl.main --use-versioned-collection --switch-alias -y` (carga + switch del alias) <br> `python -m src.etl.main --skip-rows 50000` (resumir carga interrumpida) |
| Argumentos (`argparse`) | `--recreate` (borra colección y recarga, sin prompt), `-y/--yes` (skip prompt), `--skip-rows N` (saltar N filas parseadas), `--use-versioned-collection` (escribe en `<col>_<QDRANT_COLLECTION_VERSION_SUFFIX>`), `--switch-alias` (al final cambia `QDRANT_COLLECTION_ALIAS` al colección target). |
| Dependencias | Qdrant accesible, CSV en `CSV_FILE_PATH`, `fastembed`, `qdrant-client`, modelo de embeddings (descargado o disponible), espacio en disco (`models_cache/`, `etl_pipeline.log`). |
| Conexiones externas | Qdrant (HTTP/gRPC), FastEmbed (descarga inicial desde HuggingFace Hub), filesystem (CSV, `etl_pipeline.log`). |

#### `scripts/clean_vector_db.py`

| Campo | Detalle |
|---|---|
| Propósito | Elimina una colección de Qdrant (por defecto `QDRANT_COLLECTION_NAME`). Útil antes de un rebuild completo. |
| Comando | `python scripts/clean_vector_db.py` (pide confirmación) <br> `python scripts/clean_vector_db.py --force` (sin prompt) <br> `python scripts/clean_vector_db.py --collection real_estate_properties_v2` |
| Argumentos (`argparse`) | `--collection / -c` (nombre de colección, default `QDRANT_COLLECTION_NAME`), `--force / -f` (no pedir confirmación). |
| Dependencias | Qdrant levantado. |
| Conexiones externas | Qdrant. |

#### `scripts/check_property_by_url.py`

| Campo | Detalle |
|---|---|
| Propósito | Verifica si una propiedad existe en la base vectorial filtrando por su URL exacta y muestra todo el payload guardado (ID, comuna, precio, fotos, descripción truncada, JSON completo). Útil para validar la calidad de la carga. |
| Comando | `python scripts/check_property_by_url.py` (usa una URL por defecto) <br> `python scripts/check_property_by_url.py "https://www.portalinmobiliario.com/MLC-…_JM"` |
| Argumentos | No usa `argparse`. Acepta opcionalmente la URL como `sys.argv[1]`. |
| Dependencias | Qdrant levantado y colección `QDRANT_COLLECTION_NAME` con datos. |
| Conexiones externas | Qdrant (`scroll` con filtro sobre `payload.url`). |

---

### 1.4 Auditoría y limpieza de datos

#### `scripts/audit_string_cleaning.py`

| Campo | Detalle |
|---|---|
| Propósito | Audita el CSV de origen para identificar registros donde la limpieza puede fallar: campos numéricos no convertibles, coordenadas fuera de Chile, JSON de imágenes inválido y blob semántico insuficiente. Genera un reporte CSV y/o Markdown. |
| Comando | `python scripts/audit_string_cleaning.py` <br> `python scripts/audit_string_cleaning.py --csv ./lyon_balmaceda_scraper.csv --output audit_cleaning_report.csv --format both` <br> `python scripts/audit_string_cleaning.py --exclude-types images_json_invalid` |
| Argumentos (`argparse`) | `--csv` (ruta al CSV; default `settings.csv_file_path`), `--output / -o` (archivo de salida; default `audit_cleaning_report.csv`), `--format {csv,md,both}` (formato del reporte; default `both`), `--exclude-types TYPE …` (excluir tipos: `numeric_invalid`, `coordinates_invalid`, `images_json_invalid`, `semantic_content_insufficient`). |
| Dependencias | CSV existente en disco. **No** necesita Qdrant. Reutiliza `ETLLoader._parse_csv_row` y `DataCleaner` de `src/etl/`. |
| Conexiones externas | Filesystem: lectura del CSV y escritura del reporte (`audit_cleaning_report.csv` y/o `.md`). |

---

### 1.5 Evaluación y baseline

#### `scripts/capture_baseline.py`

| Campo | Detalle |
|---|---|
| Propósito | Ejecuta un set de queries doradas (`scripts/eval_data/golden_queries.json`) **forzando los flags a `False`** (sin two-stage, sin cross-encoder, sin hybrid) para fijar un baseline reproducible de resultados (URL, título, comuna, scores, telemetry). |
| Comando | `python scripts/capture_baseline.py` <br> `python scripts/capture_baseline.py --top-k 10 --out scripts/eval_data/baseline_v2.json` |
| Argumentos (`argparse`) | `--queries` (default `scripts/eval_data/golden_queries.json`), `--out` (default `scripts/eval_data/baseline_results.json`), `--top-k N` (default `5`). |
| Dependencias | Qdrant levantado y colección poblada, archivo de queries doradas. |
| Conexiones externas | Qdrant, FastEmbed; escritura en `scripts/eval_data/baseline_results.json`. |

#### `scripts/eval_relevance.py`

| Campo | Detalle |
|---|---|
| Propósito | Evaluación offline de calidad: calcula NDCG@k, Precision@k y hard-filter pass-rate sobre las queries doradas. Soporta un *judge* heurístico (overlap léxico + match de comuna) o, opcionalmente, un *LLM-as-a-judge* vía OpenAI. |
| Comando | `python scripts/eval_relevance.py` <br> `python scripts/eval_relevance.py --top-k 10 --use-llm-judge` |
| Argumentos (`argparse`) | `--queries` (default `scripts/eval_data/golden_queries.json`), `--out` (default `scripts/eval_data/eval_report.json`), `--top-k N` (default `5`), `--use-llm-judge` (flag, requiere `LLM_ENRICHMENT_API_KEY` para hablar con OpenAI; si no hay key cae al heurístico). |
| Dependencias | Qdrant + colección poblada. Para LLM judge: `LLM_ENRICHMENT_API_KEY` válida y acceso a `https://api.openai.com`. |
| Conexiones externas | Qdrant, FastEmbed, opcionalmente OpenAI (`/v1/chat/completions`); escritura en `scripts/eval_data/eval_report.json`. |

---

### 1.6 Debugging (scripts sueltos en la raíz)

> Estos scripts viven en la raíz del repo y son herramientas puntuales de
> diagnóstico. Algunos asumen rutas de import antiguas (`src/` añadido al
> `sys.path`). Si llegan a fallar por imports, basta con ejecutarlos con el
> venv activado y desde la raíz del proyecto.

#### `check_models.py`

| Campo | Detalle |
|---|---|
| Propósito | Lista los modelos de texto soportados por FastEmbed (los primeros 10 y los primeros 20). Útil para descubrir nombres válidos para `EMBEDDING_MODEL`. |
| Comando | `python check_models.py` |
| Argumentos | Ninguno. |
| Dependencias | `fastembed` instalado. |
| Conexiones externas | Solo lectura local del catálogo de FastEmbed (puede gatillar consultas a HuggingFace si no hay caché). |

#### `debug_csv.py`

| Campo | Detalle |
|---|---|
| Propósito | Inspección rápida del CSV: imprime el header, la primera fila cruda, y prueba a cargar con distintos modos de quoting de pandas (`QUOTE_ALL`, `QUOTE_MINIMAL`, `QUOTE_NONNUMERIC`, `QUOTE_NONE`). |
| Comando | `python debug_csv.py` |
| Argumentos | Ninguno (la ruta del CSV está hardcodeada en `lyon_balmaceda_scraper.csv`). |
| Dependencias | `pandas`, CSV en la ruta esperada. |
| Conexiones externas | Filesystem (CSV). |

#### `debug_csv_parsing.py`

| Campo | Detalle |
|---|---|
| Propósito | Prueba aislada de parseo de una fila CSV problemática (campo `IMAGES` con JSON anidado y comillas dobles), reproduciendo la configuración del loader (`quoting=3`, `escapechar='\\'`). Útil para depurar nuevas variantes del scraper. |
| Comando | `python debug_csv_parsing.py` |
| Argumentos | Ninguno. |
| Dependencias | `pandas`. |
| Conexiones externas | Ninguna (datos embebidos en el script). |

#### `debug_payload.py`

| Campo | Detalle |
|---|---|
| Propósito | Hace una búsqueda mínima (`apartamento moderno`) y dumpea la estructura del primer resultado (tipo, atributos, payload, score, id). Útil para entender la forma exacta de los hits que devuelve Qdrant. |
| Comando | `python debug_payload.py` |
| Argumentos | Ninguno. |
| Dependencias | Qdrant accesible y con datos en `QDRANT_COLLECTION_NAME`, modelo de embeddings disponible. |
| Conexiones externas | Qdrant, FastEmbed. |

#### `debug_qdrant.py`

| Campo | Detalle |
|---|---|
| Propósito | Inspecciona el `QdrantClient` activo: lista métodos relacionados con `search`/`query` y devuelve el `points_count` de la colección configurada. Útil para validar conectividad y versión de SDK. |
| Comando | `python debug_qdrant.py` |
| Argumentos | Ninguno. |
| Dependencias | Qdrant levantado y `qdrant-client` instalado. |
| Conexiones externas | Qdrant. |

---

### 1.7 Tests (no son `pytest`, son scripts manuales)

> A pesar del prefijo `test_`, estos archivos no son tests de `pytest`: son
> ejecutables manuales para verificar el comportamiento end-to-end. Para
> testing automatizado real, `requirements.txt` ya incluye `pytest`.

#### `test_cleaning.py`

| Campo | Detalle |
|---|---|
| Propósito | Carga 3 filas del CSV, genera el blob semántico y la metadata con `DataCleaner`, e imprime longitudes y previews. Sirve para validar el pipeline de limpieza. |
| Comando | `python test_cleaning.py` |
| Argumentos | Ninguno (CSV hardcodeado). |
| Dependencias | `pandas`, CSV en disco, `src/etl/cleaner.py`. |
| Conexiones externas | Filesystem. |

#### `test_cleaning_issue.py`

| Campo | Detalle |
|---|---|
| Propósito | Reproduce un caso concreto donde `BANIOS='32'` (valor problemático) y comuna/barrio sucios; corre `DataCleaner.prepare_metadata` y `DataCleaner.clean_numeric` para verificar el output. |
| Comando | `python test_cleaning_issue.py` |
| Argumentos | Ninguno. |
| Dependencias | `pandas`, `src/etl/cleaner.py`. |
| Conexiones externas | Ninguna. |

#### `test_semantic_search.py`

| Campo | Detalle |
|---|---|
| Propósito | Variante anterior de `demo_search.py`: ofrece menú de búsqueda interactiva o demo predefinida sobre `EmbeddingService` + `QdrantManager`. Algunos campos del payload que muestra (`location`, `price`, `total_area`) son del esquema antiguo, así que parte de la salida puede aparecer como `N/A`. |
| Comando | `python test_semantic_search.py` |
| Argumentos | Ninguno (menú interactivo `1` interactivo / `2` demo). |
| Dependencias | Qdrant accesible y poblado, FastEmbed disponible. |
| Conexiones externas | Qdrant, FastEmbed. |

---

## 2. Instalación paso a paso (desde cero)

Estas instrucciones consolidan `README.md`, `docs/SETUP.md`, `requirements.txt`,
`pyproject.toml`, `Dockerfile`, `docker-compose.yml` y `.env.example`.

### 2.1 Requisitos previos

- **Python 3.9+** (el `pyproject.toml` exige `requires-python = ">=3.9"`; el
  `Dockerfile` corre con `python:3.11-slim`).
- **Docker** (para Qdrant, recomendado).
- **Git** (ya tienes el repo si estás leyendo esto).
- ~6–8 GB de RAM libres si vas a cargar el CSV completo y descargar el modelo
  `BAAI/bge-m3` la primera vez.

### 2.2 Clonar / entrar al proyecto

```bash
cd /ruta/a/semantic-search-real-state
```

### 2.3 Crear y activar el entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate            # macOS / Linux
# Windows PowerShell: .venv\Scripts\Activate.ps1
```

Verifica que veas `(.venv)` en tu prompt.

### 2.4 Instalar dependencias de Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Esto instala las dependencias core declaradas en `requirements.txt`:

- **Datos / ETL**: `pandas>=2.1.0`, `numpy>=1.24.0`, `tqdm>=4.65.0`.
- **Config**: `pydantic>=2.0.0`, `pydantic-settings>=2.0.0`,
  `python-dotenv>=1.0.0`.
- **Vector DB**: `qdrant-client>=1.6.0`.
- **Embeddings**: `fastembed>=0.2.0` (descarga modelos open-source desde
  HuggingFace).
- **Texto**: `unidecode>=1.3.6`, `regex>=2023.8.8`.
- **Logging**: `loguru>=0.7.0`.
- **Frontend**: `streamlit>=1.36.0`.
- **Dev/test**: `pytest`, `pytest-asyncio`, `black`, `isort`.

> El cross-encoder opcional (`sentence-transformers`) **no** está en
> `requirements.txt`. Si quieres activar `ENABLE_CROSS_ENCODER_RERANK=true`,
> instálalo manualmente: `pip install sentence-transformers`.

### 2.5 Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tu editor preferido si necesitas ajustar algo
```

Variables relevantes (extraídas de `.env.example` y `config/settings.py`):

| Variable | Default | Descripción |
|---|---|---|
| `QDRANT_HOST` | `localhost` | Host de Qdrant (`qdrant` si lo corres por docker-compose y el cliente está dentro del compose). |
| `QDRANT_PORT` | `6333` | Puerto HTTP de Qdrant. |
| `QDRANT_GRPC_PORT` | `6334` | Puerto gRPC de Qdrant. |
| `QDRANT_API_KEY` | *(vacío)* | API key (vacía para Qdrant local). |
| `QDRANT_COLLECTION_NAME` | `real_estate_properties` | Colección base. |
| `QDRANT_COLLECTION_ALIAS` | `real_estate_properties_current` | Alias activo en producción. |
| `QDRANT_COLLECTION_VERSION_SUFFIX` | `v2` | Sufijo para colecciones versionadas (ej. `real_estate_properties_v2`). |
| `BATCH_SIZE` | `1000` | Tamaño de batch del ETL. |
| `MAX_WORKERS` | `4` | Threads paralelos del ETL. |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Modelo FastEmbed. Debe estar soportado por FastEmbed (ver `python check_models.py`). |
| `EMBEDDING_DIMENSION` | `1024` | Debe coincidir con la salida del modelo. Si difiere, el embedder lo corrige automáticamente y avisa. |
| `TOP_K_FINAL` | `5` | Resultados finales devueltos al usuario. |
| `TOP_K_RETRIEVAL` | `100` | Candidatos recuperados antes del rerank. |
| `SCORE_THRESHOLD` | `0.0` | Umbral mínimo de score denso. |
| `ENABLE_TWO_STAGE_RANKING` | `false` | Activa retrieval amplio + rerank. |
| `ENABLE_CROSS_ENCODER_RERANK` | `false` | Activa cross-encoder (requiere `sentence-transformers`). |
| `ENABLE_SPARSE_DENSE_HYBRID` | `false` | Activa búsqueda híbrida densa + sparse en Qdrant. |
| `HYBRID_ALPHA` | `0.7` | Peso del score denso en la combinación híbrida. |
| `SPARSE_HASH_SPACE` | `1048576` | Tamaño del hash space del sparse vectorizer. |
| `SPARSE_MIN_TOKEN_LENGTH` | `3` | Longitud mínima de token para el sparse. |
| `ENABLE_LLM_BATCH_ENRICHMENT` | `false` | Enriquecimiento con LLM en el ETL. |
| `LLM_ENRICHMENT_PROVIDER` | `openai` | Proveedor del LLM. |
| `LLM_ENRICHMENT_MODEL` | `gpt-4o-mini` | Modelo LLM (también usado por `eval_relevance.py --use-llm-judge`). |
| `LLM_ENRICHMENT_API_KEY` | *(vacío)* | API key del proveedor LLM. |
| `ENABLE_QUERY_TELEMETRY` | `true` | Expone telemetría por etapa en cada query. |
| `CSV_FILE_PATH` | `./lyon_balmaceda_scraper.csv` | CSV fuente del ETL y de la auditoría. |
| `LOG_LEVEL` | `INFO` | Nivel de logging. |

### 2.6 Levantar Qdrant

#### Opción A — Solo Qdrant (recomendado para dev local)

```bash
docker run -d \
  -p 6333:6333 -p 6334:6334 \
  --name qdrant \
  qdrant/qdrant:latest
```

#### Opción B — Stack completo con docker-compose

```bash
docker-compose up -d
```

Esto levanta:

- `realstate-qdrant` (Qdrant en `6333/6334`, con volumen persistente
  `qdrant_data`).
- `realstate-chat` (Streamlit en `8501`, con `QDRANT_HOST=qdrant` apuntando al
  servicio interno y `EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-es`,
  dimensión `768`, según el `docker-compose.yml`).

> Si vas a correr Streamlit en tu máquina (no en Docker), usa la **Opción A** y
> ejecuta el frontend con tu venv (`streamlit run …`). Si usas la **Opción B**,
> ten presente que el contenedor `chat` usa otro modelo y otra dimensión que
> los defaults de `.env.example`; ajusta tu colección en consecuencia o
> sobreescribe esas variables en el `docker-compose.yml`.

### 2.7 (Opcional) Cargar datos con el ETL

Si la colección está vacía, ejecuta el pipeline:

```bash
python -m src.etl.main             # con confirmación interactiva
# o
python -m src.etl.main -y          # sin confirmación
# o, para rebuild limpio:
python -m src.etl.main --recreate
```

Requisitos:

- `CSV_FILE_PATH` apunta a un archivo existente (ej.
  `./lyon_balmaceda_scraper.csv`).
- Qdrant está corriendo (paso 2.6).
- La primera ejecución descargará el modelo de embeddings (`BAAI/bge-m3` por
  defecto) en `./models_cache/`. Esto puede tardar varios minutos.

### 2.8 Lanzar el frontend de chat

```bash
streamlit run scripts/chat_search_frontend.py
```

Abre <http://localhost:8501> en tu navegador.

### 2.9 Resumen de comandos (modo express)

```bash
# 1. Entorno
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Config
cp .env.example .env

# 3. Qdrant
docker run -d -p 6333:6333 -p 6334:6334 --name qdrant qdrant/qdrant:latest

# 4. (Opcional) Cargar datos
python -m src.etl.main -y

# 5. Frontend
streamlit run scripts/chat_search_frontend.py
```

### 2.10 Errores frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: pydantic_settings` (u otro módulo) | Estás usando el `python3` del sistema en vez del venv. | Activa el venv (`source .venv/bin/activate`) o usa `.venv/bin/python -m src.etl.main` y `.venv/bin/streamlit run …`. |
| `ModuleNotFoundError: streamlit` | Dependencias no instaladas o no estás en el venv. | `pip install -r requirements.txt` y `source .venv/bin/activate`. |
| `Warning: to view this Streamlit app … run with streamlit run` | Ejecutaste `python scripts/chat_search_frontend.py`. | Usar **`streamlit run scripts/chat_search_frontend.py`**. |
| Error de conexión a Qdrant / sin resultados | Qdrant no está corriendo o `QDRANT_HOST`/`QDRANT_PORT` mal configurados. | Levantar Qdrant (paso 2.6) y revisar `.env`. |
| Colección vacía | No se ha ejecutado el ETL aún. | `python -m src.etl.main -y` (paso 2.7). |
| Dimensión del modelo no coincide | `EMBEDDING_MODEL` y `EMBEDDING_DIMENSION` no se corresponden. | El embedder corrige `embedding_dimension` en runtime, pero la colección debe haberse creado con la dimensión correcta. Si cambiaste de modelo, recrea la colección con `python -m src.etl.main --recreate`. |
| Cross-encoder deshabilitado en logs | `sentence-transformers` no está instalado. | `pip install sentence-transformers` si quieres `ENABLE_CROSS_ENCODER_RERANK=true`. |

---

## 3. Diagrama de conexiones externas

El siguiente diagrama Mermaid muestra cómo se conectan los componentes:
usuario → frontend / scripts CLI → servicios (embedder, sparse, reranker,
search pipeline) → Qdrant; el ETL en paralelo carga datos desde el CSV.

```mermaid
flowchart LR
    %% Actores
    User([👤 Usuario / Navegador])
    Dev([🛠️ Operador / Dev])

    %% Subgrafo: scripts y servicios Python locales
    subgraph LP["Local: Python (venv)"]
        direction TB

        subgraph Frontend["Frontend Streamlit"]
            Chat["scripts/chat_search_frontend.py<br/>(streamlit run :8501)"]
        end

        subgraph CLI["Scripts CLI de búsqueda y demo"]
            SemSearch["scripts/semantic_search.py"]
            DemoSearch["demo_search.py"]
            TestSem["test_semantic_search.py"]
        end

        subgraph Eval["Evaluación y baseline"]
            Baseline["scripts/capture_baseline.py"]
            EvalRel["scripts/eval_relevance.py"]
        end

        subgraph Maint["Mantenimiento BD vectorial"]
            CleanDB["scripts/clean_vector_db.py"]
            CheckURL["scripts/check_property_by_url.py"]
        end

        subgraph DebugAudit["Debug y auditoría"]
            Audit["scripts/audit_string_cleaning.py"]
            DbgQ["debug_qdrant.py"]
            DbgP["debug_payload.py"]
            DbgCSV["debug_csv.py / debug_csv_parsing.py"]
            ChkModels["check_models.py"]
            TstClean["test_cleaning.py / test_cleaning_issue.py"]
        end

        subgraph ETL["ETL"]
            ETLMain["python -m src.etl.main<br/>(src/etl/main.py)"]
            Loader["src/etl/loader.py"]
            Cleaner["src/etl/cleaner.py"]
        end

        subgraph Services["src/services"]
            Pipeline["search_pipeline.py"]
            Embedder["embedder.py<br/>(FastEmbed singleton)"]
            Sparse["sparse_embedder.py<br/>(hash-based, local)"]
            Reranker["reranker.py<br/>(opcional, CrossEncoder)"]
        end

        DBClient["src/db/client.py<br/>(QdrantManager)"]
        Settings["config/settings.py<br/>(.env)"]
    end

    %% Subgrafo: Docker local (Qdrant)
    subgraph Docker["Local: Docker"]
        Qdrant[("Qdrant<br/>HTTP :6333 · gRPC :6334<br/>colección + alias<br/>vectores: dense + sparse")]
    end

    %% Subgrafo: Externo
    subgraph Ext["Externo (Internet)"]
        HF[("HuggingFace Hub<br/>descarga modelos")]
        OpenAI[("OpenAI API<br/>opcional<br/>chat/completions")]
    end

    %% Subgrafo: Filesystem
    subgraph FS["Filesystem"]
        CSV[("CSV fuente<br/>CSV_FILE_PATH<br/>(lyon_balmaceda_scraper.csv)")]
        ModelsCache[("./models_cache/<br/>pesos del modelo")]
        EvalData[("scripts/eval_data/<br/>golden_queries.json<br/>baseline_results.json<br/>eval_report.json")]
        AuditOut[("audit_cleaning_report.csv / .md")]
        Logs[("etl_pipeline.log")]
    end

    %% Usuario y operador
    User -- HTTP :8501 --> Chat
    Dev -- ejecuta CLI --> SemSearch
    Dev -- ejecuta CLI --> DemoSearch
    Dev -- ejecuta CLI --> TestSem
    Dev -- ejecuta CLI --> Baseline
    Dev -- ejecuta CLI --> EvalRel
    Dev -- ejecuta CLI --> CleanDB
    Dev -- ejecuta CLI --> CheckURL
    Dev -- ejecuta CLI --> Audit
    Dev -- ejecuta CLI --> DbgQ
    Dev -- ejecuta CLI --> DbgP
    Dev -- ejecuta CLI --> DbgCSV
    Dev -- ejecuta CLI --> ChkModels
    Dev -- ejecuta CLI --> TstClean
    Dev -- ejecuta CLI --> ETLMain

    %% Configuración
    Settings -. lee .env .-> Chat
    Settings -. lee .env .-> SemSearch
    Settings -. lee .env .-> ETLMain
    Settings -. lee .env .-> Pipeline
    Settings -. lee .env .-> DBClient

    %% Frontend y scripts -> pipeline
    Chat --> Pipeline
    SemSearch --> Pipeline
    Baseline --> Pipeline
    EvalRel --> Pipeline

    %% Demo / tests usan embedder + db client directamente
    DemoSearch --> Embedder
    DemoSearch --> DBClient
    TestSem --> Embedder
    TestSem --> DBClient
    DbgP --> Embedder
    DbgP --> DBClient

    %% Pipeline orquesta servicios y db
    Pipeline --> Embedder
    Pipeline --> Sparse
    Pipeline --> Reranker
    Pipeline --> DBClient

    %% Mantenimiento y debugging Qdrant
    CleanDB --> DBClient
    CheckURL --> DBClient
    DbgQ --> DBClient

    %% ETL
    ETLMain --> Loader
    Loader --> Cleaner
    Loader --> Embedder
    Loader --> Sparse
    Loader --> DBClient

    %% Auditoría: usa cleaner/loader sin tocar Qdrant
    Audit --> Loader
    Audit --> Cleaner
    TstClean --> Cleaner

    %% DB client <-> Qdrant
    DBClient -- HTTP/gRPC --> Qdrant

    %% Embedder y modelos externos
    Embedder -- "carga / descarga<br/>BAAI/bge-m3" --> ModelsCache
    Embedder -- "primera vez<br/>(HTTPS)" --> HF
    Reranker -- "opcional<br/>jinaai/jina-reranker-v2" --> HF
    ChkModels -- catálogo --> HF

    %% LLM externo (opcional)
    EvalRel -- "opcional<br/>--use-llm-judge" --> OpenAI

    %% Filesystem
    Loader -- lee --> CSV
    Audit -- lee --> CSV
    DbgCSV -- lee --> CSV
    TstClean -- lee --> CSV
    ETLMain -- escribe --> Logs
    Audit -- escribe --> AuditOut
    Baseline -- escribe --> EvalData
    EvalRel -- escribe --> EvalData

    %% Estilos
    classDef external fill:#fde68a,stroke:#a16207,color:#111;
    classDef docker fill:#bae6fd,stroke:#075985,color:#111;
    classDef fs fill:#e5e7eb,stroke:#374151,color:#111;
    classDef python fill:#dcfce7,stroke:#166534,color:#111;
    class HF,OpenAI external;
    class Qdrant docker;
    class CSV,ModelsCache,EvalData,AuditOut,Logs fs;
    class Chat,SemSearch,DemoSearch,TestSem,Baseline,EvalRel,CleanDB,CheckURL,Audit,DbgQ,DbgP,DbgCSV,ChkModels,TstClean,ETLMain,Loader,Cleaner,Pipeline,Embedder,Sparse,Reranker,DBClient,Settings python;
```

### Notas sobre las conexiones del diagrama

- **HuggingFace Hub** solo se contacta la primera vez (o cuando cambia
  `EMBEDDING_MODEL`) para descargar pesos de FastEmbed o del cross-encoder.
  Una vez cacheados en `./models_cache/`, todo es local.
- **OpenAI** es opcional: solo se usa desde `scripts/eval_relevance.py
  --use-llm-judge` (y, si se activara, desde el enriquecimiento LLM del ETL,
  que está deshabilitado por default).
- **Qdrant** se asume local en Docker (`6333` HTTP, `6334` gRPC). En
  `docker-compose.yml` el servicio `chat` (Streamlit en contenedor) usa
  `QDRANT_HOST=qdrant` para hablar con el contenedor `realstate-qdrant`.
- **`models_cache/`** y **`etl_pipeline.log`** se crean en la raíz del
  proyecto; añádelos a tu `.gitignore` si aún no están.
- Los archivos en **`scripts/eval_data/`** son entradas/salidas de la
  evaluación: `golden_queries.json` (entrada), `baseline_results.json` y
  `eval_report.json` (salidas).

