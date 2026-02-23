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
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = ETLSettings()