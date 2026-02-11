"""
ETL Pipeline Loader
==================

Batch processing pipeline for loading real estate data into Qdrant.
"""

import uuid
import sys
from typing import Iterator, List, Dict, Any
import pandas as pd
from pathlib import Path
from loguru import logger
from tqdm import tqdm

from qdrant_client.models import PointStruct

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from src.db.client import qdrant
from src.services.embedder import embedder
from src.etl.cleaner import DataCleaner


class ETLLoader:
    """Main ETL pipeline for processing and loading real estate data."""
    
    def __init__(self, csv_path: Path = None, batch_size: int = None):
        self.csv_path = csv_path or settings.csv_file_path
        self.batch_size = batch_size or settings.batch_size
        self.collection_name = settings.qdrant_collection_name
        
        # Initialize components
        self.cleaner = DataCleaner()
        
        # Stats tracking
        self.stats = {
            "total_processed": 0,
            "total_embedded": 0,
            "total_uploaded": 0,
            "failed_records": 0,
            "batches_processed": 0,
        }
    
    def setup_collection(self) -> bool:
        """Initialize Qdrant collection for the pipeline."""
        logger.info(f"Setting up collection: {self.collection_name}")
        
        # Ensure embedder is initialized to get correct dimension
        embedder.model  # This triggers initialization
        
        success = qdrant.create_collection(
            collection_name=self.collection_name,
            vector_size=settings.embedding_dimension,
        )
        
        if success:
            # Get and log collection info
            info = qdrant.get_collection_info(self.collection_name)
            if info:
                logger.info(f"Collection setup complete. Vectors config: {info.config.params.vectors}")
        
        return success
    
    def load_csv_chunks(self) -> Iterator[pd.DataFrame]:
        """Load CSV in chunks for memory efficiency."""
        logger.info(f"Loading CSV from: {self.csv_path}")
        
        if not Path(self.csv_path).exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        
        try:
            # Read in chunks with special handling for malformed CSV
            chunk_reader = pd.read_csv(
                self.csv_path,
                chunksize=self.batch_size,
                low_memory=False,
                on_bad_lines='skip',  # Skip problematic lines
                encoding='utf-8',
            )
            
            for chunk_idx, chunk in enumerate(chunk_reader):
                logger.debug(f"Loaded chunk {chunk_idx + 1} with {len(chunk)} rows")
                yield chunk
                
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            raise
    
    def process_batch(self, df_batch: pd.DataFrame) -> List[PointStruct]:
        """Process a batch of records into Qdrant points."""
        points = []
        batch_texts = []
        batch_metadata = []
        valid_indices = []
        
        # First pass: clean data and prepare texts
        for idx, row in df_batch.iterrows():
            try:
                # Create semantic text blob
                semantic_text = self.cleaner.create_semantic_blob(row)
                
                # Prepare metadata
                metadata = self.cleaner.prepare_metadata(row)
                
                # Only process if we have meaningful semantic content
                if len(semantic_text.strip()) > 3:  # Relaxed from 10 to 3 characters
                    batch_texts.append(semantic_text)
                    batch_metadata.append(metadata)
                    valid_indices.append(idx)
                else:
                    logger.warning(f"Skipping row {idx}: insufficient semantic content (only {len(semantic_text.strip())} chars)")
                    self.stats["failed_records"] += 1
                    
            except Exception as e:
                logger.error(f"Failed to process row {idx}: {e}")
                self.stats["failed_records"] += 1
                continue
        
        if not batch_texts:
            logger.warning("No valid texts in batch")
            return points
        
        # Generate embeddings for the batch
        logger.info(f"Generating embeddings for {len(batch_texts)} texts")
        batch_embeddings = embedder.embed_batch(batch_texts, batch_size=32)
        
        if len(batch_embeddings) != len(batch_texts):
            logger.error(f"Embedding count mismatch: {len(batch_embeddings)} vs {len(batch_texts)}")
            return points
        
        # Create Qdrant points
        for i, (embedding, metadata) in enumerate(zip(batch_embeddings, batch_metadata)):
            try:
                # Generate unique ID (using original index for consistency)
                point_id = str(uuid.uuid4())
                
                # Create point
                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=metadata,
                )
                
                points.append(point)
                self.stats["total_embedded"] += 1
                
            except Exception as e:
                logger.error(f"Failed to create point for record {i}: {e}")
                self.stats["failed_records"] += 1
                continue
        
        logger.success(f"Prepared {len(points)} points for upload")
        return points
    
    def upload_batch(self, points: List[PointStruct]) -> bool:
        """Upload a batch of points to Qdrant."""
        if not points:
            return True
        
        try:
            success = qdrant.upsert_points(self.collection_name, points)
            if success:
                self.stats["total_uploaded"] += len(points)
                return True
            else:
                logger.error("Failed to upload batch")
                return False
                
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False
    
    def run_pipeline(self) -> Dict[str, Any]:
        """Run the complete ETL pipeline."""
        logger.info("🚀 Starting ETL Pipeline")
        
        # Setup collection
        if not self.setup_collection():
            raise RuntimeError("Failed to setup Qdrant collection")
        
        # Process CSV in batches
        try:
            for batch_idx, df_batch in enumerate(self.load_csv_chunks()):
                logger.info(f"Processing batch {batch_idx + 1} ({len(df_batch)} records)")
                
                # Process the batch
                points = self.process_batch(df_batch)
                self.stats["total_processed"] += len(df_batch)
                
                # Upload to Qdrant
                if points:
                    upload_success = self.upload_batch(points)
                    if not upload_success:
                        logger.error(f"Failed to upload batch {batch_idx + 1}")
                        # Continue processing other batches
                
                self.stats["batches_processed"] += 1
                
                # Log progress
                logger.info(f"Batch {batch_idx + 1} complete. Progress: {self.get_progress_summary()}")
        
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
        
        # Final summary
        logger.success("🎉 ETL Pipeline completed successfully!")
        final_stats = self.get_final_stats()
        
        for key, value in final_stats.items():
            logger.info(f"{key}: {value}")
        
        return final_stats
    
    def get_progress_summary(self) -> str:
        """Get a brief progress summary."""
        return (
            f"Processed: {self.stats['total_processed']}, "
            f"Embedded: {self.stats['total_embedded']}, "
            f"Uploaded: {self.stats['total_uploaded']}, "
            f"Failed: {self.stats['failed_records']}"
        )
    
    def get_final_stats(self) -> Dict[str, Any]:
        """Get comprehensive final statistics."""
        success_rate = (
            (self.stats["total_uploaded"] / self.stats["total_processed"]) * 100
            if self.stats["total_processed"] > 0 else 0
        )
        
        return {
            "Total Records Processed": self.stats["total_processed"],
            "Successfully Embedded": self.stats["total_embedded"],
            "Successfully Uploaded": self.stats["total_uploaded"],
            "Failed Records": self.stats["failed_records"],
            "Batches Processed": self.stats["batches_processed"],
            "Success Rate": f"{success_rate:.1f}%",
            "Collection Name": self.collection_name,
            "Embedding Model": settings.embedding_model,
            "Vector Dimension": settings.embedding_dimension,
        }