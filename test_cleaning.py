"""
Test data cleaning functionality
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.etl.cleaner import DataCleaner

# Test with a few sample rows
csv_path = "lyon_balmaceda_scraper.csv"
df = pd.read_csv(csv_path, nrows=3, quoting=3, escapechar='\\', on_bad_lines='skip', encoding='utf-8')

print("=== TESTING DATA CLEANING ===")
print(f"Loaded {len(df)} rows")
print(f"Columns: {list(df.columns)}")
print()

cleaner = DataCleaner()

for idx, row in df.iterrows():
    print(f"--- Row {idx} ---")
    
    # Test semantic blob creation
    semantic_blob = cleaner.create_semantic_blob(row)
    print(f"Semantic blob length: {len(semantic_blob)}")
    print(f"First 100 chars: {semantic_blob[:100]}...")
    
    # Test metadata preparation
    metadata = cleaner.prepare_metadata(row)
    print(f"Metadata keys: {list(metadata.keys())}")
    print(f"Title: {metadata.get('titulo', 'N/A')}")
    print(f"Description preview: {metadata.get('descripcion', 'N/A')[:50]}...")
    print()