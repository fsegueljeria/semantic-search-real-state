"""
Embedding Service
================

High-performance text embedding using BAAI/bge-m3 via FastEmbed.
"""

import sys
from typing import List, Union, Optional
from pathlib import Path
import threading
from loguru import logger

from fastembed import TextEmbedding

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings


class EmbeddingService:
    """Singleton embedding service using BAAI/bge-m3."""
    
    _instance: Optional["EmbeddingService"] = None
    _model: Optional[TextEmbedding] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _initialize_model(self) -> None:
        """Initialize the embedding model (thread-safe)."""
        with self._lock:
            if self._model is None:
                logger.info(f"Initializing embedding model: {settings.embedding_model}")
                
                try:
                    self._model = TextEmbedding(
                        model_name=settings.embedding_model,
                        max_length=512,  # Optimal for real estate descriptions
                        cache_dir=Path("./models_cache"),  # Local cache for model weights
                    )
                    
                    # Test the model with a simple text
                    test_embedding = list(self._model.embed(["test"]))[0]
                    actual_dim = len(test_embedding)
                    
                    if actual_dim != settings.embedding_dimension:
                        logger.warning(
                            f"Model dimension ({actual_dim}) differs from config ({settings.embedding_dimension})"
                        )
                        # Update settings to match actual dimension
                        settings.embedding_dimension = actual_dim
                    
                    logger.success(
                        f"Model initialized successfully. Dimension: {actual_dim}"
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to initialize model: {e}")
                    raise
    
    @property
    def model(self) -> TextEmbedding:
        """Get the embedding model, initializing if necessary."""
        if self._model is None:
            self._initialize_model()
        return self._model
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * settings.embedding_dimension
        
        try:
            # Clean the text
            cleaned_text = self._preprocess_text(text)
            
            # Generate embedding
            embedding_generator = self.model.embed([cleaned_text])
            embedding = list(embedding_generator)[0]
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {e}")
            # Return zero vector as fallback
            return [0.0] * settings.embedding_dimension
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently."""
        if not texts:
            return []
        
        try:
            # Preprocess all texts
            cleaned_texts = [self._preprocess_text(text) for text in texts]
            
            # Process in batches for memory efficiency
            all_embeddings = []
            
            for i in range(0, len(cleaned_texts), batch_size):
                batch = cleaned_texts[i:i + batch_size]
                
                # Generate embeddings for the batch
                batch_embeddings = list(self.model.embed(batch))
                
                # Convert to lists
                batch_embeddings = [emb.tolist() for emb in batch_embeddings]
                all_embeddings.extend(batch_embeddings)
                
                logger.info(f"Processed embeddings batch {i//batch_size + 1} ({len(batch)} texts)")
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            # Return zero vectors as fallback
            return [[0.0] * settings.embedding_dimension] * len(texts)
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for embedding."""
        if not text:
            return ""
        
        # Convert to string if not already
        text = str(text)
        
        # Remove extra whitespace and normalize
        text = " ".join(text.split())
        
        # Truncate if too long (model has max_length limit)
        max_chars = 2000  # Conservative limit for 512 tokens
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
            logger.debug(f"Truncated text to {max_chars} characters")
        
        return text
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_name": settings.embedding_model,
            "dimension": settings.embedding_dimension,
            "max_length": getattr(self.model, "max_length", "unknown"),
            "is_initialized": self._model is not None,
        }


# Global instance
embedder = EmbeddingService()