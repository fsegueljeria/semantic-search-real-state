#!/usr/bin/env python3
"""
Búsqueda semántica de propiedades inmobiliarias
==============================================

Permite buscar propiedades usando lenguaje natural. El sistema encuentra propiedades
similares en significado, no solo por palabras exactas.

Uso:
  python scripts/semantic_search.py "casa en Buin con jardín"
  python scripts/semantic_search.py  # modo interactivo
"""

import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.db.client import qdrant
from src.services.embedder import embedder


def format_result(hit, index: int):
    """Formatea un resultado de búsqueda para mostrar."""
    # El resultado puede venir como objeto con .score y .payload o como dict
    if hasattr(hit, 'score'):
        score = hit.score
        payload = hit.payload if hasattr(hit, 'payload') else hit.get('payload', {})
    else:
        score = hit.get('score', 0.0)
        payload = hit.get('payload', hit)
    
    print(f"\n{'='*70}")
    print(f"#{index} 🏠 Relevancia: {score:.4f}")
    print(f"{'='*70}")
    
    # Información básica
    print(f"📍 Comuna: {payload.get('comuna', 'No especificada')}")
    if payload.get('barrio'):
        print(f"🏘️  Barrio: {payload.get('barrio')}")
    print(f"💰 Precio UF: {payload.get('precio_uf', 0):.2f}")
    print(f"🛏️  Dormitorios: {payload.get('dormitorios', 'N/A')}")
    print(f"🚿 Baños: {payload.get('banios', 'N/A')}")
    print(f"📐 Área Útil: {payload.get('m2_util', 'N/A')} m²")
    print(f"📐 Área Total: {payload.get('m2_total', 'N/A')} m²")
    print(f"🚗 Estacionamientos: {payload.get('estacionamiento', 'N/A')}")
    if payload.get('bodega', 0) > 0:
        print(f"📦 Bodegas: {payload.get('bodega')}")
    
    # Tipo y operación
    print(f"🏷️  Tipo: {payload.get('tipo_propiedad', 'N/A')} | Operación: {payload.get('operacion', 'N/A')}")
    
    # Título y descripción
    titulo = payload.get('titulo', '')
    if titulo:
        print(f"\n📝 Título: {titulo}")
    
    descripcion = payload.get('descripcion', '')
    if descripcion:
        # Mostrar primeros 200 caracteres
        desc_short = descripcion[:200] + "..." if len(descripcion) > 200 else descripcion
        print(f"\n📋 Descripción: {desc_short}")
    
    # URL
    url = payload.get('url', '')
    if url:
        print(f"\n🔗 URL: {url}")

    # Fotos
    images = payload.get('images', [])
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except json.JSONDecodeError:
            images = []
    if not isinstance(images, list):
        images = []

    if images:
        print(f"\n🖼️  Fotos ({len(images)}):")
        for img_idx, image_url in enumerate(images, 1):
            print(f"   {img_idx}. {image_url}")


def _normalize_text(text: str) -> str:
    """Lowercase + remove accents for robust matching."""
    text = text.lower()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", text).strip()


def _extract_uf_range(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae rango de UF desde la consulta.
    Soporta:
    - 'entre 20000 y 30000 uf'
    - '20000-30000 uf'
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)

    # Formato: entre X y Y uf
    match_between = re.search(
        r"entre\s+(\d+(?:[.,]\d+)?)\s+y\s+(\d+(?:[.,]\d+)?)\s*uf",
        qn,
    )
    if match_between:
        a = float(match_between.group(1).replace(",", "."))
        b = float(match_between.group(2).replace(",", "."))
        low, high = (a, b) if a <= b else (b, a)
        filters["precio_uf"] = {"gte": low, "lte": high}
        query_clean = re.sub(
            r"entre\s+\d+(?:[.,]\d+)?\s+y\s+\d+(?:[.,]\d+)?\s*uf",
            "",
            query_clean,
            flags=re.IGNORECASE,
        )
        return query_clean, filters

    # Formato: X-Y uf
    match_dash = re.search(
        r"(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)\s*uf",
        qn,
    )
    if match_dash:
        a = float(match_dash.group(1).replace(",", "."))
        b = float(match_dash.group(2).replace(",", "."))
        low, high = (a, b) if a <= b else (b, a)
        filters["precio_uf"] = {"gte": low, "lte": high}
        query_clean = re.sub(
            r"\d+(?:[.,]\d+)?\s*-\s*\d+(?:[.,]\d+)?\s*uf",
            "",
            query_clean,
            flags=re.IGNORECASE,
        )
        return query_clean, filters

    return query_clean, filters


