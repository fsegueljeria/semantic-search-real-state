"""
Deep debug of CSV parsing
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd

# Read with different options to handle the complex quoting
csv_path = "lyon_balmaceda_scraper.csv"

print("=== RAW CSV INSPECTION ===")

# First, read raw lines to see actual content
with open(csv_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print(f"Header: {lines[0].strip()}")
print()
print(f"First data row (raw):")
print(f"{lines[1][:200]}...")
print()

# Try different pandas read options
try:
    df1 = pd.read_csv(csv_path, nrows=3, quoting=1)  # QUOTE_ALL
    print(f"Method 1 (QUOTE_ALL): {len(df1)} rows loaded")
    print(f"TITULO_PROPIEDAD sample: {df1['TITULO_PROPIEDAD'].iloc[0]}")
    print(f"DESCRIPCION sample: {df1['DESCRIPCION'].iloc[0][:100]}...")
except Exception as e:
    print(f"Method 1 failed: {e}")

print()

try:
    df2 = pd.read_csv(csv_path, nrows=3, quoting=0)  # QUOTE_MINIMAL
    print(f"Method 2 (QUOTE_MINIMAL): {len(df2)} rows loaded")
    print(f"TITULO_PROPIEDAD sample: {df2['TITULO_PROPIEDAD'].iloc[0]}")
    print(f"DESCRIPCION sample: {df2['DESCRIPCION'].iloc[0][:100]}...")
except Exception as e:
    print(f"Method 2 failed: {e}")

print()

try:
    df3 = pd.read_csv(csv_path, nrows=3, quoting=2)  # QUOTE_NONNUMERIC
    print(f"Method 3 (QUOTE_NONNUMERIC): {len(df3)} rows loaded")
    print(f"TITULO_PROPIEDAD sample: {df3['TITULO_PROPIEDAD'].iloc[0]}")
    print(f"DESCRIPCION sample: {df3['DESCRIPCION'].iloc[0][:100]}...")
except Exception as e:
    print(f"Method 3 failed: {e}")

print()

try:
    df4 = pd.read_csv(csv_path, nrows=3, quoting=3)  # QUOTE_NONE
    print(f"Method 4 (QUOTE_NONE): {len(df4)} rows loaded")
    print(f"TITULO_PROPIEDAD sample: {df4['TITULO_PROPIEDAD'].iloc[0]}")
    print(f"DESCRIPCION sample: {df4['DESCRIPCION'].iloc[0][:100]}...")
except Exception as e:
    print(f"Method 4 failed: {e}")