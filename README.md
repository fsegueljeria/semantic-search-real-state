# Semantic Search ETL Pipeline

High-performance ETL system for processing real estate data and building a semantic search engine using Qdrant vector database and open-source embeddings.

## Features

- **High Performance**: Processes 500,000+ records efficiently using batch processing
- **Open Source Embeddings**: Uses BAAI/bge-m3 model for state-of-the-art multilingual understanding
- **Scalable Architecture**: Modular design with configurable batch sizes and parallel processing
- **Vector Search**: Optimized for Qdrant vector database with hybrid search capabilities
- **Chat Frontend**: Streamlit chat UI with property cards, photos and links

## Project Structure

```
semantic-search/
├── config/
│   ├── __init__.py
│   └── settings.py          # Centralized configuration
├── src/
│   ├── __init__.py
│   ├── db/
│   │   ├── __init__.py
│   │   └── client.py        # Qdrant client (to be implemented)
│   ├── etl/
│   │   ├── __init__.py
│   │   ├── cleaner.py       # Data cleaning utilities (to be implemented)
│   │   └── loader.py        # Batch processing pipeline (to be implemented)
│   └── services/
│       ├── __init__.py
│       └── embedder.py      # Embedding service (to be implemented)
├── .env.example             # Environment configuration template
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Modern Python packaging
└── lyon_balmaceda_scraper_summary.csv  # Source data
```

## Installation

1. Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment configuration:
```bash
cp .env.example .env
# Edit .env with your specific configuration
```

## Quick Start

1. Ensure Qdrant is running (Docker recommended):
```bash
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

2. (Optional) Run the ETL pipeline to load data (use the venv Python):
```bash
python -m src.etl.main   # with venv activated
# or: .venv/bin/python -m src.etl.main
```
3
3. Run the chat frontend — **use `streamlit run`** (do not run with `python script.py`):
```bash
streamlit run scripts/chat_search_frontend.py
```

Then open http://localhost:8501 in your browser.

**Guía detallada:** see [docs/SETUP.md](docs/SETUP.md) for a full step-by-step setup guide.

## Data Schema

The pipeline processes real estate data with the following key fields:
- `TITULO_PROPIEDAD`: Property title
- `DESCRIPCION`: Detailed property description  
- `COMUNA`, `BARRIO`: Location information
- `PRECIO_UF`: Price in UF (Unidad de Fomento)
- `M2_UTIL`, `M2_TOTAL`: Property dimensions
- `DORMITORIOS`, `BANIOS`: Room counts
- And 20+ additional metadata fields

## Configuration

Key settings in [config/settings.py](config/settings.py):

- **EMBEDDING_MODEL**: Configurable via `.env` (use a model supported by FastEmbed)
- **EMBEDDING_DIMENSION**: Must match your selected model output vector size
- **BATCH_SIZE**: 500 records per batch (adjustable)
- **QDRANT_COLLECTION_NAME**: `real_estate_properties`

## Next Steps

The following modules are ready to be implemented:
1. Vector database client (`src/db/client.py`)
2. Embedding service (`src/services/embedder.py`) 
3. Data cleaning pipeline (`src/etl/cleaner.py`)
4. Batch loader (`src/etl/loader.py`)
5. Main ETL orchestrator (`src/etl/main.py`)