def _extract_area_filters(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae filtros de superficie para m2 útiles y m2 totales.
    Soporta:
    - "mas de 250 metros utiles"
    - "menos de 400 m2 total"
    - "entre 200 y 350 mts utiles"
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)

    # Order matters: keep longer variants first to avoid partial matches ("mt" in "mtetros")
    metric = r"(?:mtetros?|metros?|mts?|m2)"
    kind_util = r"(?:util|utiles)"
    kind_total = r"(?:total|totales)"

    # Entre X y Y
    between_pattern = rf"entre\s+(\d+(?:[.,]\d+)?)\s+y\s+(\d+(?:[.,]\d+)?)\s*{metric}\s*(?:{kind_util}|{kind_total})?"
    m_between = re.search(between_pattern, qn)
    if m_between:
        a = float(m_between.group(1).replace(",", "."))
        b = float(m_between.group(2).replace(",", "."))
        low, high = (a, b) if a <= b else (b, a)
        matched_text = m_between.group(0)
        if re.search(kind_total, matched_text):
            filters["m2_total"] = {"gte": low, "lte": high}
        else:
            # default: útiles si no especifica
            filters["m2_util"] = {"gte": low, "lte": high}
        query_clean = re.sub(between_pattern, "", query_clean, flags=re.IGNORECASE)

    # Más de X
    more_pattern = rf"(?:mas\s+de|sobre|superior\s+a)\s+(\d+(?:[.,]\d+)?)\s*{metric}\s*(?:{kind_util}|{kind_total})?"
    m_more = re.search(more_pattern, qn)
    if m_more:
        val = float(m_more.group(1).replace(",", "."))
        matched_text = m_more.group(0)
        if re.search(kind_total, matched_text):
            filters["m2_total"] = {"gte": val}
        else:
            filters["m2_util"] = {"gte": val}
        query_clean = re.sub(more_pattern, "", query_clean, flags=re.IGNORECASE)

    # Menos de X
    less_pattern = rf"(?:menos\s+de|bajo|inferior\s+a)\s+(\d+(?:[.,]\d+)?)\s*{metric}\s*(?:{kind_util}|{kind_total})?"
    m_less = re.search(less_pattern, qn)
    if m_less:
        val = float(m_less.group(1).replace(",", "."))
        matched_text = m_less.group(0)
        if re.search(kind_total, matched_text):
            filters["m2_total"] = {"lte": val}
        else:
            filters["m2_util"] = {"lte": val}
        query_clean = re.sub(less_pattern, "", query_clean, flags=re.IGNORECASE)

    return query_clean, filters


