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
    if payload.get('anio'):
        print(f"📅 Año: {payload.get('anio')}")
    if payload.get('piso') is not None and payload.get('piso', 0) > 0:
        print(f"🏢 Piso: {payload.get('piso')}")
    gastos = payload.get('gastos_comunes')
    if gastos is not None and gastos > 0:
        print(f"📊 Gastos comunes: {gastos:,.0f}")

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
    Extrae rango de precio en UF desde la consulta.
    Soporta:
    - 'entre 20000 y 30000 uf' o '20000-30000 uf' -> precio entre min y max
    - 'desde 20000 hasta 30000 uf' -> mismo que entre
    - 'desde 25000 uf', 'desde los 25000 uf' -> precio >= X (mínimo)
    - 'más de 20000 uf', 'sobre 20000 uf' -> precio >= X
    - 'menos de 50000 uf', 'hasta 50000 uf' -> precio <= X
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)
    num = r"(\d+(?:[.,]\d+)?)"
    uf_suffix = r"\s*uf\b"

    # Formato: entre X y Y uf
    match_between = re.search(rf"entre\s+{num}\s+y\s+{num}{uf_suffix}", qn)
    if match_between:
        a = float(match_between.group(1).replace(",", "."))
        b = float(match_between.group(2).replace(",", "."))
        low, high = (a, b) if a <= b else (b, a)
        filters["precio_uf"] = {"gte": low, "lte": high}
        query_clean = re.sub(r"entre\s+\d+(?:[.,]\d+)?\s+y\s+\d+(?:[.,]\d+)?\s*uf\b", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Formato: desde X hasta Y uf
    match_desde_hasta = re.search(rf"desde\s+{num}\s+hasta\s+{num}{uf_suffix}", qn)
    if match_desde_hasta:
        a = float(match_desde_hasta.group(1).replace(",", "."))
        b = float(match_desde_hasta.group(2).replace(",", "."))
        low, high = (a, b) if a <= b else (b, a)
        filters["precio_uf"] = {"gte": low, "lte": high}
        query_clean = re.sub(r"desde\s+\d+(?:[.,]\d+)?\s+hasta\s+\d+(?:[.,]\d+)?\s*uf\b", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Formato: X-Y uf
    match_dash = re.search(rf"{num}\s*-\s*{num}{uf_suffix}", qn)
    if match_dash:
        a = float(match_dash.group(1).replace(",", "."))
        b = float(match_dash.group(2).replace(",", "."))
        low, high = (a, b) if a <= b else (b, a)
        filters["precio_uf"] = {"gte": low, "lte": high}
        query_clean = re.sub(r"\d+(?:[.,]\d+)?\s*-\s*\d+(?:[.,]\d+)?\s*uf\b", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Formato: desde X uf / desde los X uf (precio mínimo)
    match_desde = re.search(rf"desde\s+(?:los\s+)?{num}{uf_suffix}", qn)
    if match_desde:
        val = float(match_desde.group(1).replace(",", "."))
        filters["precio_uf"] = {"gte": val}
        query_clean = re.sub(r"desde\s+(?:los\s+)?\d+(?:[.,]\d+)?\s*uf\b", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Formato: más de X uf / sobre X uf / superior a X uf
    match_more = re.search(rf"(?:mas\s+de|sobre|superior\s+a)\s+{num}{uf_suffix}", qn)
    if match_more:
        val = float(match_more.group(1).replace(",", "."))
        filters["precio_uf"] = {"gte": val}
        query_clean = re.sub(r"(?:mas\s+de|sobre|superior\s+a)\s+\d+(?:[.,]\d+)?\s*uf\b", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Formato: menos de X uf / hasta X uf / inferior a X uf
    match_less = re.search(rf"(?:menos\s+de|hasta|inferior\s+a)\s+{num}{uf_suffix}", qn)
    if match_less:
        val = float(match_less.group(1).replace(",", "."))
        filters["precio_uf"] = {"lte": val}
        query_clean = re.sub(r"(?:menos\s+de|hasta|inferior\s+a)\s+\d+(?:[.,]\d+)?\s*uf\b", "", query_clean, flags=re.IGNORECASE)
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


def _extract_barrio_with_tolerance(query: str, barrios: list[str]) -> tuple[str, Dict[str, Any]]:
    """
    Detecta barrio exacto o aproximado en la consulta.
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)
    normalized_barrios = {b: _normalize_text(b) for b in barrios}

    for barrio, barrio_n in normalized_barrios.items():
        if barrio_n in qn:
            filters["barrio"] = barrio.title()
            query_clean = re.sub(rf"\b{re.escape(barrio)}\b", "", query_clean, flags=re.IGNORECASE)
            return query_clean, filters

    return query_clean, filters


def _extract_estacionamiento_filters(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae filtros de estacionamientos.
    - "N estacionamientos" -> exacto
    - "con estacionamiento" / "con estacionamientos" -> al menos 1
    - "más de N estacionamientos" -> gte N+1
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)

    # Más de N
    m_more = re.search(r"(?:mas\s+de|sobre)\s+(\d+)\s*estacionamientos?", qn)
    if m_more:
        val = int(m_more.group(1))
        filters["estacionamiento"] = {"gte": val + 1}
        query_clean = re.sub(r"(?:mas\s+de|sobre)\s+\d+\s*estacionamientos?", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Con estacionamiento(s)
    if re.search(r"\bcon\s+estacionamientos?\b", qn):
        filters["estacionamiento"] = {"gte": 1}
        query_clean = re.sub(r"\bcon\s+estacionamientos?\b", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # N estacionamientos (exacto)
    m_exact = re.search(r"\b(\d+)\s*estacionamientos?", qn)
    if m_exact:
        filters["estacionamiento"] = int(m_exact.group(1))
        query_clean = re.sub(r"\b\d+\s*estacionamientos?", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    return query_clean, filters


def _extract_bodega_filters(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae filtros de bodega.
    - "con bodega(s)" -> al menos 1
    - "N bodegas" -> exacto
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)

    if re.search(r"\bcon\s+bodegas?\b", qn):
        filters["bodega"] = {"gte": 1}
        query_clean = re.sub(r"\bcon\s+bodegas?\b", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    m_exact = re.search(r"\b(\d+)\s*bodegas?", qn)
    if m_exact:
        filters["bodega"] = int(m_exact.group(1))
        query_clean = re.sub(r"\b\d+\s*bodegas?", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    return query_clean, filters


def _extract_anio_filters(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae filtros por año de construcción/entrega.
    - "año N", "construido N", "entrega N" -> exacto
    - "después de N", "desde N" -> anio >= N
    - "antes de N" -> anio <= N
    - "entre N y M" -> anio en rango
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)

    # Entre N y M
    m_between = re.search(r"entre\s+(\d{4})\s+y\s+(\d{4})\s*(?:anios?|anos?|construccion)?", qn)
    if m_between:
        a, b = int(m_between.group(1)), int(m_between.group(2))
        low, high = (a, b) if a <= b else (b, a)
        filters["anio"] = {"gte": low, "lte": high}
        query_clean = re.sub(r"entre\s+\d{4}\s+y\s+\d{4}\s*(?:anios?|anos?|construccion)?", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Después de / desde
    m_after = re.search(r"(?:despues\s+de|desde)\s+(\d{4})\s*(?:anios?|anos?)?", qn)
    if m_after:
        filters["anio"] = {"gte": int(m_after.group(1))}
        query_clean = re.sub(r"(?:despues\s+de|desde)\s+\d{4}\s*(?:anios?|anos?)?", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Antes de
    m_before = re.search(r"antes\s+de\s+(\d{4})\s*(?:anios?|anos?)?", qn)
    if m_before:
        filters["anio"] = {"lte": int(m_before.group(1))}
        query_clean = re.sub(r"antes\s+de\s+\d{4}\s*(?:anios?|anos?)?", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Año N / construido N / entrega N (exacto)
    m_exact = re.search(r"(?:anio|construido|entrega)\s+(\d{4})", qn)
    if m_exact:
        filters["anio"] = int(m_exact.group(1))
        query_clean = re.sub(r"(?:anio|construido|entrega)\s+\d{4}", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    # Solo "2024" o "año 2024" ya cubierto arriba
    return query_clean, filters


def _extract_piso_filters(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae filtro por piso (para departamentos).
    - "piso N" -> exacto
    - "desde piso N" -> piso >= N
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)

    m_from = re.search(r"desde\s+piso\s+(\d+)", qn)
    if m_from:
        filters["piso"] = {"gte": int(m_from.group(1))}
        query_clean = re.sub(r"desde\s+piso\s+\d+", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    m_exact = re.search(r"\bpiso\s+(\d+)\b", qn)
    if m_exact:
        filters["piso"] = int(m_exact.group(1))
        query_clean = re.sub(r"\bpiso\s+\d+\b", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    return query_clean, filters


def _extract_gastos_comunes_filters(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae filtros por gastos comunes (en pesos).
    - "gastos comunes menos de N", "gastos hasta N"
    """
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)

    m_less = re.search(r"gastos\s+comunes?\s+(?:menos\s+de|hasta)\s+(\d+(?:[.,]\d+)?)\s*(?:mil|k|pesos)?", qn)
    if m_less:
        val = float(m_less.group(1).replace(",", "."))
        if "mil" in qn or "k" in qn:
            val = val * 1000
        filters["gastos_comunes"] = {"lte": val}
        query_clean = re.sub(r"gastos\s+comunes?\s+(?:menos\s+de|hasta)\s+\d+(?:[.,]\d+)?\s*(?:mil|k|pesos)?", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    m_more = re.search(r"gastos\s+comunes?\s+(?:mas\s+de|desde)\s+(\d+(?:[.,]\d+)?)\s*(?:mil|k|pesos)?", qn)
    if m_more:
        val = float(m_more.group(1).replace(",", "."))
        if "mil" in qn or "k" in qn:
            val = val * 1000
        filters["gastos_comunes"] = {"gte": val}
        query_clean = re.sub(r"gastos\s+comunes?\s+(?:mas\s+de|desde)\s+\d+(?:[.,]\d+)?\s*(?:mil|k|pesos)?", "", query_clean, flags=re.IGNORECASE)
        return query_clean, filters

    return query_clean, filters


def _extract_dormitorios_range(query: str) -> tuple[str, Dict[str, Any]]:
    """Soporta 'entre N y M dormitorios' además del exacto ya manejado en extract_filters."""
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)
    m = re.search(r"entre\s+(\d+)\s+y\s+(\d+)\s*(?:dormitorios?|dorm|habitaciones?)", qn)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        low, high = (a, b) if a <= b else (b, a)
        filters["dormitorios"] = {"gte": low, "lte": high}
        query_clean = re.sub(r"entre\s+\d+\s+y\s+\d+\s*(?:dormitorios?|dorm|habitaciones?)", "", query_clean, flags=re.IGNORECASE)
    return query_clean, filters


def _extract_banios_range(query: str) -> tuple[str, Dict[str, Any]]:
    """Soporta 'entre N y M baños' además del exacto."""
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)
    m = re.search(r"entre\s+(\d+)\s+y\s+(\d+)\s*(?:banos?|banios?|bath)", qn)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        low, high = (a, b) if a <= b else (b, a)
        filters["banios"] = {"gte": low, "lte": high}
        query_clean = re.sub(r"entre\s+\d+\s+y\s+\d+\s*(?:banos?|banios?|bath)", "", query_clean, flags=re.IGNORECASE)
    return query_clean, filters


def _extract_portal_filter(query: str) -> tuple[str, Dict[str, Any]]:
    """Filtro por portal (ej. 'portal inmobiliario')."""
    filters: Dict[str, Any] = {}
    query_clean = query
    qn = _normalize_text(query)
    if "portal inmobiliario" in qn or "portalinmobiliario" in qn:
        filters["portal"] = "Portal Inmobiliario"
        query_clean = re.sub(r"portal\s+inmobiliario|portalinmobiliario", "", query_clean, flags=re.IGNORECASE)
    return query_clean, filters


def extract_filters(query: str) -> tuple[str, Dict[str, Any]]:
    """
    Extrae filtros de metadata de la consulta y devuelve (query_limpia, filtros).
    Soporta filtro por todos los atributos de una propiedad:
    operación, tipo, comuna, barrio, precio UF, m² útiles/totales, dormitorios,
    baños, estacionamiento, bodega, año, piso, gastos comunes, portal.
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
        "buin", "colina", "chicureo", "la florida", "maipú", "puente alto",
        "vitacura", "la reina", "macul", "peñalolén", "huechuraba",
    ]
    query, comuna_filter = _extract_comuna_with_tolerance(query, comunas_comunes)
    if "comuna" in comuna_filter:
        filters.update(comuna_filter)

    # Barrio
    barrios_comunes = [
        "las condes", "vitacura", "lo barnechea", "providencia", "ñuñoa",
        "chicureo", "colina", "umbrales", "la dehesa", "el golf", "san damián",
    ]
    _, barrio_filter = _extract_barrio_with_tolerance(query, barrios_comunes)
    if "barrio" in barrio_filter:
        filters.update(barrio_filter)

    # Baños: primero rango ("entre N y M"), luego exacto
    _, banios_range = _extract_banios_range(query)
    if "banios" in banios_range:
        filters.update(banios_range)
    else:
        banios_match = re.search(r'\b(\d+)\s*(?:baños?|banos?|bath)', query_lower)
        if banios_match:
            filters["banios"] = int(banios_match.group(1))
            words_to_remove.append(banios_match.group(0))

    # Dormitorios: primero rango ("entre N y M"), luego exacto
    _, dorm_range = _extract_dormitorios_range(query)
    if "dormitorios" in dorm_range:
        filters.update(dorm_range)
    else:
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

    # Estacionamiento, bodega, año, piso, gastos comunes, portal
    _, est_filter = _extract_estacionamiento_filters(query)
    if est_filter:
        filters.update(est_filter)
    _, bodega_filter = _extract_bodega_filters(query)
    if bodega_filter:
        filters.update(bodega_filter)
    _, anio_filter = _extract_anio_filters(query)
    if anio_filter:
        filters.update(anio_filter)
    _, piso_filter = _extract_piso_filters(query)
    if piso_filter:
        filters.update(piso_filter)
    _, gastos_filter = _extract_gastos_comunes_filters(query)
    if gastos_filter:
        filters.update(gastos_filter)
    _, portal_filter = _extract_portal_filter(query)
    if portal_filter:
        filters.update(portal_filter)

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
    print("  • 'casa con bodega y 2 estacionamientos'")
    print("  • 'depto piso 5, gastos comunes menos de 100 mil'")
    print("  • 'entre 2 y 4 dormitorios, entre 20000 y 30000 uf'")
    print("\n💡 Filtros por atributos (detectados automáticamente):")
    print("  - Operación: venta / arriendo")
    print("  - Tipo: casa / departamento")
    print("  - Ubicación: comuna, barrio")
    print("  - Precio UF: 'entre X y Y uf', 'desde X hasta Y uf', 'más de X uf', 'menos de X uf', 'hasta X uf'")
    print("  - Superficie: m² útiles o totales (más/menos de X, entre X y Y)")
    print("  - Dormitorios y baños: número exacto o rango (entre N y M)")
    print("  - Estacionamiento: N estacionamientos, con estacionamiento")
    print("  - Bodega: con bodega, N bodegas")
    print("  - Año: año N, construido N, después/antes de N")
    print("  - Piso: piso N, desde piso N")
    print("  - Gastos comunes: menos de N / hasta N (pesos)")
    print("  - Portal: portal inmobiliario")
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
