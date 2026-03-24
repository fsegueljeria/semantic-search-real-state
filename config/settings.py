"""
Application Settings
===================

Centralized configuration management using Pydantic.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class ETLSettings(BaseSettings):
    """ETL Pipeline Configuration."""
    
    # Data Source
    csv_file_path: Path = Field(
        default="./lyon_balmaceda_scraper.csv",
        description="Path to the CSV file to process"
    )
    
    # Processing Configuration
    batch_size: int = Field(
        default=1000,
        description="Number of records to process in each batch"
    )
    max_workers: int = Field(
        default=4,
        description="Maximum number of worker threads for parallel processing"
    )
    
    # Embedding Configuration
    embedding_model: str = Field(
        default="BAAI/bge-large-en-v1.5",
        description="Name of the embedding model to use"
    )
    embedding_dimension: int = Field(
        default=1024,
        description="Dimension of the embedding vectors"
    )
    
    # Qdrant Configuration
    qdrant_host: str = Field(default="localhost", description="Qdrant server host")
    qdrant_port: int = Field(default=6333, description="Qdrant HTTP port")
    qdrant_grpc_port: int = Field(default=6334, description="Qdrant gRPC port")
    qdrant_api_key: Optional[str] = Field(default=None, description="Qdrant API key")
    qdrant_collection_name: str = Field(
        default="real_estate_properties",
        description="Name of the Qdrant collection"
    )
    qdrant_collection_alias: str = Field(
        default="real_estate_properties_current",
        description="Alias used as active production collection"
    )
    qdrant_collection_version_suffix: str = Field(
        default="v2",
        description="Version suffix used when creating new collection versions"
    )

    # Search Pipeline Configuration
    top_k_final: int = Field(default=5, description="Final results returned to user")
    top_k_retrieval: int = Field(default=100, description="Candidates retrieved from vector DB")
    score_threshold: float = Field(default=0.0, description="Minimum dense score accepted")
    enable_two_stage_ranking: bool = Field(
        default=False,
        description="Enable two-stage retrieval + reranking pipeline"
    )
    enable_cross_encoder_rerank: bool = Field(
        default=False,
        description="Enable cross-encoder reranking when available"
    )
    enable_sparse_dense_hybrid: bool = Field(
        default=False,
        description="Enable hybrid dense+sparse score combination"
    )
    hybrid_alpha: float = Field(
        default=0.7,
        description="Weight for dense score in final blend (0-1)"
    )
    sparse_hash_space: int = Field(
        default=1048576,
        description="Hash space used by sparse hashing vectorizer"
    )
    sparse_min_token_length: int = Field(
        default=3,
        description="Minimum token length to include in sparse vectors"
    )

    # ETL Derived Metadata
    enable_llm_batch_enrichment: bool = Field(
        default=False,
        description="Use LLM for metadata enrichment during ETL"
    )
    llm_enrichment_provider: str = Field(
        default="openai",
        description="Provider for metadata enrichment"
    )
    llm_enrichment_model: str = Field(
        default="gpt-4o-mini",
        description="Model name for ETL metadata enrichment"
    )
    llm_enrichment_api_key: Optional[str] = Field(
        default=None,
        description="API key used by ETL enrichment provider"
    )

    # Optional online/online evaluation
    enable_query_telemetry: bool = Field(
        default=True,
        description="Capture and expose per-stage query telemetry"
    )
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = ETLSettings()