def _extract_comuna_with_tolerance(query: str, comunas: list[str]) -> tuple[str, Dict[str, Any]]:
    """
    Detecta comuna exacta o aproximada (typos leves), p.ej. 'barnehea' -> 'Lo Barnechea'.
    """
    filters: Dict[str, Any] = {}
    query_clean = query

    qn = _normalize_text(query)
    q_tokens = qn.split()
    normalized_comunas = {c: _normalize_text(c) for c in comunas}

    # 1) Match exacto por substring normalizado
    for comuna, comuna_n in normalized_comunas.items():
        if comuna_n in qn:
            filters["comuna"] = comuna.title()
            query_clean = re.sub(rf"\b{re.escape(comuna)}\b", "", query_clean, flags=re.IGNORECASE)
            return query_clean, filters

    # 2) Match aproximado por ventanas de tokens (mismo largo de palabras)
    best_score = 0.0
    best_comuna: Optional[str] = None
    best_window: Optional[str] = None

    for comuna, comuna_n in normalized_comunas.items():
        n_words = len(comuna_n.split())
        if n_words == 0 or n_words > len(q_tokens):
            continue
        for i in range(len(q_tokens) - n_words + 1):
            window = " ".join(q_tokens[i : i + n_words])
            score = difflib.SequenceMatcher(None, window, comuna_n).ratio()
            if score > best_score:
                best_score = score
                best_comuna = comuna
                best_window = window

    # Umbral conservador para evitar falsos positivos
    if best_comuna and best_window and best_score >= 0.82:
        filters["comuna"] = best_comuna.title()
        query_clean = re.sub(rf"\b{re.escape(best_window)}\b", "", _normalize_text(query_clean), flags=re.IGNORECASE)
        return query_clean, filters

    return query_clean, filters


