"""
Quick script to check available embedding models in fastembed
"""
from fastembed import TextEmbedding

print("Available text embedding models:")
models = TextEmbedding.list_supported_models()

for i, model in enumerate(models[:10]):  # Show first 10
    print(f"- {model}")

# Look for BGE models specifically
print(f"\nTotal models available: {len(models)}")
print(f"\nFirst 20 models:")
for i, model in enumerate(models[:20]):
    print(f"  {i+1}. {model}")