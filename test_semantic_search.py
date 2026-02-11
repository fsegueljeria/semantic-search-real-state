#!/usr/bin/env python3
"""
Semantic Search Test Script
Prueba la búsqueda semántica en la base de datos vectorial de propiedades inmobiliarias.
"""

import sys
import os
from pathlib import Path

# Add src to Python path
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from services.embedder import EmbeddingService
from db.client import QdrantManager
from config.settings import settings
import json

def format_property_result(hit):
    """Format search result for display"""
    score = hit.score
    payload = hit.payload
    
    print(f"\n🏠 Relevancia: {score:.4f}")
    print(f"📍 Ubicación: {payload.get('location', 'No especificada')}")
    print(f"💰 Precio: ${payload.get('price', 0):,}")
    print(f"🛏️  Habitaciones: {payload.get('bedrooms', 'N/A')}")
    print(f"🚿 Baños: {payload.get('bathrooms', 'N/A')}")
    print(f"📐 Área: {payload.get('total_area', 'N/A')} m²")
    
    # Show semantic text (truncated)
    semantic_text = payload.get('semantic_text', '')
    if semantic_text:
        print(f"📝 Descripción: {semantic_text[:200]}...")
    
    print("-" * 60)

def search_properties(query, top_k=5):
    """Perform semantic search"""
    try:
        # Initialize services
        embedder = EmbeddingService()
        qdrant = QdrantManager()
        
        print(f"\n🔍 Buscando: '{query}'")
        print("=" * 60)
        
        # Generate embedding for query
        print("Generando embedding para la consulta...")
        query_vector = embedder.embed_text(query)
        
        # Search in Qdrant
        print("Realizando búsqueda semántica...")
        results = qdrant.search_similar(
            query_vector=query_vector,
            collection_name=settings.qdrant_collection_name,
            limit=top_k
        )
        
        if not results:
            print("❌ No se encontraron resultados")
            return
        
        print(f"✅ Se encontraron {len(results)} propiedades similares:")
        
        for i, hit in enumerate(results, 1):
            print(f"\n#{i}")
            format_property_result(hit)
            
    except Exception as e:
        print(f"❌ Error en la búsqueda: {e}")

def interactive_search():
    """Interactive search mode"""
    print("\n🏡 BÚSQUEDA SEMÁNTICA DE PROPIEDADES INMOBILIARIAS")
    print("=" * 60)
    print("Ejemplos de búsquedas:")
    print("- 'apartamento moderno con vista al mar'")
    print("- 'casa familiar cerca de colegios'")
    print("- 'propiedad de lujo bajo 400 millones'")
    print("- 'departamento céntrico con estacionamiento'")
    print("- 'casa con jardín y piscina'")
    print("=" * 60)
    
    while True:
        try:
            query = input("\n🔍 Ingresa tu búsqueda (o 'exit' para salir): ").strip()
            
            if query.lower() in ['exit', 'salir', 'quit']:
                print("¡Hasta luego! 👋")
                break
                
            if not query:
                print("Por favor ingresa una consulta válida.")
                continue
                
            search_properties(query)
            
        except KeyboardInterrupt:
            print("\n¡Hasta luego! 👋")
            break
        except Exception as e:
            print(f"Error: {e}")

def run_demo_searches():
    """Run predefined demo searches"""
    demo_queries = [
        "apartamento moderno con vista al mar",
        "casa familiar con jardín",
        "propiedad de lujo",
        "departamento céntrico",
        "casa económica",
        "modern apartment with ocean view",
        "family house with garden",
        "luxury property with pool"
    ]
    
    print("\n🎯 DEMOSTRACIÓN DE BÚSQUEDAS SEMÁNTICAS")
    print("=" * 60)
    
    for query in demo_queries:
        search_properties(query, top_k=3)
        input("\nPresiona Enter para continuar...")

def main():
    """Main function"""
    print("🏠 SISTEMA DE BÚSQUEDA SEMÁNTICA INMOBILIARIA")
    print("=" * 60)
    
    # Check if collection exists and has data
    try:
        qdrant = QdrantManager()
        
        collection_info = qdrant.client.get_collection(settings.qdrant_collection_name)
        vectors_count = collection_info.points_count if hasattr(collection_info, 'points_count') else "Unknown"
        
        print(f"✅ Colección: {settings.qdrant_collection_name}")
        print(f"📊 Vectores disponibles: {vectors_count}")
        print(f"🤖 Modelo de embeddings: {settings.embedding_model}")
        
        if vectors_count == 0 or vectors_count == "Unknown":
            print("\n❌ No hay vectores en la colección o no se pudo verificar. Ejecuta primero el ETL pipeline.")
            return
            
    except Exception as e:
        print(f"❌ Error conectando a Qdrant: {e}")
        return
    
    print("\nOpciones:")
    print("1. Búsqueda interactiva")
    print("2. Demo con búsquedas predefinidas")
    
    while True:
        try:
            choice = input("\nElige una opción (1-2): ").strip()
            
            if choice == "1":
                interactive_search()
                break
            elif choice == "2":
                run_demo_searches()
                break
            else:
                print("Opción inválida. Elige 1 o 2.")
                
        except KeyboardInterrupt:
            print("\n¡Hasta luego! 👋")
            break

if __name__ == "__main__":
    main()