def extract_filters(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae filtros de metadata de la consulta y devuelve (query_limpia, filtros).
    Detecta: operacion (venta/arriendo), comuna, tipo, número de baños/dormitorios.
    Mantiene palabras descriptivas (jardín, piscina, etc.) para el embedding.
    """
    query_lower = query.lower()
    filters: Dict[str, Any] = {}
    words_to_remove = []
    
    # Operación: "venta" o "arriendo"
    if "venta" in query_lower or "vender" in query_lower or "comprar" in query_lower:
        filters["operacion"] = "Venta"
        words_to_remove.extend(["venta", "vender", "comprar", "en venta"])
    elif "arriendo" in query_lower or "arrendar" in query_lower or "alquiler" in query_lower:
        filters["operacion"] = "Arriendo"
        words_to_remove.extend(["arriendo", "arrendar", "alquiler", "en arriendo"])
    
    # Tipo de propiedad
    if "departamento" in query_lower or "depto" in query_lower or "apartamento" in query_lower:
        filters["tipo_propiedad"] = "departamento"
        words_to_remove.extend(["departamento", "depto", "apartamento"])
    elif "casa" in query_lower:
        filters["tipo_propiedad"] = "casa"
        words_to_remove.append("casa")
    
    # Comuna (buscar patrones comunes + typo tolerance)
    comunas_comunes = [
        "lo barnechea", "las condes", "providencia", "ñuñoa", "santiago",
        "buin", "colina", "chicureo", "la florida", "maipú", "puente alto"
    ]
    query, comuna_filter = _extract_comuna_with_tolerance(query, comunas_comunes)
    if "comuna" in comuna_filter:
        filters.update(comuna_filter)
    
    # Número de baños
    banios_match = re.search(r'\b(\d+)\s*(?:baños?|banos?|bath)', query_lower)
    if banios_match:
        filters["banios"] = int(banios_match.group(1))
        words_to_remove.append(banios_match.group(0))
    
    # Número de dormitorios
    dorm_match = re.search(r'\b(\d+)\s*(?:dormitorios?|dorm|habitaciones?)', query_lower)
    if dorm_match:
        filters["dormitorios"] = int(dorm_match.group(1))
        words_to_remove.append(dorm_match.group(0))

    # Rango de precio UF (entre X y Y UF, o X-Y UF)
    query, uf_filter = _extract_uf_range(query)
    if "precio_uf" in uf_filter:
        filters.update(uf_filter)

    # Filtros de superficie (m2 útiles / m2 total)
    query, area_filters = _extract_area_filters(query)
    if area_filters:
        filters.update(area_filters)
    
    # Remover palabras de filtros de la query, pero mantener palabras descriptivas
    query_clean = query
    for word in words_to_remove:
        query_clean = re.sub(rf'\b{re.escape(word)}\b', '', query_clean, flags=re.IGNORECASE)
    
    # Limpiar espacios múltiples y palabras vacías comunes
    query_clean = re.sub(r'\s+', ' ', query_clean).strip()
    # Remover palabras de conexión vacías si quedan solas
    query_clean = re.sub(r'\b(en|con|de|la|el|los|las)\b', '', query_clean, flags=re.IGNORECASE).strip()
    query_clean = re.sub(r'\s+', ' ', query_clean).strip()
    
    # Si la query queda muy corta o vacía, usar la original sin filtros de texto
    if len(query_clean.split()) < 2:
        query_clean = query
        # Solo remover operación y tipo si están explícitos
        for word in ["venta", "vender", "comprar", "arriendo", "arrendar", "alquiler"]:
            query_clean = re.sub(rf'\b{word}\b', '', query_clean, flags=re.IGNORECASE)
        query_clean = re.sub(r'\s+', ' ', query_clean).strip()
    
    return query_clean, filters


def search(query: str, top_k: int = 5):
    """Realiza una búsqueda semántica con filtros automáticos."""
    print(f"\n🔍 Búsqueda: '{query}'")
    
    # Extraer filtros de la consulta
    query_clean, filters = extract_filters(query)
    
    if filters:
        print(f"🔧 Filtros aplicados: {filters}")
        if query_clean != query:
            print(f"📝 Query para embedding: '{query_clean}'")
    print(f"📊 Mostrando top {top_k} resultados más relevantes\n")
    
    try:
        # Generar embedding de la consulta limpia
        query_vector = embedder.embed_text(query_clean if query_clean else query)
        
        # Buscar en Qdrant con filtros
        results = qdrant.search_similar(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_vector,
            limit=top_k,
            metadata_filter=filters if filters else None,
        )
        
        if not results:
            print("❌ No se encontraron resultados que coincidan con los filtros.")
            if filters:
                print("   Intenta relajar los filtros o verifica que existan propiedades con esos criterios.")
            return
        
        print(f"✅ Encontradas {len(results)} propiedades similares:\n")
        
        for i, hit in enumerate(results, 1):
            format_result(hit, i)
            
    except Exception as e:
        print(f"❌ Error en la búsqueda: {e}")
        import traceback
        traceback.print_exc()


def interactive_mode():
    """Modo interactivo para hacer múltiples búsquedas."""
    print("\n" + "="*70)
    print("🏡 BÚSQUEDA SEMÁNTICA DE PROPIEDADES INMOBILIARIAS")
    print("="*70)
    print("\nEjemplos de búsquedas:")
    print("  • 'casa en Buin con jardín'")
    print("  • 'venta casa en Lo Barnechea 4 baños'")
    print("  • 'arriendo departamento 3 dormitorios'")
    print("  • 'casa familiar con piscina'")
    print("\n💡 El sistema detecta automáticamente:")
    print("  - Operación: 'venta' o 'arriendo'")
    print("  - Tipo: 'casa' o 'departamento'")
    print("  - Comuna: nombres comunes (Lo Barnechea, Las Condes, etc.)")
    print("  - Características: número de baños/dormitorios")
    print("\n" + "="*70)
    
    while True:
        try:
            query = input("\n🔍 Ingresa tu búsqueda (o 'exit' para salir): ").strip()
            
            if query.lower() in ['exit', 'salir', 'quit', 'q']:
                print("\n¡Hasta luego! 👋")
                break
            
            if not query:
                print("Por favor ingresa una consulta válida.")
                continue
            
            search(query, top_k=5)
            
        except KeyboardInterrupt:
            print("\n\n¡Hasta luego! 👋")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    """Función principal."""
    if len(sys.argv) > 1:
        # Modo con argumento: búsqueda única
        query = " ".join(sys.argv[1:])
        search(query, top_k=5)
    else:
        # Modo interactivo
        interactive_mode()


if __name__ == "__main__":
    main()
