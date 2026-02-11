#!/usr/bin/env python3
"""
Debug Qdrant Client methods
"""

import sys
from pathlib import Path

# Add src to Python path
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from db.client import QdrantManager
from qdrant_client import QdrantClient

def main():
    """Debug Qdrant client methods"""
    try:
        qdrant = QdrantManager()
        client = qdrant.client
        
        print("Qdrant client type:", type(client))
        print("\nAvailable methods:")
        
        # List search-related methods
        search_methods = [method for method in dir(client) if 'search' in method.lower()]
        print("Search methods:", search_methods)
        
        # List query-related methods
        query_methods = [method for method in dir(client) if 'query' in method.lower()]
        print("Query methods:", query_methods)
        
        # Check if we can access collection
        from config.settings import settings
        collection_name = settings.qdrant_collection_name
        
        print(f"\nCollection '{collection_name}' info:")
        collection_info = client.get_collection(collection_name)
        print(f"Points count: {collection_info.points_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()