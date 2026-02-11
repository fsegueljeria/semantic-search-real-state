#!/usr/bin/env python3
"""
Debug search results payload
"""

import sys
from pathlib import Path

# Add src to Python path
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from services.embedder import EmbeddingService
from db.client import QdrantManager
from config.settings import settings

def debug_search():
    """Debug search results structure"""
    try:
        # Initialize services
        embedder = EmbeddingService()
        qdrant = QdrantManager()
        
        # Simple search
        query = "apartamento moderno"
        print(f"Searching for: {query}")
        
        query_vector = embedder.embed_text(query)
        results = qdrant.search_similar(
            query_vector=query_vector,
            collection_name=settings.qdrant_collection_name,
            limit=1
        )
        
        if results:
            result = results[0]
            print(f"\nResult type: {type(result)}")
            print(f"Result attributes: {dir(result)}")
            
            if hasattr(result, 'payload'):
                print(f"\nPayload: {result.payload}")
                print(f"Payload keys: {list(result.payload.keys()) if result.payload else 'None'}")
            
            if hasattr(result, 'score'):
                print(f"Score: {result.score}")
                
            if hasattr(result, 'id'):
                print(f"ID: {result.id}")
                
        else:
            print("No results found")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_search()