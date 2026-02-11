#!/usr/bin/env python3
"""
Quick Semantic Search Test
Prueba rápida de búsqueda semántica para propiedades inmobiliarias.
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

def format_property_result(hit, index):
    """Format search result for display"""
    score = hit.score
    payload = hit.payload
    
    print(f"\n#{index} 🏠 Relevancia: {score:.4f}")
    print(f"📍 Comuna: {payload.get('comuna', 'No especificada')}")
    print(f"🏘️  Barrio: {payload.get('barrio', 'No especificado')}")
    print(f"💰 Precio UF: {payload.get('precio_uf', 0)}")
    print(f"🛏️  Dormitorios: {payload.get('dormitorios', 'N/A')}")
    print(f"🚿 Baños: {payload.get('banios', 'N/A')}")
    print(f"📐 Área Total: {payload.get('m2_total', 'N/A')} m²")
    print(f"📐 Área Útil: {payload.get('m2_util', 'N/A')} m²")
    print(f"🚗 Estacionamientos: {payload.get('estacionamiento', 'N/A')}")
    print(f"📦 Bodegas: {payload.get('bodega', 'N/A')}")
    
    # Show title and description
    titulo = payload.get('titulo', '')
    if titulo:
        print(f"📝 Título: {titulo[:100]}...")
    
    descripcion = payload.get('descripcion', '')
    if descripcion:
        print(f"📋 Descripción: {descripcion[:150]}...")
    
    print("-" * 60)

def search_properties(query, top_k=5):
    """Perform semantic search"""
    try:
        # Initialize services
        print("Inicializando servicios...")
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
            format_property_result(hit, i)
            
    except Exception as e:
        print(f"❌ Error en la búsqueda: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function - run demo searches"""
    print("\n🏠 DEMOSTRACIÓN DE BÚSQUEDA SEMÁNTICA INMOBILIARIA")
    print("=" * 60)
    
    # Check collection status
    try:
        qdrant = QdrantManager()
        collection_info = qdrant.client.get_collection(settings.qdrant_collection_name)
        vectors_count = collection_info.points_count if hasattr(collection_info, 'points_count') else "Unknown"
        
        print(f"✅ Colección: {settings.qdrant_collection_name}")
        print(f"📊 Vectores disponibles: {vectors_count}")
        print(f"🤖 Modelo: {settings.embedding_model}")
        
        if vectors_count == 0 or vectors_count == "Unknown":
            print("\n❌ No hay vectores disponibles.")
            return
            
    except Exception as e:
        print(f"❌ Error conectando a Qdrant: {e}")
        return
    
    # Demo searches
    demo_queries = [
        "apartamento moderno con vista al mar",
        "casa familiar con jardín", 
        "propiedad de lujo",
        "departamento céntrico",
        "casa económica bajo 200 millones"
    ]
    
    print("\n" + "="*60)
    print("EJECUTANDO BÚSQUEDAS DE DEMOSTRACIÓN")
    print("="*60)
    
    for i, query in enumerate(demo_queries, 1):
        print(f"\n\n{'='*60}")
        print(f"BÚSQUEDA {i}/{len(demo_queries)}")
        print(f"{'='*60}")
        
        search_properties(query, top_k=3)
        
        if i < len(demo_queries):
            input("\nPresiona Enter para continuar con la siguiente búsqueda...")

if __name__ == "__main__":
    main()